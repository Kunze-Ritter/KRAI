from pathlib import Path
from typing import Any

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.chunk_preprocessor import ChunkPreprocessor
from backend.processors.classification_processor import ClassificationProcessor
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.pipeline,
    pytest.mark.link,
    pytest.mark.chunk_prep,
    pytest.mark.classification,
]


def _make_context(document_id: str, pdf_path: Path) -> ProcessingContext:
    return ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={},
    )


class TestLinkChunkClassificationPipeline:
    async def test_full_link_chunk_classification_flow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_database_adapter,
        sample_pdf_with_links,
        sample_chunks_for_preprocessing,
        sample_document_metadata_for_classification,
    ) -> None:
        # Prepare document metadata representing a Canon parts catalog
        canon_meta = None
        for meta in sample_document_metadata_for_classification:
            if "Canon_iR_ADV_C5560_Parts_Guide.pdf" in meta["filename"]:
                canon_meta = meta
                break
        if canon_meta is None:
            canon_meta = sample_document_metadata_for_classification[0]

        document_id = canon_meta["id"]
        mock_database_adapter.documents[document_id] = dict(canon_meta)

        # Seed chunks for this document
        for chunk in sample_chunks_for_preprocessing:
            chunk["document_id"] = document_id
            mock_database_adapter.chunks[chunk["id"]] = dict(chunk)

        # Database-like client used by ChunkPreprocessor and ClassificationProcessor
        class DummyResult:
            def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
                self.data = data or []

        class ChunksTable:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage
                self._doc: str | None = None
                self._update_id: str | None = None
                self._payload: dict[str, Any] | None = None

            def select(self, *_args: Any) -> "ChunksTable":
                return self

            def eq(self, column: str, value: Any) -> "ChunksTable":
                if column == "document_id":
                    self._doc = value
                if column == "id":
                    self._update_id = value
                return self

            def order(self, _col: str) -> "ChunksTable":
                return self

            def update(self, payload: dict[str, Any]) -> "ChunksTable":
                self._payload = payload
                return self

            def execute(self) -> DummyResult:
                if self._payload is not None and self._update_id is not None:
                    if self._update_id in self._storage:
                        self._storage[self._update_id].update(self._payload)
                    return DummyResult([])

                if self._doc is None:
                    return DummyResult([])
                rows = [c for c in self._storage.values() if c.get("document_id") == self._doc]
                rows = sorted(rows, key=lambda r: r.get("chunk_index", 0))
                return DummyResult(rows)

        class CountTable:
            def __init__(self, count: int) -> None:
                self._count = count

            def select(self, *_args: Any) -> "CountTable":
                return self

            def eq(self, *_args: Any, **_kwargs: Any) -> "CountTable":
                return self

            def execute(self) -> DummyResult:
                return DummyResult([{"id": i} for i in range(self._count)])

        class DummyClient:
            def __init__(self, adapter) -> None:
                self._adapter = adapter

            def table(self, name: str) -> Any:
                if name == "chunks":
                    return ChunksTable(self._adapter.chunks)
                if name == "error_codes":
                    return CountTable(0)
                if name == "parts_catalog":
                    return CountTable(10)
                return CountTable(0)

        mock_database_adapter.client = DummyClient(mock_database_adapter)

        # Stage 1: Link extraction (no DB persistence, no enrichment)
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        link_processor = LinkExtractionProcessorAI(database_service=None)

        pdf_info = sample_pdf_with_links
        ctx_link = _make_context(document_id, pdf_info["path"])
        ctx_link.page_texts = {
            1: "Visit http://support.example.com and https://download.example.com/drivers",
        }
        ctx_link.manufacturer = "Canon"

        async def fake_save_links(links: list[dict[str, Any]], doc_id: str, adapter: Any) -> dict[str, str]:
            return {}

        async def fake_save_videos(videos: list[dict[str, Any]], mapping: dict[str, str], adapter: Any) -> None:
            return None

        link_processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        link_processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        link_result = await link_processor.process(ctx_link)

        assert link_result.success is True
        assert link_result.data["links_found"] >= 1

        # Stage 2: Chunk preprocessing
        chunk_processor = ChunkPreprocessor(database_service=mock_database_adapter)
        ctx_chunk = _make_context(document_id, pdf_info["path"])

        chunk_result = await chunk_processor.process(ctx_chunk)

        assert chunk_result.success is True
        assert chunk_result.data["chunks_preprocessed"] > 0
        assert chunk_result.data["total_chunks"] == len(sample_chunks_for_preprocessing)

        # Stage 3: Classification
        classification_processor = ClassificationProcessor(
            database_service=mock_database_adapter,
            ai_service=None,
            features_service=None,
        )

        ctx_cls = _make_context(document_id, pdf_info["path"])

        cls_result = await classification_processor.process(ctx_cls)

        assert cls_result.success is True
        data = cls_result.data
        assert data["manufacturer"] is not None
        assert data["document_type"] in {"parts_catalog", "service_manual", "user_manual"}

        updated = mock_database_adapter.documents[document_id]
        assert updated.get("manufacturer") is not None
        assert updated.get("document_type") is not None
