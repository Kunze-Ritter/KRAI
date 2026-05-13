"""
Test Classification with Product Discovery (Classification stage only)
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment
load_dotenv()

from backend.processors.classification_processor import ClassificationProcessor
from backend.services.ai_service import AIService
from backend.services.database_service import DatabaseService
from backend.services.features_service import FeaturesService
from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


class SimpleContext:
    """Simple context object for testing"""

    def __init__(self, document_id, file_path):
        self.document_id = document_id
        self.file_path = file_path


async def test_classification():
    """Test classification with product discovery"""
    print("=" * 80)
    print("🧪 Classification + Product Discovery Test")
    print("=" * 80)
    print()

    # Test file
    test_file = r"C:\Users\haast\OneDrive - Kunze & Ritter\Desktop\ServiceManuals\HP\HP_E877_CPMD.pdf"

    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return

    print(f"📄 Test File: {Path(test_file).name}")
    print()

    # Initialize services
    print("🔧 Initializing services...")

    db_service = DatabaseService()
    await db_service.connect()

    ai_service = AIService()
    features_service = FeaturesService()

    web_scraping_service = create_web_scraping_service()
    manufacturer_verification_service = ManufacturerVerificationService(
        database_service=db_service, web_scraping_service=web_scraping_service
    )

    # Create classification processor with verification service
    classifier = ClassificationProcessor(
        database_service=db_service,
        ai_service=ai_service,
        features_service=features_service,
        manufacturer_verification_service=manufacturer_verification_service,
    )

    print("✅ Services initialized")
    print()

    # Create test context
    context = SimpleContext(document_id="test-classification-" + str(Path(test_file).stem), file_path=test_file)

    print("=" * 80)
    print("📋 Running Classification")
    print("=" * 80)
    print()

    try:
        result = await classifier.process(context)

        print()
        print("=" * 80)
        print("📊 Result")
        print("=" * 80)
        print()

        if result and result.success:
            print("✅ Classification successful")
            print()

            data = result.data
            print(f"   Manufacturer: {data.get('manufacturer')}")
            print(f"   Document Type: {data.get('document_type')}")
            print(f"   Version: {data.get('version')}")
            print()

            if "products_discovered" in data:
                products = data["products_discovered"]
                if products:
                    print(f"   ✅ Products Discovered: {len(products)}")
                    print()
                    for p in products:
                        print(f"      📦 Model: {p['model']}")
                        print(f"         URL: {p['url']}")
                        print(f"         Confidence: {p['confidence']}")
                        if p.get("product_id"):
                            print(f"         DB ID: {p['product_id']}")
                        print()
                else:
                    print("   ⚠️  No products discovered")
            else:
                print("   ⚠️  No products_discovered in result")
        else:
            print("❌ Classification failed")
            if result:
                print(f"   Error: {result.message}")

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
    asyncio.run(test_classification())
