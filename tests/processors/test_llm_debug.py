"""
Full LLM extraction debug test
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.llm_extractor import LLMProductExtractor

# Sample text
text = """
AccurioPress C4080 / C4070 Specifications

AccurioPress C4080
- Print Speed: 80 ppm (A4)
- Resolution: 1200 x 1200 dpi

AccurioPress C4070
- Print Speed: 70 ppm (A4)

MK-746 Booklet Finisher
- Stapling capacity: 100 sheets
"""

print("=== LLM EXTRACTION DEBUG TEST ===\n")

# Initialize
print("1. Initializing LLM Extractor...")
llm = LLMProductExtractor(model_name="qwen2.5:7b", debug=False)  # debug=False to see our output clearly
print("   ✓ Initialized\n")

# Call extraction
print("2. Calling extract_from_specification_section...")
products = llm.extract_from_specification_section(text, manufacturer="KONICA MINOLTA", page_number=1)

print(f"3. Got {len(products)} products back\n")

# Show results
if products:
    print("=== EXTRACTED PRODUCTS ===")
    for i, p in enumerate(products, 1):
        print(f"\n{i}. {p.model_number}")
        print(f"   Series: {p.product_series}")
        print(f"   Type: {p.product_type}")
        print(f"   Method: {p.extraction_method}")
        print(f"   Specs: {json.dumps(p.specifications, indent=6)}")
else:
    print("❌ NO PRODUCTS EXTRACTED!")
    print("\nDebugging: Let me call Ollama directly...")

    # Direct Ollama call
    import requests

    prompt = llm._build_extraction_prompt(text, "KONICA MINOLTA")

    print(f"\nPrompt length: {len(prompt)}")
    print("\n=== PROMPT ===")
    print(prompt[:500])
    print("...")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 2000},
        },
        timeout=60,
    )

    result = response.json()
    llm_response = result.get("response", "")

    print("\n=== OLLAMA RAW RESPONSE ===")
    print(llm_response)

    # Try to parse
    try:
        data = json.loads(llm_response)
        print("\n✓ Valid JSON")
        print(f"Type: {type(data)}")
        print(f"Data: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"\n✗ JSON Parse Error: {e}")
