"""Test API direkt"""

import requests

print("Testing KRAI API...")

# Test 1: Health check
try:
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"✅ Health: {response.status_code}")
except Exception as e:
    print(f"❌ Health check failed: {e}")

# Test 2: Models endpoint
try:
    response = requests.get("http://localhost:8000/v1/models", timeout=5)
    print(f"✅ Models: {response.status_code}")
    if response.status_code == 200:
        print(f"   Models: {response.json()}")
except Exception as e:
    print(f"❌ Models failed: {e}")

# Test 3: Chat completion
try:
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={"model": "krai-assistant", "messages": [{"role": "user", "content": "Test"}], "stream": False},
        timeout=30,
    )
    print(f"✅ Chat: {response.status_code}")
    if response.status_code != 200:
        print(f"   Error: {response.text[:500]}")
except Exception as e:
    print(f"❌ Chat failed: {e}")
