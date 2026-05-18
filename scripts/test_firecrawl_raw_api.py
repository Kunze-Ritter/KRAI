"""
Test Firecrawl API directly with raw HTTP requests
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_firecrawl_raw():
    """Test Firecrawl API directly"""

    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    print("=" * 80)
    print("🔍 Firecrawl Raw API Test")
    print("=" * 80)
    print()
    print(f"🔗 API URL: {firecrawl_url}")
    print(f"🔑 API Key: {api_key}")
    print()

    # Test 1: Check if API is reachable
    print("Test 1: API Reachability")
    print("-" * 80)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(firecrawl_url)
            print("✅ API is reachable!")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()

    # Test 2: Try scrape endpoint
    print("Test 2: Scrape Endpoint (POST /scrape)")
    print("-" * 80)

    scrape_url = f"{firecrawl_url}/scrape"
    test_target = "https://example.com"

    payload = {"url": test_target, "formats": ["markdown", "html"], "onlyMainContent": True}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print(f"📤 Sending POST to: {scrape_url}")
    print(f"📄 Target URL: {test_target}")
    print()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print("⏳ Waiting for response (60s timeout)...")
            response = await client.post(scrape_url, json=payload, headers=headers)

            print("✅ Response received!")
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            print()

            if response.status_code == 200:
                data = response.json()
                print("📊 Response Data:")
                print(f"   Success: {data.get('success')}")
                if "data" in data:
                    print(f"   Data keys: {list(data['data'].keys())}")
                    if "markdown" in data["data"]:
                        print(f"   Markdown length: {len(data['data']['markdown'])} chars")
                    if "html" in data["data"]:
                        print(f"   HTML length: {len(data['data']['html'])} chars")
                print()
                print("📝 Full Response:")
                print(response.text[:1000])
            else:
                print("❌ Error Response:")
                print(response.text[:500])

    except httpx.TimeoutException as e:
        print(f"❌ Timeout Error: {e}")
        print("   Firecrawl is not responding within 60 seconds")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

    print()
    print("=" * 80)
    print("✅ Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_firecrawl_raw())
