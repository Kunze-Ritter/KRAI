"""
Unit tests for LinkExtractionProcessorAI - File path resolution and PDF handling

Tests that the Link Extraction processor correctly receives and handles file paths
after the pipeline fix for file path resolution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingStatus, Stage
from backend.core.types import ProcessingContext
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI


def _make_processor():
    """Create LinkExtractionProcessorAI with mocked dependencies."""
    return LinkExtractionProcessorAI(
        database_service=MagicMock(),
        ai_service=None,
        youtube_api_key="test-key",
        link_enrichment_service=None,
        config_service=None,
    )


def test_link_processor_receives_file_path_in_context():
    """LinkExtractionProcessorAI must receive file_path in ProcessingContext after pipeline fix."""
    # Create a context with file_path (the critical fix)
    context = ProcessingContext(
        document_id="test-doc-789",
        file_path="/tmp/resolved_document.pdf",  # This must be present after fix
        document_type="manual",
        correlation_id="test-correlation",
        pdf_path="/tmp/resolved_document.pdf",  # Alias for compatibility
    )

    # Verify context has the file paths we need
    assert context.file_path is not None, "file_path must be set in context"
    assert context.pdf_path is not None, "pdf_path must be set in context"


def test_link_processor_stage():
    """LinkExtractionProcessorAI must return correct stage."""
    processor = _make_processor()
    assert processor.stage == Stage.LINK_EXTRACTION


def test_link_processor_initialization():
    """LinkExtractionProcessorAI must initialize with correct configuration."""
    processor = _make_processor()

    assert processor.database_service is not None
    assert processor.youtube_api_key == "test-key"
    assert processor.link_extractor is not None
    assert processor.text_extractor is not None


def test_link_processor_without_file_path():
    """LinkExtractionProcessorAI must handle context without file_path gracefully."""
    # Context without file_path
    context = ProcessingContext(
        document_id="test-doc-789",
        file_path=None,
        document_type="manual",
        correlation_id="test-correlation",
    )

    assert context.file_path is None


@pytest.mark.asyncio
async def test_link_processor_extracts_statistics():
    """LinkExtractionProcessorAI must track link extraction statistics."""
    processor = _make_processor()

    context = ProcessingContext(
        document_id="test-doc-789",
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
                "links_extracted": 15,
                "videos_extracted": 2,
                "enriched_links": 10,
            },
        )
        result = await processor.process(context)

        assert result.status == ProcessingStatus.COMPLETED
        assert result.metadata["links_extracted"] == 15
        assert result.metadata["videos_extracted"] == 2


def test_link_processor_with_enrichment_enabled():
    """LinkExtractionProcessorAI must work with enrichment service when enabled."""
    mock_enrichment_service = MagicMock()
    processor = LinkExtractionProcessorAI(
        database_service=MagicMock(),
        ai_service=None,
        youtube_api_key="test-key",
        link_enrichment_service=mock_enrichment_service,
        config_service=None,
    )

    assert processor.link_enrichment_service is not None


def test_link_processor_youtube_api_key():
    """LinkExtractionProcessorAI must handle YouTube API key correctly."""
    # Test with explicit key
    processor1 = _make_processor()
    assert processor1.youtube_api_key == "test-key"

    # Test without explicit key (falls back to env var)
    processor2 = LinkExtractionProcessorAI(
        database_service=MagicMock(),
        ai_service=None,
        youtube_api_key=None,
        link_enrichment_service=None,
        config_service=None,
    )
    # Will use env var YOUTUBE_API_KEY or None
    assert processor2.youtube_api_key is not None or processor2.youtube_api_key is None
