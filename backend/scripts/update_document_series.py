#!/usr/bin/env python3
"""
Update document series from existing products

Reads product_series from document_products and updates documents.series
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from dotenv import load_dotenv

from backend.services.db_pool import get_pool

load_dotenv()


async def main():
    print("=" * 80)
    print("UPDATE DOCUMENT SERIES FROM PRODUCTS")
    print("=" * 80)

    pool = await get_pool()

    # Get all documents without series
    async with pool.acquire() as conn:
        docs = await conn.fetch(
            """
            SELECT id, filename, manufacturer
            FROM public.vw_documents
            WHERE series IS NULL
        """
        )

    print(f"\n📄 Documents without series: {len(docs)}")

    updated_count = 0

    for doc in docs:
        doc_id = doc["id"]
        filename = doc["filename"]

        # Get products for this document via JOIN
        async with pool.acquire() as conn:
            result = await conn.fetch(
                """
                SELECT DISTINCT p.series
                FROM krai_core.document_products dp
                JOIN krai_core.products p ON dp.product_id = p.id
                WHERE dp.document_id = $1
                AND p.series IS NOT NULL
            """,
                doc_id,
            )

        if not result:
            continue

        # Collect unique series
        series_set = set()
        for row in result:
            series = row.get("series")
            if series:
                series_set.add(series)

        if series_set:
            # Update document with series
            series_str = ",".join(sorted(series_set))

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE krai_core.documents
                    SET series = $1
                    WHERE id = $2
                """,
                    series_str,
                    doc_id,
                )

            print(f"✅ {filename}: {series_str}")
            updated_count += 1

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Documents updated: {updated_count}")
    print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
