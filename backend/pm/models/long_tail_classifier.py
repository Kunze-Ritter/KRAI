"""
Long-tail classification model for PM tickets.

Binary classifier to distinguish Common problems (top 20) from Long-Tail (rare)
problems using XGBoost. Trained on service ticket features with 5-fold CV.
"""

from pathlib import Path

import joblib
import numpy as np
from xgboost import XGBClassifier

from backend.pm.models.ticket import PredictionResult, ServiceTicketFeatures


class LongTailClassifier:
    """
    Binary XGBoost classifier for Common vs. Long-Tail problem classification.

    Common: Problem appears in top 20 problem_short values by frequency.
    Long-Tail: All other problems (rare).

    Attributes:
        MODEL_NAME: Fixed model identifier
        MODEL_VERSION: Semantic version
        TOP_N_COMMON: Number of top problems considered "common"
    """

    MODEL_NAME = "long_tail_xgb_v1"
    MODEL_VERSION = "1.0.0"
    TOP_N_COMMON = 20

    def __init__(self, threshold: int | None = None) -> None:
        """
        Initialize classifier.

        Args:
            threshold: Number of top problems to consider "common" (default: TOP_N_COMMON)
        """
        self.threshold = threshold or self.TOP_N_COMMON
        self._model: XGBClassifier | None = None
        self._feature_names: list[str] = [
            "repair_time_minutes",
            "problem_frequency",
            "part_replacement_count",
            "error_code_count",
            "manufacturer_encoded",
            "error_code_top10[0]",
            "error_code_top10[1]",
            "error_code_top10[2]",
            "error_code_top10[3]",
            "error_code_top10[4]",
            "error_code_top10[5]",
            "error_code_top10[6]",
            "error_code_top10[7]",
            "error_code_top10[8]",
            "error_code_top10[9]",
            "device_age_months",
            "page_count",
            "service_history_count",
        ]

    def fit(
        self,
        features: list[ServiceTicketFeatures],
        labels: list[int],
    ) -> dict[str, float]:
        """
        Train classifier on feature vectors and labels.

        Args:
            features: List of ServiceTicketFeatures
            labels: Binary labels (1=Common, 0=Long-Tail)

        Returns:
            Dict with training metrics (accuracy, f1, auc_roc)
        """
        # Convert to numpy arrays
        x = self._features_to_array(features)
        y = np.array(labels)

        # Compute class weights for imbalance handling
        class_counts = np.bincount(y)
        scale_pos_weight = class_counts[0] / class_counts[1] if class_counts[1] > 0 else 1

        # Initialize and train XGBoost model
        self._model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            verbosity=0,
        )
        self._model.fit(x, y, verbose=False)

        # Return training metrics
        y_pred = self._model.predict(x)
        y_prob = self._model.predict_proba(x)[:, 1]

        from backend.pm.evaluation.model_evaluator import ModelEvaluator

        return ModelEvaluator.compute_metrics(y.tolist(), y_pred.tolist(), y_prob.tolist())

    def predict(self, features: ServiceTicketFeatures) -> PredictionResult:
        """
        Predict on a single ticket.

        Args:
            features: ServiceTicketFeatures for one ticket

        Returns:
            PredictionResult with is_common and confidence
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")

        x = self._features_to_array([features])
        prob = self._model.predict_proba(x)[0, 1]  # Probability of positive class
        is_common = bool(self._model.predict(x)[0])

        return PredictionResult(
            ticket_id=features.ticket_id,
            is_common=is_common,
            confidence=float(prob),
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
        )

    def predict_batch(self, features: list[ServiceTicketFeatures]) -> list[PredictionResult]:
        """
        Predict on multiple tickets.

        Args:
            features: List of ServiceTicketFeatures

        Returns:
            List of PredictionResult objects
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")

        x = self._features_to_array(features)
        predictions = self._model.predict(x)
        probabilities = self._model.predict_proba(x)[:, 1]

        results = []
        for feature, pred, prob in zip(features, predictions, probabilities):
            results.append(
                PredictionResult(
                    ticket_id=feature.ticket_id,
                    is_common=bool(pred),
                    confidence=float(prob),
                    model_name=self.MODEL_NAME,
                    model_version=self.MODEL_VERSION,
                )
            )

        return results

    def save(self, path: str | Path) -> None:
        """
        Save trained model to disk.

        Args:
            path: Path to save model to

        Raises:
            ValueError: If model not trained
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")

        joblib.dump(self._model, str(path))

    @classmethod
    def load(cls, path: str | Path) -> "LongTailClassifier":
        """
        Load trained model from disk.

        Args:
            path: Path to load model from

        Returns:
            LongTailClassifier instance with loaded model
        """
        classifier = cls()
        classifier._model = joblib.load(str(path))
        return classifier

    def get_feature_importance(self) -> dict[str, float]:
        """
        Get feature importances from trained model.

        Returns:
            Dict mapping feature name to importance score

        Raises:
            ValueError: If model not trained
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")

        importances = self._model.feature_importances_
        return dict(zip(self._feature_names, importances))

    @staticmethod
    def build_labels(features: list[ServiceTicketFeatures], top_problems: list[str]) -> list[int]:
        """
        Build binary labels from features and top problems list.

        Args:
            features: List of ServiceTicketFeatures
            top_problems: List of problem_short values considered "common"

        Returns:
            List of binary labels (1=Common, 0=Long-Tail)
        """
        labels = []
        for feature in features:
            # Note: ServiceTicketFeatures doesn't have problem_short directly
            # In actual usage, need to match features to problem_short via database
            # This is a placeholder that would be filled in during training
            labels.append(0)  # Default to long-tail
        return labels

    def _features_to_array(self, features: list[ServiceTicketFeatures]) -> np.ndarray:
        """
        Convert ServiceTicketFeatures list to numpy array for model input.

        Args:
            features: List of ServiceTicketFeatures

        Returns:
            Numpy array of shape (n_samples, 18)
        """
        rows = []
        for f in features:
            row = [
                f.repair_time_minutes or 0,
                f.problem_frequency,
                f.part_replacement_count,
                f.error_code_count,
                f.manufacturer_encoded,
                *f.error_code_top10,
                f.device_age_months or 0,
                f.page_count or 0,
                f.service_history_count or 0,
            ]
            rows.append(row)

        return np.array(rows, dtype=np.float32)

    def predict_arrays(self, x: np.ndarray) -> np.ndarray:
        """
        Predict using raw numpy array (for testing/CV).

        Args:
            x: Numpy array of shape (n_samples, 18)

        Returns:
            Array of predictions (0 or 1)
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self._model.predict(x)

    def predict_proba_arrays(self, x: np.ndarray) -> np.ndarray:
        """
        Get prediction probabilities using raw numpy array.

        Args:
            x: Numpy array of shape (n_samples, 18)

        Returns:
            Array of probabilities for positive class
        """
        if self._model is None:
            raise ValueError("Model not trained. Call fit() first.")
        return self._model.predict_proba(x)[:, 1]

    def fit_arrays(self, x: np.ndarray, y: np.ndarray) -> None:
        """
        Train on raw numpy arrays (for CV).

        Args:
            x: Features array of shape (n_samples, 18)
            y: Labels array of shape (n_samples,)
        """
        class_counts = np.bincount(y)
        scale_pos_weight = class_counts[0] / class_counts[1] if class_counts[1] > 0 else 1

        self._model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            verbosity=0,
        )
        self._model.fit(x, y, verbose=False)

    def predict_arrays_raw(self, x: np.ndarray) -> np.ndarray:
        """
        Predict without model state check (for ablation testing).

        Args:
            x: Numpy array of shape (n_samples, 18)

        Returns:
            Array of predictions
        """
        if self._model is None:
            return np.zeros(x.shape[0], dtype=int)
        return self._model.predict(x)
