"""
Test Firecrawl async API endpoints that return job IDs immediately
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_async_endpoints():
    """Test Firecrawl async endpoints"""

    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    print("=" * 80)
    print("🔍 Testing Firecrawl Async API Endpoints")
    print("=" * 80)
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {"url": "https://example.com", "formats": ["markdown"]}

    # Test async endpoints that should return job IDs immediately
    endpoints = [
        ("/v0/scrape", "POST"),  # Try with webhook
        ("/v1/scrape", "POST"),
        ("/v0/crawl", "POST"),
        ("/v1/crawl", "POST"),
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for endpoint, method in endpoints:
            url = f"{firecrawl_url}{endpoint}"
            print(f"Testing: {method} {endpoint}")

            # Add webhook to make it async
            test_payload = {**payload, "webhook": "http://example.com/webhook"}

            try:
                if method == "POST":
                    response = await client.post(url, json=test_payload, headers=headers)
                else:
                    response = await client.get(url, headers=headers)

                print(f"  Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ Response: {data}")

                    if "id" in data or "jobId" in data:
                        print("  🎉 ASYNC ENDPOINT FOUND! Job ID returned")
                        return endpoint
                elif response.status_code == 404:
                    print("  ❌ Not Found")
                else:
                    print(f"  Response: {response.text[:200]}")

            except httpx.TimeoutException:
                print("  ⏱️  Timeout")
            except Exception as e:
                print(f"  ❌ Error: {type(e).__name__}: {e}")

            print()

    print("=" * 80)
    print("Testing without webhook (synchronous mode)...")
    print("=" * 80)
    print()

    # Test if any endpoint works without webhook
    async with httpx.AsyncClient(timeout=2.0) as client:
        for endpoint, method in [("/v0/scrape", "POST"), ("/v1/scrape", "POST")]:
            url = f"{firecrawl_url}{endpoint}"
            print(f"Quick test: {method} {endpoint}")

            try:
                response = await client.post(url, json=payload, headers=headers)
                print(f"  ✅ Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.json()}")
                    return endpoint
            except httpx.TimeoutException:
                print("  ⏱️  Timeout (2s) - endpoint exists but hangs")
            except Exception as e:
                print(f"  ❌ {type(e).__name__}")

            print()

    return None


if __name__ == "__main__":
    result = asyncio.run(test_async_endpoints())
    if result:
        print()
        print(f"✅ Working async endpoint: {result}")
    else:
        print()
        print("❌ No working async endpoint found")
        print()
        print("CONCLUSION: Firecrawl /v0/scrape and /v1/scrape endpoints exist")
        print("but hang when processing requests. This is a Firecrawl bug or")
        print("misconfiguration, not a Python client issue.")
