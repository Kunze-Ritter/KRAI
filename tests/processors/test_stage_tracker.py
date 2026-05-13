#!/usr/bin/env python3
"""
Test Suite for Stage Tracker

Comprehensive tests for the stage tracking system including:
- PostgreSQL adapter integration
- Stage status management
- Progress tracking
- Error handling
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.base_processor import Stage
from backend.processors.stage_tracker import StageContext, StageTracker
from backend.services.postgresql_adapter import PostgreSQLAdapter


class TestStageTracker:
    """Test suite for StageTracker class"""

    @pytest.fixture
    async def mock_adapter(self):
        """Create a mock PostgreSQL adapter"""
        adapter = AsyncMock(spec=PostgreSQLAdapter)

        # Mock RPC responses
        adapter.rpc.return_value = {"success": True}
        adapter.execute_query.return_value = [{"stage_status": {}}]

        return adapter

    @pytest.fixture
    async def stage_tracker(self, mock_adapter):
        """Create StageTracker instance with mock adapter"""
        return StageTracker(mock_adapter)

    @pytest.mark.asyncio
    async def test_start_stage(self, stage_tracker, mock_adapter):
        """Test starting a stage"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value

        result = await stage_tracker.start_stage(document_id, stage)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.start_stage", {"document_id": document_id, "stage": stage, "metadata": {}}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_start_stage_with_metadata(self, stage_tracker, mock_adapter):
        """Test starting a stage with metadata"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        metadata = {"test": "value"}

        await stage_tracker.start_stage(document_id, stage, metadata)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.start_stage", {"document_id": document_id, "stage": stage, "metadata": metadata}
        )

    @pytest.mark.asyncio
    async def test_update_progress(self, stage_tracker, mock_adapter):
        """Test updating stage progress"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        progress = 50

        await stage_tracker.update_progress(document_id, stage, progress)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.update_stage_progress",
            {"document_id": document_id, "stage": stage, "progress": progress, "metadata": {}},
        )

    @pytest.mark.asyncio
    async def test_complete_stage(self, stage_tracker, mock_adapter):
        """Test completing a stage"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value

        await stage_tracker.complete_stage(document_id, stage)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.complete_stage", {"document_id": document_id, "stage": stage, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_fail_stage(self, stage_tracker, mock_adapter):
        """Test failing a stage"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        error = "Test error"

        await stage_tracker.fail_stage(document_id, stage, error)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.fail_stage", {"document_id": document_id, "stage": stage, "error": error, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_skip_stage(self, stage_tracker, mock_adapter):
        """Test skipping a stage"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        reason = "Test reason"

        await stage_tracker.skip_stage(document_id, stage, reason)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.skip_stage", {"document_id": document_id, "stage": stage, "reason": reason, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_get_progress(self, stage_tracker, mock_adapter):
        """Test getting document progress"""
        document_id = "test-doc-123"
        expected_result = {"total_stages": 15, "completed": 5}
        mock_adapter.rpc.return_value = expected_result

        result = await stage_tracker.get_progress(document_id)

        mock_adapter.rpc.assert_called_once_with("krai_core.get_document_progress", {"document_id": document_id})
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_get_current_stage(self, stage_tracker, mock_adapter):
        """Test getting current stage"""
        document_id = "test-doc-123"
        expected_stage = Stage.TEXT_EXTRACTION.value
        mock_adapter.rpc.return_value = {"current_stage": expected_stage}

        result = await stage_tracker.get_current_stage(document_id)

        mock_adapter.rpc.assert_called_once_with("krai_core.get_current_stage", {"document_id": document_id})
        assert result == expected_stage

    @pytest.mark.asyncio
    async def test_can_start_stage(self, stage_tracker, mock_adapter):
        """Test checking if stage can start"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        mock_adapter.rpc.return_value = {"can_start": True}

        result = await stage_tracker.can_start_stage(document_id, stage)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.can_start_stage", {"document_id": document_id, "stage": stage}
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_get_stage_status(self, stage_tracker, mock_adapter):
        """Test getting stage status"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        expected_status = {"status": "completed"}
        mock_adapter.rpc.return_value = expected_status

        result = await stage_tracker.get_stage_status(document_id, stage)

        mock_adapter.rpc.assert_called_once_with(
            "krai_core.get_stage_status", {"document_id": document_id, "stage": stage}
        )
        assert result == expected_status

    @pytest.mark.asyncio
    async def test_get_statistics(self, stage_tracker, mock_adapter):
        """Test getting stage statistics"""
        expected_stats = {"total_documents": 100, "completed_stages": 500}
        mock_adapter.execute_query.return_value = [expected_stats]

        result = await stage_tracker.get_statistics()

        mock_adapter.execute_query.assert_called_once_with("SELECT * FROM public.vw_stage_statistics")
        assert result == expected_stats

    @pytest.mark.asyncio
    async def test_stage_context(self, mock_adapter):
        """Test StageContext context manager"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value

        async with StageContext(mock_adapter, document_id, stage) as context:
            assert context.document_id == document_id
            assert context.stage == stage

        # Verify stage was completed
        mock_adapter.rpc.assert_any_call(
            "krai_core.start_stage", {"document_id": document_id, "stage": stage, "metadata": {}}
        )
        mock_adapter.rpc.assert_any_call(
            "krai_core.complete_stage", {"document_id": document_id, "stage": stage, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_stage_context_with_exception(self, mock_adapter):
        """Test StageContext handles exceptions properly"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        error_msg = "Test error"

        try:
            async with StageContext(mock_adapter, document_id, stage) as context:
                raise ValueError(error_msg)
        except ValueError:
            pass  # Expected

        # Verify stage was marked as failed
        mock_adapter.rpc.assert_any_call(
            "krai_core.fail_stage", {"document_id": document_id, "stage": stage, "error": error_msg, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_stage_context_update_progress(self, mock_adapter):
        """Test StageContext progress updates"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value

        async with StageContext(mock_adapter, document_id, stage) as context:
            await context.update_progress(50)
            await context.update_progress(75, {"extra": "info"})

        # Verify progress updates
        mock_adapter.rpc.assert_any_call(
            "krai_core.update_stage_progress",
            {"document_id": document_id, "stage": stage, "progress": 50, "metadata": {}},
        )
        mock_adapter.rpc.assert_any_call(
            "krai_core.update_stage_progress",
            {"document_id": document_id, "stage": stage, "progress": 75, "metadata": {"extra": "info"}},
        )

    @pytest.mark.asyncio
    async def test_stage_context_skip(self, mock_adapter):
        """Test StageContext skip functionality"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        reason = "Not needed"

        async with StageContext(mock_adapter, document_id, stage) as context:
            await context.skip(reason)

        # Verify stage was skipped
        mock_adapter.rpc.assert_any_call(
            "krai_core.skip_stage", {"document_id": document_id, "stage": stage, "reason": reason, "metadata": {}}
        )

    @pytest.mark.asyncio
    async def test_rpc_error_handling(self, stage_tracker, mock_adapter):
        """Test RPC error handling"""
        document_id = "test-doc-123"
        stage = Stage.UPLOAD.value
        mock_adapter.rpc.side_effect = Exception("RPC Error")

        # Should not raise exception, should log error
        result = await stage_tracker.start_stage(document_id, stage)
        assert result is None


class TestPostgreSQLAdapterStageTracking:
    """Test suite for PostgreSQL adapter stage tracking methods"""

    @pytest.fixture
    async def adapter(self):
        """Create PostgreSQL adapter with mocked pool"""
        with patch("backend.services.postgresql_adapter.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            adapter = PostgreSQLAdapter(connection_string="postgresql://test", logger=MagicMock())
            adapter._pool = mock_pool
            adapter._connection_string = "postgresql://test"

            return adapter

    @pytest.mark.asyncio
    async def test_start_stage_success(self, adapter):
        """Test successful stage start"""
        document_id = "test-doc-123"
        stage = "upload"
        metadata = {"test": "value"}

        adapter.rpc = AsyncMock(return_value={"success": True})

        result = await adapter.start_stage(document_id, stage, metadata)

        adapter.rpc.assert_called_once_with(
            "krai_core.start_stage", {"document_id": document_id, "stage": stage, "metadata": metadata}
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_start_stage_error(self, adapter):
        """Test stage start with error"""
        document_id = "test-doc-123"
        stage = "upload"

        adapter.rpc = AsyncMock(side_effect=Exception("Database error"))
        adapter.logger = MagicMock()

        result = await adapter.start_stage(document_id, stage)

        assert result["success"] is False
        assert "error" in result
        adapter.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_stage(self, adapter):
        """Test stage completion"""
        document_id = "test-doc-123"
        stage = "upload"
        metadata = {"chunks_processed": 100}

        adapter.rpc = AsyncMock(return_value={"success": True})

        result = await adapter.complete_stage(document_id, stage, metadata)

        adapter.rpc.assert_called_once_with(
            "krai_core.complete_stage", {"document_id": document_id, "stage": stage, "metadata": metadata}
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_fail_stage(self, adapter):
        """Test stage failure"""
        document_id = "test-doc-123"
        stage = "upload"
        error = "Processing failed"
        metadata = {"error_code": 500}

        adapter.rpc = AsyncMock(return_value={"success": True})

        result = await adapter.fail_stage(document_id, stage, error, metadata)

        adapter.rpc.assert_called_once_with(
            "krai_core.fail_stage", {"document_id": document_id, "stage": stage, "error": error, "metadata": metadata}
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_get_current_stage(self, adapter):
        """Test getting current stage"""
        document_id = "test-doc-123"
        expected_stage = "text_extraction"

        adapter.rpc = AsyncMock(return_value={"current_stage": expected_stage})

        result = await adapter.get_current_stage(document_id)

        adapter.rpc.assert_called_once_with("krai_core.get_current_stage", {"document_id": document_id})
        assert result == expected_stage

    @pytest.mark.asyncio
    async def test_get_stage_statistics(self, adapter):
        """Test getting stage statistics"""
        expected_stats = {"total_documents": 100, "completed_stages": 500, "failed_stages": 5}

        adapter.execute_query = AsyncMock(return_value=[expected_stats])

        result = await adapter.get_stage_statistics()

        adapter.execute_query.assert_called_once_with("SELECT * FROM public.vw_stage_statistics LIMIT 1")
        assert result == expected_stats


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
