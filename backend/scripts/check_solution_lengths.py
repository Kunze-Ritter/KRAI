#!/usr/bin/env python3
"""Check solution text lengths in extracted error codes"""

import json
from pathlib import Path

# Load test results
hp_file = Path("test_hp_NO_PART_NUMBERS.json")
km_file = Path("test_km_AFTER_FIX.json")

for file in [hp_file, km_file]:
    if not file.exists():
        print(f"File not found: {file}")
        continue

    print(f"\n{'='*60}")
    print(f"FILE: {file.name}")
    print(f"{'='*60}")

    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "error_codes" in data[0]:
            error_codes = data[0]["error_codes"]
        else:
            error_codes = data
    else:
        error_codes = data.get("error_codes", [])

    if not error_codes:
        print("No error codes found")
        continue

    # Statistics
    total = len(error_codes)
    with_solution = len([c for c in error_codes if c["has_solution"]])
    solution_lengths = [c["solution_length"] for c in error_codes if c["has_solution"]]

    print(f"\nTotal codes: {total}")
    print(f"With solution: {with_solution} ({with_solution/total*100:.1f}%)")

    if solution_lengths:
        print("\nSolution lengths:")
        print(f"  Min:     {min(solution_lengths)} chars")
        print(f"  Max:     {max(solution_lengths)} chars")
        print(f"  Average: {sum(solution_lengths)/len(solution_lengths):.0f} chars")
        print(f"  Median:  {sorted(solution_lengths)[len(solution_lengths)//2]} chars")

    # Show examples
    print("\nTop 5 longest solutions:")
    longest = sorted(error_codes, key=lambda x: x["solution_length"], reverse=True)[:5]
    for i, code in enumerate(longest, 1):
        print(f"{i}. {code['code']}: {code['solution_length']} chars (page {code['page']})")

    print("\nTop 5 shortest solutions:")
    shortest = sorted([c for c in error_codes if c["has_solution"]], key=lambda x: x["solution_length"])[:5]
    for i, code in enumerate(shortest, 1):
        print(f"{i}. {code['code']}: {code['solution_length']} chars (page {code['page']})")

    # Check for truncated (exactly 1000 chars = likely truncated)
    truncated = [c for c in error_codes if c["solution_length"] == 1000]
    if truncated:
        print(f"\n⚠️  WARNING: {len(truncated)} solutions are exactly 1000 chars (likely truncated!):")
        for code in truncated[:3]:
            print(f"  - {code['code']} (page {code['page']})")
