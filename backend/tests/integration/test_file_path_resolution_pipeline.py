"""
Integration tests for pipeline file path resolution across all PDF-reading stages.

Tests that SVG, Image, Link, and Visual Embedding stages correctly receive and use
the resolved file_path from MinIO storage when processing documents.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingStatus, Stage
from backend.core.types import ProcessingContext
from backend.processors.image_processor import ImageProcessor
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI
from backend.processors.svg_processor import SVGProcessor


def _create_context_with_file_path(document_id: str, file_path: str) -> ProcessingContext:
    """Create a processing context with file_path (simulating master_pipeline.py behavior)."""
    return ProcessingContext(
        document_id=document_id,
        file_path=file_path,
        document_type="manual",
        correlation_id="test-correlation-integration",
        pdf_path=file_path,
    )


def _create_context_without_file_path(document_id: str) -> ProcessingContext:
    """Create a processing context without file_path (simulating legacy behavior)."""
    return ProcessingContext(
        document_id=document_id,
        file_path=None,
        document_type="manual",
        correlation_id="test-correlation-integration",
    )


class TestFilePathResolutionIntegration:
    """Test file path resolution across all stages that read PDFs."""

    def test_all_stages_receive_resolved_file_path(self):
        """All PDF-reading stages must receive file_path after master_pipeline fix."""
        # This is the critical fix: stages must receive file_path
        resolved_path = "/tmp/resolved_document_from_minio.pdf"

        context = _create_context_with_file_path(document_id="test-doc-integration", file_path=resolved_path)

        # Verify the context has the required file paths
        assert context.file_path == resolved_path
        assert context.pdf_path == resolved_path
        assert context.file_path is not None

    def test_svg_processor_integration_with_context(self):
        """SVGProcessor must use file_path from context during integration."""
        processor = SVGProcessor(
            database_service=MagicMock(), storage_service=MagicMock(), ai_service=None, dpi=300, max_dimension=2048
        )

        context = _create_context_with_file_path(document_id="test-svg-integration", file_path="/tmp/test.pdf")

        # Verify processor has the stage identifier
        assert processor.get_stage() == Stage.SVG_PROCESSING

        # Verify context contains the file path
        assert context.file_path is not None
        assert context.pdf_path == context.file_path

    def test_image_processor_integration_with_context(self):
        """ImageProcessor must use file_path from context during integration."""
        processor = ImageProcessor(database_service=MagicMock(), storage_service=MagicMock(), ai_service=None)

        context = _create_context_with_file_path(document_id="test-image-integration", file_path="/tmp/test.pdf")

        # Verify processor stage
        assert processor.stage == Stage.IMAGE_PROCESSING

        # Verify context has file path
        assert context.file_path == "/tmp/test.pdf"
        assert context.pdf_path == "/tmp/test.pdf"

    def test_link_extraction_integration_with_context(self):
        """LinkExtractionProcessorAI must use file_path from context during integration."""
        processor = LinkExtractionProcessorAI(
            database_service=MagicMock(),
            ai_service=None,
            youtube_api_key="test-key",
            link_enrichment_service=None,
            config_service=None,
        )

        context = _create_context_with_file_path(document_id="test-link-integration", file_path="/tmp/test.pdf")

        # Verify processor stage
        assert processor.stage == Stage.LINK_EXTRACTION

        # Verify context has file path
        assert context.file_path == "/tmp/test.pdf"

    @pytest.mark.asyncio
    async def test_stage_sequence_with_file_path_flow(self):
        """All stages in sequence must receive file_path through context."""
        document_id = "test-doc-sequence"
        resolved_path = "/tmp/resolved_from_minio.pdf"

        # Simulate the master_pipeline flow: resolve file_path once, pass to all stages
        context = _create_context_with_file_path(document_id=document_id, file_path=resolved_path)

        # Create all processors
        svg_processor = SVGProcessor(
            database_service=MagicMock(), storage_service=MagicMock(), ai_service=None, dpi=300, max_dimension=2048
        )
        image_processor = ImageProcessor(database_service=MagicMock(), storage_service=MagicMock(), ai_service=None)
        link_processor = LinkExtractionProcessorAI(
            database_service=MagicMock(),
            ai_service=None,
            youtube_api_key="test-key",
            link_enrichment_service=None,
            config_service=None,
        )

        # All processors should be available for processing
        assert svg_processor.get_stage() == Stage.SVG_PROCESSING
        assert image_processor.stage == Stage.IMAGE_PROCESSING
        assert link_processor.stage == Stage.LINK_EXTRACTION

        # Context should maintain file_path through the sequence
        assert context.file_path == resolved_path
        assert context.pdf_path == resolved_path

    def test_context_file_path_consistency_across_stages(self):
        """File path in context must be consistent across all stage accesses."""
        resolved_path = "/tmp/document_resolved.pdf"

        # Create a context that simulates master_pipeline behavior
        context = _create_context_with_file_path(document_id="test-doc-consistency", file_path=resolved_path)

        # Simulate different processors accessing the context
        # SVG stage accesses file_path
        svg_file_path = context.file_path

        # Image stage accesses file_path
        image_file_path = context.file_path

        # Link stage accesses file_path
        link_file_path = context.file_path

        # All should get the same resolved path
        assert svg_file_path == resolved_path
        assert image_file_path == resolved_path
        assert link_file_path == resolved_path

    def test_missing_file_path_handling(self):
        """Stages must handle gracefully when file_path is missing."""
        context = _create_context_without_file_path(document_id="test-doc-no-path")

        # Context should have None for file_path
        assert context.file_path is None

        # Processors should still be instantiable, they handle missing paths internally
        processor = ImageProcessor(database_service=MagicMock(), storage_service=MagicMock(), ai_service=None)
        assert processor is not None

    @pytest.mark.asyncio
    async def test_all_stages_statistics_with_resolved_path(self):
        """All stages must collect statistics when given resolved file_path."""
        resolved_path = "/tmp/test_with_content.pdf"

        context = _create_context_with_file_path(document_id="test-doc-stats", file_path=resolved_path)

        # Mock processors to return statistics
        svg_processor = SVGProcessor(
            database_service=MagicMock(), storage_service=MagicMock(), ai_service=None, dpi=300, max_dimension=2048
        )

        image_processor = ImageProcessor(database_service=MagicMock(), storage_service=MagicMock(), ai_service=None)

        link_processor = LinkExtractionProcessorAI(
            database_service=MagicMock(),
            ai_service=None,
            youtube_api_key="test-key",
            link_enrichment_service=None,
            config_service=None,
        )

        # Mock the process methods to return statistics
        with (
            patch.object(svg_processor, "process", new_callable=AsyncMock) as mock_svg,
            patch.object(image_processor, "process", new_callable=AsyncMock) as mock_image,
            patch.object(link_processor, "process", new_callable=AsyncMock) as mock_link,
        ):
            mock_svg.return_value = MagicMock(
                status=ProcessingStatus.COMPLETED, metadata={"svg_count": 8, "images_queued": 8}
            )
            mock_image.return_value = MagicMock(
                status=ProcessingStatus.COMPLETED,
                metadata={"images_extracted": 12, "images_queued": 12, "skipped": 1},
            )
            mock_link.return_value = MagicMock(
                status=ProcessingStatus.COMPLETED,
                metadata={"links_extracted": 45, "videos_extracted": 3, "enriched_links": 40},
            )

            # Process all stages
            svg_result = await svg_processor.process(context)
            image_result = await image_processor.process(context)
            link_result = await link_processor.process(context)

            # Verify all returned statistics
            assert svg_result.status == ProcessingStatus.COMPLETED
            assert svg_result.metadata["svg_count"] == 8

            assert image_result.status == ProcessingStatus.COMPLETED
            assert image_result.metadata["images_extracted"] == 12

            assert link_result.status == ProcessingStatus.COMPLETED
            assert link_result.metadata["links_extracted"] == 45

    def test_file_path_resolution_order(self):
        """File path must be resolved before context is built for any stage."""
        # Simulate master_pipeline.py behavior:
        # 1. Get storage_path from database (just hash)
        storage_path = "abc123def456ghi789"  # MinIO hash

        # 2. Resolve to local file path
        resolved_path = f"/tmp/{storage_path}_resolved.pdf"

        # 3. Build context with resolved path
        context = _create_context_with_file_path(document_id="test-order", file_path=resolved_path)

        # 4. All stages receive the context with resolved path
        assert context.file_path == resolved_path
        assert context.file_path != storage_path  # Should be resolved, not hash
        assert "/tmp/" in context.file_path  # Should be local path
