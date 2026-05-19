"""
Model evaluation framework for PM classification models.

Computes performance metrics (Accuracy, Precision, Recall, F1, AUC-ROC),
performs cross-validation, and conducts ablation testing to assess feature importance.
"""

from typing import TYPE_CHECKING

import numpy as np
from sklearn.metrics import accuracy_score, auc, f1_score, precision_score, recall_score, roc_curve
from sklearn.model_selection import StratifiedKFold

if TYPE_CHECKING:
    from backend.pm.models.long_tail_classifier import LongTailClassifier

from backend.pm.models.ticket import ServiceTicketFeatures


class ModelEvaluator:
    """
    Evaluates classification models on PM prediction tasks.

    Provides metrics computation, cross-validation, and ablation testing
    for model selection and feature importance analysis.
    """

    @staticmethod
    def compute_metrics(y_true: list[int], y_pred: list[int], y_prob: list[float] | None = None) -> dict[str, float]:
        """
        Compute classification metrics.

        Args:
            y_true: Ground truth binary labels (0 or 1)
            y_pred: Predicted binary labels
            y_prob: Predicted probabilities (for AUC-ROC)

        Returns:
            Dict with keys: accuracy, precision, recall, f1, auc_roc (if y_prob provided)
        """
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        }

        # Compute AUC-ROC if probabilities provided
        if y_prob is not None:
            y_prob_array = np.array(y_prob)
            fpr, tpr, _ = roc_curve(y_true, y_prob_array)
            metrics["auc_roc"] = float(auc(fpr, tpr))

        return metrics

    @staticmethod
    def cross_validate(
        classifier: "LongTailClassifier",
        features: list[ServiceTicketFeatures],
        labels: list[int],
        cv: int = 5,
    ) -> dict[str, list[float]]:
        """
        Perform k-fold stratified cross-validation.

        Args:
            classifier: LongTailClassifier instance to train/evaluate
            features: List of feature vectors
            labels: Binary labels (0 or 1)
            cv: Number of folds

        Returns:
            Dict with keys (accuracy, precision, recall, f1, auc_roc) mapping to fold scores
        """
        # Convert features to numpy array
        x = classifier._features_to_array(features)
        y = np.array(labels)

        # Initialize cross-validation splitter
        skf = StratifiedKFold(n_splits=cv, shuffle=False)
        fold_metrics = {
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1": [],
            "auc_roc": [],
        }

        for train_idx, val_idx in skf.split(x, y):
            x_train, x_val = x[train_idx], x[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Train on this fold
            classifier.fit_arrays(x_train, y_train)

            # Predict on validation set
            y_pred = classifier.predict_arrays(x_val)
            y_prob = classifier.predict_proba_arrays(x_val)

            # Compute metrics
            metrics = ModelEvaluator.compute_metrics(y_val.tolist(), y_pred, y_prob.tolist())
            for key, value in metrics.items():
                fold_metrics[key].append(value)

        return fold_metrics

    @staticmethod
    def ablation_test(
        classifier: "LongTailClassifier",
        features: list[ServiceTicketFeatures],
        labels: list[int],
    ) -> dict[str, dict[str, float]]:
        """
        Perform feature ablation testing.

        Trains model with each feature removed and measures accuracy drop
        to estimate feature importance.

        Args:
            classifier: LongTailClassifier instance
            features: List of feature vectors
            labels: Binary labels

        Returns:
            Dict mapping feature name to {baseline_accuracy, ablated_accuracy, importance}
        """
        # Feature names in order of features_to_array
        feature_names = [
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

        # Convert to arrays
        x = classifier._features_to_array(features)
        y = np.array(labels)

        # Get baseline accuracy
        classifier.fit_arrays(x, y)
        y_pred_baseline = classifier.predict_arrays(x)
        baseline_accuracy = float(accuracy_score(y, y_pred_baseline))

        # Ablate each feature
        ablation_results = {}
        for feature_idx, feature_name in enumerate(feature_names):
            # Create copy with feature zeroed out
            x_ablated = x.copy()
            x_ablated[:, feature_idx] = 0

            # Predict with ablated feature
            y_pred_ablated = classifier.predict_arrays_raw(x_ablated)
            ablated_accuracy = float(accuracy_score(y, y_pred_ablated))

            ablation_results[feature_name] = {
                "baseline_accuracy": baseline_accuracy,
                "ablated_accuracy": ablated_accuracy,
                "importance": baseline_accuracy - ablated_accuracy,
            }

        return ablation_results
