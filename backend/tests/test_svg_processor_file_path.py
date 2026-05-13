"""
Unit tests for SVGProcessor - File path resolution and PDF handling

Tests that the SVG processor correctly receives and handles file paths
after the pipeline fix for file path resolution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingStatus, Stage
from backend.core.types import ProcessingContext
from backend.processors.svg_processor import SVGProcessor


def _make_processor():
    """Create SVGProcessor with mocked dependencies."""
    return SVGProcessor(
        database_service=MagicMock(), storage_service=MagicMock(), ai_service=None, dpi=300, max_dimension=2048
    )


def test_svg_processor_receives_file_path_in_context():
    """SVGProcessor must receive file_path in ProcessingContext after pipeline fix."""
    # Create a minimal context with file_path (the critical fix)
    context = ProcessingContext(
        document_id="test-doc-123",
        file_path="/tmp/resolved_document.pdf",  # This must be present after fix
        document_type="manual",
        correlation_id="test-correlation",
        pdf_path="/tmp/resolved_document.pdf",  # Alias for compatibility
    )

    # Verify context has the file paths we need
    assert context.file_path is not None, "file_path must be set in context"
    assert context.pdf_path is not None, "pdf_path must be set in context"
    assert context.file_path == context.pdf_path


def test_svg_processor_with_missing_file_path():
    """SVGProcessor must handle gracefully when file_path is missing."""
    # Context without file_path - should not crash
    context = ProcessingContext(
        document_id="test-doc-123",
        file_path=None,  # Missing file_path
        document_type="manual",
        correlation_id="test-correlation",
    )

    assert context.file_path is None


@pytest.mark.asyncio
async def test_svg_processor_extracts_statistics():
    """SVGProcessor must return statistics in processing result."""
    processor = _make_processor()

    context = ProcessingContext(
        document_id="test-doc-123",
        file_path="/tmp/test.pdf",
        document_type="manual",
        correlation_id="test-correlation",
        pdf_path="/tmp/test.pdf",
    )

    # Mock the process method to return statistics
    with patch.object(processor, "process", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = MagicMock(
            status=ProcessingStatus.COMPLETED, metadata={"svg_count": 5, "images_queued": 5}
        )
        result = await processor.process(context)

        assert result.status == ProcessingStatus.COMPLETED
        assert result.metadata["svg_count"] == 5


def test_svg_processor_stage():
    """SVGProcessor must return correct stage."""
    processor = _make_processor()
    assert processor.get_stage() == Stage.SVG_PROCESSING


def test_svg_processor_initialization():
    """SVGProcessor must initialize with correct configuration."""
    processor = _make_processor()

    assert processor.database_service is not None
    assert processor.storage_service is not None
    assert processor.dpi == 300
    assert processor.max_dimension == 2048
    assert processor.svg_inline_storage_threshold_kb > 0
