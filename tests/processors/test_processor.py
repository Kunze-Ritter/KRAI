"""
Test script for Processor V2

This module provides unit tests for DocumentProcessor functionality.
Integrates with conftest.py fixtures for consistent testing infrastructure.

DEPRECATED CLI: The legacy CLI interface (main function) is deprecated.
Use pytest to run the modern async tests instead:
    pytest tests/processors/test_processor.py -v

The CLI interface below references old APIs and will be removed in a future version.
"""

import argparse
import json
import sys
from pathlib import Path

import pytest

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.base_processor import ProcessingContext, ProcessingResult
from backend.processors.document_processor import DocumentProcessor
from backend.processors.logger import get_logger

pytestmark = [
    pytest.mark.processor,
    pytest.mark.skip(
        reason="Legacy DocumentProcessor unit tests are disabled because DocumentProcessor is deprecated and replaced by the pipeline.",
    ),
]


class TestDocumentProcessorBasic:
    """Basic unit tests for DocumentProcessor functionality."""

    @pytest.mark.asyncio
    async def test_document_processor_initialization(self, mock_database_adapter, processor_test_config):
        """Test DocumentProcessor initialization with mock database."""
        # Arrange & Act
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Assert
        assert processor is not None, "Processor should be initialized"
        assert processor.pdf_engine == processor_test_config["pdf_engine"]
        assert processor.database_adapter == mock_database_adapter

    @pytest.mark.asyncio
    async def test_basic_document_processing(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test basic document processing functionality."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert isinstance(result, ProcessingResult), "Should return ProcessingResult"
        assert result.success, f"Valid PDF should process successfully: {result.error}"
        assert result.data is not None, "Should have result data"
        assert "page_texts" in result.data, "Should have page texts"
        assert "metadata" in result.data, "Should have document metadata"

    @pytest.mark.asyncio
    async def test_text_extraction(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test text extraction from documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create test content
        test_content = """Test Document for Text Extraction
====================================

This document tests text extraction functionality.
It contains multiple lines and paragraphs.

Technical Specifications:
- Engine: PyMuPDF
- Purpose: Text extraction testing
- Expected: Successful extraction

This content should be extracted and preserved."""

        test_file = temp_test_pdf / "text_extraction_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Text extraction should succeed"

        page_texts = result.data["page_texts"]
        assert isinstance(page_texts, dict), "Page texts should be a dictionary"
        assert len(page_texts) > 0, "Should extract text from at least one page"

        # Verify content extraction
        all_text = " ".join(page_texts.values())
        assert "Test Document for Text Extraction" in all_text, "Should extract title"
        assert "Technical Specifications" in all_text, "Should extract section headers"
        assert "PyMuPDF" in all_text, "Should preserve engine name"

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test metadata extraction from documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create content with detectable metadata
        metadata_content = """Konica Minolta C750i Service Manual
=====================================

Document Information:
- Manufacturer: Konica Minolta
- Model: C750i
- Document Type: Service Manual
- Language: English

Technical Details:
This document contains technical information.
It should be processed and metadata extracted."""

        test_file = temp_test_pdf / "metadata_extraction_test.pdf"
        test_file.write_text(metadata_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Metadata extraction should succeed"

        document_metadata = result.data["metadata"]
        assert isinstance(document_metadata, dict), "Metadata should be a dictionary"

        # Verify metadata extraction
        assert "manufacturer" in document_metadata, "Should detect manufacturer"
        assert "model" in document_metadata, "Should detect model"
        assert "document_type" in document_metadata, "Should detect document type"
        assert "language" in document_metadata, "Should detect language"

        # Verify specific values
        manufacturer = document_metadata.get("manufacturer", "").lower()
        assert (
            "konica" in manufacturer or "minolta" in manufacturer
        ), f"Should detect Konica Minolta, got {manufacturer}"

        doc_type = document_metadata.get("document_type", "").lower()
        assert "service_manual" in doc_type or "manual" in doc_type, f"Should detect service manual, got {doc_type}"

    @pytest.mark.asyncio
    async def test_language_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test language detection functionality."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create English content
        english_content = """English Language Test Document
==================================

This document is written in English.
It contains technical information and specifications.
The language detection should identify this as English.

Error Code 900.01: Fuser Unit Error
Description: The fuser unit has failed to reach operating temperature.
Solution: Check the fuser lamp and thermal fuse."""

        test_file = temp_test_pdf / "language_detection_test.pdf"
        test_file.write_text(english_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Language detection should succeed"

        document_metadata = result.data["metadata"]
        detected_language = document_metadata.get("language")
        assert detected_language is not None, "Should detect language"
        assert detected_language.lower() in [
            "en",
            "english",
            "en-us",
        ], f"Should detect English, got {detected_language}"

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test error handling in document processing."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create corrupted file
        corrupted_file = temp_test_pdf / "corrupted_test.pdf"
        corrupted_file.write_bytes(b"This is not a valid PDF file content")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=corrupted_file, metadata={"filename": corrupted_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        # Should handle corrupted files gracefully
        if not result.success:
            assert (
                "pdf" in result.error.lower()
                or "corrupted" in result.error.lower()
                or "invalid" in result.error.lower()
            ), "Should provide meaningful error message"

    @pytest.mark.asyncio
    async def test_empty_document_handling(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of empty documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create empty file
        empty_file = temp_test_pdf / "empty_test.pdf"
        empty_file.write_bytes(b"")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=empty_file, metadata={"filename": empty_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        # Should handle empty files gracefully
        if result.success:
            page_texts = result.data["page_texts"]
            assert len(page_texts) == 0, "Empty document should have no pages"
        else:
            assert (
                "empty" in result.error.lower() or "content" in result.error.lower()
            ), "Should provide meaningful error for empty document"

    @pytest.mark.asyncio
    async def test_multi_page_document(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing of multi-page documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create multi-page content
        multi_page_content = """Page 1: Introduction
==================

This is the first page of a multi-page test document.
It contains introductory information and context.

Page 2: Technical Details
=========================

This is the second page with technical specifications.
It includes detailed technical information and parameters.

Page 3: Error Codes
==================

This is the third page containing error codes.
900.01: Fuser unit error
900.02: Exposure lamp error
900.03: High voltage error

Page 4: Troubleshooting
=====================

This is the fourth page with troubleshooting procedures.
It provides step-by-step instructions."""

        test_file = temp_test_pdf / "multi_page_test.pdf"
        test_file.write_text(multi_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Multi-page processing should succeed"

        page_texts = result.data["page_texts"]
        assert len(page_texts) >= 1, "Should extract text from pages"

        # Verify page-specific content
        all_text = " ".join(page_texts.values())
        assert "Page 1" in all_text, "Should extract page 1 content"
        assert "Page 2" in all_text, "Should extract page 2 content"
        assert "Page 3" in all_text, "Should extract page 3 content"
        assert "Page 4" in all_text, "Should extract page 4 content"
        assert "900.01" in all_text, "Should preserve error codes"


# DEPRECATED: Legacy CLI interface - DO NOT USE
# This legacy CLI is deprecated. Use pytest to run modern async tests instead:
#   pytest tests/processors/test_processor.py -v
def main():
    """DEPRECATED: Legacy CLI interface - use pytest instead.

    This CLI is deprecated and references old APIs.
    Use pytest to run modern async tests:
        pytest tests/processors/test_processor.py -v
    """
    print("=" * 70)
    print("DEPRECATED: This CLI interface is deprecated.")
    print("=" * 70)
    print()
    print("To run document processor tests, use pytest:")
    print("  pytest tests/processors/test_processor.py -v")
    print()
    print("Or run all processor tests:")
    print("  pytest tests/processors/ -v")
    print()
    print("=" * 70)
    sys.exit(1)

    # Legacy code below is kept for reference only
    parser = argparse.ArgumentParser(description="DEPRECATED: Test Document Processor V2 (use pytest instead)")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file path (optional)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging for product extraction")
    parser.add_argument(
        "--manufacturer",
        type=str,
        default="AUTO",
        help="Manufacturer name (HP, KONICA MINOLTA, RICOH, etc.) or AUTO for auto-detection",
    )
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size (default: 1000)")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")

    args = parser.parse_args()

    # Check PDF exists
    if not args.pdf_path.exists():
        print(f"❌ PDF not found: {args.pdf_path}")
        sys.exit(1)

    # Get logger
    logger = get_logger()

    # Initialize processor
    logger.section("Processor V2 Test (Legacy)")
    logger.info(f"PDF: {args.pdf_path}")
    logger.info(f"Manufacturer: {args.manufacturer}")

    # Create mock database adapter for legacy testing
    class MockDatabaseAdapter:
        def __init__(self):
            self.documents = {}
            self.chunks = {}

        async def create_document(self, document):
            doc_id = f"doc-{len(self.documents)}"
            self.documents[doc_id] = document
            return doc_id

        async def get_document_by_hash(self, file_hash):
            return None  # No duplicates for testing

        async def create_chunk(self, chunk):
            chunk_id = f"chunk-{len(self.chunks)}"
            self.chunks[chunk_id] = chunk
            return chunk_id

        async def execute_rpc(self, rpc_name, params):
            return True  # Mock successful RPC calls

    mock_db = MockDatabaseAdapter()

    processor = DocumentProcessor(
        database_adapter=mock_db, manufacturer=args.manufacturer, chunk_size=args.chunk_size, debug=args.debug
    )

    # Create processing context
    context = ProcessingContext(
        document_id="legacy-test-doc", file_path=args.pdf_path, metadata={"filename": args.pdf_path.name}
    )

    # Process
    result = processor.process_document(args.pdf_path)

    # Display results
    logger.section("Results")

    if result.success:
        # Summary
        summary_data = {
            "Document": args.pdf_path.name,
            "Pages": result.metadata.page_count,
            "Chunks": len(result.chunks),
            "Products": len(result.products),
            "Error Codes": len(result.error_codes),
            "Validation Errors": len(result.validation_errors),
        }
        logger.table(summary_data, title="📊 Processing Summary")

        # Products
        if result.products:
            logger.panel(
                "\n".join(
                    [
                        f"• {p.model_number} ({p.product_type}) - Confidence: {p.confidence:.2f}"
                        for p in result.products[:10]
                    ]
                ),
                title="📦 Products Extracted",
                style="green",
            )

        # Error Codes
        if result.error_codes:
            logger.panel(
                "\n".join(
                    [
                        f"• {e.error_code}: {e.error_description[:60]}... - Confidence: {e.confidence:.2f}"
                        for e in result.error_codes[:10]
                    ]
                ),
                title="🔴 Error Codes Extracted",
                style="yellow",
            )

        # Validation Errors
        if result.validation_errors:
            logger.warning(f"Found {len(result.validation_errors)} validation errors:")
            for error in result.validation_errors[:5]:
                logger.warning(f"  {error}")

        # Statistics
        logger.table(result.statistics, title="📈 Statistics")

        # Save to file
        if args.output:
            # Convert to Path and make absolute if relative
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = Path.cwd() / output_path
            logger.info(f"Saving results to: {output_path}")
            save_results(result, output_path)
            logger.success(f"Results saved to: {output_path}")

    else:
        logger.error("Processing failed!")
        for error in result.validation_errors:
            logger.error(f"  {error}")

    logger.section("Test Complete")


def save_results(result, output_path: Path):
    """Save results to JSON file"""

    # Convert to dict
    data = {
        "document_id": str(result.document_id),
        "success": result.success,
        "metadata": {
            "title": result.metadata.title,
            "page_count": result.metadata.page_count,
            "document_type": result.metadata.document_type,
        },
        "chunks": [
            {
                "chunk_id": str(c.chunk_id),
                "chunk_index": c.chunk_index,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "text_preview": c.text[:200],
                "chunk_type": c.chunk_type,
            }
            for c in result.chunks[:50]  # First 50
        ],
        "products": [
            {
                "model_number": p.model_number,
                "display_name": p.display_name,  # Computed from series + model_number
                "product_series": p.product_series,
                "product_type": p.product_type,
                "manufacturer_name": p.manufacturer_name,
                "confidence": p.confidence,
                "source_page": p.source_page,
                "extraction_method": p.extraction_method,
                # Specifications (JSONB - flexible)
                "specifications": p.specifications if p.specifications else None,
            }
            for p in result.products
        ],
        "error_codes": [
            {
                "error_code": e.error_code,
                "description": e.error_description,
                "solution": e.solution_text,
                "confidence": e.confidence,
                "page_number": e.page_number,
                "severity": e.severity_level,
            }
            for e in result.error_codes
        ],
        "statistics": result.statistics,
        "processing_time": result.processing_time_seconds,
    }

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Run legacy CLI interface
    main()
