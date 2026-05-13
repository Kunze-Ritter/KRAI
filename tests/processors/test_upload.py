"""
Test Upload Processor

This module provides basic unit tests for UploadProcessor functionality.
Integrates with conftest.py fixtures for consistent testing infrastructure.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext, ProcessingResult
from backend.processors.upload_processor import UploadProcessor

pytestmark = pytest.mark.processor


class TestUploadProcessorBasic:
    """Basic unit tests for UploadProcessor functionality."""

    @pytest.mark.asyncio
    async def test_upload_processor_initialization(self, mock_database_adapter, processor_test_config):
        """Test UploadProcessor initialization with mock database."""
        # Arrange & Act
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Assert
        assert processor is not None, "Processor should be initialized"
        assert processor.max_file_size_bytes == processor_test_config["max_file_size_mb"] * 1024 * 1024
        assert processor.database == mock_database_adapter

    @pytest.mark.asyncio
    async def test_simple_file_validation(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test basic file validation functionality."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert isinstance(result, ProcessingResult), "Should return ProcessingResult"
        assert result.success, f"Valid PDF should process successfully: {result.error}"
        assert result.data is not None, "Should have result data"
        assert "document_id" in result.data, "Should have document ID"

    @pytest.mark.asyncio
    async def test_file_size_validation(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test file size validation."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=1,  # Small limit for testing
        )

        # Use larger file to test size limit
        large_pdf = sample_pdf_files.get("large_pdf")
        if large_pdf and large_pdf["size"] > 1024 * 1024:  # > 1MB
            # Act
            context = ProcessingContext(
                document_id=str(uuid4()), file_path=str(large_pdf["path"]), document_type="service_manual"
            )
            result = await processor.process(context)

            # Assert
            assert not result.success, "Large file should be rejected"
            assert "File too large" in str(result.error)

    @pytest.mark.asyncio
    async def test_nonexistent_file_handling(self, mock_database_adapter, processor_test_config):
        """Test handling of non-existent files."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        nonexistent_file = Path("/nonexistent/path/file.pdf")

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(nonexistent_file), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success, "Non-existent file should be rejected"
        assert "File not found" in str(result.error)

    @pytest.mark.asyncio
    async def test_file_extension_validation(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test file extension validation."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create non-PDF file
        text_file = temp_test_pdf / "test.txt"
        text_file.write_text("This is not a PDF file.")

        # Act
        context = ProcessingContext(document_id=str(uuid4()), file_path=str(text_file), document_type="service_manual")
        result = await processor.process(context)

        # Assert
        # Should either reject non-PDF or handle gracefully
        if not result.success:
            error_str = str(result.error)
            assert "Invalid file type" in error_str

    @pytest.mark.asyncio
    async def test_duplicate_detection(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test duplicate file detection."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create test file
        test_file = temp_test_pdf / "duplicate_test.pdf"
        test_file.write_text("Test content for duplicate detection.")

        # Act - First upload
        context1 = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        first_result = await processor.process(context1)

        # Assert - First upload should succeed
        assert first_result.success, "First upload should succeed"
        document_id = first_result.data["document_id"]

        # Act - Second upload (should detect duplicate)
        context2 = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        second_result = await processor.process(context2)

        # Assert - Second upload should succeed with duplicate status
        assert second_result.success, "Second upload should succeed with duplicate status"
        assert second_result.data.get("status") == "duplicate", "Should mark as duplicate"

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test metadata extraction from uploaded files."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should succeed"

        metadata = result.metadata
        assert metadata is not None, "Should have metadata"
        assert "file_path" in metadata, "Should have file path"

        # Verify metadata values
        assert metadata.get("file_path") == str(valid_pdf["path"]), "File path should match"


# DEPRECATED: Legacy test function - DO NOT USE
# This legacy entrypoint is deprecated and should not be used.
# Use pytest to run the modern async tests in this file instead:
#   pytest tests/processors/test_upload.py -v
#
# The legacy function below references old APIs that no longer exist.
# It is kept only for historical reference and will be removed in a future version.


def test_upload_processor_legacy():
    """DEPRECATED: Legacy test function - use pytest instead.

    This function is deprecated and references old APIs.

    To run tests, use:
        pytest tests/processors/test_upload.py -v
    """
    raise DeprecationWarning(
        "This legacy test entrypoint is deprecated. "
        "Use 'pytest tests/processors/test_upload.py -v' to run modern async tests."
    )


if __name__ == "__main__":
    print("=" * 70)
    print("DEPRECATED: This script is deprecated.")
    print("=" * 70)
    print()
    print("To run upload processor tests, use pytest:")
    print("  pytest tests/processors/test_upload.py -v")
    print()
    print("Or run all processor tests:")
    print("  pytest tests/processors/ -v")
    print()
    print("=" * 70)
