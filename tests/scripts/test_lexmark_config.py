"""Test Lexmark config loading and pattern matching"""

import sys

sys.path.insert(0, "backend")

from utils.manufacturer_config import get_manufacturer_config

# Load Lexmark config
config = get_manufacturer_config("Lexmark")

if config:
    print(f"✓ Loaded config: {config.canonical_name}")
    print(f"  Patterns: {len(config.product_patterns)}")
    print(f"  Series: {len(config.series)}")
    print()

    # Get compiled patterns
    patterns = config.get_compiled_patterns()
    print(f"✓ Compiled {len(patterns)} patterns:")
    for series, pattern, ptype in patterns:
        print(f"  - {series}: {pattern.pattern[:50]}...")
    print()

    # Test with filename
    test_text = "CX833 CX961 CX962 CX963 XC8355 XC9635 XC9645 SM"
    print(f"Testing with: '{test_text}'")
    print()

    found = []
    for series, pattern, ptype in patterns:
        matches = pattern.finditer(test_text)
        for match in matches:
            model = match.group(0).strip()
            found.append((series, model, ptype))
            print(f"  ✓ {series}: {model} ({ptype})")

    print()
    print(f"Total found: {len(found)} products")
else:
    print("✗ Failed to load Lexmark config")
