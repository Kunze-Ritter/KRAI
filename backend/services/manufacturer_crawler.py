"""Manufacturer crawling service built on top of WebScrapingService.

This module coordinates scheduled manufacturer website crawls, persistence of
crawled pages, and downstream structured extraction for content discovered via
Firecrawl. It relies on ``krai_system.manufacturer_crawl_*`` tables introduced in
migration 122 and bridges across batch task scheduling, scraping, and
transformation layers.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

try:
    from croniter import croniter
except Exception:
    croniter = None

from .config_service import ConfigService
from .web_scraping_service import FirecrawlUnavailableError, WebScrapingService


class ManufacturerCrawler:
    """High-level coordinator for manufacturer crawling workflows."""

    def __init__(
        self,
        web_scraping_service: WebScrapingService,
        database_service: Any,
        config_service: ConfigService | None = None,
        structured_extraction_service: Any | None = None,
        batch_task_service: Any | None = None,
    ) -> None:
        self._scraper = web_scraping_service
        self._database_service = database_service
        self._config_service = config_service
        self._structured_extraction_service = structured_extraction_service
        self._batch_task_service = batch_task_service
        self._logger = logging.getLogger("krai.services.manufacturer_crawler")

        self._config = self._load_config()
        self._enabled = self._config.get("enable_manufacturer_crawling", False)
        if not self._enabled:
            self._logger.info("Manufacturer crawler initialised but feature flag disabled")

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------
    async def create_crawl_schedule(self, manufacturer_id: str, crawl_config: dict[str, Any]) -> str | None:
        if not self._enabled:
            self._logger.warning("Manufacturer crawling disabled; schedule not created")
            return None

        import json

        payload = {
            "manufacturer_id": manufacturer_id,
            "crawl_type": crawl_config.get("crawl_type", "full_site"),
            "start_url": crawl_config["start_url"],
            "url_patterns": crawl_config.get("url_patterns"),
            "exclude_patterns": crawl_config.get("exclude_patterns"),
            "max_depth": crawl_config.get("max_depth", self._config.get("default_max_depth", 2)),
            "max_pages": crawl_config.get("max_pages", self._config.get("default_max_pages", 100)),
            "schedule_cron": crawl_config.get("schedule_cron"),
            "enabled": crawl_config.get("enabled", True),
            "crawl_options": crawl_config.get("crawl_options", {}),
            "next_run_at": self._calculate_next_run(crawl_config.get("schedule_cron")),
        }

        try:
            query = """
                INSERT INTO krai_system.manufacturer_crawl_schedules
                (manufacturer_id, crawl_type, start_url, url_patterns, exclude_patterns,
                 max_depth, max_pages, schedule_cron, enabled, crawl_options, next_run_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """
            # Convert ISO datetime string to datetime object for asyncpg
            next_run_dt = None
            if payload["next_run_at"]:
                from datetime import datetime

                next_run_dt = datetime.fromisoformat(payload["next_run_at"].replace("Z", "+00:00"))

            params = [
                payload["manufacturer_id"],
                payload["crawl_type"],
                payload["start_url"],
                payload["url_patterns"],
                payload["exclude_patterns"],
                payload["max_depth"],
                payload["max_pages"],
                payload["schedule_cron"],
                payload["enabled"],
                json.dumps(payload["crawl_options"]) if payload["crawl_options"] else None,
                next_run_dt,
            ]
            rows = await self._database_service.execute_query(query, params)
            schedule_id = rows[0]["id"] if rows else None
            self._logger.info("Created crawl schedule %s for manufacturer %s", schedule_id, manufacturer_id)
            return str(schedule_id) if schedule_id else None
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.error("Failed to create crawl schedule: %s", exc)
            return None

    async def update_crawl_schedule(self, schedule_id: str, updates: dict[str, Any]) -> bool:
        import json

        if "schedule_cron" in updates:
            updates["next_run_at"] = self._calculate_next_run(updates.get("schedule_cron"))

        try:
            # Build dynamic UPDATE query
            set_clauses = []
            params = []
            param_idx = 1

            for key, value in updates.items():
                set_clauses.append(f"{key} = ${param_idx}")
                # Serialize dicts to JSON
                if isinstance(value, dict):
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                param_idx += 1

            params.append(str(schedule_id))
            query = f"""
                UPDATE krai_system.manufacturer_crawl_schedules
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_idx}
            """

            await self._database_service.execute_query(query, params)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.error("Failed to update crawl schedule %s: %s", schedule_id, exc)
            return False

    async def delete_crawl_schedule(self, schedule_id: str) -> bool:
        try:
            query = """
                DELETE FROM krai_system.manufacturer_crawl_schedules
                WHERE id = $1
            """
            await self._database_service.execute_query(query, [str(schedule_id)])
            return True
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to delete crawl schedule %s: %s", schedule_id, exc)
            return False

    async def list_crawl_schedules(self, manufacturer_id: str | None = None) -> list[dict[str, Any]]:
        try:
            if manufacturer_id:
                query = """
                    SELECT * FROM krai_system.manufacturer_crawl_schedules
                    WHERE manufacturer_id = $1
                    ORDER BY created_at
                """
                rows = await self._database_service.execute_query(query, [str(manufacturer_id)])
            else:
                query = """
                    SELECT * FROM krai_system.manufacturer_crawl_schedules
                    ORDER BY created_at
                """
                rows = await self._database_service.execute_query(query)
            return rows or []
        except Exception as exc:
            self._logger.error("Failed to list crawl schedules: %s", exc)
            return []

    async def get_crawl_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        try:
            query = """
                SELECT * FROM krai_system.manufacturer_crawl_schedules
                WHERE id = $1
                LIMIT 1
            """
            rows = await self._database_service.execute_query(query, [str(schedule_id)])
            return rows[0] if rows else None
        except Exception as exc:
            self._logger.error("Failed to get crawl schedule %s: %s", schedule_id, exc)
            return None

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------
    async def start_crawl_job(self, schedule_id: str) -> str | None:
        if not self._enabled:
            self._logger.warning("Manufacturer crawling disabled; job not started")
            return None

        schedule = await self.get_crawl_schedule(schedule_id)
        if not schedule:
            self._logger.error("Schedule %s not found", schedule_id)
            return None

        import json

        payload = {
            "schedule_id": schedule_id,
            "manufacturer_id": schedule["manufacturer_id"],
            "status": "queued",
            "crawl_metadata": {},
        }
        try:
            query = """
                INSERT INTO krai_system.manufacturer_crawl_jobs
                (schedule_id, manufacturer_id, status, crawl_metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """
            rows = await self._database_service.execute_query(
                query,
                [schedule_id, payload["manufacturer_id"], payload["status"], json.dumps(payload["crawl_metadata"])],
            )
            job_id = str(rows[0]["id"]) if rows else None
            self._logger.info("Queued crawl job %s for schedule %s", job_id, schedule_id)

            # Dispatch job via BatchTaskService if available, otherwise inline
            if job_id:
                await self._dispatch_crawl_job(job_id, schedule_id)

            return job_id
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Failed to start crawl job: %s", exc)
            return None

    async def _dispatch_crawl_job(self, job_id: str, schedule_id: str) -> None:
        """Dispatch a crawl job for execution via BatchTaskService or inline background."""
        if self._batch_task_service:
            try:
                task_request = {
                    "operation_type": "manufacturer_crawl",
                    "priority": "medium",
                    "user_id": "system",
                    "payload": {"job_id": job_id, "schedule_id": schedule_id},
                }
                task_id = await self._batch_task_service.create_task(task_request)
                self._logger.info("Enqueued crawl job %s as batch task %s", job_id, task_id)
            except Exception as exc:
                self._logger.warning("Failed to enqueue crawl job %s, falling back to inline: %s", job_id, exc)
                # Fallback to inline execution
                asyncio.create_task(self.execute_crawl_job(job_id))
        else:
            self._logger.warning("BatchTaskService unavailable, running crawl job %s inline", job_id)
            asyncio.create_task(self.execute_crawl_job(job_id))

    async def execute_crawl_job(self, job_id: str) -> dict[str, Any]:
        job = await self.get_crawl_job_status(job_id)
        if not job:
            return {"success": False, "error": "job not found"}

        schedule = await self.get_crawl_schedule(job["schedule_id"]) if job.get("schedule_id") else None
        if not schedule:
            return {"success": False, "error": "schedule not found"}

        await self._update_job(job_id, {"status": "running", "started_at": datetime.now(UTC).isoformat()})

        crawl_options = schedule.get("crawl_options", {}) or {}
        crawl_options.setdefault("limit", schedule.get("max_pages") or self._config.get("default_max_pages", 100))
        crawl_options.setdefault("maxDepth", schedule.get("max_depth") or self._config.get("default_max_depth", 2))

        try:
            response = await self._scraper.crawl_site(schedule.get("start_url"), options=crawl_options)
        except FirecrawlUnavailableError as exc:  # pragma: no cover
            await self._update_job(job_id, {"status": "failed", "error_message": str(exc)})
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # pragma: no cover
            await self._update_job(job_id, {"status": "failed", "error_message": str(exc)})
            return {"success": False, "error": str(exc)}

        if not response.get("success"):
            await self._update_job(job_id, {"status": "failed", "error_message": response.get("error")})
            return {"success": False, "error": response.get("error")}

        pages = response.get("pages", [])
        persisted = await self._persist_crawled_pages(job_id, schedule.get("manufacturer_id"), pages)

        await self._update_job(
            job_id,
            {
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "pages_discovered": len(pages),
                "pages_scraped": persisted["scraped"],
                "pages_failed": persisted["failed"],
                "crawl_metadata": {"backend": response.get("backend")},
            },
        )

        await self._update_schedule_run(schedule.get("id"))

        if self._structured_extraction_service:
            await self.process_crawled_pages(job_id)

        return {
            "success": True,
            "job_id": job_id,
            "pages_discovered": len(pages),
            "pages_scraped": persisted["scraped"],
            "pages_failed": persisted["failed"],
        }

    async def process_crawled_pages(self, job_id: str) -> dict[str, Any]:
        if not self._structured_extraction_service:
            return {"processed": 0, "extractions": 0}

        try:
            query = """
                SELECT id, page_type
                FROM krai_system.crawled_pages
                WHERE crawl_job_id = $1 AND status = $2
            """
            pages = await self._database_service.execute_query(query, [str(job_id), "scraped"])

            extraction_count = 0
            processed_ids = []
            failed_ids = []

            for page in pages or []:
                result = await self._structured_extraction_service.extract_from_crawled_page(page["id"])
                if result.get("success"):
                    extraction_count += 1
                    processed_ids.append(page["id"])
                else:
                    failed_ids.append(page["id"])

            # Update pages individually based on extraction outcome
            if processed_ids:
                update_query = """
                    UPDATE krai_system.crawled_pages
                    SET status = $1, processed_at = $2
                    WHERE id = ANY($3)
                """
                await self._database_service.execute_query(
                    update_query, ["processed", datetime.now(UTC), processed_ids]
                )
            if failed_ids:
                update_query = """
                    UPDATE krai_system.crawled_pages
                    SET status = $1, processed_at = $2
                    WHERE id = ANY($3)
                """
                await self._database_service.execute_query(update_query, ["failed", datetime.now(UTC), failed_ids])

            return {"processed": len(processed_ids), "failed": len(failed_ids), "extractions": extraction_count}
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to process crawled pages: %s", exc)
            return {"processed": 0, "extractions": 0}

    async def detect_content_changes(self, manufacturer_id: str) -> list[dict[str, Any]]:
        try:
            query = """
                SELECT url, content_hash, created_at
                FROM krai_system.crawled_pages
                WHERE manufacturer_id = $1
                ORDER BY url, created_at
            """
            rows = await self._database_service.execute_query(query, [str(manufacturer_id)])

            changes: dict[str, dict[str, Any]] = {}
            for row in rows or []:
                url = row.get("url")
                url_hash = row.get("content_hash")
                created_at = row.get("created_at")
                if not url or not url_hash:
                    continue
                if url not in changes:
                    changes[url] = {"last_hash": url_hash, "last_seen": created_at, "changed": False}
                else:
                    if changes[url]["last_hash"] != url_hash:
                        changes[url]["changed"] = True
                        changes[url]["previous_hash"] = changes[url]["last_hash"]
                        changes[url]["last_hash"] = url_hash
                        changes[url]["last_seen"] = created_at

            return [
                {
                    "url": url,
                    "changed": meta.get("changed", False),
                    "last_hash": meta.get("last_hash"),
                    "previous_hash": meta.get("previous_hash"),
                    "last_seen": meta.get("last_seen"),
                }
                for url, meta in changes.items()
                if meta.get("changed")
            ]
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to detect content changes: %s", exc)
            return []

    async def get_crawl_job_status(self, job_id: str) -> dict[str, Any] | None:
        try:
            query = """
                SELECT *
                FROM krai_system.manufacturer_crawl_jobs
                WHERE id = $1
                LIMIT 1
            """
            rows = await self._database_service.execute_query(query, [str(job_id)])
            job = rows[0] if rows else None
            if job and job.get("pages_discovered"):
                discovered = job.get("pages_discovered", 0) or 0
                scraped = job.get("pages_scraped", 0) or 0
                job["progress_percent"] = 0 if discovered == 0 else round((scraped / discovered) * 100, 2)
            return job
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to get crawl job status %s: %s", job_id, exc)
            return None

    async def list_crawl_jobs(self, schedule_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        try:
            conditions = []
            params = []
            param_idx = 1

            if schedule_id:
                conditions.append(f"schedule_id = ${param_idx}")
                params.append(str(schedule_id))
                param_idx += 1
            if status:
                conditions.append(f"status = ${param_idx}")
                params.append(status)
                param_idx += 1

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT *
                FROM krai_system.manufacturer_crawl_jobs
                WHERE {where_clause}
                ORDER BY created_at DESC
            """
            rows = await self._database_service.execute_query(query, params)
            return rows or []
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to list crawl jobs: %s", exc)
            return []

    async def retry_failed_job(self, job_id: str) -> str | None:
        job = await self.get_crawl_job_status(job_id)
        if not job or job.get("status") != "failed":
            return None
        schedule_id = job.get("schedule_id")
        if not schedule_id:
            return None
        return await self.start_crawl_job(schedule_id)

    async def get_crawled_pages(
        self,
        *,
        job_id: str | None = None,
        manufacturer_id: str | None = None,
        page_type: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            conditions = []
            params = []
            param_idx = 1

            if job_id:
                conditions.append(f"crawl_job_id = ${param_idx}")
                params.append(str(job_id))
                param_idx += 1
            if manufacturer_id:
                conditions.append(f"manufacturer_id = ${param_idx}")
                params.append(str(manufacturer_id))
                param_idx += 1
            if page_type:
                conditions.append(f"page_type = ${param_idx}")
                params.append(page_type)
                param_idx += 1

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT *
                FROM krai_system.crawled_pages
                WHERE {where_clause}
                ORDER BY created_at DESC
            """
            rows = await self._database_service.execute_query(query, params)
            return rows or []
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to get crawled pages: %s", exc)
            return []

    async def check_scheduled_crawls(self) -> list[str]:
        if not self._enabled:
            return []

        try:
            now = datetime.now(UTC)
            query = """
                SELECT id
                FROM krai_system.manufacturer_crawl_schedules
                WHERE enabled = $1 AND next_run_at <= $2
            """
            rows = await self._database_service.execute_query(query, [True, now])

            job_ids: list[str] = []
            for row in rows or []:
                schedule_id = row["id"]
                job_id = await self.start_crawl_job(schedule_id)
                if job_id:
                    job_ids.append(job_id)
            return job_ids
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to check scheduled crawls: %s", exc)
            return []

    async def get_crawler_stats(self) -> dict[str, Any]:
        try:
            # Get schedule counts
            schedules_query = "SELECT COUNT(*) as count FROM krai_system.manufacturer_crawl_schedules"
            schedules_result = await self._database_service.execute_query(schedules_query)
            total_schedules = schedules_result[0]["count"] if schedules_result else 0

            active_query = "SELECT COUNT(*) as count FROM krai_system.manufacturer_crawl_schedules WHERE enabled = $1"
            active_result = await self._database_service.execute_query(active_query, [True])
            active_schedules = active_result[0]["count"] if active_result else 0

            # Get job counts
            jobs_query = "SELECT COUNT(*) as count FROM krai_system.manufacturer_crawl_jobs"
            jobs_result = await self._database_service.execute_query(jobs_query)
            total_jobs = jobs_result[0]["count"] if jobs_result else 0

            running_query = "SELECT COUNT(*) as count FROM krai_system.manufacturer_crawl_jobs WHERE status = $1"
            running_result = await self._database_service.execute_query(running_query, ["running"])
            running_jobs = running_result[0]["count"] if running_result else 0

            # Get page counts
            pages_query = "SELECT COUNT(*) as count FROM krai_system.crawled_pages"
            pages_result = await self._database_service.execute_query(pages_query)
            total_pages = pages_result[0]["count"] if pages_result else 0

            # Get page type distribution
            page_type_query = """
                SELECT page_type, COUNT(*) as count
                FROM krai_system.crawled_pages
                WHERE page_type IS NOT NULL
                GROUP BY page_type
            """
            page_type_rows = await self._database_service.execute_query(page_type_query)
            page_type_dist = {row["page_type"]: row["count"] for row in (page_type_rows or [])}

            return {
                "total_schedules": total_schedules,
                "active_schedules": active_schedules,
                "total_jobs": total_jobs,
                "running_jobs": running_jobs,
                "total_pages": total_pages,
                "page_types": page_type_dist,
            }
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to get crawler stats: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _get_db_client(self):
        """
        Get a compatible database client for database operations.

        Returns the underlying client from DatabaseService if available.
        Logs an error and returns None if unavailable.
        """
        if hasattr(self._database_service, "service_client") and self._database_service.service_client:
            return self._database_service.service_client
        if hasattr(self._database_service, "client") and self._database_service.client:
            return self._database_service.client
        self._logger.error("Database client unavailable for database operations")
        return None

    async def _update_job(self, job_id: str, updates: dict[str, Any]) -> None:
        import json

        try:
            set_clauses = []
            params = []
            param_idx = 1

            for key, value in updates.items():
                set_clauses.append(f"{key} = ${param_idx}")
                if isinstance(value, dict):
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                param_idx += 1

            params.append(str(job_id))
            query = f"""
                UPDATE krai_system.manufacturer_crawl_jobs
                SET {', '.join(set_clauses)}
                WHERE id = ${param_idx}
            """
            await self._database_service.execute_query(query, params)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.debug("Failed to update crawl job %s: %s", job_id, exc)

    async def _update_schedule_run(self, schedule_id: str) -> None:
        next_run = self._calculate_next_run(None)
        try:
            query = """
                UPDATE krai_system.manufacturer_crawl_schedules
                SET last_run_at = $1, next_run_at = $2
                WHERE id = $3
            """
            await self._database_service.execute_query(query, [datetime.now(UTC), next_run, str(schedule_id)])
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.debug("Failed to update schedule run %s: %s", schedule_id, exc)

    async def _persist_crawled_pages(
        self, job_id: str, manufacturer_id: str, pages: Sequence[dict[str, Any]]
    ) -> dict[str, int]:
        client = self._get_db_client()
        if client is None:
            self._logger.error("Cannot persist crawled pages: database client unavailable")
            return {"scraped": 0, "failed": len(pages)}

        scraped = 0
        failed = 0
        for page in pages:
            url = page.get("url")
            content = page.get("content")
            if not url:
                failed += 1
                continue
            url_hash = hashlib.sha256(url.encode("utf-8", errors="ignore")).hexdigest()
            content_hash = (
                hashlib.sha256((content or "").encode("utf-8", errors="ignore")).hexdigest() if content else None
            )
            page_type = self._determine_page_type(url)

            payload = {
                "crawl_job_id": job_id,
                "manufacturer_id": manufacturer_id,
                "url": url,
                "url_hash": url_hash,
                "content": content,
                "content_hash": content_hash,
                "html": page.get("html"),
                "page_title": (page.get("metadata") or {}).get("title"),
                "page_type": page_type,
                "depth": (page.get("metadata") or {}).get("depth"),
                "status": "scraped",
                "scrape_metadata": page.get("metadata") or {},
            }

            try:
                existing = (
                    client.table("crawled_pages", schema="krai_system")
                    .select("id")
                    .eq("crawl_job_id", str(job_id))
                    .eq("url_hash", url_hash)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    client.table("crawled_pages", schema="krai_system").update(payload).eq(
                        "id", existing.data[0]["id"]
                    ).execute()
                else:
                    client.table("crawled_pages", schema="krai_system").insert(payload).execute()
                scraped += 1
            except Exception as exc:  # pragma: no cover - defensive logging
                failed += 1
                self._logger.debug("Failed to persist crawled page %s: %s", url, exc)

        return {"scraped": scraped, "failed": failed}

    def _determine_page_type(self, url: str) -> str | None:
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in ["product", "spec", "datasheet"]):
            return "product_page"
        if any(keyword in url_lower for keyword in ["error", "support", "troubleshoot"]):
            return "error_code_page"
        if any(keyword in url_lower for keyword in ["manual", "download", "pdf"]):
            return "manual_page"
        if "parts" in url_lower or "catalog" in url_lower:
            return "parts_page"
        return "unknown"

    def _calculate_next_run(self, cron_expression: str | None) -> str | None:
        if not cron_expression or croniter is None:
            return None
        try:
            iterator = croniter(cron_expression, datetime.now(UTC))
            return iterator.get_next(datetime).isoformat()
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.debug("Invalid cron expression %s: %s", cron_expression, exc)
            return None

    def _load_config(self) -> dict[str, Any]:
        if self._config_service:
            try:
                config = self._config_service.get_scraping_config()
                return {
                    "enable_manufacturer_crawling": config.get("enable_manufacturer_crawling", False),
                    "default_max_pages": config.get("crawler_default_max_pages", 100),
                    "default_max_depth": config.get("crawler_default_max_depth", 2),
                }
            except Exception as exc:  # pragma: no cover - defensive logging
                self._logger.debug("Failed loading crawler config: %s", exc)
        return {
            "enable_manufacturer_crawling": False,
            "default_max_pages": 100,
            "default_max_depth": 2,
        }
