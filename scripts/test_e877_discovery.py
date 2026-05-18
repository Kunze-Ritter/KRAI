"""
Quick test for E877z product page discovery
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


async def test_e877_discovery():
    print("=" * 80)
    print("Testing E877z Product Page Discovery")
    print("=" * 80)

    # Initialize services
    web_service = create_web_scraping_service()
    verification_service = ManufacturerVerificationService(web_scraping_service=web_service)

    # Test with different model variations
    test_cases = [
        ("HP Inc.", "E877"),
        ("HP Inc.", "E877z"),
        ("HP Inc.", "Color LaserJet Managed MFP E877z"),
        ("HP Inc.", "HP Color LaserJet Managed MFP E877z"),
        ("HP Inc.", "LaserJet Managed E877z"),
    ]

    for manufacturer, model in test_cases:
        print(f"\n{'=' * 80}")
        print(f"🔍 Testing: {manufacturer} {model}")
        print(f"{'=' * 80}")

        result = await verification_service._perplexity_search(manufacturer=manufacturer, model_number=model)

        if result:
            print("\n✅ Found URL:")
            print(f"   URL: {result['url']}")
            print(f"   Source: {result['source']}")
            print(f"   Confidence: {result['confidence']:.2f}")
            print(f"   Score: {result.get('score', 0)}")

            if result.get("answer"):
                print("\n💬 AI Answer:")
                print(f"   {result['answer'][:300]}...")

            # Check if it's the correct URL
            correct_url = (
                "https://support.hp.com/us-en/drivers/hp-color-laserjet-managed-mfp-e877z-printer-series/2101127729"
            )
            if result["url"] == correct_url:
                print("\n   ✅ CORRECT URL FOUND!")
            elif correct_url in str(result.get("citations", [])):
                print("\n   ⚠️  Correct URL in citations but not selected")
            else:
                print("\n   ❌ Different URL than expected")
                print(f"   Expected: {correct_url}")
        else:
            print("\n❌ No result found")

    print(f"\n{'=' * 80}")
    print("Test Complete")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(test_e877_discovery())
