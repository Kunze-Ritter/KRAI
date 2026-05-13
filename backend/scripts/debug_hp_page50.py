#!/usr/bin/env python3
"""Debug HP page 50 in detail"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from uuid import uuid4

from processors.error_code_extractor import ErrorCodeExtractor
from processors.text_extractor import extract_text_from_pdf

print("Loading HP PDF...")
pdf_text, meta = extract_text_from_pdf(Path(r"C:\Manuals\HP\HP_E778_CPMD.pdf"), uuid4())

page = pdf_text[50]

print("=== PAGE 50 FULL TEXT ===")
print("=" * 80)
print(f"Length: {len(page)} chars")
print(f"First 1000 chars:\n{page[:1000]}")
print("=" * 80)

# Find codes
pattern = re.compile(r"\b(\d{2}\.\d{2}(?:\.\d{2})?)\b")
matches = list(pattern.finditer(page))

print(f"\nFound {len(matches)} code matches:")
for i, match in enumerate(matches, 1):
    code = match.group(1)
    start = max(0, match.start() - 100)
    end = min(len(page), match.end() + 200)
    context = page[start:end]

    print(f"\n{i}. Code: {code}")
    print(f"   Position: {match.start()}-{match.end()}")
    print(f"   Context: {context}")
    print(f"   {'-'*60}")

# Test extractor
print("\n" + "=" * 80)
print("TESTING EXTRACTOR:")
extractor = ErrorCodeExtractor()
extracted = extractor.extract_from_text(page, 50, "hp")

print(f"\nExtracted: {len(extracted)} codes")
if extracted:
    for c in extracted:
        print(f"  - {c.error_code} (conf: {c.confidence:.2f})")
        print(f"    Desc: {c.error_description[:100] if c.error_description else 'None'}")
else:
    print("  None!")

    # Manual check context validation
    print("\n" + "=" * 80)
    print("MANUAL CONTEXT CHECK for 10.26.15:")

    idx = page.find("10.26.15")
    if idx > 0:
        context_size = 500
        context = page[max(0, idx - context_size) : min(len(page), idx + context_size)]

        print(f"\nContext ({len(context)} chars):")
        print(context)

        # Check keywords
        required = [
            "error",
            "code",
            "fault",
            "trouble",
            "malfunction",
            "failure",
            "alarm",
            "warning",
            "service",
            "maintenance",
            "troubleshooting",
            "diagnostic",
            "status",
            "message",
            "alert",
            "problem",
            "issue",
            "exception",
        ]

        excluded = [
            "page",
            "figure",
            "table",
            "section",
            "chapter",
            "model",
            "serial",
            "copyright",
            "trademark",
            "manual",
            "guide",
            "version",
            "revision",
            "date",
            "user",
            "customer",
            "contact",
            "support",
        ]

        context_lower = context.lower()
        found_required = [kw for kw in required if kw in context_lower]
        found_excluded = [kw for kw in excluded if kw in context_lower]

        print(f"\nRequired keywords found: {found_required}")
        print(f"Excluded keywords found: {found_excluded}")

        has_req = len(found_required) > 0
        has_exc = len(found_excluded) > 0

        print("\nValidation:")
        print(f"  has_required: {has_req}")
        print(f"  has_excluded: {has_exc}")
        print(f"  PASS = has_required AND NOT has_excluded: {has_req and not has_exc}")
