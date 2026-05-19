"""
Unit tests for LongTailClassifier.

Tests model training, prediction, and persistence.
"""

from numbers import Number
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from backend.pm.models.long_tail_classifier import LongTailClassifier
from backend.pm.models.ticket import ServiceTicketFeatures


@pytest.fixture
def sample_features() -> list[ServiceTicketFeatures]:
    """Provide sample features for testing."""
    features = []
    for i in range(20):
        features.append(
            ServiceTicketFeatures(
                ticket_id=f"tk-{i:03d}",
                repair_time_minutes=30.0 + i,
                problem_frequency=10 + i,
                part_replacement_count=1 + (i % 3),
                error_code_count=2 + (i % 4),
                manufacturer_encoded=1 + (i % 3),
                error_code_top10=[int(j < 2) for j in range(10)],
                device_age_months=24.0 + i,
                page_count=100000 + i * 1000,
                service_history_count=2 + (i % 5),
            )
        )
    return features


@pytest.fixture
def sample_labels() -> list[int]:
    """Provide sample binary labels."""
    return [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0]


class TestLongTailClassifierTraining:
    """Tests for model training."""

    def test_fit_basic(self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]) -> None:
        """Test basic model training."""
        classifier = LongTailClassifier()
        metrics = classifier.fit(sample_features, sample_labels)

        assert "accuracy" in metrics
        assert "f1" in metrics
        assert 0 <= metrics["accuracy"] <= 1
        assert 0 <= metrics["f1"] <= 1

    def test_fit_imbalanced_classes(self, sample_features: list[ServiceTicketFeatures]) -> None:
        """Test training with imbalanced classes."""
        # 90% common, 10% long-tail
        labels = [1] * 18 + [0] * 2

        classifier = LongTailClassifier()
        metrics = classifier.fit(sample_features, labels)

        assert "accuracy" in metrics
        assert metrics["accuracy"] > 0


class TestLongTailClassifierPrediction:
    """Tests for prediction."""

    def test_predict_single(self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]) -> None:
        """Test prediction on single ticket."""
        classifier = LongTailClassifier()
        classifier.fit(sample_features, sample_labels)

        result = classifier.predict(sample_features[0])

        assert result.ticket_id == "tk-000"
        assert isinstance(result.is_common, bool)
        assert 0 <= result.confidence <= 1
        assert result.model_name == "long_tail_xgb_v1"

    def test_predict_batch(self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]) -> None:
        """Test batch prediction."""
        classifier = LongTailClassifier()
        classifier.fit(sample_features, sample_labels)

        results = classifier.predict_batch(sample_features[:5])

        assert len(results) == 5
        for result in results:
            assert result.model_name == "long_tail_xgb_v1"
            assert 0 <= result.confidence <= 1

    def test_predict_without_training(self, sample_features: list[ServiceTicketFeatures]) -> None:
        """Test that predict raises error if not trained."""
        classifier = LongTailClassifier()

        with pytest.raises(ValueError, match="not trained"):
            classifier.predict(sample_features[0])

    def test_predict_batch_without_training(self, sample_features: list[ServiceTicketFeatures]) -> None:
        """Test that predict_batch raises error if not trained."""
        classifier = LongTailClassifier()

        with pytest.raises(ValueError, match="not trained"):
            classifier.predict_batch(sample_features)


class TestLongTailClassifierPersistence:
    """Tests for model saving and loading."""

    def test_save_and_load(self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]) -> None:
        """Test saving and loading model."""
        with TemporaryDirectory() as tmpdir:
            # Train and save
            classifier = LongTailClassifier()
            classifier.fit(sample_features, sample_labels)
            model_path = Path(tmpdir) / "model.joblib"
            classifier.save(model_path)

            # Load and predict
            loaded_classifier = LongTailClassifier.load(model_path)
            result = loaded_classifier.predict(sample_features[0])

            assert result.ticket_id == "tk-000"
            assert 0 <= result.confidence <= 1

    def test_save_without_training(self) -> None:
        """Test that save raises error if not trained."""
        with TemporaryDirectory() as tmpdir:
            classifier = LongTailClassifier()
            model_path = Path(tmpdir) / "model.joblib"

            with pytest.raises(ValueError, match="not trained"):
                classifier.save(model_path)


class TestLongTailClassifierFeatureImportance:
    """Tests for feature importance."""

    def test_get_feature_importance(
        self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]
    ) -> None:
        """Test retrieving feature importances."""
        classifier = LongTailClassifier()
        classifier.fit(sample_features, sample_labels)

        importances = classifier.get_feature_importance()

        assert len(importances) == 18
        assert all(isinstance(v, Number) for v in importances.values())
        assert sum(importances.values()) > 0

    def test_get_feature_importance_without_training(self) -> None:
        """Test that get_feature_importance raises error if not trained."""
        classifier = LongTailClassifier()

        with pytest.raises(ValueError, match="not trained"):
            classifier.get_feature_importance()


class TestLongTailClassifierArrayMethods:
    """Tests for array-based methods used in CV."""

    def test_features_to_array_shape(self, sample_features: list[ServiceTicketFeatures]) -> None:
        """Test feature array conversion shape."""
        classifier = LongTailClassifier()
        x = classifier._features_to_array(sample_features)

        assert x.shape == (len(sample_features), 18)

    def test_fit_arrays(self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]) -> None:
        """Test training with numpy arrays."""
        classifier = LongTailClassifier()
        x = classifier._features_to_array(sample_features)
        y = np.array(sample_labels)

        classifier.fit_arrays(x, y)

        # Should be able to predict now
        y_pred = classifier.predict_arrays(x)
        assert y_pred.shape == (len(sample_features),)

    def test_predict_arrays_and_proba(
        self, sample_features: list[ServiceTicketFeatures], sample_labels: list[int]
    ) -> None:
        """Test prediction with numpy arrays."""
        classifier = LongTailClassifier()
        classifier.fit(sample_features, sample_labels)

        x = classifier._features_to_array(sample_features[:5])
        y_pred = classifier.predict_arrays(x)
        y_prob = classifier.predict_proba_arrays(x)

        assert y_pred.shape == (5,)
        assert y_prob.shape == (5,)
        assert all(0 <= p <= 1 for p in y_prob)
