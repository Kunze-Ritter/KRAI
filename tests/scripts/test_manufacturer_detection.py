"""
Tests for manufacturer detection from filenames

Tests the filename-based fallback mechanisms for:
1. Manufacturer detection from filename patterns (HP_E475_SM.pdf, KM_C759_SM.pdf)
2. Product model extraction from filenames when content extraction fails
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.classification_processor import ClassificationProcessor
from backend.processors.product_extractor import ProductExtractor

pytestmark = [pytest.mark.unit, pytest.mark.manufacturer_detection]


class TestManufacturerDetectionFromFilename:
    """Test manufacturer detection from structured filename patterns"""

    async def test_detect_hp_from_filename_pattern(self, tmp_path: Path) -> None:
        """Test HP detection from HP_E475_SM.pdf pattern"""
        pdf_path = tmp_path / "HP_E475_SM.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert manufacturer.upper() == "HP"

    async def test_detect_konica_minolta_from_km_prefix(self, tmp_path: Path) -> None:
        """Test Konica Minolta detection from KM_C759_SM.pdf pattern"""
        pdf_path = tmp_path / "KM_C759_SM.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "KONICA" in manufacturer.upper() or "MINOLTA" in manufacturer.upper()

    async def test_detect_canon_from_filename_pattern(self, tmp_path: Path) -> None:
        """Test Canon detection from CANON_iR_ADV_C5550i.pdf pattern"""
        pdf_path = tmp_path / "CANON_iR_ADV_C5550i.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "CANON" in manufacturer.upper()

    async def test_detect_ricoh_from_filename_pattern(self, tmp_path: Path) -> None:
        """Test Ricoh detection from RICOH_IM_C6000.pdf pattern"""
        pdf_path = tmp_path / "RICOH_IM_C6000.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "RICOH" in manufacturer.upper()

    async def test_detect_lexmark_from_filename_pattern(self, tmp_path: Path) -> None:
        """Test Lexmark detection from LEXMARK_CX920_SM.pdf pattern"""
        pdf_path = tmp_path / "LEXMARK_CX920_SM.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "LEXMARK" in manufacturer.upper()


class TestProductExtractorFilenameDetection:
    """Test ProductExtractor.extract_from_filename() for model extraction"""

    def test_extract_hp_e475_from_filename(self) -> None:
        """Test extracting E475 from HP_E475_SM.pdf"""
        extractor = ProductExtractor(manufacturer_name="HP", debug=False)

        products = extractor.extract_from_filename("HP_E475_SM.pdf")

        assert len(products) > 0
        assert any(p.model_number == "E475" for p in products)

        e475_product = next(p for p in products if p.model_number == "E475")
        assert e475_product.confidence <= 0.5
        assert e475_product.extraction_method == "filename_parsing"
        assert e475_product.source_page == -1

    def test_extract_km_c759_from_filename(self) -> None:
        """Test extracting C759 from KM_C759_SM.pdf"""
        extractor = ProductExtractor(manufacturer_name="KONICA MINOLTA", debug=False)

        products = extractor.extract_from_filename("KM_C759_SM.pdf")

        assert len(products) > 0
        assert any(p.model_number == "C759" for p in products)

        c759_product = next(p for p in products if p.model_number == "C759")
        assert c759_product.confidence <= 0.5
        assert c759_product.extraction_method == "filename_parsing"
        assert c759_product.source_page == -1

    def test_extract_multiple_models_from_filename(self) -> None:
        """Test extracting C759 and C659 from KM_C759_C659_FW4.1_SM.pdf"""
        extractor = ProductExtractor(manufacturer_name="KONICA MINOLTA", debug=False)

        products = extractor.extract_from_filename("KM_C759_C659_FW4.1_SM.pdf")

        assert len(products) >= 2
        model_numbers = {p.model_number for p in products}
        assert "C759" in model_numbers
        assert "C659" in model_numbers

        for product in products:
            assert product.confidence <= 0.5
            assert product.extraction_method == "filename_parsing"
            assert product.source_page == -1

    def test_extract_canon_c5550i_from_filename(self) -> None:
        """Test extracting C5550i from CANON_iR_ADV_C5550i_Manual.pdf"""
        extractor = ProductExtractor(manufacturer_name="CANON", debug=False)

        products = extractor.extract_from_filename("CANON_iR_ADV_C5550i_Manual.pdf")

        assert len(products) > 0
        assert any("C5550i" in p.model_number for p in products)

        c5550i_product = next(p for p in products if "C5550i" in p.model_number)
        assert c5550i_product.confidence <= 0.5
        assert c5550i_product.extraction_method == "filename_parsing"

    def test_filename_extraction_filters_version_patterns(self) -> None:
        """Test that version patterns like FW4.1 are filtered out"""
        extractor = ProductExtractor(manufacturer_name="KONICA MINOLTA", debug=False)

        products = extractor.extract_from_filename("KM_C759_FW4.1_SM.pdf")

        model_numbers = {p.model_number for p in products}
        assert "FW4" not in model_numbers
        assert "FW4.1" not in model_numbers
        assert "4.1" not in model_numbers
        assert "C759" in model_numbers

    def test_filename_extraction_lower_confidence_than_content(self) -> None:
        """Test that filename extraction has lower confidence than content-based"""
        extractor = ProductExtractor(manufacturer_name="HP", debug=False)

        products = extractor.extract_from_filename("HP_E475_SM.pdf")

        assert len(products) > 0
        for product in products:
            assert product.confidence < 0.6


class TestManufacturerDetectionFromPages:
    """Test manufacturer detection from first and last pages using page_texts"""

    async def test_detect_hp_from_first_page(self, tmp_path: Path) -> None:
        """Test HP detection from first page text"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing HP on first page
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "HP LaserJet Pro Service Manual - Introduction",
            2: "Table of Contents",
            3: "Chapter 1: Overview",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_hewlett_packard_alias_from_first_page(self, tmp_path: Path) -> None:
        """Test HP detection from 'Hewlett Packard' alias on first page"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing Hewlett Packard alias
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Service Manual for Hewlett Packard LaserJet Enterprise",
            2: "Copyright Notice",
            3: "Safety Information",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_hewlett_hyphen_packard_alias_from_first_page(self, tmp_path: Path) -> None:
        """Test HP detection from 'Hewlett-Packard' alias on first page"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing Hewlett-Packard alias
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Hewlett-Packard Company - Technical Documentation",
            2: "Model Specifications",
            3: "Installation Guide",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_konica_minolta_from_last_page(self, tmp_path: Path) -> None:
        """Test Konica Minolta detection from last page (imprint)"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing Konica Minolta on last page
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Service Manual - Generic Introduction",
            2: "Technical Specifications",
            3: "Troubleshooting Guide",
            49: "Appendix A - Parts List",
            50: "Copyright 2023 Konica Minolta Business Solutions. All rights reserved.",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "KONICA" in manufacturer.upper() or "MINOLTA" in manufacturer.upper()

    async def test_detect_hp_from_page_2(self, tmp_path: Path) -> None:
        """Test HP detection from page 2 (within first 3 pages)"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing HP on page 2
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Service Manual",
            2: "This manual covers HP LaserJet Enterprise MFP M631 series",
            3: "Table of Contents",
            4: "Chapter 1",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_hp_from_page_3(self, tmp_path: Path) -> None:
        """Test HP detection from page 3 (within first 3 pages)"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing HP on page 3
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Service Manual",
            2: "Copyright Notice",
            3: "HP Inc. - All Rights Reserved",
            4: "Chapter 1",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_no_detection_from_page_4_onwards(self, tmp_path: Path) -> None:
        """Test that manufacturer on page 4+ is not detected (only first 3 pages checked)"""
        pdf_path = tmp_path / "generic_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with page_texts containing HP only on page 4 (should not be detected)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Generic Service Manual",
            2: "Generic Copyright",
            3: "Generic Table of Contents",
            4: "HP LaserJet mentioned here",
            5: "More content",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should not detect HP since it's only on page 4
        assert manufacturer is None or "HP" not in manufacturer.upper()

    async def test_first_page_priority_over_last_page(self, tmp_path: Path) -> None:
        """Test that first page detection has priority over last page"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with different manufacturers on first and last pages
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "HP LaserJet Service Manual",
            2: "Technical Specifications",
            3: "Installation Guide",
            49: "Parts manufactured by Canon",
            50: "Canon components used in this device",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should detect HP from first page, not Canon from last page
        assert manufacturer is not None
        assert "HP" in manufacturer.upper()
        assert "CANON" not in manufacturer.upper()

    async def test_page_detection_precedes_ai_detection(self, tmp_path: Path) -> None:
        """Test that page-based detection has priority over AI detection"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        # Mock AI service that would return Canon
        class MockAIService:
            async def generate(self, prompt: str, max_tokens: int = 100):
                return "Canon"

        processor = ClassificationProcessor(database_service=None, ai_service=MockAIService(), features_service=None)

        # Create context with HP in page_texts
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {1: "HP LaserJet Enterprise Service Manual", 2: "Copyright HP Inc.", 3: "Table of Contents"}

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should detect HP from pages, not Canon from AI
        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_page_detection_precedes_filename_parsing(self, tmp_path: Path) -> None:
        """Test that page-based detection has priority over filename parsing"""
        pdf_path = tmp_path / "CANON_iR_ADV_Manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Create context with HP in page_texts (filename suggests Canon)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {1: "HP LaserJet Service Manual", 2: "HP Inc. All Rights Reserved", 3: "Introduction"}

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should detect HP from pages, not Canon from filename
        assert manufacturer is not None
        assert "HP" in manufacturer.upper()


class TestHPDetectionEdgeCases:
    """Test HP detection edge cases to catch bugs preventing HP detection"""

    async def test_detect_hp_short_name_exact_match(self, tmp_path: Path) -> None:
        """Test that 'HP' (2 chars) is detected despite being short"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Test with exact 'HP' in text
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {1: "HP Service Manual for LaserJet Printers", 2: "Table of Contents", 3: "Chapter 1"}

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_hp_lowercase_in_text(self, tmp_path: Path) -> None:
        """Test that 'hp' (lowercase) is detected"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {1: "Service manual for hp printers", 2: "Copyright notice", 3: "Introduction"}

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_detect_hp_inc_in_text(self, tmp_path: Path) -> None:
        """Test that 'HP Inc.' is detected"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Copyright 2023 HP Inc. All Rights Reserved",
            2: "Service Manual",
            3: "Technical Specifications",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_hp_not_detected_in_false_positives(self, tmp_path: Path) -> None:
        """Test that HP is not detected in false positives like 'SHOP' or 'CHIP'"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Visit our online SHOP for more products",
            2: "CHIP specifications and memory details",
            3: "WHIP cream dispenser accessories",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should NOT detect HP from SHOP, CHIP, or WHIP
        assert manufacturer is None or "HP" not in manufacturer.upper()

    async def test_manufacturer_alias_iteration_order(self, tmp_path: Path) -> None:
        """Test that all aliases are checked, not just the first one"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Use an alias that appears later in the HP alias list
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "LaserJet Enterprise Service Manual",  # LaserJet is an HP alias
            2: "Technical Documentation",
            3: "Safety Information",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should detect HP from LaserJet alias
        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_hp_detection_real_world_patterns(self, tmp_path: Path) -> None:
        """Test HP detection with real-world document patterns"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Test with real-world HP copyright notice
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Service Manual",
            2: "© Copyright 2023 HP Inc. All rights reserved.",
            3: "Reproduction, adaptation, or translation without prior written permission is prohibited.",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_hp_laserjet_pattern(self, tmp_path: Path) -> None:
        """Test HP detection with 'HP LaserJet' pattern"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "HP LaserJet Enterprise MFP M631 Service Manual",
            2: "Introduction and Overview",
            3: "Safety Precautions",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper()

    async def test_hewlett_packard_enterprise_pattern(self, tmp_path: Path) -> None:
        """Test HP detection with 'Hewlett Packard Enterprise' pattern"""
        pdf_path = tmp_path / "service_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {
            1: "Hewlett Packard Enterprise Technical Documentation",
            2: "Product Specifications",
            3: "Installation Guide",
        }

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        assert manufacturer is not None
        assert "HP" in manufacturer.upper() or "HEWLETT" in manufacturer.upper()

    async def test_page_detection_executes_before_fallbacks(self, tmp_path: Path) -> None:
        """Verify page-based detection is attempted before filename parsing"""
        pdf_path = tmp_path / "CANON_iR_Manual.pdf"  # Filename suggests Canon
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)

        # Page text contains HP (should take priority over filename)
        ctx = ProcessingContext(
            document_id=str(uuid4()), file_path=str(pdf_path), document_type="service_manual", metadata={}
        )
        ctx.page_texts = {1: "HP Service Manual", 2: "HP Inc. Copyright Notice", 3: "Technical Specifications"}

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)

        # Should detect HP from pages, not Canon from filename
        assert manufacturer is not None
        assert "HP" in manufacturer.upper()
        assert "CANON" not in manufacturer.upper()


class TestFilenameExtractorFallback:
    """Test that extract_from_text invokes filename fallback when content yields no results"""

    def test_fallback_invoked_when_no_content_products(self) -> None:
        """Test filename fallback is invoked when content extraction returns nothing"""
        extractor = ProductExtractor(manufacturer_name="HP", debug=False)

        empty_text = "This document contains no product models."
        products = extractor.extract_from_text(text=empty_text, page_number=1, filename="HP_E475_SM.pdf")

        assert len(products) > 0
        assert any(p.model_number == "E475" for p in products)
        assert all(p.extraction_method == "filename_parsing" for p in products)

    def test_fallback_not_invoked_when_content_has_products(self) -> None:
        """Test filename fallback is NOT invoked when content extraction succeeds"""
        extractor = ProductExtractor(manufacturer_name="HP", debug=False)

        content_with_model = "HP LaserJet Pro M455dn specifications and features."
        products = extractor.extract_from_text(text=content_with_model, page_number=1, filename="HP_E475_SM.pdf")

        if products:
            assert not any(p.model_number == "E475" for p in products)
            assert not any(p.extraction_method == "filename_parsing" for p in products)

    def test_fallback_not_invoked_without_filename(self) -> None:
        """Test filename fallback is NOT invoked when filename parameter is missing"""
        extractor = ProductExtractor(manufacturer_name="HP", debug=False)

        empty_text = "This document contains no product models."
        products = extractor.extract_from_text(text=empty_text, page_number=1, filename=None)

        assert len(products) == 0

    def test_fallback_confidence_priority(self) -> None:
        """Test that filename fallback products have lower confidence than content-derived"""
        extractor = ProductExtractor(manufacturer_name="KONICA MINOLTA", debug=False)

        empty_text = "Generic service manual content."
        filename_products = extractor.extract_from_text(text=empty_text, page_number=1, filename="KM_C759_SM.pdf")

        assert len(filename_products) > 0
        for product in filename_products:
            assert product.confidence <= 0.5
            assert product.extraction_method == "filename_parsing"
