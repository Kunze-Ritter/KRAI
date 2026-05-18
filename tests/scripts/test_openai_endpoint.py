"""Test OpenAI-compatible endpoint"""

import json

import requests

API_URL = "http://localhost:8000"

print("=" * 80)
print("🤖 OPENAI-COMPATIBLE API TEST")
print("=" * 80)

# Test 1: List Models
print("\n📝 Test 1: List Models")
print("-" * 80)

try:
    response = requests.get(f"{API_URL}/v1/models")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Models available: {len(data.get('data', []))}")
        for model in data.get("data", []):
            print(f"   - {model['id']}")
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 2: Chat Completion (non-streaming)
print("\n📝 Test 2: Chat Completion (Non-Streaming)")
print("-" * 80)

test_messages = [{"role": "user", "content": "Konica Minolta C3320i Fehler C9402"}]

try:
    response = requests.post(
        f"{API_URL}/v1/chat/completions",
        json={"model": "krai-assistant", "messages": test_messages, "stream": False},
        timeout=30,
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Response ID: {data.get('id')}")
        print(f"✅ Model: {data.get('model')}")

        if data.get("choices"):
            message = data["choices"][0]["message"]
            print("\n📌 Assistant Response:")
            print("-" * 40)
            print(message["content"])
            print("-" * 40)

        usage = data.get("usage", {})
        print(f"\n📊 Tokens: {usage.get('total_tokens', 0)}")
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Exception: {e}")

# Test 3: Chat Completion (streaming)
print("\n📝 Test 3: Chat Completion (Streaming)")
print("-" * 80)

try:
    response = requests.post(
        f"{API_URL}/v1/chat/completions",
        json={
            "model": "krai-assistant",
            "messages": [{"role": "user", "content": "HP Fehler 10.00.33"}],
            "stream": True,
        },
        stream=True,
        timeout=30,
    )

    if response.status_code == 200:
        print("✅ Streaming response:")
        print("-" * 40)

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("choices"):
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        pass

        print("\n" + "-" * 40)
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n" + "=" * 80)
print("✅ Tests abgeschlossen!")
print("=" * 80)
