"""
Complete Product Discovery Test with Database Storage

Tests the full workflow:
1. Find product pages with Perplexity AI
2. Extract specifications
3. Save to database
4. Log everything
"""

import asyncio
import json
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from backend.services.database_service import DatabaseService
from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


class DetailedLogger:
    """Logger that writes to both console and file"""

    def __init__(self, log_file):
        self.log_file = log_file
        self.logs = []

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.logs.append(log_entry)

    def section(self, title):
        separator = "=" * 80
        self.log(separator)
        self.log(title)
        self.log(separator)

    def save(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.logs))
        print(f"\n💾 Log saved to: {self.log_file}")


async def test_full_product_discovery():
    """
    Complete test of product discovery and database storage
    """
    # Setup logging
    log_file = f"product_discovery_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    logger = DetailedLogger(log_file)

    logger.section("🧪 Product Discovery & Database Storage Test")
    logger.log(f"Test started at: {datetime.now().isoformat()}")

    # Initialize services
    logger.section("🔧 Initializing Services")

    try:
        web_service = create_web_scraping_service()
        logger.log("✅ Web scraping service initialized")

        database_service = DatabaseService()
        logger.log("✅ Database service initialized")

        verification_service = ManufacturerVerificationService(
            database_service=database_service, web_scraping_service=web_service
        )
        logger.log("✅ Manufacturer verification service initialized")

    except Exception as e:
        logger.log(f"❌ Error initializing services: {e}", "ERROR")
        logger.save()
        return

    # Test cases - different HP models
    test_cases = [
        {
            "manufacturer": "HP Inc.",
            "model": "Color LaserJet Managed MFP E877z",
            "description": "HP E877z - Full product name with Managed MFP",
        },
        {"manufacturer": "HP Inc.", "model": "M454dn", "description": "HP M454dn - Simple model number"},
        {"manufacturer": "Brother", "model": "HL-L8360CDW", "description": "Brother HL-L8360CDW - Color laser printer"},
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        logger.section(f"📋 Test Case {i}/{len(test_cases)}: {test_case['description']}")

        manufacturer = test_case["manufacturer"]
        model = test_case["model"]

        logger.log(f"Manufacturer: {manufacturer}")
        logger.log(f"Model: {model}")

        # Step 1: Discover product page
        logger.log("\n🔍 Step 1: Discovering product page...")

        try:
            start_time = datetime.now()

            discovery_result = await verification_service.discover_product_page(
                manufacturer=manufacturer,
                model_number=model,
                save_to_db=True,  # Enable auto-save to DB
            )

            discovery_time = (datetime.now() - start_time).total_seconds()

            if discovery_result and discovery_result.get("url"):
                logger.log(f"✅ Product page found in {discovery_time:.2f}s")
                logger.log(f"   URL: {discovery_result['url']}")
                logger.log(f"   Source: {discovery_result['source']}")
                logger.log(f"   Confidence: {discovery_result['confidence']:.2f}")
                logger.log(f"   Score: {discovery_result.get('score', 0)}")

                if discovery_result.get("product_id"):
                    logger.log(f"   ✅ Saved to DB with ID: {discovery_result['product_id']}")

                # Log alternatives
                if discovery_result.get("alternatives"):
                    logger.log("\n   📚 Alternative URLs found:")
                    for alt in discovery_result["alternatives"]:
                        logger.log(f"      - {alt['url']} (score: {alt['score']})")

                # Log AI answer
                if discovery_result.get("answer"):
                    answer_preview = discovery_result["answer"][:200]
                    logger.log(f"\n   💬 AI Answer: {answer_preview}...")

                # Step 2: Extract specifications (if URL found)
                logger.log("\n📊 Step 2: Extracting specifications...")

                try:
                    specs_result = await verification_service.extract_and_save_specifications(
                        manufacturer=manufacturer, model_number=model, product_url=discovery_result["url"]
                    )

                    if specs_result.get("specifications"):
                        logger.log("✅ Specifications extracted:")
                        for key, value in specs_result["specifications"].items():
                            logger.log(f"   - {key}: {value}")
                    else:
                        logger.log("⚠️  No specifications extracted")
                        if specs_result.get("error"):
                            logger.log(f"   Error: {specs_result['error']}")

                except Exception as e:
                    logger.log(f"❌ Error extracting specs: {e}", "ERROR")

                # Step 3: Verify database entry
                logger.log("\n💾 Step 3: Verifying database entry...")

                try:
                    # Query database for the product
                    query = """
                        SELECT
                            p.id,
                            p.model_number,
                            m.name as manufacturer_name,
                            p.urls,
                            p.metadata,
                            p.specifications,
                            p.created_at,
                            p.updated_at
                        FROM krai_core.products p
                        JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
                        WHERE m.name = %s AND p.model_number = %s
                        LIMIT 1
                    """

                    db_result = await database_service.fetch_one(query, (manufacturer, model))

                    if db_result:
                        logger.log("✅ Product found in database:")
                        logger.log(f"   ID: {db_result['id']}")
                        logger.log(f"   Model: {db_result['model_number']}")
                        logger.log(f"   Manufacturer: {db_result['manufacturer_name']}")
                        logger.log(f"   Created: {db_result['created_at']}")
                        logger.log(f"   Updated: {db_result['updated_at']}")

                        # Log URLs
                        if db_result["urls"]:
                            logger.log("\n   📍 Stored URLs:")
                            urls_data = db_result["urls"]
                            for key, value in urls_data.items():
                                logger.log(f"      {key}: {value}")

                        # Log Metadata
                        if db_result["metadata"]:
                            logger.log("\n   📋 Stored Metadata:")
                            metadata = db_result["metadata"]
                            for key, value in metadata.items():
                                if key != "discovery_answer":  # Skip long answer
                                    logger.log(f"      {key}: {value}")

                        # Log Specifications
                        if db_result["specifications"]:
                            logger.log("\n   ⚙️  Stored Specifications:")
                            specs = db_result["specifications"]
                            for key, value in specs.items():
                                logger.log(f"      {key}: {value}")

                        discovery_result["db_entry"] = {
                            "id": str(db_result["id"]),
                            "created_at": str(db_result["created_at"]),
                            "updated_at": str(db_result["updated_at"]),
                        }
                    else:
                        logger.log("⚠️  Product not found in database")

                except Exception as e:
                    logger.log(f"❌ Error querying database: {e}", "ERROR")

                results.append({"test_case": test_case, "discovery": discovery_result, "success": True})

            else:
                logger.log("❌ No product page found")
                results.append({"test_case": test_case, "success": False, "error": "No product page found"})

        except Exception as e:
            logger.log(f"❌ Error in test case: {e}", "ERROR")
            import traceback

            logger.log(traceback.format_exc(), "ERROR")
            results.append({"test_case": test_case, "success": False, "error": str(e)})

    # Summary
    logger.section("📊 Test Summary")

    successful = sum(1 for r in results if r["success"])
    total = len(results)

    logger.log(f"Total test cases: {total}")
    logger.log(f"Successful: {successful}")
    logger.log(f"Failed: {total - successful}")
    logger.log(f"Success rate: {(successful/total*100):.1f}%")

    logger.log("\n✅ Successful discoveries:")
    for result in results:
        if result["success"]:
            tc = result["test_case"]
            disc = result["discovery"]
            logger.log(f"   - {tc['manufacturer']} {tc['model']}")
            logger.log(f"     URL: {disc.get('url', 'N/A')}")
            logger.log(f"     Source: {disc.get('source', 'N/A')}")
            if disc.get("db_entry"):
                logger.log(f"     DB ID: {disc['db_entry']['id']}")

    # Save results to JSON
    json_file = f"product_discovery_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    logger.log(f"\n💾 Results saved to: {json_file}")

    # Save log
    logger.save()

    logger.section("✅ Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_full_product_discovery())
