"""
Debug Firecrawl configuration and timeout settings
"""

import asyncio
import os

from dotenv import load_dotenv

from backend.services.web_scraping_service import create_web_scraping_service

load_dotenv()


async def debug_firecrawl():
    """Debug Firecrawl configuration"""

    print("=" * 80)
    print("🔍 Firecrawl Configuration Debug")
    print("=" * 80)
    print()

    # Check environment variables
    print("📋 Environment Variables:")
    print(f"   FIRECRAWL_API_URL: {os.getenv('FIRECRAWL_API_URL')}")
    print(f"   FIRECRAWL_SCRAPE_TIMEOUT: {os.getenv('FIRECRAWL_SCRAPE_TIMEOUT')}")
    print(f"   FIRECRAWL_CRAWL_TIMEOUT: {os.getenv('FIRECRAWL_CRAWL_TIMEOUT')}")
    print(f"   FIRECRAWL_RETRIES: {os.getenv('FIRECRAWL_RETRIES')}")
    print()

    # Create service and inspect backend
    print("🔧 Creating web scraping service...")
    service = create_web_scraping_service(backend="firecrawl")

    # Access the primary backend
    backend = service._primary_backend

    print()
    print("📊 FirecrawlBackend Configuration:")
    print(f"   API URL: {backend.api_url}")
    print(f"   Timeout: {backend.timeout}s")
    print(f"   Crawl Timeout: {backend.crawl_timeout}s")
    print(f"   Retries: {backend.retries}")
    print(f"   Block Media: {backend.block_media}")
    print()

    # Test with a simple URL
    test_url = "https://example.com"
    print(f"🧪 Testing with simple URL: {test_url}")
    print()

    try:
        result = await service.scrape_url(test_url)

        if result and result.get("success"):
            print("✅ Scraping successful!")
            print(f"   Backend: {result.get('backend')}")
            print(f"   Content length: {len(result.get('content', ''))} characters")
        else:
            print("❌ Scraping failed!")
            print(f"   Backend: {result.get('backend')}")
            print(f"   Error: {result.get('error')}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

    print()
    print("=" * 80)
    print("✅ Debug Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_firecrawl())
