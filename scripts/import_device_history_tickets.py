#!/usr/bin/env python3
"""
Import Radix service tickets from device history export (8,071 real events).

Processes device_part_replacement_history.json containing complete device lifecycles
with parts, page counters, and dates. Replaces mock test data with real Radix records.

Usage:
    python scripts/import_device_history_tickets.py --clear-mock
    python scripts/import_device_history_tickets.py --dry-run
    python scripts/import_device_history_tickets.py --limit 500
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files  # noqa: E402
from backend.services.database_factory import create_database_adapter  # noqa: E402

load_all_env_files(PROJECT_ROOT)

logger = logging.getLogger("import_device_history_tickets")

PRINTER_MANUFACTURERS = {
    "konica minolta",
    "kyocera",
    "samsung",
    "hp",
    "hewlett packard",
    "ricoh",
    "lexmark",
    "xerox",
    "canon",
}


def extract_manufacturer_name(device_name: str) -> str | None:
    """Extract manufacturer name from device name."""
    if not device_name:
        return None

    device_lower = device_name.lower()

    mapping = {
        "konica minolta": ["konica", "minolta"],
        "kyocera": ["kyocera"],
        "samsung": ["samsung"],
        "hp": ["hewlett packard", "hp inc", " hp "],
        "ricoh": ["ricoh"],
        "lexmark": ["lexmark"],
        "xerox": ["xerox"],
        "canon": ["canon"],
    }

    for mfr_name, keywords in mapping.items():
        for keyword in keywords:
            if keyword in device_lower:
                return mfr_name

    return None


def is_printer_manufacturer(device_name: str) -> bool:
    """Check if device is from a printer/copier manufacturer."""
    device_lower = device_name.lower()
    return any(mfr in device_lower for mfr in PRINTER_MANUFACTURERS)


def _load_json(json_path: str) -> dict[str, Any] | None:
    """Load JSON data from file."""
    json_file = Path(json_path)
    if not json_file.exists():
        logger.error(f"JSON file not found: {json_path}")
        return None
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


async def import_device_history(
    json_path: str, clear_mock: bool = False, dry_run: bool = False, limit: int | None = None
) -> dict[str, Any]:
    """Import service tickets from device history export."""

    data = _load_json(json_path)
    if data is None:
        return {"imported": 0, "skipped": 0, "errors": 0, "manufacturer_breakdown": {}}

    device_histories = data.get("device_histories", {})
    logger.info(f"[LOAD] {json_path}")
    logger.info(f"[DATA] {len(device_histories)} unique devices in export\n")

    # Connect to database
    db = create_database_adapter()
    await db.connect()

    try:
        # Get manufacturers
        mfr_query = "SELECT id, name FROM krai_core.manufacturers"
        manufacturers = await db.fetch_all(mfr_query)
        mfr_map = {mfr["name"].lower(): mfr["id"] for mfr in manufacturers}

        logger.info(f"[LOOKUP] Found {len(mfr_map)} manufacturers in database\n")

        # Optionally clear mock data
        if clear_mock and not dry_run:
            logger.info("[PREP] Clearing mock test tickets...\n")
            clear_query = "DELETE FROM krai_pm.service_tickets WHERE id ~ '^MOCK'"
            await db.execute_query(clear_query)
            logger.info("[PREP] Mock data cleared\n")

        # Process and import tickets
        imported = 0
        skipped = 0
        errors = 0
        manufacturer_breakdown: dict[str, int] = {}
        event_count = 0

        for device_name, device_data in device_histories.items():
            events = device_data.get("events", [])

            for event in events:
                event_count += 1

                try:
                    # Extract key fields
                    ticket_id = event.get("ticket_id")
                    if not ticket_id:
                        skipped += 1
                        continue

                    # Check if already imported
                    check_query = "SELECT id FROM krai_pm.service_tickets WHERE id = %s"
                    existing = await db.fetch_one(check_query, [ticket_id])
                    if existing:
                        skipped += 1
                        continue

                    # Extract manufacturer
                    mfr_name = extract_manufacturer_name(device_name)
                    if not mfr_name or not is_printer_manufacturer(device_name):
                        skipped += 1
                        continue

                    # Find manufacturer ID
                    mfr_id = None
                    for db_mfr_name, db_mfr_id in mfr_map.items():
                        if mfr_name.lower() in db_mfr_name or db_mfr_name in mfr_name.lower():
                            mfr_id = db_mfr_id
                            break

                    if not mfr_id:
                        skipped += 1
                        continue

                    # Extract parts
                    parts = event.get("parts_replaced", [])
                    if not parts:
                        skipped += 1
                        continue

                    # Parse date - convert to naive UTC datetime
                    completed_date = None
                    date_str = event.get("date")
                    if date_str:
                        try:
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            # Convert to naive UTC
                            if dt.tzinfo:
                                dt = dt.replace(tzinfo=None)
                            completed_date = dt
                        except Exception:
                            pass

                    # Build metadata
                    metadata = {
                        "radix_ticket_id": ticket_id,
                        "device_name": device_name,
                        "device_serial": event.get("device_serial", ""),
                        "device_model": event.get("device_model", ""),
                        "mfr_serial": event.get("mfr_serial", ""),
                        "counters": event.get("counters", {}),
                        "part_numbers": event.get("part_numbers", []),
                    }

                    problem_description = event.get("full_description", "")

                    # Insert ticket
                    insert_query = """
                    INSERT INTO krai_pm.service_tickets (
                        source_system, source_ticket_id, manufacturer_id, problem_long,
                        problem_short, replaced_part_categories, created_at_source, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_system, source_ticket_id) DO NOTHING
                    """

                    if not dry_run:
                        await db.execute_query(
                            insert_query,
                            [
                                "radix",
                                ticket_id,
                                mfr_id,
                                problem_description[:500] or device_name,
                                device_name[:100],
                                parts,
                                completed_date,
                                json.dumps(metadata),
                            ],
                        )

                    imported += 1
                    manufacturer_breakdown[mfr_name] = manufacturer_breakdown.get(mfr_name, 0) + 1

                    # Check limit
                    if limit and imported >= limit:
                        logger.info(f"[LIMIT] Reached {limit} imported tickets")
                        break

                except Exception as e:
                    logger.debug(f"[DEBUG] Error processing event {event_count}: {e}")
                    errors += 1

                # Progress reporting
                if (event_count % 500) == 0:
                    logger.info(f"[PROGRESS] Processed {event_count} events, imported {imported}...")

            if limit and imported >= limit:
                break

        logger.info("\n[RESULTS]")
        logger.info(f"  Total events processed: {event_count}")
        logger.info(f"  Imported: {imported} tickets")
        logger.info(f"  Skipped: {skipped} records (non-printer, missing parts, or duplicate)")
        logger.info(f"  Errors: {errors} failures")

        if manufacturer_breakdown:
            logger.info("\n[BREAKDOWN] By Manufacturer:")
            for mfr, count in sorted(manufacturer_breakdown.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"   {mfr}: {count}")

        if dry_run:
            logger.info("[DRY-RUN] No changes written to database")

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "manufacturer_breakdown": manufacturer_breakdown,
        }

    finally:
        await db.disconnect()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import device history tickets from Radix export")
    parser.add_argument(
        "--json",
        default="docs/device_part_replacement_history.json",
        help="Path to device history JSON export",
    )
    parser.add_argument(
        "--clear-mock",
        action="store_true",
        help="Clear mock test tickets (MOCK*) before importing",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--limit", type=int, default=None, help="Maximum tickets to import")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    logger.info("=" * 60)
    logger.info("Device History Tickets Import (Real Radix Data)")
    logger.info("=" * 60 + "\n")

    result = await import_device_history(args.json, clear_mock=args.clear_mock, dry_run=args.dry_run, limit=args.limit)

    # Exit with error code if there were errors
    sys.exit(1 if result["errors"] > 0 and result["imported"] == 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
