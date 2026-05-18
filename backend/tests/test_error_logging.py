"""
Unit and Integration Tests for Error Logging System

Tests for StructuredLogger and ErrorLogger services, including:
- JSON formatting and log rotation
- Database operations and error tracking
- Correlation ID propagation
- Error classification integration
- Concurrent logging scenarios
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.base_processor import ProcessingContext
from backend.core.retry_engine import ErrorClassification
from backend.services.error_logging_service import ErrorLogger
from backend.services.structured_logger import StructuredLogger

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        log_path = f.name
    yield log_path
    # Cleanup
    Path(log_path).unlink(missing_ok=True)
    # Cleanup rotation files
    for i in range(1, 11):
        Path(f"{log_path}.{i}").unlink(missing_ok=True)


@pytest.fixture
def structured_logger(temp_log_file):
    """Create a StructuredLogger instance with temporary file."""
    return StructuredLogger(
        logger_name="test_logger",
        log_file_path=temp_log_file,
        max_bytes=1024 * 1024,
        backup_count=3,  # 1MB for testing
    )


@pytest.fixture
def sample_error():
    """Create a sample exception for testing."""
    try:
        raise ValueError("Test error message")
    except ValueError as e:
        return e


@pytest.fixture
def sample_context():
    """Create a sample context dictionary for testing."""
    return {
        "document_id": "doc_123",
        "stage": "embedding",
        "request_id": "req_456",
        "file_path": "/path/to/document.pdf",
        "manufacturer": "HP",
        "model": "LaserJet Pro",
    }


@pytest.fixture
def mock_db_adapter():
    """Create a mock DatabaseAdapter."""
    adapter = AsyncMock()
    adapter.execute_query = AsyncMock(return_value=None)
    adapter.fetch_one = AsyncMock(return_value=None)
    adapter.fetch_all = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def mock_structured_logger():
    """Create a mock StructuredLogger."""
    logger = AsyncMock()
    logger.log_error = AsyncMock()
    logger.log_info = AsyncMock()
    logger.log_warning = AsyncMock()
    logger.log_debug = AsyncMock()
    return logger


@pytest.fixture
def error_logger(mock_db_adapter, mock_structured_logger):
    """Create an ErrorLogger instance with mocks."""
    logger = ErrorLogger(mock_db_adapter)
    logger.structured_logger = mock_structured_logger
    return logger


@pytest.fixture
def sample_processing_context():
    """Create a sample ProcessingContext for testing."""
    return ProcessingContext(
        document_id="doc_123",
        file_path="/path/to/document.pdf",
        document_type="service_manual",
        manufacturer="HP",
        model="LaserJet Pro",
        series="LaserJet",
        version="1.0",
        language="en",
        file_hash="abc123",
        file_size=1024000,
        request_id="req_456",
        correlation_id="req_456.embedding.retry_0",
        retry_attempt=0,
    )


@pytest.fixture
def sample_error_classification():
    """Create a sample ErrorClassification for testing (current API: is_transient, error_type, error_category, optional http_status_code)."""
    return ErrorClassification(
        is_transient=True, error_type="ValueError", error_category="transient", http_status_code=None
    )


# ============================================================================
# TestStructuredLogger - JSON Formatting Tests
# ============================================================================


class TestStructuredLogger:
    """Test suite for StructuredLogger JSON formatting and file operations."""

    @pytest.mark.asyncio
    async def test_format_json_basic(self, structured_logger):
        """Test basic JSON formatting with required fields."""
        json_str = structured_logger._format_json(level="INFO", message="Test message")

        data = json.loads(json_str)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")

    @pytest.mark.asyncio
    async def test_format_json_with_correlation_id(self, structured_logger):
        """Test JSON formatting with correlation ID."""
        json_str = structured_logger._format_json(
            level="ERROR", message="Error occurred", correlation_id="req_123.embedding.retry_1", request_id="req_123"
        )

        data = json.loads(json_str)

        assert data["correlation_id"] == "req_123.embedding.retry_1"
        assert data["request_id"] == "req_123"

    @pytest.mark.asyncio
    async def test_format_json_with_exception(self, structured_logger, sample_error):
        """Test JSON formatting with exception and stack trace."""
        import traceback

        stack_trace = traceback.format_exc()

        json_str = structured_logger._format_json(
            level="ERROR", message=str(sample_error), error_type=type(sample_error).__name__, stack_trace=stack_trace
        )

        data = json.loads(json_str)

        assert data["error_type"] == "ValueError"
        assert "stack_trace" in data
        assert len(data["stack_trace"]) > 0

    @pytest.mark.asyncio
    async def test_format_json_with_context(self, structured_logger, sample_context):
        """Test JSON formatting with context dictionary."""
        json_str = structured_logger._format_json(
            level="INFO",
            message="Processing document",
            context=sample_context,
            document_id=sample_context["document_id"],
            stage=sample_context["stage"],
        )

        data = json.loads(json_str)

        assert data["context"] == sample_context
        assert data["document_id"] == "doc_123"
        assert data["stage"] == "embedding"

    @pytest.mark.asyncio
    async def test_log_rotation_configuration(self, temp_log_file):
        """Test log rotation configuration."""
        logger = StructuredLogger(
            logger_name="rotation_test",
            log_file_path=temp_log_file,
            max_bytes=100 * 1024 * 1024,  # 100MB
            backup_count=10,
        )

        assert logger.max_bytes == 100 * 1024 * 1024
        assert logger.backup_count == 10
        assert len(logger._logger.handlers) == 1

        handler = logger._logger.handlers[0]
        assert handler.maxBytes == 100 * 1024 * 1024
        assert handler.backupCount == 10

    @pytest.mark.asyncio
    async def test_log_file_creation(self, temp_log_file):
        """Test that log file is created at specified path."""
        logger = StructuredLogger(logger_name="file_test", log_file_path=temp_log_file)

        # Write a log entry
        await logger.log_info(message="Test message", context={"test": "data"})

        # Give async write time to complete
        await asyncio.sleep(0.1)

        # Verify file exists and contains data
        assert Path(temp_log_file).exists()
        assert Path(temp_log_file).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_async_write(self, structured_logger, temp_log_file):
        """Test non-blocking async write operation."""
        start_time = datetime.utcnow()

        # Write multiple entries
        tasks = []
        for i in range(10):
            task = structured_logger.log_info(message=f"Message {i}", context={"index": i})
            tasks.append(task)

        await asyncio.gather(*tasks)

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Should complete quickly (async)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, structured_logger, temp_log_file):
        """Test multiple concurrent log writes."""
        # Write 50 concurrent log entries
        tasks = []
        for i in range(50):
            task = structured_logger.log_info(message=f"Concurrent message {i}", context={"index": i, "thread": "test"})
            tasks.append(task)

        # All should complete without errors
        await asyncio.gather(*tasks)

        # Give time for writes to complete
        await asyncio.sleep(0.2)

        # Verify file has content
        assert Path(temp_log_file).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_log_error(self, structured_logger, sample_error, sample_context):
        """Test ERROR level logging."""
        await structured_logger.log_error(
            error=sample_error, context=sample_context, correlation_id="req_123.test.retry_0", error_id="err_abc123"
        )

        await asyncio.sleep(0.1)

        # Verify log was written
        assert Path(structured_logger.log_file_path).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_log_warning(self, structured_logger, sample_context):
        """Test WARNING level logging."""
        await structured_logger.log_warning(
            message="Warning message", context=sample_context, correlation_id="req_123.test.retry_0"
        )

        await asyncio.sleep(0.1)

        assert Path(structured_logger.log_file_path).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_log_info(self, structured_logger, sample_context):
        """Test INFO level logging."""
        await structured_logger.log_info(
            message="Info message", context=sample_context, correlation_id="req_123.test.retry_0"
        )

        await asyncio.sleep(0.1)

        assert Path(structured_logger.log_file_path).stat().st_size > 0


# ============================================================================
# TestErrorLogger - Database and Error Tracking Tests
# ============================================================================


class TestErrorLogger:
    """Test suite for ErrorLogger database operations and error tracking."""

    @pytest.mark.asyncio
    async def test_log_error_creates_database_record(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test that log_error creates a database record."""
        error_id = await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=1,
            max_retries=3,
            correlation_id="req_456.embedding.retry_1",
        )

        # Verify database insert was called
        mock_db_adapter.execute_query.assert_called_once()

        # Verify query structure
        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO krai_system.pipeline_errors" in query
        assert params[0] == error_id  # error_id
        assert params[1] == "doc_123"  # document_id
        assert params[4] == "transient"  # error_category

    @pytest.mark.asyncio
    async def test_log_error_generates_unique_error_id(self, error_logger):
        """Test that error_id is unique and follows format."""
        error_id_1 = error_logger._generate_error_id()
        error_id_2 = error_logger._generate_error_id()

        # Should be unique
        assert error_id_1 != error_id_2

        # Should follow format: err_{16_hex_chars}
        assert error_id_1.startswith("err_")
        assert len(error_id_1) == 20  # "err_" + 16 hex chars
        assert all(c in "0123456789abcdef" for c in error_id_1[4:])

    @pytest.mark.asyncio
    async def test_log_error_captures_stack_trace(
        self, error_logger, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test that stack trace is captured."""
        with patch.object(error_logger, "_extract_stack_trace", return_value="Mock stack trace"):
            await error_logger.log_error(
                context=sample_processing_context,
                error=sample_error,
                classification=sample_error_classification,
                retry_count=0,
                max_retries=3,
                correlation_id="req_456.embedding.retry_0",
            )

            error_logger._extract_stack_trace.assert_called_once_with(sample_error)

    @pytest.mark.asyncio
    async def test_log_error_stores_context_as_jsonb(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test that context is stored as JSONB."""
        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=1,
            max_retries=3,
            correlation_id="req_456.embedding.retry_1",
        )

        # Get the context parameter (8th parameter, index 7)
        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]
        context_json = params[7]

        # Should be valid JSON
        context_data = json.loads(context_json)

        assert context_data["document_id"] == "doc_123"
        assert context_data["manufacturer"] == "HP"
        assert context_data["model"] == "LaserJet Pro"
        assert context_data["retry_count"] == 1
        assert context_data["max_retries"] == 3

    @pytest.mark.asyncio
    async def test_log_error_writes_to_json_log(
        self, error_logger, mock_structured_logger, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test that error is written to JSON log file."""
        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=1,
            max_retries=3,
            correlation_id="req_456.embedding.retry_1",
        )

        # Verify structured logger was called
        mock_structured_logger.log_error.assert_called_once()

        call_kwargs = mock_structured_logger.log_error.call_args[1]
        assert call_kwargs["error"] == sample_error
        assert call_kwargs["correlation_id"] == "req_456.embedding.retry_1"
        assert "error_id" in call_kwargs

    @pytest.mark.asyncio
    async def test_log_error_includes_correlation_id(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test that correlation_id is included in database record."""
        correlation_id = "req_456.embedding.retry_2"

        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=2,
            max_retries=3,
            correlation_id=correlation_id,
        )

        # Get correlation_id parameter (13th parameter, index 12)
        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]

        assert params[12] == correlation_id

    @pytest.mark.asyncio
    async def test_update_error_status(self, error_logger, mock_db_adapter, mock_structured_logger):
        """Test error status update."""
        error_id = "err_abc123"
        next_retry = datetime.utcnow() + timedelta(seconds=30)

        await error_logger.update_error_status(error_id=error_id, status="retrying", next_retry_at=next_retry)

        # Verify database update was called
        mock_db_adapter.execute_query.assert_called_once()

        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "UPDATE krai_system.pipeline_errors" in query
        assert params[0] == "retrying"
        assert params[1] == next_retry
        assert params[2] == error_id

        # Verify info log was written
        mock_structured_logger.log_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_error_status_with_next_retry(self, error_logger, mock_db_adapter):
        """Test error status update with next_retry_at timestamp."""
        error_id = "err_xyz789"
        next_retry = datetime.utcnow() + timedelta(minutes=5)

        await error_logger.update_error_status(error_id=error_id, status="pending", next_retry_at=next_retry)

        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]

        assert params[1] == next_retry

    @pytest.mark.asyncio
    async def test_mark_error_resolved(self, error_logger, mock_db_adapter, mock_structured_logger):
        """Test marking error as resolved."""
        error_id = "err_resolved123"

        await error_logger.mark_error_resolved(
            error_id=error_id, resolved_by="retry_engine", notes="Successfully retried after 2 attempts"
        )

        # Verify database update was called
        mock_db_adapter.execute_query.assert_called_once()

        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "UPDATE krai_system.pipeline_errors" in query
        assert "status = 'resolved'" in query
        assert params[0] == "retry_engine"
        assert params[1] == "Successfully retried after 2 attempts"
        assert params[2] == error_id

        # Verify info log was written
        mock_structured_logger.log_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_error_with_transient_classification(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error
    ):
        """Test logging error with transient classification."""
        classification = ErrorClassification(
            is_transient=True, error_type="ValueError", error_category="transient", http_status_code=None
        )

        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=classification,
            retry_count=0,
            max_retries=3,
            correlation_id="req_456.test.retry_0",
        )

        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]

        # is_transient should be True (12th parameter, index 11)
        assert params[11] is True
        # error_category should be "transient" (5th parameter, index 4)
        assert params[4] == "transient"

    @pytest.mark.asyncio
    async def test_log_error_with_permanent_classification(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error
    ):
        """Test logging error with permanent classification."""
        classification = ErrorClassification(
            is_transient=False, error_type="ValueError", error_category="permanent", http_status_code=None
        )

        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=classification,
            retry_count=0,
            max_retries=0,
            correlation_id="req_456.test.retry_0",
        )

        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]

        # is_transient should be False
        assert params[11] is False
        # error_category should be "permanent"
        assert params[4] == "permanent"

    @pytest.mark.asyncio
    async def test_stage_name_normalized_from_correlation_id(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error, sample_error_classification
    ):
        """Regression: stage_name becomes 'embedding' for correlation_id req_x.stage_embedding.retry_1 (strip 'stage_' prefix)."""
        await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=1,
            max_retries=3,
            correlation_id="req_x.stage_embedding.retry_1",
            stage_name=None,
        )
        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]
        # stage_name is 3rd column (index 2) in INSERT
        assert params[2] == "embedding"

    @pytest.mark.asyncio
    async def test_concurrent_error_logging(
        self, error_logger, mock_db_adapter, sample_processing_context, sample_error_classification
    ):
        """Test multiple concurrent log_error calls."""
        # Create multiple errors
        errors = [ValueError(f"Error {i}") for i in range(10)]

        # Log all errors concurrently
        tasks = []
        for i, error in enumerate(errors):
            task = error_logger.log_error(
                context=sample_processing_context,
                error=error,
                classification=sample_error_classification,
                retry_count=0,
                max_retries=3,
                correlation_id=f"req_456.test.retry_{i}",
            )
            tasks.append(task)

        error_ids = await asyncio.gather(*tasks)

        # All should have unique error IDs
        assert len(error_ids) == len(set(error_ids))

        # Database should have been called 10 times
        assert mock_db_adapter.execute_query.call_count == 10

    @pytest.mark.asyncio
    async def test_database_error_handling(
        self,
        error_logger,
        mock_db_adapter,
        mock_structured_logger,
        sample_processing_context,
        sample_error,
        sample_error_classification,
    ):
        """Test graceful handling of database errors."""
        # Make database raise an error
        mock_db_adapter.execute_query.side_effect = Exception("Database connection failed")

        # Should not raise, but log the DB error
        error_id = await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=0,
            max_retries=3,
            correlation_id="req_456.test.retry_0",
        )

        # Should still return an error_id
        assert error_id is not None
        assert error_id.startswith("err_")

        # Should have logged the DB error to structured logger
        assert mock_structured_logger.log_error.call_count == 2  # Original error + DB error


# ============================================================================
# TestErrorLoggingIntegration - End-to-End Tests
# ============================================================================


class TestErrorLoggingIntegration:
    """Integration tests for error logging flow."""

    @pytest.mark.asyncio
    async def test_error_logging_full_flow(
        self, temp_log_file, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test complete error logging flow from error to DB + JSON."""
        # Create real StructuredLogger with temp file
        structured_logger = StructuredLogger(logger_name="integration_test", log_file_path=temp_log_file)

        # Create ErrorLogger with mock DB
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=None)

        error_logger = ErrorLogger(mock_db, log_file_path=temp_log_file)
        error_logger.structured_logger = structured_logger

        # Log an error
        error_id = await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=1,
            max_retries=3,
            correlation_id="req_456.embedding.retry_1",
        )

        # Give async writes time to complete
        await asyncio.sleep(0.2)

        # Verify error_id was generated
        assert error_id.startswith("err_")

        # Verify database was called
        mock_db.execute_query.assert_called_once()

        # Verify JSON log file has content
        assert Path(temp_log_file).stat().st_size > 0

        # Read and verify JSON log content
        with open(temp_log_file) as f:
            log_line = f.readline()
            log_data = json.loads(log_line)

            assert log_data["level"] == "ERROR"
            assert log_data["error_id"] == error_id
            assert log_data["correlation_id"] == "req_456.embedding.retry_1"
            assert log_data["document_id"] == "doc_123"

    @pytest.mark.asyncio
    async def test_error_logging_with_retry_engine(self, temp_log_file, sample_processing_context, sample_error):
        """Test integration with ErrorClassifier (classify(exception) API)."""
        from backend.core.retry_engine import ErrorClassifier

        # Classify the error using current API
        classification = ErrorClassifier.classify(sample_error)

        # Create error logger
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=None)

        error_logger = ErrorLogger(mock_db, log_file_path=temp_log_file)

        # Log the classified error
        error_id = await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=classification,
            retry_count=0,
            max_retries=3,
            correlation_id="req_456.embedding.retry_0",
        )

        await asyncio.sleep(0.1)

        # Verify error was logged
        assert error_id is not None
        mock_db.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(
        self, temp_log_file, sample_processing_context, sample_error, sample_error_classification
    ):
        """Test correlation_id propagation through entire flow."""
        correlation_id = "req_789.classification.retry_2"

        # Create error logger
        mock_db = AsyncMock()
        mock_db.execute_query = AsyncMock(return_value=None)

        structured_logger = StructuredLogger(logger_name="correlation_test", log_file_path=temp_log_file)

        error_logger = ErrorLogger(mock_db, log_file_path=temp_log_file)
        error_logger.structured_logger = structured_logger

        # Log error with correlation_id
        error_id = await error_logger.log_error(
            context=sample_processing_context,
            error=sample_error,
            classification=sample_error_classification,
            retry_count=2,
            max_retries=3,
            correlation_id=correlation_id,
        )

        await asyncio.sleep(0.1)

        # Verify correlation_id in database call
        call_args = mock_db.execute_query.call_args
        params = call_args[0][1]
        assert params[12] == correlation_id

        # Verify correlation_id in JSON log
        with open(temp_log_file) as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
            assert log_data["correlation_id"] == correlation_id
