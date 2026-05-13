"""
Product Discovery Test - Logging Only (No DB Storage)

Tests product discovery and logs all findings without database operations.
"""

import asyncio
import json
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service


async def test_discovery_logging():
    """Test product discovery and log all results"""

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"product_discovery_log_{timestamp}.txt"
    json_file = f"product_discovery_results_{timestamp}.json"

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("🧪 Product Discovery Test - Logging Only")
    log("=" * 80)
    log(f"Started: {datetime.now().isoformat()}")
    log("")

    # Initialize services (without DB)
    log("🔧 Initializing services...")
    web_service = create_web_scraping_service()
    verification_service = ManufacturerVerificationService(
        database_service=None,
        web_scraping_service=web_service,  # No DB
    )
    log("✅ Services initialized")
    log("")

    # Test cases
    test_cases = [
        {
            "manufacturer": "HP Inc.",
            "model": "Color LaserJet Managed MFP E877z",
            "expected_url": "https://support.hp.com/us-en/drivers/hp-color-laserjet-managed-mfp-e877z-printer-series/2101127729",
        },
        {"manufacturer": "HP Inc.", "model": "M454dn", "expected_url": None},
        {"manufacturer": "Brother", "model": "HL-L8360CDW", "expected_url": None},
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        log("=" * 80)
        log(f"📋 Test Case {i}/{len(test_cases)}")
        log("=" * 80)
        log(f"Manufacturer: {test_case['manufacturer']}")
        log(f"Model: {test_case['model']}")
        if test_case["expected_url"]:
            log(f"Expected URL: {test_case['expected_url']}")
        log("")

        try:
            log("🔍 Discovering product page...")
            start_time = datetime.now()

            # Discover without saving to DB
            discovery = await verification_service.discover_product_page(
                manufacturer=test_case["manufacturer"],
                model_number=test_case["model"],
                save_to_db=False,  # Don't save to DB
            )

            duration = (datetime.now() - start_time).total_seconds()

            if discovery and discovery.get("url"):
                log(f"✅ Product page found in {duration:.2f}s")
                log("")
                log("📍 Main URL:")
                log(f"   {discovery['url']}")
                log(f"   Source: {discovery['source']}")
                log(f"   Confidence: {discovery['confidence']:.2f}")
                log(f"   Score: {discovery.get('score', 0)}")
                log("")

                # Check if it matches expected URL
                if test_case["expected_url"]:
                    if discovery["url"] == test_case["expected_url"]:
                        log("   ✅ EXACT MATCH with expected URL!")
                    elif test_case["expected_url"] in str(discovery.get("citations", [])):
                        log("   ⚠️  Expected URL found in citations but not selected")
                    else:
                        log("   ℹ️  Different URL than expected (may be valid alternative)")
                log("")

                # Log alternatives
                if discovery.get("alternatives"):
                    log(f"📚 Alternative URLs ({len(discovery['alternatives'])}):")
                    for j, alt in enumerate(discovery["alternatives"], 1):
                        log(f"   {j}. {alt['url']}")
                        log(f"      Score: {alt['score']}")
                    log("")

                # Log AI answer
                if discovery.get("answer"):
                    log("💬 AI Answer:")
                    answer_lines = discovery["answer"][:500].split("\n")
                    for line in answer_lines[:5]:  # First 5 lines
                        log(f"   {line}")
                    if len(discovery["answer"]) > 500:
                        log("   ...")
                    log("")

                # Log citations
                if discovery.get("citations"):
                    log(f"📖 Citations ({len(discovery['citations'])}):")
                    for j, citation in enumerate(discovery["citations"][:5], 1):
                        if isinstance(citation, str):
                            log(f"   {j}. {citation}")
                        elif isinstance(citation, dict):
                            log(f"   {j}. {citation.get('url', citation)}")
                    log("")

                # What would be saved to DB
                log("💾 Data that would be saved to database:")
                log("")
                log("   URLs (JSONB):")
                log(f"      product_page: {discovery['url']}")
                log(f"      source: {discovery['source']}")
                log(f"      verified: {discovery.get('verified', False)}")
                log("")
                log("   Metadata (JSONB):")
                log(f"      discovery_confidence: {discovery['confidence']:.2f}")
                log(f"      discovery_source: {discovery['source']}")
                log(f"      score: {discovery.get('score', 0)}")
                if discovery.get("alternatives"):
                    log(f"      alternatives_count: {len(discovery['alternatives'])}")
                log("")

                results.append({"test_case": test_case, "discovery": discovery, "duration": duration, "success": True})
            else:
                log("❌ No product page found")
                results.append({"test_case": test_case, "success": False, "error": "No product page found"})

        except Exception as e:
            log(f"❌ Error: {e}")
            import traceback

            log(traceback.format_exc())
            results.append({"test_case": test_case, "success": False, "error": str(e)})

        log("")

    # Summary
    log("=" * 80)
    log("📊 SUMMARY")
    log("=" * 80)

    successful = sum(1 for r in results if r["success"])
    total = len(results)

    log(f"Total tests: {total}")
    log(f"Successful: {successful}")
    log(f"Failed: {total - successful}")
    log(f"Success rate: {(successful/total*100):.1f}%")
    log("")

    if successful > 0:
        log("✅ Successful discoveries:")
        for result in results:
            if result["success"]:
                tc = result["test_case"]
                disc = result["discovery"]
                log(f"   • {tc['manufacturer']} {tc['model']}")
                log(f"     URL: {disc['url']}")
                log(f"     Confidence: {disc['confidence']:.2f}")
                log(f"     Duration: {result['duration']:.2f}s")
        log("")

    log("=" * 80)
    log("💾 Saving results...")
    log("=" * 80)

    # Save log file
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log(f"✅ Log saved: {log_file}")

    # Save JSON results
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    log(f"✅ JSON saved: {json_file}")

    log("")
    log("=" * 80)
    log("✅ Test Complete!")
    log("=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(test_discovery_logging())
