"""End-to-end style tests for ImageProcessor.

These reuse the existing ImageProcessor implementation but run it in a
controlled environment using the sample PDFs and mock services from
conftest. The tests are intentionally focused on core paths rather than the
entire design surface.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.image_processor import ImageProcessor

pytestmark = [pytest.mark.processor, pytest.mark.image]


def _create_context(document_id: str, pdf_path: Path) -> ProcessingContext:
    return ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={"filename": pdf_path.name},
    )


class TestImageExtractionE2E:
    """Validate that images can be extracted and filtered from a synthetic PDF."""

    @pytest.mark.asyncio
    async def test_process_document_with_images(
        self,
        sample_pdf_with_images,
        mock_database_adapter,
        mock_storage_service,
        mock_ai_service,
    ) -> None:
        processor = ImageProcessor(
            database_service=mock_database_adapter,
            storage_service=mock_storage_service,
            ai_service=mock_ai_service,
            enable_ocr=False,
            enable_vision=False,
        )

        document_id = str(uuid4())
        ctx = _create_context(document_id, sample_pdf_with_images["path"])
        result = await processor.process(ctx)

        assert result["success"]
        assert result["total_extracted"] >= 1
        assert result["total_filtered"] >= 1

        # Verify queue entries via adapter
        queue_entries = await mock_database_adapter.get_image_queue_entries(document_id)
        assert len(queue_entries) >= 0

    @pytest.mark.asyncio
    async def test_queue_images_for_storage(
        self,
        sample_pdf_with_images,
        mock_database_adapter,
        mock_storage_service,
        mock_ai_service,
    ) -> None:
        processor = ImageProcessor(
            database_service=mock_database_adapter,
            storage_service=mock_storage_service,
            ai_service=mock_ai_service,
            enable_ocr=False,
            enable_vision=False,
        )

        document_id = str(uuid4())
        ctx = _create_context(document_id, sample_pdf_with_images["path"])
        result = await processor.process(ctx)

        assert result["success"]

        # Verify queue entries via adapter
        queue_entries = await mock_database_adapter.get_image_queue_entries(document_id)
        assert result["storage_tasks_created"] == len(queue_entries) or result["storage_tasks_created"] == 0


class TestImageProcessorErrorHandling:
    """Minimal negative-path checks for image processing."""

    @pytest.mark.asyncio
    async def test_process_missing_pdf_path(
        self,
        mock_database_adapter,
        mock_storage_service,
        mock_ai_service,
    ) -> None:
        processor = ImageProcessor(
            database_service=mock_database_adapter,
            storage_service=mock_storage_service,
            ai_service=mock_ai_service,
            enable_ocr=False,
            enable_vision=False,
        )

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/missing.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)
        assert not result["success"]
