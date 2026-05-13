"""Test Agent Search Endpoints"""

import requests

API_URL = "http://localhost:8000"

print("=" * 80)
print("🤖 KRAI AGENT - SEARCH TESTS")
print("=" * 80)

# Test 1: Error Code Search
print("\n📝 Test 1: Fehlercode-Suche")
print("-" * 80)

test_cases = ["C9402", "Konica Minolta C3320i Fehler C9402", "HP Fehler 10.00.33", "Papierstau beheben"]

for query in test_cases:
    print(f"\n🔍 Query: '{query}'")

    try:
        response = requests.get(f"{API_URL}/search/error-codes", params={"q": query, "limit": 3}, timeout=30)

        if response.status_code == 200:
            results = response.json()
            print(f"   ✅ {len(results)} Ergebnisse")

            if results:
                top = results[0]
                print(f"   📌 Top: {top.get('error_code', 'N/A')} - {top.get('description', 'N/A')[:60]}...")
                print(f"   📊 Confidence: {top.get('confidence', 0):.2f}")
                print(f"   🏭 Hersteller: {top.get('manufacturer', 'N/A')}")
            else:
                print("   ⚠️  Keine Ergebnisse")
        else:
            print(f"   ❌ Error {response.status_code}")
            print(f"   {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

# Test 2: Semantic Search
print("\n" + "=" * 80)
print("📝 Test 2: Semantic Search (Vector)")
print("-" * 80)

semantic_queries = ["Wie behebe ich einen Papierstau?", "Druckkopf reinigen", "Toner wechseln Anleitung"]

for query in semantic_queries:
    print(f"\n🔍 Query: '{query}'")

    try:
        response = requests.post(f"{API_URL}/search/vector", params={"query": query, "limit": 3}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print(f"   ✅ {len(results)} Ergebnisse")

            if results:
                top = results[0]
                # match_chunks returns: id, content, metadata, similarity
                text_preview = top.get("content", "N/A")[:80].replace("\n", " ")
                print(f"   📌 Top: {text_preview}...")
                print(f"   📊 Similarity: {top.get('similarity', 0):.3f}")
                metadata = top.get("metadata", {})
                print(f"   📄 Seite: {metadata.get('page_start', 'N/A')}")
            else:
                print("   ⚠️  Keine Ergebnisse")
        else:
            print(f"   ❌ Error {response.status_code}")
            print(f"   {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

print("\n" + "=" * 80)
print("✅ Tests abgeschlossen!")
print("=" * 80)
