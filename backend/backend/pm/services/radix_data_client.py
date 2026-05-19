"""
Low-level HTTP client for Radix RxPlusService API.

Handles authentication, request formatting, and paginated data fetching.
Only GET requests — no mutation allowed.
"""

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class RadixDataClient:
    """HTTP client for Radix API with Bearer token authentication."""

    def __init__(self, base_url: str, bearer_token: str, language: str = "DE") -> None:
        """
        Initialize Radix API client.

        Args:
            base_url: Base URL of Radix API (e.g., https://radix.kunze-ritter.de/IM.RxPlusService.Api)
            bearer_token: JWT Bearer token from login
            language: Language code (DE, EN, etc.)
        """
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.language = language
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "RadixDataClient":
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    def _headers(self) -> dict[str, str]:
        """Build request headers with Bearer token."""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": self.language,
        }

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Execute GET request to Radix API.

        Args:
            endpoint: API endpoint (e.g., "/api/activity")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            aiohttp.ClientError: Network error
            ValueError: HTTP error status
        """
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.get(url, headers=self._headers(), params=params) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(f"Radix API error {resp.status}: {text[:500]}")
                    raise ValueError(f"HTTP {resp.status}: {text[:200]}")

                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling Radix {endpoint}: {e}")
            raise

    async def get_activities(self, filters: dict[str, Any] | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        """
        Fetch service activities (tickets).

        Args:
            filters: Query filters (id, customer, state, date range, etc.)
            limit: Maximum results (Radix may paginate)

        Returns:
            List of activity objects
        """
        params = filters or {}
        params.setdefault("limit", limit)

        logger.info(f"Fetching activities with filters: {filters}")
        response = await self.get("/api/activity", params)

        # Radix returns either a list or an object with data property
        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        logger.warning(f"Unexpected activity response format: {type(response)}")
        return []

    async def get_activity_by_id(self, activity_id: str) -> dict[str, Any]:
        """
        Fetch single activity by ID.

        Args:
            activity_id: Radix activity ID

        Returns:
            Activity object
        """
        logger.info(f"Fetching activity {activity_id}")
        return await self.get(f"/api/activity/{activity_id}")

    async def get_activity_spare_parts(self, activity_id: str) -> list[dict[str, Any]]:
        """
        Fetch spare parts for an activity.

        Args:
            activity_id: Radix activity ID

        Returns:
            List of spare part records
        """
        logger.info(f"Fetching spare parts for activity {activity_id}")
        response = await self.get(f"/api/activity/{activity_id}/sparepart")

        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return []

    async def get_activity_work_times(self, activity_id: str) -> list[dict[str, Any]]:
        """
        Fetch work time entries for an activity.

        Args:
            activity_id: Radix activity ID

        Returns:
            List of work time records
        """
        logger.info(f"Fetching work times for activity {activity_id}")
        response = await self.get(f"/api/activity/{activity_id}/time")

        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return []

    async def get_activity_states(self) -> list[dict[str, Any]]:
        """Fetch available activity status codes."""
        logger.info("Fetching activity states")
        response = await self.get("/api/activity/states")

        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return []

    async def get_activity_types(self) -> list[dict[str, Any]]:
        """Fetch available activity type codes."""
        logger.info("Fetching activity types")
        response = await self.get("/api/activity/activitytypes")

        if isinstance(response, list):
            return response
        if isinstance(response, dict) and "data" in response:
            return response["data"]
        return []

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
