"""
End-to-end tests for MetadataProcessorAI.

Tests full processing flows with realistic test data and mocks,
including PDF processing, database integration, and stage tracking.
"""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.metadata_processor import MetadataProcessorAI
from backend.processors.models import ExtractedErrorCode, ExtractedVersion


@pytest.mark.skip(reason="Legacy E2E tests for pre-BaseProcessor MetadataProcessor API; replaced by v2 tests.")
@pytest.mark.metadata
@pytest.mark.e2e
class TestMetadataProcessorE2E:
    """End-to-end tests for MetadataProcessorAI with realistic scenarios."""

    @pytest.fixture
    def mock_processor(self, mock_error_code_extractor, mock_version_extractor, mock_database_adapter):
        """Create MetadataProcessorAI with all dependencies mocked."""
        with (
            patch("backend.processors.metadata_processor.ErrorCodeExtractor") as mock_ec_class,
            patch("backend.processors.metadata_processor.VersionExtractor") as mock_v_class,
        ):
            mock_ec_class.return_value = mock_error_code_extractor
            mock_v_class.return_value = mock_version_extractor

            processor = MetadataProcessorAI()
            processor.error_code_extractor = mock_error_code_extractor
            processor.version_extractor = mock_version_extractor
            processor.db_adapter = mock_database_adapter

            yield processor

    @pytest.fixture
    def sample_document_data(self):
        """Create sample document data for testing."""
        return {
            "id": str(uuid.uuid4()),
            "filename": "test_manual.pdf",
            "manufacturer": "HP",
            "model_number": "LaserJet Pro M404n",
            "document_type": "service_manual",
        }

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        return [
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Error 13.A1.B2: Paper jam in tray 2. Remove paper from tray 2 and restart printer.",
                "metadata": {"chunk_type": "error_codes"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Error 49.4C02: Firmware error. Power cycle printer and update firmware.",
                "metadata": {"chunk_type": "error_codes"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Service Manual Edition 3, 5/2024",
                "metadata": {"chunk_type": "version_info"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 3,
                "page_start": 4,
                "page_end": 4,
                "content": "FW 4.2 - Current Firmware Version",
                "metadata": {"chunk_type": "version_info"},
            },
        ]

    @pytest.mark.asyncio
    async def test_process_document_complete_flow(
        self, mock_processor, sample_document_data, sample_chunks, mock_stage_tracker
    ):
        """Test complete document processing flow with metadata extraction."""
        processor = mock_processor
        document_id = sample_document_data["id"]

        # Mock database adapter to return chunks
        processor.db_adapter.get_chunks_by_document.return_value = sample_chunks

        # Process the document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer=sample_document_data["manufacturer"], stage_tracker=mock_stage_tracker
        )

        # Verify processing results
        assert result is not None
        assert "success" in result
        assert result["success"] is True
        assert "error_codes" in result
        assert "versions" in result
        assert "statistics" in result

        # Verify error codes extracted
        error_codes = result["error_codes"]
        assert len(error_codes) >= 2  # Should find at least 2 error codes

        # Verify versions extracted
        versions = result["versions"]
        assert len(versions) >= 2  # Should find at least 2 versions

        # Verify database calls
        processor.db_adapter.get_chunks_by_document.assert_called_once_with(document_id)

        # Verify error codes were saved to database
        assert processor.db_adapter.create_error_code.call_count >= 2

        # Verify stage tracker calls
        assert mock_stage_tracker.set_stage.called
        assert mock_stage_tracker.complete_stage.called

    @pytest.mark.asyncio
    async def test_process_hp_service_manual(self, mock_processor, sample_pdf_with_error_codes, mock_stage_tracker):
        """Test processing HP service manual with realistic error codes."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks from HP service manual
        hp_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "HP LaserJet Error Codes\n\nError 13.A1.B2: Paper jam in tray 2. Solution: Remove paper from tray 2 and restart printer.\nError 49.4C02: Firmware error. Solution: Power cycle printer and update firmware.",
                "metadata": {"chunk_type": "error_codes"},
            }
        ]

        processor.db_adapter.get_chunks_by_document.return_value = hp_chunks

        # Process HP service manual
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Verify HP-specific error codes
        error_codes = result["error_codes"]
        hp_error_codes = [ec for ec in error_codes if ec.error_code in ["13.A1.B2", "49.4C02"]]

        assert len(hp_error_codes) >= 2

        # Verify error code details
        for error_code in hp_error_codes:
            assert isinstance(error_code, ExtractedErrorCode)
            assert error_code.error_code in ["13.A1.B2", "49.4C02"]
            assert error_code.severity_level in ["medium", "high"]
            assert error_code.confidence >= 0.8
            assert len(error_code.error_description) >= 10
            assert len(error_code.context_text) >= 50

    @pytest.mark.asyncio
    async def test_process_konica_minolta_document(self, mock_processor, mock_stage_tracker):
        """Test processing Konica Minolta document with specific error codes."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks from Konica Minolta document
        km_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Konica Minolta bizhub Error Codes\n\nError C-2557: Developer unit error. Solution: Replace developer unit.\nError J-0001: Fuser temperature error. Solution: Check fuser unit and temperature sensor.",
                "metadata": {"chunk_type": "error_codes"},
            }
        ]

        processor.db_adapter.get_chunks_by_document.return_value = km_chunks

        # Process Konica Minolta document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="Konica Minolta", stage_tracker=mock_stage_tracker
        )

        # Verify Konica Minolta-specific error codes
        error_codes = result["error_codes"]
        km_error_codes = [ec for ec in error_codes if ec.error_code in ["C-2557", "J-0001"]]

        assert len(km_error_codes) >= 2

        # Verify error code details
        for error_code in km_error_codes:
            assert isinstance(error_code, ExtractedErrorCode)
            assert error_code.error_code in ["C-2557", "J-0001"]
            assert error_code.severity_level in ["critical", "high"]
            assert error_code.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_process_lexmark_document(self, mock_processor, mock_stage_tracker):
        """Test processing Lexmark document with specific error codes."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks from Lexmark document
        lexmark_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Lexmark Error Codes\n\nError 900.01: Fuser unit error. Solution: Replace fuser unit.\nError 200.02: Memory error. Solution: Check memory modules and restart.",
                "metadata": {"chunk_type": "error_codes"},
            }
        ]

        processor.db_adapter.get_chunks_by_document.return_value = lexmark_chunks

        # Process Lexmark document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="Lexmark", stage_tracker=mock_stage_tracker
        )

        # Verify Lexmark-specific error codes
        error_codes = result["error_codes"]
        lexmark_error_codes = [ec for ec in error_codes if ec.error_code in ["900.01", "200.02"]]

        assert len(lexmark_error_codes) >= 2

        # Verify error code details
        for error_code in lexmark_error_codes:
            assert isinstance(error_code, ExtractedErrorCode)
            assert error_code.error_code in ["900.01", "200.02"]
            assert error_code.severity_level in ["critical", "medium"]
            assert error_code.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_process_document_with_versions(self, mock_processor, sample_pdf_with_versions, mock_stage_tracker):
        """Test processing document with version information."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with version information
        version_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Service Manual Edition Information\n\nEdition 3, 5/2024\nEdition 4.0 - Latest Revision\nPublication Date: 2024/12/25",
                "metadata": {"chunk_type": "version_info"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Firmware and Software Versions\n\nFW 4.2 - Current Firmware Version\nFirmware 4.2 - Latest Release\nVersion 1.0 - Software Version",
                "metadata": {"chunk_type": "version_info"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Revision History\n\nRev 1.0 - Initial Release\nRevision 1.0 - First Major Revision",
                "metadata": {"chunk_type": "version_info"},
            },
        ]

        processor.db_adapter.get_chunks_by_document.return_value = version_chunks

        # Process document with versions
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="AUTO", stage_tracker=mock_stage_tracker
        )

        # Verify versions extracted
        versions = result["versions"]
        assert len(versions) >= 5  # Should find multiple version types

        # Verify version types
        version_types = set(v.version_type for v in versions)
        expected_types = {"edition", "date", "firmware", "version", "revision"}
        assert expected_types.intersection(version_types)

        # Verify version quality
        for version in versions:
            assert isinstance(version, ExtractedVersion)
            assert version.version_type in ["edition", "date", "firmware", "version", "revision"]
            assert version.confidence >= 0.8
            assert len(version.version_string) >= 1
            assert len(version.version_string) <= 50

    @pytest.mark.asyncio
    async def test_process_multimodal_document(
        self, mock_processor, sample_pdf_multimodal_metadata, mock_stage_tracker
    ):
        """Test processing document with mixed error codes, parts, and versions."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with mixed content
        mixed_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "HP LaserJet Error Codes - Edition 3, 5/2024\n\nError 13.A1.B2: Paper jam in tray 2. Solution: Remove paper from tray 2.\nError 49.4C02: Firmware error. Solution: Power cycle printer.\nParts: 6QN29-67005 Fuser Unit, RM1-1234-000 Transfer Roller",
                "metadata": {"chunk_type": "mixed"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Konica Minolta bizhub Parts - FW 4.2\n\nA1DU-R750-00 - Developer Unit\n4062-R750-01 - Drum Unit\nError C-2557: Developer unit failure",
                "metadata": {"chunk_type": "mixed"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Multi-Manufacturer Reference - Rev 1.0\n\nCanon: FM3-5945-000 Fuser Film\nLexmark: 40X5852 Toner Cartridge, Error 900.01\nVersion 1.0 - Document Revision",
                "metadata": {"chunk_type": "mixed"},
            },
        ]

        processor.db_adapter.get_chunks_by_document.return_value = mixed_chunks

        # Process multimodal document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="AUTO", stage_tracker=mock_stage_tracker
        )

        # Verify mixed content extraction
        error_codes = result["error_codes"]
        versions = result["versions"]

        assert len(error_codes) >= 3  # Should find error codes from multiple manufacturers
        assert len(versions) >= 3  # Should find multiple version types

        # Verify manufacturer diversity
        error_code_strings = [ec.error_code for ec in error_codes]
        assert any(code in error_code_strings for code in ["13.A1.B2", "49.4C02"])  # HP
        assert any(code in error_code_strings for code in ["C-2557"])  # Konica Minolta
        assert any(code in error_code_strings for code in ["900.01"])  # Lexmark

    @pytest.mark.asyncio
    async def test_process_empty_document(self, mock_processor, mock_stage_tracker):
        """Test processing document with no extractable metadata."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock empty chunks
        empty_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "This document contains no error codes or version information.",
                "metadata": {"chunk_type": "general"},
            }
        ]

        processor.db_adapter.get_chunks_by_document.return_value = empty_chunks

        # Process empty document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="AUTO", stage_tracker=mock_stage_tracker
        )

        # Verify empty results
        assert result["success"] is True
        assert len(result["error_codes"]) == 0
        assert len(result["versions"]) == 0
        assert result["statistics"]["chunks_processed"] == 1
        assert result["statistics"]["error_codes_found"] == 0
        assert result["statistics"]["versions_found"] == 0

    @pytest.mark.asyncio
    async def test_process_large_document(self, mock_processor, mock_stage_tracker):
        """Test processing large document with many chunks."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Create many chunks
        large_chunks = []
        for i in range(50):
            chunk = {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": i,
                "page_start": i + 1,
                "page_end": i + 1,
                "content": f"Error 13.A1.B2: Paper jam in tray {i % 3 + 1}. Solution: Remove paper.",
                "metadata": {"chunk_type": "error_codes"},
            }
            large_chunks.append(chunk)

        processor.db_adapter.get_chunks_by_document.return_value = large_chunks

        # Process large document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Verify large document processing
        assert result["success"] is True
        assert result["statistics"]["chunks_processed"] == 50
        assert len(result["error_codes"]) >= 1  # Should find error codes

    @pytest.mark.asyncio
    async def test_error_handling_during_processing(self, mock_processor, sample_document_data, mock_stage_tracker):
        """Test error handling during document processing."""
        processor = mock_processor
        document_id = sample_document_data["id"]

        # Mock database adapter to raise an exception
        processor.db_adapter.get_chunks_by_document.side_effect = Exception("Database error")

        # Process document should handle error gracefully
        with pytest.raises(Exception):
            await processor.process_document_async(
                document_id=document_id,
                manufacturer=sample_document_data["manufacturer"],
                stage_tracker=mock_stage_tracker,
            )

        # Verify stage tracker error handling
        assert mock_stage_tracker.set_stage.called

    @pytest.mark.asyncio
    async def test_database_integration(self, mock_processor, sample_chunks, mock_stage_tracker):
        """Test database integration for metadata persistence."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.db_adapter.get_chunks_by_document.return_value = sample_chunks

        # Process document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Verify database calls for error codes
        error_code_calls = processor.db_adapter.create_error_code.call_args_list
        assert len(error_code_calls) >= 2

        for call in error_code_calls:
            error_code = call[0][0]  # First argument
            assert isinstance(error_code, ExtractedErrorCode)
            assert error_code.document_id == document_id
            assert hasattr(error_code, "error_code")
            assert hasattr(error_code, "error_description")

    @pytest.mark.asyncio
    async def test_stage_tracking_integration(self, mock_processor, sample_chunks, mock_stage_tracker):
        """Test stage tracking integration during processing."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.db_adapter.get_chunks_by_document.return_value = sample_chunks

        # Process document
        await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Verify stage tracker calls
        assert mock_stage_tracker.set_stage.called
        assert mock_stage_tracker.complete_stage.called

        # Check stage tracker call arguments
        stage_calls = mock_stage_tracker.set_stage.call_args_list
        assert any("metadata" in str(call) for call in stage_calls)

    @pytest.mark.asyncio
    async def test_processing_statistics(self, mock_processor, sample_chunks, mock_stage_tracker):
        """Test processing statistics collection."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.db_adapter.get_chunks_by_document.return_value = sample_chunks

        # Process document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Verify statistics
        statistics = result["statistics"]
        assert "chunks_processed" in statistics
        assert "error_codes_found" in statistics
        assert "versions_found" in statistics
        assert "processing_time_seconds" in statistics

        assert statistics["chunks_processed"] == len(sample_chunks)
        assert statistics["error_codes_found"] >= 2
        assert statistics["versions_found"] >= 2
        assert statistics["processing_time_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_manufacturer_specific_processing(self, mock_processor, mock_stage_tracker):
        """Test manufacturer-specific processing behavior."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Test different manufacturers
        manufacturers = ["HP", "Konica Minolta", "Lexmark", "Canon"]

        for manufacturer in manufacturers:
            # Create manufacturer-specific chunks
            chunks = [
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_index": 0,
                    "page_start": 1,
                    "page_end": 1,
                    "content": f"{manufacturer} Error Codes - Test content",
                    "metadata": {"chunk_type": "error_codes"},
                }
            ]

            processor.db_adapter.get_chunks_by_document.return_value = chunks

            # Process with specific manufacturer
            result = await processor.process_document_async(
                document_id=document_id, manufacturer=manufacturer, stage_tracker=mock_stage_tracker
            )

            # Verify manufacturer-specific processing
            assert result["success"] is True
            assert "error_codes" in result
            assert "versions" in result

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, mock_processor, mock_stage_tracker):
        """Test concurrent processing of multiple documents."""
        processor = mock_processor

        # Create multiple document scenarios
        documents = []
        for i in range(3):
            document_id = str(uuid.uuid4())
            chunks = [
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_index": 0,
                    "page_start": 1,
                    "page_end": 1,
                    "content": f"Error 13.A1.B2: Paper jam in document {i}",
                    "metadata": {"chunk_type": "error_codes"},
                }
            ]

            processor.db_adapter.get_chunks_by_document.return_value = chunks
            documents.append(document_id)

        # Process documents concurrently
        results = []
        for document_id in documents:
            result = await processor.process_document_async(
                document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
            )
            results.append(result)

        # Verify all documents processed successfully
        assert len(results) == 3
        for result in results:
            assert result["success"] is True
            assert len(result["error_codes"]) >= 1


@pytest.mark.skip(
    reason="Legacy performance tests for old MetadataProcessor API; replaced by BaseProcessor-aligned tests."
)
@pytest.mark.metadata
@pytest.mark.e2e
@pytest.mark.slow
class TestMetadataProcessorPerformance:
    """Performance tests for MetadataProcessorAI."""

    @pytest.mark.asyncio
    async def test_processing_performance_large_document(self, mock_processor, mock_stage_tracker):
        """Test processing performance with large document."""
        import time

        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Create large document (100 chunks)
        large_chunks = []
        for i in range(100):
            chunk = {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": i,
                "page_start": i + 1,
                "page_end": i + 1,
                "content": "Error 13.A1.B2: Paper jam. Edition 3, 5/2024. FW 4.2.",
                "metadata": {"chunk_type": "mixed"},
            }
            large_chunks.append(chunk)

        processor.db_adapter.get_chunks_by_document.return_value = large_chunks

        # Measure processing time
        start_time = time.time()
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )
        end_time = time.time()

        # Verify performance
        processing_time = end_time - start_time
        assert result["success"] is True
        assert result["statistics"]["chunks_processed"] == 100
        assert processing_time < 30.0  # Should complete within 30 seconds

    @pytest.mark.asyncio
    async def test_memory_usage_processing(self, mock_processor, mock_stage_tracker):
        """Test memory usage during processing."""
        import os

        import psutil

        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create medium-sized document
        medium_chunks = []
        for i in range(50):
            chunk = {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": i,
                "page_start": i + 1,
                "page_end": i + 1,
                "content": "Error 13.A1.B2: Paper jam. " * 100,  # Larger content
                "metadata": {"chunk_type": "error_codes"},
            }
            medium_chunks.append(chunk)

        processor.db_adapter.get_chunks_by_document.return_value = medium_chunks

        # Process document
        result = await processor.process_document_async(
            document_id=document_id, manufacturer="HP", stage_tracker=mock_stage_tracker
        )

        # Check memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Verify reasonable memory usage
        assert result["success"] is True
        assert memory_increase < 100  # Should not increase by more than 100MB


class FakeDatabaseResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeDatabaseTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self._last_operation = None
        self._pending_row = None
        self._pending_update = None
        self._last_filter = None

    def insert(self, row):
        self._last_operation = "insert"
        self._pending_row = row
        return self

    def update(self, values):
        self._last_operation = "update"
        self._pending_update = values
        return self

    def eq(self, column, value):
        self._last_filter = (column, value)
        return self

    def execute(self):
        if self.name == "error_codes" and self._last_operation == "insert":
            if getattr(self.client, "fail_error_code_inserts", False):
                raise Exception("Simulated error_codes insert failure")
            self.client.error_code_rows.append(self._pending_row)
            return FakeDatabaseResult([self._pending_row])

        if self.name == "documents" and self._last_operation == "update":
            if getattr(self.client, "fail_document_updates", False):
                raise Exception("Simulated document update failure")
            update_record = {
                "document_id": self._last_filter,
                "values": self._pending_update,
            }
            self.client.document_updates.append(update_record)
            return FakeDatabaseResult([self._pending_update])

        return FakeDatabaseResult([])


class FakeDatabaseClient:
    def __init__(self):
        self.error_code_rows = []
        self.document_updates = []
        self.fail_error_code_inserts = False
        self.fail_document_updates = False

    def table(self, name):
        return FakeDatabaseTable(name, self)


class FakeDatabaseService:
    def __init__(self):
        self.client = FakeDatabaseClient()


@pytest.mark.metadata
@pytest.mark.e2e
class TestMetadataProcessorAIDatabasePersistenceV2:
    @pytest.fixture
    def database_service(self):
        return FakeDatabaseService()

    @pytest.fixture
    def processor(
        self,
        database_service,
        mock_error_code_extractor,
        mock_version_extractor,
    ):
        """MetadataProcessorAI wired to fake database-style database_service and mocks."""
        processor = MetadataProcessorAI(database_service=database_service)
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

        def fake_version_extract(pdf_path: Path):
            versions = mock_version_extractor.extract_from_text(
                "Edition 3, 5/2024",
                manufacturer="AUTO",
            )
            return versions[0].version_string if versions else None

        mock_version_extractor.extract = MagicMock(side_effect=fake_version_extract)

        async def fake_get_document_manufacturer(document_id: str) -> str:
            return "HP"

        processor._get_document_manufacturer = fake_get_document_manufacturer  # type: ignore[attr-defined]

        return processor

    @pytest.mark.asyncio
    async def test_safe_process_persists_error_codes_and_version(
        self,
        processor,
        database_service,
        tmp_path,
    ):
        """safe_process() persists extracted error codes and version via client.table()."""
        pdf_path = tmp_path / "test_metadata_db.pdf"
        pdf_path.write_text("dummy pdf content")

        context = ProcessingContext(
            document_id="doc-db-123",
            file_path=str(pdf_path),
            document_type="service_manual",
            manufacturer="HP",
        )

        result = await processor.safe_process(context)

        assert result.success is True
        assert result.processor == "metadata_processor_ai"
        assert result.data.get("error_codes_extracted", 0) >= 1
        assert result.data.get("version_info") == "Edition 3, 5/2024"

        # Verify error_codes persisted via database-style client.table('error_codes').insert()
        error_rows = database_service.client.error_code_rows
        assert len(error_rows) >= 1
        row = error_rows[0]
        assert row["document_id"] == "doc-db-123"
        # Core error code details mapped to krai_intelligence.error_codes
        assert row["error_code"] is not None
        assert row["error_description"] is not None
        assert "solution_text" in row
        assert row["page_number"] is not None
        # Quality and context metadata
        assert "confidence_score" in row
        assert "severity_level" in row
        assert "context_text" in row

        # Verify document version update persisted via client.table('documents').update().eq().execute()
        updates = database_service.client.document_updates
        assert len(updates) == 1
        update = updates[0]
        assert update["where"] == ("id", "doc-db-123")
        assert update["values"]["version"] == "Edition 3, 5/2024"

    @pytest.mark.asyncio
    async def test_db_errors_do_not_break_safe_process(
        self,
        processor,
        database_service,
        tmp_path,
    ):
        """Failures during DB insert/update are logged and do not crash safe_process()."""
        pdf_path = tmp_path / "test_metadata_db_error.pdf"
        pdf_path.write_text("dummy pdf content")

        # Force failures in both helpers
        database_service.client.fail_error_code_inserts = True
        database_service.client.fail_document_updates = True

        context = ProcessingContext(
            document_id="doc-db-err",
            file_path=str(pdf_path),
            document_type="service_manual",
            manufacturer="HP",
        )

        result = await processor.safe_process(context)

        # Even with DB failures, extraction still succeeds and result is successful
        assert result.success is True
        assert result.data.get("error_codes_extracted", 0) >= 1
        assert result.data.get("version_info") == "Edition 3, 5/2024"

        # No rows/updates should be recorded due to simulated failures
        assert database_service.client.error_code_rows == []
        assert database_service.client.document_updates == []
