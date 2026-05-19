"""Batch prediction service for long-tail classification."""

import json
import logging
from typing import Any

from backend.pm.features.feature_engineer import FeatureEngineer
from backend.pm.models.long_tail_classifier import LongTailClassifier
from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class PredictionService:
    """Run batch predictions and store to database."""

    def __init__(
        self,
        db_adapter: DatabaseAdapter,
        feature_engineer: FeatureEngineer,
        classifier: LongTailClassifier,
    ) -> None:
        """Initialize prediction service.

        Args:
            db_adapter: Database adapter
            feature_engineer: Feature engineer for extraction
            classifier: Trained model for predictions
        """
        self.db = db_adapter
        self.engineer = feature_engineer
        self.classifier = classifier

    async def run_batch(self, limit: int | None = None) -> dict[str, int]:
        """Run batch predictions on all tickets.

        Args:
            limit: Maximum tickets to predict on

        Returns:
            Dict with predicted, skipped, errors counts
        """
        logger.info("Starting batch predictions")

        # Get all tickets
        query = """
            SELECT id FROM krai_pm.service_tickets
            ORDER BY created_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        tickets = await self.db.fetch_all(query)
        logger.info(f"Found {len(tickets)} tickets for prediction")

        predicted_count = 0
        skipped_count = 0
        error_count = 0

        for ticket in tickets:
            ticket_id = ticket["id"]
            try:
                # Check if already predicted
                existing = await self.db.fetch_one(
                    """
                    SELECT id FROM krai_pm.predictions
                    WHERE metadata->>'ticket_id' = %s
                      AND prediction_type = 'long_tail'
                    """,
                    ticket_id,
                )

                if existing:
                    logger.debug(f"Ticket {ticket_id} already predicted, skipping")
                    skipped_count += 1
                    continue

                # Extract features
                features = await self.engineer.extract_features(ticket_id)
                if not features:
                    logger.warning(f"Failed to extract features for {ticket_id}")
                    skipped_count += 1
                    continue

                # Predict
                result = self.classifier.predict(features)

                # Save to database
                await self._save_prediction(ticket_id, result)
                predicted_count += 1

            except Exception as e:
                logger.error(f"Error predicting for {ticket_id}: {e}")
                error_count += 1

        logger.info(
            f"Batch predictions complete: {predicted_count} predicted, "
            f"{skipped_count} skipped, {error_count} errors"
        )

        return {
            "predicted": predicted_count,
            "skipped": skipped_count,
            "errors": error_count,
        }

    async def _save_prediction(self, ticket_id: str, result: Any) -> None:
        """Save prediction result to database.

        Args:
            ticket_id: Service ticket ID
            result: PredictionResult object
        """
        metadata = {
            "ticket_id": result.ticket_id,
            "is_common": result.is_common,
            "confidence": float(result.confidence),
        }

        await self.db.execute(
            """
            INSERT INTO krai_pm.predictions (
                prediction_type, model_name, model_version,
                confidence, risk_score, metadata,
                created_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                NOW()
            )
            """,
            "long_tail",
            result.model_name,
            result.model_version,
            float(result.confidence),
            float(result.confidence) if result.is_common else 1.0 - float(result.confidence),
            json.dumps(metadata),
        )

        logger.debug(f"Saved prediction for {ticket_id}")
