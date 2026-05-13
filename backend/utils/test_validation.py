"""Test model number validation"""

from model_number_cleaner import is_valid_model_number

test_cases = [
    ("C4080", True, "Valid Konica model"),
    ("F2A72-67901", False, "HP part number"),
    ("B5L46-67912", False, "HP part number"),
    ("1PV95A", False, "HP part number"),
    ("Business card tray only", False, "Description"),
    ("RU-702", True, "Valid Konica accessory"),
    ("RM2-5683-000CN", False, "HP internal part"),
    ("C10500", True, "Valid AccurioPrint"),
    ("C10500S", True, "Valid AccurioPrint variant"),
    ("TN328K", True, "Valid toner"),
]

print("Model Number Validation Tests:")
print("=" * 80)
print(f"{'Model Number':<30} {'Expected':<10} {'Result':<10} {'Status':<10} {'Reason'}")
print("=" * 80)

for model, expected, reason in test_cases:
    result = is_valid_model_number(model)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    print(f"{model:<30} {expected!s:<10} {result!s:<10} {status:<10} {reason}")

print("=" * 80)
