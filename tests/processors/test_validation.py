"""
Test ExtractedProduct validation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.models import ExtractedProduct

# Test data from LLM
test_data = {
    "model_number": "C4080",
    "product_series": "AccurioPress",
    "specifications": {
        "max_print_speed_ppm": 80,
        "max_resolution_dpi": 1200,
        "paper_size_max_sra3": True,
        "duplex_standard": True,
    },
}

print("Testing ExtractedProduct validation...")
print(f"Input data: {test_data}\n")

try:
    product = ExtractedProduct(
        model_number=test_data.get("model_number", ""),
        product_series=test_data.get("product_series"),
        product_type="printer",
        manufacturer_name="KONICA MINOLTA",
        confidence=0.85,
        source_page=1,
        extraction_method="llm",
        specifications=test_data.get("specifications", {}),
    )

    print("✓ Validation SUCCESS!")
    print(f"  Model: {product.model_number}")
    print(f"  Series: {product.product_series}")
    print(f"  Display: {product.display_name}")
    print(f"  Specs: {product.specifications}")

except Exception as e:
    print("✗ Validation FAILED!")
    print(f"  Error: {e}")
    import traceback

    traceback.print_exc()
