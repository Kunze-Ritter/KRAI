"""
Batch prediction service for PM long-tail classification.

Loads all unpredicted tickets, runs them through the classifier,
and stores results in krai_pm.predictions table.
"""

from backend.pm.features.feature_engineer import FeatureEngineer
from backend.pm.models.long_tail_classifier import LongTailClassifier
from backend.pm.models.ticket import PredictionResult
from backend.services.database_adapter import DatabaseAdapter


class PredictionService:
    """
    Batch prediction service for long-tail classification.

    Loads tickets without predictions, runs classifier, and persists results
    to database with idempotency checks (skip tickets already predicted).
    """

    def __init__(
        self,
        db_adapter: DatabaseAdapter,
        feature_engineer: FeatureEngineer,
        classifier: LongTailClassifier,
    ) -> None:
        """
        Initialize prediction service.

        Args:
            db_adapter: Database adapter for querying and storing predictions
            feature_engineer: Feature extraction service
            classifier: Trained LongTailClassifier
        """
        self.db = db_adapter
        self.feature_engineer = feature_engineer
        self.classifier = classifier

    async def run_batch(self, limit: int | None = None) -> dict[str, int]:
        """
        Run batch predictions on unpredicted tickets.

        Loads tickets without existing predictions in krai_pm.predictions,
        extracts features, runs classifier, and stores results.
        Idempotent: skips tickets already predicted.

        Args:
            limit: Maximum number of tickets to predict (None = all)

        Returns:
            Dict with keys:
            - 'predicted': Number of tickets successfully predicted
            - 'skipped': Number of tickets already predicted
            - 'errors': Number of tickets that failed to predict
        """
        # Get all ticket IDs without predictions
        unpredicted_ticket_ids = await self._get_unpredicted_tickets(limit)

        # Extract features for unpredicted tickets
        features_list = []
        for ticket_id in unpredicted_ticket_ids:
            try:
                features = await self.feature_engineer.extract_features(ticket_id)
                features_list.append(features)
            except Exception as e:
                # Log error and continue to next ticket
                print(f"Error extracting features for {ticket_id}: {e}")
                continue

        # Run predictions
        predicted_count = 0
        error_count = 0
        for features in features_list:
            try:
                result = self.classifier.predict(features)
                await self._save_prediction(result)
                predicted_count += 1
            except Exception as e:
                # Log error and continue to next prediction
                print(f"Error predicting for {features.ticket_id}: {e}")
                error_count += 1

        # Calculate skipped count (tickets that weren't in our unpredicted list)
        # This is implicit - tickets already in krai_pm.predictions
        skipped_count = len(unpredicted_ticket_ids) - len(features_list) - error_count

        return {
            "predicted": predicted_count,
            "skipped": skipped_count,
            "errors": error_count,
        }

    async def _get_unpredicted_tickets(self, limit: int | None = None) -> list[str]:
        """
        Get all ticket IDs without existing predictions.

        Queries krai_pm.service_tickets for tickets that don't have
        a corresponding entry in krai_pm.predictions.

        Args:
            limit: Maximum number of tickets to return

        Returns:
            List of ticket IDs without predictions
        """
        query = """
            SELECT st.id
            FROM krai_pm.service_tickets st
            LEFT JOIN krai_pm.predictions p ON st.id = p.metadata->>'ticket_id'
            WHERE p.id IS NULL
        """
        if limit:
            query += f" LIMIT {limit}"

        rows = await self.db.fetch_all(query)
        return [row["id"] for row in rows]

    async def _save_prediction(self, result: PredictionResult) -> None:
        """
        Save prediction result to krai_pm.predictions table.

        Args:
            result: PredictionResult object from classifier
        """
        query = """
            INSERT INTO krai_pm.predictions (
                prediction_type, model_name, model_version, confidence, risk_score, metadata
            ) VALUES (
                'long_tail',
                %s, %s, %s, %s,
                %s
            )
        """

        # Risk score is inverse of confidence (0 = certain common, 1 = certain long-tail)
        risk_score = 1.0 - result.confidence if result.is_common else result.confidence

        metadata = {
            "ticket_id": result.ticket_id,
            "is_common": result.is_common,
            "confidence": result.confidence,
        }

        await self.db.execute(
            query,
            result.model_name,
            result.model_version,
            result.confidence,
            risk_score,
            metadata,
        )
