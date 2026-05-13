"""Brightcove CMS API client for metadata enrichment."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import time
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class BrightcoveClient:
    """Thin Brightcove API client with OAuth, retry, and simple rate limiting."""

    VIDEO_ID_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"[?&]videoId=(\d+)", re.IGNORECASE),
        re.compile(r"/index\.html\?videoId=(\d+)", re.IGNORECASE),
        re.compile(r"/(\d{8,})/?$"),
    ]

    def __init__(
        self,
        account_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 3,
        rate_limit_per_second: float = 5.0,
    ) -> None:
        self.account_id = account_id or os.getenv("BRIGHTCOVE_ACCOUNT_ID", "").strip()
        self.client_id = client_id or os.getenv("BRIGHTCOVE_CLIENT_ID", "").strip()
        self.client_secret = client_secret or os.getenv("BRIGHTCOVE_CLIENT_SECRET", "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.rate_limit_per_second = max(rate_limit_per_second, 0.1)

        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "KRAI-Brightcove-Enrichment/1.0",
                "Accept": "application/json",
            }
        )
        self._token_value: str | None = None
        self._token_expires_at: float = 0.0
        self._last_request_at: float = 0.0

    @property
    def has_credentials(self) -> bool:
        return bool(self.account_id and self.client_id and self.client_secret)

    def extract_video_id(self, video_url: str, metadata: dict[str, Any] | None = None) -> str | None:
        """Extract Brightcove video id from metadata or URL."""
        if metadata:
            direct = metadata.get("brightcove_id") or metadata.get("video_id")
            if direct:
                return str(direct)

        for pattern in self.VIDEO_ID_PATTERNS:
            match = pattern.search(video_url or "")
            if match:
                return match.group(1)
        return None

    async def _rate_limit(self) -> None:
        min_interval = 1.0 / self.rate_limit_per_second
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

    async def _request_token(self) -> str:
        if self._token_value and time.monotonic() < self._token_expires_at:
            return self._token_value

        if not self.has_credentials:
            raise RuntimeError("Brightcove credentials are not configured")

        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        def _do_token_request() -> requests.Response:
            return self._session.post(
                "https://oauth.brightcove.com/v4/access_token",
                data={"grant_type": "client_credentials"},
                headers=headers,
                timeout=self.timeout_seconds,
            )

        response = await asyncio.to_thread(_do_token_request)
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError("Brightcove token response missing access_token")

        expires_in = int(payload.get("expires_in") or 300)
        self._token_value = str(access_token)
        self._token_expires_at = time.monotonic() + max(expires_in - 30, 30)
        return self._token_value

    async def fetch_video_metadata(self, video_id: str) -> dict[str, Any]:
        """Fetch a single Brightcove video metadata record."""
        if not self.has_credentials:
            return {"success": False, "video_id": video_id, "error": "missing_credentials"}

        token = await self._request_token()
        endpoint = f"https://cms.api.brightcove.com/v1/accounts/{self.account_id}/videos/{video_id}"
        headers = {"Authorization": f"Bearer {token}"}

        last_error = "unknown_error"
        for attempt in range(1, self.max_retries + 1):
            await self._rate_limit()

            def _do_request() -> requests.Response:
                return self._session.get(endpoint, headers=headers, timeout=self.timeout_seconds)

            try:
                response = await asyncio.to_thread(_do_request)
                self._last_request_at = time.monotonic()
                if response.status_code == 404:
                    return {"success": False, "video_id": video_id, "error": "video_not_found"}
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = f"http_{response.status_code}"
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.75 * attempt)
                        continue
                response.raise_for_status()
                payload = response.json()
                duration_ms = payload.get("duration")
                duration_seconds = int(duration_ms / 1000) if isinstance(duration_ms, int | float) else None
                return {
                    "success": True,
                    "video_id": str(payload.get("id") or video_id),
                    "title": payload.get("name"),
                    "description": payload.get("description"),
                    "duration": duration_seconds,
                    "thumbnail_url": payload.get("thumbnail")
                    or payload.get("poster")
                    or (payload.get("images") or {}).get("poster", {}).get("src"),
                    "published_at": payload.get("published_at"),
                    "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
                    "raw": payload,
                }
            except requests.RequestException as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "Brightcove request failed (video_id=%s attempt=%s/%s): %s",
                    video_id,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.75 * attempt)

        return {"success": False, "video_id": video_id, "error": last_error}

    async def batch_fetch_video_metadata(self, video_ids: list[str]) -> dict[str, Any]:
        """Fetch metadata for multiple Brightcove videos."""
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for video_id in video_ids:
            response = await self.fetch_video_metadata(video_id)
            if response.get("success"):
                results.append(response)
            else:
                errors.append(response)

        return {
            "total": len(video_ids),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }
