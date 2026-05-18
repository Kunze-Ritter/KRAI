import asyncio

from backend.services.web_scraping_service import create_web_scraping_service


async def test_hp_url():
    print("Testing Firecrawl with HP URL...")
    service = create_web_scraping_service()

    # Test with example.com first to verify Firecrawl works
    test_url = "https://example.com"
    print(f"Testing basic connectivity with: {test_url}")

    test_result = await service.scrape_url(test_url)
    print(f"✅ Basic test success: {test_result.get('success', False)}")
    print(f"📄 Content length: {len(test_result.get('content', ''))}")

    # Now test with HP URL
    url = "https://www.hp.com/us-en/home.html"
    print(f"\nTesting HP homepage: {url}")

    result = await service.scrape_url(url)

    print(f"\n✅ Success: {result.get('success', False)}")
    content = result.get("content", "")
    print(f"📄 Content length: {len(content) if content else 0} characters")
    print(f"🔧 Backend used: {result.get('metadata', {}).get('backend_used', 'unknown')}")

    if content:
        # Show first 500 characters
        print("\n📝 Content preview (first 500 chars):")
        print(content[:500])
        print("...")

        # Check for printer-related keywords
        printer_count = content.lower().count("printer")
        laserjet_count = content.lower().count("laserjet")
        print(f"\n🔍 Found 'printer' {printer_count} times")
        print(f"🔍 Found 'laserjet' {laserjet_count} times")
    else:
        print("\n⚠️ No content returned")

    if result.get("error"):
        print(f"\n❌ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_hp_url())
