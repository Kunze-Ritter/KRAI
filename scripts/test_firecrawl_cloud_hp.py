"""
Test Firecrawl Cloud API on HP product page

This script tests the official Firecrawl Cloud API (https://api.firecrawl.dev)
instead of the self-hosted instance.

Setup:
1. Add your Firecrawl API key to .env: FIRECRAWL_API_KEY=fc-...
2. Set FIRECRAWL_API_URL=https://api.firecrawl.dev in .env
3. Run: python test_firecrawl_cloud_hp.py
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    # Use Cloud API URL
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

    # HP LaserJet E877 support page
    hp_url = "https://support.hp.com/us-en/product/hp-laserjet-managed-mfp-e877-series/2101946605"

    payload = {
        "url": hp_url,
        "formats": ["markdown", "html"],
        "onlyMainContent": True,
        "timeout": 180000,  # 3 minutes
        "waitFor": 2000,  # Wait 2s for JS to load
    }

    url = f"{firecrawl_url}/v1/scrape"

    print("=" * 80)
    print("🔥 Firecrawl CLOUD API Test - HP Product Page")
    print("=" * 80)
    print(f"Target URL: {hp_url}")
    print(f"Firecrawl API: {url}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "API Key: [hidden]")
    print()

    timeout_seconds = 240.0

    print(f"⏱️  Starting request (timeout: {timeout_seconds}s)...")
    print()

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)

        print(f"Status: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            if data.get("success"):
                doc = data.get("data", {})
                markdown = doc.get("markdown", "")
                html = doc.get("html", "")

                print("✅ SUCCESS!")
                print()
                print(f"Markdown length: {len(markdown)} chars")
                print(f"HTML length: {len(html)} chars")
                print()
                print("Markdown preview (first 1000 chars):")
                print("-" * 80)
                print(markdown[:1000])
                print("-" * 80)
                print()

                # Check for key HP content
                keywords = ["HP", "LaserJet", "E877", "support", "driver", "manual", "printer"]
                found = [kw for kw in keywords if kw.lower() in markdown.lower()]
                missing = [kw for kw in keywords if kw.lower() not in markdown.lower()]

                print(f"✅ Keywords found ({len(found)}/{len(keywords)}): {', '.join(found)}")
                if missing:
                    print(f"⚠️  Keywords missing: {', '.join(missing)}")
                print()

                # Check metadata
                metadata = doc.get("metadata", {})
                if metadata:
                    print("📊 Metadata:")
                    print(f"   Title: {metadata.get('title', 'N/A')}")
                    print(f"   Description: {metadata.get('description', 'N/A')[:100]}...")
                    print(f"   Language: {metadata.get('language', 'N/A')}")
                    print(f"   Status Code: {metadata.get('statusCode', 'N/A')}")
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


if __name__ == "__main__":
    main()
