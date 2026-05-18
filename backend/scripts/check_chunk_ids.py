#!/usr/bin/env python3
"""Check if error codes have chunk_ids"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from dotenv import load_dotenv

from services.db_pool import get_pool

load_dotenv()


async def main():
    print("=" * 80)
    print("ERROR CODES WITH CHUNK IDs")
    print("=" * 80)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get sample error codes
        result = await conn.fetch(
            """
            SELECT error_code, chunk_id, page_number
            FROM public.vw_error_codes
            WHERE document_id = '89387251-6506-4c41-ac7c-53666e82d457'
            LIMIT 10
        """
        )

        print("\nSample error codes (first 10):")
        for ec in result:
            chunk_id = ec.get("chunk_id")
            chunk_display = chunk_id[:8] + "..." if chunk_id else "NULL"
            print(f"  {ec['error_code']:<12} chunk_id={chunk_display:<12} (page {ec['page_number']})")

        # Count with/without chunk_id
        with_chunk_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM public.vw_error_codes
            WHERE document_id = '89387251-6506-4c41-ac7c-53666e82d457'
            AND chunk_id IS NOT NULL
        """
        )

        without_chunk_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM public.vw_error_codes
            WHERE document_id = '89387251-6506-4c41-ac7c-53666e82d457'
            AND chunk_id IS NULL
        """
        )

        total = with_chunk_count + without_chunk_count

        print("\n" + "=" * 80)
        print("STATISTICS")
        print("=" * 80)
        print(f"Total error codes: {total}")
        print(f"✅ With chunk_id: {with_chunk_count} ({with_chunk_count/total*100:.1f}%)")
        print(f"❌ Without chunk_id: {without_chunk_count} ({without_chunk_count/total*100:.1f}%)")

        if with_chunk_count == total:
            print("\n🎉 ALL ERROR CODES HAVE CHUNK IDs!")


if __name__ == "__main__":
    asyncio.run(main())
