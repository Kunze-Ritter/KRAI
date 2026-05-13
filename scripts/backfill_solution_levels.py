#!/usr/bin/env python3
"""
Backfill Solution Levels
========================
Fills solution_customer_text, solution_agent_text, solution_technician_text
for all existing error_codes rows that have no technician solution yet.

Uses chunks already in the DB — no re-processing of PDFs needed.

Usage:
    python scripts/backfill_solution_levels.py
    python scripts/backfill_solution_levels.py --dry-run   # show stats only
    python scripts/backfill_solution_levels.py --limit 100  # test on 100 rows
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

from backend.utils.hp_solution_filter import extract_all_hp_levels

# ── SQL ────────────────────────────────────────────────────────────────────────

# Fetch all error codes that need backfilling (NULL or previously truncated)
# Re-run on ALL non-category rows to pick up the new full-text extraction.
_FETCH_SQL = """
SELECT
    ec.id,
    ec.error_code,
    ec.document_id,
    m.name AS manufacturer_name,
    d.manufacturer AS doc_manufacturer
FROM krai_intelligence.error_codes ec
LEFT JOIN krai_core.manufacturers m  ON ec.manufacturer_id = m.id
LEFT JOIN krai_core.documents      d ON ec.document_id = d.id
WHERE ec.is_category IS NOT TRUE
ORDER BY ec.error_code
{limit_clause}
"""

# Find the best chunk for this error code in this document.
# Prefer chunks that contain "Recommended action" — avoids TOC entries.
_CHUNK_SQL = """
SELECT c.text_chunk
FROM krai_intelligence.chunks c
WHERE c.document_id = $1
  AND c.text_chunk ILIKE $2
ORDER BY
    CASE WHEN c.text_chunk ILIKE '%Recommended action%' THEN 0
         WHEN c.text_chunk ILIKE '%action%'             THEN 1
         ELSE 2 END,
    c.page_start
LIMIT 5
"""

# Update the three solution columns
_UPDATE_SQL = """
UPDATE krai_intelligence.error_codes
SET
    solution_customer_text   = $2,
    solution_agent_text      = $3,
    solution_technician_text = $4
WHERE id = $1
"""

# Fallback: find same-document same-page chunks that have "Recommended action"
# Used when the code chunk is truncated (header only, no steps).
_ADJACENT_SQL = """
SELECT DISTINCT c2.text_chunk
FROM krai_intelligence.chunks c1
JOIN krai_intelligence.chunks c2
     ON  c2.document_id = c1.document_id
     AND c2.page_start  = c1.page_start
     AND c2.id         != c1.id
WHERE c1.document_id       = $1
  AND c1.text_chunk ILIKE  $2
  AND c2.text_chunk ILIKE '%Recommended action%'
LIMIT 5
"""


# ── Extraction helpers ─────────────────────────────────────────────────────────


def _is_toc_or_index(text: str) -> bool:
    """Return True if text looks like a table-of-contents or index entry (not real content)."""
    if not text:
        return True
    # TOC entries have many consecutive dots
    if text.count("...") > 3:
        return True
    # Very short with no sentence structure
    stripped = text.strip()
    if len(stripped) < 80 and "\n" not in stripped:
        return True
    return False


def _extract_solution_block(chunk_text: str, error_code: str) -> str:
    """
    Find the section in chunk_text that starts at error_code and return
    the full solution block (everything up to the next error code entry).
    """
    idx = chunk_text.upper().find(error_code.upper())
    if idx == -1:
        return chunk_text  # Give the whole chunk to the level extractor

    section = chunk_text[idx:]
    # Stop at the next error-code entry (e.g. "99.00.03 Upgrade…")
    stop = re.search(r"\n\d{2,3}\.\d{2}[\.\d]*\s+\S", section[len(error_code) :])
    if stop:
        section = section[: len(error_code) + stop.start()]
    return section.strip()


def _levels_for_manufacturer(chunk_text: str, error_code: str, manufacturer: str):
    """
    Extract the three solution levels from chunk_text for a given manufacturer.

    HP: use the 3-level extractor.
    Others: put everything into technician_text (flat format).
    """
    block = _extract_solution_block(chunk_text, error_code)
    levels = extract_all_hp_levels(block)

    # When the error code is mentioned at the END of the solution (e.g. in a
    # combined header "13.60.A1, 13.60.A2 or 13.60.A3 Paper stay jam"),
    # _extract_solution_block starts after the code and finds nothing.
    # Fall back to the full chunk in that case.
    if not any(levels.values()):
        levels = extract_all_hp_levels(chunk_text)

    return levels


# ── Main ───────────────────────────────────────────────────────────────────────


async def main(dry_run: bool = False, limit: int = 0):
    db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: POSTGRES_URL not set in environment")
        sys.exit(1)

    # asyncpg needs postgresql:// not postgres://
    db_url = db_url.replace("postgres://", "postgresql://", 1)

    print("Connecting to DB…")
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=8)

    limit_clause = f"LIMIT {limit}" if limit else ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_FETCH_SQL.format(limit_clause=limit_clause))

    total = len(rows)
    print(f"Found {total} error_code rows needing backfill{f' (limited to {limit})' if limit else ''}")

    if dry_run:
        print("DRY RUN — no DB writes")

    updated = 0
    skipped = 0
    no_chunk = 0

    for i, row in enumerate(rows, 1):
        ec_id = row["id"]
        code = row["error_code"]
        doc_id = row["document_id"]
        mfr_name = row["manufacturer_name"] or row["doc_manufacturer"] or ""

        # Find matching chunk(s)
        async with pool.acquire() as conn:
            chunks = await conn.fetch(_CHUNK_SQL, doc_id, f"%{code}%")

        if not chunks:
            no_chunk += 1
            if i % 500 == 0 or i == total:
                print(f"  [{i}/{total}] no chunks found for {code} (doc {str(doc_id)[:8]}…)")
            continue

        # Pick the chunk with the most solution-related content
        best_chunk = None
        best_levels = None
        for cr in chunks:
            levels = _levels_for_manufacturer(cr["text_chunk"], code, mfr_name)
            tech = levels.get("technician") or ""
            if levels["technician"] and not _is_toc_or_index(tech):
                if best_levels is None or len(tech) > len(best_levels.get("technician") or ""):
                    best_chunk = cr["text_chunk"]
                    best_levels = levels

        if best_levels is None:
            # Second pass: some chunks are truncated — the PDF chunker split the
            # error-code header and solution steps into separate chunks on the same
            # page.  Concatenate the code-chunk with each adjacent same-page chunk
            # that contains a "Recommended action" header and retry extraction.
            async with pool.acquire() as conn:
                adj_chunks = await conn.fetch(_ADJACENT_SQL, doc_id, f"%{code}%")

            for adj in adj_chunks:
                # Process adjacent chunk directly (no code context) — when the
                # error code is absent, _extract_solution_block returns the full
                # chunk, and extract_all_hp_levels picks up the last header section.
                levels = _levels_for_manufacturer(adj["text_chunk"], code, mfr_name)
                tech = levels.get("technician") or ""
                if levels["technician"] and not _is_toc_or_index(tech):
                    if best_levels is None or len(tech) > len(best_levels.get("technician") or ""):
                        best_levels = levels

        if best_levels is None:
            # Truly no usable solution content — leave NULL (better than TOC junk)
            skipped += 1
            if i % 500 == 0 or i == total:
                print(f"  [{i}/{total}] updated={updated}  no_chunk={no_chunk}  skipped={skipped}")
            continue

        if dry_run:
            updated += 1
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    _UPDATE_SQL,
                    ec_id,
                    best_levels["customer"],
                    best_levels["agent"],
                    best_levels["technician"],
                )
            updated += 1

        if i % 500 == 0 or i == total:
            print(f"  [{i}/{total}] updated={updated}  no_chunk={no_chunk}  skipped={skipped}")

    await pool.close()
    print(f"\nDone.  Updated={updated}  No-chunk={no_chunk}  Skipped={skipped}  Total={total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill solution_*_text columns from chunks")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing to DB")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N rows (0=all)")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
