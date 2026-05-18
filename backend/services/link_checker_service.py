"""
Link Checker Service
Wraps the link checker script for use in the API
"""

import logging
import sys
from pathlib import Path
from typing import Any

# Add scripts directory to path (resolve to /app/scripts inside container)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# DISABLED: check_and_fix_links uses old database client which has been removed
# from check_and_fix_links import LinkChecker

logger = logging.getLogger(__name__)


class LinkCheckerService:
    """Service for checking and fixing broken links"""

    def __init__(self):
        """Initialize link checker service"""
        self.checker = None
        logger.info("✅ Link Checker Service initialized")

    async def check_links(
        self, limit: int | None = None, check_only: bool = True, check_inactive: bool = False
    ) -> dict[str, Any]:
        """
        Check links for validity and optionally fix broken ones

        DISABLED: This service used old database client which has been removed.
        Now using PostgreSQL via DatabaseAdapter.

        Args:
            limit: Maximum number of links to check
            check_only: Only check without fixing (default: True)
            check_inactive: Also check inactive links (default: False)

        Returns:
            Dictionary with check results
        """
        logger.warning("Link checker service is disabled (old database client dependency removed)")
        return {
            "checked": 0,
            "working": 0,
            "broken": 0,
            "fixed": 0,
            "errors": 0,
            "message": "Link checker service disabled - requires migration to PostgreSQL",
        }

    async def health_check(self) -> dict[str, Any]:
        """Health check for link checker service"""
        try:
            return {
                "status": "healthy",
                "features": {
                    "url_cleaning": True,
                    "redirect_following": True,
                    "auto_fixing": True,
                    "common_fixes": ["https/http", "www", "trailing_slash", "url_encoding"],
                },
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
