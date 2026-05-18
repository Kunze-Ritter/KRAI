"""
Comprehensive E2E Tests for DocumentProcessor

This module provides extensive end-to-end testing for the DocumentProcessor component,
focusing on text extraction, language detection, manufacturer detection, and
document type classification with comprehensive error handling and edge cases.

Test Categories:
1. Text Extraction Tests
2. Language Detection Tests
3. Manufacturer Detection Tests
4. Document Type Classification Tests
5. Error Handling Tests
6. Integration Tests

All tests use the fixtures from conftest.py for consistent mock objects and test data.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.document_processor import DocumentProcessor

pytestmark = [
    pytest.mark.processor,
    pytest.mark.skip(
        reason="DocumentProcessor is deprecated and replaced by the new pipeline; legacy E2E tests are disabled.",
    ),
]


class TestDocumentTextExtraction:
    """Test text extraction functionality of DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_basic_text_extraction(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test successful text extraction with PyMuPDF."""
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
        assert result.success, f"Text extraction should succeed: {result.error}"
        assert result.data is not None
        assert "page_texts" in result.data
        assert "metadata" in result.data

        page_texts = result.data["page_texts"]
        assert isinstance(page_texts, dict)
        assert len(page_texts) > 0, "Should extract text from at least one page"

        # Verify page text structure
        for page_num, text in page_texts.items():
            assert isinstance(page_num, int), "Page numbers should be integers"
            assert isinstance(text, str), "Page text should be strings"
            assert len(text.strip()) > 0, "Page text should not be empty"

    @pytest.mark.asyncio
    async def test_text_extraction_with_pdfplumber_fallback(
        self, mock_database_adapter, sample_pdf_files, processor_test_config
    ):
        """Test fallback to pdfplumber when PyMuPDF fails."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine="pdfplumber",  # Force pdfplumber usage
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, f"pdfplumber extraction should succeed: {result.error}"
        assert "page_texts" in result.data
        assert len(result.data["page_texts"]) > 0

    @pytest.mark.asyncio
    async def test_ocr_fallback_for_scanned_pdf(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test OCR fallback for scanned PDFs with no extractable text."""
        # Arrange
        processor = DocumentProcessor(database_adapter=mock_database_adapter, enable_ocr_fallback=True)
        ocr_pdf = sample_pdf_files["ocr_required_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=ocr_pdf["path"], metadata={"filename": ocr_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        # Should either succeed with OCR text or fail gracefully
        if result.success:
            assert "page_texts" in result.data
            # OCR might not work in test environment, so we just check it doesn't crash
        else:
            # Should fail gracefully with appropriate error
            assert "ocr" in result.error.lower() or "text" in result.error.lower()

    @pytest.mark.asyncio
    async def test_multi_page_text_extraction(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test text extraction from multi-page documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Create multi-page content
        multi_page_content = """Page 1: This is the first page of the document.
It contains important technical information.

Page 2: This is the second page.
It continues with more technical details.

Page 3: This is the third page.
It concludes the document."""

        test_file = temp_test_pdf / "multi_page.pdf"
        test_file.write_text(multi_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Multi-page extraction should succeed"
        page_texts = result.data["page_texts"]
        assert len(page_texts) >= 1, "Should extract text from pages"

        # Verify content is distributed across pages
        all_text = " ".join(page_texts.values())
        assert "Page 1" in all_text
        assert "Page 2" in all_text
        assert "Page 3" in all_text

    @pytest.mark.asyncio
    async def test_text_extraction_with_special_characters(
        self, mock_database_adapter, temp_test_pdf, processor_test_config
    ):
        """Test text extraction with special characters and Unicode."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content with special characters
        special_content = """Special Characters Test:
• Bullet points
© Copyright symbol
® Registered trademark
™ Trademark
° Degrees
± Plus-minus
× Multiplication
÷ Division
€ Euro symbol
£ Pound symbol
¥ Yen symbol
Unicode: ßáéíóúñç中文"""

        test_file = temp_test_pdf / "special_chars.pdf"
        test_file.write_text(special_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Special character extraction should succeed"
        page_texts = result.data["page_texts"]
        all_text = " ".join(page_texts.values())

        # Verify special characters are preserved (at least some)
        assert "©" in all_text or "copyright" in all_text.lower()
        assert "°" in all_text or "degrees" in all_text.lower()

    @pytest.mark.asyncio
    async def test_text_extraction_with_tables(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test text extraction from tabular content."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Table-like content
        table_content = """Service Manual - Error Codes

| Code | Description | Severity |
|------|-------------|----------|
| 900.01 | Fuser Unit Error | Critical |
| 900.02 | Lamp Error | Warning |
| 900.03 | Temperature Error | Critical |

Table 2: Maintenance Schedule
| Interval | Task | Parts Required |
|----------|------|----------------|
| Monthly | Clean Rollers | Cleaning Kit |
| Quarterly | Replace Toner | Toner Cartridge |
| Annually | Service Check | Technician"""

        test_file = temp_test_pdf / "table_content.pdf"
        test_file.write_text(table_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Table content extraction should succeed"
        page_texts = result.data["page_texts"]
        all_text = " ".join(page_texts.values())

        # Verify table content is extracted
        assert "900.01" in all_text
        assert "Fuser Unit Error" in all_text
        assert "Maintenance Schedule" in all_text


class TestDocumentLanguageDetection:
    """Test language detection functionality of DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_english_language_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test detection of English language content."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        english_content = """Service Manual - English

This document contains technical information in English.
It includes error codes, troubleshooting procedures,
and maintenance instructions for office equipment.

Error Code 900.01: Fuser Unit Error
Description: The fuser unit has failed to reach operating temperature.
Solution: Check the fuser lamp and thermal fuse."""

        test_file = temp_test_pdf / "english_manual.pdf"
        test_file.write_text(english_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "English document processing should succeed"
        metadata = result.data.get("metadata", {})

        # Language should be detected as English
        detected_language = metadata.get("language")
        assert detected_language in ["en", "english", "en-US"], f"Expected English, got {detected_language}"

    @pytest.mark.asyncio
    async def test_german_language_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test detection of German language content."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        german_content = """Servicehandbuch - Deutsch

Dieses Dokument enthält technische Informationen in deutscher Sprache.
Es umfasst Fehlercodes, Fehlerbehebungsverfahren
und Wartungsanweisungen für Büroequipment.

Fehlercode 900.01: Fixiereinheit-Fehler
Beschreibung: Die Fixiereinheit hat die Betriebstemperatur nicht erreicht.
Lösung: Überprüfen Sie die Fixierlampe und die thermische Sicherung."""

        test_file = temp_test_pdf / "german_manual.pdf"
        test_file.write_text(german_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "German document processing should succeed"
        metadata = result.data.get("metadata", {})

        # Language should be detected as German
        detected_language = metadata.get("language")
        assert detected_language in ["de", "german", "de-DE"], f"Expected German, got {detected_language}"

    @pytest.mark.asyncio
    async def test_multi_language_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test language detection in multi-language documents."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        multi_lang_content = """Service Manual - Multi Language

English Section:
This document provides technical information.
Error code 900.01 indicates a fuser unit problem.

German Section:
Dieses Dokument enthält technische Informationen.
Fehlercode 900.01 deutet auf ein Problem mit der Fixiereinheit hin.

French Section:
Ce document fournit des informations techniques.
Le code d'erreur 900.01 indique un problème d'unité de fusion."""

        test_file = temp_test_pdf / "multi_lang_manual.pdf"
        test_file.write_text(multi_lang_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Multi-language document processing should succeed"
        metadata = result.data.get("metadata", {})

        # Should detect some language (might be primary language)
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should detect some language"

    @pytest.mark.asyncio
    async def test_language_confidence_threshold(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test language detection confidence thresholds."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Very short text (low confidence scenario)
        short_content = "Test"

        test_file = temp_test_pdf / "short_text.pdf"
        test_file.write_text(short_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Short text processing should succeed"
        metadata = result.data.get("metadata", {})

        # Should still attempt language detection
        detected_language = metadata.get("language")
        assert detected_language is not None, "Should still detect language for short text"

    @pytest.mark.asyncio
    async def test_unknown_language_fallback(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test fallback handling for unknown languages."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Random characters/noise
        unknown_content = "x1y2z3 a4b5c6 d7e8f9 g0h1i2"

        test_file = temp_test_pdf / "unknown_lang.pdf"
        test_file.write_text(unknown_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Unknown language processing should succeed"
        metadata = result.data.get("metadata", {})

        # Should fallback to default language
        detected_language = metadata.get("language")
        assert detected_language in ["en", "unknown", None], f"Should fallback to default, got {detected_language}"


class TestDocumentManufacturerDetection:
    """Test manufacturer detection functionality of DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_auto_manufacturer_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test automatic manufacturer detection from content."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content with manufacturer information
        manufacturer_content = """Konica Minolta C750i Service Manual

This service manual is for the Konica Minolta C750i digital copier.
Manufacturer: Konica Minolta
Model: C750i
Serial Number: KL123456

Technical Specifications:
- Print Speed: 75 ppm
- Resolution: 1200 x 1200 dpi
- Manufacturer: Konica Minolta"""

        test_file = temp_test_pdf / "konica_manual.pdf"
        test_file.write_text(manufacturer_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Manufacturer detection should succeed"
        metadata = result.data.get("metadata", {})

        # Should detect Konica Minolta
        detected_manufacturer = metadata.get("manufacturer")
        assert detected_manufacturer is not None, "Should detect manufacturer"
        assert "konica" in detected_manufacturer.lower() or "minolta" in detected_manufacturer.lower()

    @pytest.mark.asyncio
    async def test_manufacturer_from_filename(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test manufacturer detection from filename."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Filename with manufacturer
        filename = "HP_LaserJet_Pro_M404n_Service_Manual.pdf"
        test_file = temp_test_pdf / filename
        test_file.write_text("Generic service manual content")

        context = ProcessingContext(document_id="test-doc-id", file_path=test_file, metadata={"filename": filename})

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Filename-based manufacturer detection should succeed"
        metadata = result.data.get("metadata", {})

        # Should detect HP from filename
        detected_manufacturer = metadata.get("manufacturer")
        assert detected_manufacturer is not None, "Should detect manufacturer from filename"
        assert "hp" in detected_manufacturer.lower()

    @pytest.mark.asyncio
    async def test_manufacturer_from_title(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test manufacturer detection from document title."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content with manufacturer in title
        title_content = """Canon imageRUNNER ADVANCE C7550i Service Manual
========================================================

This document provides service procedures for Canon equipment.
Technical specifications and troubleshooting guides included."""

        test_file = temp_test_pdf / "canon_manual.pdf"
        test_file.write_text(title_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Title-based manufacturer detection should succeed"
        metadata = result.data.get("metadata", {})

        # Should detect Canon from title
        detected_manufacturer = metadata.get("manufacturer")
        assert detected_manufacturer is not None, "Should detect manufacturer from title"
        assert "canon" in detected_manufacturer.lower()

    @pytest.mark.asyncio
    async def test_manufacturer_normalization(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test manufacturer name normalization."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Various manufacturer name formats
        test_cases = [
            ("Brother MFC-L8900CDW Manual.pdf", "brother"),
            ("Xerox WorkCentre 6515.pdf", "xerox"),
            ("RICOH MP 5055 Service.pdf", "ricoh"),
            ("Kyocera TASKalfa 2552ci.pdf", "kyocera"),
            ("Sharp MX-3071V Manual.pdf", "sharp"),
        ]

        for filename, expected_manufacturer in test_cases:
            test_file = temp_test_pdf / filename
            test_file.write_text(f"Service manual for {expected_manufacturer}")

            context = ProcessingContext(
                document_id=f"test-doc-{expected_manufacturer}", file_path=test_file, metadata={"filename": filename}
            )

            # Act
            result = await processor.process(context)

            # Assert
            assert result.success, f"Should process {filename}"
            metadata = result.data.get("metadata", {})
            detected_manufacturer = metadata.get("manufacturer")

            assert detected_manufacturer is not None, f"Should detect manufacturer for {filename}"
            assert (
                expected_manufacturer in detected_manufacturer.lower()
            ), f"Expected {expected_manufacturer} in {detected_manufacturer}"

    @pytest.mark.asyncio
    async def test_manual_manufacturer_override(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test manual manufacturer override in context metadata."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Generic content
        generic_content = "This is a generic service manual."
        test_file = temp_test_pdf / "generic_manual.pdf"
        test_file.write_text(generic_content)

        # Context with manual manufacturer override
        context = ProcessingContext(
            document_id="test-doc-id",
            file_path=test_file,
            metadata={"filename": test_file.name, "manufacturer": "Custom Manufacturer"},  # Manual override
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Manual manufacturer override should succeed"
        metadata = result.data.get("metadata", {})

        # Should use manual override
        detected_manufacturer = metadata.get("manufacturer")
        assert (
            detected_manufacturer == "Custom Manufacturer"
        ), f"Should use manual override, got {detected_manufacturer}"


class TestDocumentTypeClassification:
    """Test document type classification functionality of DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_service_manual_classification(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test classification as Service Manual."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        service_manual_content = """Service Manual
================

Table of Contents:
1. Safety Precautions
2. Technical Specifications
3. Installation Procedures
4. Maintenance Operations
5. Troubleshooting Guide
6. Error Codes
7. Parts Catalog
8. Wiring Diagrams

This service manual provides detailed technical information
for service technicians and maintenance personnel."""

        test_file = temp_test_pdf / "service_manual.pdf"
        test_file.write_text(service_manual_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Service manual classification should succeed"
        metadata = result.data.get("metadata", {})

        # Should classify as service manual
        document_type = metadata.get("document_type")
        assert document_type in ["service_manual", "manual"], f"Expected service_manual, got {document_type}"

    @pytest.mark.asyncio
    async def test_parts_catalog_classification(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test classification as Parts Catalog."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        parts_catalog_content = """Parts Catalog
==============

Part Number | Description | Price
-----------|-------------|-------
A03U       | Fuser Unit  | $450.00
A04V       | Transfer Belt | $120.00
B12K       | Toner Cartridge Black | $85.00
C45M       | Drum Unit | $220.00
D67Y       | Developer Unit | $180.00

Exploded Views:
- Figure 1: Main Assembly
- Figure 2: Paper Path Assembly
- Figure 3: Fuser Assembly

Ordering Information:
Contact Customer Service for part availability."""

        test_file = temp_test_pdf / "parts_catalog.pdf"
        test_file.write_text(parts_catalog_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Parts catalog classification should succeed"
        metadata = result.data.get("metadata", {})

        # Should classify as parts catalog
        document_type = metadata.get("document_type")
        assert document_type in ["parts_catalog", "catalog"], f"Expected parts_catalog, got {document_type}"

    @pytest.mark.asyncio
    async def test_user_guide_classification(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test classification as User Guide."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        user_guide_content = """User Guide
==========

Getting Started:
- Unpacking the Device
- Connecting Power
- Loading Paper
- Installing Toner

Basic Operations:
- Making Copies
- Scanning Documents
- Printing from Computer
- Setting Up Fax

Advanced Features:
- Network Configuration
- Mobile Printing
- Cloud Services
- Security Settings

Troubleshooting:
- Paper Jams
- Print Quality Issues
- Error Messages
- Contact Support

For more information, visit our website."""

        test_file = temp_test_pdf / "user_guide.pdf"
        test_file.write_text(user_guide_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "User guide classification should succeed"
        metadata = result.data.get("metadata", {})

        # Should classify as user guide
        document_type = metadata.get("document_type")
        assert document_type in ["user_guide", "guide", "manual"], f"Expected user_guide, got {document_type}"

    @pytest.mark.asyncio
    async def test_troubleshooting_classification(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test classification as Troubleshooting Guide."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        troubleshooting_content = """Troubleshooting Guide
====================

Common Problems and Solutions:

Error Code 900.01: Fuser Unit Error
Symptoms: Machine stops with error 900.01
Causes: Fuser lamp failure, thermal fuse blown
Solutions:
1. Power cycle the machine
2. Check fuser lamp continuity
3. Replace thermal fuse if needed
4. Replace fuser unit

Error Code 900.02: Lamp Error
Symptoms: Print quality issues, blank pages
Causes: Lamp failure, power supply issue
Solutions:
1. Check lamp connections
2. Test power supply output
3. Replace exposure lamp

Paper Jam Problems:
- Jam at Input Tray: Check paper alignment
- Jam in Fuser: Clean fuser entrance
- Jam at Output: Check output path

Performance Issues:
- Slow Printing: Check network connection
- Poor Quality: Clean drum and corona wire"""

        test_file = temp_test_pdf / "troubleshooting.pdf"
        test_file.write_text(troubleshooting_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Troubleshooting classification should succeed"
        metadata = result.data.get("metadata", {})

        # Should classify as troubleshooting
        document_type = metadata.get("document_type")
        assert document_type in [
            "troubleshooting",
            "error_codes",
            "guide",
        ], f"Expected troubleshooting, got {document_type}"


class TestDocumentErrorHandling:
    """Test error handling in DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_missing_file_error(self, mock_database_adapter, processor_test_config):
        """Test error handling for missing files."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        non_existent_path = Path("/non/existent/document.pdf")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=non_existent_path, metadata={"filename": non_existent_path.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "Should fail for missing file"
        assert "not found" in result.error.lower() or "exist" in result.error.lower()

    @pytest.mark.asyncio
    async def test_corrupted_pdf_error(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test error handling for corrupted PDF files."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )
        corrupted_pdf = sample_pdf_files["corrupted_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id",
            file_path=corrupted_pdf["path"],
            metadata={"filename": corrupted_pdf["path"].name},
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert not result.success, "Should fail for corrupted PDF"
        assert "corrupted" in result.error.lower() or "invalid" in result.error.lower() or "pdf" in result.error.lower()

    @pytest.mark.asyncio
    async def test_extraction_failure_recovery(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test recovery from text extraction failures."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        test_file = temp_test_pdf / "test.pdf"
        test_file.write_text("Test content")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Mock text extraction to fail
        with patch.object(processor.text_extractor, "extract_text") as mock_extract:
            mock_extract.side_effect = Exception("Extraction failed")

            # Act
            result = await processor.process(context)

            # Assert
            assert not result.success, "Should fail when extraction fails"
            assert "extraction" in result.error.lower()

    @pytest.mark.asyncio
    async def test_partial_page_failure(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test continuation when individual pages fail to extract."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        test_file = temp_test_pdf / "multi_page.pdf"
        test_file.write_text("Page 1 content\nPage 2 content\nPage 3 content")

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Mock partial failure - some pages succeed, others fail
        original_extract = processor.text_extractor.extract_text

        async def mock_extract_with_failure(file_path):
            result = await original_extract(file_path)
            # Simulate failure on page 2
            if result and 2 in result[0]:  # page_texts
                result[0][2] = ""  # Empty text for page 2
            return result

        with patch.object(processor.text_extractor, "extract_text", side_effect=mock_extract_with_failure):
            # Act
            result = await processor.process(context)

            # Assert
            # Should succeed despite partial failure
            assert result.success, "Should succeed with partial page failure"
            page_texts = result.data.get("page_texts", {})
            assert len(page_texts) >= 1, "Should have at least some pages"


class TestDocumentIntegration:
    """Test integration scenarios for DocumentProcessor."""

    @pytest.mark.asyncio
    async def test_full_document_processing_flow(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test complete document processing flow."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Comprehensive test content
        full_content = """Konica Minolta C750i Service Manual
=====================================

Document Information:
- Manufacturer: Konica Minolta
- Model: C750i
- Document Type: Service Manual
- Language: English

Table of Contents:
1. Safety Information
2. Technical Specifications
3. Installation Procedures
4. Maintenance Operations
5. Error Code Troubleshooting

Error Codes:
900.01: Fuser unit temperature error
900.02: Exposure lamp failure
900.03: Development unit failure

Technical Specifications:
- Print Speed: 75 pages per minute
- Resolution: 1200 x 1200 dpi
- Memory: 2GB standard
- Paper Capacity: 1,150 sheets maximum

Maintenance Procedures:
- Daily: Clean platen glass
- Weekly: Check waste toner container
- Monthly: Clean transfer roller
- Quarterly: Replace maintenance kit"""

        test_file = temp_test_pdf / "full_test_manual.pdf"
        test_file.write_text(full_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Full processing flow should succeed"

        # Verify all components are present
        assert "page_texts" in result.data, "Should have page texts"
        assert "metadata" in result.data, "Should have metadata"

        page_texts = result.data["page_texts"]
        metadata = result.data["metadata"]

        # Verify text extraction
        assert len(page_texts) > 0, "Should extract text"
        all_text = " ".join(page_texts.values())
        assert "Konica Minolta" in all_text, "Should contain manufacturer"
        assert "C750i" in all_text, "Should contain model"
        assert "900.01" in all_text, "Should contain error codes"

        # Verify metadata extraction
        assert metadata.get("manufacturer") is not None, "Should detect manufacturer"
        assert metadata.get("language") is not None, "Should detect language"
        assert metadata.get("document_type") is not None, "Should detect document type"

        # Verify manufacturer detection
        manufacturer = metadata.get("manufacturer", "").lower()
        assert (
            "konica" in manufacturer or "minolta" in manufacturer
        ), f"Should detect Konica Minolta, got {manufacturer}"

        # Verify language detection
        language = metadata.get("language", "").lower()
        assert language in ["en", "english"], f"Should detect English, got {language}"

        # Verify document type detection
        doc_type = metadata.get("document_type", "").lower()
        assert "manual" in doc_type or "service" in doc_type, f"Should detect service manual, got {doc_type}"

    @pytest.mark.asyncio
    async def test_document_with_images_and_text(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing documents with both images and text."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content that simulates text with image placeholders
        mixed_content = """Service Manual with Images
============================

[Diagram: Machine Front Panel]
The front panel includes:
- Display screen
- Control buttons
- Card slots

[Image: Internal Components]
Internal components shown above include:
1. Fuser unit (A)
2. Transfer belt (B)
3. Development unit (C)

[Flowchart: Startup Sequence]
1. Power on
2. Self-test
3. Warm-up
4. Ready state

Text continues here with detailed explanations..."""

        test_file = temp_test_pdf / "mixed_content.pdf"
        test_file.write_text(mixed_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Mixed content processing should succeed"
        page_texts = result.data["page_texts"]
        all_text = " ".join(page_texts.values())

        # Should extract text even with image placeholders
        assert "front panel" in all_text.lower()
        assert "internal components" in all_text.lower()
        assert "startup sequence" in all_text.lower()

    @pytest.mark.asyncio
    async def test_document_with_links(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing documents with hyperlinks."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content with links
        linked_content = """Service Manual with Links
==========================

For more information, visit:
- Manufacturer website: https://www.konicaminolta.com
- Support portal: https://support.konicaminolta.com
- Parts ordering: https://parts.konicaminolta.com

Related Documents:
- [User Guide](user_guide.pdf)
- [Quick Start Guide](quick_start.pdf)
- [Technical Specifications](specs.pdf)

Contact Information:
Email: support@konicaminolta.com
Phone: 1-800-555-0123
Website: www.konicaminolta.com/support"""

        test_file = temp_test_pdf / "linked_document.pdf"
        test_file.write_text(linked_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Linked document processing should succeed"
        page_texts = result.data["page_texts"]
        all_text = " ".join(page_texts.values())

        # Should extract text including URLs
        assert "konicaminolta.com" in all_text.lower()
        assert "support" in all_text.lower()
        assert "user guide" in all_text.lower()

    @pytest.mark.asyncio
    async def test_document_with_error_codes(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test processing documents with error codes."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
        )

        # Content with error codes
        error_code_content = """Error Code Reference
====================

Critical Errors (Red):
- 900.01: Fuser Unit Failure - Immediate service required
- 900.02: Exposure Lamp Failure - Replace lamp assembly
- 900.03: High Voltage Failure - Check power supply

Warning Errors (Yellow):
- 920.00: Waste Toner Full - Replace waste toner container
- 921.00: Low Toner Warning - Replace toner cartridge soon
- 922.00: Drum Life Warning - Replace drum unit soon

Information Messages (Blue):
- 001.00: Warming Up - Please wait
- 002.00: Calibrating - Performing automatic calibration
- 003.00: Energy Save Mode - Press any key to wake

Troubleshooting Steps:
1. Note the error code displayed
2. Check this manual for the specific error
3. Follow the recommended solution
4. Contact support if error persists"""

        test_file = temp_test_pdf / "error_codes.pdf"
        test_file.write_text(error_code_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Error code document processing should succeed"
        page_texts = result.data["page_texts"]
        all_text = " ".join(page_texts.values())

        # Should extract error codes
        assert "900.01" in all_text
        assert "920.00" in all_text
        assert "001.00" in all_text
        assert "fuser unit" in all_text.lower()
        assert "waste toner" in all_text.lower()


# Parameterized tests for different manufacturers
@pytest.mark.parametrize(
    "manufacturer,model,keywords",
    [
        ("HP", "LaserJet Pro", ["hp", "laserjet", "pro"]),
        ("Canon", "imageRUNNER", ["canon", "imagerunner"]),
        ("Xerox", "WorkCentre", ["xerox", "workcentre"]),
        ("Brother", "MFC", ["brother", "mfc"]),
        ("Ricoh", "MP", ["ricoh", "mp "]),
    ],
)
@pytest.mark.asyncio
async def test_manufacturer_detection_various(
    mock_database_adapter, temp_test_pdf, processor_test_config, manufacturer, model, keywords
):
    """Test manufacturer detection for various brands."""
    # Arrange
    processor = DocumentProcessor(
        database_adapter=mock_database_adapter, pdf_engine=processor_test_config["pdf_engine"]
    )

    # Content with manufacturer-specific information
    content = f"""{manufacturer} {model} Service Manual

Technical specifications for {manufacturer} {model}.
Manufacturer: {manufacturer}
Model: {model}
Serial: {manufacturer.upper()}{model.replace(' ', '')}123456

This is the official service manual for {manufacturer} equipment."""

    filename = f"{manufacturer}_{model.replace(' ', '_')}_Manual.pdf"
    test_file = temp_test_pdf / filename
    test_file.write_text(content)

    context = ProcessingContext(
        document_id=f"test-doc-{manufacturer.lower()}", file_path=test_file, metadata={"filename": filename}
    )

    # Act
    result = await processor.process(context)

    # Assert
    assert result.success, f"Should process {manufacturer} manual"
    metadata = result.data.get("metadata", {})
    detected_manufacturer = metadata.get("manufacturer", "").lower()

    # Should detect manufacturer
    assert any(
        keyword in detected_manufacturer for keyword in keywords
    ), f"Should detect {manufacturer} in '{detected_manufacturer}'"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
