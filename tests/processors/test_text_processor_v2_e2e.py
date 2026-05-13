"""
E2E tests for OptimizedTextProcessor (v2 API)

These tests are aligned with the current OptimizedTextProcessor implementation,
which uses:
- database_service / config_service
- TextExtractor.extract_text(pdf_path, document_id)
- SmartChunker.chunk_document(page_texts, document_id)

The processor returns a BaseProcessor.ProcessingResult with a summary in
result.data (pages_processed, chunks_created, chunks_saved, total_characters,
page_texts_attached, metadata).
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.text_processor_optimized import OptimizedTextProcessor

pytestmark = pytest.mark.processor


class DummyConfigService:
    """Simple config service stub that provides chunk settings for tests."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self._settings = {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

    def get_chunk_settings(self) -> dict[str, Any]:
        return dict(self._settings)


class DummyMetadata:
    """Minimal metadata stub with only the attributes used in tests."""

    def __init__(self, page_count: int = 1):
        self.page_count = page_count


def make_context(file_path: Path) -> ProcessingContext:
    """Create a minimal ProcessingContext compatible with OptimizedTextProcessor."""
    return ProcessingContext(
        document_id=str(uuid4()),
        file_path=str(file_path),
        file_hash="test-hash",
        document_type="service_manual",
        language="en",
    )


class TestOptimizedTextProcessorV2Basic:
    """Basic positive and negative flows for OptimizedTextProcessor v2."""

    @pytest.mark.asyncio
    async def test_basic_extraction_and_chunking_no_db(self, sample_pdf_files):
        """Text is extracted and chunked; summary stats are returned."""
        # Arrange
        valid_pdf_info = sample_pdf_files["valid_pdf"]
        processor = OptimizedTextProcessor(
            database_service=None,
            config_service=DummyConfigService(chunk_size=500, chunk_overlap=100),
        )

        context = make_context(valid_pdf_info["path"])

        # The current OptimizedTextProcessor expects TextExtractor.extract_text
        # to return (page_texts, metadata) even though the real extractor
        # returns three values. For this high-level E2E test we stub the
        # extractor to focus on processor + chunker orchestration instead of
        # low-level PDF I/O.
        def fake_extract_text(file_path, document_id):  # type: ignore[override]
            page_texts = {1: "This is some test content for chunking. " * 5}
            metadata = DummyMetadata(page_count=1)
            structured_texts = {}
            return page_texts, metadata, structured_texts

        processor.text_extractor.extract_text = fake_extract_text  # type: ignore[assignment]

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success is True
        assert isinstance(result.data, dict)

        data = result.data
        assert data.get("pages_processed", 0) >= 1
        assert data.get("chunks_created", 0) >= 1
        # With no database_service, chunks_saved should be 0
        assert data.get("chunks_saved", 0) == 0
        assert data.get("total_characters", 0) > 0
        assert data.get("page_texts_attached") is True

        # Metadata should be a DocumentMetadata-like object
        metadata = data.get("metadata")
        assert metadata is not None
        # page_count should be at least 1 for a valid PDF
        assert getattr(metadata, "page_count", 0) >= 1

        # The processor should attach page_texts to the context
        assert getattr(context, "page_texts", None) is not None
        assert len(context.page_texts) >= 1

    @pytest.mark.asyncio
    async def test_file_not_found_returns_error(self, tmp_path):
        """Non-existent file should produce a failed ProcessingResult with error."""
        # Arrange
        missing_file = tmp_path / "missing.pdf"
        processor = OptimizedTextProcessor(
            database_service=None,
            config_service=None,
        )

        context = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(missing_file),
            file_hash="test-hash",
            document_type="service_manual",
            language="en",
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success is False
        assert result.error is not None
        # The error message should mention that the file was not found
        assert "File not found" in result.error.message
