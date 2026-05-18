"""
Test different Firecrawl API versions to find the correct endpoint
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_api_versions():
    """Test different API endpoint versions"""

    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    print("=" * 80)
    print("🔍 Testing Firecrawl API Versions")
    print("=" * 80)
    print()

    # Test different API versions and endpoints
    test_configs = [
        {"version": "v0", "endpoint": "/v0/scrape", "method": "POST"},
        {"version": "v1", "endpoint": "/v1/scrape", "method": "POST"},
        {"version": "legacy", "endpoint": "/scrape", "method": "POST"},
        {"version": "v0-async", "endpoint": "/v0/scrape-async", "method": "POST"},
        {"version": "v1-async", "endpoint": "/v1/scrape-async", "method": "POST"},
    ]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {"url": "https://example.com", "formats": ["markdown"]}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for config in test_configs:
            url = f"{firecrawl_url}{config['endpoint']}"
            print(f"Testing {config['version']:15} -> {config['endpoint']}")

            try:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    print(f"  ✅ SUCCESS! Status: {response.status_code}")
                    data = response.json()
                    print(f"  📊 Response keys: {list(data.keys())}")
                    if "success" in data:
                        print(f"  ✨ Success: {data['success']}")
                    print()
                    return config  # Found working endpoint!
                if response.status_code == 404:
                    print("  ❌ Not Found (404)")
                elif response.status_code == 500:
                    print("  ⚠️  Server Error (500)")
                else:
                    print(f"  ⚠️  Status: {response.status_code}")
                    print(f"  Response: {response.text[:200]}")

            except httpx.TimeoutException:
                print("  ⏱️  Timeout (15s)")
            except Exception as e:
                print(f"  ❌ Error: {type(e).__name__}: {e}")

            print()

    print("=" * 80)
    print("❌ No working API endpoint found")
    print("=" * 80)
    return None


if __name__ == "__main__":
    result = asyncio.run(test_api_versions())
    if result:
        print()
        print("✅ Working Configuration:")
        print(f"   Version: {result['version']}")
        print(f"   Endpoint: {result['endpoint']}")
        print(f"   Method: {result['method']}")
