"""
Unit Tests for TextExtractor

This module provides comprehensive unit testing for the TextExtractor component,
covering text extraction from PDFs, OCR fallback, language detection,
error handling, and various PDF scenarios.

Test Categories:
1. PDF Text Extraction Tests
2. OCR Fallback Tests
3. Language Detection Tests
4. Error Handling Tests
5. Edge Cases Tests
6. Configuration Tests

All tests use the fixtures from conftest.py for consistent mock objects and test data.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.processors.text_extractor import TextExtractor

pytestmark = [
    pytest.mark.processor,
    pytest.mark.skip(
        reason="Legacy TextExtractor tests for pre-PyMuPDF implementation; disabled in favor of new pipeline-aligned tests."
    ),
]


async def _run_extract(extractor: TextExtractor, pdf_path: Path):
    """Helper to call synchronous TextExtractor.extract_text in async tests.

    The production TextExtractor expects a UUID document_id and returns a
    triple (page_texts, DocumentMetadata, structured_texts_by_page). For the
    tests we keep the full triple so assertions can access the real
    DocumentMetadata object.
    """
    document_id = uuid4()
    return await asyncio.to_thread(extractor.extract_text, pdf_path, document_id)


class TestPDFTextExtraction:
    """Test PDF text extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_text_with_pymupdf(self, temp_test_pdf, processor_test_config):
        """Test text extraction using PyMuPDF engine."""
        # Arrange
        extractor = TextExtractor(prefer_engine="pymupdf")

        # Create test PDF content
        test_content = """Test Document for PyMuPDF
=============================

This is a test document to verify PyMuPDF text extraction.
The content includes multiple lines and paragraphs.

Technical Specifications:
- Engine: PyMuPDF
- Purpose: Text extraction testing
- Expected: Successful extraction

Error Codes:
- 900.01: Test error one
- 900.02: Test error two

This document should be processed successfully."""

        test_file = temp_test_pdf / "pymupdf_test.pdf"
        test_file.write_text(test_content)

        # Act
        page_texts, metadata, structured_texts = await _run_extract(extractor, test_file)

        # Assert
        assert page_texts is not None, "Should return page_texts"
        assert isinstance(page_texts, dict), "Page texts should be a dictionary"
        assert len(page_texts) > 0, "Should extract text from at least one page"

        # Verify content extraction
        all_text = " ".join(page_texts.values())
        assert "Test Document for PyMuPDF" in all_text, "Should extract title"
        assert "Technical Specifications" in all_text, "Should extract section headers"
        assert "900.01" in all_text, "Should extract error codes"
        assert "PyMuPDF" in all_text, "Should preserve engine name"

        # Verify metadata (DocumentMetadata instance)
        assert metadata is not None, "Metadata should be returned"
        assert getattr(metadata, "page_count", 0) >= 1, "Should have at least one page"

    @pytest.mark.asyncio
    async def test_extract_text_with_pdfplumber(self, temp_test_pdf, processor_test_config):
        """Test text extraction using pdfplumber engine."""
        # Arrange
        extractor = TextExtractor(prefer_engine="pdfplumber")

        # Create test PDF content
        test_content = """Test Document for pdfplumber
================================

This is a test document to verify pdfplumber text extraction.
pdfplumber provides different text extraction capabilities.

Table Test:
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value A  | Value B  | Value C  |
| Value D  | Value E  | Value F  |

The table content should be preserved during extraction."""

        test_file = temp_test_pdf / "pdfplumber_test.pdf"
        test_file.write_text(test_content)

        # Act
        page_texts, metadata, structured_texts = await _run_extract(extractor, test_file)

        # Assert
        assert page_texts is not None, "Should return extraction result"
        assert isinstance(page_texts, dict), "Page texts should be a dictionary"
        assert len(page_texts) > 0, "Should extract text from at least one page"

        # Verify content extraction
        all_text = " ".join(page_texts.values())
        assert "Test Document for pdfplumber" in all_text, "Should extract title"
        assert "pdfplumber" in all_text, "Should preserve engine name"
        assert "Table Test" in all_text, "Should extract table content"
        assert "Value A" in all_text, "Should preserve table values"

    @pytest.mark.asyncio
    async def test_extract_text_multi_page_document(self, temp_test_pdf, processor_test_config):
        """Test text extraction from multi-page documents."""
        # Arrange
        extractor = TextExtractor(prefer_engine="pymupdf")

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

        # Act
        page_texts, metadata, structured_texts = await _run_extract(extractor, test_file)

        # Assert
        assert page_texts is not None, "Should return extraction result"
        assert isinstance(page_texts, dict), "Page texts should be a dictionary"
        assert len(page_texts) >= 1, "Should extract text from pages"

        # Verify page-specific content
        all_text = " ".join(page_texts.values())
        assert "Page 1" in all_text, "Should extract page 1 content"
        assert "Page 2" in all_text, "Should extract page 2 content"
        assert "Page 3" in all_text, "Should extract page 3 content"
        assert "Page 4" in all_text, "Should extract page 4 content"
        assert "900.01" in all_text, "Should preserve error codes"

        # Verify page count
        assert getattr(metadata, "page_count", 0) >= 1, "Should have correct page count"

    @pytest.mark.asyncio
    async def test_extract_text_with_special_characters(self, temp_test_pdf, processor_test_config):
        """Test text extraction with special characters and Unicode."""
        # Arrange
        extractor = TextExtractor(prefer_engine="pymupdf")

        # Content with special characters
        special_content = """Special Characters Test
========================

Unicode Characters:
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
₹ Rupee

International Characters:
Français: café, élève, naïve
Deutsch: Müller, Grüße, öffentlich
Español: niño, año, español
中文: 测试文档
日本語: テスト文書
Русский: тест документа"""

        test_file = temp_test_pdf / "special_chars_test.pdf"
        test_file.write_text(special_content)

        # Act
        page_texts, metadata, structured_texts = await _run_extract(extractor, test_file)

        # Assert
        assert page_texts is not None, "Should return extraction result"
        all_text = " ".join(page_texts.values())

        # Verify special characters are preserved (at least some)
        assert "©" in all_text or "Copyright" in all_text, "Should preserve copyright symbol"
        assert "°" in all_text or "Degree" in all_text, "Should preserve degree symbol"
        assert "€" in all_text or "Euro" in all_text, "Should preserve euro symbol"
        assert "Français" in all_text, "Should preserve French text"
        assert "Deutsch" in all_text, "Should preserve German text"
        assert "中文" in all_text, "Should preserve Chinese text"

    @pytest.mark.asyncio
    async def test_extract_text_with_tables(self, temp_test_pdf, processor_test_config):
        """Test text extraction from tabular content."""
        # Arrange
        extractor = TextExtractor(prefer_engine="pdfplumber")  # pdfplumber is better for tables

        # Table content
        table_content = """Error Code Reference Table
==========================

| Error Code | Description | Severity | Solution |
|------------|-------------|----------|----------|
| 900.01 | Fuser Unit Error | Critical | Check fuser assembly |
| 900.02 | Lamp Error | Warning | Replace exposure lamp |
| 900.03 | High Voltage Error | Critical | Check HV power supply |
| 920.00 | Waste Toner Full | Warning | Replace waste container |
| 921.00 | Low Toner Warning | Info | Replace toner cartridge |

Parts List Table:
| Part Number | Description | Price | Availability |
|-------------|-------------|-------|---------------|
| FM1-0011 | Fuser Unit | $450.00 | In Stock |
| FM1-0012 | Fuser Lamp | $120.00 | In Stock |
| DV1-0021 | Developer Unit | $180.00 | 2-3 Days |
| PF1-0031 | Pick-up Roller | $45.00 | In Stock |
"""

        test_file = temp_test_pdf / "table_extraction_test.pdf"
        test_file.write_text(table_content)

        # Act
        page_texts, metadata, structured_texts = await _run_extract(extractor, test_file)

        # Assert
        assert page_texts is not None, "Should return extraction result"
        all_text = " ".join(page_texts.values())

        # Verify table content is extracted
        assert "Error Code Reference Table" in all_text, "Should extract table title"
        assert "900.01" in all_text, "Should extract error codes from table"
        assert "Fuser Unit Error" in all_text, "Should extract descriptions from table"
        assert "Critical" in all_text, "Should extract severity from table"
        assert "Parts List Table" in all_text, "Should extract second table"
        assert "FM1-0011" in all_text, "Should extract part numbers"
        assert "$450.00" in all_text, "Should extract prices"

    @pytest.mark.asyncio
    async def test_extract_text_with_headers_and_footers(self, temp_test_pdf, processor_test_config):
        """Test text extraction with headers and footers."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Content with headers and footers
        header_footer_content = """Document Header: Test Manual - Page 1
==========================================

Main Content Section 1
======================

This is the main content of the document.
It should be extracted properly while headers and footers
might need special handling.

Technical Information:
- Device: Test Device Model X
- Serial: TEST123456
- Version: 2.1

Document Footer: © 2024 TestCorp - Confidential
=============================================="""

        test_file = temp_test_pdf / "header_footer_test.pdf"
        test_file.write_text(header_footer_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should return extraction result"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())

        # Verify content is extracted
        assert "Main Content Section 1" in all_text, "Should extract main content"
        assert "Technical Information" in all_text, "Should extract sections"
        assert "Test Device Model X" in all_text, "Should preserve technical details"
        assert "TEST123456" in all_text, "Should preserve serial numbers"

        # Headers and footers might be included or filtered depending on implementation
        # The important thing is that main content is preserved


class TestOCRFallback:
    """Test OCR fallback functionality."""

    @pytest.mark.asyncio
    async def test_ocr_fallback_when_no_text_extractable(self, temp_test_pdf, processor_test_config):
        """Test OCR fallback when no text can be extracted."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=True)

        # Create PDF-like file with no extractable text (simulated scanned PDF)
        scanned_pdf = temp_test_pdf / "scanned_document.pdf"
        scanned_pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")

        # Act
        result = await extractor.extract_text(scanned_pdf)

        # Assert
        # Should either succeed with OCR text or fail gracefully
        if result is not None:
            page_texts, metadata = result
            # OCR might not work in test environment, but should not crash
            assert isinstance(page_texts, dict), "Should return valid page_texts structure"
            assert isinstance(metadata, dict), "Should return valid metadata structure"
        else:
            # If OCR is not available, should handle gracefully
            pass  # Expected in test environment

    @pytest.mark.asyncio
    async def test_ocr_disabled_no_text(self, temp_test_pdf, processor_test_config):
        """Test behavior when OCR is disabled and no text is extractable."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=False)

        # Create PDF with no extractable text
        no_text_pdf = temp_test_pdf / "no_text_document.pdf"
        no_text_pdf.write_bytes(b"%PDF-1.4\n[Binary content with no text]\n")

        # Act
        result = await extractor.extract_text(no_text_pdf)

        # Assert
        # Should return None or raise appropriate error when OCR disabled
        assert result is None, "Should return None when no text and OCR disabled"

    @pytest.mark.asyncio
    async def test_ocr_with_image_content(self, temp_test_pdf, processor_test_config):
        """Test OCR with simulated image content."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=True)

        # Create PDF that simulates image-only content
        image_pdf = temp_test_pdf / "image_only_document.pdf"
        image_pdf.write_bytes(b"%PDF-1.4\n[Image data - no extractable text]\n")

        # Act
        result = await extractor.extract_text(image_pdf)

        # Assert
        # Should handle gracefully - either succeed with OCR or fail appropriately
        if result is not None:
            page_texts, metadata = result
            assert isinstance(page_texts, dict), "Should return valid structure"
        else:
            # OCR might not be available in test environment
            pass

    @pytest.mark.asyncio
    async def test_ocr_with_mixed_content(self, temp_test_pdf, processor_test_config):
        """Test OCR with mixed text and image content."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=True)

        # Create PDF with some text and some non-text content
        mixed_content = """This page has some extractable text.
[Binary image data that requires OCR]
More extractable text follows here."""

        mixed_pdf = temp_test_pdf / "mixed_content_document.pdf"
        mixed_pdf.write_text(mixed_content)

        # Act
        result = await extractor.extract_text(mixed_pdf)

        # Assert
        assert result is not None, "Should handle mixed content"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "extractable text" in all_text, "Should preserve extractable text"


class TestLanguageDetection:
    """Test language detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_english_language(self, temp_test_pdf, processor_test_config):
        """Test detection of English language."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        english_content = """English Language Test
========================

This document is written in English.
It contains technical information and specifications.
The language detection should identify this as English.

Error Code 900.01: Fuser Unit Error
Description: The fuser unit has failed to reach operating temperature.
Solution: Check the fuser lamp and thermal fuse.

This content should be detected as English language."""

        test_file = temp_test_pdf / "english_language_test.pdf"
        test_file.write_text(english_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should return extraction result"
        page_texts, metadata = result

        # Verify language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect language"
        assert detected_language.lower() in [
            "en",
            "english",
            "en-us",
        ], f"Should detect English, got {detected_language}"

    @pytest.mark.asyncio
    async def test_detect_german_language(self, temp_test_pdf, processor_test_config):
        """Test detection of German language."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        german_content = """Deutscher Sprachtest
=====================

Dieses Dokument ist in deutscher Sprache verfasst.
Es enthält technische Informationen und Spezifikationen.
Die Spracherkennung sollte dies als Deutsch identifizieren.

Fehlercode 900.01: Fixiereinheit-Fehler
Beschreibung: Die Fixiereinheit hat die Betriebstemperatur nicht erreicht.
Lösung: Überprüfen Sie die Fixierlampe und die thermische Sicherung.

Dieser Inhalt sollte als deutsche Sprache erkannt werden."""

        test_file = temp_test_pdf / "german_language_test.pdf"
        test_file.write_text(german_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should return extraction result"
        page_texts, metadata = result

        # Verify language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect language"
        assert detected_language.lower() in ["de", "german", "de-de"], f"Should detect German, got {detected_language}"

    @pytest.mark.asyncio
    async def test_detect_french_language(self, temp_test_pdf, processor_test_config):
        """Test detection of French language."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        french_content = """Test de Langue Française
==========================

Ce document est rédigé en français.
Il contient des informations techniques et des spécifications.
La détection de langue devrait identifier ceci comme français.

Code d'erreur 900.01 : Erreur d'unité de fusion
Description : L'unité de fusion n'a pas atteint la température de fonctionnement.
Solution : Vérifiez la lampe de fusion et le fusible thermique.

Ce contenu devrait être détecté comme langue française."""

        test_file = temp_test_pdf / "french_language_test.pdf"
        test_file.write_text(french_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should return extraction result"
        page_texts, metadata = result

        # Verify language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect language"
        assert detected_language.lower() in ["fr", "french", "fr-fr"], f"Should detect French, got {detected_language}"

    @pytest.mark.asyncio
    async def test_detect_multi_language_document(self, temp_test_pdf, processor_test_config):
        """Test language detection in multi-language documents."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        multi_lang_content = """Multi-Language Document
========================

English Section:
This section is written in English.
It contains technical information.

German Section:
Dieser Abschnitt ist in deutscher Sprache verfasst.
Er enthält technische Details.

French Section:
Cette section est rédigée en français.
Elle contient des informations techniques.

Spanish Section:
Esta sección está escrita en español.
Contiene información técnica.

The document should detect the primary language or handle multiple languages."""

        test_file = temp_test_pdf / "multi_language_test.pdf"
        test_file.write_text(multi_lang_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should return extraction result"
        page_texts, metadata = result

        # Verify language detection (might detect primary language)
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect some language"

        # Should preserve content from all languages
        all_text = " ".join(page_texts.values())
        assert "English Section" in all_text
        assert "German Section" in all_text
        assert "French Section" in all_text
        assert "Spanish Section" in all_text

    @pytest.mark.asyncio
    async def test_language_confidence_threshold(self, temp_test_pdf, processor_test_config):
        """Test language detection with confidence thresholds."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Very short content (low confidence scenario)
        short_content = "Test"

        test_file = temp_test_pdf / "short_content_test.pdf"
        test_file.write_text(short_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle short content"
        page_texts, metadata = result

        # Should still attempt language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect language even for short content"

    @pytest.mark.asyncio
    async def test_unknown_language_fallback(self, temp_test_pdf, processor_test_config):
        """Test fallback handling for unknown languages."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Random characters/noise
        unknown_content = "x1y2z3 a4b5c6 d7e8f9 g0h1i2 j3k4l5 m6n7o8"

        test_file = temp_test_pdf / "unknown_language_test.pdf"
        test_file.write_text(unknown_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle unknown language"
        page_texts, metadata = result

        # Should fallback to default language
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should have fallback language"
        # Default might be 'en' or 'unknown' depending on implementation


class TestErrorHandling:
    """Test error handling in TextExtractor."""

    @pytest.mark.asyncio
    async def test_non_existent_file_error(self, processor_test_config):
        """Test error handling for non-existent files."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")
        non_existent_file = Path("/non/existent/file.pdf")

        # Act
        result = await extractor.extract_text(non_existent_file)

        # Assert
        assert result is None, "Should return None for non-existent file"

    @pytest.mark.asyncio
    async def test_corrupted_pdf_error(self, temp_test_pdf, processor_test_config):
        """Test error handling for corrupted PDF files."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create corrupted PDF file
        corrupted_pdf = temp_test_pdf / "corrupted.pdf"
        corrupted_pdf.write_bytes(b"This is not a valid PDF file content\x00\x01\x02invalid")

        # Act
        result = await extractor.extract_text(corrupted_pdf)

        # Assert
        # Should handle gracefully - either return None or raise appropriate error
        if result is not None:
            page_texts, metadata = result
            # If it doesn't raise, should return empty or minimal result
            assert isinstance(page_texts, dict), "Should return valid structure even for corrupted PDF"
        else:
            # Most likely expected behavior
            pass

    @pytest.mark.asyncio
    async def test_empty_pdf_error(self, temp_test_pdf, processor_test_config):
        """Test error handling for empty PDF files."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create empty PDF file
        empty_pdf = temp_test_pdf / "empty.pdf"
        empty_pdf.write_bytes(b"")

        # Act
        result = await extractor.extract_text(empty_pdf)

        # Assert
        # Should handle empty files gracefully
        if result is not None:
            page_texts, metadata = result
            assert isinstance(page_texts, dict), "Should return valid structure for empty PDF"
            assert len(page_texts) == 0, "Empty PDF should have no pages"
            assert metadata.get("page_count", 0) == 0, "Empty PDF should have 0 pages"
        else:
            # Might return None for completely empty files
            pass

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self, temp_test_pdf, processor_test_config):
        """Test error handling for unsupported file types."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create non-PDF file
        text_file = temp_test_pdf / "not_a_pdf.txt"
        text_file.write_text("This is not a PDF file.")

        # Act
        result = await extractor.extract_text(text_file)

        # Assert
        # Should handle unsupported file types gracefully
        if result is not None:
            page_texts, metadata = result
            # Might attempt to process anyway or return error
            assert isinstance(page_texts, dict), "Should return valid structure"
        else:
            # Most likely expected for unsupported file types
            pass

    @pytest.mark.asyncio
    async def test_permission_denied_error(self, processor_test_config):
        """Test error handling for permission denied errors."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create a file path that would likely cause permission error
        # (This is a simulated test - actual permission errors depend on system)
        restricted_file = Path("/root/restricted.pdf")

        # Act
        result = await extractor.extract_text(restricted_file)

        # Assert
        # Should handle permission errors gracefully
        if result is None:
            pass  # Expected for permission errors
        else:
            # If it doesn't raise, should handle appropriately
            assert isinstance(result, tuple), "Should return valid structure"

    @pytest.mark.asyncio
    async def test_engine_failure_fallback(self, temp_test_pdf, processor_test_config):
        """Test fallback when primary PDF engine fails."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create test file
        test_file = temp_test_pdf / "engine_failure_test.pdf"
        test_file.write_text("Test content for engine failure.")

        # Mock primary engine to fail
        with patch("fitz.open") as mock_fitz:
            mock_fitz.side_effect = Exception("PyMuPDF failed")

            # Act
            result = await extractor.extract_text(test_file)

            # Assert
            # Should either fallback to alternative engine or handle gracefully
            if result is not None:
                page_texts, metadata = result
                assert isinstance(page_texts, dict), "Should return valid structure on engine failure"
            else:
                # Might return None if no fallback available
                pass

    @pytest.mark.asyncio
    async def test_partial_extraction_failure(self, temp_test_pdf, processor_test_config):
        """Test handling of partial extraction failures."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create multi-page content
        multi_page_content = """Page 1: This is the first page.
It should extract successfully.

Page 2: This is the second page.
It might fail during extraction.

Page 3: This is the third page.
It should also extract successfully."""

        test_file = temp_test_pdf / "partial_failure_test.pdf"
        test_file.write_text(multi_page_content)

        # Mock partial failure
        with patch("fitz.open") as mock_fitz:
            # Create mock document that fails on page 2
            mock_doc = MagicMock()
            mock_page1 = MagicMock()
            mock_page1.get_text.return_value = "Page 1: This is the first page.\nIt should extract successfully."
            mock_page2 = MagicMock()
            mock_page2.get_text.side_effect = Exception("Page extraction failed")
            mock_page3 = MagicMock()
            mock_page3.get_text.return_value = "Page 3: This is the third page.\nIt should also extract successfully."

            mock_doc.__len__.return_value = 3
            mock_doc.__getitem__.side_effect = [mock_page1, mock_page2, mock_page3]
            mock_fitz.return_value = mock_doc

            # Act
            result = await extractor.extract_text(test_file)

            # Assert
            # Should handle partial failures gracefully
            if result is not None:
                page_texts, metadata = result
                # Should have extracted at least some pages
                assert len(page_texts) >= 1, "Should extract at least some pages"
                # Page 1 and 3 should be available, page 2 might be missing
                assert 1 in page_texts, "Page 1 should be extracted"
                assert 3 in page_texts, "Page 3 should be extracted"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_large_document(self, temp_test_pdf, processor_test_config):
        """Test handling of very large documents."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create large content (simulating large PDF)
        large_content = " ".join([f"Large document sentence {i}." for i in range(1000)])

        test_file = temp_test_pdf / "large_document_test.pdf"
        test_file.write_text(large_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle large documents"
        page_texts, metadata = result

        # Should extract content
        assert len(page_texts) > 0, "Should extract text from large document"

        all_text = " ".join(page_texts.values())
        assert "Large document sentence 0" in all_text, "Should preserve start of content"
        assert "Large document sentence 999" in all_text, "Should preserve end of content"

    @pytest.mark.asyncio
    async def test_document_with_only_whitespace(self, temp_test_pdf, processor_test_config):
        """Test handling of documents with only whitespace."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create document with only whitespace
        whitespace_content = """









   """

        test_file = temp_test_pdf / "whitespace_only_test.pdf"
        test_file.write_text(whitespace_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle whitespace-only documents"
        page_texts, metadata = result

        # Should handle gracefully
        assert isinstance(page_texts, dict), "Should return valid structure"

    @pytest.mark.asyncio
    async def test_document_with_unicode_filename(self, temp_test_pdf, processor_test_config):
        """Test handling of documents with Unicode filenames."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create file with Unicode filename
        unicode_filename = "tëst_döcümënt_中文.pdf"
        test_content = "Test content with Unicode filename."

        test_file = temp_test_pdf / unicode_filename
        test_file.write_text(test_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle Unicode filenames"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "Test content with Unicode filename" in all_text, "Should extract content despite Unicode filename"

    @pytest.mark.asyncio
    async def test_document_with_embedded_images(self, temp_test_pdf, processor_test_config):
        """Test handling of documents with embedded images."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create content that simulates embedded images
        image_content = """Document with Embedded Images
================================

[Image: Technical Diagram]
This section contains an embedded technical diagram.
The diagram shows the internal components of the device.

Text continues here after the image.

[Image: Flow Chart]
This section contains an embedded flow chart.
The flow chart illustrates the operational sequence.

More text follows the second image."""

        test_file = temp_test_pdf / "embedded_images_test.pdf"
        test_file.write_text(image_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle documents with embedded images"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "Document with Embedded Images" in all_text, "Should extract text content"
        assert "Technical Diagram" in all_text, "Should preserve image descriptions"
        assert "Flow Chart" in all_text, "Should preserve image descriptions"
        assert "Text continues here" in all_text, "Should preserve text between images"

    @pytest.mark.asyncio
    async def test_document_with_hyperlinks(self, temp_test_pdf, processor_test_config):
        """Test handling of documents with hyperlinks."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create content with hyperlinks
        link_content = """Document with Hyperlinks
========================

Visit our website: https://www.example.com
Technical support: support@example.com
Documentation: https://docs.example.com/manual

Related Links:
- User Guide: https://docs.example.com/user_guide
- API Reference: https://docs.example.com/api
- Contact: https://www.example.com/contact

Email addresses:
support@example.com
sales@example.com
info@example.com"""

        test_file = temp_test_pdf / "hyperlinks_test.pdf"
        test_file.write_text(link_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle documents with hyperlinks"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "https://www.example.com" in all_text, "Should preserve URLs"
        assert "support@example.com" in all_text, "Should preserve email addresses"
        assert "User Guide" in all_text, "Should preserve link text"

    @pytest.mark.asyncio
    async def test_document_with_form_fields(self, temp_test_pdf, processor_test_config):
        """Test handling of documents with form fields."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create content that simulates form fields
        form_content = """Document with Form Fields
==========================

User Information:
Name: _________________
Email: _________________
Phone: _________________

Service Request:
Device Model: _________________
Serial Number: _________________
Problem Description: _________________________
_________________________
_________________________

Priority: [ ] Low [ ] Medium [ ] High

Additional Comments:
_________________________________
_________________________________
_________________________________"""

        test_file = temp_test_pdf / "form_fields_test.pdf"
        test_file.write_text(form_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle documents with form fields"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "User Information" in all_text, "Should extract form labels"
        assert "Name:" in all_text, "Should preserve field labels"
        assert "Service Request" in all_text, "Should preserve section headers"
        assert "Priority:" in all_text, "Should preserve checkbox labels"


class TestConfiguration:
    """Test configuration options of TextExtractor."""

    @pytest.mark.asyncio
    async def test_pdf_engine_selection(self, temp_test_pdf, processor_test_config):
        """Test different PDF engine selection."""
        # Arrange
        test_content = "Test content for engine selection."
        test_file = temp_test_pdf / "engine_selection_test.pdf"
        test_file.write_text(test_content)

        engines = ["pymupdf", "pdfplumber"]

        for engine in engines:
            # Act
            extractor = TextExtractor(pdf_engine=engine)
            result = await extractor.extract_text(test_file)

            # Assert
            assert result is not None, f"Engine {engine} should work"
            page_texts, metadata = result
            assert isinstance(page_texts, dict), f"Engine {engine} should return valid page_texts"
            assert len(page_texts) > 0, f"Engine {engine} should extract text"

    @pytest.mark.asyncio
    async def test_ocr_configuration(self, temp_test_pdf, processor_test_config):
        """Test OCR configuration options."""
        # Arrange
        # Create PDF that might need OCR
        ocr_test_file = temp_test_pdf / "ocr_config_test.pdf"
        ocr_test_file.write_bytes(b"%PDF-1.4\n[Content requiring OCR]\n")

        # Test with OCR enabled
        extractor_with_ocr = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=True)

        # Test with OCR disabled
        extractor_without_ocr = TextExtractor(pdf_engine="pymupdf", enable_ocr_fallback=False)

        # Act
        result_with_ocr = await extractor_with_ocr.extract_text(ocr_test_file)
        result_without_ocr = await extractor_without_ocr.extract_text(ocr_test_file)

        # Assert
        # Both should handle gracefully (OCR might not be available in test environment)
        if result_with_ocr is not None:
            page_texts, metadata = result_with_ocr
            assert isinstance(page_texts, dict), "OCR enabled should return valid structure"

        if result_without_ocr is not None:
            page_texts, metadata = result_without_ocr
            assert isinstance(page_texts, dict), "OCR disabled should return valid structure"

    @pytest.mark.asyncio
    async def test_language_detection_configuration(self, temp_test_pdf, processor_test_config):
        """Test language detection configuration."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create multilingual content
        multi_lang_content = """English: This is English content.
Deutsch: Dies ist deutsche Inhalt.
Français: Ceci est le contenu français."""

        test_file = temp_test_pdf / "lang_detection_config_test.pdf"
        test_file.write_text(multi_lang_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should extract text with language detection"
        page_texts, metadata = result

        # Should attempt language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect language"

    @pytest.mark.asyncio
    async def test_custom_processing_options(self, temp_test_pdf, processor_test_config):
        """Test custom processing options."""
        # Arrange
        extractor = TextExtractor(pdf_engine="pymupdf")

        # Create content with various elements
        complex_content = """Complex Document
================

# Header 1
Content under header 1.

## Header 2
Content under header 2.

Table:
| Column 1 | Column 2 |
|----------|----------|
| Value A  | Value B  |

List:
- Item 1
- Item 2
- Item 3

Code block:
def function():
    return "test"

End of document."""

        test_file = temp_test_pdf / "custom_options_test.pdf"
        test_file.write_text(complex_content)

        # Act
        result = await extractor.extract_text(test_file)

        # Assert
        assert result is not None, "Should handle complex documents"
        page_texts, metadata = result

        all_text = " ".join(page_texts.values())
        assert "Complex Document" in all_text, "Should preserve headers"
        assert "Value A" in all_text, "Should preserve table content"
        assert "Item 1" in all_text, "Should preserve list content"
        assert "function()" in all_text, "Should preserve code blocks"


# Parameterized tests for different content types
@pytest.mark.parametrize(
    "content_type,test_content,expected_elements",
    [
        (
            "technical_manual",
            """Technical Manual
================

Error Codes:
900.01: Fuser Unit Error
900.02: Lamp Error

Specifications:
- Speed: 75 ppm
- Resolution: 1200 dpi""",
            ["Error Codes", "900.01", "Specifications", "75 ppm"],
        ),
        (
            "user_guide",
            """User Guide
===========

Getting Started:
1. Unpack device
2. Connect power
3. Install software

Basic Operations:
- Making copies
- Scanning documents
- Printing""",
            ["Getting Started", "Unpack device", "Basic Operations", "Making copies"],
        ),
        (
            "parts_catalog",
            """Parts Catalog
=============

Part Number | Description | Price
-----------|-------------|------
FM1-0011 | Fuser Unit | $450.00
FM1-0012 | Fuser Lamp | $120.00

Ordering Information:
Call: 1-800-PARTS
Website: parts.example.com""",
            ["Parts Catalog", "FM1-0011", "Fuser Unit", "$450.00", "Ordering Information"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_content_type_extraction(
    temp_test_pdf, processor_test_config, content_type, test_content, expected_elements
):
    """Test extraction of different content types."""
    # Arrange
    extractor = TextExtractor(pdf_engine="pymupdf")

    test_file = temp_test_pdf / f"{content_type}_test.pdf"
    test_file.write_text(test_content)

    # Act
    result = await extractor.extract_text(test_file)

    # Assert
    assert result is not None, f"Should extract {content_type} content"
    page_texts, metadata = result

    all_text = " ".join(page_texts.values())

    # Verify expected elements are preserved
    for element in expected_elements:
        assert element in all_text, f"Should preserve '{element}' in {content_type}"

    # Verify metadata
    assert isinstance(metadata, dict), "Should return metadata"
    assert "page_count" in metadata, "Should include page count"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
