"""
Test Firecrawl Cloud API specification extraction

This script tests the new extract_specifications_with_search() method
that uses Firecrawl Cloud API /v1/search to find and extract specs
from public sources (no service manuals).
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv

from backend.services.manufacturer_verification_service import ManufacturerVerificationService

load_dotenv()


async def main():
    # Initialize service (web_scraping_service will be auto-created with default backend)
    service = ManufacturerVerificationService(database_service=None)  # No DB for this test

    # Test with HP LaserJet E877
    manufacturer = "HP Inc."
    model_number = "E877"

    print("=" * 80)
    print("🔥 Firecrawl Specification Extraction Test")
    print("=" * 80)
    print(f"Manufacturer: {manufacturer}")
    print(f"Model: {model_number}")
    print()

    # Extract specifications
    result = await service.extract_specifications_with_search(
        manufacturer=manufacturer,
        model_number=model_number,
        save_to_db=False,  # Don't save for this test
    )

    print()
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)

    if result.get("specifications"):
        specs = result["specifications"]
        confidence = result.get("confidence", 0)
        sources = result.get("sources", [])

        print(f"✅ SUCCESS! Extracted {len(specs)} specifications")
        print(f"Confidence: {confidence:.2%}")
        print(f"Sources: {len(sources)}")
        print()

        print("📝 Extracted Specifications:")
        print("-" * 80)
        for key, value in sorted(specs.items()):
            if isinstance(value, list):
                print(f"  {key}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")
        print("-" * 80)
        print()

        print("🔗 Sources:")
        for i, source in enumerate(sources, 1):
            print(f"  {i}. {source}")
        print()

        # Highlight key specs
        print("🎯 Key Specifications:")
        key_specs = [
            "print_speed_color_ppm",
            "print_speed_mono_ppm",
            "print_speed_ppm",
            "print_resolution_dpi",
            "memory_gb",
            "storage_gb",
            "paper_sizes",
            "connectivity",
            "duplex",
        ]

        for spec in key_specs:
            if spec in specs:
                value = specs[spec]
                if isinstance(value, list):
                    print(f"  ✅ {spec}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"  ✅ {spec}: {value}")
            else:
                print(f"  ⚠️  {spec}: Not found")

    else:
        print("❌ No specifications extracted")
        if "error" in result:
            print(f"Error: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
