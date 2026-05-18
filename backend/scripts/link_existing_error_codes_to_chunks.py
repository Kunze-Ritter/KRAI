#!/usr/bin/env python3
"""
Link existing error codes to chunks retroactively

This script updates error_codes.chunk_id for all error codes that don't have a chunk_id yet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from dotenv import load_dotenv

from services.db_pool import get_pool

load_dotenv()


async def main():
    print("=" * 80)
    print("LINKING ERROR CODES TO CHUNKS")
    print("=" * 80)

    pool = await get_pool()

    # Get all error codes without chunk_id
    print("\n1. Finding error codes without chunk_id...")
    async with pool.acquire() as conn:
        error_codes = await conn.fetch(
            """
            SELECT id, document_id, error_code, page_number
            FROM public.vw_error_codes
            WHERE chunk_id IS NULL
        """
        )

    total_codes = len(error_codes)
    print(f"   Found {total_codes} error codes without chunk_id")

    if total_codes == 0:
        print("\n✅ All error codes already have chunk_id!")
        return

    # Group by document
    print("\n2. Grouping by document...")
    docs = {}
    for ec in error_codes:
        doc_id = ec["document_id"]
        if doc_id not in docs:
            docs[doc_id] = []
        docs[doc_id].append(ec)

    print(f"   {len(docs)} documents need linking")

    # Link each document's error codes
    print("\n3. Linking error codes to chunks...")
    total_linked = 0
    total_not_found = 0

    for doc_id, codes in docs.items():
        print(f"\n   Document: {doc_id}")
        print(f"   Error codes: {len(codes)}")

        linked = 0
        not_found = 0

        async with pool.acquire() as conn:
            for ec in codes:
                page_num = ec.get("page_number")
                if not page_num:
                    not_found += 1
                    continue

                # Find chunk that contains this page
                chunk = await conn.fetchrow(
                    """
                    SELECT id
                    FROM public.vw_chunks
                    WHERE document_id = $1
                    AND page_start <= $2
                    AND page_end >= $2
                    LIMIT 1
                """,
                    doc_id,
                    page_num,
                )

                if chunk:
                    chunk_id = chunk["id"]

                    # Update error code with chunk_id
                    await conn.execute(
                        """
                        UPDATE krai_intelligence.error_codes
                        SET chunk_id = $1
                        WHERE id = $2
                    """,
                        chunk_id,
                        ec["id"],
                    )

                    linked += 1
                else:
                    not_found += 1
                    print(f"      ⚠️  No chunk found for error code {ec['error_code']} on page {page_num}")

        print(f"   ✅ Linked: {linked}")
        if not_found > 0:
            print(f"   ⚠️  Not found: {not_found}")

        total_linked += linked
        total_not_found += not_found

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total error codes processed: {total_codes}")
    print(f"✅ Successfully linked: {total_linked}")
    if total_not_found > 0:
        print(f"⚠️  Could not link: {total_not_found}")
        print("   (No matching chunk found - page might be outside chunk range)")

    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
