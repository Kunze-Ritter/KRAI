"""
Real integration scaffolding for ManufacturerCrawler.

This module adds minimal, database-backed smoke coverage and helper utilities
for future Firecrawl-enabled E2E scenarios. Firecrawl-dependent tests are
skipped when the backend is unavailable.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.database]


async def _table_exists(db, schema: str, table: str) -> bool:
    """Check table existence in the connected database."""
    try:
        rows = await db.execute_query(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = $2
            LIMIT 1
            """,
            [schema, table],
        )
        return bool(rows)
    except Exception:
        return False


async def create_test_schedule(
    crawler,
    manufacturer_id: str,
    start_url: str,
    crawl_type: str = "full_site",
    max_depth: int = 1,
    max_pages: int = 5,
    schedule_cron: str | None = None,
) -> str | None:
    """Helper to create a schedule via crawler API."""
    return await crawler.create_crawl_schedule(
        manufacturer_id=manufacturer_id,
        crawl_config={
            "start_url": start_url,
            "crawl_type": crawl_type,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "schedule_cron": schedule_cron,
            "enabled": True,
        },
    )


async def wait_for_job_completion(crawler, job_id: str, timeout: float = 15.0) -> dict[str, Any]:
    """
    Poll job status until completion or timeout.

    Uses the public get_crawl_job_status API to check job status.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        job = await crawler.get_crawl_job_status(job_id)  # pragma: no cover - public API
        if job and job.get("status") in {"completed", "failed", "cancelled"}:
            return job
        await asyncio.sleep(0.25)
    return job if (job := await crawler.get_crawl_job_status(job_id)) else {}


class TestManufacturerCrawlerRealE2E:
    """
    Minimal real E2E coverage for ManufacturerCrawler (database-backed, Firecrawl-optional).
    """

    @pytest.mark.asyncio
    async def test_create_schedule_with_database_persistence(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            crawl_type="full_site",
            max_depth=1,
            max_pages=3,
        )

        assert schedule_id, "schedule_id should be returned"

        rows = await test_database.execute_query(
            """
            SELECT manufacturer_id, crawl_type, start_url, enabled
            FROM krai_system.manufacturer_crawl_schedules
            WHERE id = $1
            """,
            [schedule_id],
        )
        assert rows, "schedule row must exist"
        row = rows[0]
        assert row["manufacturer_id"] == test_manufacturer_data["manufacturer_id"]
        assert row["crawl_type"] == "full_site"
        assert row["start_url"] == test_crawl_urls["example"]
        assert row["enabled"] is True

    @pytest.mark.asyncio
    async def test_update_schedule_in_database(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test updating an existing schedule and verify DB changes."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create initial schedule
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            crawl_type="full_site",
            max_depth=1,
            max_pages=3,
        )
        assert schedule_id

        # Update schedule
        updated = await real_manufacturer_crawler.update_crawl_schedule(
            schedule_id=schedule_id,
            updates={
                "max_pages": 10,
                "max_depth": 2,
                "enabled": False,
            },
        )
        assert updated is True

        # Verify DB changes
        rows = await test_database.execute_query(
            """
            SELECT max_pages, max_depth, enabled
            FROM krai_system.manufacturer_crawl_schedules
            WHERE id = $1
            """,
            [schedule_id],
        )
        assert rows
        row = rows[0]
        assert row["max_pages"] == 10
        assert row["max_depth"] == 2
        assert row["enabled"] is False

    @pytest.mark.asyncio
    async def test_delete_schedule_from_database(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test deleting a schedule and verify removal from DB."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create schedule
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
        )
        assert schedule_id

        # Delete schedule
        deleted = await real_manufacturer_crawler.delete_crawl_schedule(schedule_id)
        assert deleted is True

        # Verify removal
        rows = await test_database.execute_query(
            """
            SELECT id
            FROM krai_system.manufacturer_crawl_schedules
            WHERE id = $1
            """,
            [schedule_id],
        )
        assert not rows, "Schedule should be deleted from DB"

    @pytest.mark.asyncio
    async def test_list_schedules_for_manufacturer(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test listing all schedules for a manufacturer."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create multiple schedules
        schedule_ids = []
        for i in range(3):
            schedule_id = await create_test_schedule(
                real_manufacturer_crawler,
                manufacturer_id=test_manufacturer_data["manufacturer_id"],
                start_url=f"{test_crawl_urls['example']}/page{i}",
                crawl_type="full_site" if i % 2 == 0 else "support_pages",
            )
            schedule_ids.append(schedule_id)

        # List schedules
        schedules = await real_manufacturer_crawler.list_crawl_schedules(
            manufacturer_id=test_manufacturer_data["manufacturer_id"]
        )

        assert len(schedules) >= 3, "Should have at least 3 schedules"
        schedule_ids_from_list = [str(s["id"]) for s in schedules]
        for sid in schedule_ids:
            assert sid in schedule_ids_from_list

    @pytest.mark.asyncio
    async def test_schedule_next_run_calculation(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test next_run calculation for cron-based schedules."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create schedule with cron
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            schedule_cron="0 2 * * *",  # Daily at 2 AM
        )
        assert schedule_id

        # Verify next_run_at was calculated
        rows = await test_database.execute_query(
            """
            SELECT next_run_at, schedule_cron
            FROM krai_system.manufacturer_crawl_schedules
            WHERE id = $1
            """,
            [schedule_id],
        )
        assert rows
        row = rows[0]
        assert row["schedule_cron"] == "0 2 * * *"
        assert row["next_run_at"] is not None, "next_run_at should be calculated for cron schedules"


class TestManufacturerCrawlerFirecrawlSmoke:
    """
    Placeholder smoke tests for Firecrawl-backed crawls.

    Skips automatically when Firecrawl is not configured.
    """

    @pytest.mark.asyncio
    async def test_firecrawl_health_check(self, real_manufacturer_crawler, firecrawl_available):
        if not firecrawl_available:
            pytest.skip("Firecrawl backend not available")

        scraper = real_manufacturer_crawler._scraper
        health = await scraper.health_check()
        assert isinstance(health, dict)
        assert health.get("backend") in {"firecrawl", "beautifulsoup"}

    @pytest.mark.asyncio
    async def test_execute_crawl_job_with_firecrawl(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
        firecrawl_available,
    ):
        """Test executing a crawl job with real Firecrawl backend."""
        if not firecrawl_available:
            pytest.skip("Firecrawl backend not available")
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_jobs"):
            pytest.skip("krai_system.manufacturer_crawl_jobs missing in test DB")

        # Create schedule first
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            crawl_type="full_site",
            max_depth=1,
            max_pages=2,  # Keep small for fast test
        )
        assert schedule_id

        # Start crawl job
        job_id = await real_manufacturer_crawler.start_crawl_job(schedule_id)
        assert job_id, "Job ID should be returned"

        # Wait for completion (with timeout)
        job = await wait_for_job_completion(real_manufacturer_crawler, job_id, timeout=30.0)

        # Verify job completion
        assert job, "Job should exist"
        assert job.get("status") in {"completed", "failed"}, f"Job should complete, got: {job.get('status')}"

        # If successful, verify pages were crawled
        if job.get("status") == "completed":
            assert job.get("pages_crawled", 0) > 0, "Should have crawled at least 1 page"

    @pytest.mark.asyncio
    async def test_crawl_job_persistence_in_database(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
        firecrawl_available,
    ):
        """Test that crawl jobs are persisted correctly in database."""
        if not firecrawl_available:
            pytest.skip("Firecrawl backend not available")
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_jobs"):
            pytest.skip("krai_system.manufacturer_crawl_jobs missing in test DB")

        # Create schedule
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["httpbin"],  # Use httpbin for reliable test
            max_pages=1,
        )

        # Start job
        job_id = await real_manufacturer_crawler.start_crawl_job(schedule_id)

        # Verify job in DB
        rows = await test_database.execute_query(
            """
            SELECT id, schedule_id, status, manufacturer_id
            FROM krai_system.manufacturer_crawl_jobs
            WHERE id = $1
            """,
            [job_id],
        )
        assert rows, "Job should be persisted in DB"
        job_row = rows[0]
        assert job_row["schedule_id"] == schedule_id
        assert job_row["manufacturer_id"] == test_manufacturer_data["manufacturer_id"]
        assert job_row["status"] in {"queued", "pending", "running", "completed", "failed"}

    @pytest.mark.asyncio
    async def test_crawled_pages_persistence(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
        firecrawl_available,
    ):
        """Test that crawled pages are saved to krai_system.crawled_pages."""
        if not firecrawl_available:
            pytest.skip("Firecrawl backend not available")
        if not await _table_exists(test_database, "krai_system", "crawled_pages"):
            pytest.skip("krai_system.crawled_pages missing in test DB")

        # Create schedule and start job
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["httpbin"],
            max_pages=1,
        )
        job_id = await real_manufacturer_crawler.start_crawl_job(schedule_id)

        # Wait for completion
        job = await wait_for_job_completion(real_manufacturer_crawler, job_id, timeout=30.0)

        if job.get("status") == "completed":
            # Check for crawled pages
            rows = await test_database.execute_query(
                """
                SELECT url, content_hash, crawl_job_id
                FROM krai_system.crawled_pages
                WHERE crawl_job_id = $1
                """,
                [job_id],
            )
            assert rows, "Should have at least one crawled page"
            page = rows[0]
            assert page["url"]
            assert page["content_hash"]
            assert page["crawl_job_id"] == job_id

    def test_crawl_configuration_validation(self, manufacturer_crawler):
        """Test crawl configuration validation."""
        # Test valid configurations
        valid_configs = [
            {"crawl_type": "support_pages", "start_url": "http://example.com/support", "max_pages": 50, "max_depth": 0},
            {
                "crawl_type": "product_catalog",
                "start_url": "https://example.com/products",
                "max_pages": 100,
                "max_depth": 5,
            },
        ]

        for config in valid_configs:
            result = manufacturer_crawler._validate_crawl_config(config)
            assert result is True

        # Test invalid configurations
        invalid_configs = [
            {"crawl_type": "invalid_type", "start_url": "http://example.com"},
            {"crawl_type": "support_pages", "start_url": "not-a-url"},
            {"crawl_type": "support_pages", "start_url": "http://example.com", "max_pages": -1},
            {"crawl_type": "support_pages", "start_url": "http://example.com", "max_depth": -1},
        ]

        for config in invalid_configs:
            result = manufacturer_crawler._validate_crawl_config(config)
            assert result is False

    def test_crawl_time_calculation(self, manufacturer_crawler):
        """Test crawl time calculation for various cron expressions."""
        # Test valid cron expressions
        cron_expressions = [
            "0 2 * * *",  # Daily at 2 AM
            "0 0 * * 1",  # Weekly on Monday
            "0 0 1 * *",  # Monthly on 1st
            "*/15 * * * *",  # Every 15 minutes
        ]

        for cron_expr in cron_expressions:
            next_run = manufacturer_crawler._calculate_next_run_time(cron_expr)
            assert next_run is not None
            assert next_run > datetime.now(UTC)

        # Test invalid cron expression
        invalid_cron = "invalid-cron-expression"
        next_run = manufacturer_crawler._calculate_next_run_time(invalid_cron)
        assert next_run is None

    @pytest.mark.asyncio
    async def test_crawl_performance_monitoring(
        self, manufacturer_crawler, mock_db_client, mock_scraper, sample_crawl_job
    ):
        """Test crawl performance monitoring capabilities."""
        import time

        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_crawl_job]
        )
        mock_db_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "page-id"}])

        # Setup slower crawl to test performance
        async def slow_crawl(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate slow crawl
            return {"success": True, "backend": "firecrawl", "total": 0, "pages": []}

        mock_scraper.crawl_site.side_effect = slow_crawl

        # Execute crawl with timing
        start_time = time.time()
        result = await manufacturer_crawler.execute_crawl_job("job-0")
        end_time = time.time()

        # Verify performance characteristics
        assert result["success"] is True
        assert end_time - start_time < 30.0  # Should complete within timeout
        assert "duration" in result or "backend" in result  # Performance metrics

    def test_crawler_status_and_health(self, manufacturer_crawler):
        """Test crawler status and health checks."""
        # Test enabled status
        manufacturer_crawler._enabled = True
        assert manufacturer_crawler.is_crawler_enabled() is True

        # Test disabled status
        manufacturer_crawler._enabled = False
        assert manufacturer_crawler.is_crawler_enabled() is False

        # Test configuration health
        config = manufacturer_crawler._config
        assert config["crawler_max_concurrent_jobs"] > 0
        assert config["crawler_default_max_pages"] > 0
        assert config["crawler_default_max_depth"] >= 0


class TestManufacturerCrawlerExtendedE2E:
    """
    Extended E2E tests for ManufacturerCrawler covering additional scenarios.
    """

    @pytest.mark.asyncio
    async def test_job_status_transitions(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test job status transitions from queued -> running -> completed."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_jobs"):
            pytest.skip("krai_system.manufacturer_crawl_jobs missing in test DB")

        # Create schedule
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            max_pages=1,
        )
        assert schedule_id

        # Start job
        job_id = await real_manufacturer_crawler.start_crawl_job(schedule_id)
        assert job_id

        # Check initial status (should be queued)
        job = await real_manufacturer_crawler.get_crawl_job_status(job_id)
        assert job
        assert job["status"] in {"queued", "running"}

        # Wait for completion
        final_job = await wait_for_job_completion(real_manufacturer_crawler, job_id, timeout=30.0)
        assert final_job
        assert final_job["status"] in {"completed", "failed"}

    @pytest.mark.asyncio
    async def test_content_change_detection(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
        firecrawl_available,
    ):
        """Test content change detection after multiple crawls."""
        if not firecrawl_available:
            pytest.skip("Firecrawl backend not available")
        if not await _table_exists(test_database, "krai_system", "crawled_pages"):
            pytest.skip("krai_system.crawled_pages missing in test DB")

        # Create schedule
        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["httpbin"],
            max_pages=1,
        )

        # First crawl
        job_id_1 = await real_manufacturer_crawler.start_crawl_job(schedule_id)
        await wait_for_job_completion(real_manufacturer_crawler, job_id_1, timeout=30.0)

        # Second crawl
        job_id_2 = await real_manufacturer_crawler.start_crawl_job(schedule_id)
        await wait_for_job_completion(real_manufacturer_crawler, job_id_2, timeout=30.0)

        # Detect changes
        changes = await real_manufacturer_crawler.detect_content_changes(test_manufacturer_data["manufacturer_id"])

        # Changes list may be empty if content is identical, which is expected
        assert isinstance(changes, list)

    @pytest.mark.asyncio
    async def test_check_scheduled_crawls_creates_jobs(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test that check_scheduled_crawls creates jobs for due schedules."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create schedule with next_run_at in the past
        from datetime import datetime, timedelta

        schedule_id = await create_test_schedule(
            real_manufacturer_crawler,
            manufacturer_id=test_manufacturer_data["manufacturer_id"],
            start_url=test_crawl_urls["example"],
            max_pages=1,
        )

        # Manually set next_run_at to past
        past_time = datetime.now(UTC) - timedelta(hours=1)
        await test_database.execute_query(
            """
            UPDATE krai_system.manufacturer_crawl_schedules
            SET next_run_at = $1
            WHERE id = $2
            """,
            [past_time, schedule_id],
        )

        # Check scheduled crawls
        job_ids = await real_manufacturer_crawler.check_scheduled_crawls()

        # Should have created at least one job
        assert len(job_ids) >= 1

    @pytest.mark.asyncio
    async def test_get_crawler_stats_accuracy(
        self,
        real_manufacturer_crawler,
        test_database,
        test_manufacturer_data,
        test_crawl_urls,
    ):
        """Test that get_crawler_stats returns accurate aggregate metrics."""
        if not await _table_exists(test_database, "krai_system", "manufacturer_crawl_schedules"):
            pytest.skip("krai_system.manufacturer_crawl_schedules missing in test DB")

        # Create multiple schedules
        schedule_ids = []
        for i in range(2):
            schedule_id = await create_test_schedule(
                real_manufacturer_crawler,
                manufacturer_id=test_manufacturer_data["manufacturer_id"],
                start_url=f"{test_crawl_urls['example']}/page{i}",
                max_pages=1,
            )
            schedule_ids.append(schedule_id)

        # Get stats
        stats = await real_manufacturer_crawler.get_crawler_stats()

        # Verify stats structure
        assert "total_schedules" in stats
        assert "active_schedules" in stats
        assert "total_jobs" in stats
        assert "running_jobs" in stats
        assert "total_pages" in stats
        assert "page_types" in stats

        # Should have at least our created schedules
        assert stats["total_schedules"] >= 2
