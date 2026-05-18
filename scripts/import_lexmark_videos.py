#!/usr/bin/env python3
"""
Lexmark Video Links Import Script
==================================

Reads Lexmark support video URLs from a JSON export and writes them into the
KRAI database (krai_content.videos + krai_content.video_products).
Manufacturers, product series, and products are created if they do not yet
exist.

Usage:
    python scripts/import_lexmark_videos.py --json data/lexmark_videos_2026-02-18.json

    # Dry-run (keine DB-Änderungen)
    python scripts/import_lexmark_videos.py --json data/lexmark_videos_2026-02-18.json --dry-run

    # Preview without writing
    python scripts/import_lexmark_videos.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

# Add project root so all backend imports work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.data_models import ManufacturerModel, ProductModel, ProductSeriesModel
from backend.processors.env_loader import load_all_env_files
from backend.services.database_factory import create_database_adapter

load_all_env_files(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lexmark_import")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANUFACTURER_NAME = "Lexmark"
MANUFACTURER_WEBSITE = "https://www.lexmark.com"
MANUFACTURER_COUNTRY = "US"

DEFAULT_JSON_PATH = None  # Must be provided via --json argument


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def extract_model_number(model_name: str) -> str:
    """'Lexmark B2236' → 'B2236'  (last whitespace-separated token)."""
    parts = model_name.strip().split()
    return parts[-1] if len(parts) >= 2 else model_name.strip()


def extract_series_name(model_number: str) -> str:
    """'B2236' → 'B-Series',  'MX431' → 'MX-Series',  'CS331' → 'CS-Series'."""
    match = re.match(r"^([A-Za-z]+)", model_number)
    prefix = match.group(1).upper() if match else "General"
    return f"{prefix}-Series"


def video_title_from_url(video_url: str) -> str:
    """Derive a human-readable title from a Lexmark support page URL.

    e.g. '.../clearing-paper-jam-in-the-duplex-unit.html'
         → 'Clearing Paper Jam In The Duplex Unit'
    """
    stem = Path(video_url.rstrip("/")).stem  # strip .html
    return stem.replace("-", " ").title()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def get_or_create_manufacturer(db, dry_run: bool) -> str:
    existing = await db.get_manufacturer_by_name(MANUFACTURER_NAME)
    if existing:
        mfr_id = str(existing["id"])
        logger.info("Manufacturer already exists: %s (%s)", MANUFACTURER_NAME, mfr_id)
        return mfr_id

    if dry_run:
        logger.info("[DRY RUN] Would create manufacturer: %s", MANUFACTURER_NAME)
        return "dry-run-manufacturer-id"

    mfr_id = await db.create_manufacturer(
        ManufacturerModel(
            name=MANUFACTURER_NAME,
            website=MANUFACTURER_WEBSITE,
            country=MANUFACTURER_COUNTRY,
        )
    )
    logger.info("Created manufacturer: %s (%s)", MANUFACTURER_NAME, mfr_id)
    return mfr_id


async def get_or_create_series(
    db, manufacturer_id: str, series_name: str, series_cache: dict[str, str], dry_run: bool
) -> str:
    if series_name in series_cache:
        return series_cache[series_name]

    existing = await db.get_product_series_by_name(series_name, manufacturer_id)
    if existing:
        series_id = str(existing["id"])
        series_cache[series_name] = series_id
        return series_id

    if dry_run:
        fake_id = f"dry-run-series-{series_name}"
        series_cache[series_name] = fake_id
        return fake_id

    series_id = await db.create_product_series(
        ProductSeriesModel(
            manufacturer_id=manufacturer_id,
            series_name=series_name,
            series_code=series_name.replace("-Series", ""),
        )
    )
    logger.info("Created series: %s (%s)", series_name, series_id)
    series_cache[series_name] = series_id
    return series_id


async def get_or_create_product(
    db,
    manufacturer_id: str,
    series_id: str,
    model_number: str,
    model_name_full: str,
    dry_run: bool,
) -> str:
    existing = await db.get_product_by_model(model_number, manufacturer_id)
    if existing:
        return str(existing["id"])

    if dry_run:
        return f"dry-run-product-{model_number}"

    # Strip manufacturer prefix from display name ("Lexmark B2236" → "B2236")
    display_name = model_name_full
    for prefix in ("Lexmark ", "LEXMARK "):
        if display_name.startswith(prefix):
            display_name = display_name[len(prefix) :]
            break

    product_id = await db.create_product(
        ProductModel(
            manufacturer_id=manufacturer_id,
            series_id=series_id,
            model_number=model_number,
            model_name=display_name,
            product_type="printer",
        )
    )
    logger.info("Created product: %s (%s)", display_name, product_id)
    return product_id


async def get_or_insert_video(
    db,
    video_url: str,
    title: str,
    manufacturer_id: str,
    series_id: str,
    dry_run: bool,
) -> tuple[str, bool]:
    """Return (video_id, was_newly_created).

    Uses raw asyncpg because the adapter's create_video() relies on an
    ON CONFLICT (link_id) clause which is incompatible with standalone
    videos that have no associated document link.
    """
    pool = db._ensure_pool()
    schema = db._content_schema

    async with pool.acquire() as conn:
        if dry_run:
            existing_id = await conn.fetchval(
                f"SELECT id FROM {schema}.videos WHERE video_url = $1 LIMIT 1",
                video_url,
            )
            return (str(existing_id), False) if existing_id else ("dry-run-video-id", True)

        # Atomic upsert: insert or skip on duplicate video_url
        video_id = await conn.fetchval(
            f"""
            INSERT INTO {schema}.videos
                (video_url, title, platform, manufacturer_id, series_id, metadata)
            VALUES ($1, $2, $3, $4::uuid, $5::uuid, $6::jsonb)
            ON CONFLICT (video_url) DO NOTHING
            RETURNING id
            """,
            video_url,
            title,
            "lexmark_support",
            manufacturer_id,
            series_id,
            json.dumps({"source": "lexmark_support", "needs_enrichment": True}),
        )
        if video_id:
            return str(video_id), True
        # Row already existed — fetch it
        existing_id = await conn.fetchval(
            f"SELECT id FROM {schema}.videos WHERE video_url = $1 LIMIT 1",
            video_url,
        )
        return str(existing_id), False


async def ensure_video_product_link(db, video_id: str, product_id: str, dry_run: bool) -> bool:
    """Insert into krai_content.video_products if the link doesn't already exist."""
    if dry_run:
        return True

    pool = db._ensure_pool()
    schema = db._content_schema

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            INSERT INTO {schema}.video_products (video_id, product_id)
            VALUES ($1::uuid, $2::uuid)
            ON CONFLICT (video_id, product_id) DO NOTHING
            """,
            video_id,
            product_id,
        )
        return result == "INSERT 0 1"  # True = newly inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(json_path: Path, dry_run: bool) -> None:
    logger.info("=" * 60)
    logger.info("Lexmark Video Links Import")
    if dry_run:
        logger.info("DRY RUN – no changes will be written to the database")
    logger.info("=" * 60)

    # Load JSON
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    printers = data.get("printers", [])
    logger.info("Loaded %d printer entries from %s", len(printers), json_path)

    # Connect
    db = create_database_adapter()
    await db.connect()

    try:
        manufacturer_id = await get_or_create_manufacturer(db, dry_run)

        series_cache: dict[str, str] = {}
        stats = {
            "printers_processed": 0,
            "products_created": 0,
            "videos_created": 0,
            "videos_already_existed": 0,
            "links_created": 0,
            "errors": 0,
        }

        for printer in printers:
            model_name_full = (printer.get("model_name") or "").strip()
            video_entries = printer.get("video_urls") or []

            if not model_name_full:
                logger.warning("Skipping entry without model_name")
                continue

            model_number = extract_model_number(model_name_full)
            series_name = extract_series_name(model_number)

            # Series
            series_id = await get_or_create_series(db, manufacturer_id, series_name, series_cache, dry_run)

            # Product
            before_products = stats["products_created"]
            product_id = await get_or_create_product(
                db, manufacturer_id, series_id, model_number, model_name_full, dry_run
            )
            # count only truly new products (get_or_create logs when it creates)
            # We detect "new" by checking whether the adapter logged a creation;
            # simpler: just track that we processed the model.
            stats["printers_processed"] += 1

            # Videos
            for entry in video_entries:
                video_url = (entry.get("value") or "").strip()
                if not video_url:
                    continue

                title = video_title_from_url(video_url)

                try:
                    video_id, was_created = await get_or_insert_video(
                        db, video_url, title, manufacturer_id, series_id, dry_run
                    )
                    if was_created:
                        stats["videos_created"] += 1
                    else:
                        stats["videos_already_existed"] += 1

                    new_link = await ensure_video_product_link(db, video_id, product_id, dry_run)
                    if new_link:
                        stats["links_created"] += 1

                except Exception as exc:
                    logger.error("Error processing video %s: %s", video_url, exc)
                    stats["errors"] += 1

        logger.info("=" * 60)
        logger.info("Import Summary")
        logger.info("  Printers processed    : %d", stats["printers_processed"])
        logger.info("  Videos newly inserted : %d", stats["videos_created"])
        logger.info("  Videos already in DB  : %d", stats["videos_already_existed"])
        logger.info("  video_products links  : %d new", stats["links_created"])
        logger.info("  Errors                : %d", stats["errors"])
        logger.info("=" * 60)

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Lexmark support video links from JSON into the KRAI database")
    parser.add_argument(
        "--json",
        metavar="PATH",
        type=Path,
        default=DEFAULT_JSON_PATH,
        required=True,
        help="Path to the Lexmark JSON file (e.g. data/extract-data.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be imported without writing to the database",
    )
    args = parser.parse_args()

    asyncio.run(main(args.json, args.dry_run))
