"""
Test Product Discovery with Real Metadata Extraction

Tests the complete workflow:
1. Extract metadata from PDF
2. Discover product pages for found models
3. Extract specifications
4. Save to database
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import fitz  # PyMuPDF

from backend.processors.classification_processor import ClassificationProcessor
from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


async def test_product_discovery_with_metadata():
    """
    Test complete workflow with real HP document
    """
    print("=" * 80)
    print("🧪 Product Discovery with Metadata Extraction Test")
    print("=" * 80)

    # Test file
    test_file = r"C:\Users\haast\OneDrive - Kunze & Ritter\Desktop\ServiceManuals\HP\HP_E877_CPMD.pdf"

    if not Path(test_file).exists():
        print(f"❌ Test file not found: {test_file}")
        return

    print(f"\n📄 Test File: {Path(test_file).name}")
    print(f"📁 Path: {test_file}")

    # Initialize services
    print("\n🔧 Initializing services...")
    web_service = create_web_scraping_service()
    verification_service = ManufacturerVerificationService(web_scraping_service=web_service)
    classification_processor = ClassificationProcessor()

    # Step 1: Extract text from PDF
    print("\n" + "=" * 80)
    print("📖 STEP 1: Extract Text from PDF")
    print("=" * 80)

    start_time = datetime.now()

    try:
        # Extract text using PyMuPDF
        doc = fitz.open(test_file)
        pages = []
        total_chars = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            pages.append(text)
            total_chars += len(text)

        page_count = len(pages)
        doc.close()

        extraction_time = (datetime.now() - start_time).total_seconds()

        print("✅ Text extracted successfully")
        print(f"   Pages: {page_count}")
        print(f"   Total characters: {total_chars:,}")
        print(f"   Time: {extraction_time:.2f}s")

    except Exception as e:
        print(f"❌ Error extracting text: {e}")
        return

    # Step 2: Classify and detect manufacturer/models
    print("\n" + "=" * 80)
    print("🔍 STEP 2: Classify Document & Detect Models")
    print("=" * 80)

    start_time = datetime.now()

    try:
        # Combine first few pages for classification
        sample_text = "\n".join(pages[:10])

        # Simple manufacturer detection from filename
        filename = Path(test_file).name
        manufacturer = None

        # Parse from filename (HP_E877_CPMD.pdf -> HP)
        if filename.startswith("HP_"):
            manufacturer = "HP Inc."
        elif filename.startswith("Canon_"):
            manufacturer = "Canon"
        elif filename.startswith("Brother_"):
            manufacturer = "Brother"

        # Detect models from text (simple pattern matching)
        import re

        models = []

        # HP model patterns (E877, M454dn, etc.)
        hp_patterns = [
            r"\b([A-Z]\d{3,4}[a-z]*)\b",  # E877, M454dn
            r"\b(LaserJet\s+[A-Z0-9]+)\b",
            r"\b(Color\s+LaserJet\s+[A-Z0-9]+)\b",
        ]

        for pattern in hp_patterns:
            matches = re.findall(pattern, sample_text)
            models.extend(matches)

        # Remove duplicates and limit
        models = list(dict.fromkeys(models))[:10]

        classification_time = (datetime.now() - start_time).total_seconds()

        print("✅ Classification complete")
        print("   Document Type: service_manual")
        print(f"   Manufacturer: {manufacturer or 'unknown'}")
        print(f"   Models Found: {len(models)}")
        print(f"   Time: {classification_time:.2f}s")

        if models:
            print("\n   📋 Detected Models:")
            for model in models[:5]:  # Show first 5
                print(f"      - {model}")

        classification = {
            "document_type": "service_manual",
            "manufacturer": manufacturer,
            "models": models,
            "confidence": 0.9 if manufacturer and models else 0.5,
        }

    except Exception as e:
        print(f"❌ Error in classification: {e}")
        import traceback

        traceback.print_exc()
        return

    # Step 3: Discover product pages for found models
    manufacturer = classification.get("manufacturer", "HP Inc.")
    models = classification.get("models", [])

    if not models:
        print("\n⚠️  No models found - cannot proceed with product discovery")
        return

    print("\n" + "=" * 80)
    print("🌐 STEP 3: Discover Product Pages")
    print("=" * 80)

    discovered_products = []

    # Test with first 3 models
    test_models = models[:3]

    for i, model in enumerate(test_models, 1):
        print(f"\n[{i}/{len(test_models)}] 🔍 Discovering: {manufacturer} {model}")
        print("-" * 80)

        try:
            start_time = datetime.now()

            # Discover product page (will auto-save to DB)
            result = await verification_service.discover_product_page(
                manufacturer=manufacturer,
                model_number=model,
                save_to_db=False,  # Don't save yet, just test
            )

            discovery_time = (datetime.now() - start_time).total_seconds()

            if result.get("url"):
                print("   ✅ Product page found!")
                print(f"   📍 URL: {result['url']}")
                print(f"   🎯 Source: {result.get('source')}")
                print(f"   📊 Confidence: {result.get('confidence', 0.0):.2f}")
                print(f"   ⏱️  Time: {discovery_time:.2f}s")

                if result.get("answer"):
                    answer_preview = result["answer"][:200]
                    print(f"   💬 AI Answer: {answer_preview}...")

                if result.get("citations"):
                    print(f"   📚 Citations: {len(result['citations'])} sources")

                discovered_products.append(
                    {
                        "manufacturer": manufacturer,
                        "model": model,
                        "discovery": result,
                        "discovery_time": discovery_time,
                    }
                )
            else:
                print("   ❌ No product page found")
                print(f"   ⏱️  Time: {discovery_time:.2f}s")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Step 4: Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    print(f"\n📄 Document: {Path(test_file).name}")
    print(f"   Pages: {page_count}")
    print(f"   Manufacturer: {manufacturer}")
    print(f"   Models Detected: {len(models)}")
    print(f"   Models Tested: {len(test_models)}")
    print(f"   Products Discovered: {len(discovered_products)}")

    if discovered_products:
        print("\n✅ Successfully Discovered Products:")
        for product in discovered_products:
            print(f"   - {product['model']}")
            print(f"     URL: {product['discovery']['url']}")
            print(f"     Source: {product['discovery']['source']}")
            print(f"     Confidence: {product['discovery']['confidence']:.2f}")

    # Step 5: Save results to JSON
    output_file = f"product_discovery_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = Path(__file__).parent / output_file

    results = {
        "test_file": test_file,
        "test_date": datetime.now().isoformat(),
        "extraction": {"page_count": page_count, "total_characters": total_chars, "extraction_time": extraction_time},
        "classification": {
            "document_type": classification.get("document_type"),
            "manufacturer": manufacturer,
            "models_found": len(models),
            "models": models,
            "confidence": classification.get("confidence", 0.0),
            "classification_time": classification_time,
        },
        "product_discovery": {
            "models_tested": len(test_models),
            "products_discovered": len(discovered_products),
            "discoveries": discovered_products,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_file}")

    # Step 6: Ask if user wants to save to database
    print("\n" + "=" * 80)
    print("💡 Next Steps")
    print("=" * 80)
    print("\nTo save these products to the database, you can:")
    print("1. Set save_to_db=True in discover_product_page()")
    print("2. Use extract_and_save_specifications() to get full specs")
    print("\nExample:")
    print("```python")
    print("result = await verification_service.discover_product_page(")
    print("    manufacturer='HP Inc.',")
    print("    model_number='M454dn',")
    print("    save_to_db=True  # ← Enable auto-save")
    print(")")
    print("```")

    print("\n" + "=" * 80)
    print("✅ Test Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_product_discovery_with_metadata())
