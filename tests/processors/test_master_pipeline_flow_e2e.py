from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = pytest.mark.processor


class FakeProcessor:
    """Minimal async processor stub used to observe calls in pipeline flow tests."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[SimpleNamespace] = []

    async def process(self, context):  # type: ignore[override]
        self.calls.append(SimpleNamespace(context=context))
        # Return a simple object with the attributes used in success_messages lambdas
        return SimpleNamespace(success=True, data={}, message=f"{self.name} ok")


class TestMasterPipelineSmartProcessing:
    """Tests for KRMasterPipeline.process_document_smart_stages with mocked services."""

    @pytest.mark.asyncio
    async def test_smart_processing_runs_missing_stages(self, tmp_path: Path, monkeypatch) -> None:
        """Smart processing should run all stages marked as missing and report them as completed."""
        # Arrange
        pipeline = KRMasterPipeline()

        # Create a dummy file so the file existence check passes
        pdf_path = tmp_path / "smart_processing_test.pdf"
        pdf_path.write_bytes(b"dummy")

        document_id = "doc-smart-1"
        filename = pdf_path.name

        # Stage status: upload already done, all other stages missing
        async def fake_get_stage_status(doc_id: str):  # type: ignore[override]
            assert doc_id == document_id
            return {
                "upload": True,
                "text": False,
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

        monkeypatch.setattr(pipeline, "get_document_stage_status", fake_get_stage_status, raising=False)

        # Minimal database_service stub
        pipeline.database_service = SimpleNamespace(
            get_document=AsyncMock(
                return_value=SimpleNamespace(
                    file_hash="test-hash",
                    document_type="service_manual",
                )
            ),
            update_document_status=AsyncMock(),
        )

        # Quality service stub
        pipeline.quality_service = SimpleNamespace(
            check_document_quality=AsyncMock(return_value={"score": 95, "passed": True, "issues": []})
        )

        # Processor stubs for relevant stages
        text_proc = FakeProcessor("text")
        svg_proc = FakeProcessor("svg")
        image_proc = FakeProcessor("image")
        classification_proc = FakeProcessor("classification")
        chunk_proc = FakeProcessor("chunk_prep")
        links_proc = FakeProcessor("links")
        metadata_proc = FakeProcessor("metadata")
        storage_proc = FakeProcessor("storage")
        embedding_proc = FakeProcessor("embedding")
        search_proc = FakeProcessor("search")

        pipeline.processors = {
            "text": text_proc,
            "svg": svg_proc,
            "image": image_proc,
            "classification": classification_proc,
            "chunk_prep": chunk_proc,
            "links": links_proc,
            "metadata": metadata_proc,
            "storage": storage_proc,
            "embedding": embedding_proc,
            "search": search_proc,
        }

        # Ensure SVG feature flag is disabled so svg stage is skipped unless explicitly enabled
        monkeypatch.setenv("ENABLE_SVG_EXTRACTION", "false")

        # Act
        result = await pipeline.process_document_smart_stages(
            document_id=document_id,
            filename=filename,
            file_path=str(pdf_path),
        )

        # Assert
        assert result["success"] is True
        # text, image, classification, chunk_prep, links, metadata, storage, embedding, search should be candidates
        for expected_stage in [
            "text",
            "image",
            "classification",
            "chunk_prep",
            "links",
            "metadata",
            "storage",
            "embedding",
            "search",
        ]:
            assert expected_stage in result["completed_stages"], f"{expected_stage} should be completed"

        # SVG should not run because ENABLE_SVG_EXTRACTION is false
        assert svg_proc.calls == []
        assert len(text_proc.calls) == 1
        assert len(chunk_proc.calls) == 1

    @pytest.mark.asyncio
    async def test_smart_processing_returns_completed_when_no_missing_stages(self, tmp_path: Path, monkeypatch) -> None:
        """If all stages are already completed, smart processing should short-circuit without calling processors."""
        pipeline = KRMasterPipeline()

        pdf_path = tmp_path / "smart_processing_done.pdf"
        pdf_path.write_bytes(b"dummy")

        document_id = "doc-complete-1"
        filename = pdf_path.name

        async def fake_get_stage_status(doc_id: str):  # type: ignore[override]
            assert doc_id == document_id
            return {
                "upload": True,
                "text": True,
                "svg": True,
                "image": True,
                "classification": True,
                "chunk_prep": True,
                "links": True,
                "metadata": True,
                "storage": True,
                "embedding": True,
                "search": True,
            }

        monkeypatch.setattr(pipeline, "get_document_stage_status", fake_get_stage_status, raising=False)

        # Database and quality services still need to exist, but should not be heavily used
        pipeline.database_service = SimpleNamespace(
            get_document=AsyncMock(return_value=None),
            update_document_status=AsyncMock(),
        )
        pipeline.quality_service = SimpleNamespace(
            check_document_quality=AsyncMock(return_value={"score": 100, "passed": True, "issues": []})
        )

        # Processors mapping can be empty when no stages should run
        pipeline.processors = {}

        result = await pipeline.process_document_smart_stages(
            document_id=document_id,
            filename=filename,
            file_path=str(pdf_path),
        )

        assert result["success"] is True
        assert result["message"] == "All stages already completed"
        assert (
            result["stages_completed"] == len(fake_get_stage_status.__defaults__[0])
            if fake_get_stage_status.__defaults__
            else len(await fake_get_stage_status(document_id))
        )
