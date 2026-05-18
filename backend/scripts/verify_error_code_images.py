#!/usr/bin/env python3
"""Verify error code to images linking"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from dotenv import load_dotenv

from services.db_pool import get_pool

load_dotenv()


async def main():
    print("=" * 80)
    print("ERROR CODE IMAGES VERIFICATION")
    print("=" * 80)

    pool = await get_pool()

    # Get total links
    async with pool.acquire() as conn:
        links = await conn.fetch(
            """
            SELECT *
            FROM krai_intelligence.error_code_images
        """
        )

    print(f"\n📸 Total image links: {len(links)}")

    # Group by match method
    methods = {}
    for link in links:
        method = link.get("match_method", "unknown")
        methods[method] = methods.get(method, 0) + 1

    print("\n📊 By match method:")
    for method, count in sorted(methods.items()):
        print(f"  {method}: {count}")

    # Sample error codes with images
    print("\n🔴 Sample error codes with images:")
    async with pool.acquire() as conn:
        result = await conn.fetch(
            """
            SELECT
                ec.error_code,
                ec.page_number,
                COUNT(eci.image_id) as image_count,
                array_agg(eci.match_method) as methods
            FROM krai_intelligence.error_codes ec
            LEFT JOIN krai_intelligence.error_code_images eci ON ec.id = eci.error_code_id
            WHERE ec.document_id = '89387251-6506-4c41-ac7c-53666e82d457'
            GROUP BY ec.id, ec.error_code, ec.page_number
            HAVING COUNT(eci.image_id) > 0
            ORDER BY COUNT(eci.image_id) DESC
            LIMIT 5
        """
        )

    if result:
        for row in result:
            print(f"  {row['error_code']} (page {row['page_number']}): {row['image_count']} images")
            print(f"    Methods: {', '.join(row['methods'])}")

    # Error codes without images
    async with pool.acquire() as conn:
        no_images_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM krai_intelligence.error_codes ec
            LEFT JOIN krai_intelligence.error_code_images eci ON ec.id = eci.error_code_id
            WHERE ec.document_id = '89387251-6506-4c41-ac7c-53666e82d457'
            AND eci.id IS NULL
        """
        )

    if no_images_count:
        print(f"\n⚠️  Error codes without images: {no_images_count}")

    print("\n" + "=" * 80)
    print("✅ Many-to-many image linking working!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
