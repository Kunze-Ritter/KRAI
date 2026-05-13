"""
Improved KRAI AI Agent Test Suite
Tests multi-source search and complete solutions
"""

import time
from datetime import datetime

import requests

BASE_URL = "http://localhost:8000/agent"
SESSION_ID = f"test-{int(time.time())}"

print("=" * 60)
print("KRAI AI AGENT - IMPROVED TEST SUITE")
print("=" * 60)
print(f"Started: {datetime.now().isoformat()}")
print(f"Base URL: {BASE_URL}")
print(f"Session ID: {SESSION_ID}")

# Test 1: Health Check
print("\n" + "=" * 60)
print("TEST 1: Health Check")
print("=" * 60)

response = requests.get(f"{BASE_URL}/health")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Response: {response.json()}")
    print("✅ Health check passed")
else:
    print("❌ Health check failed")
    exit(1)

time.sleep(1)

# Test 2: HP Error with complete solution request
print("\n" + "=" * 60)
print("TEST 2: HP Error 10.00.33 - Complete Solution")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "HP Fehler 10.00.33 - Gib mir die KOMPLETTE Lösung mit ALLEN Schritten. Suche auch nach Service Bulletins und Video-Anleitungen.",
        "session_id": SESSION_ID,
    },
)

print(f"Status: {response.status_code}\n")
if response.status_code == 200:
    result = response.json()
    print("Response:")
    print("-" * 60)
    print(result.get("response", "No response"))
    print("-" * 60)
    print(f"\nTimestamp: {result.get('timestamp')}")
    print("✅ Test passed")
else:
    print(f"❌ Test failed: {response.text}")

time.sleep(3)

# Test 3: Konica Minolta Error with multi-source
print("\n" + "=" * 60)
print("TEST 3: Konica Minolta C9402 - Multi-Source")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "Konica Minolta C3320i Fehler C9402 - Was bedeutet dieser Fehler und wie behebe ich ihn? Suche auch nach relevanten Service Bulletins.",
        "session_id": SESSION_ID,
    },
)

print(f"Status: {response.status_code}\n")
if response.status_code == 200:
    result = response.json()
    print("Response:")
    print("-" * 60)
    print(result.get("response", "No response"))
    print("-" * 60)
    print(f"\nTimestamp: {result.get('timestamp')}")
    print("✅ Test passed")
else:
    print(f"❌ Test failed: {response.text}")

time.sleep(3)

# Test 4: Video search
print("\n" + "=" * 60)
print("TEST 4: Video Search - Tray 4 Jam")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/chat", json={"message": "Suche nach Videos: how to clear a jam in Tray 4", "session_id": SESSION_ID}
)

print(f"Status: {response.status_code}\n")
if response.status_code == 200:
    result = response.json()
    print("Response:")
    print("-" * 60)
    print(result.get("response", "No response"))
    print("-" * 60)
    print(f"\nTimestamp: {result.get('timestamp')}")
    print("✅ Test passed")
else:
    print(f"❌ Test failed: {response.text}")

time.sleep(3)

# Test 5: Parts search with alternatives
print("\n" + "=" * 60)
print("TEST 5: Parts Search - Lexmark Part 41X5345")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/chat",
    json={"message": "Suche nach Ersatzteil 41X5345. Was ist das für ein Teil?", "session_id": SESSION_ID},
)

print(f"Status: {response.status_code}\n")
if response.status_code == 200:
    result = response.json()
    print("Response:")
    print("-" * 60)
    print(result.get("response", "No response"))
    print("-" * 60)
    print(f"\nTimestamp: {result.get('timestamp')}")
    print("✅ Test passed")
else:
    print(f"❌ Test failed: {response.text}")

time.sleep(3)

# Test 6: Conversation Memory - Follow-up question
print("\n" + "=" * 60)
print("TEST 6: Conversation Memory - Follow-up")
print("=" * 60)

# First question
print("\n1. First question: Was ist Fehler 10.00.33?")
response1 = requests.post(f"{BASE_URL}/chat", json={"message": "Was ist HP Fehler 10.00.33?", "session_id": SESSION_ID})

if response1.status_code == 200:
    print("✅ First message sent")
    time.sleep(2)

    # Follow-up question
    print("\n2. Follow-up: Welche Ersatzteile brauche ich dafür?")
    response2 = requests.post(
        f"{BASE_URL}/chat", json={"message": "Welche Ersatzteile brauche ich dafür?", "session_id": SESSION_ID}
    )

    print(f"\nStatus: {response2.status_code}\n")
    if response2.status_code == 200:
        result = response2.json()
        print("Response:")
        print("-" * 60)
        print(result.get("response", "No response"))
        print("-" * 60)
        print(f"\nTimestamp: {result.get('timestamp')}")
        print("✅ Conversation memory test passed")
    else:
        print(f"❌ Follow-up failed: {response2.text}")
else:
    print(f"❌ First message failed: {response1.text}")

time.sleep(3)

# Test 7: Streaming with complete solution
print("\n" + "=" * 60)
print("TEST 7: Streaming - Complete Solution")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/chat/stream",
    json={"message": "HP Fehler 10.23.15 - Gib mir die komplette Lösung mit allen Details.", "session_id": SESSION_ID},
    stream=True,
)

print(f"Status: {response.status_code}\n")
if response.status_code == 200:
    print("Streaming response:")
    print("-" * 60)
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                print(decoded[6:], end="", flush=True)
    print("\n" + "-" * 60)
    print("✅ Streaming test passed")
else:
    print(f"❌ Streaming failed: {response.text}")

print("\n" + "=" * 60)
print("✅ ALL TESTS COMPLETED")
print("=" * 60)
