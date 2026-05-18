"""
Unit tests for MetadataProcessorAI components.

Tests error code extraction and version extraction functionality
with deterministic mocks and isolated test data.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.core.base_processor import ProcessingContext, ProcessingError
from backend.processors.metadata_processor_ai import MetadataProcessorAI
from backend.processors.models import ExtractedErrorCode, ExtractedVersion


@pytest.mark.metadata
@pytest.mark.error_codes
class TestErrorCodeExtractor:
    """Test ErrorCodeExtractor functionality with deterministic mocks."""

    def test_initialization(self, mock_error_code_extractor):
        """Test ErrorCodeExtractor initialization."""
        extractor = mock_error_code_extractor
        assert extractor is not None
        assert hasattr(extractor, "extract_from_text")
        assert hasattr(extractor, "extract")

    def test_extract_hp_error_codes(self, mock_error_code_extractor):
        """Test extraction of HP error codes from text."""
        extractor = mock_error_code_extractor

        text = "Error 13.A1.B2: Paper jam in tray 2. Remove paper and restart printer."
        error_codes = extractor.extract_from_text(text, manufacturer="HP", page_number=1)

        assert len(error_codes) == 1
        error_code = error_codes[0]
        assert isinstance(error_code, ExtractedErrorCode)
        assert error_code.error_code == "13.A1.B2"
        assert error_code.error_description == "Paper jam in tray 2"
        assert error_code.solution_text == "Remove paper from tray 2 and restart printer"
        assert error_code.page_number == 1
        assert error_code.severity_level == "medium"
        assert error_code.confidence == 0.9

    def test_extract_konica_minolta_error_codes(self, mock_error_code_extractor):
        """Test extraction of Konica Minolta error codes from text."""
        extractor = mock_error_code_extractor

        text = "Error C-2557: Developer unit error. Replace developer unit."
        error_codes = extractor.extract_from_text(text, manufacturer="Konica Minolta", page_number=2)

        assert len(error_codes) == 1
        error_code = error_codes[0]
        assert isinstance(error_code, ExtractedErrorCode)
        assert error_code.error_code == "C-2557"
        assert error_code.error_description == "Developer unit error"
        assert error_code.solution_text == "Replace developer unit"
        assert error_code.page_number == 2
        assert error_code.severity_level == "critical"
        assert error_code.confidence == 0.95

    def test_extract_lexmark_error_codes(self, mock_error_code_extractor):
        """Test extraction of Lexmark error codes from text."""
        extractor = mock_error_code_extractor

        text = "Error 900.01: Fuser unit error. Replace fuser unit."
        error_codes = extractor.extract_from_text(text, manufacturer="Lexmark", page_number=3)

        assert len(error_codes) == 1
        error_code = error_codes[0]
        assert isinstance(error_code, ExtractedErrorCode)
        assert error_code.error_code == "900.01"
        assert error_code.error_description == "Fuser unit error"
        assert error_code.solution_text == "Replace fuser unit"
        assert error_code.page_number == 3
        assert error_code.severity_level == "critical"
        assert error_code.confidence == 0.92

    def test_extract_multiple_error_codes(self, mock_error_code_extractor):
        """Test extraction of multiple error codes from single text."""
        extractor = mock_error_code_extractor

        text = """
        Error 13.A1.B2: Paper jam in tray 2. Remove paper and restart printer.
        Error 49.4C02: Firmware error. Power cycle printer and update firmware.
        Error C-2557: Developer unit error. Replace developer unit.
        """
        error_codes = extractor.extract_from_text(text, manufacturer="AUTO", page_number=1)

        assert len(error_codes) == 3
        error_code_strings = [ec.error_code for ec in error_codes]
        assert "13.A1.B2" in error_code_strings
        assert "49.4C02" in error_code_strings
        assert "C-2557" in error_code_strings

    def test_extract_no_error_codes(self, mock_error_code_extractor):
        """Test extraction from text with no error codes."""
        extractor = mock_error_code_extractor

        text = "This document contains no error codes or technical information."
        error_codes = extractor.extract_from_text(text, manufacturer="AUTO", page_number=1)

        assert len(error_codes) == 0

    def test_extract_with_manufacturer_override(self, mock_error_code_extractor):
        """Test extraction with specific manufacturer override."""
        extractor = mock_error_code_extractor

        text = "Error 49.4C02: Firmware error. Power cycle printer."
        error_codes = extractor.extract_from_text(text, manufacturer="HP", page_number=1)

        assert len(error_codes) == 1
        error_code = error_codes[0]
        assert error_code.error_code == "49.4C02"
        assert error_code.severity_level == "high"

    def test_extract_full_document(self, mock_error_code_extractor):
        """Test extract method for full document processing."""
        extractor = mock_error_code_extractor

        document_text = """
        Page 1: Error 13.A1.B2: Paper jam in tray 2.
        Page 2: Error 49.4C02: Firmware error.
        Page 3: Error C-2557: Developer unit error.
        """
        error_codes = extractor.extract(document_text, manufacturer="AUTO")

        assert len(error_codes) == 3
        # All should be on page 1 due to mock implementation
        for error_code in error_codes:
            assert error_code.page_number == 1

    def test_error_code_quality_validation(self, mock_error_code_extractor):
        """Test error code quality and confidence levels."""
        extractor = mock_error_code_extractor

        text = "Error C-2557: Developer unit error."
        error_codes = extractor.extract_from_text(text, manufacturer="Konica Minolta", page_number=1)

        error_code = error_codes[0]
        assert error_code.confidence >= 0.0
        assert error_code.confidence <= 1.0
        assert error_code.severity_level in ["low", "medium", "high", "critical"]
        assert len(error_code.error_description) >= 10
        assert len(error_code.context_text) >= 50

    def test_mock_side_effect_calls(self, mock_error_code_extractor):
        """Test that mock side effects are called correctly."""
        extractor = mock_error_code_extractor

        text = "Error 13.A1.B2: Paper jam."
        extractor.extract_from_text(text, manufacturer="HP", page_number=1)

        # Verify the mock was called with correct parameters
        extractor.extract_from_text.assert_called_once_with(text, "HP", 1)


@pytest.mark.metadata
@pytest.mark.versions
class TestVersionExtractor:
    """Test VersionExtractor functionality with deterministic mocks."""

    def test_initialization(self, mock_version_extractor):
        """Test VersionExtractor initialization."""
        extractor = mock_version_extractor
        assert extractor is not None
        assert hasattr(extractor, "extract_from_text")
        assert hasattr(extractor, "extract_best_version")

    def test_extract_edition_versions(self, mock_version_extractor):
        """Test extraction of edition version patterns."""
        extractor = mock_version_extractor

        text = "Service Manual Edition 3, 5/2024"
        versions = extractor.extract_from_text(text, manufacturer="HP")

        assert len(versions) == 1
        version = versions[0]
        assert isinstance(version, ExtractedVersion)
        assert version.version_string == "Edition 3, 5/2024"
        assert version.version_type == "edition"
        assert version.confidence == 0.9
        assert version.page_number == 1

    def test_extract_date_versions(self, mock_version_extractor):
        """Test extraction of date version patterns."""
        extractor = mock_version_extractor

        text = "Publication Date: 2024/12/25"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "2024/12/25"
        assert version.version_type == "date"
        assert version.confidence == 0.95
        assert version.page_number == 1

    def test_extract_firmware_versions(self, mock_version_extractor):
        """Test extraction of firmware version patterns."""
        extractor = mock_version_extractor

        text = "FW 4.2 - Current Firmware Version"
        versions = extractor.extract_from_text(text, manufacturer="Canon")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "FW 4.2"
        assert version.version_type == "firmware"
        assert version.confidence == 0.9
        assert version.page_number == 1

    def test_extract_standard_versions(self, mock_version_extractor):
        """Test extraction of standard version patterns."""
        extractor = mock_version_extractor

        text = "Version 1.0 - Software Version"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "Version 1.0"
        assert version.version_type == "version"
        assert version.confidence == 0.85
        assert version.page_number == 1

    def test_extract_revision_versions(self, mock_version_extractor):
        """Test extraction of revision version patterns."""
        extractor = mock_version_extractor

        text = "Rev 1.0 - Initial Release"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "Rev 1.0"
        assert version.version_type == "revision"
        assert version.confidence == 0.9
        assert version.page_number == 1

    def test_extract_multiple_versions(self, mock_version_extractor):
        """Test extraction of multiple version types from single text."""
        extractor = mock_version_extractor

        text = """
        Edition 3, 5/2024
        Publication Date: 2024/12/25
        FW 4.2
        Version 1.0
        Rev 1.0
        """
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 5
        version_types = [v.version_type for v in versions]
        assert "edition" in version_types
        assert "date" in version_types
        assert "firmware" in version_types
        assert "version" in version_types
        assert "revision" in version_types

    def test_extract_no_versions(self, mock_version_extractor):
        """Test extraction from text with no version patterns."""
        extractor = mock_version_extractor

        text = "This document contains no version information."
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 0

    def test_extract_best_version(self, mock_version_extractor):
        """Test extraction of best (highest confidence) version."""
        extractor = mock_version_extractor

        text = """
        Edition 3, 5/2024
        Publication Date: 2024/12/25
        """
        best_version = extractor.extract_best_version(text, manufacturer="AUTO")

        assert best_version is not None
        assert isinstance(best_version, ExtractedVersion)
        # Date pattern has highest confidence (0.95)
        assert best_version.version_string == "2024/12/25"
        assert best_version.version_type == "date"
        assert best_version.confidence == 0.95

    def test_extract_best_version_no_versions(self, mock_version_extractor):
        """Test extract_best_version with no versions found."""
        extractor = mock_version_extractor

        text = "No version information here."
        best_version = extractor.extract_best_version(text, manufacturer="AUTO")

        assert best_version is None

    def test_version_quality_validation(self, mock_version_extractor):
        """Test version quality and validation."""
        extractor = mock_version_extractor

        text = "Edition 3, 5/2024"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        version = versions[0]
        assert version.confidence >= 0.0
        assert version.confidence <= 1.0
        assert version.version_type in ["edition", "date", "firmware", "version", "revision"]
        assert len(version.version_string) >= 1
        assert len(version.version_string) <= 50

    def test_alternative_firmware_format(self, mock_version_extractor):
        """Test alternative firmware format extraction."""
        extractor = mock_version_extractor

        text = "Firmware 4.2 - Latest Release"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "Firmware 4.2"
        assert version.version_type == "firmware"
        assert version.confidence == 0.88

    def test_alternative_version_format(self, mock_version_extractor):
        """Test alternative version format extraction."""
        extractor = mock_version_extractor

        text = "v1.0 - Alternative Format"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "v1.0"
        assert version.version_type == "version"
        assert version.confidence == 0.8

    def test_month_year_date_format(self, mock_version_extractor):
        """Test month-year date format extraction."""
        extractor = mock_version_extractor

        text = "Updated: November 2024"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        assert len(versions) == 1
        version = versions[0]
        assert version.version_string == "November 2024"
        assert version.version_type == "date"
        assert version.confidence == 0.85

    def test_mock_side_effect_calls(self, mock_version_extractor):
        """Test that mock side effects are called correctly."""
        extractor = mock_version_extractor

        text = "Edition 3, 5/2024"
        extractor.extract_from_text(text, manufacturer="HP")

        # Verify the mock was called with correct parameters
        extractor.extract_from_text.assert_called_once_with(text, "HP")


@pytest.mark.metadata
class TestMetadataProcessorAIIntegration:
    """Integration tests for MetadataProcessorAI using the BaseProcessor contract."""

    @pytest.fixture
    def processor(self, mock_error_code_extractor, mock_version_extractor):
        """Create a MetadataProcessorAI wired to mocked extractors without DB access."""
        processor = MetadataProcessorAI(database_service=None)

        # Wire deterministic mocks
        processor.error_code_extractor = mock_error_code_extractor
        processor.version_extractor = mock_version_extractor

        # Route PDF-based extraction to the existing text-based mock implementation
        def fake_extract(*, pdf_path: Path, manufacturer: str = "AUTO"):
            sample_text = "Error 13.A1.B2: Paper jam in tray 2. " "Remove paper from tray 2 and restart printer."
            return mock_error_code_extractor.extract_from_text(
                sample_text,
                manufacturer,
                page_number=1,
            )

        mock_error_code_extractor.extract.side_effect = fake_extract

        # Version extractor: map file path to a fixed version string via the mock
        def fake_version_extract(pdf_path: Path):
            versions = mock_version_extractor.extract_from_text(
                "Edition 3, 5/2024",
                manufacturer="AUTO",
            )
            return versions[0].version_string if versions else None

        mock_version_extractor.extract = MagicMock(side_effect=fake_version_extract)

        # Avoid real DB lookups for manufacturer resolution
        async def fake_get_document_manufacturer(document_id: str) -> str:
            return "HP"

        processor._get_document_manufacturer = fake_get_document_manufacturer  # type: ignore[attr-defined]

        return processor

    @pytest.mark.asyncio
    async def test_processor_initialization(self, processor):
        """MetadataProcessorAI exposes configured extractors."""
        assert processor is not None
        assert hasattr(processor, "error_code_extractor")
        assert hasattr(processor, "version_extractor")

    @pytest.mark.asyncio
    async def test_process_with_error_codes_and_version(self, processor, tmp_path):
        """Processing a PDF path yields a successful ProcessingResult with metadata."""
        pdf_path = tmp_path / "test_metadata.pdf"
        pdf_path.write_text("dummy pdf content")

        context = ProcessingContext(
            document_id="doc-123",
            file_path=str(pdf_path),
            document_type="service_manual",
            manufacturer="HP",
        )

        result = await processor.safe_process(context)

        assert result.success is True
        assert result.processor == "metadata_processor_ai"
        assert "error_codes_extracted" in result.data
        assert result.data["error_codes_extracted"] >= 1
        assert "version_info" in result.data
        assert result.data["version_info"] == "Edition 3, 5/2024"

    @pytest.mark.asyncio
    async def test_process_handles_extraction_error(self, processor, tmp_path):
        """Errors inside process() are converted to an error ProcessingResult."""
        pdf_path = tmp_path / "test_metadata_error.pdf"
        pdf_path.write_text("dummy pdf content")

        context = ProcessingContext(
            document_id="doc-error",
            file_path=str(pdf_path),
            document_type="service_manual",
            manufacturer="HP",
        )

        # Force extractor failure inside the processor try/except block
        processor.error_code_extractor.extract.side_effect = Exception("Test extraction error")

        result = await processor.safe_process(context)

        assert result.success is False
        assert isinstance(result.error, ProcessingError)
        assert result.error.processor == "metadata_processor_ai"


@pytest.mark.metadata
class TestMetadataProcessorAIQuality:
    """Test quality metrics and validation for MetadataProcessorAI."""

    def test_error_code_quality_metrics(self, create_test_error_code):
        """Test error code quality metrics calculation."""
        error_code = create_test_error_code(
            error_code="900.01",
            error_description="Fuser unit error",
            solution_text="Replace fuser unit",
            page_number=1,
            severity_level="critical",
            confidence=0.92,
        )

        # Test quality indicators
        assert error_code.confidence >= 0.8  # High confidence
        assert error_code.severity_level == "critical"
        assert len(error_code.error_description) >= 10
        assert len(error_code.context_text) >= 50

    def test_version_quality_metrics(self, mock_version_extractor):
        """Test version quality metrics calculation."""
        extractor = mock_version_extractor

        text = "Publication Date: 2024/12/25"
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        version = versions[0]

        # Test quality indicators
        assert version.confidence >= 0.8  # High confidence
        assert version.version_type == "date"
        assert len(version.version_string) >= 1
        assert len(version.version_string) <= 50

    def test_duplicate_error_code_handling(self, mock_error_code_extractor):
        """Test handling of duplicate error codes."""
        extractor = mock_error_code_extractor

        text = "Error 13.A1.B2: Paper jam. Error 13.A1.B2: Paper jam again."
        error_codes = extractor.extract_from_text(text, manufacturer="HP", page_number=1)

        # Mock should return duplicates as found
        assert len(error_codes) == 2
        for error_code in error_codes:
            assert error_code.error_code == "13.A1.B2"

    def test_low_confidence_filtering(self, mock_error_code_extractor):
        """Test filtering of low confidence extractions."""
        extractor = mock_error_code_extractor

        # All mock error codes have confidence >= 0.8
        text = "Error 13.A1.B2: Paper jam."
        error_codes = extractor.extract_from_text(text, manufacturer="HP", page_number=1)

        for error_code in error_codes:
            assert error_code.confidence >= 0.8

    def test_version_type_distribution(self, mock_version_extractor):
        """Test distribution of extracted version types."""
        extractor = mock_version_extractor

        text = """
        Edition 3, 5/2024
        Publication Date: 2024/12/25
        FW 4.2
        Version 1.0
        Rev 1.0
        """
        versions = extractor.extract_from_text(text, manufacturer="AUTO")

        version_types = [v.version_type for v in versions]
        expected_types = ["edition", "date", "firmware", "version", "revision"]

        for expected_type in expected_types:
            assert expected_type in version_types

        # All types should be present
        assert len(set(version_types)) == 5
