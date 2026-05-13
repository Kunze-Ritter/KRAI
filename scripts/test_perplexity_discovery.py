"""
Test Perplexity AI Product Page Discovery

Tests the Perplexity AI integration for finding product pages
"""

import asyncio
import os

from dotenv import load_dotenv

from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service

# Load environment variables from .env file
load_dotenv()


async def test_perplexity_discovery():
    print("=" * 60)
    print("Testing Perplexity AI Product Page Discovery")
    print("=" * 60)

    # Check if API key is set
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("\n⚠️  PERPLEXITY_API_KEY not set!")
        print("Please set it in your .env file to test Perplexity AI")
        print("Get your API key from: https://www.perplexity.ai/settings/api")
        return

    print(f"\n✅ Perplexity API Key found: {api_key[:10]}...")

    # Initialize services
    web_service = create_web_scraping_service()
    verification_service = ManufacturerVerificationService(web_scraping_service=web_service)

    # Test cases
    test_cases = [
        ("HP Inc.", "M454dn"),
        ("Canon", "imageRUNNER ADVANCE C5535i"),
        ("Brother", "HL-L2350DW"),
    ]

    for manufacturer, model in test_cases:
        print(f"\n{'=' * 60}")
        print(f"🔍 Testing: {manufacturer} {model}")
        print(f"{'=' * 60}")

        # Test Perplexity search directly
        result = await verification_service._perplexity_search(manufacturer=manufacturer, model_number=model)

        if result:
            print("\n📊 Perplexity Results:")
            print(f"  URL: {result.get('url')}")
            print(f"  Source: {result.get('source')}")
            print(f"  Confidence: {result.get('confidence'):.2f}")
            print(f"  Verified: {result.get('verified')}")

            if result.get("answer"):
                print("\n💬 AI Answer:")
                answer = result.get("answer", "")
                # Show first 300 characters
                print(f"  {answer[:300]}...")

            if result.get("citations"):
                print("\n📚 Citations:")
                for i, citation in enumerate(result.get("citations", [])[:3], 1):
                    print(f"  {i}. {citation}")

            # Test URL accessibility
            if result.get("url"):
                print("\n🌐 Testing URL accessibility...")
                try:
                    scrape_result = await web_service.scrape_url(result["url"])
                    if scrape_result and scrape_result.get("success"):
                        content = scrape_result.get("content", "")
                        print("  ✅ URL accessible")
                        print(f"  📄 Content length: {len(content)} characters")

                        # Check if model is mentioned
                        if model.lower() in content.lower():
                            print(f"  ✅ Model '{model}' found in content")
                        else:
                            print(f"  ⚠️  Model '{model}' NOT found in content")
                    else:
                        print("  ❌ URL not accessible")
                except Exception as e:
                    print(f"  ❌ Error accessing URL: {e}")
        else:
            print("\n❌ No result from Perplexity AI")

    print(f"\n{'=' * 60}")
    print("✅ Perplexity AI Test Complete")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(test_perplexity_discovery())
