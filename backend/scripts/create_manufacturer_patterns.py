#!/usr/bin/env python3
"""
Manufacturer Pattern Creation Tool

Helps create error code patterns for new manufacturers.
Supports copying from existing manufacturers or creating from scratch.
"""

import json
import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

PATTERNS_FILE = Path(__file__).parent.parent / "config" / "error_code_patterns.json"

# Common manufacturer rebrands
REBRANDS = {
    "utax": "kyocera",
    "ta": "kyocera",
    "triumph-adler": "kyocera",
    "olivetti": "konica_minolta",
    "develop": "konica_minolta",
    "muratec": "brother",
    "gestetner": "ricoh",
    "lanier": "ricoh",
    "savin": "ricoh",
    "nrg": "ricoh",
}


def load_patterns() -> dict:
    """Load existing patterns from JSON"""
    with open(PATTERNS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_patterns(patterns: dict):
    """Save patterns to JSON with formatting"""
    with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved to: {PATTERNS_FILE}")


def list_manufacturers(patterns: dict):
    """List all configured manufacturers"""
    print("\n📋 CONFIGURED MANUFACTURERS:")
    print("=" * 60)

    manufacturers = [k for k in patterns if k != "extraction_rules" and not k.startswith("$")]

    for i, mfr in enumerate(sorted(manufacturers), 1):
        config = patterns[mfr]
        name = config.get("manufacturer_name", mfr)
        fmt = config.get("format", "N/A")
        pattern_count = len(config.get("patterns", []))

        print(f"{i:2}. {name:<20} Format: {fmt:<30} ({pattern_count} patterns)")

    print("=" * 60)


def copy_from_existing(patterns: dict, new_name: str, base_manufacturer: str) -> dict:
    """Copy patterns from existing manufacturer"""

    # Check if base exists
    if base_manufacturer not in patterns:
        print(f"\n❌ Base manufacturer '{base_manufacturer}' not found!")
        list_manufacturers(patterns)
        sys.exit(1)

    # Copy patterns
    base_config = patterns[base_manufacturer].copy()

    # Update name
    base_config["manufacturer_name"] = new_name
    base_config["description"] = f"{new_name} error code patterns (based on {base_manufacturer})"

    print(f"\n✅ Copied patterns from '{base_manufacturer}' to '{new_name}'")
    print(f"   Format: {base_config.get('format')}")
    print(f"   Patterns: {len(base_config.get('patterns', []))}")

    return base_config


def create_interactive(new_name: str) -> dict:
    """Interactive pattern creation"""
    print(f"\n🔧 INTERACTIVE PATTERN CREATION: {new_name}")
    print("=" * 60)

    # Get format
    print("\nWhat format do error codes use?")
    print("Examples:")
    print("  - HP: XX.XX.XX or XX.XX")
    print("  - Konica Minolta: C####, J##-##")
    print("  - Canon: E### or ####")

    format_str = input("\nFormat: ").strip()

    # Get example codes
    print("\nProvide 3-5 example error codes (comma-separated):")
    print("Example: C1234,C5678,E01-02")

    examples_str = input("\nExamples: ").strip()
    examples = [e.strip() for e in examples_str.split(",")]

    # Generate patterns based on examples
    patterns = []
    validation_parts = []

    for example in examples:
        # Analyze pattern
        if re.match(r"^[A-Z]\d{4}$", example):
            # Format: C1234
            patterns.append(r"error\s+code\s+([A-Z]\d{4})")
            patterns.append(r"\b([A-Z]\d{4})\b")
            validation_parts.append(r"^[A-Z]\d{4}$")

        elif re.match(r"^[A-Z]\d{2}-\d{2}$", example):
            # Format: E01-02
            patterns.append(r"error\s+code\s+([A-Z]\d{2}-\d{2})")
            patterns.append(r"\b([A-Z]\d{2}-\d{2})\b")
            validation_parts.append(r"^[A-Z]\d{2}-\d{2}$")

        elif re.match(r"^\d{2}\.\d{2}$", example):
            # Format: 10.26
            patterns.append(r"error\s+code\s+(\d{2}\.\d{2})")
            patterns.append(r"\b(\d{2}\.\d{2})\b")
            validation_parts.append(r"^\d{2}\.\d{2}$")

    # Remove duplicates
    patterns = list(set(patterns))
    validation_regex = "|".join(set(validation_parts))

    config = {
        "manufacturer_name": new_name,
        "description": f"{new_name} error code patterns",
        "format": format_str,
        "patterns": patterns,
        "validation_regex": validation_regex,
        "categories": {
            "system": "System and general errors",
            "paper_jam": "Paper handling errors",
            "general": "General error category",
        },
    }

    print(f"\n✅ Created {len(patterns)} patterns")
    print(f"   Validation regex: {validation_regex}")

    return config


def test_patterns(config: dict, test_codes: list[str]):
    """Test patterns against example codes"""
    print("\n🧪 TESTING PATTERNS:")
    print("=" * 60)

    patterns = config.get("patterns", [])
    validation_regex = config.get("validation_regex", "")

    for test_code in test_codes:
        matched = False

        for pattern_str in patterns:
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(test_code):
                    matched = True
                    break
            except Exception:
                pass

        # Validate
        valid = bool(re.match(validation_regex, test_code)) if validation_regex else True

        status = "✅" if (matched and valid) else "❌"
        print(f"  {status} {test_code:<15} Matched: {matched}, Valid: {valid}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Create error code patterns for new manufacturers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Copy from existing manufacturer
  python create_manufacturer_patterns.py --name UTAX --based-on kyocera

  # Interactive creation
  python create_manufacturer_patterns.py --name UTAX --interactive

  # List configured manufacturers
  python create_manufacturer_patterns.py --list
        """,
    )

    parser.add_argument("--name", help="New manufacturer name")
    parser.add_argument("--based-on", help="Copy patterns from existing manufacturer")
    parser.add_argument("--interactive", action="store_true", help="Interactive pattern creation")
    parser.add_argument("--list", action="store_true", help="List configured manufacturers")
    parser.add_argument("--test", nargs="+", help="Test codes to validate patterns")

    args = parser.parse_args()

    # Load existing patterns
    patterns = load_patterns()

    # List manufacturers
    if args.list:
        list_manufacturers(patterns)
        return

    # Validate name
    if not args.name and not args.list:
        parser.print_help()
        return

    # Normalize name
    manufacturer_key = args.name.lower().replace(" ", "_")

    # Check if already exists
    if manufacturer_key in patterns:
        print(f"\n⚠️  WARNING: Manufacturer '{args.name}' already exists!")
        response = input("Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            return

    # Check for rebrand
    if manufacturer_key in REBRANDS and not args.based_on:
        suggested = REBRANDS[manufacturer_key]
        print(f"\n💡 TIP: {args.name} is commonly a {suggested} rebrand.")
        response = input(f"Use {suggested} patterns? (Y/n): ")
        if response.lower() != "n":
            args.based_on = suggested

    # Create patterns
    if args.based_on:
        config = copy_from_existing(patterns, args.name, args.based_on)
    elif args.interactive:
        config = create_interactive(args.name)
    else:
        print("\n❌ ERROR: Must specify --based-on or --interactive")
        parser.print_help()
        return

    # Test if requested
    if args.test:
        test_patterns(config, args.test)

    # Save
    patterns[manufacturer_key] = config
    save_patterns(patterns)

    print(f"\n✅ SUCCESS! Patterns for '{args.name}' created.")
    print("\n📝 Next steps:")
    print("   1. Test extraction:")
    print("      python scripts/test_error_code_extraction.py \\")
    print("        --pdf <path> \\")
    print(f"        --manufacturer {manufacturer_key}")
    print(f"\n   2. Review patterns in: {PATTERNS_FILE}")


if __name__ == "__main__":
    main()
