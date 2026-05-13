"""
Simple test: Extract model from filename and run product discovery
"""

import asyncio
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from backend.services.database_service import DatabaseService
from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


def extract_model_from_filename(filename):
    """Extract model number from filename"""
    patterns = [
        r"[A-Z]{1,3}[-_]?[0-9]{3,5}[A-Z]*",  # E877, M454dn, HL-L8360CDW
        r"[A-Z]{2,4}[-_][A-Z]?[0-9]{3,5}[A-Z]*",  # HP-E877z, HL-L8360
        r"(?:Color\s+)?LaserJet\s+(?:Managed\s+)?(?:MFP\s+)?([A-Z]?[0-9]{3,5}[A-Z]*)",  # LaserJet E877z
    ]

    for pattern in patterns:
        matches = re.findall(pattern, filename, re.IGNORECASE)
        if matches:
            model = matches[0] if isinstance(matches[0], str) else matches[0][0]
            model = model.strip().replace("_", "-")
            return model

    return None


async def test_discovery():
    """Test product discovery with extracted model"""
    print("=" * 80)
    print("🧪 Simple Product Discovery Test")
    print("=" * 80)
    print()

    # Test file
    test_file = "HP_E877_CPMD.pdf"
    manufacturer = "HP Inc."

    # Extract model
    model = extract_model_from_filename(test_file)

    print(f"📄 Filename: {test_file}")
    print(f"🏭 Manufacturer: {manufacturer}")
    print(f"📦 Extracted Model: {model}")
    print()

    if not model:
        print("❌ No model extracted from filename")
        return

    # Initialize services
    print("🔧 Initializing services...")

    db_service = DatabaseService()
    await db_service.connect()

    web_scraping_service = create_web_scraping_service()
    verification_service = ManufacturerVerificationService(
        database_service=db_service, web_scraping_service=web_scraping_service
    )

    print("✅ Services initialized")
    print()

    # Run product discovery
    print("=" * 80)
    print(f"🔍 Discovering Product: {manufacturer} {model}")
    print("=" * 80)
    print()

    try:
        result = await verification_service.discover_product_page(
            manufacturer=manufacturer,
            model_number=model,
            save_to_db=True,  # Enable DB saving to test persistence
        )

        print()
        print("=" * 80)
        print("📊 Discovery Result")
        print("=" * 80)
        print()

        if result and result.get("url"):
            print("✅ Product page found!")
            print()
            print(f"   URL: {result['url']}")
            print(f"   Source: {result.get('source', 'unknown')}")
            print(f"   Confidence: {result.get('confidence', 0)}")
            print(f"   Score: {result.get('score', 0)}")

            if result.get("product_id"):
                print(f"   DB Product ID: {result['product_id']}")

            if result.get("alternatives"):
                print()
                print(f"   Alternative URLs ({len(result['alternatives'])}):")
                for i, alt in enumerate(result["alternatives"][:3], 1):
                    print(f"      {i}. {alt['url']} (score: {alt['score']})")

            print()

            # Check database
            print("=" * 80)
            print("💾 Checking Database")
            print("=" * 80)
            print()

            query = """
                SELECT p.id, p.model_number, m.name as manufacturer_name
                FROM krai_core.products p
                JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
                WHERE m.name ILIKE %s AND p.model_number ILIKE %s
                ORDER BY p.created_at DESC
                LIMIT 1
            """

            products = await db_service.fetch_all(query, (f"%{manufacturer}%", f"%{model}%"))

            if products:
                print("✅ Product found in database:")
                print(f"   ID: {products[0]['id']}")
                print(f"   Manufacturer: {products[0]['manufacturer_name']}")
                print(f"   Model: {products[0]['model_number']}")
            else:
                print("⚠️  Product not found in database (might be schema mismatch)")

        else:
            print("❌ No product page found")
            if result:
                print(f"   Result: {result}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await db_service.disconnect()
        print()
        print("=" * 80)
        print("✅ Test Complete")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_discovery())
