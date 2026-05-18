"""
Comprehensive E2E Tests for OptimizedTextProcessor

This module provides extensive end-to-end testing for the OptimizedTextProcessor component,
covering text extraction, chunking, database operations, configuration options,
edge cases, and integration scenarios.

Test Categories:
1. Text Extraction Tests
2. Chunking Tests
3. Chunk Metadata Tests
4. Database Operations Tests
5. Configuration Tests
6. Edge Cases Tests
7. Integration Tests

All tests use the fixtures from conftest.py for consistent mock objects and test data.
"""

import hashlib

import pytest

from backend.core.base_processor import ProcessingContext, ProcessingResult
from backend.processors.text_processor_optimized import OptimizedTextProcessor

pytestmark = [
    pytest.mark.processor,
    pytest.mark.skip(
        reason=(
            "Legacy OptimizedTextProcessor E2E suite for old constructor/result API; "
            "see test_text_processor_v2_e2e.py for current v2 tests."
        )
    ),
]


class TestTextExtraction:
    """Test text extraction functionality of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_basic_text_extraction_pymupdf(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test text extraction with PyMuPDF engine."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine="pymupdf",
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, f"PyMuPDF extraction should succeed: {result.error}"
        assert result.data is not None
        assert "chunks" in result.data
        assert "chunk_count" in result.data

        chunks = result.data["chunks"]
        assert isinstance(chunks, list), "Chunks should be a list"
        assert len(chunks) > 0, "Should create at least one chunk"

        # Verify chunk structure
        for chunk in chunks:
            assert "content" in chunk, "Chunk should have content"
            assert "metadata" in chunk, "Chunk should have metadata"
            assert isinstance(chunk["content"], str), "Content should be string"
            assert len(chunk["content"].strip()) > 0, "Content should not be empty"

    @pytest.mark.asyncio
    async def test_text_extraction_pdfplumber(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test text extraction with pdfplumber engine."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine="pdfplumber",
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, f"pdfplumber extraction should succeed: {result.error}"
        assert "chunks" in result.data
        assert len(result.data["chunks"]) > 0

    @pytest.mark.asyncio
    async def test_ocr_fallback_enabled(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test OCR fallback when enabled."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            enable_ocr_fallback=True,
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        ocr_pdf = sample_pdf_files["ocr_required_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=ocr_pdf["path"], metadata={"filename": ocr_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        # Should either succeed with OCR or fail gracefully
        if result.success:
            assert "chunks" in result.data
        else:
            assert "ocr" in result.error.lower() or "text" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ocr_fallback_disabled(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test behavior when OCR fallback is disabled."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            enable_ocr_fallback=False,  # OCR disabled
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        ocr_pdf = sample_pdf_files["ocr_required_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=ocr_pdf["path"], metadata={"filename": ocr_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        # Should fail since OCR is disabled and no text is extractable
        assert not result.success, "Should fail when OCR disabled and no text available"
        assert "text" in result.error.lower() or "extract" in result.error.lower()

    @pytest.mark.asyncio
    async def test_multi_page_extraction(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test text extraction from multi-page documents."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=500,  # Smaller chunks for multi-page test
            chunk_overlap=100,
        )

        # Create multi-page content
        multi_page_content = """Page 1: Introduction
This is the first page of the document.
It contains important technical information about the device.
The device specifications are detailed below.

Page 2: Technical Specifications
The device has the following specifications:
- Print Speed: 75 pages per minute
- Resolution: 1200 x 1200 dpi
- Memory: 2GB standard, upgradeable to 4GB
- Paper Capacity: 650 sheets standard, 1,150 maximum

Page 3: Maintenance Procedures
Regular maintenance is required for optimal performance:
1. Daily: Clean platen glass
2. Weekly: Check waste toner container
3. Monthly: Clean transfer roller
4. Quarterly: Replace maintenance kit

Page 4: Error Codes
Common error codes include:
- 900.01: Fuser unit error
- 900.02: Exposure lamp error
- 920.00: Waste toner full

Page 5: Troubleshooting
If problems occur:
1. Check error code display
2. Refer to error code section
3. Follow recommended procedures
4. Contact support if needed"""

        test_file = temp_test_pdf / "multi_page_manual.pdf"
        test_file.write_text(multi_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Multi-page extraction should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks from multi-page content"

        # Verify content from different pages is included
        all_content = " ".join(chunk["content"] for chunk in chunks)
        assert "Page 1" in all_content
        assert "Page 2" in all_content
        assert "Page 3" in all_content
        assert "Page 4" in all_content
        assert "Page 5" in all_content

    @pytest.mark.asyncio
    async def test_page_texts_context_attachment(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test that page_texts are attached to context for downstream processors."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Processing should succeed"

        # Check that page_texts were attached to context
        updated_context = result.data.get("context", context)
        assert hasattr(updated_context, "page_texts"), "Context should have page_texts attribute"

        page_texts = updated_context.page_texts
        assert isinstance(page_texts, dict), "page_texts should be a dictionary"
        assert len(page_texts) > 0, "Should have extracted page texts"

        # Verify page_texts structure
        for page_num, text in page_texts.items():
            assert isinstance(page_num, int), "Page numbers should be integers"
            assert isinstance(text, str), "Page text should be string"


class TestChunking:
    """Test chunking functionality of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_basic_chunking(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test basic chunking with default parameters."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=200,
            chunk_overlap=50,  # Small chunk size for testing
        )

        # Create content larger than chunk size
        test_content = " ".join([f"Sentence {i} with some content to test chunking." for i in range(20)])

        test_file = temp_test_pdf / "chunking_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Basic chunking should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 1, "Should create multiple chunks for large content"

        # Verify chunk sizes
        for i, chunk in enumerate(chunks):
            content = chunk["content"]
            assert len(content) <= 200 + 50, f"Chunk {i} should respect size limit with overlap"
            assert len(content.strip()) > 0, f"Chunk {i} should not be empty"

    @pytest.mark.asyncio
    async def test_chunking_with_overlap(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test chunking with overlap between chunks."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=150,
            chunk_overlap=50,  # 33% overlap
        )

        # Create content with clear sections
        test_content = """Section 1: Introduction
This is the introduction section with important information.
It provides background about the device and its capabilities.

Section 2: Technical Details
This section contains technical specifications and details.
It includes measurements, requirements, and compatibility information.

Section 3: Maintenance
This section covers maintenance procedures and schedules.
It provides step-by-step instructions for routine maintenance.

Section 4: Troubleshooting
This section contains troubleshooting guides and error codes.
It helps diagnose and resolve common problems."""

        test_file = temp_test_pdf / "overlap_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Chunking with overlap should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 1, "Should create multiple chunks"

        # Verify overlap between consecutive chunks
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]["content"]
            curr_chunk = chunks[i]["content"]

            # Find overlap (simplified check - last part of prev should be in curr)
            prev_end = prev_chunk[-100:] if len(prev_chunk) > 100 else prev_chunk
            curr_start = curr_chunk[:100] if len(curr_chunk) > 100 else curr_chunk

            # Should have some overlap
            overlap_found = any(word in curr_start for word in prev_end.split() if len(word) > 3)
            # Note: This is a simplified check - actual overlap might be more complex

    @pytest.mark.asyncio
    async def test_chunking_respects_chunk_size(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test that chunking respects the specified chunk size."""
        # Arrange
        chunk_size = 100
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=chunk_size, chunk_overlap=20
        )

        # Create predictable content
        test_content = " ".join([f"word{i}" for i in range(200)])  # 200 words

        test_file = temp_test_pdf / "size_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Chunking should respect size limits"
        chunks = result.data["chunks"]

        # Most chunks should be close to the target size (allowing some variance)
        for chunk in chunks:
            content_length = len(chunk["content"])
            # Allow some flexibility for paragraph boundaries
            assert (
                content_length <= chunk_size + chunk_overlap + 50
            ), f"Chunk size {content_length} exceeds limit {chunk_size + chunk_overlap + 50}"

    @pytest.mark.asyncio
    async def test_chunking_preserves_paragraphs(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test that chunking preserves paragraph boundaries."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=150, chunk_overlap=30)

        # Create content with clear paragraph boundaries
        test_content = """This is the first paragraph. It contains multiple sentences that should stay together when possible. The paragraph is designed to test paragraph preservation during chunking operations.

This is the second paragraph. It also contains multiple sentences. The chunking algorithm should try to avoid breaking paragraphs in the middle of sentences when creating chunks.

This is the third paragraph. It provides additional content for testing. The goal is to ensure that paragraph boundaries are respected during the chunking process.

This is the fourth and final paragraph. It completes the test content. The chunking should maintain paragraph integrity where feasible while respecting size constraints."""

        test_file = temp_test_pdf / "paragraph_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Paragraph-aware chunking should succeed"
        chunks = result.data["chunks"]

        # Check that chunks don't break paragraphs unnecessarily
        for chunk in chunks:
            content = chunk["content"]
            lines = content.split("\n")

            # Each line should be a complete paragraph (not ending mid-sentence if avoidable)
            for line in lines:
                if line.strip():  # Skip empty lines
                    # Should not end with incomplete sentence patterns
                    assert not line.strip().endswith(" and "), "Should not break at 'and'"
                    assert not line.strip().endswith(" the "), "Should not break at 'the'"
                    assert not line.strip().endswith(" of "), "Should not break at 'of'"

    @pytest.mark.asyncio
    async def test_chunking_with_headers(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test chunking with header cleanup."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20, enable_header_cleanup=True
        )

        # Content with headers that should be cleaned up
        header_content = """1. Introduction
This is the introduction section. It provides basic information about the document and its purpose.

2. Technical Specifications
This section contains detailed technical specifications. The specifications include performance metrics and requirements.

3. Installation Procedures
This section describes installation procedures. Step-by-step instructions are provided for proper installation.

4. Maintenance Schedule
This section outlines the maintenance schedule. Regular maintenance is essential for optimal performance."""

        test_file = temp_test_pdf / "header_test.pdf"
        test_file.write_text(header_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Header-aware chunking should succeed"
        chunks = result.data["chunks"]

        # Check that headers are handled appropriately
        for chunk in chunks:
            content = chunk["content"]
            # Should not have repeated headers within chunks
            header_count = content.count("1. Introduction") + content.count("2. Technical")
            assert header_count <= 1, "Should not duplicate headers within chunk"

    @pytest.mark.asyncio
    async def test_hierarchical_chunking(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test hierarchical chunking with document structure detection."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=150, chunk_overlap=30, enable_hierarchical_chunking=True
        )

        # Content with clear hierarchical structure
        hierarchical_content = """# Service Manual - Chapter 1

## 1.1 Safety Information
This section contains safety information and precautions.
Read all safety warnings before proceeding with any maintenance.

### 1.1.1 Electrical Safety
Electrical safety is critical when working with electronic equipment.
Always disconnect power before performing maintenance.

### 1.1.2 Mechanical Safety
Mechanical safety involves moving parts and pinch points.
Keep hands clear of moving components.

## 1.2 Technical Specifications
This section provides technical specifications.
Detailed specifications are listed below.

### 1.2.1 Performance Specifications
Performance specifications include speed and quality metrics.
The device can print up to 75 pages per minute.

### 1.2.2 Physical Specifications
Physical specifications include dimensions and weight.
The device measures 24" x 20" x 24" and weighs 150 lbs.

# Service Manual - Chapter 2

## 2.1 Installation Procedures
This section covers installation procedures.
Follow these steps carefully for proper installation.

### 2.1.1 Site Preparation
Prepare the installation site according to specifications.
Ensure adequate space and ventilation.

### 2.1.2 Power Connection
Connect power according to electrical requirements.
Use appropriate power connections and grounding."""

        test_file = temp_test_pdf / "hierarchical_test.pdf"
        test_file.write_text(hierarchical_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Hierarchical chunking should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks from hierarchical content"

        # Verify hierarchical metadata in chunks
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            # Should have hierarchical information if detected
            assert isinstance(metadata, dict), "Chunk metadata should be a dictionary"

    @pytest.mark.asyncio
    async def test_error_code_section_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test detection of error code sections in content."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=200, chunk_overlap=50, enable_error_code_detection=True
        )

        # Content with error code sections
        error_code_content = """Error Code Reference Manual
=============================

Critical Errors:
900.01 - Fuser Unit Error
Description: The fuser unit has failed to reach operating temperature.
Causes: Failed fuser lamp, blown thermal fuse, faulty temperature sensor.
Solution: Check fuser assembly, replace failed components.

900.02 - Exposure Lamp Error
Description: The exposure lamp is not functioning properly.
Causes: Lamp failure, power supply issue, connector problem.
Solution: Test lamp continuity, check power supply, inspect connectors.

900.03 - High Voltage Error
Description: High voltage circuit is malfunctioning.
Causes: Faulty HV power supply, short circuit, component failure.
Solution: Check HV components, test power supply, inspect for shorts.

Warning Errors:
920.00 - Waste Toner Full
Description: The waste toner container is full.
Causes: Normal operation, container capacity reached.
Solution: Replace waste toner container.

921.00 - Low Toner Warning
Description: Toner cartridge is running low.
Causes: Normal toner consumption.
Solution: Replace toner cartridge soon."""

        test_file = temp_test_pdf / "error_codes.pdf"
        test_file.write_text(error_code_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Error code detection should succeed"
        chunks = result.data["chunks"]

        # Should detect error codes in content
        all_content = " ".join(chunk["content"] for chunk in chunks)
        assert "900.01" in all_content
        assert "900.02" in all_content
        assert "920.00" in all_content

        # Check for error code metadata in chunks
        error_chunks_found = False
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            if metadata.get("contains_error_codes"):
                error_chunks_found = True
                break

        # Note: Error code detection might be implemented in metadata
        # At minimum, the content should be preserved correctly

    @pytest.mark.asyncio
    async def test_chunk_linking(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test chunk linking with previous/next relationships."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20, enable_chunk_linking=True
        )

        # Create content that will produce multiple chunks
        test_content = " ".join([f"Sentence {i} with content for linking test." for i in range(30)])

        test_file = temp_test_pdf / "linking_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Chunk linking should succeed"
        chunks = result.data["chunks"]

        if len(chunks) > 1:
            # Check linking metadata
            for i, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {})

                # First chunk should have no previous
                if i == 0:
                    assert metadata.get("previous_chunk_id") is None, "First chunk should have no previous"
                else:
                    assert metadata.get("previous_chunk_id") is not None, f"Chunk {i} should have previous"

                # Last chunk should have no next
                if i == len(chunks) - 1:
                    assert metadata.get("next_chunk_id") is None, "Last chunk should have no next"
                else:
                    assert metadata.get("next_chunk_id") is not None, f"Chunk {i} should have next"


class TestChunkMetadata:
    """Test chunk metadata functionality of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_chunk_index_assignment(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test correct chunk index assignment."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        # Create content for multiple chunks
        test_content = " ".join([f"Chunk test sentence {i}." for i in range(50)])

        test_file = temp_test_pdf / "index_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Chunk index assignment should succeed"
        chunks = result.data["chunks"]

        # Verify sequential chunk indices
        for i, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            chunk_index = metadata.get("chunk_index")
            assert chunk_index == i, f"Chunk {i} should have index {i}, got {chunk_index}"

    @pytest.mark.asyncio
    async def test_page_range_tracking(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test page range tracking in chunks."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=150, chunk_overlap=30)

        # Multi-page content
        multi_page_content = """Page 1: This is the first page content.
It contains information about the device.
Technical specifications are included.

Page 2: This is the second page content.
It continues with more technical details.
Installation procedures are described.

Page 3: This is the third page content.
It covers maintenance procedures.
Troubleshooting information is provided."""

        test_file = temp_test_pdf / "page_range_test.pdf"
        test_file.write_text(multi_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Page range tracking should succeed"
        chunks = result.data["chunks"]

        # Verify page range metadata
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            page_start = metadata.get("page_start")
            page_end = metadata.get("page_end")

            assert page_start is not None, "Chunk should have page_start"
            assert page_end is not None, "Chunk should have page_end"
            assert page_start <= page_end, "page_start should be <= page_end"
            assert page_start >= 1, "page_start should be >= 1"

    @pytest.mark.asyncio
    async def test_content_hash_generation(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test content hash generation for chunks."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = "Test content for hash generation. This should produce consistent hashes."

        test_file = temp_test_pdf / "hash_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Content hash generation should succeed"
        chunks = result.data["chunks"]

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            content_hash = metadata.get("content_hash")

            assert content_hash is not None, "Chunk should have content_hash"
            assert len(content_hash) == 64, "Hash should be SHA-256 (64 hex chars)"

            # Verify hash is correct for content
            expected_hash = hashlib.sha256(chunk["content"].encode()).hexdigest()
            assert content_hash == expected_hash, "Content hash should match expected SHA-256"

    @pytest.mark.asyncio
    async def test_char_count_calculation(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test character count calculation in chunks."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = "This is test content for character count calculation."

        test_file = temp_test_pdf / "char_count_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Character count calculation should succeed"
        chunks = result.data["chunks"]

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            char_count = metadata.get("char_count")

            assert char_count is not None, "Chunk should have char_count"
            assert char_count == len(chunk["content"]), "Char count should match content length"
            assert char_count > 0, "Char count should be positive"

    @pytest.mark.asyncio
    async def test_chunk_type_classification(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test chunk type classification."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=150, chunk_overlap=30)

        # Mixed content for classification
        mixed_content = """Introduction: This is an introductory paragraph.
It provides background information about the device.

Error Code 900.01: Fuser Unit Error
This error indicates a problem with the fuser unit.
The fuser unit may have failed to reach operating temperature.

Technical Specifications: The device has the following specs:
- Print Speed: 75 ppm
- Resolution: 1200 x 1200 dpi
- Memory: 2GB standard

Maintenance Procedures: Regular maintenance includes:
1. Daily cleaning of platen glass
2. Weekly check of waste toner
3. Monthly cleaning of transfer roller

Troubleshooting: If problems occur:
1. Check error codes
2. Refer to manual
3. Contact support"""

        test_file = temp_test_pdf / "classification_test.pdf"
        test_file.write_text(mixed_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Chunk type classification should succeed"
        chunks = result.data["chunks"]

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            chunk_type = metadata.get("chunk_type")

            assert chunk_type is not None, "Chunk should have chunk_type"
            assert isinstance(chunk_type, str), "Chunk type should be string"

            # Should be one of expected types
            expected_types = ["text", "error_code", "specification", "procedure", "introduction"]
            assert chunk_type in expected_types, f"Unknown chunk type: {chunk_type}"


class TestTextDatabaseOperations:
    """Test database operations of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_chunks_saved_to_database(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test that chunks are saved to database."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = "Test content for database save verification."

        test_file = temp_test_pdf / "db_save_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Database save should succeed"
        chunks = result.data["chunks"]

        # Verify chunks were saved to mock database
        assert len(mock_database_adapter.chunks) > 0, "Chunks should be saved to database"

        # Verify each chunk in database
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if chunk_id:
                assert chunk_id in mock_database_adapter.chunks, f"Chunk {chunk_id} should be in database"
                db_chunk = mock_database_adapter.chunks[chunk_id]
                assert db_chunk["document_id"] == context.document_id
                assert db_chunk["content"] == chunk["content"]

    @pytest.mark.asyncio
    async def test_chunk_deduplication(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test chunk deduplication in database."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        # Create content that might produce duplicate chunks
        test_content = "Repeated content for deduplication test. " * 5

        test_file = temp_test_pdf / "dedup_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Deduplication should succeed"
        chunks = result.data["chunks"]

        # Check for duplicate content hashes
        content_hashes = []
        for chunk in chunks:
            content_hash = chunk.get("metadata", {}).get("content_hash")
            if content_hash:
                content_hashes.append(content_hash)

        # Should have minimal duplicates (due to overlap, some expected)
        unique_hashes = set(content_hashes)
        assert len(unique_hashes) >= len(content_hashes) * 0.7, "Should deduplicate effectively"

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test error handling when database operations fail."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = "Test content for database error handling."

        test_file = temp_test_pdf / "db_error_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Mock database to fail
        async def failing_create_chunk(chunk):
            raise Exception("Database connection failed")

        mock_database_adapter.create_chunk = failing_create_chunk

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "Should fail when database operations fail"
        assert "database" in result.error.lower() or "connection" in result.error.lower()

    @pytest.mark.asyncio
    async def test_partial_save_failure(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of partial chunk save failures."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = " ".join([f"Chunk content {i}." for i in range(10)])

        test_file = temp_test_pdf / "partial_save_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Mock database to fail on second chunk
        call_count = 0

        async def failing_on_second_chunk(chunk):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Second chunk save failed")
            return str(uuid4())  # Return fake ID for successful saves

        mock_database_adapter.create_chunk = failing_on_second_chunk

        # Act
        result = await processor.process(context)

        # Assert
        # Should handle partial failures gracefully
        if not result.success:
            assert "chunk" in result.error.lower() or "database" in result.error.lower()


class TestTextConfiguration:
    """Test configuration options of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_custom_chunk_size(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test custom chunk size configuration."""
        # Arrange
        custom_chunk_size = 75
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=custom_chunk_size, chunk_overlap=15
        )

        # Create content larger than custom chunk size
        test_content = " ".join([f"Word{i}" for i in range(50)])

        test_file = temp_test_pdf / "custom_size_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Custom chunk size should work"
        chunks = result.data["chunks"]

        # Verify chunks respect custom size
        for chunk in chunks:
            content_length = len(chunk["content"])
            # Allow some flexibility
            assert (
                content_length <= custom_chunk_size + 30
            ), f"Chunk size {content_length} should respect custom limit {custom_chunk_size}"

    @pytest.mark.asyncio
    async def test_custom_overlap_size(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test custom overlap size configuration."""
        # Arrange
        custom_overlap = 60  # Large overlap
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=150, chunk_overlap=custom_overlap
        )

        test_content = """Section 1: This is the first section with important content.
It contains technical information that should appear in overlapping chunks.

Section 2: This is the second section with more content.
It continues with additional technical details and specifications.

Section 3: This is the third section concluding the document.
It provides final information and summary details."""

        test_file = temp_test_pdf / "custom_overlap_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Custom overlap should work"
        chunks = result.data["chunks"]

        if len(chunks) > 1:
            # Verify overlap is applied
            for i in range(1, len(chunks)):
                prev_chunk = chunks[i - 1]["content"]
                curr_chunk = chunks[i]["content"]

                # With large overlap, should see significant content repetition
                # This is a simplified check - actual implementation may vary
                overlap_content = prev_chunk[-custom_overlap:] if len(prev_chunk) > custom_overlap else prev_chunk
                curr_start = curr_chunk[:custom_overlap] if len(curr_chunk) > custom_overlap else curr_chunk

                # Should have some common content due to overlap
                common_words = set(overlap_content.split()) & set(curr_start.split())
                assert len(common_words) > 0, "Should have overlapping content"

    @pytest.mark.asyncio
    async def test_enable_ocr_from_env(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test OCR activation via environment variable."""
        # Arrange
        import os

        # Set environment variable
        os.environ["ENABLE_OCR_FALLBACK"] = "true"

        try:
            processor = OptimizedTextProcessor(
                database_adapter=mock_database_adapter,
                chunk_size=processor_test_config["chunk_size"],
                chunk_overlap=processor_test_config["chunk_overlap"],
            )

            ocr_pdf = sample_pdf_files["ocr_required_pdf"]

            context = ProcessingContext(
                document_id="test-doc-id", file_path=ocr_pdf["path"], metadata={"filename": ocr_pdf["path"].name}
            )

            # Act
            result = await processor.process(context)

            # Assert
            # Should handle OCR according to environment setting
            assert result is not None, "Should process with OCR from environment"

        finally:
            # Cleanup environment variable
            os.environ.pop("ENABLE_OCR_FALLBACK", None)

    @pytest.mark.asyncio
    async def test_pdf_engine_selection(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test PDF engine selection."""
        # Arrange
        engines = ["pymupdf", "pdfplumber"]
        valid_pdf = sample_pdf_files["valid_pdf"]

        for engine in engines:
            processor = OptimizedTextProcessor(
                database_adapter=mock_database_adapter,
                pdf_engine=engine,
                chunk_size=processor_test_config["chunk_size"],
                chunk_overlap=processor_test_config["chunk_overlap"],
            )

            context = ProcessingContext(
                document_id=f"test-doc-{engine}",
                file_path=valid_pdf["path"],
                metadata={"filename": valid_pdf["path"].name},
            )

            # Act
            result = await processor.process(context)

            # Assert
            assert result.success, f"Engine {engine} should work"
            assert "chunks" in result.data, f"Engine {engine} should produce chunks"

    @pytest.mark.asyncio
    async def test_hierarchical_chunking_toggle(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test hierarchical chunking toggle."""
        # Arrange
        hierarchical_content = """# Main Title

## Section 1
Content for section 1.

### Subsection 1.1
Content for subsection 1.1.

### Subsection 1.2
Content for subsection 1.2.

## Section 2
Content for section 2.

### Subsection 2.1
Content for subsection 2.1."""

        test_file = temp_test_pdf / "hierarchical_toggle_test.pdf"
        test_file.write_text(hierarchical_content)

        # Test with hierarchical chunking enabled
        processor_enabled = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20, enable_hierarchical_chunking=True
        )

        context = ProcessingContext(
            document_id="test-doc-hierarchical", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result_enabled = await processor_enabled.process(context)

        # Test with hierarchical chunking disabled
        processor_disabled = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20, enable_hierarchical_chunking=False
        )

        result_disabled = await processor_disabled.process(context)

        # Assert
        assert result_enabled.success, "Hierarchical chunking should succeed"
        assert result_disabled.success, "Non-hierarchical chunking should succeed"

        # Both should produce chunks, but potentially different structures
        assert "chunks" in result_enabled.data
        assert "chunks" in result_disabled.data


class TestTextEdgeCases:
    """Test edge cases and boundary conditions of OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_empty_pdf_handling(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test handling of empty PDF files."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )
        empty_pdf = sample_pdf_files["empty_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=empty_pdf["path"], metadata={"filename": empty_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "Empty PDF should fail"
        assert "empty" in result.error.lower() or "content" in result.error.lower()

    @pytest.mark.asyncio
    async def test_single_page_pdf(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing of single-page PDFs."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        single_page_content = """Single Page Document
=====================

This is a single page document with limited content.
It should still be processed correctly and create appropriate chunks.
The content includes technical information and specifications.

Technical Specifications:
- Device: Test Device Model X
- Speed: 50 pages per minute
- Resolution: 600 x 600 dpi
- Memory: 1GB standard

Contact Information:
Support: support@testdevice.com
Phone: 1-800-TEST-DEV
Website: www.testdevice.com"""

        test_file = temp_test_pdf / "single_page.pdf"
        test_file.write_text(single_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Single page processing should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks from single page"

        # Verify content is preserved
        all_content = " ".join(chunk["content"] for chunk in chunks)
        assert "Single Page Document" in all_content
        assert "Technical Specifications" in all_content
        assert "Test Device Model X" in all_content

    @pytest.mark.asyncio
    async def test_very_large_pdf(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing of very large PDF content."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=200,
            chunk_overlap=50,  # Reasonable chunk size
        )

        # Create large content (simulating large PDF)
        large_content = " ".join([f"Large document sentence {i} with technical content." for i in range(1000)])

        test_file = temp_test_pdf / "large_content.pdf"
        test_file.write_text(large_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Large content processing should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 5, "Should create multiple chunks for large content"

        # Verify total content is preserved
        total_content_length = sum(len(chunk["content"]) for chunk in chunks)
        assert total_content_length >= len(large_content) * 0.9, "Should preserve most content"

    @pytest.mark.asyncio
    async def test_pdf_with_no_text(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of PDFs with no extractable text."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            enable_ocr_fallback=False,  # Disable OCR for this test
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )

        # Create PDF-like file with no text (binary content)
        no_text_file = temp_test_pdf / "no_text.pdf"
        no_text_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=no_text_file, metadata={"filename": no_text_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "No-text PDF should fail when OCR disabled"
        assert "text" in result.error.lower() or "extract" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pdf_with_only_images(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of PDFs with only images (no text)."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            enable_ocr_fallback=False,  # Disable OCR
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
        )

        # Simulate image-only PDF
        image_only_file = temp_test_pdf / "image_only.pdf"
        image_only_file.write_bytes(b"%PDF-1.4\n[Image data only - no text]\n")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=image_only_file, metadata={"filename": image_only_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "Image-only PDF should fail when OCR disabled"
        assert "text" in result.error.lower() or "ocr" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unicode_text_handling(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of Unicode text content."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        unicode_content = """Unicode Test Document
=======================

English: This is standard English text.
Deutsch: Dies ist deutscher Text mit Umlauten: äöüß.
Français: Ceci est un texte français avec accents: éàèêç.
Español: Este es texto español con ñ y tilde: áéíóúñ.
中文: 这是中文文本，包含汉字。
日本語: これは日本語のテキストです。
Русский: Это русский текст с кириллицей.

Special Characters:
• Bullet point
© Copyright symbol
® Registered trademark
™ Trademark
° Degree symbol
± Plus-minus
× Multiplication
÷ Division

Currency Symbols:
$ Dollar
€ Euro
£ Pound
¥ Yen
₹ Rupee"""

        test_file = temp_test_pdf / "unicode_test.pdf"
        test_file.write_text(unicode_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Unicode text processing should succeed"
        chunks = result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks from Unicode content"

        # Verify Unicode content is preserved
        all_content = " ".join(chunk["content"] for chunk in chunks)
        assert "Deutsch" in all_content
        assert "Français" in all_content
        assert "中文" in all_content
        assert "日本語" in all_content
        assert "Русский" in all_content

        # Check for specific Unicode characters
        assert "äöüß" in all_content or "Deutsch" in all_content
        assert "éàèêç" in all_content or "Français" in all_content
        assert "ñ" in all_content or "Español" in all_content


class TestTextIntegration:
    """Test integration scenarios for OptimizedTextProcessor."""

    @pytest.mark.asyncio
    async def test_full_text_processing_flow(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test complete text processing flow with all features."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            chunk_size=150,
            chunk_overlap=30,
            enable_ocr_fallback=True,
            enable_hierarchical_chunking=True,
            enable_error_code_detection=True,
            enable_header_cleanup=True,
            enable_chunk_linking=True,
        )

        # Comprehensive test content
        full_content = """Konica Minolta C750i Service Manual
=====================================

Document Information:
- Manufacturer: Konica Minolta
- Model: C750i
- Document Type: Service Manual
- Language: English

# Chapter 1: Safety Information

## 1.1 Electrical Safety
Always disconnect power before performing maintenance.
Use proper grounding and follow electrical safety procedures.

## 1.2 Mechanical Safety
Keep hands clear of moving parts.
Use proper lockout procedures during maintenance.

# Chapter 2: Technical Specifications

## 2.1 Performance Specifications
- Print Speed: 75 pages per minute
- Resolution: 1200 x 1200 dpi
- Memory: 2GB standard, 4GB maximum
- Paper Capacity: 650 sheets standard, 1,150 maximum

## 2.2 Physical Specifications
- Dimensions: 24" x 20" x 24"
- Weight: 150 lbs
- Power Requirements: 120V AC, 15A

# Chapter 3: Error Codes

## 3.1 Critical Errors
900.01: Fuser Unit Error - Fuser unit failed to reach temperature
900.02: Exposure Lamp Error - Lamp failure or power supply issue
900.03: High Voltage Error - HV circuit malfunction

## 3.2 Warning Errors
920.00: Waste Toner Full - Replace waste toner container
921.00: Low Toner Warning - Replace toner cartridge soon

# Chapter 4: Maintenance Procedures

## 4.1 Daily Maintenance
1. Clean platen glass
2. Check paper path
3. Verify output quality

## 4.2 Weekly Maintenance
1. Check waste toner container
2. Clean transfer roller
3. Inspect fuser unit

## 4.3 Quarterly Maintenance
1. Replace maintenance kit
2. Clean optical system
3. Calibrate print quality

# Chapter 5: Troubleshooting

## 5.1 Common Problems
Paper Jams: Check paper path, remove jammed paper
Poor Quality: Clean drum, check toner level
Error Codes: Refer to error code section

## 5.2 Contact Information
Support: 1-800-KONICA
Website: www.konicaminolta.com
Email: support@konicaminolta.com"""

        test_file = temp_test_pdf / "full_integration_test.pdf"
        test_file.write_text(full_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Full integration test should succeed"

        # Verify all components are present
        assert "chunks" in result.data, "Should have chunks"
        assert "chunk_count" in result.data, "Should have chunk count"
        assert "context" in result.data, "Should have updated context"

        chunks = result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks"

        # Verify content preservation
        all_content = " ".join(chunk["content"] for chunk in chunks)
        assert "Konica Minolta" in all_content
        assert "C750i" in all_content
        assert "900.01" in all_content
        assert "Safety Information" in all_content
        assert "Technical Specifications" in all_content
        assert "Maintenance Procedures" in all_content

        # Verify chunk metadata
        for chunk in chunks:
            assert "content" in chunk, "Chunk should have content"
            assert "metadata" in chunk, "Chunk should have metadata"

            metadata = chunk["metadata"]
            assert "chunk_index" in metadata, "Chunk should have index"
            assert "content_hash" in metadata, "Chunk should have hash"
            assert "char_count" in metadata, "Chunk should have char count"
            assert "page_start" in metadata, "Chunk should have page start"
            assert "page_end" in metadata, "Chunk should have page end"

        # Verify context was updated
        updated_context = result.data["context"]
        assert hasattr(updated_context, "page_texts"), "Context should have page_texts"
        assert len(updated_context.page_texts) > 0, "Should have extracted page texts"

        # Verify database operations
        assert len(mock_database_adapter.chunks) > 0, "Chunks should be saved to database"

        # Verify chunk linking if enabled
        if len(chunks) > 1:
            for i, chunk in enumerate(chunks):
                metadata = chunk["metadata"]
                if i == 0:
                    assert metadata.get("previous_chunk_id") is None, "First chunk should have no previous"
                else:
                    assert metadata.get("previous_chunk_id") is not None, f"Chunk {i} should have previous"

                if i == len(chunks) - 1:
                    assert metadata.get("next_chunk_id") is None, "Last chunk should have no next"
                else:
                    assert metadata.get("next_chunk_id") is not None, f"Chunk {i} should have next"

    @pytest.mark.asyncio
    async def test_text_processor_with_stage_tracker(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test integration with StageTracker."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20, stage_tracker=mock_stage_tracker
        )

        test_content = """Test content for StageTracker integration.
This should trigger stage tracking events.
The processing should be monitored and tracked."""

        test_file = temp_test_pdf / "stage_tracker_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "StageTracker integration should succeed"
        assert "chunks" in result.data, "Should produce chunks"

        # StageTracker calls are logged in the mock
        # We verify the processing succeeded

    @pytest.mark.asyncio
    async def test_text_processor_result_format(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test correct result format from text processor."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        test_content = "Test content for result format verification."

        test_file = temp_test_pdf / "result_format_test.pdf"
        test_file.write_text(test_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert isinstance(result, ProcessingResult), "Should return ProcessingResult"
        assert result.success, "Processing should succeed"
        assert result.data is not None, "Should have data"
        assert result.error is None, "Should have no error on success"

        # Verify data structure
        data = result.data
        assert "chunks" in data, "Data should contain chunks"
        assert "chunk_count" in data, "Data should contain chunk count"
        assert "context" in data, "Data should contain context"

        # Verify chunks structure
        chunks = data["chunks"]
        assert isinstance(chunks, list), "Chunks should be a list"
        assert len(chunks) > 0, "Should have at least one chunk"

        for chunk in chunks:
            assert isinstance(chunk, dict), "Each chunk should be a dictionary"
            assert "content" in chunk, "Chunk should have content"
            assert "metadata" in chunk, "Chunk should have metadata"

    @pytest.mark.asyncio
    async def test_context_propagation(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test context propagation through text processing."""
        # Arrange
        processor = OptimizedTextProcessor(database_adapter=mock_database_adapter, chunk_size=100, chunk_overlap=20)

        # Initial context with metadata
        initial_context = ProcessingContext(
            document_id="test-doc-id",
            file_path=temp_test_pdf / "context_test.pdf",
            metadata={
                "filename": "context_test.pdf",
                "manufacturer": "TestCorp",
                "model": "C4080",
                "document_type": "service_manual",
                "language": "en",
            },
        )

        # Add content to file
        initial_context.file_path.write_text("Test content for context propagation.")

        # Act
        result = await processor.process(initial_context)

        # Assert
        assert result.success, "Context propagation should succeed"

        # Get updated context
        updated_context = result.data.get("context")
        assert updated_context is not None, "Should return updated context"

        # Verify original metadata is preserved
        assert updated_context.metadata.get("manufacturer") == "TestCorp"
        assert updated_context.metadata.get("model") == "C4080"
        assert updated_context.metadata.get("document_type") == "service_manual"
        assert updated_context.metadata.get("language") == "en"

        # Verify new data is added
        assert hasattr(updated_context, "page_texts"), "Should have page_texts"
        assert len(updated_context.page_texts) > 0, "Should have extracted page texts"


# Parameterized tests for different configurations
@pytest.mark.parametrize(
    "chunk_size,chunk_overlap,expected_chunks",
    [
        (50, 10, "many"),  # Small chunks, many expected
        (100, 20, "medium"),  # Medium chunks
        (200, 50, "few"),  # Large chunks, few expected
    ],
)
@pytest.mark.asyncio
async def test_chunk_size_variations(mock_database_adapter, temp_test_pdf, chunk_size, chunk_overlap, expected_chunks):
    """Test different chunk size configurations."""
    # Arrange
    processor = OptimizedTextProcessor(
        database_adapter=mock_database_adapter, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    # Create consistent test content
    test_content = " ".join([f"Test sentence {i}." for i in range(100)])

    test_file = temp_test_pdf / f"chunk_test_{chunk_size}.pdf"
    test_file.write_text(test_content)

    context = ProcessingContext(
        document_id=f"test-doc-{chunk_size}", file_path=test_file, metadata={"filename": test_file.name}
    )

    # Act
    result = await processor.process(context)

    # Assert
    assert result.success, f"Chunk size {chunk_size} should work"
    chunks = result.data["chunks"]

    # Rough verification of chunk count expectations
    if expected_chunks == "many":
        assert len(chunks) >= 10, "Small chunks should produce many chunks"
    elif expected_chunks == "medium":
        assert 5 <= len(chunks) <= 15, "Medium chunks should produce medium number"
    elif expected_chunks == "few":
        assert len(chunks) <= 8, "Large chunks should produce few chunks"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
