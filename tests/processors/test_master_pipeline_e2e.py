"""End-to-end style tests for KRMasterPipeline orchestration.

These tests exercise the high-level flow methods on KRMasterPipeline without
hitting real external systems. They rely on the mock fixtures from
`tests/processors/conftest.py` and focus on:

- Full pipeline processing for a new document
- Smart-processing path for duplicate / already known documents
- Smart stage selection in `process_document_smart_stages`
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = [pytest.mark.master_pipeline, pytest.mark.e2e]


class TestFullPipelineSmartProcessing:
    @pytest.mark.asyncio
    async def test_full_pipeline_new_document_runs_all_stages(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """New document should run through all stages in order.

        We stub each processor to record calls and return minimal success data.
        The goal is to validate orchestration and result aggregation rather than
        processor internals.
        """

        pdf_path = tmp_path / "new_document.pdf"
        pdf_path.write_text("dummy content for pipeline test")

        pipeline = mock_master_pipeline
        calls: list[str] = []

        class UploadStub:
            async def process(self, context):  # type: ignore[override]
                calls.append("upload")
                return SimpleNamespace(
                    success=True,
                    data={
                        "document_id": "doc-new-1",
                        "file_hash": "hash-123",
                        "document_type": "service_manual",
                        "duplicate": False,
                    },
                    message="upload ok",
                )

        class GenericStub:
            def __init__(self, name: str, data: dict[str, Any] | None = None) -> None:
                self.name = name
                self._data = data or {}

            async def process(self, context):  # type: ignore[override]
                calls.append(self.name)
                return SimpleNamespace(
                    success=True,
                    data=self._data,
                    message=f"{self.name} ok",
                )

        pipeline.processors = {
            "upload": UploadStub(),
            "text": GenericStub("text", {"chunks_created": 5}),
            "table": GenericStub("table", {"tables_extracted": 1}),
            "svg": GenericStub("svg", {"svgs_extracted": 0, "svgs_converted": 0}),
            "image": GenericStub("image", {"images_processed": 2}),
            "visual_embedding": GenericStub("visual_embedding", {"embeddings_created": 2}),
            "classification": GenericStub("classification"),
            "chunk_prep": GenericStub("chunk_prep", {"chunks_preprocessed": 4}),
            "links": GenericStub(
                "links",
                {"links_extracted": 1, "video_links_created": 0},
            ),
            "metadata": GenericStub("metadata", {"error_codes_found": 0}),
            "storage": GenericStub("storage"),
            "embedding": GenericStub("embedding"),
            "search": GenericStub("search"),
        }

        result = await pipeline.process_single_document_full_pipeline(
            str(pdf_path),
            1,
            1,
        )

        assert result["success"] is True
        assert result["smart_processing"] is False
        assert result["document_id"] == "doc-new-1"
        assert result["filename"] == pdf_path.name
        assert result["chunks"] == 5
        assert result["tables"] == 1
        assert result["images"] == 2
        assert "upload" in calls and "search" in calls
        assert calls[0] == "upload"
        assert calls[-1] == "search"

    @pytest.mark.asyncio
    async def test_full_pipeline_duplicate_document_uses_smart_processing(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Duplicate uploads should delegate to smart-processing helper.

        We stub the upload processor to report a duplicate and patch
        `process_document_smart_stages` to validate that it is called exactly
        once with the expected arguments.
        """

        pdf_path = tmp_path / "duplicate_document.pdf"
        pdf_path.write_text("duplicate content")

        pipeline = mock_master_pipeline
        calls: list[dict[str, Any]] = []

        class UploadDuplicateStub:
            async def process(self, context):  # type: ignore[override]
                return SimpleNamespace(
                    success=True,
                    data={"document_id": "doc-existing", "duplicate": True},
                    message="duplicate",
                )

        pipeline.processors["upload"] = UploadDuplicateStub()

        class ShouldNotBeCalled:
            async def process(self, context):  # type: ignore[override]
                raise AssertionError("Non-upload processors must not run for duplicates")

        for key in [
            "text",
            "table",
            "svg",
            "image",
            "visual_embedding",
            "classification",
            "chunk_prep",
            "links",
            "metadata",
            "storage",
            "embedding",
            "search",
        ]:
            pipeline.processors[key] = ShouldNotBeCalled()

        async def fake_smart(document_id: str, filename: str, file_path: str) -> dict[str, Any]:
            calls.append(
                {
                    "document_id": document_id,
                    "filename": filename,
                    "file_path": file_path,
                }
            )
            return {
                "success": True,
                "filename": filename,
                "completed_stages": ["text", "embedding"],
                "failed_stages": [],
                "quality_score": 95,
                "quality_passed": True,
            }

        monkeypatch.setattr(pipeline, "process_document_smart_stages", fake_smart)

        result = await pipeline.process_single_document_full_pipeline(
            str(pdf_path),
            1,
            1,
        )

        assert result["success"] is True
        assert result["smart_processing"] is True
        assert result["document_id"] == "doc-existing"
        assert result["filename"] == pdf_path.name
        assert result.get("completed_stages") == ["text", "embedding"]
        assert result.get("quality_score") == 95
        assert result.get("quality_passed") is True
        assert len(calls) == 1
        smart_call = calls[0]
        assert smart_call["document_id"] == "doc-existing"
        assert smart_call["filename"] == pdf_path.name


class TestProcessDocumentSmartStages:
    @pytest.mark.asyncio
    async def test_smart_stages_only_runs_missing_stages(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`process_document_smart_stages` should run only missing stages.

        We stub `get_document_stage_status` and all processors so we can assert
        exactly which stages were executed and that the document status is
        updated to `completed` when no failures occur.
        """

        pipeline = mock_master_pipeline
        pdf_path = tmp_path / "smart_manual.pdf"
        pdf_path.write_text("content")

        document_id = "doc-smart-1"
        filename = pdf_path.name

        monkeypatch.setenv("ENABLE_SVG_EXTRACTION", "true")

        async def fake_get_stage_status(doc_id: str) -> dict[str, bool]:
            assert doc_id == document_id
            return {
                "upload": True,
                "text": True,
                "svg": False,
                "image": False,
                "classification": False,
                "chunk_prep": False,
                "links": False,
                "metadata": False,
                "storage": False,
                "embedding": False,
                "search": False,
            }

        monkeypatch.setattr(pipeline, "get_document_stage_status", fake_get_stage_status)

        called: list[str] = []

        class RecordingStub:
            def __init__(self, name: str, data: dict[str, Any] | None = None) -> None:
                self.name = name
                self._data = data or {}

            async def process(self, context):  # type: ignore[override]
                called.append(self.name)
                return SimpleNamespace(success=True, data=self._data, message="ok")

        pipeline.processors.update(
            {
                "text": RecordingStub("text-already"),
                "svg": RecordingStub("svg"),
                "image": RecordingStub("image"),
                "classification": RecordingStub("classification"),
                "chunk_prep": RecordingStub("chunk_prep", {"chunks_preprocessed": 3}),
                "links": RecordingStub("links", {"links_extracted": 2, "video_links_created": 1}),
                "metadata": RecordingStub("metadata", {"error_codes_found": 1}),
                "storage": RecordingStub("storage"),
                "embedding": RecordingStub("embedding", {"embeddings_created": 10}),
                "search": RecordingStub("search"),
            }
        )

        async def fake_quality(doc_id: str) -> dict[str, Any]:
            return {
                "passed": True,
                "score": 90,
                "issues": [],
                "warnings": [],
            }

        pipeline.quality_service.check_document_quality = fake_quality  # type: ignore[assignment]

        async def fake_update_status(doc_id: str, status: str) -> None:
            pipeline._last_status = (doc_id, status)

        monkeypatch.setattr(
            pipeline.database_service,
            "update_document_status",
            fake_update_status,
            raising=False,
        )

        async def fake_get_document(doc_id: str) -> Any:
            return SimpleNamespace(file_hash="hash-x", document_type="service_manual")

        monkeypatch.setattr(
            pipeline.database_service,
            "get_document",
            fake_get_document,
            raising=False,
        )

        result = await pipeline.process_document_smart_stages(
            document_id,
            filename,
            str(pdf_path),
        )

        assert result["success"] is True
        assert set(result["failed_stages"]) == set()
        for expected in [
            "svg",
            "image",
            "classification",
            "chunk_prep",
            "links",
            "metadata",
            "storage",
            "embedding",
            "search",
        ]:
            assert expected in result["completed_stages"]
        assert "text" not in result["completed_stages"]
        assert getattr(pipeline, "_last_status", None) == (document_id, "completed")
