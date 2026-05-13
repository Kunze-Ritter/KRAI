#!/usr/bin/env python3
"""Quick DB check for the Lexmark video import."""

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
        videos = await conn.fetchval(f"SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = '{LEXMARK_ID}'")
        vp_links = await conn.fetchval(
            f"SELECT COUNT(*) FROM krai_content.video_products vp JOIN krai_content.videos v ON v.id = vp.video_id WHERE v.manufacturer_id = '{LEXMARK_ID}'"
        )
        products = await conn.fetchval(
            f"SELECT COUNT(*) FROM krai_core.products WHERE manufacturer_id = '{LEXMARK_ID}'"
        )
        series = await conn.fetchval(
            f"SELECT COUNT(*) FROM krai_core.product_series WHERE manufacturer_id = '{LEXMARK_ID}'"
        )

        print(f"\n{'='*50}")
        print("  Lexmark Import Check")
        print(f"{'='*50}")
        print(f"  Videos importiert    : {videos}")
        print(f"  video_products Links : {vp_links}")
        print(f"  Produkte             : {products}")
        print(f"  Serien               : {series}")
        print(f"{'='*50}")

        print("\n  Produkte (erste 5):")
        rows = await conn.fetch(
            f"SELECT model_number, model_name FROM krai_core.products WHERE manufacturer_id = '{LEXMARK_ID}' ORDER BY model_number LIMIT 5"
        )
        for r in rows:
            print(f"    {r['model_number']}  →  {r['model_name']}")

        print("\n  Serien:")
        rows = await conn.fetch(
            f"SELECT series_name FROM krai_core.product_series WHERE manufacturer_id = '{LEXMARK_ID}' ORDER BY series_name"
        )
        for r in rows:
            print(f"    {r['series_name']}")

        print("\n  Beispiel-Videos (erste 3):")
        rows = await conn.fetch(
            f"SELECT title, video_url FROM krai_content.videos WHERE manufacturer_id = '{LEXMARK_ID}' ORDER BY created_at LIMIT 3"
        )
        for r in rows:
            print(f"    {r['title']}")
            print(f"    {r['video_url']}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
