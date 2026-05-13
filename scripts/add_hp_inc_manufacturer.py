"""
Add HP Inc. manufacturer to database
"""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def add_hp_inc():
    """Add HP Inc. manufacturer to database"""

    postgres_url = os.getenv("POSTGRES_URL")

    print("=" * 80)
    print("🏭 Adding HP Inc. Manufacturer to Database")
    print("=" * 80)
    print()

    conn = await asyncpg.connect(postgres_url)

    try:
        # Check if HP Inc. exists
        existing = await conn.fetchrow("SELECT id, name FROM krai_core.manufacturers WHERE name = $1", "HP Inc.")

        if existing:
            print("✅ HP Inc. already exists in database")
            print(f"   ID: {existing['id']}")
            print(f"   Name: {existing['name']}")
        else:
            # Insert HP Inc.
            result = await conn.fetchrow(
                """
                INSERT INTO krai_core.manufacturers (name)
                VALUES ($1)
                RETURNING id, name
                """,
                "HP Inc.",
            )

            print("✅ HP Inc. added to database")
            print(f"   ID: {result['id']}")
            print(f"   Name: {result['name']}")

        # Check if old "Hewlett Packard" exists
        old_hp = await conn.fetchrow("SELECT id, name FROM krai_core.manufacturers WHERE name = $1", "Hewlett Packard")

        if old_hp:
            print()
            print("⚠️  Old 'Hewlett Packard' manufacturer exists:")
            print(f"   ID: {old_hp['id']}")
            print("   Consider migrating products to 'HP Inc.'")

    finally:
        await conn.close()

    print()
    print("=" * 80)
    print("✅ Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(add_hp_inc())
