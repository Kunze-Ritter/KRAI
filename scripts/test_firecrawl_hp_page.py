"""
Test Firecrawl v1 scrape on real HP product page
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    firecrawl_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004").rstrip("/")
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-local-dev-key-not-required")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # HP homepage (simpler page for testing)
    hp_url = "https://www.hp.com/us-en/home.html"

    payload = {
        "url": hp_url,
        "formats": ["markdown", "html"],
        "onlyMainContent": True,
        "timeout": 180000,  # 3 minutes
        "waitFor": 2000,  # Wait 2s for JS to load
        "blockAds": True,
        "proxy": "basic",
        "parsePDF": True,
    }

    url = f"{firecrawl_url}/v1/scrape"

    print("=" * 80)
    print("🔍 Firecrawl v1 scrape - HP Homepage Test")
    print("=" * 80)
    print(f"Target: {hp_url}")
    print(f"Firecrawl: {url}")
    print()

    timeout_seconds = 240.0

    print(f"⏱️  Starting request (timeout: {timeout_seconds}s)...")
    print()

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)

    print("Status:", response.status_code)
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
            print("Markdown preview (first 800 chars):")
            print("-" * 80)
            print(markdown[:800])
            print("-" * 80)
            print()

            # Check for key HP content
            keywords = ["HP", "LaserJet", "E877", "support", "driver", "manual"]
            found = [kw for kw in keywords if kw.lower() in markdown.lower()]
            print(f"Keywords found: {', '.join(found)}")
        else:
            print("❌ Response success=false")
            print(data)
    else:
        print(f"❌ HTTP {response.status_code}")
        print("Body (first 500 chars):")
        print(response.text[:500])


if __name__ == "__main__":
    main()
