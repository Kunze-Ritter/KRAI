"""
Video Metadata Enrichment Module
Extracts metadata from YouTube, Vimeo, Brightcove and direct video URLs.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

logger = logging.getLogger(__name__)


class VideoEnricher:
    """Video enricher for YouTube, Vimeo, Brightcove metadata extraction."""

    def __init__(self, database_adapter=None):
        self.database_adapter = database_adapter
        self.youtube_api_key = None

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if self.youtube_api_key and self.youtube_api_key != "your_youtube_api_key_here":
            logger.info("YouTube API key configured")
        else:
            logger.warning("YouTube API key not configured - limited YouTube functionality")

        self.brightcove_account_id = os.getenv("BRIGHTCOVE_ACCOUNT_ID")
        self.brightcove_client_id = os.getenv("BRIGHTCOVE_CLIENT_ID")
        self.brightcove_client_secret = os.getenv("BRIGHTCOVE_CLIENT_SECRET")
        self.brightcove_api_timeout = int(os.getenv("BRIGHTCOVE_API_TIMEOUT", "30"))
        self.brightcove_rate_limit_delay = float(os.getenv("BRIGHTCOVE_RATE_LIMIT_DELAY", "1.0"))
        self._brightcove_api_calls = 0
        self._brightcove_access_token: str | None = None
        self._brightcove_token_expires_at: datetime | None = None

        if not self.has_brightcove_credentials():
            logger.warning("Brightcove credentials not configured - videos will remain with needs_enrichment=true")

        logger.info("VideoEnricher initialized - YouTube, Vimeo, Brightcove support ready")

    def has_brightcove_credentials(self) -> bool:
        return bool(self.brightcove_account_id and self.brightcove_client_id and self.brightcove_client_secret)

    def detect_platform(self, url: str) -> str:
        """Detect video platform from URL."""
        domain = urlparse(url).netloc.lower()

        if "youtube.com" in domain or "youtu.be" in domain:
            return "youtube"
        if "vimeo.com" in domain:
            return "vimeo"
        if "brightcove" in domain or "bcov" in domain:
            return "brightcove"
        if any(ext in url.lower() for ext in [".mp4", ".webm", ".mov", ".avi", ".mkv"]):
            return "direct"
        return "unknown"

    def extract_youtube_id(self, url: str) -> str | None:
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_vimeo_id(self, url: str) -> str | None:
        patterns = [r"vimeo\.com/(\d+)", r"player\.vimeo\.com/video/(\d+)"]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def extract_brightcove_ids(self, url: str) -> tuple[str | None, str | None]:
        """Extract account_id and video_id from Brightcove URL patterns."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        account_id = self.brightcove_account_id
        video_id = None

        if query.get("videoId"):
            video_id = query["videoId"][0]

        # players.brightcove.net/{account_id}/{player_id}_default/index.html?videoId=...
        m = re.search(r"players\.brightcove\.net/([^/]+)/", url)
        if m:
            account_id = m.group(1)

        patterns = [
            r"[?&]videoId=([^&]+)",
            r"[?&]bctid=([^&]+)",
            r"brightcove\.com/services/viewer/htmlFederated\?.*\bbctid=([^&]+)",
            r"bcove\.video/([^/?&#]+)",
            r"brightcove\.[^/]+/.*/video/([^/?&#]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = video_id or match.group(1)
                break

        return account_id, video_id

    async def get_brightcove_access_token(self, force_refresh: bool = False) -> str | None:
        """Get Brightcove OAuth access token using client credentials flow."""
        if not self.has_brightcove_credentials():
            return None

        now = datetime.utcnow()
        if (
            not force_refresh
            and self._brightcove_access_token
            and self._brightcove_token_expires_at
            and now < self._brightcove_token_expires_at - timedelta(seconds=60)
        ):
            return self._brightcove_access_token

        token_url = "https://oauth.brightcove.com/v4/access_token"
        payload = {
            "grant_type": "client_credentials",
            "account_id": self.brightcove_account_id,
        }

        delay = self.brightcove_rate_limit_delay
        for attempt in range(4):
            try:
                response = self.session.post(
                    token_url,
                    data=payload,
                    auth=(self.brightcove_client_id, self.brightcove_client_secret),
                    timeout=self.brightcove_api_timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    self._brightcove_access_token = data.get("access_token")
                    expires_in = int(data.get("expires_in", 300))
                    self._brightcove_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    return self._brightcove_access_token

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_for = float(retry_after) if retry_after else delay
                    await asyncio.sleep(wait_for)
                    delay *= 2
                    continue

                logger.error(
                    "Brightcove token request failed with status %s: %s",
                    response.status_code,
                    response.text,
                )
                return None
            except Exception as exc:
                logger.error("Brightcove token request error on attempt %s: %s", attempt + 1, exc)
                if attempt < 3:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    return None

        return None

    async def _brightcove_get_with_retry(self, url: str, headers: dict[str, str]) -> requests.Response:
        """GET helper with exponential backoff and 429 handling."""
        delay = self.brightcove_rate_limit_delay
        last_response: requests.Response | None = None

        for attempt in range(4):
            self._brightcove_api_calls += 1
            if self.brightcove_rate_limit_delay > 0:
                await asyncio.sleep(self.brightcove_rate_limit_delay)

            response = self.session.get(url, headers=headers, timeout=self.brightcove_api_timeout)
            last_response = response

            if response.status_code == 200:
                return response

            if response.status_code == 401 and attempt == 0:
                token = await self.get_brightcove_access_token(force_refresh=True)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_for = float(retry_after) if retry_after else delay
                await asyncio.sleep(wait_for)
                delay *= 2
                continue

            if response.status_code >= 500 and attempt < 3:
                await asyncio.sleep(delay)
                delay *= 2
                continue

            break

        if last_response is None:
            raise RuntimeError("Brightcove request failed before receiving response")
        return last_response

    async def enrich_youtube_video(self, video_id: str) -> dict[str, Any]:
        metadata = {
            "platform": "youtube",
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": None,
            "description": None,
            "duration": None,
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            "channel_title": None,
            "published_at": None,
            "view_count": None,
            "metadata": {},
            "tags": [],
            "enrichment_error": None,
        }

        if self.youtube_api_key:
            try:
                api_url = "https://www.googleapis.com/youtube/v3/videos"
                params = {
                    "part": "snippet,contentDetails,statistics",
                    "id": video_id,
                    "key": self.youtube_api_key,
                }

                response = self.session.get(api_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        item = data["items"][0]
                        snippet = item.get("snippet", {})
                        content_details = item.get("contentDetails", {})
                        statistics = item.get("statistics", {})

                        metadata.update(
                            {
                                "title": snippet.get("title"),
                                "description": snippet.get("description"),
                                "channel_title": snippet.get("channelTitle"),
                                "published_at": snippet.get("publishedAt"),
                                "view_count": statistics.get("viewCount"),
                                "tags": snippet.get("tags", []) or [],
                                "metadata": {
                                    "api_enriched": True,
                                    "tags": snippet.get("tags", []),
                                    "category_id": snippet.get("categoryId"),
                                    "duration_iso": content_details.get("duration"),
                                    "definition": content_details.get("definition"),
                                    "caption": content_details.get("caption"),
                                },
                            }
                        )

                        duration_str = content_details.get("duration", "")
                        if duration_str:
                            metadata["duration"] = self._parse_youtube_duration(duration_str)
                else:
                    logger.warning("YouTube API error: %s", response.status_code)
            except Exception as exc:
                logger.error("YouTube API request failed: %s", exc)

        if not metadata["title"]:
            try:
                oembed_url = "https://www.youtube.com/oembed"
                params = {"url": metadata["url"], "format": "json"}

                response = self.session.get(oembed_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    metadata.update(
                        {
                            "title": data.get("title"),
                            "thumbnail_url": data.get("thumbnail_url"),
                            "metadata": {**metadata["metadata"], "oembed_enriched": True},
                        }
                    )
            except Exception as exc:
                logger.error("YouTube oEmbed fallback failed: %s", exc)

        return metadata

    async def enrich_vimeo_video(self, video_id: str) -> dict[str, Any]:
        metadata = {
            "platform": "vimeo",
            "video_id": video_id,
            "url": f"https://vimeo.com/{video_id}",
            "title": None,
            "description": None,
            "duration": None,
            "thumbnail_url": None,
            "channel_title": None,
            "published_at": None,
            "metadata": {},
            "tags": [],
            "enrichment_error": None,
        }

        try:
            response = self.session.get(
                "https://vimeo.com/api/oembed.json",
                params={"url": metadata["url"]},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                metadata.update(
                    {
                        "title": data.get("title"),
                        "description": data.get("description"),
                        "duration": data.get("duration"),
                        "thumbnail_url": data.get("thumbnail_url"),
                        "metadata": {
                            "oembed_enriched": True,
                            "author_url": data.get("author_url"),
                            "width": data.get("width"),
                            "height": data.get("height"),
                        },
                    }
                )
        except Exception as exc:
            logger.error("Vimeo enrichment failed: %s", exc)

        return metadata

    async def enrich_brightcove_video(self, url: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "platform": "brightcove",
            "video_id": None,
            "url": url,
            "title": None,
            "description": None,
            "duration": None,
            "thumbnail_url": None,
            "channel_title": None,
            "published_at": None,
            "metadata": {"needs_enrichment": True},
            "tags": [],
            "enrichment_error": None,
        }

        account_id, video_id = self.extract_brightcove_ids(url)
        metadata["video_id"] = video_id
        metadata["metadata"]["account_id"] = account_id

        if not video_id:
            metadata["metadata"]["id_extraction_failed"] = True
            return metadata

        if not self.has_brightcove_credentials():
            # Try public oEmbed endpoint — works for publicly accessible Brightcove videos
            # without API credentials.
            oembed_result = await self._try_brightcove_oembed(url)
            if oembed_result:
                metadata.update(oembed_result)
                metadata["metadata"]["oembed_enriched"] = True
                metadata["metadata"]["needs_enrichment"] = False
                metadata["metadata"].pop("credentials_missing", None)
            else:
                metadata["metadata"]["credentials_missing"] = True
            return metadata

        token = await self.get_brightcove_access_token()
        if not token:
            metadata["enrichment_error"] = "Failed to obtain Brightcove OAuth token"
            metadata["metadata"]["api_enriched"] = False
            return metadata

        endpoint = f"https://cms.api.brightcove.com/v1/accounts/{account_id}/videos/{video_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            response = await self._brightcove_get_with_retry(endpoint, headers)
            if response.status_code == 200:
                data = response.json()

                duration_value = data.get("duration")
                duration_seconds = None
                if isinstance(duration_value, (int, float)):
                    duration_seconds = int(duration_value / 1000) if duration_value > 10000 else int(duration_value)

                images = data.get("images") or {}
                poster = images.get("poster") or {}
                thumbnail_url = poster.get("src")
                if not thumbnail_url:
                    sources = poster.get("sources") or []
                    if sources and isinstance(sources[0], dict):
                        thumbnail_url = sources[0].get("src")

                metadata.update(
                    {
                        "title": data.get("name"),
                        "description": data.get("description"),
                        "duration": duration_seconds,
                        "thumbnail_url": thumbnail_url,
                        "published_at": data.get("published_at"),
                        "tags": data.get("tags") or [],
                        "metadata": {
                            **metadata["metadata"],
                            "api_enriched": True,
                            "needs_enrichment": False,
                            "updated_at": datetime.utcnow().isoformat(),
                            "api_call_count": self._brightcove_api_calls,
                        },
                    }
                )
                return metadata

            metadata["enrichment_error"] = f"Brightcove CMS API error {response.status_code}: {response.text[:200]}"
            metadata["metadata"]["api_enriched"] = False
            metadata["metadata"]["needs_enrichment"] = True
            return metadata

        except Exception as exc:
            metadata["enrichment_error"] = f"Brightcove enrichment failed: {exc}"
            metadata["metadata"]["api_enriched"] = False
            metadata["metadata"]["needs_enrichment"] = True
            return metadata

    async def _try_brightcove_oembed(self, url: str) -> dict[str, Any] | None:
        """Attempt to fetch metadata via Brightcove's public oEmbed endpoint.

        Works for publicly accessible videos without API credentials.
        Returns a partial metadata dict on success, None on failure.
        """
        try:
            oembed_url = "https://players.brightcove.net/oembed"
            response = self.session.get(oembed_url, params={"url": url}, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            return {
                "title": data.get("title"),
                "description": data.get("description") or data.get("author_name"),
                "thumbnail_url": data.get("thumbnail_url"),
                "channel_title": data.get("author_name"),
                "metadata": {
                    "width": data.get("width"),
                    "height": data.get("height"),
                },
            }
        except Exception as exc:
            logger.debug("Brightcove oEmbed request failed: %s", exc)
            return None

    async def enrich_direct_video(self, url: str) -> dict[str, Any]:
        metadata = {
            "platform": "direct",
            "video_id": None,
            "url": url,
            "title": self._extract_title_from_url(url),
            "description": f"Direct video file: {url}",
            "duration": None,
            "thumbnail_url": None,
            "channel_title": None,
            "published_at": None,
            "metadata": {
                "direct_video": True,
                "file_extension": self._get_file_extension(url),
            },
            "tags": [],
            "enrichment_error": None,
        }

        try:
            from backend.utils.model_detector import extract_models_from_text

            if metadata["title"]:
                models = extract_models_from_text(metadata["title"])
                if models:
                    metadata["models"] = models
                    metadata["metadata"]["models_extracted"] = True
        except Exception as exc:
            logger.debug("Model extraction failed: %s", exc)

        return metadata

    def _extract_title_from_url(self, url: str) -> str:
        filename = url.split("/")[-1]
        if "." in filename:
            filename = ".".join(filename.split(".")[:-1])
        title = re.sub(r"[-_]", " ", filename).title()
        return title or "Unknown Video"

    def _get_file_extension(self, url: str) -> str:
        path = urlparse(url).path
        if "." in path:
            return path.split(".")[-1].lower()
        return "unknown"

    def _parse_youtube_duration(self, duration_str: str) -> int | None:
        try:
            match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = int(match.group(3) or 0)
                return hours * 3600 + minutes * 60 + seconds
        except Exception as exc:
            logger.error("Failed to parse YouTube duration: %s", exc)
        return None

    async def enrich_video(self, video_url: str, **kwargs) -> dict[str, Any]:
        logger.info("Enriching video: %s", video_url)
        platform = self.detect_platform(video_url)

        if platform == "youtube":
            video_id = self.extract_youtube_id(video_url)
            if not video_id:
                return {"error": "Invalid YouTube URL", "url": video_url}
            metadata = await self.enrich_youtube_video(video_id)
        elif platform == "vimeo":
            video_id = self.extract_vimeo_id(video_url)
            if not video_id:
                return {"error": "Invalid Vimeo URL", "url": video_url}
            metadata = await self.enrich_vimeo_video(video_id)
        elif platform == "brightcove":
            metadata = await self.enrich_brightcove_video(video_url)
        elif platform == "direct":
            metadata = await self.enrich_direct_video(video_url)
        else:
            return {"error": f"Unsupported platform: {platform}", "url": video_url}

        if kwargs.get("document_id"):
            metadata["document_id"] = kwargs["document_id"]
        if kwargs.get("manufacturer_id"):
            metadata["manufacturer_id"] = kwargs["manufacturer_id"]

        return metadata

    async def batch_enrich(self, video_urls: list[str], **kwargs) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for url in video_urls:
            try:
                result = await self.enrich_video(url, **kwargs)
                if "error" in result:
                    errors.append(result)
                else:
                    results.append(result)
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)})

        return {
            "results": results,
            "errors": errors,
            "total": len(video_urls),
            "successful": len(results),
            "failed": len(errors),
        }
