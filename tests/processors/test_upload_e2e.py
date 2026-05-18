"""
Comprehensive E2E Tests for UploadProcessor

This module provides extensive end-to-end testing for the UploadProcessor component,
covering all critical functionality including file validation, deduplication,
database operations, metadata extraction, error recovery, and edge cases.

Test Categories:
1. File Validation Tests
2. Deduplication Tests
3. Database Operations Tests
4. Metadata Extraction Tests
5. Error Recovery Tests
6. Edge Cases Tests

All tests use the fixtures from conftest.py for consistent mock objects and test data.
"""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.upload_processor import BatchUploadProcessor, UploadProcessor

pytestmark = pytest.mark.processor


class TestUploadValidation:
    """Test file validation functionality of UploadProcessor."""

    @pytest.mark.asyncio
    async def test_valid_pdf_upload(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test successful upload of a valid PDF file."""
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
        assert result.success, f"Upload should succeed: {result.error}"
        assert result.data is not None
        assert "document_id" in result.data
        assert result.metadata.get("file_path") == str(valid_pdf["path"])

        # Verify database operations
        document = await mock_database_adapter.get_document(result.data["document_id"])
        assert document is not None
        assert document["filename"] == valid_pdf["path"].name

    @pytest.mark.asyncio
    async def test_invalid_file_extension(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test rejection of files with invalid extensions."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create files with invalid extensions
        invalid_files = ["test.txt", "test.docx", "test.jpg", "test.png"]

        for filename in invalid_files:
            # Create test file
            test_file = temp_test_pdf / filename
            test_file.write_text("This is not a PDF file")

            # Act
            context = ProcessingContext(
                document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual"
            )
            result = await processor.process(context)

            # Assert
            assert not result.success, f"Should reject {filename}"
            assert "Invalid file type" in result.error or "extension" in result.error.lower()

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_database_adapter, processor_test_config):
        """Test error handling for non-existent files."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        non_existent_path = Path("/non/existent/file.pdf")

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(non_existent_path), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success
        assert "File not found" in result.error

    @pytest.mark.asyncio
    async def test_file_too_large(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test rejection of files exceeding size limit."""
        # Arrange
        processor = UploadProcessor(database_adapter=mock_database_adapter, max_file_size_mb=1)  # Set very low limit
        large_pdf = sample_pdf_files["large_pdf"]

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(large_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success
        assert "File too large" in result.error

    @pytest.mark.asyncio
    async def test_corrupted_pdf(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test detection and rejection of corrupted PDF files."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        corrupted_pdf = sample_pdf_files["corrupted_pdf"]

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(corrupted_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success
        assert "Corrupted or invalid PDF" in result.error

    @pytest.mark.asyncio
    async def test_empty_pdf(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test rejection of PDF files with zero bytes."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        empty_pdf = sample_pdf_files["empty_pdf"]

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(empty_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success
        assert "Corrupted or invalid PDF" in result.error

    @pytest.mark.asyncio
    async def test_pdf_with_zero_bytes(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test rejection of files that are exactly zero bytes."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create zero-byte file with .pdf extension
        zero_byte_file = temp_test_pdf / "zero_byte.pdf"
        zero_byte_file.write_bytes(b"")

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(zero_byte_file), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success
        assert "Corrupted or invalid PDF" in result.error


class TestUploadDeduplication:
    """Test deduplication functionality of UploadProcessor."""

    @pytest.mark.asyncio
    async def test_duplicate_detection_by_hash(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test detection of duplicate files using SHA-256 hash."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Calculate file hash
        with open(valid_pdf["path"], "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        # Pre-populate database with existing document
        existing_doc = {
            "id": "existing-doc-id",
            "filename": "existing_file.pdf",
            "file_hash": file_hash,
            "file_size_bytes": valid_pdf["size"],
            "status": "completed",
        }
        mock_database_adapter.documents["existing-doc-id"] = existing_doc

        # Act - first upload should succeed
        context1 = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result1 = await processor.process(context1)

        # Act - second upload should detect duplicate (returns success with status='duplicate')
        context2 = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result2 = await processor.process(context2)

        # Assert - Comment 2: duplicates return success with status='duplicate'
        assert result1.success, "First upload should succeed"
        assert result2.success, "Second upload should succeed with duplicate status"
        assert result2.data.get("status") == "duplicate", "Should mark as duplicate"

    @pytest.mark.asyncio
    async def test_force_reprocess_duplicate(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test reprocessing of duplicate files with force_reprocess=True."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Calculate file hash and pre-populate database
        with open(valid_pdf["path"], "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        existing_doc = {
            "id": "existing-doc-id",
            "filename": "existing_file.pdf",
            "file_hash": file_hash,
            "file_size_bytes": valid_pdf["size"],
            "status": "completed",
        }
        mock_database_adapter.documents["existing-doc-id"] = existing_doc

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(valid_pdf["path"]),
            document_type="service_manual",
        )
        context.force_reprocess = True
        result = await processor.process(context)

        # Assert
        assert result.success, "Force reprocess should succeed"
        assert result.data.get("status") == "reprocessing", "Should mark as reprocessing"

    @pytest.mark.asyncio
    async def test_different_files_same_name(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test that different files with the same name are treated as separate documents."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create two files with same name but different content
        same_name = "test_manual.pdf"
        file1 = temp_test_pdf / same_name
        file2 = temp_test_pdf / same_name

        file1.write_text("Content for file 1")
        file2.write_text("Different content for file 2")

        # Act
        context1 = ProcessingContext(document_id=str(uuid4()), file_path=str(file1), document_type="service_manual")
        context2 = ProcessingContext(document_id=str(uuid4()), file_path=str(file2), document_type="service_manual")
        result1 = await processor.process(context1)
        result2 = await processor.process(context2)

        # Assert
        assert result1.success, "First file upload should succeed"
        assert result2.success, "Second file upload should succeed"
        assert result1.data["document_id"] != result2.data["document_id"], "Should have different document IDs"

    @pytest.mark.asyncio
    async def test_same_file_different_name(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test that the same file with different names is detected as duplicate."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create same content with different filenames
        content = "Same content for both files"
        file1 = temp_test_pdf / "manual_v1.pdf"
        file2 = temp_test_pdf / "manual_v2.pdf"

        file1.write_text(content)
        file2.write_text(content)

        # Act
        hash1 = hashlib.sha256(file1.read_bytes()).hexdigest()
        hash2 = hashlib.sha256(file2.read_bytes()).hexdigest()
        context1 = ProcessingContext(document_id=str(uuid4()), file_path=str(file1), document_type="service_manual")
        context2 = ProcessingContext(document_id=str(uuid4()), file_path=str(file2), document_type="service_manual")
        result1 = await processor.process(context1)
        result2 = await processor.process(context2)

        # Assert
        assert result1.success, "First upload should succeed"
        assert result2.success, "Second upload should succeed with duplicate status"
        assert result2.data.get("status") == "duplicate"
        assert "existing_document" in result2.data


class TestUploadDatabaseOperations:
    """Test database operations of UploadProcessor."""

    @pytest.mark.asyncio
    async def test_document_creation(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test successful creation of document record in database."""
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

        # Verify document was created in database
        document = await mock_database_adapter.get_document(result.data["document_id"])
        assert document is not None
        assert document["filename"] == valid_pdf["path"].name
        assert document["file_size_bytes"] == valid_pdf["size"]
        assert document["status"] == "uploaded"
        assert "created_at" in document
        assert "updated_at" in document

    @pytest.mark.asyncio
    async def test_document_update_on_reprocess(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test document update when reprocessing with force_reprocess=True."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # First upload
        context1 = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result1 = await processor.process(context1)
        original_doc_id = result1.data["document_id"]

        # Mock update to track calls
        original_update = mock_database_adapter.update_document
        update_calls = []

        async def track_update(document_id, updates):
            update_calls.append((document_id, updates))
            return await original_update(document_id, updates)

        mock_database_adapter.update_document = track_update

        # Act - reprocess
        context2 = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        # Mark context for forced reprocessing
        context2.force_reprocess = True
        result2 = await processor.process(context2)

        # Assert
        assert result2.success, "Reprocess should succeed"
        assert len(update_calls) > 0, "Update should be called"

    @pytest.mark.asyncio
    async def test_processing_queue_creation(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test creation of processing queue item."""
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
        assert len(mock_database_adapter.processing_queue) > 0, "Processing queue item should be created"

        queue_item = mock_database_adapter.processing_queue[-1]
        assert queue_item["document_id"] == result.data["document_id"]
        assert queue_item["stage"] == "upload"
        assert queue_item["status"] == "pending"

    @pytest.mark.asyncio
    async def test_stage_tracker_integration(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test integration with StageTracker."""
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
        # StageTracker calls are logged in the mock, so we just verify the upload succeeded

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test error handling when database operations fail."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Mock database to raise exception
        async def failing_create_document(document):
            raise Exception("Database connection failed")

        mock_database_adapter.create_document = failing_create_document

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert not result.success, "Upload should fail when database fails"
        assert "database" in result.error.lower() or "connection" in result.error.lower()


class TestUploadMetadataExtraction:
    """Test metadata extraction functionality of UploadProcessor."""

    @pytest.mark.asyncio
    async def test_basic_metadata_extraction(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test extraction of basic file metadata."""
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
        assert "filename" in metadata
        assert "file_size_bytes" in metadata
        assert "page_count" in metadata
        assert "file_hash" in metadata

        assert metadata["filename"] == valid_pdf["path"].name
        assert metadata["file_size_bytes"] == valid_pdf["size"]
        assert isinstance(metadata["page_count"], int)
        assert len(metadata["file_hash"]) == 64  # SHA-256 hash length

    @pytest.mark.asyncio
    async def test_pdf_metadata_extraction(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test extraction of PDF-specific metadata."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create a PDF with metadata (mock implementation)
        test_file = temp_test_pdf / "metadata_test.pdf"
        test_file.write_text("Mock PDF with metadata")

        # Act
        context = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should succeed"

        metadata = result.metadata
        # These fields may be None for mock PDFs, but should exist in metadata
        assert "title" in metadata
        assert "author" in metadata
        assert "creator" in metadata
        assert "creation_date" in metadata

    @pytest.mark.asyncio
    async def test_file_hash_calculation(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test correct SHA-256 hash calculation."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Calculate expected hash
        with open(valid_pdf["path"], "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should succeed"
        assert result.metadata["file_hash"] == expected_hash, "File hash should match expected SHA-256"

    @pytest.mark.asyncio
    async def test_metadata_with_missing_fields(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test handling of PDFs with missing metadata fields."""
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

        # Should handle missing metadata gracefully
        metadata = result.metadata
        assert metadata is not None

    @pytest.mark.asyncio
    async def test_partial_metadata_failure(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test continuation when metadata extraction partially fails."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Mock metadata extraction to fail partially
        with patch.object(processor, "_extract_basic_metadata") as mock_metadata:
            mock_metadata.return_value = {"filename": valid_pdf["path"].name}  # Minimal metadata

            # Act
            context = ProcessingContext(
                document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
            )
            result = await processor.process(context)

            # Assert
            assert result.success, "Upload should succeed even with partial metadata failure"

    @pytest.mark.asyncio
    async def test_queue_creation_failure(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test continuation when processing queue creation fails."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Mock queue creation to fail
        async def failing_create_queue_item(item):
            raise Exception("Queue creation failed")

        mock_database_adapter.create_processing_queue_item = failing_create_queue_item

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        # Should still succeed since queue creation is non-critical
        assert result.success, "Upload should succeed even if queue creation fails"

    @pytest.mark.asyncio
    async def test_stage_tracker_failure(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test continuation when StageTracker operations fail."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )
        valid_pdf = sample_pdf_files["valid_pdf"]

        # Mock StageTracker to fail
        mock_tracker = MagicMock()
        mock_tracker.start_stage = AsyncMock(side_effect=Exception("StageTracker failed"))
        mock_tracker.complete_stage = AsyncMock(side_effect=Exception("StageTracker failed"))

        processor.stage_tracker = mock_tracker

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(valid_pdf["path"]), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        # Should still succeed since StageTracker is non-critical
        assert result.success, "Upload should succeed even if StageTracker fails"


class TestUploadEdgeCases:
    """Test edge cases and boundary conditions of UploadProcessor."""

    @pytest.mark.asyncio
    async def test_unicode_filename(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of filenames with Unicode characters."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create file with Unicode characters in name
        unicode_filename = "tëst_ßërvïcë_mänüäl_中文.pdf"
        test_file = temp_test_pdf / unicode_filename
        test_file.write_text("Test content with Unicode filename")

        # Act
        context = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should handle Unicode filenames"
        assert result.metadata["filename"] == unicode_filename

    @pytest.mark.asyncio
    async def test_special_characters_in_path(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of special characters in file paths."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create file with special characters
        special_filename = "test-service_manual(v1.2)-final[copy].pdf"
        test_file = temp_test_pdf / special_filename
        test_file.write_text("Test content with special characters")

        # Act
        context = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should handle special characters in paths"
        assert result.metadata["filename"] == special_filename

    @pytest.mark.asyncio
    async def test_very_long_filename(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of very long filenames."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create file with very long name (close to filesystem limits)
        long_filename = "a" * 200 + ".pdf"  # 200 characters + .pdf
        test_file = temp_test_pdf / long_filename
        test_file.write_text("Test content with long filename")

        # Act
        context = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
        result = await processor.process(context)

        # Assert
        assert result.success, "Upload should handle long filenames"
        assert result.metadata["filename"] == long_filename

    @pytest.mark.asyncio
    async def test_pdf_with_password(self, mock_database_adapter, temp_test_pdf, processor_test_config):
        """Test handling of password-protected PDFs."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create a mock password-protected PDF
        password_pdf = temp_test_pdf / "password_protected.pdf"
        password_pdf.write_text("Mock password-protected PDF content")

        # Act
        context = ProcessingContext(
            document_id=str(uuid4()), file_path=str(password_pdf), document_type="service_manual"
        )
        result = await processor.process(context)

        # Assert
        # Should either succeed with limited metadata or fail gracefully
        if result.success:
            assert result.metadata["filename"] == password_pdf.name
        else:
            assert "password" in result.error.lower() or "protected" in result.error.lower()


class TestBatchUploadProcessor:
    """Test BatchUploadProcessor functionality."""

    @pytest.mark.asyncio
    async def test_batch_upload_multiple_files(self, mock_database_adapter, sample_pdf_files, processor_test_config):
        """Test batch upload of multiple files."""
        # Arrange
        batch_processor = BatchUploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Select multiple test files
        files_to_upload = [sample_pdf_files["valid_pdf"]["path"], sample_pdf_files["multi_language_pdf"]["path"]]

        # Act
        results = await batch_processor.process_batch(files_to_upload)

        # Assert
        assert len(results) == len(files_to_upload), "Should return result for each file"
        assert all(r.success for r in results), "All valid files should upload successfully"
        assert len(set(r.data["document_id"] for r in results)) == len(
            results
        ), "Each file should get unique document ID"

    @pytest.mark.asyncio
    async def test_batch_upload_with_mixed_files(
        self, mock_database_adapter, sample_pdf_files, temp_test_pdf, processor_test_config
    ):
        """Test batch upload with mix of valid and invalid files."""
        # Arrange
        batch_processor = BatchUploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        # Create mix of valid and invalid files
        invalid_file = temp_test_pdf / "invalid.txt"
        invalid_file.write_text("Not a PDF")

        files_to_upload = [
            sample_pdf_files["valid_pdf"]["path"],
            invalid_file,
            sample_pdf_files["corrupted_pdf"]["path"],
        ]

        # Act
        results = await batch_processor.process_batch(files_to_upload)

        # Assert
        assert len(results) == len(files_to_upload), "Should return result for each file"
        assert results[0].success, "Valid PDF should succeed"
        assert not results[1].success, "Invalid extension should fail"
        assert not results[2].success, "Corrupted PDF should fail"

    @pytest.mark.asyncio
    async def test_batch_upload_progress_tracking(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test batch upload with progress tracking."""
        # Arrange
        batch_processor = BatchUploadProcessor(
            database_adapter=mock_database_adapter, max_file_size_mb=processor_test_config["max_file_size_mb"]
        )

        files_to_upload = [sample_pdf_files["valid_pdf"]["path"], sample_pdf_files["multi_language_pdf"]["path"]]

        # Act
        results = await batch_processor.process_batch(files_to_upload)

        # Assert
        assert len(results) == len(files_to_upload)
        assert all(r.success for r in results)


# Parameterized tests for similar scenarios
@pytest.mark.parametrize(
    "file_size_mb,should_succeed",
    [
        (1, True),  # Small file
        (10, True),  # Medium file
        (100, True),  # Large but within limit
        (200, False),  # Over limit
    ],
)
@pytest.mark.asyncio
async def test_file_size_limits(mock_database_adapter, temp_test_pdf, file_size_mb, should_succeed):
    """Test file size limits with various file sizes."""
    # Arrange
    processor = UploadProcessor(database_adapter=mock_database_adapter, max_file_size_mb=100)  # 100MB limit

    # Create file with specified size
    content = "Test content " * (1024 * 1024 * file_size_mb // len("Test content "))
    test_file = temp_test_pdf / f"test_{file_size_mb}mb.pdf"
    test_file.write_text(content)

    # Act
    context = ProcessingContext(document_id=str(uuid4()), file_path=str(test_file), document_type="service_manual")
    result = await processor.process(context)

    # Assert
    if should_succeed:
        assert result.success, f"File of {file_size_mb}MB should succeed"
    else:
        assert not result.success, f"File of {file_size_mb}MB should fail"
        assert "size" in result.error.lower()


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
