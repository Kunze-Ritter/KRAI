"""
Test Vision-based Product Extraction
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from backend.processors.vision_extractor import VisionProductExtractor

logger = get_logger()


def test_vision_extraction():
    """Test vision extraction on AccurioPress PDF"""

    # PDF path
    pdf_path = Path(
        "c:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
    )

    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return

    logger.section("Vision Product Extraction Test")
    logger.info(f"PDF: {pdf_path.name}")

    # Initialize vision extractor
    vision_extractor = VisionProductExtractor(
        vision_model="llava:13b",
        text_model="qwen2.5:7b",
        debug=True,  # or llava:7b for faster
    )

    # Find specification pages
    logger.info("Step 1: Finding specification pages...")
    spec_pages = vision_extractor.find_specification_pages(pdf_path, max_pages=100)
    logger.info(f"Found {len(spec_pages)} specification pages: {spec_pages[:10]}")

    # If no spec pages found, test known product pages directly
    if not spec_pages:
        logger.warning("No spec pages found via keywords. Testing known product pages...")
        test_pages = [2, 3, 4, 5, 10, 15, 20]  # Known pages with products
    else:
        test_pages = spec_pages[:3]  # Test first 3 pages

    # Test on pages
    all_products = []

    for page_num in test_pages:
        logger.info(f"\nStep 2: Analyzing page {page_num} with Vision...")

        products = vision_extractor.extract_from_pdf_page(
            pdf_path, page_num, manufacturer="KONICA MINOLTA", target_section="specification"
        )

        if products:
            logger.success(f"  ✓ Extracted {len(products)} products from page {page_num}")
            for p in products:
                logger.info(f"    - {p.model_number}: {len(p.specifications)} specs")
                if p.specifications:
                    logger.info(f"      Specs: {list(p.specifications.keys())[:5]}...")

            all_products.extend(products)
        else:
            logger.warning(f"  No products found on page {page_num}")

    # Summary
    logger.section("Results Summary")
    logger.info(f"Total products extracted: {len(all_products)}")
    logger.info(f"Pages analyzed: {test_pages}")

    # Show detailed results
    if all_products:
        logger.info("\nExtracted Products:")
        for product in all_products:
            logger.info(f"\n  {product.model_number}")
            logger.info(f"    Type: {product.product_type}")
            logger.info(f"    Confidence: {product.confidence}")
            logger.info(f"    Page: {product.source_page}")
            logger.info(f"    Method: {product.extraction_method}")
            if product.specifications:
                logger.info(f"    Specifications ({len(product.specifications)}):")
                for key, value in list(product.specifications.items())[:10]:
                    logger.info(f"      - {key}: {value}")

    # Save results
    output_path = Path("c:/Users/haast/Docker/KRAI-minimal/v2_tests/vision-test-results.json")
    save_results(all_products, output_path)
    logger.success(f"\nResults saved to: {output_path}")


def save_results(products, output_path: Path):
    """Save extracted products to JSON"""

    data = {
        "total_products": len(products),
        "extraction_method": "vision",
        "products": [
            {
                "model_number": p.model_number,
                "display_name": p.display_name,
                "product_series": p.product_series,
                "product_type": p.product_type,
                "manufacturer_name": p.manufacturer_name,
                "confidence": p.confidence,
                "source_page": p.source_page,
                "extraction_method": p.extraction_method,
                "specifications": p.specifications,
            }
            for p in products
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    try:
        test_vision_extraction()
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
