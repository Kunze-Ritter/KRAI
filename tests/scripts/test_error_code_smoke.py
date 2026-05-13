"""Smoke tests for manufacturer-specific error code validation"""

import os
import sys
from textwrap import dedent

# Ensure backend package is importable when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from processors.error_code_extractor import ErrorCodeExtractor
from processors.models import ExtractedErrorCode


def build_error_code(**overrides):
    base = dict(
        error_code="13.20.01",
        error_description="Fuser temperature error detected in primary assembly",
        solution_text="1. Power cycle printer\n2. Replace fuser assembly",
        context_text=dedent(
            """
            Error code 13.20.01 occurs when the printer's fuser overheats during operation.
            Recommended action: Power cycle the printer and inspect the fuser assembly for damage.
            Additional notes: Ensure adequate ventilation around the device to prevent recurrence.
            """
        ),
        confidence=0.85,
        page_number=3,
        extraction_method="hp_pattern",
        severity_level="high",
        manufacturer_name="HP",
        effective_manufacturer="HP",
    )
    base.update(overrides)
    return ExtractedErrorCode(**base)


def run_manual_validation_checks():
    extractor = ErrorCodeExtractor()

    # HP validation regex (\d{2}.\d{1,3}[xX]?.\d{2})
    valid_hp = build_error_code(error_code="13.20.01")
    invalid_hp = build_error_code(error_code="13-20-01")

    assert not extractor.validate_extraction(valid_hp), "HP code should pass validation"
    print("✓ HP validation: '13.20.01' accepted")

    invalid_hp_errors = extractor.validate_extraction(invalid_hp)
    assert invalid_hp_errors and any(
        "validation regex" in err.error_message for err in invalid_hp_errors
    ), "Expected regex validation error for HP code with wrong format"
    print("✓ HP validation: '13_20_01' rejected")

    # Canon validation regex (E### or ####)
    valid_canon = build_error_code(
        manufacturer_name="Canon",
        effective_manufacturer="Canon",
        error_code="E826",
        extraction_method="canon_pattern",
    )
    invalid_canon = build_error_code(
        manufacturer_name="Canon",
        effective_manufacturer="Canon",
        error_code="13.20.01",
        extraction_method="canon_pattern",
    )

    assert not extractor.validate_extraction(valid_canon), "Canon E-code should pass validation"
    print("✓ Canon validation: 'E826' accepted")

    canon_errors = extractor.validate_extraction(invalid_canon)
    assert canon_errors and any(
        "validation regex" in err.error_message for err in canon_errors
    ), "Expected regex validation error for Canon code using HP format"
    print("✓ Canon validation: HP-style code rejected for Canon")

    # Unknown manufacturer should skip regex validation gracefully
    unknown = build_error_code(
        manufacturer_name="UnknownBrand",
        effective_manufacturer=None,
        error_code="999",
        extraction_method="unknown_pattern",
    )
    assert not extractor.validate_extraction(unknown), "Unknown manufacturer should not fail due to missing regex"
    print("✓ Unknown manufacturer: validation skipped without errors")


def main():
    run_manual_validation_checks()
    print("\n============================================================")
    print("✅ ERROR CODE SMOKE TESTS PASSED")
    print("============================================================")


if __name__ == "__main__":
    main()
