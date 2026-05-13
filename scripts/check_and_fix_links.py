#!/usr/bin/env python3
"""
Link Checker & Fixer Script
============================
Checks links for validity and attempts to fix broken links.

Features:
- HTTP status check (200, 404, etc.)
- Multiline link detection and fixing
- URL encoding fixes
- Redirect following
- Batch processing with rate limiting
- Auto-update database with fixed links

Usage:
    python scripts/check_and_fix_links.py [--check-only] [--limit 10]

Options:
    --check-only    Only check links, don't fix them
    --limit N       Check only N links (default: all)
    --inactive      Also check inactive links
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None  # Fallback

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Database adapter will be injected
db_adapter = None

# Import get_pool for async PostgreSQL connections
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from services.db_pool import get_pool


class LinkChecker:
    """Checks and fixes broken links"""

    def __init__(self, check_only: bool = False):
        self.check_only = check_only
        # Use longer timeout for slow servers and redirect chains
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),  # 30s total, 10s connect
            follow_redirects=True,
            max_redirects=10,  # Allow up to 10 redirects
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )

        # Statistics
        self.checked_count = 0
        self.valid_count = 0
        self.broken_count = 0
        self.fixed_count = 0
        self.error_count = 0

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    def clean_url(self, url: str) -> str:
        """
        Clean URL by removing common trailing characters from PDF extraction
        Examples:
        - https://example.com. → https://example.com
        - https://example.com, → https://example.com
        - https://example.com) → https://example.com
        """
        url = url.strip()

        # Remove trailing punctuation that's likely from sentence end
        while url and url[-1] in ".,;:!?)]}":
            url = url[:-1]

        return url

    def is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def fix_multiline_url(self, url: str, document_text: str = None) -> str | None:
        """
        Attempt to fix URLs that were split across lines.
        Common patterns:
        - URL ends abruptly without TLD
        - Spaces in URL (should be %20)
        - Missing protocol
        """

        # Remove whitespace
        url = url.strip()

        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            # Try https first
            fixed = f"https://{url}"
            if self.is_valid_url(fixed):
                return fixed

        # Fix common encoding issues
        # Replace spaces with %20
        if " " in url:
            fixed = url.replace(" ", "%20")
            if self.is_valid_url(fixed):
                return fixed

        # Remove line breaks
        if "\n" in url or "\r" in url:
            fixed = url.replace("\n", "").replace("\r", "")
            if self.is_valid_url(fixed):
                return fixed

        return None

    def try_common_fixes(self, url: str) -> list[str]:
        """Generate list of potential fixes for a broken URL"""
        fixes = []

        # Original
        fixes.append(url)

        # Add/change protocol
        if url.startswith("http://"):
            fixes.append(url.replace("http://", "https://"))
        elif url.startswith("https://"):
            fixes.append(url.replace("https://", "http://"))
        else:
            fixes.append(f"https://{url}")
            fixes.append(f"http://{url}")

        # Remove trailing slashes or add them
        if url.endswith("/"):
            fixes.append(url.rstrip("/"))
        else:
            fixes.append(f"{url}/")

        # URL decode and re-encode
        try:
            decoded = unquote(url)
            if decoded != url:
                fixes.append(decoded)
        except:
            pass

        # Remove www or add it
        parsed = urlparse(url)
        if parsed.netloc.startswith("www."):
            fixed = url.replace("www.", "", 1)
            fixes.append(fixed)
        else:
            fixed = url.replace("://", "://www.", 1)
            fixes.append(fixed)

        # Remove duplicates while preserving order
        seen = set()
        unique_fixes = []
        for fix in fixes:
            if fix not in seen and self.is_valid_url(fix):
                seen.add(fix)
                unique_fixes.append(fix)

        return unique_fixes

    async def check_url(self, url: str) -> tuple[int, str, str | None]:
        """
        Check if URL is accessible.
        Returns: (status_code, status_text, final_url)

        Note: HEAD requests are faster but some servers don't support them or
        handle redirects differently. We try HEAD first, then fall back to GET.
        """
        if not self.is_valid_url(url):
            return (0, "Invalid URL", None)

        # Try HEAD first (faster, less bandwidth)
        try:
            response = await self.http_client.head(url, follow_redirects=True)

            # Some servers return 405 (Method Not Allowed) for HEAD
            # or other error codes that might work with GET
            if response.status_code == 405 or (400 <= response.status_code < 500 and response.status_code != 404):
                # Fallback to GET
                logger.debug(f"HEAD failed with {response.status_code}, trying GET...")
                response = await self.http_client.get(url, follow_redirects=True)

            # Return final URL after redirects
            final_url_str = str(response.url)
            # Only return final_url if it's different (redirect happened)
            final_url = final_url_str if final_url_str != url else None

            # Log redirect info
            if final_url and response.status_code in [200, 201, 202, 203, 204]:
                logger.debug(f"Followed redirect: {url} → {final_url}")

            return (response.status_code, "OK" if response.is_success else "Error", final_url)

        except httpx.HTTPStatusError as e:
            # For 3xx redirects that raise errors, try GET
            if 300 <= e.response.status_code < 400:
                try:
                    response = await self.http_client.get(url, follow_redirects=True)
                    final_url = str(response.url) if response.url != url else None
                    return (response.status_code, "OK" if response.is_success else "Error", final_url)
                except:
                    pass
            return (e.response.status_code, str(e), None)
        except httpx.ConnectError:
            return (0, "Connection failed", None)
        except httpx.TimeoutException:
            # On timeout, try GET as a last resort (some servers ignore HEAD)
            logger.debug("HEAD timeout, trying GET with longer timeout...")
            try:
                response = await self.http_client.get(url, follow_redirects=True)
                final_url_str = str(response.url)
                final_url = final_url_str if final_url_str != url else None
                return (response.status_code, "OK" if response.is_success else "Error", final_url)
            except:
                return (0, "Timeout", None)
        except Exception as e:
            return (0, str(e), None)

    async def find_working_url(self, original_url: str) -> tuple[str, int, str] | None:
        """
        Try to find a working version of the URL.
        Returns: (working_url, status_code, method) or None
        """

        # First check original
        status, msg, final_url = await self.check_url(original_url)
        if 200 <= status < 400:
            return (final_url or original_url, status, "original")

        # Try common fixes
        fixes = self.try_common_fixes(original_url)

        for i, fixed_url in enumerate(fixes[1:], 1):  # Skip first (original)
            status, msg, final_url = await self.check_url(fixed_url)
            if 200 <= status < 400:
                logger.info(f"   ✅ Found working URL: {fixed_url}")
                return (final_url or fixed_url, status, f"fix_{i}")

            # Rate limiting
            await asyncio.sleep(0.2)

        return None

    async def check_and_fix_link(self, link: dict[str, Any]) -> dict[str, Any]:
        """Check a link and attempt to fix if broken"""
        url = link["url"]
        link_id = link["id"]

        # Clean URL (remove trailing punctuation from PDF extraction)
        url_cleaned = self.clean_url(url)
        if url_cleaned != url:
            logger.info(f"\n🔗 Checking: {url[:80]}...")
            logger.info(f"   🧹 Cleaned: {url_cleaned[:80]}...")
            url = url_cleaned
        else:
            logger.info(f"\n🔗 Checking: {url[:80]}...")

        result = {
            "id": link_id,
            "original_url": link["url"],  # Store ORIGINAL (with trailing dot)
            "status": "unknown",
            "status_code": 0,
            "fixed_url": url if url != link["url"] else None,  # Mark as fixed if cleaned
            "needs_update": url != link["url"],  # Update needed if cleaned
            "error": None,
        }

        try:
            # Check current URL
            status, msg, final_url = await self.check_url(url)
            result["status_code"] = status

            if 200 <= status < 400:
                # Link is working
                # Check if it was auto-fixed by cleaning
                if result["fixed_url"]:
                    result["status"] = "fixed"
                    logger.info(f"   ✅ Working after cleaning (Status: {status})")
                    self.fixed_count += 1
                else:
                    result["status"] = "working"
                    logger.info(f"   ✅ Working (Status: {status})")
                    self.valid_count += 1

                # Check if redirected
                if final_url and final_url != url:
                    logger.info(f"   🔀 Redirects to: {final_url}")
                    result["fixed_url"] = final_url
                    result["needs_update"] = True
                    if result["status"] == "working":
                        result["status"] = "fixed"
                        self.valid_count -= 1
                        self.fixed_count += 1

            else:
                # Link is broken
                result["status"] = "broken"
                logger.warning(f"   ❌ Broken (Status: {status}, {msg})")
                self.broken_count += 1

                if not self.check_only:
                    # Try to fix
                    logger.info("   🔧 Attempting to fix...")
                    working = await self.find_working_url(url)

                    if working:
                        fixed_url, new_status, method = working
                        result["fixed_url"] = fixed_url
                        result["status_code"] = new_status
                        result["status"] = "fixed"
                        result["needs_update"] = True
                        logger.info(f"   ✅ Fixed! New URL: {fixed_url}")
                        self.fixed_count += 1
                    else:
                        logger.warning("   ⚠️  Could not fix link")

            self.checked_count += 1

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"   ❌ Error: {e}")
            self.error_count += 1

        return result

    async def update_link(self, link_id: str, new_url: str, old_url: str):
        """Update link in database"""
        try:
            import json

            pool = await get_pool()
            async with pool.acquire() as conn:
                metadata = {
                    "fixed_at": datetime.utcnow().isoformat(),
                    "original_url": old_url,
                    "fixed_by": "link_checker_script",
                }
                await conn.execute(
                    "UPDATE krai_content.links SET url = $1, metadata = $2 WHERE id = $3",
                    new_url,
                    json.dumps(metadata),
                    link_id,
                )

            logger.info("   💾 Database updated")

        except Exception as e:
            logger.error(f"   ❌ Failed to update database: {e}")

    async def deactivate_link(self, link_id: str):
        """Mark link as inactive"""
        try:
            import json

            pool = await get_pool()
            async with pool.acquire() as conn:
                metadata = {"deactivated_at": datetime.utcnow().isoformat(), "reason": "broken_link_404"}
                await conn.execute(
                    "UPDATE krai_content.links SET is_active = $1, metadata = $2 WHERE id = $3",
                    False,
                    json.dumps(metadata),
                    link_id,
                )

            logger.info("   💾 Link marked as inactive")

        except Exception as e:
            logger.error(f"   ❌ Failed to deactivate link: {e}")

    async def process_links(self, limit: int | None = None, check_inactive: bool = False):
        """Process all links"""
        logger.info("🔍 Finding links to check...")

        try:
            # Query links
            pool = await get_pool()
            async with pool.acquire() as conn:
                if check_inactive:
                    # Get all links
                    query = "SELECT id, url, link_type, is_active FROM krai_content.links"
                    if limit:
                        query += f" LIMIT {limit}"
                    links = await conn.fetch(query)
                else:
                    # Include links where is_active is NULL or TRUE (exclude only FALSE)
                    query = "SELECT id, url, link_type, is_active FROM krai_content.links WHERE (is_active IS NULL OR is_active = true)"
                    if limit:
                        query += f" LIMIT {limit}"
                    links = await conn.fetch(query)

            logger.info(f"📊 Query returned {len(links) if links else 0} links")

            if not links:
                logger.info("✅ No links found to check!")
                logger.info("ℹ️  Try: --inactive flag to check all links")
                return

            logger.info(f"🔗 Found {len(links)} links to check")

            results = []

            for i, link in enumerate(links, 1):
                logger.info(f"\n{'='*80}")
                logger.info(f"[{i}/{len(links)}]")

                result = await self.check_and_fix_link(link)
                results.append(result)

                # Update database if needed
                if result["needs_update"] and not self.check_only:
                    await self.update_link(result["id"], result["fixed_url"], result["original_url"])

                # Deactivate if permanently broken
                if result["status"] == "broken" and result["status_code"] == 404:
                    if not self.check_only:
                        await self.deactivate_link(result["id"])

                # Rate limiting
                await asyncio.sleep(0.5)

            # Summary
            logger.info(f"\n{'='*80}")
            logger.info("📊 SUMMARY")
            logger.info(f"{'='*80}")
            logger.info(f"   Total checked: {self.checked_count}")
            logger.info(f"   ✅ Working: {self.valid_count}")
            logger.info(f"   ❌ Broken: {self.broken_count}")
            logger.info(f"   🔧 Fixed: {self.fixed_count}")
            logger.info(f"   ⚠️  Errors: {self.error_count}")
            logger.info(f"{'='*80}")

            # Show broken links
            broken = [r for r in results if r["status"] == "broken"]
            if broken:
                logger.info(f"\n❌ BROKEN LINKS ({len(broken)}):")
                for r in broken:
                    logger.info(f"   [{r['status_code']}] {r['original_url']}")

        except Exception as e:
            logger.error(f"Error processing links: {e}")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Check and fix broken links")
    parser.add_argument("--check-only", action="store_true", help="Only check, do not fix")
    parser.add_argument("--limit", type=int, help="Limit number of links to check")
    parser.add_argument("--inactive", action="store_true", help="Also check inactive links")
    args = parser.parse_args()

    if args.check_only:
        logger.info("ℹ️  Running in CHECK ONLY mode (no fixes will be applied)")

    checker = LinkChecker(check_only=args.check_only)

    try:
        await checker.process_links(limit=args.limit, check_inactive=args.inactive)
    finally:
        await checker.close()


if __name__ == "__main__":
    asyncio.run(main())
