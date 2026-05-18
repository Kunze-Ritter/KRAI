"""Test solution extraction"""

import re

# Sample text from chunk
text = """Recommended action for customers
Follow these troubleshooting steps in the order presented.
Use the following general troubleshooting steps to try to resolve the problem.
1. Set the time and date on the printer control panel.
2. If the error persists, contact your HP-authorized service or support provider, or contact customer support at www.hp.com/go/contactHP.

Recommended action for call-center agents and onsite technicians
Follow these troubleshooting steps in the order presented.
Use the following general troubleshooting steps to try to resolve the problem.
1. Turn the printer off, and then on.
2. Set the time and date on the printer control panel.
3. Replace the formatter."""

print("=" * 80)
print("TESTING EXTRACTION")
print("=" * 80)

# Test current regex
if "Recommended action for call-center agents" in text or "Recommended action for onsite technicians" in text:
    print("\n✅ Found 'Recommended action for call-center agents'")

    match = re.search(
        r"Recommended action for (?:call-center agents|onsite technicians)[^\n]*\n(.+?)(?=\n\s*\d+\.\d+|$)",
        text,
        re.DOTALL,
    )

    if match:
        print("✅ Regex matched!")
        solution = match.group(1).strip()
        print(f"\nExtracted text ({len(solution)} chars):")
        print("-" * 80)
        print(solution)
        print("-" * 80)

        # Extract numbered steps
        steps = re.findall(r"\d+\.\s+[^\n]+", solution)
        print(f"\n✅ Found {len(steps)} steps:")
        for step in steps:
            print(f"  {step}")
    else:
        print("❌ Regex did not match")
else:
    print("❌ Text not found")
