#!/usr/bin/env python3
"""Find HP wildcard error codes"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from uuid import uuid4

from backend.processors.text_extractor import extract_text_from_pdf

print("Loading HP PDF...")
pdf_text, meta = extract_text_from_pdf(Path(r"C:\Manuals\HP\HP_E778_CPMD.pdf"), uuid4())

# Search for wildcard patterns
wildcard_pattern = re.compile(r"\b(\d{2}\.[xX]\d\.\d{2})\b")

found_wildcards = []
for page_num, page_text in pdf_text.items():
    matches = wildcard_pattern.findall(page_text)
    if matches:
        for match in matches:
            found_wildcards.append((page_num, match))

print(f"\nFound {len(found_wildcards)} wildcard codes:")
for page, code in found_wildcards[:20]:
    print(f"  Page {page}: {code}")

# Also search for "10.0x" format
print("\n" + "=" * 60)
alt_pattern = re.compile(r"(\d{2}\.0x\.\d{2})", re.IGNORECASE)
found_alt = []
for page_num, page_text in list(pdf_text.items())[:100]:
    matches = alt_pattern.findall(page_text)
    if matches:
        for match in matches:
            found_alt.append((page_num, match))
            # Show context
            idx = page_text.find(match)
            if idx > 0:
                context = page_text[max(0, idx - 100) : min(len(page_text), idx + 200)]
                print(f"\nPage {page_num}: {match}")
                print(f"Context: {context}")

print(f"\nTotal '10.0x' format: {len(found_alt)}")
