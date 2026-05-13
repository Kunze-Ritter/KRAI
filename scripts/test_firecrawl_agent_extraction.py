"""
Test Firecrawl Agent specification extraction

This script tests the new extract_specifications_with_agent() method
that uses Firecrawl's /v2/agent endpoint for AI-powered structured
data extraction with citations.
"""

import asyncio
import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from dotenv import load_dotenv

from backend.services.manufacturer_verification_service import ManufacturerVerificationService

load_dotenv()


async def main():
    # Initialize service
    service = ManufacturerVerificationService(database_service=None)  # No DB for this test

    # Test with HP LaserJet E877
    manufacturer = "HP Inc."
    model_number = "E877"

    print("=" * 80)
    print("🤖 Firecrawl Agent Specification Extraction Test")
    print("=" * 80)
    print(f"Manufacturer: {manufacturer}")
    print(f"Model: {model_number}")
    print()

    # Extract specifications using Agent
    result = await service.extract_specifications_with_agent(
        manufacturer=manufacturer,
        model_number=model_number,
        save_to_db=False,  # Don't save for this test
    )

    print()
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)

    if result.get("model_configurations"):
        configs = result["model_configurations"]
        confidence = result.get("confidence", 0)
        sources = result.get("sources", [])
        credits_used = result.get("credits_used", 0)
        accessories_saved = result.get("accessories_saved", 0)

        print(f"✅ SUCCESS! Found {len(configs)} model configurations")
        print(f"Confidence: {confidence:.2%}")
        print(f"Sources: {len(sources)}")
        print(f"Credits used: {credits_used}")
        if accessories_saved > 0:
            print(f"💾 Accessories saved to parts catalog: {accessories_saved}")
        print()

        # Save full result to JSON file
        output_file = f"agent_extraction_result_{model_number}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"💾 Full result saved to: {output_file}")
        print()

        # Display summary of each configuration
        print("📝 Model Configurations:")
        print("-" * 80)
        for i, config in enumerate(configs, 1):
            print(f"\n{i}. {config.get('model_name', 'Unknown')}")

            # Variant type
            variant_type = config.get("variant_type")
            if variant_type:
                print(f"   Variant Type: {variant_type}")

            # Hardware specs
            hardware = config.get("hardware_specs", {})
            if hardware:
                print(f"   Print Speed: {hardware.get('print_speed', 'N/A')}")
                print(f"   Paper Capacity: {hardware.get('paper_capacity', 'N/A')}")
                print(f"   Dimensions: {hardware.get('dimensions', 'N/A')}")
                print(f"   Weight: {hardware.get('weight', 'N/A')}")

                # Other technical details
                tech = hardware.get("other_technical_details", {})
                if tech:
                    print("   Technical Details:")
                    for key, value in list(tech.items())[:5]:  # Show first 5
                        print(f"     - {key}: {value}")

            # Key features count
            features = config.get("key_features", [])
            if features:
                print(f"   Key Features: {len(features)} features")
                flow_exclusive = [f for f in features if f.get("is_flow_exclusive")]
                if flow_exclusive:
                    print(f"     - {len(flow_exclusive)} Flow-exclusive features")

            # Accessories count
            accessories = config.get("accessories_and_supplies", [])
            if accessories:
                print(f"   Accessories & Supplies: {len(accessories)} items")

                # Count by category
                categories = {}
                for acc in accessories:
                    cat = acc.get("category", "Unknown")
                    categories[cat] = categories.get(cat, 0) + 1

                print("     Categories:")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                    print(f"       - {cat}: {count} items")

        print("-" * 80)
        print()

        # Display sample accessories
        if configs and configs[0].get("accessories_and_supplies"):
            accessories = configs[0]["accessories_and_supplies"]
            print("🔧 Sample Accessories (first 5):")
            print("-" * 80)
            for i, acc in enumerate(accessories[:5], 1):
                print(f"\n{i}. {acc.get('name', 'Unknown')}")
                print(f"   Part Number: {acc.get('part_number', 'N/A')}")
                print(f"   Category: {acc.get('category', 'N/A')}")
                if acc.get("description"):
                    desc = acc["description"]
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    print(f"   Description: {desc}")
            print("-" * 80)
            print()

        # Display sources
        print("🔗 Sources:")
        for i, source in enumerate(sources, 1):
            print(f"  {i}. {source}")
        print()

        # Highlight key differences between configurations
        print("🎯 Key Differences:")
        if len(configs) > 1:
            base_config = configs[0]
            for i, config in enumerate(configs[1:], 2):
                print(f"\n  Configuration {i} vs Base:")

                # Compare print speed
                if config.get("print_speed") != base_config.get("print_speed"):
                    print(f"    Print Speed: {base_config.get('print_speed')} → {config.get('print_speed')}")

                # Check for speed upgrade kit
                tech = config.get("technical_details", {})
                if "speed_upgrade_kit" in tech:
                    print(f"    Speed Upgrade Kit: {tech['speed_upgrade_kit']}")

                # Compare duty cycle
                base_duty = base_config.get("technical_details", {}).get("duty_cycle_monthly")
                config_duty = tech.get("duty_cycle_monthly")
                if config_duty and config_duty != base_duty:
                    print(f"    Duty Cycle: {base_duty} → {config_duty}")
        else:
            print("  Only one configuration found")

    else:
        print("❌ No model configurations extracted")
        if "error" in result:
            print(f"Error: {result['error']}")

        # Check if it's a credits issue
        if result.get("error") and "402" in str(result.get("error")):
            print()
            print("💡 Tip: Your Firecrawl API key needs credits.")
            print("   Visit: https://www.firecrawl.dev/app/usage")


if __name__ == "__main__":
    asyncio.run(main())
