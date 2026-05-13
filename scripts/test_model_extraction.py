"""
Test model extraction from filename
"""

import re


def extract_model_from_filename(filename):
    """Extract model number from filename using multiple patterns"""
    patterns = [
        r"[A-Z]{1,3}[-_]?[0-9]{3,5}[A-Z]*",  # E877, M454dn, HL-L8360CDW
        r"[A-Z]{2,4}[-_][A-Z]?[0-9]{3,5}[A-Z]*",  # HP-E877z, HL-L8360
        r"(?:Color\s+)?LaserJet\s+(?:Managed\s+)?(?:MFP\s+)?([A-Z]?[0-9]{3,5}[A-Z]*)",  # LaserJet E877z
    ]

    for pattern in patterns:
        matches = re.findall(pattern, filename, re.IGNORECASE)
        if matches:
            model = matches[0] if isinstance(matches[0], str) else matches[0][0]
            model = model.strip().replace("_", "-")
            return model

    return None


# Test cases
test_files = [
    "HP_E877_CPMD.pdf",
    "Brother_HL-L8360CDW_UM_ENG.pdf",
    "HP_M454dn_ServiceManual.pdf",
    "Canon_iR-ADV_C5550i_SM.pdf",
    "HP_Color_LaserJet_Managed_MFP_E877z.pdf",
]

print("=" * 80)
print("🧪 Model Extraction Test")
print("=" * 80)
print()

for filename in test_files:
    model = extract_model_from_filename(filename)
    if model:
        print(f"✅ {filename:50} → {model}")
    else:
        print(f"❌ {filename:50} → No match")

print()
print("=" * 80)
