"""
Product Research CLI
====================

Command-line tool for researching products online

Usage:
    # Research single product
    python scripts/research_product.py "Konica Minolta" "C750i"

    # Batch research products without specs
    python scripts/research_product.py --batch --limit 50

    # Force refresh cached research
    python scripts/research_product.py "HP" "LaserJet Pro M454dw" --force

    # Verify research results
    python scripts/research_product.py --verify
"""

import json
import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import asyncio

from research.product_researcher import ProductResearcher
from research.research_integration import ResearchIntegration

from backend.processors.env_loader import load_all_env_files
from services.db_pool import get_pool

# Load environment variables
project_root = Path(__file__).parent.parent
print("Loading environment variables...")
loaded_env_files = load_all_env_files(project_root)
for env_file in loaded_env_files:
    print(f"  ✓ Loaded: {env_file}")

# Database connection will be initialized via get_pool()
print("✓ Database connection ready\n")


async def research_single_product(manufacturer: str, model: str, force: bool = False):
    """Research a single product"""
    print("=" * 80)
    print(f"Researching: {manufacturer} {model}")
    print("=" * 80)

    researcher = ProductResearcher()
    result = await researcher.research_product(manufacturer, model, force_refresh=force)

    if result:
        print("\n✅ Research successful!")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"\n📋 Series: {result.get('series_name')}")
        print(f"Type: {result.get('product_type')}")

        if result.get("specifications"):
            print("\n📊 Specifications:")
            print(json.dumps(result["specifications"], indent=2))

        if result.get("oem_manufacturer"):
            print(f"\n🔄 OEM: {result['oem_manufacturer']}")
            if result.get("oem_notes"):
                print(f"   Notes: {result['oem_notes']}")

        if result.get("source_urls"):
            print("\n🔗 Sources:")
            for url in result["source_urls"][:3]:
                print(f"   - {url}")
    else:
        print("\n❌ Research failed")
        print("   Check logs for details")


async def batch_research(limit: int = 50):
    """Batch research products without specs"""
    print("=" * 80)
    print(f"Batch Research (limit: {limit})")
    print("=" * 80)

    integration = ResearchIntegration(enabled=True)
    stats = await integration.batch_enrich_products(limit=limit)

    print("\n✅ Batch research complete:")
    print(f"   Enriched: {stats['enriched']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"   Failed: {stats['failed']}")


async def verify_research():
    """Show unverified research results for manual verification"""
    print("=" * 80)
    print("Unverified Research Results")
    print("=" * 80)

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT manufacturer, model_number, series_name, product_type,
                       confidence, source_urls
                FROM krai_intelligence.product_research_cache
                WHERE verified = false
                ORDER BY confidence DESC
                LIMIT 20
            """
            )

        if not results:
            print("\n✅ No unverified results")
            return

        print(f"\nFound {len(results)} unverified results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result['manufacturer']} {result['model_number']}")
            print(f"   Series: {result.get('series_name') or 'N/A'}")
            print(f"   Type: {result.get('product_type') or 'N/A'}")
            print(f"   Confidence: {result.get('confidence') or 0:.2f}")
            print(f"   Sources: {len(result.get('source_urls') or [])} URLs")
            print()

        print("\nTo verify a result:")
        print("  python scripts/verify_research.py <manufacturer> <model>")

    except Exception as e:
        print(f"\n❌ Error: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Research products online")
    parser.add_argument("manufacturer", nargs="?", help="Manufacturer name")
    parser.add_argument("model", nargs="?", help="Model number")
    parser.add_argument("--force", action="store_true", help="Force refresh cache")
    parser.add_argument("--batch", action="store_true", help="Batch research products")
    parser.add_argument("--limit", type=int, default=50, help="Batch limit")
    parser.add_argument("--verify", action="store_true", help="Show unverified results")

    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_research())
    elif args.batch:
        asyncio.run(batch_research(limit=args.limit))
    elif args.manufacturer and args.model:
        asyncio.run(research_single_product(args.manufacturer, args.model, force=args.force))
    else:
        parser.print_help()
        print("\nExamples:")
        print('  python scripts/research_product.py "Konica Minolta" "C750i"')
        print("  python scripts/research_product.py --batch --limit 20")
        print("  python scripts/research_product.py --verify")


if __name__ == "__main__":
    main()
