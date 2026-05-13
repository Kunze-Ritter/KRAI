"""
Tests for automatic performance metrics collection in BaseProcessor.safe_process().
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import BaseProcessor
from backend.core.types import ProcessingContext, ProcessingResult, ProcessingStatus


class ConcreteProcessor(BaseProcessor):
    """Minimal concrete processor for testing."""

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        return ProcessingResult(
            success=True,
            processor=self.name,
            status=ProcessingStatus.COMPLETED,
            data={"key": "value"},
            metadata={"document_id": str(context.document_id)},
            processing_time=0.0,
        )


class DictResultProcessor(BaseProcessor):
    """Processor returning dict payloads (legacy behavior)."""

    async def process(self, context: ProcessingContext):
        return {
            "success": True,
            "images_processed": 3,
            "metadata": {"document_id": str(context.document_id)},
        }


class FailingProcessor(BaseProcessor):
    """Processor raising an error to exercise ErrorLogger invocation."""

    async def process(self, context: ProcessingContext):
        raise ValueError("boom")


@pytest.fixture
def processor():
    return ConcreteProcessor("test_processor", {})


@pytest.fixture
def context():
    return ProcessingContext(
        document_id="doc-test-123",
        file_path="/tmp/test.pdf",
        document_type="application/pdf",
    )


# --- 7.1 Metrics collection integration ---


@pytest.mark.asyncio
async def test_safe_process_calls_collect_stage_metrics_on_success(processor, context):
    """Test that safe_process() calls collect_stage_metrics() and store_stage_metric() after successful processing."""
    mock_collector = MagicMock()
    mock_collector.collect_stage_metrics = AsyncMock()
    mock_collector.store_stage_metric = AsyncMock()
    processor.set_performance_collector(mock_collector)

    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=None):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    with patch.object(
                        processor,
                        "_set_completion_marker",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await processor.safe_process(context)

    assert result.success is True
    mock_collector.collect_stage_metrics.assert_called_once()
    call_args = mock_collector.collect_stage_metrics.call_args
    assert call_args[0][0] == "test_processor"
    assert call_args[0][1] == result
    assert call_args[0][1].processing_time >= 0
    mock_collector.store_stage_metric.assert_called_once()
    store_args = mock_collector.store_stage_metric.call_args
    assert store_args[1]["stage_name"] == "test_processor"
    assert store_args[1]["success"] is True


@pytest.mark.asyncio
async def test_safe_process_metrics_errors_do_not_break_processing(processor, context):
    """Test that metrics collection errors don't break processing."""
    mock_collector = MagicMock()
    mock_collector.collect_stage_metrics = AsyncMock(side_effect=Exception("Metrics backend unavailable"))
    mock_collector.store_stage_metric = AsyncMock()
    processor.set_performance_collector(mock_collector)

    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=None):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    with patch.object(
                        processor,
                        "_set_completion_marker",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await processor.safe_process(context)

    assert result.success is True
    mock_collector.collect_stage_metrics.assert_called_once()


@pytest.mark.asyncio
async def test_safe_process_no_collector_skips_metrics(processor, context):
    """Test that without performance collector, no metrics are collected."""
    assert processor._performance_collector is None

    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=None):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    with patch.object(
                        processor,
                        "_set_completion_marker",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await processor.safe_process(context)

    assert result.success is True


# --- 7.2 Timing ---


@pytest.mark.asyncio
async def test_safe_process_sets_processing_time(processor, context):
    """Test that processing_time is set on result."""
    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=None):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    with patch.object(
                        processor,
                        "_set_completion_marker",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await processor.safe_process(context)

    assert hasattr(result, "processing_time")
    assert isinstance(result.processing_time, int | float)
    assert result.processing_time >= 0


@pytest.mark.asyncio
async def test_safe_process_normalizes_dict_results(context):
    """Test that dict returns are normalized to ProcessingResult."""
    processor = DictResultProcessor("dict_result_processor", {})

    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=None):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    with patch.object(
                        processor,
                        "_set_completion_marker",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        result = await processor.safe_process(context)

    assert isinstance(result, ProcessingResult)
    assert result.success is True
    assert result.status == ProcessingStatus.COMPLETED
    assert result.data["images_processed"] == 3
    assert result.metadata["document_id"] == str(context.document_id)
    assert isinstance(result.processing_time, int | float)


@pytest.mark.asyncio
async def test_safe_process_logs_error_with_expected_keywords(context):
    """Ensure BaseProcessor uses ErrorLogger.log_error(error=..., retry_count=...)."""
    processor = FailingProcessor("failing_processor", {"service_name": "test"})
    mock_error_logger = MagicMock()
    mock_error_logger.log_error = AsyncMock(return_value="err_123")

    with patch.object(processor, "_check_completion_marker", return_value=None):
        with patch.object(processor, "_get_retry_orchestrator", return_value=None):
            with patch.object(processor, "_get_error_logger", return_value=mock_error_logger):
                with patch(
                    "backend.core.base_processor.RetryPolicyManager.get_policy",
                    new_callable=AsyncMock,
                    return_value=MagicMock(max_retries=0),
                ):
                    result = await processor.safe_process(context)

    assert result.success is False
    assert result.status == ProcessingStatus.FAILED
    assert mock_error_logger.log_error.await_count == 1
    kwargs = mock_error_logger.log_error.await_args.kwargs
    assert "error" in kwargs
    assert "retry_count" in kwargs
    assert "exception" not in kwargs
    assert "retry_attempt" not in kwargs
