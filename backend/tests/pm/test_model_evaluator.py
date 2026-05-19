"""
Unit tests for ModelEvaluator.

Tests metrics computation, cross-validation, and ablation testing.
"""

import pytest

from backend.pm.evaluation.model_evaluator import ModelEvaluator


class TestMetricsComputation:
    """Tests for metrics computation."""

    def test_compute_metrics_basic(self) -> None:
        """Test basic metrics computation."""
        y_true = [1, 1, 0, 0, 1, 0]
        y_pred = [1, 1, 0, 1, 1, 0]

        metrics = ModelEvaluator.compute_metrics(y_true, y_pred)

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert 0 <= metrics["accuracy"] <= 1
        assert 0 <= metrics["precision"] <= 1
        assert 0 <= metrics["recall"] <= 1
        assert 0 <= metrics["f1"] <= 1

    def test_compute_metrics_perfect_predictions(self) -> None:
        """Test metrics when predictions are perfect."""
        y_true = [1, 1, 0, 0]
        y_pred = [1, 1, 0, 0]

        metrics = ModelEvaluator.compute_metrics(y_true, y_pred)

        assert metrics["accuracy"] == 1.0
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0

    def test_compute_metrics_with_probabilities(self) -> None:
        """Test metrics with probability scores."""
        y_true = [1, 1, 0, 0, 1]
        y_pred = [1, 1, 0, 0, 1]
        y_prob = [0.9, 0.8, 0.2, 0.1, 0.95]

        metrics = ModelEvaluator.compute_metrics(y_true, y_pred, y_prob)

        assert "auc_roc" in metrics
        assert 0 <= metrics["auc_roc"] <= 1

    def test_compute_metrics_zero_division(self) -> None:
        """Test metrics with all zeros."""
        y_true = [0, 0, 0]
        y_pred = [0, 0, 0]

        metrics = ModelEvaluator.compute_metrics(y_true, y_pred)

        # Should handle gracefully with zero_division=0
        assert metrics["precision"] == 0.0


@pytest.mark.asyncio
class TestCrossValidation:
    """Tests for cross-validation."""

    async def test_cross_validate_basic(self) -> None:
        """Test basic cross-validation with real classifier."""
        from backend.pm.models.long_tail_classifier import LongTailClassifier
        from backend.pm.models.ticket import ServiceTicketFeatures

        # Create real classifier with real data
        classifier = LongTailClassifier()
        features = [
            ServiceTicketFeatures(
                ticket_id=f"tk-{i:03d}",
                repair_time_minutes=30.0 + i,
                problem_frequency=10 + i,
                part_replacement_count=1 + (i % 3),
                error_code_count=2 + (i % 4),
                manufacturer_encoded=1 + (i % 3),
                error_code_top10=[int(j < 2) for j in range(10)],
            )
            for i in range(10)
        ]
        labels = [1, 1, 0, 0, 1, 0, 1, 0, 1, 0]

        cv_results = ModelEvaluator.cross_validate(classifier, features, labels, cv=2)

        assert "accuracy" in cv_results
        assert "precision" in cv_results
        assert len(cv_results["accuracy"]) == 2  # 2 folds
        assert all(0 <= m <= 1 for metrics in cv_results.values() for m in metrics)


@pytest.mark.asyncio
class TestAblationTesting:
    """Tests for feature ablation."""

    async def test_ablation_test_basic(self) -> None:
        """Test basic feature ablation with real classifier."""
        from backend.pm.models.long_tail_classifier import LongTailClassifier
        from backend.pm.models.ticket import ServiceTicketFeatures

        # Create real classifier with real data
        classifier = LongTailClassifier()
        features = [
            ServiceTicketFeatures(
                ticket_id=f"tk-{i:03d}",
                repair_time_minutes=30.0 + i,
                problem_frequency=10 + i,
                part_replacement_count=1 + (i % 3),
                error_code_count=2 + (i % 4),
                manufacturer_encoded=1 + (i % 3),
                error_code_top10=[int(j < 2) for j in range(10)],
            )
            for i in range(8)
        ]
        labels = [1, 0, 1, 0, 1, 0, 1, 0]

        ablation_results = ModelEvaluator.ablation_test(classifier, features, labels)

        # Should have results for all 18 features
        assert len(ablation_results) == 18
        # Each feature should have baseline and ablated accuracy
        for feature_name, metrics in ablation_results.items():
            assert "baseline_accuracy" in metrics
            assert "ablated_accuracy" in metrics
            assert "importance" in metrics
            assert 0 <= metrics["baseline_accuracy"] <= 1
            assert 0 <= metrics["ablated_accuracy"] <= 1


class TestMetricsRanges:
    """Tests that metrics are always in valid ranges."""

    def test_metrics_always_in_range(self) -> None:
        """Test that all metrics stay within valid ranges."""
        test_cases = [
            ([1, 1, 1, 0], [1, 1, 0, 0]),  # 50% accuracy
            ([0, 0, 0, 0], [1, 1, 1, 1]),  # 0% accuracy
            ([1, 1, 1, 1], [1, 1, 1, 1]),  # 100% accuracy
        ]

        for y_true, y_pred in test_cases:
            metrics = ModelEvaluator.compute_metrics(y_true, y_pred)

            for key, value in metrics.items():
                assert 0 <= value <= 1, f"{key} out of range: {value}"
