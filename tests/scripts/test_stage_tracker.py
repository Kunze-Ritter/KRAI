"""
Tests for StageTracker and StageContext
"""

from datetime import datetime
from typing import Any

import pytest

from backend.core.base_processor import Stage
from backend.processors.stage_tracker import StageContext, StageTracker


class MockDatabaseAdapter:
    """Mock database adapter for testing"""

    def __init__(self):
        self.execute_rpc_calls = []
        self.execute_query_calls = []
        self.execute_query_results = []

    async def execute_rpc(self, function_name: str, params: dict[str, Any]):
        """Mock RPC execution"""
        self.execute_rpc_calls.append((function_name, params))

        # Mock different responses based on function name
        if (
            function_name == "krai_core.start_stage"
            or function_name == "krai_core.update_stage_progress"
            or function_name == "krai_core.complete_stage"
            or function_name == "krai_core.fail_stage"
            or function_name == "krai_core.skip_stage"
        ):
            return True
        if function_name == "krai_core.get_document_progress":
            return 75.0
        if function_name == "krai_core.get_current_stage":
            return "embedding"
        if function_name == "krai_core.can_start_stage":
            return True
        return None

    async def execute_query(self, query: str, params: Any | None = None):
        """Mock query execution"""
        self.execute_query_calls.append((query, params))

        # Mock different responses based on query content
        if "stage_status" in query:
            return [
                {
                    "stage_status": {
                        "upload": {"status": "completed", "progress": 100},
                        "text_extraction": {"status": "completed", "progress": 100},
                        "embedding": {"status": "processing", "progress": 75},
                        "search_indexing": {"status": "pending", "progress": 0},
                    }
                }
            ]
        if "vw_stage_statistics" in query:
            return [
                {
                    "stage_name": "upload",
                    "pending_count": 0,
                    "processing_count": 0,
                    "completed_count": 10,
                    "failed_count": 1,
                    "skipped_count": 0,
                    "avg_duration_seconds": 5.2,
                },
                {
                    "stage_name": "embedding",
                    "pending_count": 2,
                    "processing_count": 1,
                    "completed_count": 7,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "avg_duration_seconds": 15.8,
                },
            ]
        return []


@pytest.fixture
def mock_adapter():
    """Fixture providing mock database adapter"""
    return MockDatabaseAdapter()


@pytest.fixture
def stage_tracker(mock_adapter):
    """Fixture providing StageTracker with mock adapter"""
    return StageTracker(mock_adapter)


class TestStageTracker:
    """Test StageTracker functionality"""

    @pytest.mark.asyncio
    async def test_start_stage(self, stage_tracker, mock_adapter):
        """Test starting a stage"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING

        result = await stage_tracker.start_stage(document_id, stage)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.start_stage"
        assert mock_adapter.execute_rpc_calls[0][1]["p_document_id"] == document_id
        assert mock_adapter.execute_rpc_calls[0][1]["p_stage_name"] == stage.value

    @pytest.mark.asyncio
    async def test_update_progress_fraction_to_percentage(self, stage_tracker, mock_adapter):
        """Test progress scaling from fraction (0-1) to percentage (0-100)"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING
        progress = 0.75  # 75%
        metadata = {"chunks_processed": 150}

        result = await stage_tracker.update_progress(document_id, stage, progress, metadata)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        call_params = mock_adapter.execute_rpc_calls[0][1]
        assert call_params["p_progress"] == 75.0  # Should be scaled to percentage
        assert call_params["p_metadata"]["progress_scale_adjusted"] is True
        assert call_params["p_metadata"]["chunks_processed"] == 150

    @pytest.mark.asyncio
    async def test_update_progress_percentage_passthrough(self, stage_tracker, mock_adapter):
        """Test that percentage values (0-100) pass through unchanged"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING
        progress = 75.0  # Already a percentage

        result = await stage_tracker.update_progress(document_id, stage, progress)

        assert result is True
        call_params = mock_adapter.execute_rpc_calls[0][1]
        assert call_params["p_progress"] == 75.0  # Should remain unchanged
        assert "progress_scale_adjusted" not in call_params["p_metadata"]

    @pytest.mark.asyncio
    async def test_complete_stage(self, stage_tracker, mock_adapter):
        """Test completing a stage"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING
        metadata = {"embeddings_created": 200, "processing_time": 15.5}

        result = await stage_tracker.complete_stage(document_id, stage, metadata)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.complete_stage"
        assert mock_adapter.execute_rpc_calls[0][1]["p_metadata"] == metadata

    @pytest.mark.asyncio
    async def test_fail_stage(self, stage_tracker, mock_adapter):
        """Test failing a stage"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING
        error = "Out of memory"
        metadata = {"memory_usage": "8GB"}

        result = await stage_tracker.fail_stage(document_id, stage, error, metadata)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.fail_stage"
        assert mock_adapter.execute_rpc_calls[0][1]["p_error"] == error
        assert mock_adapter.execute_rpc_calls[0][1]["p_metadata"] == metadata

    @pytest.mark.asyncio
    async def test_skip_stage(self, stage_tracker, mock_adapter):
        """Test skipping a stage"""
        document_id = "test-doc-123"
        stage = Stage.IMAGE_PROCESSING
        reason = "No images found"

        result = await stage_tracker.skip_stage(document_id, stage, reason)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.skip_stage"
        assert mock_adapter.execute_rpc_calls[0][1]["p_reason"] == reason

    @pytest.mark.asyncio
    async def test_get_progress(self, stage_tracker, mock_adapter):
        """Test getting document progress"""
        document_id = "test-doc-123"

        progress = await stage_tracker.get_progress(document_id)

        assert progress == 75.0
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.get_document_progress"
        assert mock_adapter.execute_rpc_calls[0][1]["p_document_id"] == document_id

    @pytest.mark.asyncio
    async def test_get_current_stage(self, stage_tracker, mock_adapter):
        """Test getting current stage"""
        document_id = "test-doc-123"

        current_stage = await stage_tracker.get_current_stage(document_id)

        assert current_stage == "embedding"
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.get_current_stage"

    @pytest.mark.asyncio
    async def test_can_start_stage(self, stage_tracker, mock_adapter):
        """Test checking if stage can start"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING

        can_start = await stage_tracker.can_start_stage(document_id, stage)

        assert can_start is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.can_start_stage"

    @pytest.mark.asyncio
    async def test_get_stage_status(self, stage_tracker, mock_adapter):
        """Test getting complete stage status"""
        document_id = "test-doc-123"

        stage_status = await stage_tracker.get_stage_status(document_id)

        assert isinstance(stage_status, dict)
        assert "upload" in stage_status
        assert stage_status["upload"]["status"] == "completed"
        assert len(mock_adapter.execute_query_calls) == 1

    @pytest.mark.asyncio
    async def test_get_statistics(self, stage_tracker, mock_adapter):
        """Test getting processing statistics"""
        stats = await stage_tracker.get_statistics()

        assert isinstance(stats, dict)
        assert "upload" in stats
        assert "embedding" in stats
        assert stats["upload"]["completed_count"] == 10
        assert stats["upload"]["failed_count"] == 1
        assert stats["embedding"]["processing_count"] == 1
        assert len(mock_adapter.execute_query_calls) == 1

    @pytest.mark.asyncio
    async def test_update_stage_progress_alias(self, stage_tracker, mock_adapter):
        """Test update_stage_progress alias method"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING
        progress = 50.0

        result = await stage_tracker.update_stage_progress(document_id, stage, progress)

        assert result is True
        assert len(mock_adapter.execute_rpc_calls) == 1
        assert mock_adapter.execute_rpc_calls[0][0] == "krai_core.update_stage_progress"

    def test_normalize_stage_with_enum(self, stage_tracker):
        """Test stage normalization with Stage enum"""
        stage = Stage.EMBEDDING
        normalized = stage_tracker._normalize_stage(stage)
        assert normalized == "embedding"

    def test_normalize_stage_with_string(self, stage_tracker):
        """Test stage normalization with string"""
        stage = "embedding"
        normalized = stage_tracker._normalize_stage(stage)
        assert normalized == "embedding"

    def test_make_json_safe(self, stage_tracker):
        """Test JSON serialization helper"""
        from uuid import UUID

        test_data = {
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "datetime": datetime(2023, 1, 1, 12, 0, 0),
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        safe_data = stage_tracker._make_json_safe(test_data)

        assert safe_data["uuid"] == "12345678-1234-5678-1234-567812345678"
        assert safe_data["datetime"] == "2023-01-01T12:00:00"
        assert safe_data["string"] == "test"
        assert safe_data["number"] == 42
        assert safe_data["list"] == [1, 2, 3]
        assert safe_data["dict"] == {"nested": "value"}


class TestStageContext:
    """Test StageContext functionality"""

    @pytest.mark.asyncio
    async def test_stage_context_success(self, stage_tracker, mock_adapter):
        """Test StageContext successful execution"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING

        async with StageContext(stage_tracker, document_id, stage) as ctx:
            # Update progress during processing
            await ctx.update_progress(25.0, {"chunks_processed": 50})
            await ctx.update_progress(50.0, {"chunks_processed": 100})
            await ctx.update_progress(100.0, {"chunks_processed": 200})

            # Set metadata
            ctx.set_metadata("processing_time", 10.5)

        # Verify stage lifecycle calls
        rpc_calls = mock_adapter.execute_rpc_calls
        assert len(rpc_calls) == 4  # start + 3 progress updates + complete

        # Verify start stage
        assert rpc_calls[0][0] == "krai_core.start_stage"
        assert rpc_calls[0][1]["p_document_id"] == document_id
        assert rpc_calls[0][1]["p_stage_name"] == stage.value

        # Verify progress updates
        assert rpc_calls[1][0] == "krai_core.update_stage_progress"
        assert rpc_calls[1][1]["p_progress"] == 25.0
        assert rpc_calls[1][1]["p_metadata"]["chunks_processed"] == 50

        assert rpc_calls[2][0] == "krai_core.update_stage_progress"
        assert rpc_calls[2][1]["p_progress"] == 50.0
        assert rpc_calls[2][1]["p_metadata"]["chunks_processed"] == 100

        assert rpc_calls[3][0] == "krai_core.update_stage_progress"
        assert rpc_calls[3][1]["p_progress"] == 100.0
        assert rpc_calls[3][1]["p_metadata"]["chunks_processed"] == 200
        assert rpc_calls[3][1]["p_metadata"]["processing_time"] == 10.5

        # Verify complete stage
        assert rpc_calls[4][0] == "krai_core.complete_stage"
        assert rpc_calls[4][1]["p_metadata"]["processing_time"] == 10.5

    @pytest.mark.asyncio
    async def test_stage_context_failure(self, stage_tracker, mock_adapter):
        """Test StageContext with exception"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING

        with pytest.raises(ValueError, match="Test error"):
            async with StageContext(stage_tracker, document_id, stage) as ctx:
                await ctx.update_progress(50.0, {"chunks_processed": 100})
                raise ValueError("Test error")

        # Verify stage lifecycle calls
        rpc_calls = mock_adapter.execute_rpc_calls
        assert len(rpc_calls) == 3  # start + progress + fail

        # Verify start stage
        assert rpc_calls[0][0] == "krai_core.start_stage"

        # Verify progress update
        assert rpc_calls[1][0] == "krai_core.update_stage_progress"
        assert rpc_calls[1][1]["p_progress"] == 50.0

        # Verify fail stage
        assert rpc_calls[2][0] == "krai_core.fail_stage"
        assert rpc_calls[2][1]["p_error"] == "Test error"
        assert rpc_calls[2][1]["p_metadata"]["chunks_processed"] == 100

    @pytest.mark.asyncio
    async def test_stage_context_metadata_merge(self, stage_tracker, mock_adapter):
        """Test StageContext metadata merging"""
        document_id = "test-doc-123"
        stage = Stage.EMBEDDING

        async with StageContext(stage_tracker, document_id, stage) as ctx:
            # Update progress with metadata
            await ctx.update_progress(25.0, {"chunks_processed": 50})
            await ctx.update_progress(50.0, {"embeddings_created": 25})

            # Set additional metadata
            ctx.set_metadata("model", "nomic-embed-text")

        # Verify metadata is merged in final complete stage call
        rpc_calls = mock_adapter.execute_rpc_calls
        complete_call = rpc_calls[-1]  # Last call should be complete_stage

        assert complete_call[0] == "krai_core.complete_stage"
        metadata = complete_call[1]["p_metadata"]
        assert metadata["chunks_processed"] == 50
        assert metadata["embeddings_created"] == 25
        assert metadata["model"] == "nomic-embed-text"


if __name__ == "__main__":
    pytest.main([__file__])
