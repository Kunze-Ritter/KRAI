"""Model evaluation and cross-validation."""

import logging
from typing import TYPE_CHECKING

import numpy as np
from sklearn.metrics import accuracy_score, auc, f1_score, precision_score, recall_score, roc_curve
from sklearn.model_selection import StratifiedKFold

if TYPE_CHECKING:
    from backend.pm.models.long_tail_classifier import LongTailClassifier
    from backend.pm.models.ticket import ServiceTicketFeatures

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Evaluate ML models with metrics, cross-validation, and ablation."""

    def compute_metrics(
        self,
        y_true: list[int],
        y_pred: list[int],
        y_prob: list[float] | None = None,
    ) -> dict[str, float]:
        """Compute classification metrics.

        Args:
            y_true: True binary labels
            y_pred: Predicted binary labels
            y_prob: Predicted probabilities (for AUC)

        Returns:
            Dict with accuracy, precision, recall, F1, AUC scores
        """
        y_true_np = np.array(y_true)
        y_pred_np = np.array(y_pred)

        metrics = {
            "accuracy": float(accuracy_score(y_true_np, y_pred_np)),
            "precision": float(precision_score(y_true_np, y_pred_np, zero_division=0)),
            "recall": float(recall_score(y_true_np, y_pred_np, zero_division=0)),
            "f1": float(f1_score(y_true_np, y_pred_np, zero_division=0)),
        }

        if y_prob is not None:
            y_prob_np = np.array(y_prob)
            fpr, tpr, _ = roc_curve(y_true_np, y_prob_np)
            metrics["auc"] = float(auc(fpr, tpr))

        return metrics

    def cross_validate(
        self,
        classifier: "LongTailClassifier",
        features: list["ServiceTicketFeatures"],
        labels: list[int],
        cv: int = 5,
    ) -> dict[str, list[float]]:
        """Perform stratified k-fold cross-validation.

        Args:
            classifier: Model to evaluate
            features: Feature vectors
            labels: Binary labels
            cv: Number of CV folds

        Returns:
            Dict mapping metric names to lists of fold scores
        """
        x_matrix = classifier._build_feature_matrix(features)
        y = np.array(labels)

        skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)
        cv_results = {
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1": [],
            "auc": [],
        }

        for fold_idx, (train_idx, test_idx) in enumerate(skf.split(x_matrix, y)):
            x_train, x_test = x_matrix[train_idx], x_matrix[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # Train on fold
            import xgboost as xgb

            fold_model = xgb.XGBClassifier(
                scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
                random_state=42,
                n_jobs=-1,
                verbosity=0,
            )
            fold_model.fit(x_train, y_train)

            # Evaluate on fold
            y_pred = fold_model.predict(x_test)
            y_prob = fold_model.predict_proba(x_test)[:, 1]

            fold_metrics = self.compute_metrics(y_test.tolist(), y_pred.tolist(), y_prob.tolist())
            for metric, value in fold_metrics.items():
                cv_results[metric].append(value)

            logger.info(f"Fold {fold_idx + 1}: {fold_metrics}")

        return cv_results

    def ablation_test(
        self,
        classifier: "LongTailClassifier",
        features: list["ServiceTicketFeatures"],
        labels: list[int],
    ) -> dict[str, dict[str, float]]:
        """Test feature importance via ablation.

        Args:
            classifier: Trained model
            features: Feature vectors
            labels: Binary labels

        Returns:
            Dict mapping feature names to accuracy drops
        """
        feature_names = [
            "repair_time_minutes",
            "problem_frequency",
            "part_replacement_count",
            "error_code_count",
            "manufacturer_encoded",
            *[f"error_code_top10_{i}" for i in range(10)],
            "device_age_months",
            "page_count",
            "service_history_count",
        ]

        x_full = classifier._build_feature_matrix(features)
        y = np.array(labels)

        # Get baseline accuracy
        baseline_pred = classifier._model.predict(x_full)
        baseline_accuracy = accuracy_score(y, baseline_pred)

        results = {}
        for feature_idx, feature_name in enumerate(feature_names):
            x_ablated = x_full.copy()
            x_ablated[:, feature_idx] = 0

            ablated_pred = classifier._model.predict(x_ablated)
            ablated_accuracy = accuracy_score(y, ablated_pred)
            accuracy_drop = baseline_accuracy - ablated_accuracy

            results[feature_name] = {
                "accuracy_drop": float(accuracy_drop),
                "baseline_accuracy": float(baseline_accuracy),
                "ablated_accuracy": float(ablated_accuracy),
            }

        return results
