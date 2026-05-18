#!/usr/bin/env python3
"""
Fix 252 Lexmark videos without series_id.
Extracts model number directly from the video_url, looks up (or creates) the
series, and also creates missing video_products entries.

Also updates platform from 'lexmark_support' → 'direct' since Lexmark
hosts plain MP4 files (no Brightcove, no YouTube).
"""

import asyncio
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.database_factory import create_database_adapter

load_all_env_files(PROJECT_ROOT)

LEXMARK_ID = "93974db7-e28e-4cd8-9ac9-5f2e1bdf7403"

# Same logic as import script
_MODEL_RE = re.compile(r"/video-details/([^/]+)/", re.IGNORECASE)


def series_from_model(model: str) -> str:
    match = re.match(r"^([A-Za-z]+)", model)
    prefix = match.group(1).upper() if match else "General"
    return f"{prefix}-Series"


async def main():
    db = create_database_adapter()
    await db.connect()
    pool = db._ensure_pool()

    async with pool.acquire() as conn:
        # --- Step 1: Fix platform: lexmark_support → direct ---
        r = await conn.execute(
            """
            UPDATE krai_content.videos
            SET platform = 'direct', updated_at = NOW()
            WHERE manufacturer_id = $1::uuid
              AND platform = 'lexmark_support'
            """,
            LEXMARK_ID,
        )
        print(f"Platform → 'direct': {r}")

        # --- Step 2: Fix series_id for videos without one ---
        videos_without_series = await conn.fetch(
            """
            SELECT id, video_url
            FROM krai_content.videos
            WHERE manufacturer_id = $1::uuid
              AND series_id IS NULL
            """,
            LEXMARK_ID,
        )
        print(f"\nVideos ohne series_id: {len(videos_without_series)}")

        series_cache = {}
        updated = 0
        skipped = 0

        for row in videos_without_series:
            video_id = str(row["id"])
            url = row["video_url"] or ""

            m = _MODEL_RE.search(url)
            if not m:
                print(f"  ⚠ Kein Modell in URL: {url}")
                skipped += 1
                continue

            model_number = m.group(1)
            series_name = series_from_model(model_number)

            # Get or create series
            if series_name not in series_cache:
                series_row = await conn.fetchrow(
                    """
                    SELECT id FROM krai_core.product_series
                    WHERE manufacturer_id = $1::uuid
                      AND LOWER(series_name) = LOWER($2)
                    LIMIT 1
                    """,
                    LEXMARK_ID,
                    series_name,
                )
                if series_row:
                    series_cache[series_name] = str(series_row["id"])
                else:
                    # Create series
                    new_series_id = await conn.fetchval(
                        """
                        INSERT INTO krai_core.product_series
                            (manufacturer_id, series_name, series_code)
                        VALUES ($1::uuid, $2, $3)
                        RETURNING id
                        """,
                        LEXMARK_ID,
                        series_name,
                        series_name.replace("-Series", ""),
                    )
                    series_cache[series_name] = str(new_series_id)
                    print(f"  + Neue Serie erstellt: {series_name}")

            series_id = series_cache[series_name]

            # Update video series_id
            await conn.execute(
                """
                UPDATE krai_content.videos
                SET series_id = $2::uuid, updated_at = NOW()
                WHERE id = $1::uuid
                """,
                video_id,
                series_id,
            )

            # Ensure product exists and video_products link exists
            product_row = await conn.fetchrow(
                """
                SELECT id, series_id FROM krai_core.products
                WHERE manufacturer_id = $1::uuid
                  AND LOWER(model_number) = LOWER($2)
                LIMIT 1
                """,
                LEXMARK_ID,
                model_number,
            )

            if product_row:
                product_id = str(product_row["id"])
                # Ensure video_products entry
                existing_link = await conn.fetchval(
                    """
                    SELECT id FROM krai_content.video_products
                    WHERE video_id = $1::uuid AND product_id = $2::uuid
                    LIMIT 1
                    """,
                    video_id,
                    product_id,
                )
                if not existing_link:
                    await conn.execute(
                        """
                        INSERT INTO krai_content.video_products (video_id, product_id)
                        VALUES ($1::uuid, $2::uuid)
                        """,
                        video_id,
                        product_id,
                    )

            updated += 1

        print(f"\nAktualisiert : {updated}")
        print(f"Übersprungen  : {skipped}")

        # --- Step 3: Final verification ---
        null_remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid AND series_id IS NULL",
            LEXMARK_ID,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_content.videos WHERE manufacturer_id = $1::uuid",
            LEXMARK_ID,
        )
        platforms = await conn.fetch(
            """
            SELECT platform, COUNT(*) AS n
            FROM krai_content.videos
            WHERE manufacturer_id = $1::uuid
            GROUP BY platform ORDER BY n DESC
            """,
            LEXMARK_ID,
        )
        series_counts = await conn.fetch(
            """
            SELECT ps.series_name, COUNT(v.id) AS videos
            FROM krai_content.videos v
            JOIN krai_core.product_series ps ON ps.id = v.series_id
            WHERE v.manufacturer_id = $1::uuid
            GROUP BY ps.series_name
            ORDER BY ps.series_name
            """,
            LEXMARK_ID,
        )

        print(f"\n{'='*55}")
        print("  Ergebnis")
        print(f"{'='*55}")
        print(f"  Videos gesamt          : {total}")
        print(f"  Noch ohne series_id    : {null_remaining}")
        print("\n  Plattformen:")
        for r in platforms:
            print(f"    {r['platform']:20s}  {r['n']:>5}")
        print("\n  Videos pro Serie:")
        for r in series_counts:
            print(f"    {r['series_name']:14s}  {r['videos']:>5}")
        print("\n  ℹ️  Lexmark nutzt direkte MP4-Dateien (kein Brightcove).")
        print("     Die eigentliche MP4-URL steckt im HTML der Support-Seite.")
        print(f"{'='*55}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
