#!/usr/bin/env python3
"""Diagnose: videos without series_id and enrichment status."""

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
        # --- 252 videos without series_id: who are they? ---
        print("=" * 60)
        print("Videos ohne series_id – nach Hersteller / Plattform")
        print("=" * 60)
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(m.name, '(kein Hersteller)') AS manufacturer,
                v.platform,
                COUNT(*) AS anzahl
            FROM krai_content.videos v
            LEFT JOIN krai_core.manufacturers m ON m.id = v.manufacturer_id
            WHERE v.series_id IS NULL
            GROUP BY m.name, v.platform
            ORDER BY anzahl DESC
            """
        )
        for r in rows:
            print(f"  {r['manufacturer']:30s}  {r['platform'] or '?':20s}  {r['anzahl']:>5}")

        # --- Lexmark specifically ---
        lex_null = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid AND series_id IS NULL",
            LEXMARK_ID,
        )
        print(f"\nLexmark-Videos ohne series_id: {lex_null}")

        if lex_null > 0:
            rows2 = await conn.fetch(
                """
                SELECT v.video_url
                FROM krai_content.videos v
                WHERE v.manufacturer_id = $1::uuid AND v.series_id IS NULL
                LIMIT 5
                """,
                LEXMARK_ID,
            )
            print("  Beispiele:")
            for r in rows2:
                print(f"    {r['video_url']}")

        # --- Enrichment status for Lexmark videos ---
        print("\n" + "=" * 60)
        print("Enrichment-Status Lexmark-Videos")
        print("=" * 60)
        enriched = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid AND enriched_at IS NOT NULL",
            LEXMARK_ID,
        )
        needs_enrichment = await conn.fetchval(
            """
            SELECT COUNT(*) FROM krai_content.videos
            WHERE manufacturer_id = $1::uuid
              AND (metadata->>'needs_enrichment')::boolean = true
            """,
            LEXMARK_ID,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid",
            LEXMARK_ID,
        )
        platforms = await conn.fetch(
            """
            SELECT platform, COUNT(*) AS anzahl
            FROM krai_content.videos
            WHERE manufacturer_id = $1::uuid
            GROUP BY platform
            """,
            LEXMARK_ID,
        )
        print(f"  Gesamt            : {total}")
        print(f"  enriched_at gesetzt: {enriched}")
        print(f"  needs_enrichment   : {needs_enrichment}")
        print("  Plattformen:")
        for r in platforms:
            print(f"    {r['platform']:20s}  {r['anzahl']:>5}")
        print()
        print("  ⚠  Der Standard-VideoEnricher verarbeitet nur")
        print("     brightcove / youtube / vimeo.")
        print("     Lexmark-Support-Seiten (lexmark_support) brauchen")
        print("     einen eigenen Scraper.")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
