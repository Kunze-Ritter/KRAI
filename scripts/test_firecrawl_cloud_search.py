"""
Test Firecrawl Cloud API /v1/search endpoint

The search endpoint allows you to search the web and get clean, structured data
from the search results.

Firecrawl Search API Docs: https://docs.firecrawl.dev/features/search
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")
    api_key = os.getenv("FIRECRAWL_API_KEY", "")

    if not api_key or api_key == "fc-local-dev-key-not-required":
        print("❌ ERROR: No valid Firecrawl API key found!")
        print("Please set FIRECRAWL_API_KEY in .env file")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Search query for HP LaserJet E877
    search_query = "HP LaserJet Managed MFP E877 specifications manual"

    payload = {
        "query": search_query,
        "limit": 5,  # Number of results to return
        "lang": "en",
        "country": "us",
        "scrapeOptions": {
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
        },
    }

    url = f"{firecrawl_url}/v1/search"

    print("=" * 80)
    print("🔍 Firecrawl CLOUD API - Search Test")
    print("=" * 80)
    print(f"Search Query: {search_query}")
    print(f"Firecrawl API: {url}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "API Key: [hidden]")
    print()

    timeout_seconds = 120.0

    print(f"⏱️  Starting search (timeout: {timeout_seconds}s)...")
    print()

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)

        print(f"Status: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            if data.get("success"):
                results = data.get("data", [])

                print(f"✅ SUCCESS! Found {len(results)} results")
                print()

                for i, result in enumerate(results, 1):
                    print(f"{'=' * 80}")
                    print(f"Result #{i}")
                    print(f"{'=' * 80}")
                    print(f"URL: {result.get('url', 'N/A')}")
                    print(f"Title: {result.get('title', 'N/A')}")
                    print()

                    markdown = result.get("markdown", "")
                    if markdown:
                        print(f"Markdown length: {len(markdown)} chars")
                        print("Preview (first 500 chars):")
                        print("-" * 80)
                        print(markdown[:500])
                        print("-" * 80)
                    else:
                        print("⚠️  No markdown content")

                    # Check for keywords
                    keywords = ["HP", "LaserJet", "E877", "specifications", "manual"]
                    found = [kw for kw in keywords if kw.lower() in markdown.lower()]
                    if found:
                        print(f"✅ Keywords found: {', '.join(found)}")

                    print()

                # Summary
                print("=" * 80)
                print("📊 SUMMARY")
                print("=" * 80)
                print(f"Total results: {len(results)}")

                # Find best result (most keywords)
                best_result = None
                best_score = 0
                keywords = ["HP", "LaserJet", "E877", "specifications", "manual", "support"]

                for result in results:
                    markdown = result.get("markdown", "").lower()
                    score = sum(1 for kw in keywords if kw.lower() in markdown)
                    if score > best_score:
                        best_score = score
                        best_result = result

                if best_result:
                    print(f"\n🏆 Best result (score: {best_score}/{len(keywords)}):")
                    print(f"   URL: {best_result.get('url', 'N/A')}")
                    print(f"   Title: {best_result.get('title', 'N/A')}")

            else:
                print("❌ Response success=false")
                print(data)
        else:
            print(f"❌ HTTP {response.status_code}")
            print("Response body:")
            print(response.text[:1000])

    except httpx.TimeoutException:
        print("❌ Request timed out!")
        print(f"The request exceeded {timeout_seconds}s")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
