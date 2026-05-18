#!/usr/bin/env python3
"""Check HP pages 18-799 for error codes"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from uuid import uuid4

from processors.error_code_extractor import ErrorCodeExtractor
from processors.text_extractor import extract_text_from_pdf

print("Loading HP PDF...")
pdf_text, meta = extract_text_from_pdf(Path(r"C:\Manuals\HP\HP_E778_CPMD.pdf"), uuid4())

print(f"Loaded {len(pdf_text)} pages\n")

# Check specific pages
test_pages = [18, 20, 50, 100, 200, 400, 600, 799]

for page_num in test_pages:
    if page_num not in pdf_text:
        print(f"Page {page_num}: NOT FOUND")
        continue

    page = pdf_text[page_num]

    print(f"=== PAGE {page_num} ===")
    print(f"Length: {len(page)} chars")

    # Find all XX.XX or XX.XX.XX patterns
    pattern1 = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
    pattern2 = re.compile(r"\b(\d{2}\.\d{2})\b")

    codes_xxx = pattern1.findall(page)
    codes_xx = pattern2.findall(page)

    print(f"XX.XX.XX codes: {len(set(codes_xxx))} unique")
    if codes_xxx:
        print(f"  Examples: {list(set(codes_xxx))[:5]}")

    print(f"XX.XX codes: {len(set(codes_xx))} unique")
    if codes_xx:
        print(f"  Examples: {list(set(codes_xx))[:5]}")

    # Show first 400 chars
    print("\nFirst 400 chars:")
    print(page[:400])

    # Test with extractor
    extractor = ErrorCodeExtractor()
    extracted = extractor.extract_from_text(page, page_num, "hp")
    print(f"\nExtractor found: {len(extracted)} codes")
    for c in extracted[:3]:
        print(f"  - {c.error_code} (conf: {c.confidence:.2f})")

    print("\n" + "=" * 60 + "\n")

# Overall statistics for pages 18-799
print("=" * 60)
print("OVERALL STATISTICS for pages 18-799:")
print("=" * 60)

total_regex = 0
total_extracted = 0
extractor = ErrorCodeExtractor()

for page_num in range(18, min(800, len(pdf_text) + 1)):
    if page_num not in pdf_text:
        continue

    page = pdf_text[page_num]

    # Count regex matches
    pattern = re.compile(r"\b(\d{2}\.\d{2}(?:\.\d{2})?)\b")
    matches = set(pattern.findall(page))
    total_regex += len(matches)

    # Count extracted
    extracted = extractor.extract_from_text(page, page_num, "hp")
    total_extracted += len(extracted)

print(f"Total regex matches: {total_regex}")
print(f"Total extracted: {total_extracted}")
print(f"Filtered out: {total_regex - total_extracted}")
print(f"Extraction rate: {total_extracted/total_regex*100 if total_regex else 0:.1f}%")
