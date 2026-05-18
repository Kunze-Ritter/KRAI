"""
Backfill related_error_codes for krai_content.images.

For each image that has no related_error_codes, finds error codes from
krai_intelligence.error_codes on the same document + page and sets them.

Safe to re-run: only updates rows where related_error_codes is empty/null.
Use --all to force-update all images (including those with existing links).

Usage:
    python scripts/backfill_image_error_codes.py
    python scripts/backfill_image_error_codes.py --all
    python scripts/backfill_image_error_codes.py --dry-run
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER','krai_user')}:{os.getenv('POSTGRES_PASSWORD','krai_password')}"
    f"@{os.getenv('POSTGRES_HOST','localhost')}:{os.getenv('POSTGRES_PORT','5432')}/{os.getenv('POSTGRES_DB','krai_db')}",
)

FETCH_SQL = """
    SELECT
        img.id,
        array_agg(DISTINCT ec.error_code) AS error_codes
    FROM krai_content.images img
    JOIN krai_intelligence.error_codes ec
        ON ec.document_id = img.document_id
        AND ec.page_number = img.page_number
        AND ec.is_category IS NOT TRUE
    {where_clause}
    GROUP BY img.id
"""

UPDATE_SQL = """
    UPDATE krai_content.images
    SET related_error_codes = $1::text[]
    WHERE id = $2::uuid
"""


async def run(force_all: bool, dry_run: bool) -> None:
    print(f"Connecting to: {DATABASE_URL.split('@')[1]}")
    conn = await asyncpg.connect(DATABASE_URL)

    where = "" if force_all else "WHERE (img.related_error_codes IS NULL OR img.related_error_codes = '{}')"
    rows = await conn.fetch(FETCH_SQL.format(where_clause=where))
    print(f"Found {len(rows)} image(s) to update")

    if dry_run:
        for r in rows[:10]:
            print(f"  {r['id']}: {r['error_codes']}")
        if len(rows) > 10:
            print(f"  ... and {len(rows) - 10} more")
        await conn.close()
        return

    updated = 0
    for row in rows:
        await conn.execute(UPDATE_SQL, row["error_codes"], row["id"])
        updated += 1
        if updated % 100 == 0:
            print(f"  Updated {updated}/{len(rows)}...")

    await conn.close()
    print(f"Done — updated {updated} image(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill related_error_codes for images")
    parser.add_argument("--all", action="store_true", help="Re-link all images, not just empty ones")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without updating")
    args = parser.parse_args()
    asyncio.run(run(force_all=args.all, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
