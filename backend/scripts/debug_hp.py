#!/usr/bin/env python3
"""Quick debug script for HP error code extraction"""

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

# Test page with many codes
page_num = 45
page = pdf_text[page_num]

print(f"=== PAGE {page_num} ===")
print(f"Text length: {len(page)} chars")
print("\nFirst 500 chars:")
print(page[:500])

# Find all XX.XX.XX patterns
pattern = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
all_matches = pattern.findall(page)
print(f"\n{'='*60}")
print(f"Regex found {len(all_matches)} XX.XX.XX codes:")
print(f"  {all_matches[:10]}")

# Now extract with ErrorCodeExtractor
print(f"\n{'='*60}")
print("Testing ErrorCodeExtractor...")
extractor = ErrorCodeExtractor()
codes = extractor.extract_from_text(page, page_num, "hp")

print(f"\nExtractor returned: {len(codes)} codes")
for i, c in enumerate(codes, 1):
    print(f"  {i}. {c.error_code} (conf: {c.confidence:.2f})")
    print(f"     Desc: {c.error_description[:60] if c.error_description else 'None'}...")

print(f"\n{'='*60}")
print(f"SUMMARY: {len(all_matches)} regex matches → {len(codes)} extracted")
print(f"Filtered out: {len(all_matches) - len(codes)} codes")

# Check one more page
print(f"\n{'='*60}")
print("=== PAGE 418 ===")
page = pdf_text[418]
all_matches = pattern.findall(page)
codes = extractor.extract_from_text(page, 418, "hp")
print(f"Regex: {len(all_matches)} codes")
print(f"Extractor: {len(codes)} codes")
print(f"Codes: {[c.error_code for c in codes]}")
