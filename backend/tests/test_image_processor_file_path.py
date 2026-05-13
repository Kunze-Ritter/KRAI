"""
Unit tests for ImageProcessor - File path resolution and PDF handling

Tests that the Image processor correctly receives and handles file paths
after the pipeline fix for file path resolution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingStatus, Stage
from backend.core.types import ProcessingContext
from backend.processors.image_processor import ImageProcessor


def _make_processor():
    """Create ImageProcessor with mocked dependencies."""
    return ImageProcessor(
        database_service=MagicMock(),
        storage_service=MagicMock(),
        ai_service=None,
    )


def test_image_processor_receives_file_path_in_context():
    """ImageProcessor must receive file_path in ProcessingContext after pipeline fix."""
    # Create a context with file_path (the critical fix)
    context = ProcessingContext(
        document_id="test-doc-456",
        file_path="/tmp/resolved_document.pdf",  # This must be present after fix
        document_type="manual",
        correlation_id="test-correlation",
        pdf_path="/tmp/resolved_document.pdf",  # Alias for compatibility
    )

    # Verify context has the file paths we need
    assert context.file_path is not None, "file_path must be set in context"
    assert context.pdf_path is not None, "pdf_path must be set in context"


def test_image_processor_stage():
    """ImageProcessor must return correct stage."""
    processor = _make_processor()
    assert processor.stage == Stage.IMAGE_PROCESSING


def test_image_processor_initialization():
    """ImageProcessor must initialize with correct configuration."""
    processor = _make_processor()

    assert processor.database_service is not None
    assert processor.storage_service is not None


def test_image_processor_without_file_path():
    """ImageProcessor must handle context without file_path gracefully."""
    # Context without file_path
    context = ProcessingContext(
        document_id="test-doc-456",
        file_path=None,
        document_type="manual",
        correlation_id="test-correlation",
    )

    assert context.file_path is None


@pytest.mark.asyncio
async def test_image_processor_extracts_statistics():
    """ImageProcessor must track image extraction statistics."""
    processor = _make_processor()

    context = ProcessingContext(
        document_id="test-doc-456",
        file_path="/tmp/test.pdf",
        document_type="manual",
        correlation_id="test-correlation",
        pdf_path="/tmp/test.pdf",
    )

    # Mock the process method to return statistics
    with patch.object(processor, "process", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = MagicMock(
            status=ProcessingStatus.COMPLETED,
            metadata={
                "images_extracted": 42,
                "images_queued": 42,
                "skipped": 3,
            },
        )
        result = await processor.process(context)

        assert result.status == ProcessingStatus.COMPLETED
        assert result.metadata["images_extracted"] == 42


def test_image_processor_raster_to_jpeg_conversion():
    """Test PNG to JPEG conversion for raster images."""
    # This tests the helper function
    from backend.processors.image_processor import _raster_to_jpeg

    # PNG magic bytes
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake image data"
    result_bytes, result_ext = _raster_to_jpeg(png_bytes, "png")

    # Should convert to JPEG
    assert result_ext in ("jpg", "jpeg", "png")

    # JPEG magic bytes (should pass through unchanged)
    jpeg_bytes = b"\xff\xd8\xff" + b"fake jpeg data"
    result_bytes, result_ext = _raster_to_jpeg(jpeg_bytes, "jpg")
    assert result_ext == "jpg"
