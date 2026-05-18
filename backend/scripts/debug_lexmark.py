#!/usr/bin/env python3
"""Debug Lexmark error code formats"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from uuid import uuid4

from processors.text_extractor import extract_text_from_pdf

print("Loading Lexmark PDF...")
pdf_text, meta = extract_text_from_pdf(Path(r"C:\Manuals\Lexmark\7566-69x_sm.pdf"), uuid4())

print(f"Loaded {len(pdf_text)} pages\n")

# Sample different pages
test_pages = [100, 500, 1000, 1500]

for page_num in test_pages:
    if page_num not in pdf_text:
        continue

    page = pdf_text[page_num]
    print(f"=== PAGE {page_num} ===")

    # Search for various error code patterns
    patterns = [
        (r"\b(\d{3}\.\d{2})\b", "###.##"),
        (r"\b(\d{2}\.\d{2})\b", "##.##"),
        (r"\b(9\d{2})\b", "9##"),
        (r"\b(SC\d{3})\b", "SC###"),
        (r"error\s+(\d{3})", "error ###"),
    ]

    for pattern, label in patterns:
        matches = re.findall(pattern, page[:2000])  # First 2000 chars
        if matches:
            print(f"  {label}: {len(set(matches))} unique - {list(set(matches))[:5]}")

    # Show sample text
    if "error" in page.lower() or "code" in page.lower():
        idx = page.lower().find("error")
        if idx < 0:
            idx = page.lower().find("code")
        if idx > 0:
            print("\n  Sample text around 'error/code':")
            print(f"  {page[max(0,idx-50):min(len(page),idx+150)]}")

    print()
