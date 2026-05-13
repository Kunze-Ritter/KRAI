"""Alert manager for pipeline stage failures with severity-based notifications."""

import logging
from datetime import datetime
from typing import ClassVar

from backend.core.base_processor import ProcessingResult, Stage
from backend.core.types import ProcessingContext
from backend.services.alert_service import AlertService

LOGGER = logging.getLogger(__name__)


class StageAlertManager:
    """Manages alerts for pipeline stage failures and critical events."""

    # Alert severity mapping based on stage and error type
    STAGE_CRITICALITY: ClassVar = {
        Stage.TEXT_EXTRACTION: "critical",
        Stage.TABLE_EXTRACTION: "high",
        Stage.SVG_PROCESSING: "high",
        Stage.IMAGE_PROCESSING: "high",
        Stage.VISUAL_EMBEDDING: "high",
        Stage.LINK_EXTRACTION: "high",
        Stage.VIDEO_ENRICHMENT: "medium",
        Stage.CHUNK_PREPROCESSING: "medium",
        Stage.CLASSIFICATION: "medium",
        Stage.METADATA_EXTRACTION: "medium",
        Stage.PARTS_EXTRACTION: "medium",
        Stage.SERIES_DETECTION: "medium",
        Stage.STORAGE: "high",
        Stage.EMBEDDING: "critical",
        Stage.SEARCH_INDEXING: "medium",
    }

    # Error type severity multiplier
    ERROR_SEVERITY: ClassVar = {
        "transient": "low",  # Retryable errors
        "permanent": "high",  # Won't retry
        "timeout": "medium",  # Time-based
        "resource": "high",  # Resource exhaustion
        "data_validation": "medium",  # Invalid input
    }

    def __init__(self, alert_service: AlertService | None = None):
        """Initialize stage alert manager."""
        self.alert_service = alert_service
        self.logger = LOGGER

    async def alert_stage_failure(
        self,
        stage_name: str,
        context: ProcessingContext,
        error: Exception,
        is_transient: bool = False,
        retry_attempt: int = 0,
        max_retries: int = 3,
    ) -> bool:
        """
        Alert on stage failure with appropriate severity and details.

        Args:
            stage_name: Name of the failed stage
            context: Processing context
            error: The exception that occurred
            is_transient: Whether error is retryable
            retry_attempt: Current retry attempt number
            max_retries: Maximum retries for this stage

        Returns:
            bool: True if alert was sent successfully
        """
        if not self.alert_service:
            self.logger.warning("AlertService not available for stage failure alert")
            return False

        try:
            # Determine severity
            stage = self._get_stage_from_name(stage_name)
            base_severity = self.STAGE_CRITICALITY.get(stage, "medium")
            error_severity = "low" if is_transient else "high"

            # Upgrade severity if final attempt failing
            if retry_attempt >= max_retries:
                severity = "critical" if base_severity == "critical" else "high"
            else:
                severity = "medium" if error_severity == "low" else base_severity

            # Build alert message
            error_type = error.__class__.__name__
            error_msg = str(error)[:200]  # Truncate long messages

            message = (
                f"Stage {stage_name} failed on document {context.document_id}\n"
                f"Error: {error_type}: {error_msg}\n"
                f"Attempt: {retry_attempt + 1}/{max_retries + 1}"
            )

            # Queue alert with AlertService format
            alert_result = await self.alert_service.queue_alert(
                error_data={
                    "error_type": error_type,
                    "stage_name": stage_name,
                    "severity": severity,
                    "error_message": message,
                    "document_id": str(context.document_id),
                    "correlation_id": context.correlation_id,
                    "context": {
                        "is_transient": is_transient,
                        "retry_attempt": retry_attempt,
                        "max_retries": max_retries,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )

            if alert_result:
                self.logger.info(f"Alert queued for stage {stage_name} failure on document {context.document_id}")
                return True

            self.logger.warning(f"Failed to queue alert for stage {stage_name} failure")
            return False

        except Exception as e:
            self.logger.error(f"Error sending stage failure alert: {e}", exc_info=True)
            return False

    async def alert_stage_success(
        self,
        stage_name: str,
        context: ProcessingContext,
        result: ProcessingResult,
    ) -> bool:
        """
        Alert on stage success (optional, for critical stages).

        Args:
            stage_name: Name of the successful stage
            context: Processing context
            result: Processing result

        Returns:
            bool: True if alert was sent
        """
        if not self.alert_service:
            return False

        # Only alert on success for critical stages after failures
        stage = self._get_stage_from_name(stage_name)
        if self.STAGE_CRITICALITY.get(stage) != "critical":
            return True  # Skip for non-critical stages

        # Check if there were previous failures (via context)
        if not hasattr(context, "previous_failures") or not context.previous_failures:
            return True  # Skip if no previous failures

        try:
            message = f"Stage {stage_name} recovered successfully for document {context.document_id}"

            await self.alert_service.queue_alert(
                error_data={
                    "error_type": "stage_recovered",
                    "stage_name": stage_name,
                    "severity": "info",
                    "error_message": message,
                    "document_id": str(context.document_id),
                    "correlation_id": context.correlation_id,
                    "context": {
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"Error sending stage recovery alert: {e}", exc_info=True)
            return False

    async def alert_pipeline_completion(
        self,
        document_id: str,
        total_stages: int,
        successful_stages: int,
        failed_stages: int,
        correlation_id: str,
    ) -> bool:
        """
        Alert on pipeline completion with summary.

        Args:
            document_id: Document being processed
            total_stages: Total number of stages
            successful_stages: Number of successful stages
            failed_stages: Number of failed stages
            correlation_id: Correlation ID for the run

        Returns:
            bool: True if alert was sent
        """
        if not self.alert_service:
            return False

        try:
            if failed_stages == 0:
                severity = "info"
                status_text = "COMPLETE"
            elif failed_stages <= 2:
                severity = "medium"
                status_text = "PARTIAL"
            else:
                severity = "high"
                status_text = "FAILED"

            message = (
                f"Pipeline {status_text} for document {document_id}\n"
                f"Success: {successful_stages}/{total_stages} stages\n"
                f"Failed: {failed_stages} stages"
            )

            await self.alert_service.queue_alert(
                error_data={
                    "error_type": "pipeline_completion",
                    "stage_name": "pipeline",
                    "severity": severity,
                    "error_message": message,
                    "document_id": str(document_id),
                    "correlation_id": correlation_id,
                    "context": {
                        "total_stages": total_stages,
                        "successful_stages": successful_stages,
                        "failed_stages": failed_stages,
                        "status": status_text,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"Error sending pipeline completion alert: {e}", exc_info=True)
            return False

    @staticmethod
    def _get_stage_from_name(stage_name: str) -> Stage | None:
        """Convert stage name string to Stage enum."""
        try:
            # Convert snake_case to UPPER_CASE
            stage_key = stage_name.upper().replace("-", "_")
            return Stage[stage_key]
        except (KeyError, AttributeError):
            return None
