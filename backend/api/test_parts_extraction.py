"""
Test parts extraction to see why part_name is empty
"""

# Example context from a parts catalog
test_contexts = [
    # Format 1: Part number with name on same line
    """
    41X5345 Toner Cartridge Black
    High yield cartridge for Lexmark printers
    Compatible with: MS810, MS811, MS812
    """,
    # Format 2: Part number with name on next line
    """
    Part Number: 41X5345
    Toner Cartridge - Black
    Description: High capacity toner for enterprise printers
    """,
    # Format 3: Table format
    """
    41X5345    |    Toner Black    |    $199.99
    """,
    # Format 4: Just part number (what we're seeing?)
    """
    41X5345
    """,
]


def extract_part_info(context: str, part_number: str):
    """Simulate the IMPROVED extraction logic"""
    lines = context.split("\n")
    part_name = None
    part_description = None

    for i, line in enumerate(lines):
        if part_number in line:
            # Try to extract name from same line
            remaining = line.split(part_number, 1)[1].strip()

            # Clean up common prefixes/separators
            for prefix in [":", "|", "-", "–"]:
                if remaining.startswith(prefix):
                    remaining = remaining[1:].strip()

            # If we have text after part number, use it as name
            if remaining and len(remaining) > 3:
                # Stop at common delimiters
                for delimiter in ["|", "\t", "  "]:  # pipe, tab, double space
                    if delimiter in remaining:
                        remaining = remaining.split(delimiter)[0].strip()
                part_name = remaining[:255]

            # If no name yet, check next line
            if not part_name and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Skip common labels
                for label in ["Description:", "Desc:", "Part Name:", "Name:"]:
                    if next_line.startswith(label):
                        next_line = next_line[len(label) :].strip()

                if next_line and len(next_line) > 3:
                    part_name = next_line[:255]

            # Description from next lines (skip if it's the name)
            for j in range(i + 1, min(i + 4, len(lines))):
                desc_line = lines[j].strip()
                if desc_line and len(desc_line) > 10 and desc_line != part_name:
                    part_description = desc_line[:500]
                    break

            break

    return part_name, part_description


print("=" * 60)
print("TESTING PARTS EXTRACTION")
print("=" * 60)

for i, context in enumerate(test_contexts, 1):
    print(f"\n--- Test {i} ---")
    print(f"Context:\n{context}")

    part_name, part_desc = extract_part_info(context, "41X5345")

    print("\nExtracted:")
    print(f"  Part Name: {part_name}")
    print(f"  Description: {part_desc}")
    print("-" * 60)

print("\n" + "=" * 60)
print("CONCLUSION")
print("=" * 60)
print(
    """
If part_name is None in most tests, the problem is:
1. Part number appears alone on a line (Format 4)
2. No text after part number on same line
3. Next line is too short (< 10 chars) or empty

SOLUTION:
- Improve pattern matching
- Look for part names in surrounding context
- Use LLM to extract part names if pattern fails
"""
)
