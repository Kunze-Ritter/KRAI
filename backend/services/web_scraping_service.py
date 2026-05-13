"""Web scraping service with Firecrawl and BeautifulSoup backends.

This module introduces the ``WebScrapingService`` abstraction that standardises
web scraping capabilities across multiple backends. Firecrawl is used as the
primary backend when available, providing JavaScript rendering, crawling, URL
mapping, and structured data extraction. A BeautifulSoup-based backend acts as a
fallback offering resilient baseline scraping capabilities when Firecrawl is not
accessible.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

try:  # pragma: no cover - optional dependency in some environments
    from firecrawl import AsyncFirecrawl
except Exception:  # pragma: no cover - imported lazily
    AsyncFirecrawl = None  # type: ignore


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class FirecrawlUnavailableError(RuntimeError):
    """Raised when Firecrawl backend is unreachable or misconfigured."""


class WebScraperBackend(ABC):
    """Abstract base class for web scraping backends."""

    backend_name: str = "abstract"

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self.logger = logging.getLogger(f"krai.scraping.{self.backend_name}")

    @abstractmethod
    async def scrape_url(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Scrape a single URL and return a normalized response dictionary."""

    @abstractmethod
    async def crawl_site(self, start_url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Crawl a website starting from ``start_url`` returning aggregated data."""

    @abstractmethod
    async def extract_structured_data(
        self,
        url: str,
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract structured data from a URL using the provided schema."""

    @abstractmethod
    async def map_urls(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Discover URLs on the target site."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return backend health metadata."""


class FirecrawlBackend(WebScraperBackend):
    """Firecrawl-backed scraping implementation."""

    backend_name = "firecrawl"

    def __init__(
        self,
        api_url: str,
        llm_provider: str = "ollama",
        model_name: str = "llama3.2:latest",
        embedding_model: str = "nomic-embed-text:latest",
        timeout: float = 30.0,
        crawl_timeout: float = 300.0,
        retries: int = 3,
        block_media: bool = True,
        allow_local_webhooks: bool = True,
        max_concurrency: int = 4,
        proxy: dict[str, str] | None = None,
        openai_api_key: str | None = None,
        mock_mode: bool = False,
    ) -> None:
        super().__init__(mock_mode=mock_mode)
        self.api_url = api_url.rstrip("/")
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.embedding_model = embedding_model
        self.timeout = timeout
        self.crawl_timeout = crawl_timeout
        self.retries = max(retries, 1)
        self.block_media = block_media
        self.allow_local_webhooks = allow_local_webhooks
        self.max_concurrency = max(1, max_concurrency)
        self.proxy = proxy or {}
        self.openai_api_key = openai_api_key
        self.logger = logging.getLogger("krai.scraping.firecrawl")

        # Normalize Firecrawl URL when running outside Docker and targeting Docker-internal host.
        try:
            parsed = urlparse(self.api_url)
            running_in_docker = os.path.exists("/.dockerenv") or os.getenv("KRAI_IN_DOCKER") == "1"
            if parsed.hostname in ("krai-firecrawl-api", "firecrawl", "krai-firecrawl") and not running_in_docker:
                # Host-side access uses mapped port 9004 -> container 3002.
                original_url = self.api_url
                self.api_url = urlunparse(parsed._replace(netloc="127.0.0.1:9004"))
                self.logger.info(
                    "Overriding Firecrawl URL for local execution: %r -> %r",
                    original_url,
                    self.api_url,
                )
        except Exception:
            # Best-effort normalization only; fall back silently on errors
            pass

        if AsyncFirecrawl is None and not self.mock_mode:
            raise FirecrawlUnavailableError(
                "firecrawl-py SDK is not installed. Install `firecrawl-py` to enable " "Firecrawl backend."
            )

        self._client: AsyncFirecrawl | None = None
        if AsyncFirecrawl is not None:
            client_kwargs = {"api_key": self.api_key}
            if self.api_url:
                client_kwargs["api_url"] = self.api_url
            self._client = AsyncFirecrawl(**client_kwargs)

    async def scrape_url(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            self.logger.debug("Mock scrape_url called for %s", url)
            return {
                "success": True,
                "backend": self.backend_name,
                "content": "Mock content for scraping",
                "html": "<html><body>Mock</body></html>",
                "metadata": {"url": url, "mock": True},
            }

        options = options or {}
        request_options = {
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
            **options,
        }
        if "blockMedia" not in request_options:
            request_options["blockMedia"] = self.block_media
        if self.proxy and "proxy" not in request_options:
            request_options["proxy"] = self.proxy
        attempt = 0
        last_error: Exception | None = None
        while attempt < self.retries:
            attempt += 1
            try:
                if not self._client:
                    raise FirecrawlUnavailableError("Firecrawl client unavailable")
                self.logger.debug(
                    "Firecrawl scrape attempt %s for %s with options %s",
                    attempt,
                    url,
                    request_options,
                )
                response = await asyncio.wait_for(
                    self._client.scrape(url=url, options=request_options),
                    timeout=self.timeout,
                )
                payload = response.get("data", response)
                return {
                    "success": True,
                    "backend": self.backend_name,
                    "content": payload.get("markdown") or payload.get("content"),
                    "html": payload.get("html"),
                    "metadata": payload.get("metadata", {}),
                }
            except (TimeoutError, httpx.TimeoutException) as exc:
                last_error = exc
                self.logger.warning(
                    "Firecrawl scrape timeout for %s (attempt %s/%s)",
                    url,
                    attempt,
                    self.retries,
                )
            except (httpx.ConnectError, httpx.TransportError) as exc:
                last_error = exc
                self.logger.error("Firecrawl connection error for %s: %s", url, exc)
                raise FirecrawlUnavailableError("Firecrawl connection failed") from exc
            except httpx.HTTPStatusError as exc:
                last_error = exc
                self.logger.error(
                    "Firecrawl HTTP error %s for %s: %s",
                    exc.response.status_code,
                    url,
                    exc,
                )
                break
            except FirecrawlUnavailableError:
                raise
            except Exception as exc:  # pragma: no cover - guard against SDK changes
                last_error = exc
                self.logger.exception("Unexpected Firecrawl error for %s: %s", url, exc)
                break
            await asyncio.sleep(2**attempt)

        error_message = f"Firecrawl scrape failed for {url}: {last_error!s}" if last_error else ""
        return {
            "success": False,
            "backend": self.backend_name,
            "error": error_message,
        }

    async def crawl_site(self, start_url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "total": 1,
                "pages": [
                    {
                        "url": start_url,
                        "content": "Mock crawl page",
                        "metadata": {"depth": 0, "mock": True},
                    }
                ],
            }

        if not self._client:
            raise FirecrawlUnavailableError("Firecrawl client unavailable")

        options = options or {}
        crawl_options = {
            "limit": options.get("limit", 10),
            "maxDepth": options.get("maxDepth", 2),
            "allowBackwardLinks": options.get("allowBackwardLinks", False),
            **{k: v for k, v in options.items() if k not in {"limit", "maxDepth"}},
        }
        if "blockMedia" not in crawl_options:
            crawl_options["blockMedia"] = self.block_media
        if self.proxy and "proxy" not in crawl_options:
            crawl_options["proxy"] = self.proxy

        try:
            if hasattr(self._client, "crawl"):
                response = await asyncio.wait_for(
                    self._client.crawl(url=start_url, options=crawl_options),
                    timeout=self.crawl_timeout,
                )
                data = response.get("data", response)
            else:
                crawl_job = await asyncio.wait_for(
                    self._client.start_crawl(url=start_url, options=crawl_options),
                    timeout=self.timeout,
                )
                crawl_id = crawl_job.get("id") or crawl_job.get("jobId") or crawl_job.get("crawlId")
                if not crawl_id:
                    raise RuntimeError("Firecrawl start_crawl did not return an identifier")

                poll_interval = float(options.get("pollInterval", 2.0))
                deadline = asyncio.get_event_loop().time() + self.crawl_timeout
                status: dict[str, Any] = {}

                while asyncio.get_event_loop().time() < deadline:
                    status = await self._client.get_crawl_status(crawl_id)
                    state = status.get("status") or status.get("state")
                    if state in {"completed", "succeeded", "failed", "error"}:
                        break
                    await asyncio.sleep(poll_interval)
                else:
                    raise TimeoutError(f"Firecrawl crawl for {start_url} exceeded timeout")

                if status.get("status") not in {"completed", "succeeded"}:
                    error_message = status.get("error") or status.get("message") or "Unknown crawl failure"
                    return {
                        "success": False,
                        "backend": self.backend_name,
                        "error": error_message,
                    }

                data = status.get("result") or status.get("data") or status

            pages = data.get("pages") or data.get("data", {}).get("pages") or []
            normalized_pages = [
                {
                    "url": page.get("url") or page.get("link"),
                    "content": page.get("markdown") or page.get("content") or page.get("text"),
                    "metadata": page.get("metadata", {}),
                }
                for page in pages
            ]

            return {
                "success": True,
                "backend": self.backend_name,
                "total": len(normalized_pages),
                "pages": normalized_pages,
            }
        except (httpx.ConnectError, httpx.TransportError) as exc:
            self.logger.error("Firecrawl crawl connection error: %s", exc)
            raise FirecrawlUnavailableError("Firecrawl connection failed") from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            self.logger.warning("Firecrawl crawl timeout for %s", start_url)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": f"Crawl timed out: {exc}",
            }
        except Exception as exc:  # pragma: no cover - unexpected SDK behaviour
            self.logger.exception("Unexpected Firecrawl crawl error: %s", exc)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": str(exc),
            }

    async def extract_structured_data(
        self,
        url: str,
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "data": {"mock": True},
                "confidence": 1.0,
            }

        if not self._client:
            raise FirecrawlUnavailableError("Firecrawl client unavailable")

        extraction_options = options or {}
        if "blockMedia" not in extraction_options:
            extraction_options["blockMedia"] = self.block_media
        if self.proxy and "proxy" not in extraction_options:
            extraction_options["proxy"] = self.proxy
        try:
            response = await asyncio.wait_for(
                self._client.extract(url=url, schema=schema, options=extraction_options),
                timeout=self.timeout,
            )
            data = response.get("data", response)
            return {
                "success": True,
                "backend": self.backend_name,
                "data": data.get("data") or data.get("result") or data,
                "confidence": data.get("confidence", 0.0),
            }
        except (httpx.ConnectError, httpx.TransportError) as exc:
            self.logger.error("Firecrawl extract connection error: %s", exc)
            raise FirecrawlUnavailableError("Firecrawl connection failed") from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            self.logger.warning("Firecrawl extract timeout for %s", url)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": f"Extraction timed out: {exc}",
            }
        except Exception as exc:  # pragma: no cover - unexpected SDK behaviour
            self.logger.exception("Unexpected Firecrawl extraction error: %s", exc)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": str(exc),
            }

    async def map_urls(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "urls": [url, f"{url.rstrip('/')}/mock"],
                "total": 2,
            }

        if not self._client:
            raise FirecrawlUnavailableError("Firecrawl client unavailable")

        map_options = options or {}
        if "blockMedia" not in map_options:
            map_options["blockMedia"] = self.block_media
        if self.proxy and "proxy" not in map_options:
            map_options["proxy"] = self.proxy
        try:
            response = await asyncio.wait_for(
                self._client.map(url=url, options=map_options),
                timeout=self.timeout,
            )
            data = response.get("data", response)
            urls = data.get("urls") or data.get("links") or []
            return {
                "success": True,
                "backend": self.backend_name,
                "urls": urls,
                "total": len(urls),
            }
        except (httpx.ConnectError, httpx.TransportError) as exc:
            self.logger.error("Firecrawl map connection error: %s", exc)
            raise FirecrawlUnavailableError("Firecrawl connection failed") from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            self.logger.warning("Firecrawl map timeout for %s", url)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": f"Mapping timed out: {exc}",
            }
        except Exception as exc:  # pragma: no cover - unexpected SDK behaviour
            self.logger.exception("Unexpected Firecrawl map error: %s", exc)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": str(exc),
            }

    async def health_check(self) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "status": "mock",
                "backend": self.backend_name,
                "details": {"mock": True},
            }

        url = f"{self.api_url}/health"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return {
                    "status": "healthy",
                    "backend": self.backend_name,
                    "details": response.json() if response.content else {},
                }
        except httpx.HTTPStatusError as exc:
            return {
                "status": "degraded",
                "backend": self.backend_name,
                "details": {"status_code": exc.response.status_code},
            }
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise FirecrawlUnavailableError("Firecrawl health check failed") from exc


class BeautifulSoupBackend(WebScraperBackend):
    """BeautifulSoup fallback scraping implementation."""

    backend_name = "beautifulsoup"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 10.0,
        delay: float = 1.0,
        mock_mode: bool = False,
    ) -> None:
        super().__init__(mock_mode=mock_mode)
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay = delay
        self.logger = logging.getLogger("krai.scraping.beautifulsoup")

    async def scrape_url(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "content": "Mock BeautifulSoup content",
                "html": "<html><body>Mock</body></html>",
                "metadata": {"url": url, "mock": True},
            }

        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                cleaned = self._clean_text(text)
                return {
                    "success": True,
                    "backend": self.backend_name,
                    "content": cleaned,
                    "html": response.text,
                    "metadata": {
                        "status_code": response.status_code,
                        "content_type": response.headers.get("content-type"),
                        "url": str(response.url),
                    },
                }
        except httpx.HTTPStatusError as exc:
            self.logger.warning("HTTP error scraping %s: %s", url, exc)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": f"HTTP error {exc.response.status_code}",
            }
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            self.logger.warning("Connection error scraping %s: %s", url, exc)
            return {
                "success": False,
                "backend": self.backend_name,
                "error": str(exc),
            }

    async def crawl_site(self, start_url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "total": 1,
                "pages": [
                    {
                        "url": start_url,
                        "content": "Mock crawl page",
                        "metadata": {"depth": 0, "mock": True},
                    }
                ],
            }

        options = options or {}
        limit = int(options.get("limit", 10))
        max_depth = int(options.get("maxDepth", 2))
        visited: dict[str, int] = {}
        queue: list[tuple[str, int]] = [(start_url, 0)]
        pages: list[dict[str, Any]] = []

        while queue and len(pages) < limit:
            current_url, depth = queue.pop(0)
            if current_url in visited and visited[current_url] <= depth:
                continue
            visited[current_url] = depth
            result = await self.scrape_url(current_url)
            if not result.get("success"):
                continue
            pages.append(
                {
                    "url": current_url,
                    "content": result.get("content"),
                    "metadata": {"depth": depth, **result.get("metadata", {})},
                }
            )
            if depth >= max_depth:
                continue
            links = self._extract_links(result.get("html", ""), current_url)
            for link in links:
                if link not in visited:
                    queue.append((link, depth + 1))
            await asyncio.sleep(self.delay)

        return {
            "success": True,
            "backend": self.backend_name,
            "total": len(pages),
            "pages": pages,
        }

    async def extract_structured_data(
        self,
        url: str,
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.logger.warning("Structured extraction not available with BeautifulSoup backend")
        return {
            "success": False,
            "backend": self.backend_name,
            "error": "Structured extraction requires Firecrawl backend",
        }

    async def map_urls(self, url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "backend": self.backend_name,
                "urls": [url, f"{url.rstrip('/')}/mock"],
                "total": 2,
            }

        result = await self.scrape_url(url)
        if not result.get("success"):
            return result
        html = result.get("html", "")
        links = self._extract_links(html, url)
        options = options or {}
        search = options.get("search")
        if search:
            pattern = re.compile(search)
            links = [link for link in links if pattern.search(link)]
        limit = options.get("limit")
        if isinstance(limit, int):
            links = links[:limit]
        return {
            "success": True,
            "backend": self.backend_name,
            "urls": links,
            "total": len(links),
        }

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "backend": self.backend_name,
            "details": {"message": "BeautifulSoup backend available"},
        }

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(base_url).netloc
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            absolute = urljoin(base_url, href)
            if urlparse(absolute).netloc == base_domain:
                links.append(absolute)
        return list(dict.fromkeys(links))  # unique preserving order

    def _clean_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        if len(cleaned) > 50000:
            cleaned = cleaned[:50000]
        return cleaned


class WebScrapingService:
    """High level service that provides automatic backend selection."""

    def __init__(
        self,
        primary_backend: WebScraperBackend,
        fallback_backend: WebScraperBackend | None = None,
        config_service: Any | None = None,
    ) -> None:
        self._primary_backend = primary_backend
        self._fallback_backend = fallback_backend
        self._config_service = config_service
        self._logger = logging.getLogger("krai.scraping")
        self._fallback_count = 0

    @property
    def fallback_count(self) -> int:
        return self._fallback_count

    @property
    def primary_backend(self) -> WebScraperBackend:
        return self._primary_backend

    @property
    def fallback_backend(self) -> WebScraperBackend | None:
        return self._fallback_backend

    async def scrape_url(
        self,
        url: str,
        options: dict[str, Any] | None = None,
        force_backend: str | None = None,
    ) -> dict[str, Any]:
        backend = self._resolve_backend(force_backend)
        start = asyncio.get_event_loop().time()
        try:
            result = await backend.scrape_url(url, options)
        except FirecrawlUnavailableError as exc:
            result = await self._handle_fallback("scrape_url", url, options, exc)
        else:
            # If the primary backend failed and no specific backend was forced,
            # try the fallback (e.g. Firecrawl InternalServerError → BeautifulSoup).
            if not result.get("success") and not force_backend and self._fallback_backend:
                self._logger.warning(
                    "Primary backend %s failed for %s, trying fallback %s",
                    backend.backend_name,
                    url,
                    self._fallback_backend.backend_name,
                )
                self._fallback_count += 1
                result = await self._fallback_backend.scrape_url(url, options)
        duration = asyncio.get_event_loop().time() - start
        status = "completed" if result.get("success") else "failed"
        self._logger.info("Scrape %s using %s in %.2fs", status, result.get("backend"), duration)
        return result

    async def crawl_site(
        self,
        start_url: str,
        options: dict[str, Any] | None = None,
        force_backend: str | None = None,
    ) -> dict[str, Any]:
        self._assert_valid_url(start_url)
        backend = self._resolve_backend(force_backend)
        try:
            return await backend.crawl_site(start_url, options)
        except FirecrawlUnavailableError as exc:
            return await self._handle_fallback("crawl_site", start_url, options, exc)

    async def extract_structured_data(
        self,
        url: str,
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        backend = self._resolve_backend()
        if backend.backend_name != "firecrawl":
            return {
                "success": False,
                "backend": backend.backend_name,
                "error": "Structured extraction requires Firecrawl backend",
            }
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a dictionary")
        try:
            return await backend.extract_structured_data(url, schema, options)
        except FirecrawlUnavailableError as exc:
            self._logger.warning("Firecrawl unavailable during extract_structured_data for %s", url)
            raise exc

    async def map_urls(
        self,
        url: str,
        options: dict[str, Any] | None = None,
        force_backend: str | None = None,
    ) -> dict[str, Any]:
        backend = self._resolve_backend(force_backend)
        try:
            return await backend.map_urls(url, options)
        except FirecrawlUnavailableError as exc:
            return await self._handle_fallback("map_urls", url, options, exc)

    async def health_check(self) -> dict[str, Any]:
        status = "healthy"
        backends: dict[str, Any] = {}

        for backend in filter(None, [self._primary_backend, self._fallback_backend]):
            try:
                backends[backend.backend_name] = await backend.health_check()
            except FirecrawlUnavailableError as exc:
                backends[backend.backend_name] = {
                    "status": "unavailable",
                    "error": str(exc),
                }
                status = "degraded"

        aggregated_status = {
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "backends": backends,
        }
        return aggregated_status

    def get_backend_info(self) -> dict[str, Any]:
        active_backend = self._primary_backend.backend_name
        capabilities = ["scrape", "crawl", "map"]
        if active_backend == "firecrawl":
            capabilities.append("extract")
        fallback_available = bool(self._fallback_backend)
        return {
            "backend": active_backend,
            "capabilities": capabilities,
            "fallback_available": fallback_available,
            "fallback_count": self._fallback_count,
        }

    def switch_backend(self, backend: WebScraperBackend) -> None:
        self._logger.info(
            "Switching primary scraping backend from %s to %s",
            self._primary_backend.backend_name,
            backend.backend_name,
        )
        self._primary_backend = backend

    def _resolve_backend(self, force_backend: str | None = None) -> WebScraperBackend:
        if force_backend:
            if self._primary_backend.backend_name == force_backend or (
                self._fallback_backend and self._fallback_backend.backend_name == force_backend
            ):
                return (
                    self._primary_backend
                    if self._primary_backend.backend_name == force_backend
                    else self._fallback_backend  # type: ignore[return-value]
                )
            raise ValueError(f"Backend {force_backend} is not configured")
        return self._primary_backend

    async def _handle_fallback(
        self,
        method: str,
        url: str,
        options: dict[str, Any] | None,
        error: Exception,
    ) -> dict[str, Any]:
        if not self._fallback_backend:
            raise error
        self._fallback_count += 1
        self._logger.warning(
            "Firecrawl unavailable, falling back to %s for %s",
            self._fallback_backend.backend_name,
            url,
        )
        fallback_method = getattr(self._fallback_backend, method)
        return await fallback_method(url, options)

    def _assert_valid_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Invalid URL scheme for {url}")


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def create_web_scraping_service(
    backend: str | None = None,
    config_service: Any | None = None,
) -> WebScrapingService:
    """Factory for ``WebScrapingService`` instances following config patterns."""

    logger = logging.getLogger("krai.scraping")
    config: dict[str, Any] = {}

    if config_service:
        config = config_service.get_scraping_config()
    else:
        config = {
            "backend": backend or os.getenv("SCRAPING_BACKEND", "beautifulsoup"),
            "firecrawl_api_url": os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"),
            "firecrawl_llm_provider": os.getenv("FIRECRAWL_LLM_PROVIDER", "ollama"),
            "firecrawl_model_name": os.getenv("FIRECRAWL_MODEL_NAME", "llama3.2:latest"),
            "firecrawl_embedding_model": os.getenv("FIRECRAWL_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            "max_concurrency": int(os.getenv("FIRECRAWL_MAX_CONCURRENCY", "4")),
            "scrape_timeout": float(os.getenv("FIRECRAWL_SCRAPE_TIMEOUT", "300")),
            "crawl_timeout": float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "900")),
            "retries": int(os.getenv("FIRECRAWL_RETRIES", "3")),
            "block_media": _env_bool(os.getenv("FIRECRAWL_BLOCK_MEDIA"), True),
            "allow_local_webhooks": _env_bool(os.getenv("FIRECRAWL_ALLOW_LOCAL_WEBHOOKS"), True),
            "proxy_server": os.getenv("FIRECRAWL_PROXY_SERVER"),
            "proxy_username": os.getenv("FIRECRAWL_PROXY_USERNAME"),
            "proxy_password": os.getenv("FIRECRAWL_PROXY_PASSWORD"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "mock_mode": _env_bool(os.getenv("SCRAPING_MOCK_MODE"), False),
        }

    backend_name = (backend or config.get("backend") or "beautifulsoup").lower()

    mock_mode = bool(config.get("mock_mode", False))

    bs_backend = BeautifulSoupBackend(mock_mode=mock_mode)
    firecrawl_backend: FirecrawlBackend | None = None

    if backend_name == "firecrawl":
        try:
            proxy_config = None
            if config.get("proxy_server"):
                proxy_config = {
                    "server": config.get("proxy_server"),
                    "username": config.get("proxy_username"),
                    "password": config.get("proxy_password"),
                }
            firecrawl_backend = FirecrawlBackend(
                api_url=config.get("firecrawl_api_url", "http://localhost:3002"),
                llm_provider=config.get("firecrawl_llm_provider", "ollama"),
                model_name=config.get("firecrawl_model_name", "llama3.2:latest"),
                embedding_model=config.get("firecrawl_embedding_model", "nomic-embed-text:latest"),
                timeout=float(config.get("scrape_timeout", 30.0)),
                crawl_timeout=float(config.get("crawl_timeout", 300.0)),
                retries=int(config.get("retries", 3)),
                block_media=bool(config.get("block_media", True)),
                allow_local_webhooks=bool(config.get("allow_local_webhooks", True)),
                max_concurrency=int(config.get("max_concurrency", 4)),
                proxy=proxy_config,
                openai_api_key=config.get("openai_api_key"),
                mock_mode=mock_mode,
            )
            logger.info("Creating web scraping service: firecrawl backend")
            return WebScrapingService(
                primary_backend=firecrawl_backend,
                fallback_backend=bs_backend,
                config_service=config_service,
            )
        except FirecrawlUnavailableError as exc:
            logger.warning("Firecrawl unavailable during service creation: %s", exc)

    logger.info("Creating web scraping service: beautifulsoup backend")
    return WebScrapingService(
        primary_backend=bs_backend,
        fallback_backend=firecrawl_backend,
        config_service=config_service,
    )
