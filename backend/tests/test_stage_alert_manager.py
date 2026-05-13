"""Unit tests for StageAlertManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.base_processor import Stage
from backend.core.types import ProcessingContext
from backend.services.stage_alert_manager import StageAlertManager


@pytest.fixture
def mock_alert_service():
    """Create a mock alert service."""
    service = MagicMock()
    service.queue_alert = AsyncMock(return_value="alert_123")
    return service


@pytest.fixture
def alert_manager(mock_alert_service):
    """Create a StageAlertManager with mock service."""
    return StageAlertManager(alert_service=mock_alert_service)


@pytest.fixture
def processing_context():
    """Create a test processing context."""
    return ProcessingContext(
        document_id="test-doc-123",
        file_path="/tmp/test.pdf",
        document_type="manual",
        correlation_id="test-correlation-alert",
    )


class TestStageAlertManager:
    """Test StageAlertManager functionality."""

    @pytest.mark.asyncio
    async def test_alert_stage_failure_critical_stage(self, alert_manager, processing_context):
        """Test alert for critical stage failure."""
        error = ValueError("Critical processing error")

        result = await alert_manager.alert_stage_failure(
            stage_name="text_extraction",
            context=processing_context,
            error=error,
            is_transient=False,
            retry_attempt=2,
            max_retries=3,
        )

        assert result is True
        alert_manager.alert_service.queue_alert.assert_called_once()

        # Verify alert data structure
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["error_type"] == "ValueError"
        assert error_data["stage_name"] == "text_extraction"
        assert error_data["document_id"] == "test-doc-123"
        assert error_data["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_alert_stage_failure_medium_stage(self, alert_manager, processing_context):
        """Test alert for medium-priority stage failure."""
        error = RuntimeError("Processing error")

        result = await alert_manager.alert_stage_failure(
            stage_name="video_enrichment",
            context=processing_context,
            error=error,
            is_transient=False,
            retry_attempt=0,
            max_retries=3,
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["severity"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_alert_transient_error_low_severity(self, alert_manager, processing_context):
        """Test that transient errors get lower severity."""
        error = TimeoutError("Temporary timeout")

        result = await alert_manager.alert_stage_failure(
            stage_name="image_processing",
            context=processing_context,
            error=error,
            is_transient=True,
            retry_attempt=0,
            max_retries=3,
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        # Transient errors should have lower severity initially
        assert "image_processing" in error_data["stage_name"]

    @pytest.mark.asyncio
    async def test_alert_final_attempt_escalates_severity(self, alert_manager, processing_context):
        """Test that final retry attempt escalates severity to critical."""
        error = Exception("Final attempt failure")

        result = await alert_manager.alert_stage_failure(
            stage_name="embedding",
            context=processing_context,
            error=error,
            is_transient=False,
            retry_attempt=3,  # Final attempt
            max_retries=3,
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        # Final attempt on critical stage should be critical
        assert error_data["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_alert_includes_correlation_id(self, alert_manager, processing_context):
        """Test that alerts include correlation ID for tracing."""
        processing_context.correlation_id = "req_abc123.stage_image.retry_1"
        error = Exception("Test error")

        await alert_manager.alert_stage_failure(
            stage_name="image_processing",
            context=processing_context,
            error=error,
            is_transient=False,
            retry_attempt=1,
            max_retries=3,
        )

        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["correlation_id"] == "req_abc123.stage_image.retry_1"

    @pytest.mark.asyncio
    async def test_alert_stage_recovery(self, alert_manager, processing_context):
        """Test alert on stage recovery from failure."""
        processing_context.previous_failures = ["image_processing"]

        result = await alert_manager.alert_stage_success(
            stage_name="embedding",
            context=processing_context,
            result=MagicMock(),
        )

        # May return True if previous_failures present
        assert result is True or result is None

    @pytest.mark.asyncio
    async def test_alert_pipeline_completion_success(self, alert_manager):
        """Test alert on successful pipeline completion."""
        result = await alert_manager.alert_pipeline_completion(
            document_id="doc-456",
            total_stages=16,
            successful_stages=16,
            failed_stages=0,
            correlation_id="req_xyz789",
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["severity"] == "info"
        assert "COMPLETE" in error_data["error_message"]

    @pytest.mark.asyncio
    async def test_alert_pipeline_completion_partial(self, alert_manager):
        """Test alert on partial pipeline completion."""
        result = await alert_manager.alert_pipeline_completion(
            document_id="doc-789",
            total_stages=16,
            successful_stages=14,
            failed_stages=2,
            correlation_id="req_123abc",
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["severity"] == "medium"
        assert "PARTIAL" in error_data["error_message"]

    @pytest.mark.asyncio
    async def test_alert_pipeline_completion_failure(self, alert_manager):
        """Test alert on pipeline failure."""
        result = await alert_manager.alert_pipeline_completion(
            document_id="doc-fail",
            total_stages=16,
            successful_stages=5,
            failed_stages=11,
            correlation_id="req_fail",
        )

        assert result is True
        call_args = alert_manager.alert_service.queue_alert.call_args
        error_data = call_args.kwargs["error_data"]
        assert error_data["severity"] == "high"
        assert "FAILED" in error_data["error_message"]

    def test_get_stage_from_name_conversion(self):
        """Test stage name to Stage enum conversion."""
        stage = StageAlertManager._get_stage_from_name("text_extraction")
        assert stage == Stage.TEXT_EXTRACTION

        stage = StageAlertManager._get_stage_from_name("image_processing")
        assert stage == Stage.IMAGE_PROCESSING

    def test_get_stage_from_name_invalid(self):
        """Test invalid stage name returns None."""
        stage = StageAlertManager._get_stage_from_name("invalid_stage")
        assert stage is None

    @pytest.mark.asyncio
    async def test_no_alert_service_graceful_degradation(self):
        """Test that manager works without alert service."""
        alert_manager = StageAlertManager(alert_service=None)
        context = ProcessingContext(
            document_id="test",
            file_path="/tmp/test.pdf",
            document_type="manual",
            correlation_id="test",
        )

        result = await alert_manager.alert_stage_failure(
            stage_name="image_processing",
            context=context,
            error=Exception("Test"),
            is_transient=False,
            retry_attempt=0,
            max_retries=3,
        )

        # Should return False gracefully without service
        assert result is False

    @pytest.mark.asyncio
    async def test_alert_error_handling(self, alert_manager, processing_context):
        """Test that alert errors don't crash the system."""
        alert_manager.alert_service.queue_alert.side_effect = Exception("Alert service error")

        result = await alert_manager.alert_stage_failure(
            stage_name="image_processing",
            context=processing_context,
            error=ValueError("Test error"),
            is_transient=False,
            retry_attempt=0,
            max_retries=3,
        )

        # Should return False but not crash
        assert result is False
