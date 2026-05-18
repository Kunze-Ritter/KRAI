"""Status tracking and quality check tests for KRMasterPipeline.

This module focuses on:
- `get_document_stage_status` low-level stage flags
- `get_stage_status` view-based status lookup
- Status + quality handling inside `process_document_smart_stages`
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = [pytest.mark.master_pipeline, pytest.mark.status_tracking]


class TestGetDocumentStageStatus:
    @pytest.mark.asyncio
    async def test_get_document_stage_status_basic_flags(self, mock_master_pipeline: KRMasterPipeline) -> None:
        """Basic flags should be derived from simple DB adapter queries."""

        pipeline = mock_master_pipeline
        document_id = "doc-stage-1"

        class FakeDB:
            async def get_document(self, doc_id: str) -> Any:  # type: ignore[override]
                assert doc_id == document_id
                return SimpleNamespace(
                    manufacturer="HP",
                    document_type="service_manual",
                )

            async def count_chunks_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 5

            async def count_images_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 0

            async def get_intelligence_chunks_by_document(self, doc_id: str):  # type: ignore[override]
                return []

            async def count_links_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 0

            pg_pool = None

        pipeline.database_service = FakeDB()  # type: ignore[assignment]

        status = await pipeline.get_document_stage_status(document_id)

        assert status["upload"] is True
        assert status["classification"] is True
        assert status["text"] is True
        # No chunks in intelligence table yet
        assert status["chunk_prep"] is False
        # No images / links / embeddings
        assert status["image"] is False
        assert status["links"] is False
        assert status["embedding"] is False
        assert status["storage"] is False
        # Stages that depend on pg_pool stay False
        assert status["svg"] is False
        assert status["metadata"] is False

    @pytest.mark.asyncio
    async def test_get_document_stage_status_with_embeddings_and_images(
        self, mock_master_pipeline: KRMasterPipeline
    ) -> None:
        """When DB has data, flags for images, chunks and embeddings should flip."""

        pipeline = mock_master_pipeline
        document_id = "doc-stage-2"

        class FakeDB:
            async def get_document(self, doc_id: str) -> Any:  # type: ignore[override]
                return SimpleNamespace(
                    manufacturer=None,
                    document_type="unknown",
                )

            async def count_chunks_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 3

            async def count_images_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 2

            async def get_intelligence_chunks_by_document(self, doc_id: str):  # type: ignore[override]
                return [
                    {"id": 1},
                ]

            async def count_links_by_document(self, doc_id: str) -> int:  # type: ignore[override]
                return 4

            async def check_embeddings_exist(self, doc_id: str) -> bool:  # type: ignore[override]
                return True

            pg_pool = None

        pipeline.database_service = FakeDB()  # type: ignore[assignment]

        status = await pipeline.get_document_stage_status(document_id)

        assert status["upload"] is True
        # classification should remain False (no manufacturer / unknown type)
        assert status["classification"] is False
        assert status["text"] is True
        assert status["image"] is True
        assert status["chunk_prep"] is True
        assert status["links"] is True
        assert status["embedding"] is True
        # storage is inferred from image stage
        assert status["storage"] is True
        # pg_pool-dependent stages still False here
        assert status["svg"] is False
        assert status["metadata"] is False


class TestGetStageStatus:
    @pytest.mark.asyncio
    async def test_get_stage_status_found_document(
        self,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`get_stage_status` should unwrap view result when document exists."""

        pipeline = mock_master_pipeline

        async def fake_execute_query(query: str, params) -> Any:  # type: ignore[override]
            assert "vw_documents" in query
            assert params == ["doc-123"]
            return [
                {
                    "stage_status": {"upload": True, "text": False},
                }
            ]

        monkeypatch.setattr(
            pipeline.database_service,
            "execute_query",
            fake_execute_query,
            raising=False,
        )

        result = await pipeline.get_stage_status("doc-123")

        assert result["document_id"] == "doc-123"
        assert result["found"] is True
        assert result["stage_status"] == {"upload": True, "text": False}
        assert "error" not in result


class TestSmartProcessingStatusAndQuality:
    @pytest.mark.asyncio
    async def test_smart_stages_marks_document_failed_when_all_stages_fail(
        self,
        tmp_path: Path,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If every attempted stage fails, document status should be set to `failed`.

        Also validates propagation of quality score and pass/fail flag from the
        quality service into the result dict.
        """

        pipeline = mock_master_pipeline
        document_id = "doc-status-fail"
        pdf_path = tmp_path / "status_manual.pdf"
        pdf_path.write_text("x")
        filename = pdf_path.name

        async def fake_stage_status(doc_id: str) -> dict[str, bool]:  # type: ignore[override]
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

        monkeypatch.setattr(pipeline, "get_document_stage_status", fake_stage_status)

        class FailingProcessor:
            def __init__(self, name: str) -> None:
                self.name = name

            async def process(self, context):  # type: ignore[override]
                raise RuntimeError(f"{self.name} failed")

        pipeline.processors.update(
            {
                "text": FailingProcessor("text"),
                "image": FailingProcessor("image"),
                "classification": FailingProcessor("classification"),
                "chunk_prep": FailingProcessor("chunk_prep"),
                "links": FailingProcessor("links"),
                "metadata": FailingProcessor("metadata"),
                "storage": FailingProcessor("storage"),
                "embedding": FailingProcessor("embedding"),
                "search": FailingProcessor("search"),
            }
        )

        # Ensure SVG stage is skipped via feature flag
        monkeypatch.setenv("ENABLE_SVG_EXTRACTION", "false")

        async def fake_get_document(doc_id: str) -> Any:  # type: ignore[override]
            return SimpleNamespace(file_hash="hash-xyz", document_type="service_manual")

        monkeypatch.setattr(
            pipeline.database_service,
            "get_document",
            fake_get_document,
            raising=False,
        )

        async def fake_update_status(doc_id: str, status: str) -> None:  # type: ignore[override]
            pipeline._last_status = (doc_id, status)

        monkeypatch.setattr(
            pipeline.database_service,
            "update_document_status",
            fake_update_status,
            raising=False,
        )

        async def fake_quality(doc_id: str) -> dict[str, Any]:  # type: ignore[override]
            return {
                "passed": False,
                "score": 10,
                "issues": ["too few chunks"],
                "warnings": [],
            }

        pipeline.quality_service.check_document_quality = fake_quality  # type: ignore[assignment]

        result = await pipeline.process_document_smart_stages(
            document_id,
            filename,
            str(pdf_path),
        )

        assert result["success"] is False
        assert result["filename"] == filename
        assert result.get("quality_score") == 10
        assert result.get("quality_passed") is False
        assert "completed_stages" in result and not result["completed_stages"]
        # At least some stages should be reported as failed
        assert "text" in result.get("failed_stages", [])
        assert "embedding" in result.get("failed_stages", [])
        # Document status should be updated to failed
        assert getattr(pipeline, "_last_status", None) == (document_id, "failed")


class TestPipelineStatusHelpers:
    @pytest.mark.asyncio
    async def test_get_pipeline_status_returns_counts(
        self,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pipeline = mock_master_pipeline

        documents = [
            {"id": "doc-1", "manufacturer": "HP", "filename": "a.pdf", "created_at": "2024-01-02T00:00:00"},
            {"id": "doc-2", "manufacturer": None, "filename": "b.pdf", "created_at": "2024-01-01T00:00:00"},
        ]
        chunks = [{"document_id": "doc-1"}]
        images = []

        async def fake_execute_query(query: str, params: list[Any] | None = None):  # type: ignore[override]
            q = query.lower()
            if "krai_core.documents" in q:
                return documents
            if "krai_intelligence.chunks" in q:
                return chunks
            if "krai_content.images" in q:
                return images
            return []

        monkeypatch.setattr(pipeline.database_service, "execute_query", fake_execute_query, raising=False)

        status = await pipeline._get_pipeline_status()

        assert status["total_docs"] == 2
        assert status["classified_docs"] == 1
        assert status["pending_docs"] == 1
        assert status["total_chunks"] == 1
        assert status["total_images"] == 0
        assert status["overall_progress"] >= 0
        assert status["current_stage"] is not None


class TestMonitorHardware:
    @pytest.mark.asyncio
    async def test_monitor_hardware_runs_single_iteration(
        self,
        mock_master_pipeline: KRMasterPipeline,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pipeline = mock_master_pipeline
        pipeline.interactive_console = False

        pipeline._get_pipeline_status = AsyncMock(
            return_value={
                "total_docs": 1,
                "classified_docs": 1,
                "pending_docs": 0,
                "total_chunks": 10,
                "total_images": 2,
                "overall_progress": 75.0,
                "current_stage": "Classification Complete - sample.pdf",
                "recent_activity": [],
            }
        )
        pipeline._get_error_count = AsyncMock(return_value=0)
        pipeline._print_detailed_pipeline_view = AsyncMock()
        pipeline._get_gpu_status = lambda: None  # type: ignore[assignment]

        sleep_calls: list[float] = []

        async def fake_sleep(interval: float) -> None:
            sleep_calls.append(interval)

        await pipeline.monitor_hardware(
            sleep_interval=0,
            max_iterations=1,
            sleep_func=fake_sleep,
        )

        pipeline._get_pipeline_status.assert_awaited_once()
        pipeline._get_error_count.assert_awaited_once()
        pipeline._print_detailed_pipeline_view.assert_awaited()
        assert sleep_calls == [0]
