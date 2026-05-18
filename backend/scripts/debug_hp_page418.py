#!/usr/bin/env python3
"""Debug HP page 418 in detail"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from uuid import uuid4

from processors.text_extractor import extract_text_from_pdf

print("Loading HP PDF...")
pdf_text, meta = extract_text_from_pdf(Path(r"C:\Manuals\HP\HP_E778_CPMD.pdf"), uuid4())

page = pdf_text[418]

print("=== PAGE 418 ===")
print(f"Length: {len(page)} chars\n")

# Show full text
print("FULL TEXT:")
print("=" * 80)
print(page)
print("=" * 80)

# Find all XX.XX.XX codes
pattern = re.compile(r"\b(\d{2}\.\d{2}\.?\d{0,2})\b")
matches = pattern.finditer(page)

print("\nALL MATCHES:")
for i, match in enumerate(matches, 1):
    code = match.group(1)
    start = max(0, match.start() - 50)
    end = min(len(page), match.end() + 100)
    context = page[start:end]
    print(f"\n{i}. Code: {code}")
    print(f"   Context: {context}")
