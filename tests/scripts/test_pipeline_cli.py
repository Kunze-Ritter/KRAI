"""
Tests for Pipeline CLI functionality
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts to path for testing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pipeline_processor import (
    list_stages,
    main,
    parse_stage_input,
    run_multiple_stages,
    run_single_stage,
    run_smart_processing,
    show_status,
    upload_file,
)

from backend.core.base_processor import Stage


class TestParseStageInput:
    """Test stage input parsing"""

    def test_parse_stage_by_number(self):
        """Test parsing stage by number"""
        assert parse_stage_input("1") == Stage.UPLOAD
        assert parse_stage_input("7") == Stage.EMBEDDING
        assert parse_stage_input("15") == Stage.SEARCH_INDEXING

    def test_parse_stage_by_name(self):
        """Test parsing stage by name"""
        assert parse_stage_input("upload") == Stage.UPLOAD
        assert parse_stage_input("embedding") == Stage.EMBEDDING
        assert parse_stage_input("search_indexing") == Stage.SEARCH_INDEXING

    def test_parse_stage_invalid_number(self):
        """Test parsing invalid stage number"""
        with pytest.raises(ValueError, match="Invalid stage number"):
            parse_stage_input("16")
        with pytest.raises(ValueError, match="Invalid stage number"):
            parse_stage_input("0")

    def test_parse_stage_invalid_name(self):
        """Test parsing invalid stage name"""
        with pytest.raises(ValueError, match="Invalid stage"):
            parse_stage_input("invalid_stage")
        with pytest.raises(ValueError, match="Invalid stage"):
            parse_stage_input("")


class MockPipeline:
    """Mock KRMasterPipeline for testing"""

    def __init__(self):
        self.initialize_services = AsyncMock()
        self.get_available_stages = MagicMock(return_value=list(Stage))
        self.get_stage_status = AsyncMock()
        self.run_single_stage = AsyncMock()
        self.run_stages = AsyncMock()
        self.database_service = MagicMock()
        self.database_service.adapter = None


class TestCLICommands:
    """Test CLI command functions"""

    @pytest.mark.asyncio
    async def test_list_stages(self, capsys):
        """Test listing stages"""
        mock_pipeline = MockPipeline()

        await list_stages(mock_pipeline)

        captured = capsys.readouterr()
        assert "Available Pipeline Stages:" in captured.out
        assert "Total: 15 stages" in captured.out

    @pytest.mark.asyncio
    async def test_show_status_document_found(self, capsys):
        """Test showing status for existing document"""
        mock_pipeline = MockPipeline()
        mock_pipeline.get_stage_status.return_value = {
            "found": True,
            "stage_status": {
                "upload": {"status": "completed"},
                "embedding": {"status": "processing", "progress": 75},
                "search_indexing": {"status": "pending"},
            },
        }

        await show_status(mock_pipeline, "test-doc-123")

        captured = capsys.readouterr()
        assert "Document Status: test-doc-123" in captured.out
        assert "✅ upload: completed" in captured.out
        assert "🔄 embedding: processing" in captured.out
        assert "⏳ search_indexing: pending" in captured.out

    @pytest.mark.asyncio
    async def test_show_status_document_not_found(self, capsys):
        """Test showing status for non-existent document"""
        mock_pipeline = MockPipeline()
        mock_pipeline.get_stage_status.return_value = {"found": False, "error": "Document not found"}

        await show_status(mock_pipeline, "nonexistent-doc")

        captured = capsys.readouterr()
        assert "❌ Document not found: nonexistent-doc" in captured.out
        assert "Error: Document not found" in captured.out

    @pytest.mark.asyncio
    async def test_run_single_stage_success(self, capsys):
        """Test running a single stage successfully"""
        mock_pipeline = MockPipeline()
        mock_pipeline.run_single_stage.return_value = {
            "success": True,
            "data": {"embeddings_created": 200, "processing_time": 15.5},
        }

        await run_single_stage(mock_pipeline, "test-doc-123", "embedding")

        captured = capsys.readouterr()
        assert "Running stage: embedding for document: test-doc-123" in captured.out
        assert "✅ Stage completed successfully!" in captured.out
        assert "embeddings_created: 200" in captured.out
        assert "processing_time: 15.5" in captured.out

    @pytest.mark.asyncio
    async def test_run_single_stage_failure(self, capsys):
        """Test running a single stage with failure"""
        mock_pipeline = MockPipeline()
        mock_pipeline.run_single_stage.return_value = {"success": False, "error": "Out of memory"}

        await run_single_stage(mock_pipeline, "test-doc-123", "embedding")

        captured = capsys.readouterr()
        assert "❌ Stage failed!" in captured.out
        assert "Error: Out of memory" in captured.out

    @pytest.mark.asyncio
    async def test_run_multiple_stages_success(self, capsys):
        """Test running multiple stages successfully"""
        mock_pipeline = MockPipeline()
        mock_pipeline.run_stages.return_value = {
            "total_stages": 3,
            "successful": 2,
            "failed": 1,
            "success_rate": 66.7,
            "stage_results": [
                {"stage": "upload", "success": True},
                {"stage": "text_extraction", "success": True},
                {"stage": "embedding", "success": False, "error": "Memory error"},
            ],
        }

        await run_multiple_stages(mock_pipeline, "test-doc-123", ["upload", "text_extraction", "embedding"])

        captured = capsys.readouterr()
        assert "Running 3 stages for document: test-doc-123" in captured.out
        assert "Total stages: 3" in captured.out
        assert "Successful: 2" in captured.out
        assert "Failed: 1" in captured.out
        assert "Success rate: 66.7%" in captured.out
        assert "✅ upload" in captured.out
        assert "✅ text_extraction" in captured.out
        assert "❌ embedding" in captured.out
        assert "Error: Memory error" in captured.out

    @pytest.mark.asyncio
    async def test_run_smart_processing(self, capsys):
        """Test smart processing functionality"""
        mock_pipeline = MockPipeline()
        mock_pipeline.get_stage_status.return_value = {
            "found": True,
            "stage_status": {
                "upload": {"status": "completed"},
                "text_extraction": {"status": "completed"},
                "embedding": {"status": "failed"},
                "search_indexing": {"status": "pending"},
            },
        }
        mock_pipeline.run_stages.return_value = {
            "total_stages": 2,
            "successful": 2,
            "failed": 0,
            "success_rate": 100.0,
            "stage_results": [{"stage": "embedding", "success": True}, {"stage": "search_indexing", "success": True}],
        }

        await run_smart_processing(mock_pipeline, "test-doc-123")

        captured = capsys.readouterr()
        assert "Smart processing for document: test-doc-123" in captured.out
        assert "Stages to run: 2" in captured.out
        assert "- embedding" in captured.out
        assert "- search_indexing" in captured.out
        assert "Smart Processing Results:" in captured.out
        assert "Successful: 2" in captured.out

    @pytest.mark.asyncio
    async def test_run_smart_processing_all_completed(self, capsys):
        """Test smart processing when all stages are completed"""
        mock_pipeline = MockPipeline()
        mock_pipeline.get_stage_status.return_value = {
            "found": True,
            "stage_status": {
                "upload": {"status": "completed"},
                "text_extraction": {"status": "completed"},
                "embedding": {"status": "completed"},
                "search_indexing": {"status": "completed"},
            },
        }

        await run_smart_processing(mock_pipeline, "test-doc-123")

        captured = capsys.readouterr()
        assert "✅ All stages are already completed!" in captured.out


class TestUploadFunctionality:
    """Test upload functionality"""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, capsys):
        """Test successful file upload"""
        mock_pipeline = MockPipeline()
        mock_adapter = MagicMock()
        mock_pipeline.database_service.adapter = mock_adapter

        # Mock UploadProcessor
        with patch("pipeline_processor.UploadProcessor") as mock_upload_processor_class:
            mock_processor = MagicMock()
            mock_upload_processor_class.return_value = mock_processor

            # Mock successful upload result
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.document_id = "new-doc-123"
            mock_processor.process = AsyncMock(return_value=mock_result)

            document_id = await upload_file(mock_pipeline, "/path/to/file.pdf")

            assert document_id == "new-doc-123"

            captured = capsys.readouterr()
            assert "Uploading file: /path/to/file.pdf" in captured.out
            assert "✅ File uploaded successfully!" in captured.out
            assert "Document ID: new-doc-123" in captured.out

    @pytest.mark.asyncio
    async def test_upload_file_failure(self, capsys):
        """Test file upload failure"""
        mock_pipeline = MockPipeline()
        mock_adapter = MagicMock()
        mock_pipeline.database_service.adapter = mock_adapter

        # Mock UploadProcessor
        with patch("pipeline_processor.UploadProcessor") as mock_upload_processor_class:
            mock_processor = MagicMock()
            mock_upload_processor_class.return_value = mock_processor

            # Mock failed upload result
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.error = "File too large"
            mock_processor.process = AsyncMock(return_value=mock_result)

            with pytest.raises(SystemExit):
                await upload_file(mock_pipeline, "/path/to/large.pdf")

            captured = capsys.readouterr()
            assert "❌ Upload failed: File too large" in captured.out


class TestMainCLI:
    """Test main CLI functionality"""

    @pytest.mark.asyncio
    async def test_main_list_stages(self, capsys, monkeypatch):
        """Test main CLI with --list-stages"""
        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", ["pipeline_processor.py", "--list-stages"])

        # Mock pipeline initialization
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline_class.return_value = mock_pipeline

            # Mock list_stages
            with patch("pipeline_processor.list_stages") as mock_list_stages:
                mock_list_stages.return_value = asyncio.Future()
                mock_list_stages.return_value.set_result(None)

                with pytest.raises(SystemExit) as exc_info:
                    await main()

                assert exc_info.value.code == 0
                mock_list_stages.assert_called_once_with(mock_pipeline)

    @pytest.mark.asyncio
    async def test_main_upload_first_flow(self, capsys, monkeypatch):
        """Test main CLI with upload-first flow"""
        # Mock sys.argv
        monkeypatch.setattr(
            sys, "argv", ["pipeline_processor.py", "--file-path", "/path/to/file.pdf", "--stage", "upload"]
        )

        # Mock pipeline initialization
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline_class.return_value = mock_pipeline

            # Mock upload_file
            with patch("pipeline_processor.upload_file") as mock_upload_file:
                mock_upload_file.return_value = asyncio.Future()
                mock_upload_file.return_value.set_result("new-doc-123")

                with pytest.raises(SystemExit) as exc_info:
                    await main()

                assert exc_info.value.code == 0
                mock_upload_file.assert_called_once_with(mock_pipeline, "/path/to/file.pdf", "service_manual")

    @pytest.mark.asyncio
    async def test_main_upload_first_flow_invalid_stage(self, capsys, monkeypatch):
        """Test main CLI with upload-first flow but invalid stage"""
        # Mock sys.argv
        monkeypatch.setattr(
            sys, "argv", ["pipeline_processor.py", "--file-path", "/path/to/file.pdf", "--stage", "embedding"]
        )

        # Mock pipeline initialization
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1

            captured = capsys.readouterr()
            assert "❌ Error: --file-path requires --stage upload or --stage 1" in captured.out
            assert "You requested stage: embedding" in captured.out

    @pytest.mark.asyncio
    async def test_main_missing_document_id(self, capsys, monkeypatch):
        """Test main CLI with missing document ID"""
        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", ["pipeline_processor.py", "--stage", "embedding"])

        # Mock pipeline initialization
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1

            captured = capsys.readouterr()
            assert "❌ Error: --document-id is required for --stage" in captured.out

    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self, monkeypatch):
        """Test main CLI with keyboard interrupt"""
        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", ["pipeline_processor.py", "--list-stages"])

        # Mock pipeline initialization to raise KeyboardInterrupt
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline.initialize_services = AsyncMock(side_effect=KeyboardInterrupt())
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_main_unexpected_error(self, monkeypatch):
        """Test main CLI with unexpected error"""
        # Mock sys.argv
        monkeypatch.setattr(sys, "argv", ["pipeline_processor.py", "--list-stages"])

        # Mock pipeline initialization to raise exception
        with patch("pipeline_processor.KRMasterPipeline") as mock_pipeline_class:
            mock_pipeline = MockPipeline()
            mock_pipeline.initialize_services = AsyncMock(side_effect=Exception("Database connection failed"))
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1


class TestCLIIntegration:
    """Integration tests for CLI functionality"""

    @pytest.mark.asyncio
    async def test_parse_stage_input_integration(self):
        """Test stage parsing integration"""
        # Test all valid stage numbers
        stage_mapping = {
            1: Stage.UPLOAD,
            2: Stage.TEXT_EXTRACTION,
            3: Stage.TABLE_EXTRACTION,
            4: Stage.SVG_PROCESSING,
            5: Stage.IMAGE_PROCESSING,
            6: Stage.VISUAL_EMBEDDING,
            7: Stage.LINK_EXTRACTION,
            8: Stage.CHUNK_PREPROCESSING,
            9: Stage.CLASSIFICATION,
            10: Stage.METADATA_EXTRACTION,
            11: Stage.PARTS_EXTRACTION,
            12: Stage.SERIES_DETECTION,
            13: Stage.STORAGE,
            14: Stage.EMBEDDING,
            15: Stage.SEARCH_INDEXING,
        }

        for num, expected_stage in stage_mapping.items():
            assert parse_stage_input(str(num)) == expected_stage

        # Test all valid stage names
        for stage in Stage:
            assert parse_stage_input(stage.value) == stage

    @pytest.mark.asyncio
    async def test_stage_number_mapping_completeness(self):
        """Test that all stage numbers are mapped correctly"""
        # This ensures the CLI mapping matches the Stage enum
        for i, stage in enumerate(Stage, 1):
            assert parse_stage_input(str(i)) == stage


if __name__ == "__main__":
    pytest.main([__file__])
