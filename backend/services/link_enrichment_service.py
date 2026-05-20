"""Link enrichment service for scraping external URLs.

This module orchestrates scraping of URLs using WebScrapingService
(Firecrawl primary, BeautifulSoup fallback) and persists the
resulting artefacts into ``krai_system.link_scraping_jobs`` table.

Refactored to use DatabaseService for database operations.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from .config_service import ConfigService
from .web_scraping_service import FirecrawlUnavailableError, WebScrapingService


class LinkEnrichmentService:
    """Service responsible for scraping and enriching stored link records."""

    def __init__(
        self,
        web_scraping_service: WebScrapingService,
        database_service: Any,
        config_service: ConfigService | None = None,
    ) -> None:
        self._scraper = web_scraping_service
        self._database_service = database_service
        self._config_service = config_service
        self._logger = logging.getLogger("krai.services.link_enrichment")

        cfg = self._load_config()
        self._max_concurrent_enrichments = cfg.get("max_concurrent_enrichments", 3)
        self._enrichment_timeout = cfg.get("enrichment_timeout", 30)
        self._retry_failed_after_hours = cfg.get("retry_failed_after_hours", 24)
        self._enabled = cfg.get("enable_link_enrichment", True)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    async def enrich_link(
        self,
        link_id: str,
        url: str,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Scrape a single link and persist enrichment artefacts.

        Args:
            link_id: UUID identifier for the link row.
            url: URL to scrape.
            force_refresh: When ``True`` scraping is performed even when a
                successful enrichment already exists.

        Returns:
            Dict[str, Any]: Summary payload describing enrichment outcome.
        """

        if not self._enabled:
            return {"success": False, "link_id": link_id, "error": "link enrichment disabled"}

        # Fetch existing record from link_scraping_jobs
        query = """
            SELECT id, scrape_status, scraped_content, scraped_metadata, content_hash
            FROM krai_system.link_scraping_jobs
            WHERE id = $1::uuid
            LIMIT 1
        """

        try:
            existing = await self._database_service.execute_query(query, (str(link_id),))
        except Exception as exc:
            self._logger.error("Failed to fetch link %s: %s", link_id, exc)
            return {"success": False, "link_id": link_id, "error": f"database error: {exc}"}

        if not existing:
            return {"success": False, "link_id": link_id, "error": "link record not found"}

        row = existing[0]
        scrape_status = row.get("scrape_status")
        scraped_content = row.get("scraped_content")
        content_hash = row.get("content_hash")

        if scrape_status == "success" and scraped_content and content_hash and not force_refresh:
            self._logger.debug("Link %s already enriched; skipping", link_id)
            return {"success": True, "link_id": link_id, "skipped": True}

        metadata = self._parse_metadata(row.get("scraped_metadata"))
        retry_count = int(metadata.get("retry_count", 0))

        try:
            result = await asyncio.wait_for(
                self._scraper.scrape_url(url),
                timeout=self._enrichment_timeout + 5,
            )
        except FirecrawlUnavailableError as exc:  # pragma: no cover - defensive
            self._logger.warning("Firecrawl unavailable for %s: %s", url, exc)
            result = await self._scraper.scrape_url(url, force_backend="beautifulsoup")
        except TimeoutError as exc:
            self._logger.warning("Scrape timed out for %s", url)
            await self._mark_link_failed(
                link_id,
                error_message=f"Scrape timeout: {exc}",
                metadata=metadata,
            )
            return {"success": False, "link_id": link_id, "error": "timeout"}
        except Exception as exc:  # pragma: no cover - safety net
            self._logger.exception("Unexpected scraping failure for %s", url)
            await self._mark_link_failed(
                link_id,
                error_message=str(exc),
                metadata=metadata,
            )
            return {"success": False, "link_id": link_id, "error": str(exc)}

        if not result.get("success"):
            error_message = result.get("error", "scrape failed")
            self._logger.debug("Scrape failed for %s: %s", url, error_message)
            metadata["retry_count"] = retry_count + 1
            await self._mark_link_failed(
                link_id,
                error_message=error_message,
                metadata=metadata,
            )
            return {"success": False, "link_id": link_id, "error": error_message}

        content: str | None = result.get("content")
        backend = result.get("backend")
        scrape_metadata = result.get("metadata") or {}

        if not content:
            metadata["retry_count"] = retry_count + 1
            await self._mark_link_failed(
                link_id,
                error_message="No content returned by scraper",
                metadata=metadata,
            )
            return {"success": False, "link_id": link_id, "error": "empty content"}

        content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
        metadata.update(
            {
                "backend": backend,
                "status_code": scrape_metadata.get("status_code"),
                "content_type": scrape_metadata.get("content_type"),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "retry_count": 0,
            }
        )

        # Update link_scraping_jobs with enrichment data
        update_query = """
            UPDATE krai_system.link_scraping_jobs
            SET scraped_content = $1,
                scraped_metadata = $2,
                scraped_at = $3,
                scrape_status = $4,
                scrape_error = NULL,
                content_hash = $5,
                updated_at = $3
            WHERE id = $6::uuid
        """

        try:
            await self._database_service.execute_query(
                update_query,
                (
                    content,
                    json.dumps(metadata),  # Serialize dict to JSON string
                    datetime.now(UTC),
                    "success",
                    content_hash,
                    str(link_id),
                ),
            )
        except Exception as exc:
            self._logger.error("Failed to persist enrichment for %s: %s", link_id, exc)
            return {"success": False, "link_id": link_id, "error": str(exc)}

        self._logger.info(
            "Enriched link %s using %s (content %s chars)",
            link_id,
            backend,
            len(content),
        )
        return {
            "success": True,
            "link_id": link_id,
            "backend": backend,
            "content_length": len(content),
        }

    async def enrich_links_batch(
        self,
        link_ids: Sequence[str],
        *,
        max_concurrent: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Enrich multiple links concurrently while respecting concurrency limits."""

        if not link_ids:
            return {"total": 0, "enriched": 0, "failed": 0, "skipped": 0, "results": []}

        # Fetch all links from link_scraping_jobs
        placeholders = ", ".join([f"${i+1}::uuid" for i in range(len(link_ids))])
        query = f"""
            SELECT id, url, scrape_status, scraped_content, content_hash
            FROM krai_system.link_scraping_jobs
            WHERE id IN ({placeholders})
        """

        if not force_refresh:
            query += " AND scrape_status IN ('pending', 'failed')"

        try:
            records = await self._database_service.execute_query(query, tuple(str(link_id) for link_id in link_ids))
        except Exception as exc:
            self._logger.error("Failed to fetch links for batch: %s", exc)
            return {"total": 0, "enriched": 0, "failed": len(link_ids), "skipped": 0, "results": []}

        links = {str(row["id"]): row for row in records or []}

        semaphore = asyncio.Semaphore(max_concurrent or self._max_concurrent_enrichments)
        results: list[dict[str, Any]] = []

        async def _worker(link_id: str) -> None:
            link = links.get(link_id)
            if not link:
                results.append({"success": False, "link_id": link_id, "error": "link record missing"})
                return

            if (
                link.get("scrape_status") == "success"
                and link.get("scraped_content")
                and link.get("content_hash")
                and not force_refresh
            ):
                results.append({"success": True, "link_id": link_id, "skipped": True})
                return

            async with semaphore:
                outcome = await self.enrich_link(link_id, link.get("url"), force_refresh=force_refresh)
                results.append(outcome)

        await asyncio.gather(*[_worker(str(link_id)) for link_id in link_ids])

        enriched = sum(1 for item in results if item.get("success") and not item.get("skipped"))
        skipped = sum(1 for item in results if item.get("skipped"))
        failed = sum(1 for item in results if not item.get("success"))

        return {
            "total": len(link_ids),
            "enriched": enriched,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    async def enrich_document_links(self, document_id: str) -> dict[str, Any]:
        """Enrich all links belonging to the supplied document identifier."""

        query = """
            SELECT id
            FROM krai_system.link_scraping_jobs
            WHERE document_id = $1::uuid
              AND scrape_status IN ('pending', 'failed')
        """

        try:
            response = await self._database_service.execute_query(query, (str(document_id),))
            link_ids = [row["id"] for row in response or []]
            return await self.enrich_links_batch(link_ids)
        except Exception as exc:
            self._logger.error("Failed to fetch document links: %s", exc)
            return {"total": 0, "enriched": 0, "failed": 0, "skipped": 0, "results": []}

    async def refresh_stale_links(self, days_old: int = 90) -> dict[str, Any]:
        """Re-enrich links whose content is older than the configured threshold."""

        cutoff = datetime.now(UTC) - timedelta(days=days_old)
        query = """
            SELECT id
            FROM krai_system.link_scraping_jobs
            WHERE scraped_at < $1
              AND scrape_status = 'success'
        """

        try:
            response = await self._database_service.execute_query(query, (cutoff,))
            link_ids = [row["id"] for row in response or []]
            return await self.enrich_links_batch(link_ids, force_refresh=True)
        except Exception as exc:
            self._logger.error("Failed to fetch stale links: %s", exc)
            return {"total": 0, "enriched": 0, "failed": 0, "skipped": 0, "results": []}

    async def retry_failed_links(self, max_retries: int = 3) -> dict[str, Any]:
        """Retry enrichment for links that previously failed within retry budget."""

        query = """
            SELECT id, scraped_metadata, retry_count
            FROM krai_system.link_scraping_jobs
            WHERE scrape_status = 'failed'
              AND COALESCE(retry_count, 0) < $1
        """

        try:
            response = await self._database_service.execute_query(query, (max_retries,))
        except Exception as exc:
            self._logger.error("Failed to fetch failed links: %s", exc)
            return {"total": 0, "enriched": 0, "failed": 0, "skipped": 0, "results": []}

        eligible_ids: list[str] = []
        threshold = datetime.now(UTC) - timedelta(hours=self._retry_failed_after_hours)

        for row in response or []:
            metadata = self._parse_metadata(row.get("scraped_metadata"))
            last_error_iso = metadata.get("last_error_at")
            last_error_at = None

            if last_error_iso:
                with contextlib.suppress(ValueError):
                    last_error_at = datetime.fromisoformat(last_error_iso)

            if last_error_at is None or last_error_at <= threshold:
                eligible_ids.append(row["id"])

        return await self.enrich_links_batch(eligible_ids)

    async def get_enrichment_stats(self) -> dict[str, Any]:
        """Return aggregated statistics for monitoring dashboards."""

        stats_query = """
            SELECT
                COUNT(*) as total_links,
                COUNT(*) FILTER (WHERE scrape_status = 'success') as enriched_links,
                COUNT(*) FILTER (WHERE scrape_status = 'pending') as pending_links,
                COUNT(*) FILTER (WHERE scrape_status = 'failed') as failed_links,
                AVG(LENGTH(scraped_content)) FILTER (WHERE scraped_content IS NOT NULL) as avg_content_length
            FROM krai_system.link_scraping_jobs
        """

        backend_query = """
            SELECT scraped_metadata
            FROM krai_system.link_scraping_jobs
            WHERE scraped_metadata IS NOT NULL
        """

        try:
            stats_result = await self._database_service.execute_query(stats_query)
            backend_result = await self._database_service.execute_query(backend_query)

            stats = stats_result[0] if stats_result else {}

            backend_distribution: dict[str, int] = {}
            for row in backend_result or []:
                metadata = self._parse_metadata(row.get("scraped_metadata"))
                backend = metadata.get("backend") or "unknown"
                backend_distribution[backend] = backend_distribution.get(backend, 0) + 1

            return {
                "total_links": int(stats.get("total_links") or 0),
                "enriched_links": int(stats.get("enriched_links") or 0),
                "pending_links": int(stats.get("pending_links") or 0),
                "failed_links": int(stats.get("failed_links") or 0),
                "average_content_length": int(stats.get("avg_content_length") or 0),
                "backend_distribution": backend_distribution,
            }
        except Exception as exc:
            self._logger.error("Failed to get enrichment stats: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_metadata(self, metadata: Any) -> dict[str, Any]:
        """Parse metadata - handle both dict and JSON string."""
        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except (json.JSONDecodeError, ValueError):
                self._logger.warning("Failed to parse metadata JSON: %s", metadata[:100])
                return {}
        return {}

    def _load_config(self) -> dict[str, Any]:
        if self._config_service:
            try:
                config = self._config_service.get_scraping_config()
                return {
                    "enable_link_enrichment": config.get("enable_link_enrichment", False),
                    "max_concurrent_enrichments": config.get("max_concurrency", 3),
                    "enrichment_timeout": int(config.get("scrape_timeout", 30)),
                    "retry_failed_after_hours": int(config.get("retry_failed_after_hours", 24)),
                }
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.debug("Failed loading scraping config: %s", exc)
        return {
            "enable_link_enrichment": True,
            "max_concurrent_enrichments": 3,
            "enrichment_timeout": 30,
            "retry_failed_after_hours": 24,
        }

    async def _mark_link_failed(
        self,
        link_id: str,
        *,
        error_message: str,
        metadata: dict[str, Any],
    ) -> None:
        """Mark a link scraping job as failed in database."""
        metadata = metadata or {}
        metadata["last_error_at"] = datetime.now(UTC).isoformat()

        query = """
            UPDATE krai_system.link_scraping_jobs
            SET scrape_status = $1,
                scrape_error = $2,
                scraped_metadata = $3,
                scraped_at = $4,
                updated_at = $4,
                retry_count = COALESCE(retry_count, 0) + 1
            WHERE id = $5::uuid
        """

        try:
            await self._database_service.execute_query(
                query,
                (
                    "failed",
                    error_message,
                    json.dumps(metadata),  # Serialize dict to JSON string
                    datetime.now(UTC),
                    str(link_id),
                ),
            )
        except Exception as exc:
            self._logger.debug("Failed updating failure state for %s: %s", link_id, exc)
