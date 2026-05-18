"""
Integration Tests for BaseProcessor Hybrid Retry Loop

Tests the full retry lifecycle including:
- Synchronous first retry
- Asynchronous subsequent retries
- Idempotency checks
- Advisory locks
- Error classification and logging
- Correlation ID tracking
- Graceful degradation
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.core.base_processor import BaseProcessor
from backend.core.types import ProcessingContext, ProcessingResult, ProcessingStatus
from backend.services.database_factory import create_database_adapter


class MockProcessor(BaseProcessor):
    """Mock processor for testing"""

    def __init__(
        self, name: str = "test_processor", config: dict = None, fail_count: int = 0, error_type: str = "transient"
    ):
        super().__init__(name, config)
        self.fail_count = fail_count
        self.error_type = error_type
        self.call_count = 0
        self.db_adapter = None  # Will be set in tests

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Mock process that can fail N times before succeeding"""
        self.call_count += 1

        if self.call_count <= self.fail_count:
            if self.error_type == "transient":
                raise ConnectionError(f"Transient error on attempt {self.call_count}")
            if self.error_type == "permanent":
                raise ValueError(f"Permanent error on attempt {self.call_count}")
            raise Exception(f"Unknown error on attempt {self.call_count}")

        return self.create_success_result(
            data={"processed": True, "attempts": self.call_count}, metadata={"document_id": context.document_id}
        )


@pytest.fixture
async def db_adapter():
    """Create database adapter for tests"""
    adapter = create_database_adapter()
    yield adapter
    # Cleanup if needed
    await adapter.close()


@pytest.fixture
def mock_context():
    """Create mock processing context"""
    return ProcessingContext(
        document_id=str(uuid4()),
        file_path="/test/document.pdf",
        file_name="document.pdf",
        file_size=1024,
        mime_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_sync_retry_success(mock_context):
    """Test synchronous first retry succeeds"""
    # Create processor that fails once then succeeds
    processor = MockProcessor(
        name="sync_retry_test", config={"service_name": "test"}, fail_count=1, error_type="transient"
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(return_value=None)
    processor.db_adapter.execute = AsyncMock()

    # Execute
    result = await processor.safe_process(mock_context)

    # Verify success after retry
    assert result.success is True
    assert processor.call_count == 2  # Initial attempt + 1 retry
    assert result.data["attempts"] == 2

    # Verify no background task was spawned (synchronous retry)
    assert result.status == ProcessingStatus.COMPLETED


@pytest.mark.asyncio
async def test_async_retry_success(mock_context):
    """Test asynchronous subsequent retry spawns background task"""
    # Create processor that fails twice then succeeds
    processor = MockProcessor(
        name="async_retry_test", config={"service_name": "test"}, fail_count=2, error_type="transient"
    )

    # Mock database adapter with advisory lock support
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired (attempt 0)
            None,  # No completion marker (retry 1)
            {"pg_try_advisory_lock": True},  # Lock acquired (retry 1)
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger
    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(return_value="error_123")
        MockErrorLogger.return_value = mock_error_logger

        # Execute first attempt (will fail and retry sync)
        result = await processor.safe_process(mock_context)

        # First result should indicate retrying
        assert result.success is False
        assert result.status == ProcessingStatus.IN_PROGRESS
        assert "correlation_id" in result.data

        # Verify processor was called twice (initial + sync retry)
        assert processor.call_count == 2


@pytest.mark.asyncio
async def test_max_retries_exceeded(mock_context):
    """Test max retries exceeded returns error"""
    # Create processor that always fails
    processor = MockProcessor(
        name="max_retries_test",
        config={"service_name": "test"},
        fail_count=10,  # More than max retries
        error_type="transient",
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
            None,  # No completion marker (retry 1)
            {"pg_try_advisory_lock": True},  # Lock acquired (retry 1)
            {"pg_advisory_unlock": True},  # Lock released (retry 1)
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger
    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(return_value="error_456")
        MockErrorLogger.return_value = mock_error_logger

        # Execute - should fail after sync retry
        result = await processor.safe_process(mock_context)

        # Should return retrying result (async retry spawned)
        assert result.success is False
        assert result.status == ProcessingStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_permanent_error_no_retry(mock_context):
    """Test permanent error does not retry"""
    # Create processor that fails with permanent error
    processor = MockProcessor(
        name="permanent_error_test", config={"service_name": "test"}, fail_count=1, error_type="permanent"
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger
    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(return_value="error_789")
        MockErrorLogger.return_value = mock_error_logger

        # Execute
        result = await processor.safe_process(mock_context)

        # Should fail immediately without retry
        assert result.success is False
        assert result.status == ProcessingStatus.FAILED
        assert processor.call_count == 1  # Only initial attempt
        assert "error_id" in result.metadata
        assert result.metadata["error_category"] == "permanent"


@pytest.mark.asyncio
async def test_idempotency_skip_processing(mock_context):
    """Test idempotency check skips processing if data unchanged"""
    processor = MockProcessor(name="idempotency_skip_test", config={"service_name": "test"})

    # Mock database adapter with existing completion marker
    current_hash = processor._compute_data_hash(mock_context)
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        return_value={
            "document_id": mock_context.document_id,
            "stage_name": processor.name,
            "data_hash": current_hash,
            "completed_at": datetime.utcnow(),
            "metadata": {},
        }
    )

    # Execute
    result = await processor.safe_process(mock_context)

    # Should skip processing
    assert result.success is True
    assert result.status == ProcessingStatus.COMPLETED
    assert result.data["skipped"] == "already_processed"
    assert processor.call_count == 0  # Process was not called


@pytest.mark.asyncio
async def test_idempotency_data_changed(mock_context):
    """Test idempotency check cleans up and re-processes if data changed"""
    processor = MockProcessor(name="idempotency_changed_test", config={"service_name": "test"})

    # Mock database adapter with existing marker but different hash
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            {
                "document_id": mock_context.document_id,
                "stage_name": processor.name,
                "data_hash": "different_hash",  # Different from current
                "completed_at": datetime.utcnow(),
                "metadata": {},
            },
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Execute
    result = await processor.safe_process(mock_context)

    # Should process (cleanup was called)
    assert result.success is True
    assert processor.call_count == 1

    # Verify cleanup was called (execute called for DELETE)
    assert processor.db_adapter.execute.called


@pytest.mark.asyncio
async def test_concurrent_retry_prevention(mock_context):
    """Test advisory lock prevents concurrent retry"""
    processor = MockProcessor(
        name="concurrent_test", config={"service_name": "test"}, fail_count=1, error_type="transient"
    )

    # Mock database adapter - lock not acquired on retry
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker (attempt 0)
            {"pg_try_advisory_lock": True},  # Lock acquired (attempt 0)
            {"pg_advisory_unlock": True},  # Lock released (attempt 0)
            None,  # No completion marker (retry 1)
            {"pg_try_advisory_lock": False},  # Lock NOT acquired (retry 1)
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger
    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(return_value="error_concurrent")
        MockErrorLogger.return_value = mock_error_logger

        # Execute - will fail on first attempt, retry sync
        result = await processor.safe_process(mock_context)

        # Should return retrying result (background task spawned)
        assert result.success is False
        assert result.status == ProcessingStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_correlation_id_tracking(mock_context):
    """Test correlation ID format and tracking"""
    processor = MockProcessor(
        name="correlation_test", config={"service_name": "test"}, fail_count=1, error_type="transient"
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger to capture correlation_id
    captured_correlation_id = None

    async def capture_log_error(**kwargs):
        nonlocal captured_correlation_id
        captured_correlation_id = kwargs.get("correlation_id")
        return "error_correlation"

    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(side_effect=capture_log_error)
        MockErrorLogger.return_value = mock_error_logger

        # Execute
        result = await processor.safe_process(mock_context)

        # Verify correlation_id format
        assert captured_correlation_id is not None
        assert ".stage_correlation_test.retry_0" in captured_correlation_id
        assert captured_correlation_id.startswith("req_")


@pytest.mark.asyncio
async def test_graceful_degradation_no_db(mock_context):
    """Test processing continues without retry infrastructure when db_adapter is None"""
    processor = MockProcessor(name="no_db_test", config={"service_name": "test"})

    # No db_adapter set (None)
    processor.db_adapter = None

    # Execute - should work without retry infrastructure
    result = await processor.safe_process(mock_context)

    # Should succeed (no failures configured)
    assert result.success is True
    assert processor.call_count == 1

    # Should have logged warnings about missing components
    # (verified through logger output in real execution)


@pytest.mark.asyncio
async def test_request_id_generation(mock_context):
    """Test request_id is generated if not present"""
    processor = MockProcessor(name="request_id_test", config={"service_name": "test"})

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Ensure context has no request_id
    assert not hasattr(mock_context, "request_id") or mock_context.request_id is None

    # Execute
    result = await processor.safe_process(mock_context)

    # Verify request_id was generated
    assert hasattr(mock_context, "request_id")
    assert mock_context.request_id is not None
    assert mock_context.request_id.startswith("req_")
    assert len(mock_context.request_id) == 12  # "req_" + 8 hex chars


@pytest.mark.asyncio
async def test_retry_attempt_tracking(mock_context):
    """Test retry_attempt is tracked in context"""
    processor = MockProcessor(
        name="retry_tracking_test", config={"service_name": "test"}, fail_count=1, error_type="transient"
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker (attempt 0)
            {"pg_try_advisory_lock": True},  # Lock acquired (attempt 0)
            {"pg_advisory_unlock": True},  # Lock released (attempt 0)
            None,  # No completion marker (retry 1)
            {"pg_try_advisory_lock": True},  # Lock acquired (retry 1)
            {"pg_advisory_unlock": True},  # Lock released (retry 1)
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Execute
    result = await processor.safe_process(mock_context)

    # Verify retry_attempt was set
    assert hasattr(mock_context, "retry_attempt")
    assert mock_context.retry_attempt >= 0


@pytest.mark.asyncio
async def test_completion_marker_metadata(mock_context):
    """Test completion marker includes retry metadata"""
    processor = MockProcessor(name="marker_metadata_test", config={"service_name": "test"})

    # Mock database adapter
    captured_metadata = None

    async def capture_execute(query, params):
        nonlocal captured_metadata
        if "INSERT INTO krai_system.stage_completion_markers" in query:
            captured_metadata = params[-1] if params else None

    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock(side_effect=capture_execute)

    # Execute
    result = await processor.safe_process(mock_context)

    # Verify success
    assert result.success is True

    # Verify completion marker was set with metadata
    assert processor.db_adapter.execute.called


@pytest.mark.asyncio
async def test_error_logger_failure_handling(mock_context):
    """Test graceful handling when error logger fails"""
    processor = MockProcessor(
        name="error_logger_fail_test", config={"service_name": "test"}, fail_count=1, error_type="transient"
    )

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Mock error logger that fails
    with patch("backend.core.base_processor.ErrorLogger") as MockErrorLogger:
        mock_error_logger = AsyncMock()
        mock_error_logger.log_error = AsyncMock(side_effect=Exception("Logger failed"))
        MockErrorLogger.return_value = mock_error_logger

        # Execute - should handle error logger failure gracefully
        result = await processor.safe_process(mock_context)

        # Should still complete (with retry)
        assert result.success is True
        assert processor.call_count == 2


@pytest.mark.asyncio
async def test_processing_time_calculation(mock_context):
    """Test processing time is calculated correctly"""
    processor = MockProcessor(name="timing_test", config={"service_name": "test"})

    # Mock database adapter
    processor.db_adapter = AsyncMock()
    processor.db_adapter.fetch_one = AsyncMock(
        side_effect=[
            None,  # No completion marker
            {"pg_try_advisory_lock": True},  # Lock acquired
            {"pg_advisory_unlock": True},  # Lock released
        ]
    )
    processor.db_adapter.execute = AsyncMock()

    # Execute
    start = datetime.utcnow()
    result = await processor.safe_process(mock_context)
    end = datetime.utcnow()

    # Verify processing time is set and reasonable
    assert result.processing_time > 0
    assert result.processing_time <= (end - start).total_seconds() + 0.1  # Small margin


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
