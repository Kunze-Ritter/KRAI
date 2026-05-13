from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio, pytest.mark.link]


def _make_context(document_id: str, pdf_path: Path, page_texts: dict[int, str] | None = None) -> ProcessingContext:
    ctx = ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={},
    )
    if page_texts is not None:
        ctx.page_texts = page_texts
    # Manufacturer is used when enriching links
    ctx.manufacturer = "Konica Minolta"
    return ctx


class TestLinkExtractionSuccessPaths:
    async def test_process_pdf_with_links_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_database_adapter,
        sample_pdf_with_links,
    ) -> None:
        # Disable enrichment and use in-memory page_texts from fixture
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        processor = LinkExtractionProcessorAI(database_service=None)

        pdf_info = sample_pdf_with_links
        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com and https://download.example.com/drivers"}
        ctx = _make_context(document_id, pdf_info["path"], page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert result.data["links_found"] >= 1
        assert result.data["videos_found"] >= 0

    async def test_process_pdf_with_youtube_and_direct_videos(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_pdf_with_videos,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        processor = LinkExtractionProcessorAI(database_service=None)

        pdf_info = sample_pdf_with_videos
        document_id = str(uuid4())
        page_texts = {
            1: (
                "YouTube: https://www.youtube.com/watch?v=ABCDEFGHIJK\n"
                "Direct MP4: https://cdn.example.com/training/video.mp4\n"
            )
        }
        ctx = _make_context(document_id, pdf_info["path"], page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert result.data["links_found"] >= 2
        # At least one video (YouTube or direct)
        assert result.data["videos_found"] >= 1

    async def test_process_pdf_with_multipage_links_uses_page_numbers(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_pdf_multipage_links,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        processor = LinkExtractionProcessorAI(database_service=None)

        pdf_info = sample_pdf_multipage_links
        document_id = str(uuid4())
        page_texts = {
            1: "Error 900.01 details at http://errors.example.com/90001.",
            2: "Product C4080 support: http://support.example.com/c4080.",
            3: "General info: http://www.example.com/info.",
        }
        ctx = _make_context(document_id, pdf_info["path"], page_texts)

        captured_links: list[dict[str, Any]] = []

        # Wrap link_extractor to capture links without touching DB helpers
        real_extract = processor.link_extractor.extract_from_document

        def capturing_extract_from_document(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = real_extract(*args, **kwargs)
            captured_links.extend(result.get("links", []))
            return result

        monkeypatch.setattr(
            processor.link_extractor,
            "extract_from_document",
            capturing_extract_from_document,
        )

        result = await processor.process(ctx)

        assert result.success is True
        pages = {l.get("page_number") for l in captured_links}
        # Ensure that we have links for multiple pages
        assert pages == {1, 2, 3}


class TestContextExtractionIntegration:
    async def test_extract_link_contexts_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_pdf_with_links,
        mock_context_extraction_service,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "true")

        processor = LinkExtractionProcessorAI(database_service=None)
        # Swap real ContextExtractionService with mock
        processor.context_service = mock_context_extraction_service

        pdf_info = sample_pdf_with_links
        document_id = uuid4()
        page_texts = {1: "Visit http://support.example.com"}
        ctx = _make_context(str(document_id), pdf_info["path"], page_texts)

        # Prepare simple links list
        links = [
            {
                "id": str(uuid4()),
                "url": "http://support.example.com",
                "page_number": 1,
                "description": "Support",
            }
        ]

        enriched = processor._extract_link_contexts(  # type: ignore[attr-defined]
            links=links,
            page_texts=page_texts,
            adapter=processor.logger,
            document_id=document_id,
        )

        assert len(enriched) == 1
        link = enriched[0]
        assert link["context_description"].startswith("Context for")
        assert link["page_header"].startswith("Header page")
        assert "900.01" in link.get("related_error_codes", []) or link.get("related_error_codes") is None

    async def test_extract_link_contexts_populates_related_chunks_from_db(
        self,
        mock_context_extraction_service,
    ) -> None:
        document_id = uuid4()
        page_number = 2

        chunk_rows = [
            {"id": "chunk-1"},
            {"id": "chunk-2"},
        ]

        class FakeResult:
            def __init__(self, data: list[dict[str, Any]]):
                self.data = data

        class FakeQuery:
            def __init__(self, rows: list[dict[str, Any]]):
                self._rows = rows

            def select(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
                return self

            def eq(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
                return self

            def or_(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
                return self

            def execute(self) -> FakeResult:
                return FakeResult(self._rows)

        class FakeClient:
            def __init__(self, rows: list[dict[str, Any]]):
                self._rows = rows

            def table(self, name: str) -> FakeQuery:
                assert name == "vw_chunks"
                return FakeQuery(self._rows)

        class FakeDatabaseService:
            def __init__(self, rows: list[dict[str, Any]]):
                self.client = FakeClient(rows)

        fake_db = FakeDatabaseService(chunk_rows)
        processor = LinkExtractionProcessorAI(database_service=fake_db)
        processor.context_service = mock_context_extraction_service  # type: ignore[assignment]

        page_texts = {page_number: "Visit http://support.example.com"}
        links = [
            {
                "id": str(uuid4()),
                "url": "http://support.example.com",
                "page_number": page_number,
                "description": "Support",
            }
        ]

        class StubAdapter:
            def warning(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def info(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def error(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def debug(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        adapter = StubAdapter()

        enriched = processor._extract_link_contexts(  # type: ignore[attr-defined]
            links=links,
            page_texts=page_texts,
            adapter=adapter,
            document_id=document_id,
        )

        assert len(enriched) == 1
        assert enriched[0].get("related_chunks") == ["chunk-1", "chunk-2"]


class TestErrorHandling:
    async def test_process_missing_document_id_raises(self, tmp_path: Path) -> None:
        processor = LinkExtractionProcessorAI(database_service=None)
        ctx = ProcessingContext(
            document_id=None,
            file_path=str(tmp_path / "missing.pdf"),
            document_type="service_manual",
            metadata={},
        )

        with pytest.raises(ValueError):
            await processor.process(ctx)

    async def test_process_file_not_found_returns_failure(self, tmp_path: Path) -> None:
        processor = LinkExtractionProcessorAI(database_service=None)
        bogus = tmp_path / "does_not_exist.pdf"
        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(bogus),
            document_type="service_manual",
            metadata={},
        )

        result = await processor.process(ctx)
        assert result.success is False
        assert "File not found" in result.message

    async def test_process_no_page_texts_returns_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

        processor = LinkExtractionProcessorAI(database_service=None)

        async def fake_load_page_texts(context: Any, file_path: Path, adapter: Any) -> dict[int, str]:
            return {}

        monkeypatch.setattr(processor, "_load_page_texts", fake_load_page_texts)

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(pdf_path),
            document_type="service_manual",
            metadata={},
        )

        result = await processor.process(ctx)
        assert result.success is False
        assert "No page texts" in result.message


class TestDatabasePersistenceHelpers:
    async def test_save_links_to_db_inserts_records(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_database_adapter,
    ) -> None:
        # Build a minimal database-like client
        inserted: list[dict[str, Any]] = []

        class DummyResult:
            def __init__(self, data: list[dict[str, Any]] | None = None):
                self.data = data or []

        class LinksTable:
            def __init__(self) -> None:
                self._existing: dict[str, dict[str, Any]] = {}
                self._op: str | None = None
                self._payload: dict[str, Any] | None = None

            def select(self, *_args: Any) -> "LinksTable":
                self._op = "select"
                return self

            def eq(self, _col: str, _val: Any) -> "LinksTable":
                return self

            def limit(self, _n: int) -> "LinksTable":
                return self

            def execute(self) -> DummyResult:
                if self._op == "select":
                    return DummyResult([])
                if self._op == "insert" and self._payload is not None:
                    row = {"id": str(uuid4()), **self._payload}
                    inserted.append(row)
                    return DummyResult([row])
                return DummyResult([])

            def insert(self, payload: dict[str, Any]) -> "LinksTable":
                self._op = "insert"
                self._payload = payload
                return self

            def update(self, payload: dict[str, Any]) -> "LinksTable":  # pragma: no cover - not used here
                self._op = "update"
                self._payload = payload
                return self

        class DummyClient:
            def table(self, name: str) -> LinksTable:
                assert name == "vw_links"
                return LinksTable()

            def rpc(self, *_args: Any, **_kwargs: Any) -> Any:
                class _R:
                    def execute(self_inner) -> DummyResult:  # pragma: no cover - not critical
                        return DummyResult([])

                return _R()

        mock_database_adapter.client = DummyClient()
        processor = LinkExtractionProcessorAI(database_service=mock_database_adapter)

        links = [
            {
                "url": "http://example.com/support",
                "page_number": 1,
                "description": "Support",
                "link_type": "support",
                "link_category": "support_portal",
                "confidence_score": 0.9,
            }
        ]

        mapping = await processor._save_links_to_db(  # type: ignore[attr-defined]
            links,
            document_id="doc-1",
            adapter=processor.logger,
        )

        assert len(inserted) == 1
        assert mapping["http://example.com/support"] == inserted[0]["id"]

    async def test_save_videos_to_db_no_client_noop(self, mock_database_adapter) -> None:
        processor = LinkExtractionProcessorAI(database_service=mock_database_adapter)

        videos = [
            {
                "youtube_id": "ABCDEFGHIJK",
                "title": "Video",
                "description": "Desc",
                "thumbnail_url": None,
                "duration": None,
            }
        ]

        # Without a client attribute this should be a no-op and not raise
        await processor._save_videos_to_db(  # type: ignore[attr-defined]
            videos,
            link_id_map={},
            adapter=processor.logger,
        )
