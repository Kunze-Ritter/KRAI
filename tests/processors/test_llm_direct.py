"""
Direct LLM Extractor Test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.llm_extractor import LLMProductExtractor
from backend.processors.logger import get_logger

logger = get_logger()


def test_llm_extraction():
    """Test LLM extraction directly"""

    logger.section("LLM Direct Test")

    # Sample text with products
    sample_text = """
    AccurioPress C4080 / C4070 Specifications

    AccurioPress C4080
    - Print Speed: 80 ppm (A4)
    - Resolution: 1200 x 1200 dpi
    - Paper Size: Max SRA3
    - Duplex: Standard
    - Paper Capacity: 3,000 sheets (standard), 6,000 sheets (max)
    - Monthly Duty Cycle: 300,000 pages

    AccurioPress C4070
    - Print Speed: 70 ppm (A4)
    - Resolution: 1200 x 1200 dpi
    - Paper Size: Max SRA3

    Options:
    MK-746 Booklet Finisher
    - Stapling capacity: 100 sheets
    - Folding types: Half-fold, Tri-fold

    SD-513 Paper Deck
    - Capacity: 2,500 sheets
    """

    # Initialize LLM extractor
    try:
        llm = LLMProductExtractor(model_name="qwen2.5:7b", debug=True)
        logger.success("LLM Extractor initialized!")
    except Exception as e:
        logger.error(f"Failed to init LLM: {e}")
        return

    # Extract
    logger.info("\nExtracting products...")
    logger.info(f"Sample text length: {len(sample_text)}")

    products = llm.extract_from_specification_section(sample_text, manufacturer="KONICA MINOLTA", page_number=1)

    logger.info(f"Returned products: {products}")

    # Results
    logger.section("Results")
    logger.info(f"Extracted {len(products)} products")

    if products:
        for p in products:
            logger.success(f"\n  {p.model_number}")
            logger.info(f"    Series: {p.product_series}")
            logger.info(f"    Type: {p.product_type}")
            logger.info(f"    Method: {p.extraction_method}")
            logger.info(f"    Specs: {len(p.specifications)}")
            if p.specifications:
                for key, value in list(p.specifications.items())[:10]:
                    logger.info(f"      - {key}: {value}")
    else:
        logger.warning("No products extracted!")


if __name__ == "__main__":
    test_llm_extraction()
