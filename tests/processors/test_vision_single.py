"""
Quick Vision Test - Single Page Only
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from backend.processors.vision_extractor import VisionProductExtractor

logger = get_logger()


def test_single_page():
    """Test vision on ONE page only (fast test)"""

    pdf_path = Path(
        "c:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
    )

    logger.section("Vision Single Page Test")
    logger.info(f"PDF: {pdf_path.name}")
    logger.info("Testing PAGE 2 (known to have products)")

    # Initialize
    vision = VisionProductExtractor(vision_model="llava:13b", text_model="qwen2.5:7b", debug=True)

    # Test page 2
    logger.info("\nAnalyzing page 2 with Vision...")
    products = vision.extract_from_pdf_page(
        pdf_path, page_number=2, manufacturer="KONICA MINOLTA", target_section="specification"
    )

    # Results
    logger.section("Results")
    logger.info(f"Extracted {len(products)} products")

    if products:
        for p in products:
            logger.success(f"\n  {p.model_number}")
            logger.info(f"    Series: {p.product_series}")
            logger.info(f"    Type: {p.product_type}")
            logger.info(f"    Confidence: {p.confidence}")
            logger.info(f"    Specs: {len(p.specifications)}")
            if p.specifications:
                for key, value in list(p.specifications.items())[:5]:
                    logger.info(f"      - {key}: {value}")

        # Save
        output = Path("c:/Users/haast/Docker/KRAI-minimal/v2_tests/vision-page2.json")
        with open(output, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "page": 2,
                    "products": [
                        {
                            "model_number": p.model_number,
                            "display_name": p.display_name,
                            "specifications": p.specifications,
                        }
                        for p in products
                    ],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.success(f"\nSaved to: {output}")
    else:
        logger.warning("No products extracted!")


if __name__ == "__main__":
    test_single_page()
