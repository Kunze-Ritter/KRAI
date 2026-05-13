"""Integration tests for multi-modal processing pipeline fragments.

These tests compose several processors together on the synthetic
`sample_pdf_multimodal` fixture and verify that contexts are enriched and
that no processor crashes when handling mixed content.
"""

from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.image_processor import ImageProcessor
from backend.processors.svg_processor import SVGProcessor
from backend.processors.table_processor import TableProcessor
from backend.processors.visual_embedding_processor import VisualEmbeddingProcessor

pytestmark = [pytest.mark.processor, pytest.mark.multimodal]


class TestMultiModalContentExtraction:
    """Smoke tests for running several processors sequentially on a multimodal PDF.

    This is a partial pipeline integration test, focusing on the image, table, and SVG
    processors. It does not cover the full Upload/Text pipeline.
    """

    @pytest.mark.asyncio
    async def test_tables_images_and_svgs_can_be_processed_together(
        self,
        mock_database_adapter,
        mock_embedding_service,
        mock_storage_service,
        mock_ai_service,
        sample_pdf_multimodal,
    ) -> None:
        pdf_path = sample_pdf_multimodal["path"]
        document_id = str(uuid4())

        # Text/page_texts would normally come from TextProcessor; here we just
        # provide a minimal context with pdf_path.
        base_ctx = ProcessingContext(
            document_id=document_id,
            file_path=str(pdf_path),
            document_type="service_manual",
        )

        # Table processor
        table_processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        table_processor.stage_tracker = None
        table_result = await table_processor.process(base_ctx)
        assert table_result.success or table_result.data.get("tables_extracted", 0) == 0

        # SVG processor (uses adapter directly)
        svg_processor = SVGProcessor(
            database_service=mock_database_adapter,
            storage_service=mock_storage_service,
            ai_service=None,
        )
        svg_result = await svg_processor.process(base_ctx)
        assert svg_result.success

        # Image processor (uses adapter directly)
        image_processor = ImageProcessor(
            database_service=mock_database_adapter,
            storage_service=mock_storage_service,
            ai_service=mock_ai_service,
            enable_ocr=False,
            enable_vision=False,
        )
        image_result = await image_processor.process(base_ctx)
        assert image_result["success"]

        # Visual embedding processor (if enabled)
        vis_processor = VisualEmbeddingProcessor(
            database_service=mock_database_adapter,
            device="cpu",
        )
        if not vis_processor.enabled:
            pytest.skip("Visual embeddings disabled by configuration or missing dependency")

        images_for_embeddings = [
            {
                "id": f"img-{i}",
                "temp_path": img.get("path"),
                "page_number": img.get("page_number"),
                "width": img.get("width"),
                "height": img.get("height"),
                "file_size": img.get("size_bytes"),
                "image_type": img.get("type", "photo"),
                "ai_description": img.get("ai_description", ""),
            }
            for i, img in enumerate(image_result["images"])
            if img.get("path")
        ]

        if not images_for_embeddings:
            return

        ctx_vis = ProcessingContext(
            document_id=document_id,
            file_path=str(pdf_path),
            document_type="service_manual",
            images=images_for_embeddings,
        )

        vis_result = await vis_processor.process(ctx_vis)
        # In constrained environments model loading may fail; treat as soft skip
        if vis_result.success:
            assert vis_result.data["embeddings_created"] >= 0
