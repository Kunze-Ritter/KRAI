"""
Test script for KRAI AI Agent
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

from backend.processors.env_loader import load_all_env_files

# Load environment files via centralized loader
project_root = Path(__file__).parent.parent.parent
load_all_env_files(project_root)

BASE_URL = "http://localhost:8000/agent"
SESSION_ID = f"test-{int(time.time())}"


def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 60)
    print("TEST: Health Check")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    print("✅ Health check passed")


def test_chat_error_code():
    """Test error code search"""
    print("\n" + "=" * 60)
    print("TEST: Error Code Search")
    print("=" * 60)

    message = "Konica Minolta C3320i Fehler C9402"
    print(f"Message: {message}")
    print(f"Session: {SESSION_ID}")

    response = requests.post(f"{BASE_URL}/chat", json={"message": message, "session_id": SESSION_ID})

    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        print("-" * 60)
        print(data["response"])
        print("-" * 60)
        print(f"\nTimestamp: {data['timestamp']}")
        print("✅ Error code search passed")
    else:
        print(f"❌ Error: {response.text}")

    # Test 2: Error code search with multi-source request
    print("\n" + "=" * 60)
    print("TEST: Error Code Search (Multi-Source)")
    print("=" * 60)

    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "HP Fehler 10.00.33 - Gib mir die komplette Lösung mit allen Schritten. Suche auch nach Service Bulletins und Videos.",
            "session_id": SESSION_ID,
        },
    )

    print("Message: HP Fehler 10.00.33 - Komplette Lösung mit Bulletins und Videos")
    print(f"Session: {SESSION_ID}\n")
    print(f"Status: {response.status_code}\n")

    if response.status_code == 200:
        result = response.json()
        print("Response:")
        print("-" * 60)
        print(result.get("response", "No response"))
        print("-" * 60)
        print(f"\nTimestamp: {result.get('timestamp')}")
        print("✅ Error code search passed")
    else:
        print(f"❌ Error code search failed: {response.text}")
        print("⚠️ Continuing with other tests...")

    time.sleep(2)


def test_chat_parts():
    """Test parts search"""
    print("\n" + "=" * 60)
    print("TEST: Parts Search")
    print("=" * 60)

    message = "Fuser Unit für HP E877"
    print(f"Message: {message}")
    print(f"Session: {SESSION_ID}")

    response = requests.post(f"{BASE_URL}/chat", json={"message": message, "session_id": SESSION_ID})

    print(f"\nStatus: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        print("-" * 60)
        print(data["response"])
        print("-" * 60)
        print(f"\nTimestamp: {data['timestamp']}")
        print("✅ Parts search passed")
    else:
        print(f"❌ Error: {response.text}")


def test_chat_streaming():
    """Test streaming chat"""
    print("\n" + "=" * 60)
    print("TEST: Streaming Chat")
    print("=" * 60)

    message = "HP Fehler 10.00.33"
    print(f"Message: {message}")
    print(f"Session: {SESSION_ID}")

    response = requests.post(
        f"{BASE_URL}/chat/stream", json={"message": message, "session_id": SESSION_ID}, stream=True
    )

    print(f"\nStatus: {response.status_code}")
    print("\nStreaming response:")
    print("-" * 60)

    for line in response.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    print(chunk["chunk"], end="", flush=True)
                except json.JSONDecodeError:
                    pass

    print("\n" + "-" * 60)
    print("✅ Streaming chat passed")


def test_conversation_memory():
    """Test conversation memory"""
    print("\n" + "=" * 60)
    print("TEST: Conversation Memory")
    print("=" * 60)

    # First message
    message1 = "Was ist Fehler C9402?"
    print(f"\n1. Message: {message1}")

    response1 = requests.post(f"{BASE_URL}/chat", json={"message": message1, "session_id": SESSION_ID})

    if response1.status_code == 200:
        print("✅ First message sent")

    time.sleep(1)

    # Follow-up message (should remember context)
    message2 = "Wie kann ich das beheben?"
    print(f"\n2. Message: {message2}")

    response2 = requests.post(f"{BASE_URL}/chat", json={"message": message2, "session_id": SESSION_ID})

    print(f"\nStatus: {response2.status_code}")

    if response2.status_code == 200:
        data = response2.json()
        print("\nResponse:")
        print("-" * 60)
        print(data["response"])
        print("-" * 60)
        print("✅ Conversation memory passed")
    else:
        print(f"❌ Error: {response2.text}")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("KRAI AI AGENT TEST SUITE")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Base URL: {BASE_URL}")
    print(f"Session ID: {SESSION_ID}")

    try:
        test_health()
        test_chat_error_code()
        test_chat_parts()
        test_chat_streaming()
        test_conversation_memory()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    run_all_tests()
