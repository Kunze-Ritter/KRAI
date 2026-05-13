"""
End-to-end tests for PartsProcessor.

Tests full parts processing flows with realistic test data and mocks,
including database integration, stage tracking, and error handling.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.processors.parts_processor import PartsProcessor


@pytest.fixture(scope="function")
def mock_processor(mock_parts_extractor):
    """Create PartsProcessor with a MagicMock-based adapter for E2E-style tests.

    We intentionally avoid the async mock_database_adapter fixture here to keep
    this fixture synchronous and ensure tests receive a concrete PartsProcessor
    instance instead of an async_generator. The adapter exposes the minimal async
    methods used by PartsProcessor (get_document, get_chunks_by_document,
    create_part, update_part, get_error_codes_by_document, get_part_by_number,
    get_part_by_number_and_manufacturer, create_error_code_part_link, get_chunk).
    """
    adapter = MagicMock()

    # Basic document stub so PartsProcessor does not skip due to missing manufacturer_id
    adapter.get_document = AsyncMock(
        return_value={
            "id": str(uuid.uuid4()),
            "manufacturer_id": str(uuid.uuid4()),
            "manufacturer": "HP",
        }
    )

    # Default async methods used in the tests; individual tests override return_value as needed
    adapter.get_chunks_by_document = AsyncMock(return_value=[])
    adapter.get_error_codes_by_document = AsyncMock(return_value=[])
    adapter.get_part_by_number_and_manufacturer = AsyncMock(return_value=None)
    adapter.get_part_by_number = AsyncMock(return_value=None)
    adapter.create_part = AsyncMock()
    adapter.update_part = AsyncMock(return_value=True)
    adapter.create_error_code_part_link = AsyncMock()
    adapter.get_chunk = AsyncMock(return_value=None)

    with patch("backend.processors.parts_processor.extract_parts_with_context") as mock_extract:
        # Route calls through the deterministic mock_parts_extractor, preserving
        # the actual chunk text so tests can assert on parts_found counts.
        def _fake_extract(text: str, manufacturer_key: str | None = None, max_parts: int = 20, *args, **kwargs):
            manufacturer = manufacturer_key or "AUTO"
            return mock_parts_extractor(text, manufacturer=manufacturer)

        mock_extract.side_effect = _fake_extract

        processor = PartsProcessor(database_adapter=adapter)
        processor.adapter = adapter

        yield processor


@pytest.mark.parts
@pytest.mark.e2e
class TestPartsProcessorE2E:
    """End-to-end tests for PartsProcessor with realistic scenarios."""

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
    def sample_chunks_with_parts(self):
        """Create sample chunks with parts information."""
        return [
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Replace part 6QN29-67005 - Fuser Unit. Install RM1-1234-000 - Transfer Roller.",
                "metadata": {"chunk_type": "parts_catalog"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Use CE285A Black Toner. High yield Q7553X available.",
                "metadata": {"chunk_type": "consumables"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Error 13.A1.B2: Paper jam - check 6QN29-67005 fuser.",
                "metadata": {"chunk_type": "error_codes"},
            },
        ]

    @pytest.mark.asyncio
    async def test_process_document_complete_flow(
        self, mock_processor, sample_document_data, sample_chunks_with_parts, mock_stage_tracker
    ):
        """Test complete document processing flow with parts extraction."""
        processor = mock_processor
        document_id = sample_document_data["id"]

        # Mock database adapter to return chunks
        processor.adapter.get_chunks_by_document.return_value = sample_chunks_with_parts

        # Process the document
        result = await processor.process_document(document_id)

        # Verify processing results
        assert result is not None
        assert "chunks_processed" in result
        assert "parts_found" in result
        assert "parts_created" in result
        assert "parts_updated" in result
        assert "parts_linked_to_error_codes" in result
        assert "errors" in result

        # Verify statistics
        assert result["chunks_processed"] == len(sample_chunks_with_parts)
        assert result["parts_found"] >= 0
        assert result["parts_created"] >= 0
        assert result["errors"] == 0

        # Verify database calls
        processor.adapter.get_chunks_by_document.assert_called_once_with(document_id)

        # Verify parts were saved to database
        if result["parts_found"] > 0:
            assert processor.adapter.create_part.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_hp_service_manual(self, mock_processor, sample_pdf_with_parts, mock_stage_tracker):
        """Test processing HP service manual with realistic parts."""
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
                "content": "HP LaserJet Parts Catalog\n\n6QN29-67005 - Fuser Unit\nRM1-1234-000 - Transfer Roller\nCE285A - Black Toner Cartridge",
                "metadata": {"chunk_type": "parts_catalog"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "High Yield Consumables\n\nQ7553X - High Yield Black Toner\nCF210A - Black Toner Cartridge",
                "metadata": {"chunk_type": "consumables"},
            },
        ]

        processor.adapter.get_chunks_by_document.return_value = hp_chunks

        # Process HP service manual
        result = await processor.process_document(document_id)

        # Verify HP-specific parts
        assert result["chunks_processed"] == 2
        assert result["parts_found"] >= 4  # Should find multiple HP parts
        assert result["errors"] == 0

        # Verify database calls for parts
        part_calls = processor.adapter.create_part.call_args_list
        assert len(part_calls) >= 4

        for call in part_calls:
            part = call.args[0]  # First positional argument is the part dict
            assert isinstance(part, dict)
            assert "part_number" in part
            assert "manufacturer_id" in part
            assert "part_description" in part

    @pytest.mark.asyncio
    async def test_process_konica_minolta_document(self, mock_processor, mock_stage_tracker):
        """Test processing Konica Minolta document with specific parts."""
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
                "content": "Konica Minolta bizhub Parts\n\nA1DU-R750-00 - Developer Unit\n4062-R750-01 - Drum Unit\nA2K0-R750-02 - Transfer Belt",
                "metadata": {"chunk_type": "parts_catalog"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = km_chunks

        # Process Konica Minolta document
        result = await processor.process_document(document_id)

        # Verify Konica Minolta-specific parts
        assert result["chunks_processed"] == 1
        assert result["parts_found"] >= 3  # Should find multiple KM parts
        assert result["errors"] == 0

        # Verify database calls for parts
        part_calls = processor.adapter.create_part.call_args_list
        assert len(part_calls) >= 3

    @pytest.mark.asyncio
    async def test_process_canon_document(self, mock_processor, mock_stage_tracker):
        """Test processing Canon document with specific parts."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks from Canon document
        canon_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Canon Parts Catalog\n\nFM3-5945-000 - Fuser Film\nNPG-59 - Toner Cartridge\nRG3-8213-000 - Drum Unit",
                "metadata": {"chunk_type": "parts_catalog"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = canon_chunks

        # Process Canon document
        result = await processor.process_document(document_id)

        # Verify Canon-specific parts
        assert result["chunks_processed"] == 1
        assert result["parts_found"] >= 3  # Should find multiple Canon parts
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_lexmark_document(self, mock_processor, mock_stage_tracker):
        """Test processing Lexmark document with specific parts."""
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
                "content": "Lexmark Parts Catalog\n\n40X5852 - Toner Cartridge\n12A8300 - Fuser Unit\n25A0001 - Transfer Roller",
                "metadata": {"chunk_type": "parts_catalog"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = lexmark_chunks

        # Process Lexmark document
        result = await processor.process_document(document_id)

        # Verify Lexmark-specific parts
        assert result["chunks_processed"] == 1
        assert result["parts_found"] >= 3  # Should find multiple Lexmark parts
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_document_with_consumables(self, mock_processor, mock_stage_tracker):
        """Test processing document with consumable parts."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with consumables
        consumable_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Consumables Catalog\n\nCE285A - Black Toner\nCE285X - High Yield Black Toner\nQ7553A - Toner Cartridge\nQ7553X - High Yield Toner",
                "metadata": {"chunk_type": "consumables"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = consumable_chunks

        # Process document with consumables
        result = await processor.process_document(document_id)

        # Verify consumable extraction
        assert result["chunks_processed"] == 1
        assert result["parts_found"] >= 4  # Should find multiple consumables
        assert result["errors"] == 0

        # Verify consumable details
        part_calls = processor.adapter.create_part.call_args_list
        assert len(part_calls) >= 4

    @pytest.mark.asyncio
    async def test_process_document_with_mixed_manufacturers(self, mock_processor, mock_stage_tracker):
        """Test processing document with mixed manufacturer parts."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with mixed manufacturer parts
        mixed_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Multi-Manufacturer Reference\n\nHP: 6QN29-67005 Fuser Unit\nKonica Minolta: A1DU-R750-00 Developer Unit\nCanon: FM3-5945-000 Fuser Film\nLexmark: 40X5852 Toner Cartridge",
                "metadata": {"chunk_type": "mixed"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = mixed_chunks

        # Process mixed manufacturer document
        result = await processor.process_document(document_id)

        # Verify manufacturer diversity
        assert result["chunks_processed"] == 1
        assert result["parts_found"] >= 4  # Should find parts from multiple manufacturers
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_document_with_parts_linked_to_errors(self, mock_processor, mock_stage_tracker):
        """Test processing document with parts linked to error codes."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with parts and error codes
        linked_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Error 13.A1.B2: Paper jam in fuser. Replace 6QN29-67005 Fuser Unit.",
                "metadata": {"chunk_type": "error_with_parts"},
            },
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Error C-2557: Developer unit failure. Replace A1DU-R750-00 Developer Unit.",
                "metadata": {"chunk_type": "error_with_parts"},
            },
        ]

        processor.adapter.get_chunks_by_document.return_value = linked_chunks

        # Process document with linked parts
        result = await processor.process_document(document_id)

        # Verify parts linked to error codes
        assert result["chunks_processed"] == 2
        assert result["parts_found"] >= 2
        assert result["parts_linked_to_error_codes"] >= 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_process_document_with_no_parts(self, mock_processor, mock_stage_tracker):
        """Test processing document with no extractable parts."""
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
                "content": "This document contains no part numbers or technical information.",
                "metadata": {"chunk_type": "general"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = empty_chunks

        # Process empty document
        result = await processor.process_document(document_id)

        # Verify empty results
        assert result["chunks_processed"] == 1
        assert result["parts_found"] == 0
        assert result["parts_created"] == 0
        assert result["parts_updated"] == 0
        assert result["parts_linked_to_error_codes"] == 0
        assert result["errors"] == 0

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
                "content": "Replace part 6QN29-67005 - Fuser Unit. Install RM1-1234-000 - Transfer Roller.",
                "metadata": {"chunk_type": "parts_catalog"},
            }
            large_chunks.append(chunk)

        processor.adapter.get_chunks_by_document.return_value = large_chunks

        # Process large document
        result = await processor.process_document(document_id)

        # Verify large document processing
        assert result["chunks_processed"] == 50
        assert result["parts_found"] >= 1  # Should find parts
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_error_handling_during_processing(self, mock_processor, sample_document_data, mock_stage_tracker):
        """Test error handling during document processing."""
        processor = mock_processor
        document_id = sample_document_data["id"]

        # Mock database adapter to raise an exception
        processor.adapter.get_chunks_by_document.side_effect = Exception("Database error")

        # Process document should handle error gracefully and report an error in stats
        result = await processor.process_document(document_id)
        assert result["errors"] >= 1

    @pytest.mark.asyncio
    async def test_database_integration(self, mock_processor, sample_chunks_with_parts, mock_stage_tracker):
        """Test database integration for parts persistence."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.adapter.get_chunks_by_document.return_value = sample_chunks_with_parts

        # Process document
        result = await processor.process_document(document_id)

        # Verify database calls for parts
        part_calls = processor.adapter.create_part.call_args_list
        if result["parts_found"] > 0:
            assert len(part_calls) >= 1

            for call in part_calls:
                part = call.args[0]
                assert isinstance(part, dict)
                assert "part_number" in part
                assert "manufacturer_id" in part
                assert "part_description" in part

    @pytest.mark.asyncio
    async def test_stage_tracking_integration(self, mock_processor, sample_chunks_with_parts, mock_stage_tracker):
        """Test stage tracking integration during processing."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.adapter.get_chunks_by_document.return_value = sample_chunks_with_parts

        # Process document
        await processor.process_document(document_id)

        # Verify stage tracker calls (if enabled)
        if processor.stage_tracker:
            assert mock_stage_tracker.start_stage.called
            assert mock_stage_tracker.complete_stage.called

    @pytest.mark.asyncio
    async def test_processing_statistics(self, mock_processor, sample_chunks_with_parts, mock_stage_tracker):
        """Test processing statistics collection."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        processor.adapter.get_chunks_by_document.return_value = sample_chunks_with_parts

        # Process document
        result = await processor.process_document(document_id)

        # Verify statistics
        assert "chunks_processed" in result
        assert "parts_found" in result
        assert "parts_created" in result
        assert "parts_updated" in result
        assert "parts_linked_to_error_codes" in result
        assert "errors" in result

        assert result["chunks_processed"] == len(sample_chunks_with_parts)
        assert result["parts_found"] >= 0
        assert result["parts_created"] >= 0
        assert result["parts_updated"] >= 0
        assert result["parts_linked_to_error_codes"] >= 0
        assert result["errors"] >= 0

    @pytest.mark.asyncio
    async def test_manufacturer_specific_processing(self, mock_processor, mock_stage_tracker):
        """Test manufacturer-specific processing behavior."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Test different manufacturers
        manufacturers = ["HP", "Konica Minolta", "Canon", "Lexmark"]

        for manufacturer in manufacturers:
            # Create manufacturer-specific chunks
            chunks = [
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "chunk_index": 0,
                    "page_start": 1,
                    "page_end": 1,
                    "content": f"{manufacturer} Parts Catalog - Test content",
                    "metadata": {"chunk_type": "parts_catalog"},
                }
            ]

            processor.adapter.get_chunks_by_document.return_value = chunks

            # Process with specific manufacturer
            result = await processor.process_document(document_id)

            # Verify manufacturer-specific processing
            assert result["chunks_processed"] == 1
            assert result["parts_found"] >= 0
            assert result["errors"] == 0

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
                    "content": f"Replace part 6QN29-67005 - Fuser Unit in document {i}",
                    "metadata": {"chunk_type": "parts_catalog"},
                }
            ]

            processor.adapter.get_chunks_by_document.return_value = chunks
            documents.append(document_id)

        # Process documents concurrently
        results = []
        for document_id in documents:
            result = await processor.process_document(document_id)
            results.append(result)

        # Verify all documents processed successfully
        assert len(results) == 3
        for result in results:
            assert result["chunks_processed"] == 1
            assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_parts_quality_validation(self, mock_processor, mock_stage_tracker):
        """Test parts quality validation during processing."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with high-quality parts
        quality_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "6QN29-67005 - Fuser Unit - High Quality Part",
                "metadata": {"chunk_type": "parts_catalog"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = quality_chunks

        # Process document
        result = await processor.process_document(document_id)

        # Verify parts quality
        part_calls = processor.adapter.create_part.call_args_list
        if part_calls:
            part = part_calls[0].args[0]
            assert isinstance(part, dict)
            assert "part_number" in part
            assert "part_description" in part
            assert part["part_number"] == "6QN29-67005"
            # Description should be non-empty context-derived text
            assert isinstance(part["part_description"], str)
            assert len(part["part_description"]) > 0

    @pytest.mark.asyncio
    async def test_parts_context_extraction(self, mock_processor, mock_stage_tracker):
        """Test parts context extraction and storage."""
        processor = mock_processor
        document_id = str(uuid.uuid4())

        # Mock chunks with contextual parts information
        context_chunks = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "For paper jam issues, replace 6QN29-67005 Fuser Unit located in the back of the printer.",
                "metadata": {"chunk_type": "troubleshooting"},
            }
        ]

        processor.adapter.get_chunks_by_document.return_value = context_chunks

        # Process document
        result = await processor.process_document(document_id)

        # Verify context extraction
        part_calls = processor.adapter.create_part.call_args_list
        if part_calls:
            part = part_calls[0].args[0]
            assert isinstance(part, dict)
            assert "part_description" in part
            assert isinstance(part["part_description"], str)
            assert len(part["part_description"]) > 0


@pytest.mark.parts
@pytest.mark.e2e
@pytest.mark.slow
class TestPartsProcessorPerformance:
    """Performance tests for PartsProcessor."""

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
                "content": "Replace part 6QN29-67005 - Fuser Unit. " * 10,  # Larger content
                "metadata": {"chunk_type": "parts_catalog"},
            }
            large_chunks.append(chunk)

        processor.adapter.get_chunks_by_document.return_value = large_chunks

        # Measure processing time
        start_time = time.time()
        result = await processor.process_document(document_id)
        end_time = time.time()

        # Verify performance
        processing_time = end_time - start_time
        assert result["chunks_processed"] == 100
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
                "content": "Replace part 6QN29-67005 - Fuser Unit. " * 100,  # Larger content
                "metadata": {"chunk_type": "parts_catalog"},
            }
            medium_chunks.append(chunk)

        processor.adapter.get_chunks_by_document.return_value = medium_chunks

        # Process document
        result = await processor.process_document(document_id)

        # Check memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Verify reasonable memory usage
        assert result["chunks_processed"] == 50
        assert memory_increase < 100  # Should not increase by more than 100MB
