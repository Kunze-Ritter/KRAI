"""
Quick test for PostgreSQL direct connection
"""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv


async def test_connection():
    # Load environment
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", "env.database")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Loaded env from: {env_file}")

    postgres_url = os.getenv("POSTGRES_URL")

    if not postgres_url:
        print("❌ POSTGRES_URL not found in environment!")
        return

    print(f"✅ POSTGRES_URL found: {postgres_url[:50]}...")

    try:
        # Test connection
        print("\n🔌 Testing PostgreSQL connection...")
        conn = await asyncpg.connect(postgres_url)
        print("✅ Connected to PostgreSQL!")

        # Test cross-schema query (images)
        print("\n📊 Testing cross-schema query (krai_content.images)...")
        result = await conn.fetchval("SELECT COUNT(*) FROM krai_content.images")
        print(f"✅ Found {result} images in krai_content.images")

        # Test cross-schema query (chunks)
        print("\n📊 Testing cross-schema query (krai_content.chunks)...")
        result = await conn.fetchval("SELECT COUNT(*) FROM krai_content.chunks")
        print(f"✅ Found {result} chunks in krai_content.chunks")

        # Test image deduplication query
        print("\n🔍 Testing image deduplication query...")
        result = await conn.fetchrow(
            """
            SELECT file_hash, COUNT(*) as count
            FROM krai_content.images
            WHERE file_hash IS NOT NULL
            GROUP BY file_hash
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """
        )
        if result:
            print(f"✅ Found duplicate: {result['file_hash'][:16]}... appears {result['count']}x")
        else:
            print("✅ No duplicates found")

        await conn.close()
        print("\n✅ All tests passed! PostgreSQL connection works perfectly!")

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n🔍 Troubleshooting:")
        print("   1. Check POSTGRES_URL in env.database")
        print("   2. Verify password is correct")
        print("   3. Ensure using Session Pooler (not Direct Connection)")


if __name__ == "__main__":
    asyncio.run(test_connection())
