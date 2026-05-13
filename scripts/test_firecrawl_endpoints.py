"""
Discover available Firecrawl API endpoints
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def discover_endpoints():
    """Try to discover available Firecrawl endpoints"""

    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    print("=" * 80)
    print("🔍 Firecrawl Endpoint Discovery")
    print("=" * 80)
    print()
    print(f"🔗 Base URL: {firecrawl_url}")
    print()

    # Common Firecrawl endpoints to test
    endpoints = [
        "/",
        "/v0/scrape",
        "/v1/scrape",
        "/api/scrape",
        "/scrape",
        "/v0/crawl",
        "/v1/crawl",
        "/health",
        "/status",
    ]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print("Testing endpoints:")
    print("-" * 80)

    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in endpoints:
            url = f"{firecrawl_url}{endpoint}"

            # Try GET
            try:
                response = await client.get(url, headers=headers)
                print(f"✅ GET  {endpoint:20} -> {response.status_code} {response.reason_phrase}")
            except Exception as e:
                print(f"❌ GET  {endpoint:20} -> Error: {type(e).__name__}")

            # Try POST with minimal payload
            try:
                payload = {"url": "https://example.com"}
                response = await client.post(url, json=payload, headers=headers)
                print(f"✅ POST {endpoint:20} -> {response.status_code} {response.reason_phrase}")
                if response.status_code == 200:
                    print(f"   ⭐ WORKING ENDPOINT: {endpoint}")
            except Exception as e:
                print(f"❌ POST {endpoint:20} -> Error: {type(e).__name__}")

    print()
    print("=" * 80)
    print("✅ Discovery Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(discover_endpoints())
