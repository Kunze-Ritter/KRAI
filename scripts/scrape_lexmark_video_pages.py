#!/usr/bin/env python3
"""
Lexmark Video Page Scraper
===========================

Fetches each Lexmark support video page and extracts:
  - Direct MP4 URL  (stored in metadata->direct_video_url)
  - Poster / thumbnail URL
  - Video title and description (from the page)
  - Subtitle tracks  (stored in metadata->tracks)
    e.g. [{"src": "...en.vtt", "srclang": "en", "label": "English", "kind": "subtitles"}]

Results are written back to krai_content.videos via:
  - thumbnail_url  (updated if empty)
  - title          (updated if slug-derived, overwritten with real page title)
  - description    (updated)
  - metadata       merged with direct_video_url, tracks, scraped_at
  - enriched_at    set to NOW() on success

Pages where the <source src> is loaded by JavaScript (dynamic) are marked
with metadata->scrape_status = "js_dynamic" so they can be retried later
with a browser-based scraper (Playwright).

Usage:
    # Scrape all un-enriched Lexmark videos (default: 10 concurrent)
    python scripts/scrape_lexmark_video_pages.py

    # Limit to first 100, 5 concurrent workers
    python scripts/scrape_lexmark_video_pages.py --limit 100 --concurrency 5

    # Re-scrape even already enriched videos
    python scripts/scrape_lexmark_video_pages.py --force

    # Dry-run: show what would be fetched, no DB writes
    python scripts/scrape_lexmark_video_pages.py --dry-run --limit 10
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.database_factory import create_database_adapter

load_all_env_files(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lexmark_scraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEXMARK_ID = "93974db7-e28e-4cd8-9ac9-5f2e1bdf7403"  # fallback, resolved at runtime
BASE_URL = "https://support.lexmark.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def parse_video_page(html: str, page_url: str) -> dict:
    """
    Extract video metadata from a Lexmark support video page.

    Returns a dict with keys:
        title, description, direct_video_url, thumbnail_url,
        tracks, scrape_status
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {
        "title": None,
        "description": None,
        "direct_video_url": None,
        "thumbnail_url": None,
        "tracks": [],
        "scrape_status": "ok",
    }

    # --- title from <h3 id="video-title"> ---
    title_el = soup.find("h3", id="video-title")
    if title_el and title_el.get_text(strip=True):
        result["title"] = title_el.get_text(strip=True)

    # --- description from <p id="video-description"> ---
    desc_el = soup.find("p", id="video-description")
    if desc_el and desc_el.get_text(strip=True):
        result["description"] = desc_el.get_text(strip=True)

    # --- video element ---
    video_el = soup.find("video")
    if video_el:
        # Poster / thumbnail
        poster = video_el.get("poster")
        if poster:
            result["thumbnail_url"] = urljoin(BASE_URL, poster)

        # <source src="...mp4">
        source_el = video_el.find("source", type="video/mp4")
        if source_el:
            src = source_el.get("src", "").strip()
            if src:
                result["direct_video_url"] = urljoin(BASE_URL, src)
            else:
                # src attribute empty → page loads video via JS
                result["scrape_status"] = "js_dynamic"

        # <track> elements (subtitles / captions)
        tracks = []
        for track in video_el.find_all("track"):
            track_src = track.get("src", "").strip()
            track_kind = track.get("kind", "subtitles")
            srclang = track.get("srclang", "").strip().lower()
            label = track.get("label", "").strip()
            if track_src:
                tracks.append(
                    {
                        "src": urljoin(BASE_URL, track_src),
                        "kind": track_kind,
                        "srclang": srclang,
                        "label": label,
                    }
                )
        result["tracks"] = tracks
    else:
        result["scrape_status"] = "no_video_element"

    return result


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def resolve_manufacturer_id(pool, name: str) -> str | None:
    """Look up manufacturer UUID by name (case-insensitive)."""
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT id FROM krai_core.manufacturers WHERE LOWER(name) = LOWER($1) LIMIT 1",
            name,
        )
    return str(row) if row else None


async def load_videos(pool, schema: str, manufacturer_id: str, force: bool, limit: int | None) -> list[dict]:
    """Fetch Lexmark videos that still need scraping."""
    where_enriched = "" if force else "AND (metadata->>'direct_video_url') IS NULL"
    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"""
        SELECT id, video_url, title, thumbnail_url
        FROM {schema}.videos
        WHERE manufacturer_id = $1::uuid
          {where_enriched}
        ORDER BY created_at ASC
        {limit_clause}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, manufacturer_id)
        return [dict(r) for r in rows]


async def save_result(pool, schema: str, video_id: str, scraped: dict, dry_run: bool) -> None:
    """Merge scraped data into the videos row."""
    if dry_run:
        return

    now = datetime.now(UTC)

    meta_patch = {
        "scrape_status": scraped["scrape_status"],
        "scraped_at": now.isoformat(),
    }
    if scraped["direct_video_url"]:
        meta_patch["direct_video_url"] = scraped["direct_video_url"]
    if scraped["tracks"]:
        meta_patch["tracks"] = scraped["tracks"]

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {schema}.videos
            SET
                title         = COALESCE(NULLIF($2, ''), title),
                description   = COALESCE(NULLIF($3, ''), description),
                thumbnail_url = COALESCE(NULLIF($4, ''), thumbnail_url),
                metadata      = COALESCE(metadata, '{{}}'::jsonb) || $5::jsonb,
                enriched_at   = CASE WHEN $6 THEN $7 ELSE enriched_at END,
                updated_at    = $7
            WHERE id = $1::uuid
            """,
            video_id,
            scraped["title"] or "",
            scraped["description"] or "",
            scraped["thumbnail_url"] or "",
            json.dumps(meta_patch),
            scraped["scrape_status"] == "ok",  # only set enriched_at on success
            now,
        )


# ---------------------------------------------------------------------------
# Async scraping worker
# ---------------------------------------------------------------------------


async def scrape_one(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    video: dict,
) -> dict:
    """Fetch and parse one video page. Returns merged result dict."""
    url = video.get("video_url", "")
    video_id = str(video["id"])

    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {
                        **video,
                        "scrape_status": f"http_{resp.status}",
                        "title": None,
                        "description": None,
                        "direct_video_url": None,
                        "thumbnail_url": None,
                        "tracks": [],
                    }
                html = await resp.text(encoding="utf-8", errors="replace")

            parsed = parse_video_page(html, url)
            return {**video, **parsed}

        except TimeoutError:
            return {
                **video,
                "scrape_status": "timeout",
                "title": None,
                "description": None,
                "direct_video_url": None,
                "thumbnail_url": None,
                "tracks": [],
            }
        except Exception as exc:
            logger.warning("Error scraping %s: %s", url, exc)
            return {
                **video,
                "scrape_status": f"error:{exc}",
                "title": None,
                "description": None,
                "direct_video_url": None,
                "thumbnail_url": None,
                "tracks": [],
            }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(limit: int | None, concurrency: int, force: bool, dry_run: bool) -> None:
    logger.info("=" * 60)
    logger.info("Lexmark Video Page Scraper")
    if dry_run:
        logger.info("DRY RUN – keine DB-Änderungen")
    logger.info("=" * 60)

    db = create_database_adapter()
    await db.connect()
    pool = db._ensure_pool()

    try:
        lexmark_id = await resolve_manufacturer_id(pool, "Lexmark")
        if not lexmark_id:
            logger.error("Manufacturer 'Lexmark' not found in database.")
            return

        videos = await load_videos(pool, db._content_schema, lexmark_id, force, limit)
        logger.info("Videos zu scrapen: %d", len(videos))

        stats = {"ok": 0, "js_dynamic": 0, "no_video_element": 0, "error": 0, "tracks_found": 0, "mp4_found": 0}

        semaphore = asyncio.Semaphore(concurrency)

        connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
        async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
            # Process in chunks of 50 to give periodic progress updates
            chunk_size = 50
            for chunk_start in range(0, len(videos), chunk_size):
                chunk = videos[chunk_start : chunk_start + chunk_size]
                tasks = [scrape_one(session, semaphore, v) for v in chunk]
                results = await asyncio.gather(*tasks)

                for result in results:
                    status = result.get("scrape_status", "error")
                    vid_id = str(result["id"])

                    if status == "ok":
                        stats["ok"] += 1
                        if result.get("direct_video_url"):
                            stats["mp4_found"] += 1
                        if result.get("tracks"):
                            stats["tracks_found"] += 1
                            logger.debug(
                                "Tracks found for %s: %s",
                                result.get("video_url", ""),
                                [t["srclang"] for t in result["tracks"]],
                            )
                    elif status == "js_dynamic":
                        stats["js_dynamic"] += 1
                    else:
                        stats["error"] += 1
                        logger.warning("  %-10s  %s", status, result.get("video_url", "?"))

                    await save_result(pool, db._content_schema, vid_id, result, dry_run)

                done = min(chunk_start + chunk_size, len(videos))
                logger.info(
                    "Fortschritt: %d / %d  (ok=%d, js_dynamic=%d, fehler=%d)",
                    done,
                    len(videos),
                    stats["ok"],
                    stats["js_dynamic"],
                    stats["error"],
                )

                # Small delay between chunks to be polite
                if chunk_start + chunk_size < len(videos):
                    await asyncio.sleep(0.5)

        logger.info("=" * 60)
        logger.info("Ergebnis")
        logger.info("  Erfolgreich gescrapt  : %d", stats["ok"])
        logger.info("  MP4-URL gefunden      : %d", stats["mp4_found"])
        logger.info("  Untertitel gefunden   : %d", stats["tracks_found"])
        logger.info("  JS-dynamisch (kein MP4): %d", stats["js_dynamic"])
        logger.info("  Fehler / Timeout      : %d", stats["error"])
        logger.info("=" * 60)
        if stats["js_dynamic"] > 0:
            logger.info(
                "  ℹ️  %d Seiten laden das Video per JavaScript.",
                stats["js_dynamic"],
            )
            logger.info("     Für diese wäre ein Playwright-basierter Scraper nötig.")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Lexmark support video pages for MP4 URLs and subtitles")
    parser.add_argument("--limit", type=int, default=None, help="Maximale Anzahl Videos (Standard: alle)")
    parser.add_argument("--concurrency", type=int, default=10, help="Parallele HTTP-Requests (Standard: 10)")
    parser.add_argument("--force", action="store_true", help="Bereits angereicherte Videos neu scrapen")
    parser.add_argument("--dry-run", action="store_true", help="Nur scrapen, nichts in DB schreiben")
    args = parser.parse_args()

    asyncio.run(main(args.limit, args.concurrency, args.force, args.dry_run))
