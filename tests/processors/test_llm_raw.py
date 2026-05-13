"""
Test raw Ollama response
"""

import json

import requests

# Sample text
text = """
AccurioPress C4080 / C4070 Specifications

AccurioPress C4080
- Print Speed: 80 ppm (A4)
- Resolution: 1200 x 1200 dpi
- Paper Size: Max SRA3
- Duplex: Standard

Options:
MK-746 Booklet Finisher
- Stapling capacity: 100 sheets
"""

# Prompt
prompt = f"""Extract ALL products from this KONICA MINOLTA technical document.

TEXT:
{text}

INSTRUCTIONS:
1. Find ALL product model numbers
2. Extract specifications
3. Return ONLY valid JSON array

JSON FORMAT:
[
  {{
    "model_number": "C4080",
    "product_series": "AccurioPress",
    "specifications": {{
      "max_print_speed_ppm": 80,
      "max_resolution_dpi": 1200
    }}
  }}
]

JSON:"""

print("Calling Ollama...")
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

print(f"\n=== RAW RESPONSE ({len(llm_response)} chars) ===")
print(llm_response)
print("\n=== END ===\n")

# Try to parse
try:
    data = json.loads(llm_response)
    print(f"✓ Valid JSON! Type: {type(data)}")
    print(f"  Content: {data}")
except json.JSONDecodeError as e:
    print(f"✗ Invalid JSON: {e}")
