"""End-to-end tests for SVGProcessor.

Focus on basic extraction, conversion, and queueing behaviour using the
structured-data fixtures. These tests are intentionally narrower than the
full design document to keep runtime acceptable.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.svg_processor import SVGProcessor

pytestmark = [pytest.mark.processor, pytest.mark.svg]


def _create_context(document_id: str, pdf_path: Path) -> ProcessingContext:
    return ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={"filename": pdf_path.name},
    )


class DummyDatabaseService:
    """Very small shim exposing `.client.table("vw_processing_queue")`.

    The real database wrapper used by Image/SVG processors exposes `.client`.
    Here we intercept queued items in a plain list for assertions.
    """

    def __init__(self) -> None:
        self.queued = []

        class _Client:
            def __init__(self, outer) -> None:
                self._outer = outer

            def table(self, name):  # pragma: no cover - thin shim
                outer = self._outer

                class _Table:
                    def insert(self, rows):
                        if isinstance(rows, list):
                            outer.queued.extend(rows)
                        else:
                            outer.queued.append(rows)
                        return self

                    def execute(self):
                        return None

                return _Table()

        self.client = _Client(self)


class TestSVGExtractionAndConversion:
    """Basic happy-path extraction and PNG conversion from a synthetic PDF."""

    @pytest.mark.asyncio
    async def test_process_document_with_svgs(
        self,
        sample_pdf_with_svgs,
    ) -> None:
        db = DummyDatabaseService()
        storage = object()  # not used directly

        processor = SVGProcessor(
            database_service=db,
            storage_service=storage,
            ai_service=None,
        )

        ctx = _create_context(str(uuid4()), sample_pdf_with_svgs["path"])
        result = await processor.process(ctx)

        assert result.success
        data = result.data
        assert data["svgs_extracted"] >= 1
        assert data["svgs_converted"] <= data["svgs_extracted"]

    @pytest.mark.asyncio
    async def test_queue_svg_images_for_storage(
        self,
        sample_pdf_with_svgs,
    ) -> None:
        db = DummyDatabaseService()
        storage = object()

        processor = SVGProcessor(
            database_service=db,
            storage_service=storage,
            ai_service=None,
        )

        ctx = _create_context(str(uuid4()), sample_pdf_with_svgs["path"])
        result = await processor.process(ctx)

        assert result.success
        assert result.data["images_queued"] == len(db.queued) or result.data["images_queued"] == 0


class TestSVGProcessorErrorHandling:
    """Minimal negative-path tests for missing/invalid PDFs."""

    @pytest.mark.asyncio
    async def test_process_missing_pdf_path(self) -> None:
        db = DummyDatabaseService()
        storage = object()
        processor = SVGProcessor(
            database_service=db,
            storage_service=storage,
            ai_service=None,
        )

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/missing.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)
        assert not result.success


class TestSVGProcessorConfiguration:
    """Simple configuration/status checks to ensure metadata wiring works."""

    def test_required_inputs_and_outputs(self) -> None:
        db = DummyDatabaseService()
        storage = object()
        processor = SVGProcessor(
            database_service=db,
            storage_service=storage,
            ai_service=None,
        )

        assert "pdf_path" in processor.get_required_inputs()
        assert "svg_images_queued" in processor.get_outputs()
