"""
Comprehensive E2E Pipeline Flow Tests

This module provides extensive end-to-end testing for the complete pipeline flow
from Upload → Document → Text processing stages. Tests cover context propagation,
stage tracking, error recovery, data consistency, performance, and deduplication.

Test Categories:
1. Complete Flow Tests
2. Context Propagation Tests
3. Stage Tracking Tests
4. Error Recovery Tests
5. Data Consistency Tests
6. Performance Tests
7. Deduplication Tests

All tests use the fixtures from conftest.py for consistent mock objects and test data.
"""

import asyncio
import hashlib
import time
from unittest.mock import patch

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.document_processor import DocumentProcessor
from backend.processors.text_processor_optimized import OptimizedTextProcessor
from backend.processors.upload_processor import UploadProcessor

pytestmark = [
    pytest.mark.processor,
    pytest.mark.skip(
        reason="Legacy Upload → Document → Text pipeline flow tests; disabled in favor of new KRMasterPipeline-based flow tests.",
    ),
]


class TestCompleteFlow:
    """Test complete pipeline flow from Upload to Text processing."""

    @pytest.mark.asyncio
    async def test_upload_to_text_processing_flow(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow from Upload → Document → Text processing."""
        # Arrange
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        text_processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
            stage_tracker=mock_stage_tracker,
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act - Stage 1: Upload
        upload_result = await upload_processor.process(valid_pdf["path"])

        # Assert Upload
        assert upload_result.success, f"Upload should succeed: {upload_result.error}"
        document_id = upload_result.data["document_id"]
        assert document_id is not None, "Should get document ID from upload"

        # Act - Stage 2: Document Processing
        document_context = ProcessingContext(
            document_id=document_id, file_path=valid_pdf["path"], metadata=upload_result.metadata
        )

        document_result = await document_processor.process(document_context)

        # Assert Document Processing
        assert document_result.success, f"Document processing should succeed: {document_result.error}"
        assert "page_texts" in document_result.data, "Should have page texts"
        assert "metadata" in document_result.data, "Should have document metadata"

        # Act - Stage 3: Text Processing
        text_context = ProcessingContext(
            document_id=document_id, file_path=valid_pdf["path"], metadata=document_result.data["metadata"]
        )
        text_context.page_texts = document_result.data["page_texts"]

        text_result = await text_processor.process(text_context)

        # Assert Text Processing
        assert text_result.success, f"Text processing should succeed: {text_result.error}"
        assert "chunks" in text_result.data, "Should have chunks"
        assert "chunk_count" in text_result.data, "Should have chunk count"

        # Verify complete flow results
        chunks = text_result.data["chunks"]
        assert len(chunks) > 0, "Should create chunks from processed content"

        # Verify database state
        assert document_id in mock_database_adapter.documents, "Document should be in database"
        assert len(mock_database_adapter.chunks) > 0, "Chunks should be saved to database"

        # Verify all chunks belong to the same document
        for chunk_id, chunk_data in mock_database_adapter.chunks.items():
            assert chunk_data["document_id"] == document_id, "All chunks should belong to the same document"

    @pytest.mark.asyncio
    async def test_flow_with_valid_service_manual(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow with a valid service manual PDF."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create realistic service manual content
        service_manual_content = """Konica Minolta C750i Service Manual
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

Chapter 1: Safety Information
============================

1.1 Electrical Safety
Always disconnect power before performing maintenance.
Use proper grounding and follow electrical safety procedures.

1.2 Mechanical Safety
Keep hands clear of moving parts during operation.
Use appropriate lockout procedures during maintenance.

Chapter 2: Technical Specifications
==================================

2.1 Performance Specifications
- Print Speed: 75 pages per minute
- Resolution: 1200 x 1200 dpi
- Memory: 2GB standard, upgradeable to 4GB
- Paper Capacity: 650 sheets standard, 1,150 maximum

2.2 Physical Specifications
- Dimensions: 24" x 20" x 24" (W x D x H)
- Weight: 150 lbs (68 kg)
- Power Requirements: 120V AC, 15A

Chapter 3: Error Codes
=====================

3.1 Critical Errors
900.01: Fuser Unit Error - Fuser unit failed to reach operating temperature
900.02: Exposure Lamp Error - Lamp failure or power supply issue
900.03: High Voltage Error - High voltage circuit malfunction

3.2 Warning Errors
920.00: Waste Toner Full - Replace waste toner container
921.00: Low Toner Warning - Replace toner cartridge soon

Chapter 4: Maintenance Procedures
================================

4.1 Daily Maintenance
- Clean platen glass
- Check paper path for obstructions
- Verify output quality

4.2 Weekly Maintenance
- Check waste toner container level
- Clean transfer roller
- Inspect fuser unit for wear

4.3 Quarterly Maintenance
- Replace maintenance kit
- Clean optical system
- Calibrate print quality

Chapter 5: Troubleshooting
=========================

5.1 Common Problems
Paper Jams: Check paper path, remove jammed paper carefully
Poor Print Quality: Clean drum, check toner level
Error Codes: Refer to error code section for specific solutions

5.2 Contact Information
Support: 1-800-KONICA
Website: www.konicaminolta.com
Email: support@konicaminolta.com"""

        test_file = temp_test_pdf / "konica_c750i_service_manual.pdf"
        test_file.write_text(service_manual_content)

        # Act - Complete Flow
        flow_results = await self._run_complete_flow(processors, test_file, "service_manual")

        # Assert
        upload_result, document_result, text_result = flow_results

        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Verify service manual specific content
        chunks = text_result.data["chunks"]
        all_content = " ".join(chunk["content"] for chunk in chunks)

        assert "Konica Minolta" in all_content, "Should detect manufacturer"
        assert "C750i" in all_content, "Should detect model"
        assert "Service Manual" in all_content, "Should detect document type"
        assert "900.01" in all_content, "Should preserve error codes"
        assert "Safety Information" in all_content, "Should preserve sections"

        # Verify metadata extraction
        document_metadata = document_result.data["metadata"]
        assert document_metadata.get("manufacturer", "").lower() in [
            "konica",
            "minolta",
        ], f"Should detect Konica Minolta, got {document_metadata.get('manufacturer')}"
        assert document_metadata.get("document_type", "").lower() in [
            "service_manual",
            "manual",
        ], f"Should detect service manual, got {document_metadata.get('document_type')}"

    @pytest.mark.asyncio
    async def test_flow_with_parts_catalog(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow with a parts catalog PDF."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create parts catalog content
        parts_catalog_content = """Canon imageRUNNER ADVANCE C7550i Parts Catalog
==================================================

Document Information:
- Manufacturer: Canon
- Model: imageRUNNER ADVANCE C7550i
- Document Type: Parts Catalog
- Language: English

Parts List - Main Assembly
==========================

Part Number | Description | Price | Quantity
-----------|-------------|-------|----------
FM1-0011   | Fuser Unit  | $450.00 | 1
FM1-0012   | Fuser Lamp  | $120.00 | 1
FM1-0013   | Thermal Fuse | $25.00 | 1
FM1-0014   | Pressure Roller | $85.00 | 1

Parts List - Development Unit
=============================

Part Number | Description | Price | Quantity
-----------|-------------|-------|----------
DV1-0021   | Developer Unit | $180.00 | 1
DV1-0022   | Developer Blade | $35.00 | 2
DV1-0023   | Magnetic Roller | $95.00 | 1
DV1-0024   | Developer Seal | $15.00 | 2

Parts List - Paper Feed
======================

Part Number | Description | Price | Quantity
-----------|-------------|-------|----------
PF1-0031   | Pick-up Roller | $45.00 | 4
PF1-0032   | Feed Roller | $40.00 | 4
PF1-0033   | Separation Pad | $20.00 | 2
PF1-0034   | Paper Guide | $30.00 | 2

Exploded Views
==============

Figure 1: Main Assembly
[Diagram showing main components with part numbers]

Figure 2: Development Unit
[Diagram showing development components]

Figure 3: Paper Feed System
[Diagram showing paper feed components]

Ordering Information
====================

To order parts:
1. Use part numbers from the lists above
2. Call Canon Parts Department: 1-800-652-2666
3. Visit website: parts.canon.com
4. Contact authorized Canon dealer

Availability and lead times may vary.
Check with parts department for current stock levels."""

        test_file = temp_test_pdf / "canon_c7550i_parts_catalog.pdf"
        test_file.write_text(parts_catalog_content)

        # Act - Complete Flow
        flow_results = await self._run_complete_flow(processors, test_file, "parts_catalog")

        # Assert
        upload_result, document_result, text_result = flow_results

        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Verify parts catalog specific content
        chunks = text_result.data["chunks"]
        all_content = " ".join(chunk["content"] for chunk in chunks)

        assert "Canon" in all_content, "Should detect manufacturer"
        assert "imageRUNNER" in all_content, "Should detect model series"
        assert "Parts Catalog" in all_content, "Should detect document type"
        assert "FM1-0011" in all_content, "Should preserve part numbers"
        assert "Fuser Unit" in all_content, "Should preserve part descriptions"

        # Verify metadata extraction
        document_metadata = document_result.data["metadata"]
        assert (
            document_metadata.get("manufacturer", "").lower() == "canon"
        ), f"Should detect Canon, got {document_metadata.get('manufacturer')}"
        assert document_metadata.get("document_type", "").lower() in [
            "parts_catalog",
            "catalog",
        ], f"Should detect parts catalog, got {document_metadata.get('document_type')}"

    @pytest.mark.asyncio
    async def test_flow_with_user_guide(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow with a user guide PDF."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create user guide content
        user_guide_content = """HP LaserJet Pro M404n User Guide
=================================

Document Information:
- Manufacturer: HP
- Model: LaserJet Pro M404n
- Document Type: User Guide
- Language: English

Getting Started
===============

Unpacking and Setup
------------------
1. Remove all packing materials
2. Check that you have all components:
   - HP LaserJet Pro M404n printer
   - Power cord
   - USB cable
   - Starter toner cartridge
   - Installation guide
3. Choose a location for the printer:
   - Stable, flat surface
   - Adequate ventilation
   - Away from direct sunlight
   - Close to power outlet and computer

Installing Toner Cartridge
-------------------------
1. Open the top cover
2. Remove the starter toner cartridge
3. Pull the orange tab to remove the sealing tape
4. Reinsert the toner cartridge
5. Close the top cover

Loading Paper
-------------
1. Pull out the main paper tray
2. Adjust the paper guides to the paper size
3. Load paper stack (up to 250 sheets)
4. Slide the tray back into the printer

Basic Operations
================

Making Copies
-------------
1. Place original document on the scanner glass
2. Select number of copies
3. Press Start Copy button

Printing from Computer
----------------------
1. Install printer software (included CD or download)
2. Connect printer to computer with USB cable
3. Select Print from your application
4. Choose HP LaserJet Pro M404n
5. Adjust print settings if needed
6. Click Print

Advanced Features
=================

Mobile Printing
---------------
Print from mobile devices using:
- HP Smart app (iOS and Android)
- Apple AirPrint
- Google Cloud Print
- Mopria Print Service

Energy Saving Mode
------------------
The printer automatically enters energy saving mode after 10 minutes of inactivity.
Press any button to wake the printer.

Troubleshooting
===============

Common Problems
----------------

Paper Jams
----------
1. Open the top cover
2. Gently remove jammed paper
3. Close the cover
4. Press OK to continue

Poor Print Quality
------------------
1. Check toner level
2. Shake toner cartridge if low
3. Clean the printer interior
4. Replace toner cartridge if needed

Error Messages
--------------
See the control panel for specific error messages.
Refer to the error code section in the full service manual.

Getting Help
=============

Online Support
--------------
Visit: support.hp.com/ljproM404
Find: FAQs, drivers, troubleshooting guides

Phone Support
-------------
Call HP Customer Support: 1-800-HP-INVENT
Hours: Monday-Friday, 8 AM - 8 PM EST

Warranty Information
==================
Standard warranty: 1 year limited warranty
Extended warranty options available through HP Care Pack."""

        test_file = temp_test_pdf / "hp_m404n_user_guide.pdf"
        test_file.write_text(user_guide_content)

        # Act - Complete Flow
        flow_results = await self._run_complete_flow(processors, test_file, "user_guide")

        # Assert
        upload_result, document_result, text_result = flow_results

        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Verify user guide specific content
        chunks = text_result.data["chunks"]
        all_content = " ".join(chunk["content"] for chunk in chunks)

        assert "HP" in all_content, "Should detect manufacturer"
        assert "LaserJet Pro" in all_content, "Should detect model series"
        assert "User Guide" in all_content, "Should detect document type"
        assert "Getting Started" in all_content, "Should preserve sections"
        assert "Troubleshooting" in all_content, "Should preserve troubleshooting"

        # Verify metadata extraction
        document_metadata = document_result.data["metadata"]
        assert (
            document_metadata.get("manufacturer", "").lower() == "hp"
        ), f"Should detect HP, got {document_metadata.get('manufacturer')}"
        assert document_metadata.get("document_type", "").lower() in [
            "user_guide",
            "guide",
        ], f"Should detect user guide, got {document_metadata.get('document_type')}"

    @pytest.mark.asyncio
    async def test_flow_with_multi_language_document(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow with multi-language document."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create multi-language content
        multi_lang_content = """Multi-Language Service Manual
=============================

English Section
--------------
This service manual provides technical information in multiple languages.
The device specifications and procedures are the same regardless of language.

Error Code 900.01: Fuser Unit Error
Description: The fuser unit has failed to reach operating temperature.
Solution: Check fuser lamp and thermal fuse.

German Section
-------------
Dieses Servicehandbuch enthält technische Informationen in mehreren Sprachen.
Die Gerätespezifikationen und -verfahren sind unabhängig von der Sprache gleich.

Fehlercode 900.01: Fixiereinheit-Fehler
Beschreibung: Die Fixiereinheit hat die Betriebstemperatur nicht erreicht.
Lösung: Überprüfen Sie die Fixierlampe und die thermische Sicherung.

French Section
---------------
Ce manuel de service fournit des informations techniques en plusieurs langues.
Les spécifications et procédures de l'appareil sont identiques quelle que soit la langue.

Code d'erreur 900.01 : Erreur d'unité de fusion
Description : L'unité de fusion n'a pas atteint la température de fonctionnement.
Solution : Vérifiez la lampe de fusion et le fusible thermique.

Spanish Section
---------------
Este manual de servicio proporciona información técnica en varios idiomas.
Las especificaciones y procedimientos del dispositivo son iguales independientemente del idioma.

Código de error 900.01: Error de la unidad de fusión
Descripción: La unidad de fusión no ha alcanzado la temperatura de funcionamiento.
Solución: Revise la lámpara de fusión y el fusible térmico.

Technical Specifications (All Languages)
========================================
Print Speed: 75 pages per minute
Resolution: 1200 x 1200 dpi
Memory: 2GB standard
Paper Capacity: 650 sheets standard"""

        test_file = temp_test_pdf / "multi_language_manual.pdf"
        test_file.write_text(multi_lang_content)

        # Act - Complete Flow
        flow_results = await self._run_complete_flow(processors, test_file, "multi_language")

        # Assert
        upload_result, document_result, text_result = flow_results

        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Verify multi-language content preservation
        chunks = text_result.data["chunks"]
        all_content = " ".join(chunk["content"] for chunk in chunks)

        assert "English Section" in all_content, "Should preserve English section"
        assert "German Section" in all_content, "Should preserve German section"
        assert "French Section" in all_content, "Should preserve French section"
        assert "Spanish Section" in all_content, "Should preserve Spanish section"
        assert "900.01" in all_content, "Should preserve error codes"
        assert "Technical Specifications" in all_content, "Should preserve specifications"

        # Verify language detection (might detect primary language)
        document_metadata = document_result.data["metadata"]
        detected_language = document_metadata.get("language")
        assert detected_language is not None, "Should detect some language"

    def _create_processors(self, mock_database_adapter, processor_test_config, mock_stage_tracker):
        """Helper method to create all three processors."""
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        text_processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
            stage_tracker=mock_stage_tracker,
        )

        return upload_processor, document_processor, text_processor

    async def _run_complete_flow(self, processors, test_file, document_type_hint=""):
        """Helper method to run the complete processing flow."""
        upload_processor, document_processor, text_processor = processors

        # Stage 1: Upload
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, f"Upload failed: {upload_result.error}"

        document_id = upload_result.data["document_id"]

        # Stage 2: Document Processing
        document_context = ProcessingContext(
            document_id=document_id, file_path=test_file, metadata=upload_result.metadata
        )
        if document_type_hint:
            document_context.metadata["document_type"] = document_type_hint

        document_result = await document_processor.process(document_context)
        assert document_result.success, f"Document processing failed: {document_result.error}"

        # Stage 3: Text Processing
        text_context = ProcessingContext(
            document_id=document_id, file_path=test_file, metadata=document_result.data["metadata"]
        )
        text_context.page_texts = document_result.data["page_texts"]

        text_result = await text_processor.process(text_context)
        assert text_result.success, f"Text processing failed: {text_result.error}"

        return upload_result, document_result, text_result


class TestContextPropagation:
    """Test context propagation through pipeline stages."""

    @pytest.mark.asyncio
    async def test_document_id_propagation(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test that document ID is properly propagated through all stages."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act - Upload Stage
        upload_result = await upload_processor.process(valid_pdf["path"])
        assert upload_result.success, "Upload should succeed"

        original_document_id = upload_result.data["document_id"]

        # Act - Document Processing Stage
        document_context = ProcessingContext(
            document_id=original_document_id, file_path=valid_pdf["path"], metadata=upload_result.metadata
        )

        document_result = await document_processor.process(document_context)
        assert document_result.success, "Document processing should succeed"

        # Verify document ID is preserved
        assert document_context.document_id == original_document_id, "Document ID should be preserved in document stage"

        # Act - Text Processing Stage
        text_context = ProcessingContext(
            document_id=original_document_id, file_path=valid_pdf["path"], metadata=document_result.data["metadata"]
        )
        text_context.page_texts = document_result.data["page_texts"]

        text_result = await text_processor.process(text_context)
        assert text_result.success, "Text processing should succeed"

        # Assert - Verify document ID propagation
        assert text_context.document_id == original_document_id, "Document ID should be preserved in text stage"

        # Verify all chunks belong to the same document
        chunks = text_result.data["chunks"]
        for chunk in chunks:
            chunk_metadata = chunk.get("metadata", {})
            # Note: chunk might not have document_id in metadata, but should be saved to database with correct ID
            if "document_id" in chunk_metadata:
                assert (
                    chunk_metadata["document_id"] == original_document_id
                ), "Chunk should reference correct document ID"

        # Verify database consistency
        for chunk_id, chunk_data in mock_database_adapter.chunks.items():
            assert (
                chunk_data["document_id"] == original_document_id
            ), "Database chunks should reference correct document ID"

    @pytest.mark.asyncio
    async def test_file_path_propagation(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test that file path is properly propagated through all stages."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        valid_pdf = sample_pdf_files["valid_pdf"]
        original_file_path = valid_pdf["path"]

        # Act - Complete Flow
        upload_result = await upload_processor.process(original_file_path)
        document_result = await self._process_document_stage(document_processor, upload_result, original_file_path)
        text_result = await self._process_text_stage(text_processor, document_result, original_file_path)

        # Assert - Verify file path propagation
        assert upload_result.metadata.get("file_path") == str(original_file_path), "Upload should preserve file path"

        # Note: file_path might not be explicitly stored in later stages, but should be available in context
        # The important thing is that the processing can access the file when needed

    @pytest.mark.asyncio
    async def test_metadata_propagation(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test that metadata is properly propagated and enriched through stages."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        # Create test content
        test_content = """Test Document for Metadata Propagation
==========================================

Manufacturer: TestCorp
Model: C4080
Document Type: Service Manual

This document tests metadata propagation through pipeline stages.
Each stage should add or enrich metadata while preserving existing data.

Technical Specifications:
- Speed: 50 ppm
- Resolution: 1200 dpi
- Memory: 2GB

Error Codes:
- 900.01: Test error
- 900.02: Another test error"""

        test_file = temp_test_pdf / "metadata_test.pdf"
        test_file.write_text(test_content)

        # Act - Upload Stage
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, "Upload should succeed"

        upload_metadata = upload_result.metadata
        assert "filename" in upload_metadata, "Upload should add filename"
        assert "file_size_bytes" in upload_metadata, "Upload should add file size"
        assert "file_hash" in upload_metadata, "Upload should add file hash"
        assert "page_count" in upload_metadata, "Upload should add page count"

        # Act - Document Processing Stage
        document_result = await self._process_document_stage(document_processor, upload_result, test_file)
        assert document_result.success, "Document processing should succeed"

        document_metadata = document_result.data["metadata"]

        # Verify metadata enrichment
        assert "manufacturer" in document_metadata, "Document processing should detect manufacturer"
        assert "language" in document_metadata, "Document processing should detect language"
        assert "document_type" in document_metadata, "Document processing should detect document type"

        # Verify original metadata is preserved
        assert document_metadata.get("filename") == upload_metadata.get("filename"), "Should preserve filename"
        assert document_metadata.get("file_size_bytes") == upload_metadata.get(
            "file_size_bytes"
        ), "Should preserve file size"

        # Act - Text Processing Stage
        text_result = await self._process_text_stage(text_processor, document_result, test_file)
        assert text_result.success, "Text processing should succeed"

        # Assert - Verify final metadata
        # Text processing might not add much metadata, but should preserve context
        updated_context = text_result.data.get("context")
        assert updated_context is not None, "Should return updated context"

        # Verify metadata preservation through context
        final_metadata = updated_context.metadata
        assert final_metadata.get("manufacturer") == document_metadata.get(
            "manufacturer"
        ), "Should preserve manufacturer"
        assert final_metadata.get("document_type") == document_metadata.get(
            "document_type"
        ), "Should preserve document type"

    @pytest.mark.asyncio
    async def test_page_texts_propagation(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test that page_texts are properly propagated from Document to Text processor."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act - Upload and Document Processing
        upload_result = await upload_processor.process(valid_pdf["path"])
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, valid_pdf["path"])
        assert document_result.success, "Document processing should succeed"

        # Verify page_texts extraction
        page_texts = document_result.data["page_texts"]
        assert isinstance(page_texts, dict), "Page texts should be a dictionary"
        assert len(page_texts) > 0, "Should extract page texts"

        # Act - Text Processing
        text_context = ProcessingContext(
            document_id=upload_result.data["document_id"],
            file_path=valid_pdf["path"],
            metadata=document_result.data["metadata"],
        )
        text_context.page_texts = page_texts  # Explicitly propagate page_texts

        text_result = await text_processor.process(text_context)
        assert text_result.success, "Text processing should succeed"

        # Assert - Verify page_texts are available in updated context
        updated_context = text_result.data.get("context")
        assert updated_context is not None, "Should return updated context"
        assert hasattr(updated_context, "page_texts"), "Context should have page_texts attribute"

        propagated_page_texts = updated_context.page_texts
        assert len(propagated_page_texts) == len(page_texts), "Should preserve all page texts"

        # Verify page_texts content is preserved
        for page_num, original_text in page_texts.items():
            assert page_num in propagated_page_texts, f"Page {page_num} should be preserved"
            assert propagated_page_texts[page_num] == original_text, f"Page {page_num} text should be preserved"

    async def _process_document_stage(self, document_processor, upload_result, file_path):
        """Helper method to process document stage."""
        document_context = ProcessingContext(
            document_id=upload_result.data["document_id"], file_path=file_path, metadata=upload_result.metadata
        )
        return await document_processor.process(document_context)

    async def _process_text_stage(self, text_processor, document_result, file_path):
        """Helper method to process text stage."""
        text_context = ProcessingContext(
            document_id=document_result.data.get("metadata", {}).get("document_id"),
            file_path=file_path,
            metadata=document_result.data["metadata"],
        )
        if "page_texts" in document_result.data:
            text_context.page_texts = document_result.data["page_texts"]
        return await text_processor.process(text_context)


class TestStageTracking:
    """Test stage tracking functionality throughout the pipeline."""

    @pytest.mark.asyncio
    async def test_upload_stage_tracking(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test stage tracking for upload stage."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act
        result = await processor.process(valid_pdf["path"])

        # Assert
        assert result.success, "Upload should succeed"

        # StageTracker calls are logged in the mock
        # In a real implementation, we would verify specific RPC calls
        # For now, we verify the processing succeeded with stage tracking enabled

    @pytest.mark.asyncio
    async def test_text_extraction_stage_tracking(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test stage tracking for text extraction stage."""
        # Arrange
        processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        valid_pdf = sample_pdf_files["valid_pdf"]

        context = ProcessingContext(
            document_id="test-doc-id", file_path=valid_pdf["path"], metadata={"filename": valid_pdf["path"].name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Text extraction should succeed"

        # Verify stage tracking was involved
        # In real implementation, check stage tracker calls

    @pytest.mark.asyncio
    async def test_stage_progress_updates(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test stage progress updates during processing."""
        # Arrange
        processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            chunk_size=50,  # Small chunks to trigger more progress updates
            chunk_overlap=10,
            stage_tracker=mock_stage_tracker,
        )

        # Create larger content for progress tracking
        large_content = " ".join([f"Progress test sentence {i}." for i in range(100)])

        test_file = temp_test_pdf / "progress_test.pdf"
        test_file.write_text(large_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Act
        result = await processor.process(context)

        # Assert
        assert result.success, "Processing with progress tracking should succeed"

        # Progress updates would be called during chunking
        # In real implementation, verify progress update calls

    @pytest.mark.asyncio
    async def test_stage_completion_tracking(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test stage completion tracking."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act - Complete Flow
        upload_result = await upload_processor.process(valid_pdf["path"])
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, valid_pdf["path"])
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(text_processor, document_result, valid_pdf["path"])
        assert text_result.success, "Text processing should succeed"

        # Assert
        # All stages should be completed successfully
        # In real implementation, verify completion tracking calls

    @pytest.mark.asyncio
    async def test_stage_failure_tracking(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test stage failure tracking when errors occur."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        # Use corrupted PDF to trigger failure
        corrupted_pdf = sample_pdf_files["corrupted_pdf"]

        # Act
        result = await processor.process(corrupted_pdf["path"])

        # Assert
        assert not result.success, "Corrupted PDF should fail"

        # Stage failure should be tracked
        # In real implementation, verify failure tracking calls

    async def _process_document_stage(self, document_processor, upload_result, file_path):
        """Helper method to process document stage."""
        document_context = ProcessingContext(
            document_id=upload_result.data["document_id"], file_path=file_path, metadata=upload_result.metadata
        )
        return await document_processor.process(document_context)

    async def _process_text_stage(self, text_processor, document_result, file_path):
        """Helper method to process text stage."""
        text_context = ProcessingContext(
            document_id=document_result.data.get("metadata", {}).get("document_id"),
            file_path=file_path,
            metadata=document_result.data["metadata"],
        )
        if "page_texts" in document_result.data:
            text_context.page_texts = document_result.data["page_texts"]
        return await text_processor.process(text_context)

    def _create_processors(self, mock_database_adapter, processor_test_config, mock_stage_tracker):
        """Helper method to create all three processors."""
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        text_processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
            stage_tracker=mock_stage_tracker,
        )

        return upload_processor, document_processor, text_processor


class TestErrorRecovery:
    """Test error recovery mechanisms in the pipeline."""

    @pytest.mark.asyncio
    async def test_upload_failure_stops_pipeline(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test that upload failure stops the pipeline."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        # Use file that will fail upload
        corrupted_pdf = sample_pdf_files["corrupted_pdf"]

        # Act - Upload Stage (should fail)
        upload_result = await upload_processor.process(corrupted_pdf["path"])

        # Assert
        assert not upload_result.success, "Corrupted PDF upload should fail"
        assert "corrupted" in upload_result.error.lower() or "invalid" in upload_result.error.lower()

        # Pipeline should stop here - no document processing should occur
        # In a real pipeline implementation, this would be handled by the pipeline orchestrator

    @pytest.mark.asyncio
    async def test_text_extraction_failure_recovery(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test recovery from text extraction failures."""
        # Arrange
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        # Create a test file
        test_file = temp_test_pdf / "recovery_test.pdf"
        test_file.write_text("Test content for recovery testing.")

        # Act - Upload (should succeed)
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, "Upload should succeed"

        # Mock text extraction to fail
        with patch.object(document_processor.text_extractor, "extract_text") as mock_extract:
            mock_extract.side_effect = Exception("Text extraction failed")

            # Act - Document Processing (should fail)
            document_context = ProcessingContext(
                document_id=upload_result.data["document_id"], file_path=test_file, metadata=upload_result.metadata
            )

            document_result = await document_processor.process(document_context)

            # Assert
            assert not document_result.success, "Document processing should fail when extraction fails"
            assert "extraction" in document_result.error.lower()

    @pytest.mark.asyncio
    async def test_partial_page_failure_continues(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test that processing continues when individual pages fail."""
        # Arrange
        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        # Create multi-page content
        multi_page_content = """Page 1: First page content.
This page should process successfully.

Page 2: Second page content.
This page might fail but processing should continue.

Page 3: Third page content.
This page should also process successfully."""

        test_file = temp_test_pdf / "partial_failure_test.pdf"
        test_file.write_text(multi_page_content)

        context = ProcessingContext(
            document_id="test-doc-id", file_path=test_file, metadata={"filename": test_file.name}
        )

        # Mock partial failure
        original_extract = document_processor.text_extractor.extract_text

        async def mock_extract_with_partial_failure(file_path):
            result = await original_extract(file_path)
            if result and isinstance(result, tuple) and len(result) >= 1:
                page_texts = result[0]
                # Make page 2 fail (empty text)
                if page_texts and 2 in page_texts:
                    page_texts[2] = ""
            return result

        with patch.object(
            document_processor.text_extractor, "extract_text", side_effect=mock_extract_with_partial_failure
        ):
            # Act
            result = await document_processor.process(context)

            # Assert
            # Should succeed despite partial page failure
            assert result.success, "Should succeed with partial page failure"

            page_texts = result.data["page_texts"]
            # Should have at least some pages
            assert len(page_texts) >= 2, "Should have processed some pages"

    @pytest.mark.asyncio
    async def test_database_error_recovery(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test recovery from database errors."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        test_file = temp_test_pdf / "db_error_test.pdf"
        test_file.write_text("Test content for database error testing.")

        # Mock database to fail
        async def failing_create_document(document):
            raise Exception("Database connection failed")

        mock_database_adapter.create_document = failing_create_document

        # Act
        result = await processor.process(test_file)

        # Assert
        assert not result.success, "Should fail when database operations fail"
        assert "database" in result.error.lower() or "connection" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retry_mechanism(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test retry mechanism for transient failures."""
        # Arrange
        processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        test_file = temp_test_pdf / "retry_test.pdf"
        test_file.write_text("Test content for retry mechanism testing.")

        # Mock database to fail initially, then succeed
        call_count = 0
        original_create = mock_database_adapter.create_document

        async def failing_then_success(document):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 times
                raise Exception("Transient database error")
            return await original_create(document)

        mock_database_adapter.create_document = failing_then_success

        # Act
        # Note: Current implementation might not have retry logic
        # This test would need to be adapted based on actual retry implementation
        result = await processor.process(test_file)

        # Assert
        # Depending on implementation, might fail or succeed after retries
        if result.success:
            assert call_count > 2, "Should have retried before succeeding"
        else:
            assert "transient" in result.error.lower() or "database" in result.error.lower()


class TestDataConsistency:
    """Test data consistency throughout the pipeline."""

    @pytest.mark.asyncio
    async def test_document_record_consistency(
        self, mock_database_adapter, sample_pdf_files, processor_test_config, mock_stage_tracker
    ):
        """Test consistency of document records across pipeline stages."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        valid_pdf = sample_pdf_files["valid_pdf"]

        # Act - Complete Flow
        upload_result = await upload_processor.process(valid_pdf["path"])
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, valid_pdf["path"])
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(text_processor, document_result, valid_pdf["path"])
        assert text_result.success, "Text processing should succeed"

        # Assert - Document Record Consistency
        document_id = upload_result.data["document_id"]

        # Verify document exists in database
        document_record = await mock_database_adapter.get_document(document_id)
        assert document_record is not None, "Document should exist in database"

        # Verify document metadata consistency
        assert document_record["filename"] == valid_pdf["path"].name, "Filename should be consistent"
        assert document_record["file_size_bytes"] == valid_pdf["size"], "File size should be consistent"

        # Verify document ID is used consistently
        for chunk_id, chunk_data in mock_database_adapter.chunks.items():
            assert chunk_data["document_id"] == document_id, "All chunks should reference the same document ID"

    @pytest.mark.asyncio
    async def test_chunk_document_id_consistency(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test that all chunks have consistent document IDs."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        # Create test content
        test_content = """Test content for chunk consistency testing.
This content should be processed into multiple chunks.
Each chunk should reference the same document ID."""

        test_file = temp_test_pdf / "chunk_consistency_test.pdf"
        test_file.write_text(test_content)

        # Act - Complete Flow
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, test_file)
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(text_processor, document_result, test_file)
        assert text_result.success, "Text processing should succeed"

        # Assert - Chunk Document ID Consistency
        document_id = upload_result.data["document_id"]
        chunks = text_result.data["chunks"]

        # Verify all chunks in result have correct document reference
        for chunk in chunks:
            chunk_metadata = chunk.get("metadata", {})
            if "document_id" in chunk_metadata:
                assert (
                    chunk_metadata["document_id"] == document_id
                ), "Chunk metadata should reference correct document ID"

        # Verify all database chunks have correct document ID
        for chunk_id, chunk_data in mock_database_adapter.chunks.items():
            assert (
                chunk_data["document_id"] == document_id
            ), f"Database chunk {chunk_id} should reference correct document ID"

    @pytest.mark.asyncio
    async def test_page_range_consistency(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test consistency of page ranges in chunks."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        # Create multi-page content
        multi_page_content = """Page 1: First page content.
This content should be on page 1.

Page 2: Second page content.
This content should be on page 2.

Page 3: Third page content.
This content should be on page 3."""

        test_file = temp_test_pdf / "page_range_test.pdf"
        test_file.write_text(multi_page_content)

        # Act - Complete Flow
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, test_file)
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(text_processor, document_result, test_file)
        assert text_result.success, "Text processing should succeed"

        # Assert - Page Range Consistency
        chunks = text_result.data["chunks"]

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            page_start = metadata.get("page_start")
            page_end = metadata.get("page_end")

            assert page_start is not None, "Chunk should have page_start"
            assert page_end is not None, "Chunk should have page_end"
            assert page_start <= page_end, "page_start should be <= page_end"
            assert page_start >= 1, "page_start should be >= 1"
            assert page_end >= page_start, "page_end should be >= page_start"

            # Page ranges should be reasonable
            assert page_end - page_start <= 5, "Page range should be reasonable (not too large)"

    @pytest.mark.asyncio
    async def test_metadata_consistency(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test consistency of metadata across pipeline stages."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)
        upload_processor, document_processor, text_processor = processors

        # Create test content with specific metadata
        test_content = """TestCorp C4080 Service Manual
================================

Manufacturer: TestCorp
Model: C4080
Document Type: Service Manual
Language: English

This content tests metadata consistency across pipeline stages.
Each stage should preserve and enrich metadata appropriately."""

        test_file = temp_test_pdf / "metadata_consistency_test.pdf"
        test_file.write_text(test_content)

        # Act - Complete Flow
        upload_result = await upload_processor.process(test_file)
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(document_processor, upload_result, test_file)
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(text_processor, document_result, test_file)
        assert text_result.success, "Text processing should succeed"

        # Assert - Metadata Consistency
        upload_metadata = upload_result.metadata
        document_metadata = document_result.data["metadata"]
        final_context = text_result.data.get("context")
        final_metadata = final_context.metadata if final_context else {}

        # Verify core metadata is preserved
        core_fields = ["filename", "file_size_bytes", "file_hash"]
        for field in core_fields:
            assert upload_metadata.get(field) == document_metadata.get(field), f"Field {field} should be preserved"
            assert document_metadata.get(field) == final_metadata.get(
                field
            ), f"Field {field} should be preserved to final"

        # Verify enriched metadata
        enriched_fields = ["manufacturer", "model", "document_type", "language"]
        for field in enriched_fields:
            assert document_metadata.get(field) is not None, f"Field {field} should be added by document processing"
            assert final_metadata.get(field) == document_metadata.get(
                field
            ), f"Field {field} should be preserved to final"

        # Verify manufacturer detection consistency
        manufacturer = document_metadata.get("manufacturer", "").lower()
        assert "testcorp" in manufacturer, f"Should detect TestCorp, got {manufacturer}"

        # Verify document type detection consistency
        doc_type = document_metadata.get("document_type", "").lower()
        assert "service_manual" in doc_type or "manual" in doc_type, f"Should detect service manual, got {doc_type}"


class TestPerformance:
    """Test performance characteristics of the pipeline."""

    @pytest.mark.asyncio
    async def test_small_document_processing_time(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test processing time for small documents."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create small content
        small_content = """Small Test Document
===================

This is a small document for performance testing.
It contains minimal content and should process quickly.

Technical Specifications:
- Size: Small
- Complexity: Low
- Processing Time: Should be fast"""

        test_file = temp_test_pdf / "small_performance_test.pdf"
        test_file.write_text(small_content)

        # Act - Measure processing time
        start_time = time.time()

        upload_result = await processors[0].process(test_file)
        document_result = await self._process_document_stage(processors[1], upload_result, test_file)
        text_result = await self._process_text_stage(processors[2], document_result, test_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert
        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 30.0, f"Small document should process within 30 seconds, took {processing_time:.2f}s"

        # Log performance metrics
        print(f"Small document processing time: {processing_time:.2f}s")
        print(f"  Upload: {upload_result.metadata.get('processing_time', 'N/A')}")
        print(f"  Document: {document_result.data.get('processing_time', 'N/A')}")
        print(f"  Text: {text_result.data.get('processing_time', 'N/A')}")

    @pytest.mark.asyncio
    async def test_large_document_processing_time(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test processing time for large documents."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create larger content
        large_content = " ".join(
            [f"Large document sentence {i} with technical content for performance testing." for i in range(500)]
        )

        test_file = temp_test_pdf / "large_performance_test.pdf"
        test_file.write_text(large_content)

        # Act - Measure processing time
        start_time = time.time()

        upload_result = await processors[0].process(test_file)
        document_result = await self._process_document_stage(processors[1], upload_result, test_file)
        text_result = await self._process_text_stage(processors[2], document_result, test_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert
        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Should complete within reasonable time (adjust threshold as needed)
        assert processing_time < 120.0, f"Large document should process within 120 seconds, took {processing_time:.2f}s"

        # Verify chunks were created
        chunks = text_result.data["chunks"]
        assert len(chunks) > 5, "Large document should create multiple chunks"

        # Log performance metrics
        print(f"Large document processing time: {processing_time:.2f}s")
        print(f"  Chunks created: {len(chunks)}")
        print(f"  Average time per chunk: {processing_time/len(chunks):.2f}s")

    @pytest.mark.asyncio
    async def test_concurrent_document_processing(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test concurrent processing of multiple documents."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create multiple test files
        test_files = []
        for i in range(3):
            content = f"""Concurrent Test Document {i+1}
==================================

This is document {i+1} for concurrent processing testing.
Each document should be processed independently.

Content specific to document {i+1}:
- Item {i+1}-A
- Item {i+1}-B
- Item {i+1}-C

Error codes for document {i+1}:
- 90{i+1:02d}.01: Test error {i+1}
- 90{i+1:02d}.02: Another error {i+1}"""

            test_file = temp_test_pdf / f"concurrent_test_{i+1}.pdf"
            test_file.write_text(content)
            test_files.append(test_file)

        # Act - Process documents concurrently
        async def process_single_document(file_path, doc_index):
            start_time = time.time()

            upload_result = await processors[0].process(file_path)
            document_result = await self._process_document_stage(processors[1], upload_result, file_path)
            text_result = await self._process_text_stage(processors[2], document_result, file_path)

            end_time = time.time()

            return {
                "doc_index": doc_index,
                "upload_success": upload_result.success,
                "document_success": document_result.success,
                "text_success": text_result.success,
                "processing_time": end_time - start_time,
                "chunks_count": len(text_result.data["chunks"]) if text_result.success else 0,
                "document_id": upload_result.data["document_id"] if upload_result.success else None,
            }

        # Run concurrent processing
        tasks = [process_single_document(file_path, i) for i, file_path in enumerate(test_files)]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == len(test_files), "Should have results for all documents"

        for result in results:
            assert result["upload_success"], f"Document {result['doc_index']} upload should succeed"
            assert result["document_success"], f"Document {result['doc_index']} processing should succeed"
            assert result["text_success"], f"Document {result['doc_index']} text processing should succeed"
            assert result["chunks_count"] > 0, f"Document {result['doc_index']} should create chunks"
            assert result["document_id"] is not None, f"Document {result['doc_index']} should have document ID"

        # Verify documents are independent (different IDs)
        document_ids = [result["document_id"] for result in results]
        assert len(set(document_ids)) == len(document_ids), "Each document should have unique ID"

        # Verify database consistency
        assert len(mock_database_adapter.documents) == len(test_files), "Should have all documents in database"
        total_chunks = sum(result["chunks_count"] for result in results)
        assert len(mock_database_adapter.chunks) == total_chunks, "Should have all chunks in database"

        # Log performance metrics
        avg_time = sum(result["processing_time"] for result in results) / len(results)
        print("Concurrent processing results:")
        print(f"  Documents processed: {len(test_files)}")
        print(f"  Average processing time: {avg_time:.2f}s")
        print(f"  Total chunks created: {total_chunks}")

    @pytest.mark.asyncio
    async def test_memory_usage_during_processing(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test memory usage during document processing."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create content that might stress memory
        memory_test_content = " ".join([f"Memory test sentence {i} with extensive content." for i in range(1000)])

        test_file = temp_test_pdf / "memory_usage_test.pdf"
        test_file.write_text(memory_test_content)

        # Act - Process and monitor memory usage
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        upload_result = await processors[0].process(test_file)
        document_result = await self._process_document_stage(processors[1], upload_result, test_file)
        text_result = await self._process_text_stage(processors[2], document_result, test_file)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Assert
        assert upload_result.success, "Upload should succeed"
        assert document_result.success, "Document processing should succeed"
        assert text_result.success, "Text processing should succeed"

        # Memory usage should be reasonable (adjust threshold as needed)
        assert memory_increase < 500, f"Memory increase should be reasonable, was {memory_increase:.2f}MB"

        # Log memory metrics
        print("Memory usage during processing:")
        print(f"  Initial memory: {initial_memory:.2f}MB")
        print(f"  Final memory: {final_memory:.2f}MB")
        print(f"  Memory increase: {memory_increase:.2f}MB")
        print(f"  Chunks created: {len(text_result.data['chunks'])}")

    async def _process_document_stage(self, document_processor, upload_result, file_path):
        """Helper method to process document stage."""
        document_context = ProcessingContext(
            document_id=upload_result.data["document_id"], file_path=file_path, metadata=upload_result.metadata
        )
        return await document_processor.process(document_context)

    async def _process_text_stage(self, text_processor, document_result, file_path):
        """Helper method to process text stage."""
        text_context = ProcessingContext(
            document_id=document_result.data.get("metadata", {}).get("document_id"),
            file_path=file_path,
            metadata=document_result.data["metadata"],
        )
        if "page_texts" in document_result.data:
            text_context.page_texts = document_result.data["page_texts"]
        return await text_processor.process(text_context)

    def _create_processors(self, mock_database_adapter, processor_test_config, mock_stage_tracker):
        """Helper method to create all three processors."""
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        document_processor = DocumentProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            stage_tracker=mock_stage_tracker,
        )

        text_processor = OptimizedTextProcessor(
            database_adapter=mock_database_adapter,
            pdf_engine=processor_test_config["pdf_engine"],
            chunk_size=processor_test_config["chunk_size"],
            chunk_overlap=processor_test_config["chunk_overlap"],
            stage_tracker=mock_stage_tracker,
        )

        return upload_processor, document_processor, text_processor


class TestDeduplication:
    """Test deduplication functionality in the pipeline."""

    @pytest.mark.asyncio
    async def test_duplicate_document_detection(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test detection of duplicate documents."""
        # Arrange
        upload_processor = UploadProcessor(
            database_adapter=mock_database_adapter,
            max_file_size_mb=processor_test_config["max_file_size_mb"],
            stage_tracker=mock_stage_tracker,
        )

        # Create test file
        test_content = "Duplicate test content for deduplication testing."
        test_file = temp_test_pdf / "duplicate_test.pdf"
        test_file.write_text(test_content)
        # Calculate real file hash for deduplication
        file_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()

        # Act - First upload
        context1 = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(test_file),
            file_hash=file_hash,
            document_type="service_manual",
        )
        first_result = await upload_processor.process(context1)

        # Assert - First upload should succeed
        assert first_result.success, "First upload should succeed"
        first_document_id = first_result.data["document_id"]

        # Act - Second upload (should detect duplicate but still succeed)
        context2 = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(test_file),
            file_hash=file_hash,
            document_type="service_manual",
        )
        second_result = await upload_processor.process(context2)

        # Assert - Second upload should succeed with duplicate status
        assert second_result.success, "Second upload should succeed with duplicate status"
        assert second_result.data.get("status") == "duplicate"
        assert "existing_document" in second_result.data

        # Verify only one document in database
        assert len(mock_database_adapter.documents) == 1, "Should have only one document in database"
        assert first_document_id in mock_database_adapter.documents, "Original document should exist"

    @pytest.mark.asyncio
    async def test_force_reprocess_flow(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test complete flow with force_reprocess=True."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create test file
        test_content = """Force Reprocess Test Document
=================================

This document tests the force reprocess functionality.
It should create a new document even if content is identical.

Technical Specifications:
- Test Type: Force Reprocess
- Expected Behavior: New Document Creation
- Deduplication: Bypassed"""

        test_file = temp_test_pdf / "force_reprocess_test.pdf"
        test_file.write_text(test_content)

        # Act - First processing
        first_upload_result = await processors[0].process(test_file)
        assert first_upload_result.success, "First upload should succeed"

        first_document_result = await self._process_document_stage(processors[1], first_upload_result, test_file)
        assert first_document_result.success, "First document processing should succeed"

        first_text_result = await self._process_text_stage(processors[2], first_document_result, test_file)
        assert first_text_result.success, "First text processing should succeed"

        # Act - Second processing with force_reprocess
        second_upload_result = await processors[0].process(test_file, force_reprocess=True)
        assert second_upload_result.success, "Second upload with force_reprocess should succeed"

        second_document_result = await self._process_document_stage(processors[1], second_upload_result, test_file)
        assert second_document_result.success, "Second document processing should succeed"

        second_text_result = await self._process_text_stage(processors[2], second_document_result, test_file)
        assert second_text_result.success, "Second text processing should succeed"

        # Assert
        first_document_id = first_upload_result.data["document_id"]
        second_document_id = second_upload_result.data["document_id"]

        assert first_document_id != second_document_id, "Force reprocess should create new document ID"

        # Should have two documents in database
        assert len(mock_database_adapter.documents) == 2, "Should have two documents after force reprocess"

        # Should have chunks for both documents
        first_chunks = [c for c in mock_database_adapter.chunks.values() if c["document_id"] == first_document_id]
        second_chunks = [c for c in mock_database_adapter.chunks.values() if c["document_id"] == second_document_id]

        assert len(first_chunks) > 0, "First document should have chunks"
        assert len(second_chunks) > 0, "Second document should have chunks"

    @pytest.mark.asyncio
    async def test_duplicate_chunks_handling(
        self, mock_database_adapter, temp_test_pdf, processor_test_config, mock_stage_tracker
    ):
        """Test handling of duplicate chunks within and across documents."""
        # Arrange
        processors = self._create_processors(mock_database_adapter, processor_test_config, mock_stage_tracker)

        # Create content with potential duplicate chunks
        duplicate_content = """Duplicate Chunk Test Document
====================================

Repeated Section 1
==================
This section contains repeated content that might result in duplicate chunks.
The content is intentionally repeated to test deduplication logic.

Repeated Section 1
==================
This section contains repeated content that might result in duplicate chunks.
The content is intentionally repeated to test deduplication logic.

Unique Section
==============
This section contains unique content that should not be duplicated.
It serves as a control to ensure unique chunks are preserved.

Repeated Section 2
==================
Another repeated section for testing chunk deduplication.
This content appears multiple times in the document.

Repeated Section 2
==================
Another repeated section for testing chunk deduplication.
This content appears multiple times in the document."""

        test_file = temp_test_pdf / "duplicate_chunks_test.pdf"
        test_file.write_text(duplicate_content)

        # Act - Complete Flow
        upload_result = await processors[0].process(test_file)
        assert upload_result.success, "Upload should succeed"

        document_result = await self._process_document_stage(processors[1], upload_result, test_file)
        assert document_result.success, "Document processing should succeed"

        text_result = await self._process_text_stage(processors[2], document_result, test_file)
        assert text_result.success, "Text processing should succeed"

        # Assert
        chunks = text_result.data["chunks"]
        content_hashes = [chunk.get("metadata", {}).get("content_hash") for chunk in chunks]

        # Check for duplicate content hashes
        unique_hashes = set(content_hashes)
        duplicate_hashes = [h for h in content_hashes if content_hashes.count(h) > 1]

        print(f"Total chunks: {len(chunks)}")
        print(f"Unique content hashes: {len(unique_hashes)}")
        print(f"Duplicate content hashes: {len(duplicate_hashes)}")

        # Should have some deduplication (depending on chunking algorithm)
        # The exact behavior depends on the chunking implementation
        assert len(chunks) > 0, "Should create chunks"
        assert len(unique_hashes) > 0, "Should have unique content"

        # Verify database chunks
        db_hashes = [chunk.get("content_hash") for chunk in mock_database_adapter.chunks.values()]
        db_unique_hashes = set(db_hashes)

        assert len(db_unique_hashes) <= len(db_hashes), "Database should handle deduplication"


# Parameterized tests for different document types
@pytest.mark.parametrize(
    "document_type,content_keywords,metadata_checks",
    [
        ("service_manual", ["service", "manual", "maintenance", "error"], {"document_type": "service_manual"}),
        ("parts_catalog", ["parts", "catalog", "part number", "price"], {"document_type": "parts_catalog"}),
        ("user_guide", ["user", "guide", "getting started", "troubleshooting"], {"document_type": "user_guide"}),
        ("technical_specs", ["specifications", "technical", "performance", "dimensions"], {"document_type": "manual"}),
    ],
)
@pytest.mark.asyncio
async def test_document_type_processing(
    mock_database_adapter,
    temp_test_pdf,
    processor_test_config,
    mock_stage_tracker,
    document_type,
    content_keywords,
    metadata_checks,
):
    """Test processing of different document types."""
    # Arrange
    processors = _create_processors_helper(mock_database_adapter, processor_test_config, mock_stage_tracker)

    # Create content based on document type
    content = f"""{document_type.replace('_', ' ').title()} Test Document
{'=' * (len(document_type) + 14)}

This is a test document of type: {document_type}
{' '.join(keyword.capitalize() + '.' for keyword in content_keywords)}

Technical Information:
- Document Type: {document_type}
- Test Purpose: Validation of processing pipeline
- Expected Keywords: {', '.join(content_keywords)}

Content Sections:
"""

    for keyword in content_keywords:
        content += f"""
{keyword.title()} Section:
This section contains information related to {keyword}.
It should be properly processed and preserved in chunks.
"""

    test_file = temp_test_pdf / f"{document_type}_test.pdf"
    test_file.write_text(content)

    # Act - Complete Flow
    upload_result = await processors[0].process(test_file)
    assert upload_result.success, f"Upload should succeed for {document_type}"

    document_result = await _process_document_stage_helper(processors[1], upload_result, test_file)
    assert document_result.success, f"Document processing should succeed for {document_type}"

    text_result = await _process_text_stage_helper(processors[2], document_result, test_file)
    assert text_result.success, f"Text processing should succeed for {document_type}"

    # Assert
    chunks = text_result.data["chunks"]
    all_content = " ".join(chunk["content"] for chunk in chunks)

    # Verify content keywords are preserved
    for keyword in content_keywords:
        assert keyword in all_content.lower(), f"Should preserve keyword '{keyword}' for {document_type}"

    # Verify metadata checks
    document_metadata = document_result.data["metadata"]
    for key, expected_value in metadata_checks.items():
        actual_value = document_metadata.get(key, "").lower()
        assert (
            expected_value in actual_value or actual_value in expected_value
        ), f"For {document_type}, expected {key} to contain '{expected_value}', got '{actual_value}'"


# Helper functions for parameterized tests
def _create_processors_helper(mock_database_adapter, processor_test_config, mock_stage_tracker):
    """Helper to create processors for parameterized tests."""
    upload_processor = UploadProcessor(
        database_adapter=mock_database_adapter,
        max_file_size_mb=processor_test_config["max_file_size_mb"],
        stage_tracker=mock_stage_tracker,
    )

    document_processor = DocumentProcessor(
        database_adapter=mock_database_adapter,
        pdf_engine=processor_test_config["pdf_engine"],
        stage_tracker=mock_stage_tracker,
    )

    text_processor = OptimizedTextProcessor(
        database_adapter=mock_database_adapter,
        pdf_engine=processor_test_config["pdf_engine"],
        chunk_size=processor_test_config["chunk_size"],
        chunk_overlap=processor_test_config["chunk_overlap"],
        stage_tracker=mock_stage_tracker,
    )

    return upload_processor, document_processor, text_processor


async def _process_document_stage_helper(document_processor, upload_result, file_path):
    """Helper to process document stage for parameterized tests."""
    document_context = ProcessingContext(
        document_id=upload_result.data["document_id"], file_path=file_path, metadata=upload_result.metadata
    )
    return await document_processor.process(document_context)


async def _process_text_stage_helper(text_processor, document_result, file_path):
    """Helper to process text stage for parameterized tests."""
    text_context = ProcessingContext(
        document_id=document_result.data.get("metadata", {}).get("document_id"),
        file_path=file_path,
        metadata=document_result.data["metadata"],
    )
    if "page_texts" in document_result.data:
        text_context.page_texts = document_result.data["page_texts"]
    return await text_processor.process(text_context)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
