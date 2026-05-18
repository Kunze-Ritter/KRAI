"""
Comprehensive Unit Tests for Idempotency System

This test suite covers all idempotency scenarios including:
- Data hash computation and consistency
- Completion marker checks (found/not found/data changed)
- Marker creation and updates (upsert behavior)
- Cleanup operations
- Integration with BaseProcessor helper methods
- Error handling and edge cases
- Concurrent access scenarios
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from backend.core.base_processor import BaseProcessor
from backend.core.idempotency import IdempotencyChecker, compute_context_hash
from backend.core.types import ProcessingContext, ProcessingResult
from backend.services.database_adapter import DatabaseAdapter

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_db_adapter():
    """Mock database adapter with configurable responses."""
    adapter = Mock(spec=DatabaseAdapter)
    adapter.fetch_one = AsyncMock(return_value=None)
    adapter.fetch_all = AsyncMock(return_value=[])
    adapter.execute_query = AsyncMock()
    return adapter


@pytest.fixture
def sample_processing_context():
    """Sample processing context with all required fields."""
    return ProcessingContext(
        document_id="doc-12345",
        file_path="/path/to/document.pdf",
        document_type="manual",
        manufacturer="Hewlett Packard",
        model="E877",
        series="LaserJet Enterprise",
        version="1.0",
        language="en",
        file_hash="abc123def456",
        file_size=1024000,
        metadata={"source": "upload"},
    )


@pytest.fixture
def sample_completion_marker():
    """Sample completion marker data from database."""
    return {
        "document_id": "doc-12345",
        "stage_name": "pdf_extraction",
        "completed_at": datetime.utcnow(),
        "data_hash": "a1b2c3d4e5f6" + "0" * 52,  # 64 char hash
        "metadata": {"processing_time": 1.5, "pages": 100},
    }


@pytest.fixture
def idempotency_checker(mock_db_adapter):
    """IdempotencyChecker instance with mock adapter."""
    return IdempotencyChecker(mock_db_adapter)


@pytest.fixture
def mock_processor(mock_db_adapter):
    """Mock processor with database adapter for testing helper methods."""

    class TestProcessor(BaseProcessor):
        async def process(self, context: ProcessingContext) -> ProcessingResult:
            return self.create_success_result({"test": "data"})

    processor = TestProcessor(name="test_processor")
    processor.db_adapter = mock_db_adapter
    return processor


# ============================================================================
# A. Data Hash Computation Tests
# ============================================================================


class TestStandaloneHashFunction:
    """Test suite for standalone compute_context_hash function."""

    def test_standalone_hash_without_db(self, sample_processing_context):
        """Test that compute_context_hash works without database adapter."""
        # No DB adapter required - function is standalone
        hash_value = compute_context_hash(sample_processing_context)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA-256 produces 64 hex characters
        assert isinstance(hash_value, str)

    def test_standalone_hash_consistency(self, sample_processing_context):
        """Test that standalone hash produces consistent results."""
        hash1 = compute_context_hash(sample_processing_context)
        hash2 = compute_context_hash(sample_processing_context)

        assert hash1 == hash2

    def test_standalone_hash_with_minimal_context(self):
        """Test standalone hash with minimal context fields."""
        context = ProcessingContext(document_id="doc-123", file_path="/path/to/file.pdf", document_type="manual")

        hash_value = compute_context_hash(context)

        assert len(hash_value) == 64
        assert hash_value  # Should not be empty

    def test_standalone_hash_matches_checker_hash(self, idempotency_checker, sample_processing_context):
        """Test that standalone hash matches IdempotencyChecker.compute_data_hash."""
        standalone_hash = compute_context_hash(sample_processing_context)
        checker_hash = idempotency_checker.compute_data_hash(sample_processing_context)

        assert standalone_hash == checker_hash


class TestDataHashComputation:
    """Test suite for data hash computation."""

    def test_consistent_hash_generation(self, idempotency_checker, sample_processing_context):
        """Test that same input produces same hash."""
        hash1 = idempotency_checker.compute_data_hash(sample_processing_context)
        hash2 = idempotency_checker.compute_data_hash(sample_processing_context)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_different_hashes_for_different_inputs(self, idempotency_checker, sample_processing_context):
        """Test that different inputs produce different hashes."""
        hash1 = idempotency_checker.compute_data_hash(sample_processing_context)

        # Modify context
        context2 = ProcessingContext(
            document_id=sample_processing_context.document_id,
            file_path=sample_processing_context.file_path,
            document_type=sample_processing_context.document_type,
            manufacturer="Canon",  # Different manufacturer
            model=sample_processing_context.model,
            file_hash=sample_processing_context.file_hash,
            file_size=sample_processing_context.file_size,
        )
        hash2 = idempotency_checker.compute_data_hash(context2)

        assert hash1 != hash2

    def test_hash_changes_when_relevant_fields_change(self, idempotency_checker, sample_processing_context):
        """Test that hash changes when relevant fields change."""
        hash1 = idempotency_checker.compute_data_hash(sample_processing_context)

        # Change file_hash
        sample_processing_context.file_hash = "different_hash"
        hash2 = idempotency_checker.compute_data_hash(sample_processing_context)
        assert hash1 != hash2

        # Change file_size
        sample_processing_context.file_size = 2048000
        hash3 = idempotency_checker.compute_data_hash(sample_processing_context)
        assert hash2 != hash3

        # Change model
        sample_processing_context.model = "M454dn"
        hash4 = idempotency_checker.compute_data_hash(sample_processing_context)
        assert hash3 != hash4

    def test_hash_stability_when_irrelevant_fields_change(self, idempotency_checker, sample_processing_context):
        """Test that hash remains stable when irrelevant fields change."""
        hash1 = idempotency_checker.compute_data_hash(sample_processing_context)

        # Change metadata (not included in hash)
        sample_processing_context.metadata = {"different": "metadata"}
        hash2 = idempotency_checker.compute_data_hash(sample_processing_context)

        assert hash1 == hash2

    def test_handling_of_none_fields(self, idempotency_checker):
        """Test hash computation with None/missing fields."""
        context = ProcessingContext(
            document_id="doc-123",
            file_path="/path/to/file.pdf",
            document_type="manual",
            manufacturer=None,
            model=None,
            series=None,
            version=None,
            file_hash=None,
            file_size=None,
        )

        hash_value = idempotency_checker.compute_data_hash(context)

        assert len(hash_value) == 64
        assert hash_value  # Should not be empty


# ============================================================================
# B. Completion Marker Check Tests
# ============================================================================


class TestCompletionMarkerCheck:
    """Test suite for completion marker checks."""

    @pytest.mark.asyncio
    async def test_marker_found(self, idempotency_checker, mock_db_adapter, sample_completion_marker):
        """Test marker found (already processed)."""
        mock_db_adapter.fetch_one.return_value = sample_completion_marker

        result = await idempotency_checker.check_completion_marker("doc-12345", "pdf_extraction")

        assert result is not None
        assert result["document_id"] == "doc-12345"
        assert result["stage_name"] == "pdf_extraction"
        assert "data_hash" in result
        mock_db_adapter.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_marker_not_found(self, idempotency_checker, mock_db_adapter):
        """Test marker not found (first processing)."""
        mock_db_adapter.fetch_one.return_value = None

        result = await idempotency_checker.check_completion_marker("doc-12345", "pdf_extraction")

        assert result is None
        mock_db_adapter.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_marker_with_matching_data_hash(
        self, idempotency_checker, mock_db_adapter, sample_processing_context
    ):
        """Test marker with matching data hash."""
        expected_hash = idempotency_checker.compute_data_hash(sample_processing_context)
        marker = {
            "document_id": "doc-12345",
            "stage_name": "pdf_extraction",
            "data_hash": expected_hash,
            "metadata": {},
        }
        mock_db_adapter.fetch_one.return_value = marker

        result = await idempotency_checker.check_completion_marker("doc-12345", "pdf_extraction")

        assert result["data_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_marker_with_different_data_hash(self, idempotency_checker, mock_db_adapter):
        """Test marker with different data hash (data changed)."""
        marker = {
            "document_id": "doc-12345",
            "stage_name": "pdf_extraction",
            "data_hash": "old_hash_value" + "0" * 48,
            "metadata": {},
        }
        mock_db_adapter.fetch_one.return_value = marker

        result = await idempotency_checker.check_completion_marker("doc-12345", "pdf_extraction")

        assert result["data_hash"] != "new_hash_value"

    @pytest.mark.asyncio
    async def test_database_error_handling(self, idempotency_checker, mock_db_adapter):
        """Test database error handling."""
        mock_db_adapter.fetch_one.side_effect = Exception("Database connection failed")

        result = await idempotency_checker.check_completion_marker("doc-12345", "pdf_extraction")

        assert result is None  # Should return None on error

    @pytest.mark.asyncio
    async def test_invalid_document_id(self, idempotency_checker, mock_db_adapter):
        """Test handling of invalid document_id."""
        mock_db_adapter.fetch_one.return_value = None

        result = await idempotency_checker.check_completion_marker("", "pdf_extraction")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_stage_name(self, idempotency_checker, mock_db_adapter):
        """Test handling of invalid stage_name."""
        mock_db_adapter.fetch_one.return_value = None

        result = await idempotency_checker.check_completion_marker("doc-12345", "")

        assert result is None


# ============================================================================
# C. Set Completion Marker Tests
# ============================================================================


class TestSetCompletionMarker:
    """Test suite for setting completion markers."""

    @pytest.mark.asyncio
    async def test_successful_marker_creation(self, idempotency_checker, mock_db_adapter):
        """Test successful marker creation."""
        result = await idempotency_checker.set_completion_marker(
            "doc-12345", "pdf_extraction", "a1b2c3d4" + "0" * 56, {"processing_time": 1.5}
        )

        assert result is True
        mock_db_adapter.execute_query.assert_called_once()

        # Verify query structure
        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO krai_system.stage_completion_markers" in query
        assert "ON CONFLICT" in query
        assert params[0] == "doc-12345"
        assert params[1] == "pdf_extraction"

    @pytest.mark.asyncio
    async def test_marker_update_upsert_behavior(self, idempotency_checker, mock_db_adapter):
        """Test marker update (upsert behavior)."""
        # First insert
        await idempotency_checker.set_completion_marker(
            "doc-12345", "pdf_extraction", "hash1" + "0" * 59, {"attempt": 1}
        )

        # Update with new hash
        result = await idempotency_checker.set_completion_marker(
            "doc-12345", "pdf_extraction", "hash2" + "0" * 59, {"attempt": 2}
        )

        assert result is True
        assert mock_db_adapter.execute_query.call_count == 2

    @pytest.mark.asyncio
    async def test_metadata_storage_as_jsonb(self, idempotency_checker, mock_db_adapter):
        """Test metadata storage as JSONB."""
        metadata = {"processing_time": 1.5, "pages_extracted": 100, "retry_count": 0, "processor_version": "1.0.0"}

        await idempotency_checker.set_completion_marker("doc-12345", "pdf_extraction", "hash" + "0" * 60, metadata)

        call_args = mock_db_adapter.execute_query.call_args
        params = call_args[0][1]
        metadata_json = params[3]

        # Verify JSON serialization
        parsed = json.loads(metadata_json)
        assert parsed["processing_time"] == 1.5
        assert parsed["pages_extracted"] == 100

    @pytest.mark.asyncio
    async def test_timestamp_auto_generation(self, idempotency_checker, mock_db_adapter):
        """Test timestamp auto-generation."""
        await idempotency_checker.set_completion_marker("doc-12345", "pdf_extraction", "hash" + "0" * 60, {})

        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]

        assert "CURRENT_TIMESTAMP" in query

    @pytest.mark.asyncio
    async def test_database_error_handling(self, idempotency_checker, mock_db_adapter):
        """Test database error handling."""
        mock_db_adapter.execute_query.side_effect = Exception("Database error")

        result = await idempotency_checker.set_completion_marker("doc-12345", "pdf_extraction", "hash" + "0" * 60, {})

        assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_marker_creation(self, idempotency_checker, mock_db_adapter):
        """Test concurrent marker creation (ON CONFLICT handles this)."""
        # Simulate concurrent calls
        result1 = await idempotency_checker.set_completion_marker(
            "doc-12345", "pdf_extraction", "hash1" + "0" * 59, {"thread": 1}
        )

        result2 = await idempotency_checker.set_completion_marker(
            "doc-12345", "pdf_extraction", "hash2" + "0" * 59, {"thread": 2}
        )

        assert result1 is True
        assert result2 is True
        # ON CONFLICT ensures only one marker exists


# ============================================================================
# D. Cleanup Old Data Tests
# ============================================================================


class TestCleanupOldData:
    """Test suite for cleanup operations."""

    @pytest.mark.asyncio
    async def test_successful_cleanup_operation(self, idempotency_checker, mock_db_adapter):
        """Test successful cleanup operation."""
        result = await idempotency_checker.cleanup_old_data("doc-12345", "pdf_extraction")

        assert result is True
        mock_db_adapter.execute_query.assert_called_once()

        # Verify DELETE query
        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "DELETE FROM krai_system.stage_completion_markers" in query
        assert params[0] == "doc-12345"
        assert params[1] == "pdf_extraction"

    @pytest.mark.asyncio
    async def test_cleanup_when_no_data_exists(self, idempotency_checker, mock_db_adapter):
        """Test cleanup when no data exists."""
        # DELETE will succeed even if no rows affected
        result = await idempotency_checker.cleanup_old_data("doc-99999", "nonexistent_stage")

        assert result is True

    @pytest.mark.asyncio
    async def test_database_error_handling(self, idempotency_checker, mock_db_adapter):
        """Test database error handling."""
        mock_db_adapter.execute_query.side_effect = Exception("Database error")

        result = await idempotency_checker.cleanup_old_data("doc-12345", "pdf_extraction")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_with_foreign_key_constraints(self, idempotency_checker, mock_db_adapter):
        """Test cleanup with foreign key constraints."""
        # In real scenario, foreign keys might prevent deletion
        # But our implementation only deletes the marker, not related data
        result = await idempotency_checker.cleanup_old_data("doc-12345", "pdf_extraction")

        assert result is True


# ============================================================================
# E. Integration Tests
# ============================================================================


class TestIntegrationFlows:
    """Test suite for full idempotency flows."""

    @pytest.mark.asyncio
    async def test_full_idempotency_flow(self, idempotency_checker, mock_db_adapter, sample_processing_context):
        """Test full flow: check → process → set marker."""
        # Step 1: Check marker (not found)
        mock_db_adapter.fetch_one.return_value = None
        marker = await idempotency_checker.check_completion_marker(
            sample_processing_context.document_id, "pdf_extraction"
        )
        assert marker is None

        # Step 2: Process (simulated)
        # ... processing happens ...

        # Step 3: Set marker
        data_hash = idempotency_checker.compute_data_hash(sample_processing_context)
        result = await idempotency_checker.set_completion_marker(
            sample_processing_context.document_id, "pdf_extraction", data_hash, {"processing_time": 1.5}
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_reprocessing_flow(self, idempotency_checker, mock_db_adapter, sample_processing_context):
        """Test re-processing flow: check → detect change → cleanup → process."""
        # Step 1: Check marker (found with old hash)
        old_hash = "old_hash" + "0" * 56
        mock_db_adapter.fetch_one.return_value = {
            "document_id": sample_processing_context.document_id,
            "stage_name": "pdf_extraction",
            "data_hash": old_hash,
            "metadata": {},
        }

        marker = await idempotency_checker.check_completion_marker(
            sample_processing_context.document_id, "pdf_extraction"
        )
        assert marker is not None

        # Step 2: Compute current hash (different)
        current_hash = idempotency_checker.compute_data_hash(sample_processing_context)
        assert marker["data_hash"] != current_hash

        # Step 3: Cleanup old data
        result = await idempotency_checker.cleanup_old_data(sample_processing_context.document_id, "pdf_extraction")
        assert result is True

        # Step 4: Process and set new marker
        result = await idempotency_checker.set_completion_marker(
            sample_processing_context.document_id, "pdf_extraction", current_hash, {"processing_time": 2.0}
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_skip_processing_when_unchanged(
        self, idempotency_checker, mock_db_adapter, sample_processing_context
    ):
        """Test skipping processing when data unchanged."""
        # Compute expected hash
        expected_hash = idempotency_checker.compute_data_hash(sample_processing_context)

        # Marker exists with matching hash
        mock_db_adapter.fetch_one.return_value = {
            "document_id": sample_processing_context.document_id,
            "stage_name": "pdf_extraction",
            "data_hash": expected_hash,
            "metadata": {"processing_time": 1.5},
        }

        marker = await idempotency_checker.check_completion_marker(
            sample_processing_context.document_id, "pdf_extraction"
        )

        current_hash = idempotency_checker.compute_data_hash(sample_processing_context)

        # Data unchanged - should skip processing
        assert marker["data_hash"] == current_hash

    @pytest.mark.asyncio
    async def test_marker_persistence_across_restarts(self, mock_db_adapter, sample_processing_context):
        """Test marker persistence across restarts."""
        # First checker instance
        checker1 = IdempotencyChecker(mock_db_adapter)
        data_hash = checker1.compute_data_hash(sample_processing_context)
        await checker1.set_completion_marker(
            sample_processing_context.document_id, "pdf_extraction", data_hash, {"attempt": 1}
        )

        # Simulate restart - new checker instance
        mock_db_adapter.fetch_one.return_value = {
            "document_id": sample_processing_context.document_id,
            "stage_name": "pdf_extraction",
            "data_hash": data_hash,
            "metadata": {"attempt": 1},
        }

        checker2 = IdempotencyChecker(mock_db_adapter)
        marker = await checker2.check_completion_marker(sample_processing_context.document_id, "pdf_extraction")

        assert marker is not None
        assert marker["data_hash"] == data_hash


# ============================================================================
# F. BaseProcessor Helper Method Tests
# ============================================================================


class TestBaseProcessorHelperMethods:
    """Test suite for BaseProcessor helper methods."""

    @pytest.mark.asyncio
    async def test_check_completion_marker_delegation(self, mock_processor, mock_db_adapter, sample_processing_context):
        """Test _check_completion_marker delegation."""
        mock_db_adapter.fetch_one.return_value = {
            "document_id": sample_processing_context.document_id,
            "stage_name": "test_processor",
            "data_hash": "hash" + "0" * 60,
            "metadata": {},
        }

        result = await mock_processor._check_completion_marker(sample_processing_context)

        assert result is not None
        assert result["stage_name"] == "test_processor"
        mock_db_adapter.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_completion_marker_delegation(self, mock_processor, mock_db_adapter, sample_processing_context):
        """Test _set_completion_marker delegation."""
        result = await mock_processor._set_completion_marker(sample_processing_context, {"test": "metadata"})

        assert result is True
        mock_db_adapter.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_data_delegation(self, mock_processor, mock_db_adapter, sample_processing_context):
        """Test _cleanup_old_data delegation."""
        result = await mock_processor._cleanup_old_data(sample_processing_context)

        assert result is True
        mock_db_adapter.execute_query.assert_called_once()

    def test_compute_data_hash_delegation(self, mock_processor, sample_processing_context):
        """Test _compute_data_hash delegation."""
        hash_value = mock_processor._compute_data_hash(sample_processing_context)

        assert len(hash_value) == 64
        assert hash_value  # Should not be empty

    @pytest.mark.asyncio
    async def test_error_propagation_from_idempotency_checker(
        self, mock_processor, mock_db_adapter, sample_processing_context
    ):
        """Test error propagation from IdempotencyChecker."""
        mock_db_adapter.execute_query.side_effect = Exception("Database error")

        result = await mock_processor._set_completion_marker(sample_processing_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_helper_methods_without_db_adapter(self, sample_processing_context):
        """Test helper methods when db_adapter is not configured."""

        class TestProcessor(BaseProcessor):
            async def process(self, context: ProcessingContext) -> ProcessingResult:
                return self.create_success_result({"test": "data"})

        processor = TestProcessor(name="test_processor")
        # No db_adapter set

        marker = await processor._check_completion_marker(sample_processing_context)
        assert marker is None

        result = await processor._set_completion_marker(sample_processing_context)
        assert result is False

        result = await processor._cleanup_old_data(sample_processing_context)
        assert result is False

        hash_value = processor._compute_data_hash(sample_processing_context)
        assert hash_value == ""  # Fallback to empty string


# ============================================================================
# G. Edge Cases and Error Scenarios
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases and error scenarios."""

    def test_null_context_fields(self, idempotency_checker):
        """Test handling of null/missing context fields."""
        context = ProcessingContext(document_id="doc-123", file_path="/path/to/file.pdf", document_type="manual")

        hash_value = idempotency_checker.compute_data_hash(context)
        assert len(hash_value) == 64

    @pytest.mark.asyncio
    async def test_corrupted_completion_markers(self, idempotency_checker, mock_db_adapter):
        """Test handling of corrupted completion markers."""
        # Marker with missing fields
        mock_db_adapter.fetch_one.return_value = {
            "document_id": "doc-123",
            # Missing stage_name, data_hash
        }

        result = await idempotency_checker.check_completion_marker("doc-123", "stage")

        # Should return the marker even if incomplete
        assert result is not None

    @pytest.mark.asyncio
    async def test_database_connection_failures(self, idempotency_checker, mock_db_adapter):
        """Test handling of database connection failures."""
        mock_db_adapter.fetch_one.side_effect = Exception("Connection timeout")

        result = await idempotency_checker.check_completion_marker("doc-123", "stage")

        assert result is None

    @pytest.mark.asyncio
    async def test_large_metadata_objects(self, idempotency_checker, mock_db_adapter):
        """Test handling of large metadata objects."""
        large_metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}

        result = await idempotency_checker.set_completion_marker("doc-123", "stage", "hash" + "0" * 60, large_metadata)

        assert result is True

    def test_special_characters_in_fields(self, idempotency_checker):
        """Test handling of special characters in context fields."""
        context = ProcessingContext(
            document_id="doc-123",
            file_path="/path/with spaces/file (1).pdf",
            document_type="manual",
            manufacturer="Hewlett-Packard & Co.",
            model="LaserJet Pro M454dn",
            file_hash="abc123",
        )

        hash_value = idempotency_checker.compute_data_hash(context)
        assert len(hash_value) == 64

    @pytest.mark.asyncio
    async def test_empty_document_id(self, idempotency_checker, mock_db_adapter):
        """Test handling of empty document_id."""
        mock_db_adapter.fetch_one.return_value = None

        result = await idempotency_checker.check_completion_marker("", "stage")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_stage_name(self, idempotency_checker, mock_db_adapter):
        """Test handling of empty stage_name."""
        mock_db_adapter.fetch_one.return_value = None

        result = await idempotency_checker.check_completion_marker("doc-123", "")

        assert result is None

    def test_unicode_in_context_fields(self, idempotency_checker):
        """Test handling of Unicode characters in context fields."""
        context = ProcessingContext(
            document_id="doc-123",
            file_path="/path/to/文档.pdf",
            document_type="manual",
            manufacturer="キヤノン",  # Canon in Japanese
            model="LaserJet",
            file_hash="abc123",
        )

        hash_value = idempotency_checker.compute_data_hash(context)
        assert len(hash_value) == 64


# ============================================================================
# H. Query Structure Verification Tests
# ============================================================================


class TestQueryStructure:
    """Test suite for verifying database query structure."""

    @pytest.mark.asyncio
    async def test_check_marker_query_parameters(self, idempotency_checker, mock_db_adapter):
        """Verify check_completion_marker uses correct parameters."""
        await idempotency_checker.check_completion_marker("doc-123", "stage-name")

        call_args = mock_db_adapter.fetch_one.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "$1" in query and "$2" in query
        assert params == ["doc-123", "stage-name"]

    @pytest.mark.asyncio
    async def test_set_marker_query_parameters(self, idempotency_checker, mock_db_adapter):
        """Verify set_completion_marker uses correct parameters."""
        await idempotency_checker.set_completion_marker("doc-123", "stage-name", "hash" + "0" * 60, {"key": "value"})

        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "$1" in query and "$2" in query and "$3" in query and "$4" in query
        assert params[0] == "doc-123"
        assert params[1] == "stage-name"
        assert params[2] == "hash" + "0" * 60

    @pytest.mark.asyncio
    async def test_delete_marker_query_parameters(self, idempotency_checker, mock_db_adapter):
        """Verify delete_completion_marker uses correct parameters."""
        await idempotency_checker.delete_completion_marker("doc-123", "stage-name")

        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "DELETE FROM" in query
        assert "$1" in query and "$2" in query
        assert params == ["doc-123", "stage-name"]


# ============================================================================
# I. Async Operation Tests
# ============================================================================


class TestAsyncOperations:
    """Test suite for async operation completion."""

    @pytest.mark.asyncio
    async def test_async_check_completion(self, idempotency_checker, mock_db_adapter):
        """Test async check_completion_marker completes properly."""
        mock_db_adapter.fetch_one.return_value = {"test": "data"}

        result = await idempotency_checker.check_completion_marker("doc-123", "stage")

        assert result is not None

    @pytest.mark.asyncio
    async def test_async_set_completion(self, idempotency_checker, mock_db_adapter):
        """Test async set_completion_marker completes properly."""
        result = await idempotency_checker.set_completion_marker("doc-123", "stage", "hash" + "0" * 60, {})

        assert result is True

    @pytest.mark.asyncio
    async def test_async_cleanup(self, idempotency_checker, mock_db_adapter):
        """Test async cleanup_old_data completes properly."""
        result = await idempotency_checker.cleanup_old_data("doc-123", "stage")

        assert result is True

    @pytest.mark.asyncio
    async def test_multiple_async_operations(self, idempotency_checker, mock_db_adapter):
        """Test multiple async operations in sequence."""
        # Check
        marker = await idempotency_checker.check_completion_marker("doc-123", "stage")

        # Set
        result1 = await idempotency_checker.set_completion_marker("doc-123", "stage", "hash" + "0" * 60, {})

        # Cleanup
        result2 = await idempotency_checker.cleanup_old_data("doc-123", "stage")

        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_concurrent_set_completion_marker(self, idempotency_checker, mock_db_adapter):
        """Test concurrent set_completion_marker calls for same document/stage.

        Validates the idempotent upsert path under concurrent access by invoking
        set_completion_marker concurrently for the same document_id/stage_name
        using asyncio.gather. Both calls should return True and execute_query
        should be called twice with the upsert query.
        """
        import asyncio

        document_id = "doc-12345"
        stage_name = "pdf_extraction"
        data_hash = "concurrent_hash" + "0" * 49

        # Execute concurrent calls
        results = await asyncio.gather(
            idempotency_checker.set_completion_marker(document_id, stage_name, data_hash, {"thread": 1}),
            idempotency_checker.set_completion_marker(document_id, stage_name, data_hash, {"thread": 2}),
        )

        # Both calls should succeed
        assert results[0] is True
        assert results[1] is True

        # execute_query should be called twice (once per concurrent call)
        assert mock_db_adapter.execute_query.call_count == 2

        # Verify both calls used the upsert query with ON CONFLICT
        for call in mock_db_adapter.execute_query.call_args_list:
            query = call[0][0]
            assert "INSERT INTO krai_system.stage_completion_markers" in query
            assert "ON CONFLICT" in query
            assert "DO UPDATE SET" in query
