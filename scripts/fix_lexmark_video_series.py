#!/usr/bin/env python3
"""One-time fix: set series_id on already-imported Lexmark videos via video_products → products."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.database_factory import create_database_adapter

load_all_env_files(PROJECT_ROOT)

LEXMARK_ID = "93974db7-e28e-4cd8-9ac9-5f2e1bdf7403"


async def main():
    db = create_database_adapter()
    await db.connect()
    pool = db._ensure_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE krai_content.videos v
            SET    series_id  = p.series_id,
                   updated_at = NOW()
            FROM   krai_content.video_products vp
            JOIN   krai_core.products p ON p.id = vp.product_id
            WHERE  vp.video_id = v.id
              AND  v.manufacturer_id = $1::uuid
              AND  v.series_id IS NULL
            """,
            LEXMARK_ID,
        )
        print(f"Videos aktualisiert: {result}")

        # Verify
        counts = await conn.fetch(
            """
            SELECT ps.series_name, COUNT(v.id) AS videos
            FROM   krai_content.videos v
            JOIN   krai_core.product_series ps ON ps.id = v.series_id
            WHERE  v.manufacturer_id = $1::uuid
            GROUP  BY ps.series_name
            ORDER  BY ps.series_name
            """,
            LEXMARK_ID,
        )
        print("\nVideos pro Serie:")
        for r in counts:
            print(f"  {r['series_name']:12s}  {r['videos']:>5} Videos")

        # Remaining NULL
        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid AND series_id IS NULL",
            LEXMARK_ID,
        )
        print(f"\nVideos ohne series_id: {null_count}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
