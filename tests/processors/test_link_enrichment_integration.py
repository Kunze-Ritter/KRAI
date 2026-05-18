from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.link_enrichment]


def _make_context(document_id: str, file_path: str, page_texts: dict[int, str]) -> ProcessingContext:
    ctx = ProcessingContext(
        document_id=document_id,
        file_path=file_path,
        document_type="service_manual",
        metadata={},
    )
    ctx.page_texts = page_texts
    ctx.manufacturer = "Konica Minolta"
    return ctx


class TestLinkEnrichmentFlow:
    async def test_link_extraction_with_enrichment_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        link_enrichment_service_with_mock_scraper,
    ) -> None:
        # Enable enrichment and structured extraction
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "true")
        monkeypatch.setenv("ENABLE_STRUCTURED_EXTRACTION", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        pdf_path = tmp_path / "links.pdf"
        pdf_path.write_text("Visit http://support.example.com for more information.")

        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com for more information."}

        # Build processor with enrichment service injected but without real DB client
        processor = LinkExtractionProcessorAI(
            database_service=None,
            link_enrichment_service=link_enrichment_service_with_mock_scraper,
        )

        # Stub _save_links_to_db so that links keep their own IDs and we can observe them
        async def fake_save_links(links: list[dict[str, Any]], document_id: str, adapter: Any) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for link in links:
                # Ensure each link has a stable id
                if "id" not in link:
                    link["id"] = str(uuid4())
                mapping[link["url"]] = link["id"]
            return mapping

        async def fake_save_videos(videos: list[dict[str, Any]], mapping: dict[str, str], adapter: Any) -> None:
            return None

        processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        # Patch enrichment service to observe calls
        called: dict[str, Any] = {}

        async def fake_enrich_links_batch(link_ids: list[str], max_concurrent: int = 3) -> dict[str, Any]:
            called["link_ids"] = list(link_ids)
            return {"total": len(link_ids), "enriched": len(link_ids), "failed": 0, "skipped": 0}

        link_enrichment_service_with_mock_scraper.enrich_links_batch = fake_enrich_links_batch  # type: ignore[assignment]

        ctx = _make_context(document_id, str(pdf_path), page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert result.data["links_found"] >= 1
        assert "link_ids" in called
        assert len(called["link_ids"]) == result.data["links_found"]

    async def test_link_extraction_with_enrichment_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        link_enrichment_service_with_mock_scraper,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "false")
        monkeypatch.setenv("ENABLE_STRUCTURED_EXTRACTION", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        pdf_path = tmp_path / "links_disabled.pdf"
        pdf_path.write_text("Visit http://support.example.com for more information.")

        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com for more information."}

        processor = LinkExtractionProcessorAI(
            database_service=None,
            link_enrichment_service=None,
        )

        async def fake_save_links(links: list[dict[str, Any]], document_id: str, adapter: Any) -> dict[str, str]:
            return {link["url"]: link.get("id", str(uuid4())) for link in links}

        async def fake_save_videos(videos: list[dict[str, Any]], mapping: dict[str, str], adapter: Any) -> None:
            return None

        processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        # Wrap enrichment call to ensure it is not invoked
        called = {"count": 0}

        async def fake_enrich_links_batch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:  # pragma: no cover
            called["count"] += 1
            return {"total": 0, "enriched": 0, "failed": 0, "skipped": 0}

        link_enrichment_service_with_mock_scraper.enrich_links_batch = fake_enrich_links_batch  # type: ignore[assignment]

        ctx = _make_context(document_id, str(pdf_path), page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        # Because enable_link_enrichment is false, _enrich_document_links should be a no-op
        assert called["count"] == 0


class TestStructuredExtractionTrigger:
    async def test_structured_extraction_triggered_after_enrichment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        link_enrichment_service_with_mock_scraper,
    ) -> None:
        # Enable both enrichment and structured extraction
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "true")
        monkeypatch.setenv("ENABLE_STRUCTURED_EXTRACTION", "true")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        pdf_path = tmp_path / "links_structured.pdf"
        pdf_path.write_text("Visit http://support.example.com for more information.")

        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com for more information."}

        processor = LinkExtractionProcessorAI(
            database_service=None,
            link_enrichment_service=link_enrichment_service_with_mock_scraper,
        )

        async def fake_save_links(links: list[dict[str, Any]], document_id: str, adapter: Any) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for link in links:
                if "id" not in link:
                    link["id"] = str(uuid4())
                mapping[link["url"]] = link["id"]
            return mapping

        async def fake_save_videos(videos: list[dict[str, Any]], mapping: dict[str, str], adapter: Any) -> None:
            return None

        processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        # Provide a lightweight structured_extraction_service
        called: dict[str, Any] = {}

        class DummyStructuredService:
            async def batch_extract(
                self, source_ids: list[str], source_type: str, max_concurrent: int = 2
            ) -> dict[str, Any]:
                called["source_ids"] = list(source_ids)
                called["source_type"] = source_type
                return {"completed": len(source_ids), "failed": 0, "total": len(source_ids)}

        processor.enable_structured_extraction = True
        processor.structured_extraction_service = DummyStructuredService()  # type: ignore[assignment]

        async def fake_enrich_links_batch(link_ids: list[str], max_concurrent: int = 3) -> dict[str, Any]:
            # All links are considered enriched successfully
            return {"enriched": len(link_ids), "failed": 0, "skipped": 0}

        link_enrichment_service_with_mock_scraper.enrich_links_batch = fake_enrich_links_batch  # type: ignore[assignment]

        ctx = _make_context(document_id, str(pdf_path), page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert "source_ids" in called
        assert called["source_type"] == "link"
        assert len(called["source_ids"]) == result.data["links_found"]


class TestLinkEnrichmentErrorHandling:
    async def test_enrichment_exception_does_not_fail_process(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        link_enrichment_service_with_mock_scraper,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "true")
        monkeypatch.setenv("ENABLE_STRUCTURED_EXTRACTION", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        pdf_path = tmp_path / "links_enrichment_error.pdf"
        pdf_path.write_text("Visit http://support.example.com for more information.")

        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com for more information."}

        processor = LinkExtractionProcessorAI(
            database_service=None,
            link_enrichment_service=link_enrichment_service_with_mock_scraper,
        )

        async def fake_save_links(
            links: list[dict[str, Any]],
            doc_id: str,
            adapter: Any,
        ) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for link in links:
                if "id" not in link:
                    link["id"] = str(uuid4())
                mapping[link["url"]] = link["id"]
            return mapping

        async def fake_save_videos(
            videos: list[dict[str, Any]],
            mapping: dict[str, str],
            adapter: Any,
        ) -> None:
            return None

        processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        async def failing_enrich_links_batch(
            link_ids: list[str],
            max_concurrent: int = 3,
        ) -> dict[str, Any]:
            raise RuntimeError("enrichment failed")

        link_enrichment_service_with_mock_scraper.enrich_links_batch = failing_enrich_links_batch  # type: ignore[assignment]

        error_messages: list[str] = []

        class StubAdapter:
            def info(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def warning(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def debug(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def error(self, msg: Any, *args: Any, **_kwargs: Any) -> None:
                try:
                    message = msg % args if args else msg
                except Exception:
                    message = str(msg)
                error_messages.append(str(message))

        class LoggerContext:
            def __init__(self, adapter: Any) -> None:
                self._adapter = adapter

            def __enter__(self) -> Any:
                return self._adapter

            def __exit__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        stub_adapter = StubAdapter()

        def fake_logger_context(*_args: Any, **_kwargs: Any) -> LoggerContext:
            return LoggerContext(stub_adapter)

        processor.logger_context = fake_logger_context  # type: ignore[assignment]

        ctx = _make_context(document_id, str(pdf_path), page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert any("Link enrichment failed" in message for message in error_messages)

    async def test_structured_extraction_exception_does_not_fail_process(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        link_enrichment_service_with_mock_scraper,
    ) -> None:
        monkeypatch.setenv("ENABLE_LINK_ENRICHMENT", "true")
        monkeypatch.setenv("ENABLE_STRUCTURED_EXTRACTION", "false")
        monkeypatch.setenv("ENABLE_CONTEXT_EXTRACTION", "false")

        pdf_path = tmp_path / "links_structured_error.pdf"
        pdf_path.write_text("Visit http://support.example.com for more information.")

        document_id = str(uuid4())
        page_texts = {1: "Visit http://support.example.com for more information."}

        processor = LinkExtractionProcessorAI(
            database_service=None,
            link_enrichment_service=link_enrichment_service_with_mock_scraper,
        )

        async def fake_save_links(
            links: list[dict[str, Any]],
            doc_id: str,
            adapter: Any,
        ) -> dict[str, str]:
            mapping: dict[str, str] = {}
            for link in links:
                if "id" not in link:
                    link["id"] = str(uuid4())
                mapping[link["url"]] = link["id"]
            return mapping

        async def fake_save_videos(
            videos: list[dict[str, Any]],
            mapping: dict[str, str],
            adapter: Any,
        ) -> None:
            return None

        processor._save_links_to_db = fake_save_links  # type: ignore[assignment]
        processor._save_videos_to_db = fake_save_videos  # type: ignore[assignment]

        class FailingStructuredService:
            async def batch_extract(
                self,
                source_ids: list[str],
                source_type: str,
                max_concurrent: int = 2,
            ) -> dict[str, Any]:
                raise RuntimeError("structured extraction failed")

        processor.enable_structured_extraction = True
        processor.structured_extraction_service = FailingStructuredService()  # type: ignore[assignment]

        async def successful_enrich_links_batch(
            link_ids: list[str],
            max_concurrent: int = 3,
        ) -> dict[str, Any]:
            return {"enriched": len(link_ids), "failed": 0, "skipped": 0}

        link_enrichment_service_with_mock_scraper.enrich_links_batch = successful_enrich_links_batch  # type: ignore[assignment]

        error_messages: list[str] = []

        class StubAdapter:
            def info(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def warning(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def debug(self, *_args: Any, **_kwargs: Any) -> None:
                return None

            def error(self, msg: Any, *args: Any, **_kwargs: Any) -> None:
                try:
                    message = msg % args if args else msg
                except Exception:
                    message = str(msg)
                error_messages.append(str(message))

        class LoggerContext:
            def __init__(self, adapter: Any) -> None:
                self._adapter = adapter

            def __enter__(self) -> Any:
                return self._adapter

            def __exit__(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        stub_adapter = StubAdapter()

        def fake_logger_context(*_args: Any, **_kwargs: Any) -> LoggerContext:
            return LoggerContext(stub_adapter)

        processor.logger_context = fake_logger_context  # type: ignore[assignment]

        ctx = _make_context(document_id, str(pdf_path), page_texts)

        result = await processor.process(ctx)

        assert result.success is True
        assert any("Structured extraction batch failed" in message for message in error_messages)
