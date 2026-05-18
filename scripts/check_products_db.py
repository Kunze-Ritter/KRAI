"""
Check if products were saved to database
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment
load_dotenv()

from backend.services.database_service import DatabaseService


async def check_products():
    """Check products in database"""
    print("=" * 80)
    print("💾 Checking Products in Database")
    print("=" * 80)
    print()

    # Get PostgreSQL URL from environment
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_CONNECTION_URL") or os.getenv("DATABASE_URL")

    if not postgres_url:
        print("❌ No PostgreSQL URL found in environment")
        return

    print(f"✅ Using PostgreSQL: {postgres_url[:40]}...")
    print()

    db = DatabaseService(postgres_url=postgres_url, database_type="postgresql")

    try:
        await db.connect()
        print("✅ Connected to database")
        print()

        # Check recent products (basic fields only)
        query = """
            SELECT
                p.id,
                p.model_number,
                m.name as manufacturer_name,
                p.created_at,
                p.updated_at
            FROM krai_core.products p
            JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
            ORDER BY p.created_at DESC
            LIMIT 10
        """

        products = await db.fetch_all(query)

        if products:
            print(f"✅ Found {len(products)} recent products:")
            print()

            for i, product in enumerate(products, 1):
                print(f"{i}. {product['manufacturer_name']} {product['model_number']}")
                print(f"   ID: {product['id']}")
                print(f"   Created: {product['created_at']}")
                print(f"   Updated: {product['updated_at']}")
                print()
        else:
            print("ℹ️  No products found in database")

        # Check for HP E877 specifically
        print("=" * 80)
        print("🔍 Checking for HP E877 Products")
        print("=" * 80)
        print()

        query_e877 = """
            SELECT
                p.id,
                p.model_number,
                m.name as manufacturer_name,
                p.created_at
            FROM krai_core.products p
            JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
            WHERE m.name ILIKE '%HP%'
              AND (p.model_number ILIKE '%E877%' OR p.model_number ILIKE '%E87%')
            ORDER BY p.created_at DESC
        """

        e877_products = await db.fetch_all(query_e877)

        if e877_products:
            print(f"✅ Found {len(e877_products)} HP E877 products:")
            print()
            for product in e877_products:
                print(f"   • {product['manufacturer_name']} {product['model_number']}")
                print(f"     Created: {product['created_at']}")
                print()
        else:
            print("❌ No HP E877 products found")
            print()
            print("This means Product Discovery did NOT run during classification.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await db.disconnect()
        print()
        print("=" * 80)
        print("✅ Check Complete")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_products())
