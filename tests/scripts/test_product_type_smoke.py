"""Smoke test for product type alignment with ALLOWED_PRODUCT_TYPES"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from processors.models import ExtractedProduct
from processors.product_extractor import ProductExtractor


def test_product_type_normalization():
    """Test that product types are normalized against ALLOWED_PRODUCT_TYPES"""
    extractor = ProductExtractor(debug=False)

    # Test 1: Valid type with different case
    normalized = extractor._ensure_allowed_product_type("Laser_Printer", "smoke-test")
    print(f"✓ Test 1 - Normalized 'Laser_Printer' to: '{normalized}'")
    assert normalized == "laser_printer", f"Expected 'laser_printer', got '{normalized}'"

    # Test 2: Invalid type falls back to default
    normalized_invalid = extractor._ensure_allowed_product_type("unknown_type", "smoke-test")
    print(f"✓ Test 2 - Invalid type 'unknown_type' normalized to: '{normalized_invalid}'")
    assert normalized_invalid == "laser_multifunction", f"Expected 'laser_multifunction', got '{normalized_invalid}'"

    # Test 3: Create product with normalized type
    product = ExtractedProduct(
        model_number="C4080",
        product_series="AccurioPress",
        product_type=normalized,
        manufacturer_name="Konica Minolta",
        confidence=0.8,
    )
    print(f"✓ Test 3 - Created product with type: '{product.product_type}'")

    # Test 4: Validate product (should have no errors)
    errors = extractor.validate_extraction(product)
    print(f"✓ Test 4 - Validation errors: {errors}")
    assert len(errors) == 0, f"Expected no validation errors, got: {errors}"

    # Test 5: Test Pydantic validator directly
    try:
        invalid_product = ExtractedProduct(
            model_number="C4080",
            product_series="AccurioPress",
            product_type="invalid_type_not_in_list",
            manufacturer_name="Konica Minolta",
            confidence=0.8,
        )
        print("✗ Test 5 - FAILED: Pydantic should have rejected invalid type")
        assert False, "Pydantic validator should have raised ValueError"
    except ValueError as e:
        print(f"✓ Test 5 - Pydantic correctly rejected invalid type: {str(e)[:80]}...")

    print("\n" + "=" * 60)
    print("✅ ALL SMOKE TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_product_type_normalization()
