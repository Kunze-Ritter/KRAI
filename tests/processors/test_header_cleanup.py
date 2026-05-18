"""
Test Header Cleanup Functionality
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from backend.processors.chunker import SmartChunker


def test_header_cleanup():
    """Test that headers are correctly cleaned and extracted"""

    chunker = SmartChunker()

    # Test text with typical PDF header
    test_text = """AccurioPress C4080/C4070/C84hc/C74hc, AccurioPrint
C4065/C4065P

4. SERVICE MODE

This section describes the service mode settings for the printer.

Settings:
- Setting 1: Configure XYZ
- Setting 2: Adjust ABC
"""

    print("=" * 80)
    print("HEADER CLEANUP TEST")
    print("=" * 80)

    print("\nORIGINAL TEXT:")
    print("-" * 80)
    print(test_text[:200] + "...")

    # Test header cleaning
    cleaned_text, header_metadata = chunker._clean_headers(test_text)

    print("\n\nCLEANED TEXT:")
    print("-" * 80)
    print(cleaned_text[:200] + "...")

    print("\n\nEXTRACTED METADATA:")
    print("-" * 80)
    for key, value in header_metadata.items():
        print(f"  {key}: {value}")

    print("\n\nSTATISTICS:")
    print("-" * 80)
    print(f"  Original length: {len(test_text)} chars")
    print(f"  Cleaned length:  {len(cleaned_text)} chars")
    print(f"  Removed:         {len(test_text) - len(cleaned_text)} chars")
    print(f"  Reduction:       {((len(test_text) - len(cleaned_text)) / len(test_text) * 100):.1f}%")

    # Verify
    assert "AccurioPress" not in cleaned_text, "Header not removed!"
    assert "4. SERVICE MODE" in cleaned_text, "Content was removed!"
    assert "page_header" in header_metadata, "Header metadata not extracted!"
    assert "header_products" in header_metadata, "Product info not extracted!"

    print("\n✅ All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_header_cleanup()
