"""Error recovery tests for KRMasterPipeline.

These tests focus on how the master pipeline reacts to failures:

- `run_single_stage` when a processor raises an exception
- `process_single_document_full_pipeline` when upload fails
- `process_single_document_full_pipeline` when a later stage crashes
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.base_processor import Stage
from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = [pytest.mark.master_pipeline, pytest.mark.error_recovery]


class TestRunSingleStageErrorHandling:
    @pytest.mark.asyncio
    async def test_run_single_stage_processor_exception_returns_error_dict(
        self,
        mock_master_pipeline: KRMasterPipeline,
        mock_database_adapter,
    ) -> None:
        """If the processor raises, `run_single_stage` should catch and wrap it."""

        pipeline = mock_master_pipeline

        # Seed minimal document so context creation succeeds
        document_id = "doc-error-1"
        mock_database_adapter.documents[document_id] = {
            "id": document_id,
            "document_type": "service_manual",
        }

        class FailingProcessor:
            async def process(self, context):  # type: ignore[override]
                raise RuntimeError("processor boom")

        pipeline.processors["embedding"] = FailingProcessor()
        pipeline.database_service = mock_database_adapter

        result = await pipeline.run_single_stage(document_id, Stage.EMBEDDING)

        assert result["success"] is False
        assert result["stage"] == Stage.EMBEDDING.value
        assert "processor boom" in result["error"]


class TestFullPipelineErrorHandling:
    @pytest.mark.asyncio
    async def test_full_pipeline_upload_failure_returns_clean_error(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """Upload failures should be returned as a clear error dict."""

        pipeline = mock_master_pipeline
        pdf_path = tmp_path / "bad_upload.pdf"
        pdf_path.write_text("content")

        class UploadFailStub:
            async def process(self, context):  # type: ignore[override]
                return SimpleNamespace(success=False, data=None, message="invalid file")

        pipeline.processors["upload"] = UploadFailStub()

        result = await pipeline.process_single_document_full_pipeline(
            str(pdf_path),
            1,
            1,
        )

        assert result["success"] is False
        assert "Upload failed" in result["error"]
        assert "invalid file" in result["error"]
        assert result["filename"] == pdf_path.name

    @pytest.mark.asyncio
    async def test_full_pipeline_mid_stage_exception_returns_error(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """Exceptions in later stages should bubble up as structured error dicts."""

        pipeline = mock_master_pipeline
        pdf_path = tmp_path / "crash_in_text.pdf"
        pdf_path.write_text("content")

        class UploadOkStub:
            async def process(self, context):  # type: ignore[override]
                return SimpleNamespace(
                    success=True,
                    data={
                        "document_id": "doc-mid-1",
                        "file_hash": "hash-mid",
                        "document_type": "service_manual",
                        "duplicate": False,
                    },
                    message="ok",
                )

        class TextCrashStub:
            async def process(self, context):  # type: ignore[override]
                raise RuntimeError("text stage crash")

        pipeline.processors["upload"] = UploadOkStub()
        pipeline.processors["text"] = TextCrashStub()

        result = await pipeline.process_single_document_full_pipeline(
            str(pdf_path),
            1,
            1,
        )

        assert result["success"] is False
        assert "text stage crash" in result["error"]
        assert result["filename"] == pdf_path.name
