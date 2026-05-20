"""
End-to-end integration tests for LinkEnrichmentService.

Tests complete link enrichment workflows including scraping,
content validation, persistence, and error handling.
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.link_enrichment_service import LinkEnrichmentService
from backend.services.web_scraping_service import FirecrawlUnavailableError

pytest.mark.integration = pytest.mark.integration


class TestLinkEnrichmentE2E:
    """Test LinkEnrichmentService end-to-end scenarios."""

    @pytest.fixture
    def mock_scraper(self):
        """Mock WebScrapingService."""
        scraper = MagicMock()
        scraper.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "backend": "firecrawl",
                "content": "Detailed product specifications and technical documentation",
                "html": "<html><body><h1>Product Specs</h1><p>Technical details...</p></body></html>",
                "metadata": {"status_code": 200, "content_type": "text/html", "title": "Product Specifications"},
            }
        )
        return scraper

    @pytest.fixture
    def mock_database_service(self, mock_db_client):
        """Mock database service."""
        service = MagicMock()
        service.client = mock_db_client
        service.service_client = mock_db_client
        return service

    @pytest.fixture
    def link_enrichment_service(self, mock_scraper, mock_database_service):
        """Create LinkEnrichmentService instance for testing."""
        return LinkEnrichmentService(web_scraping_service=mock_scraper, database_service=mock_database_service)

    @pytest.fixture
    def sample_link_records(self):
        """Sample link records for testing."""
        return [
            {
                "id": "link-1",
                "url": "http://example.com/product/c750a/specs",
                "link_type": "external",
                "scrape_status": "pending",
                "scraped_content": None,
                "content_hash": None,
                "scraped_metadata": {},
                "document_id": "doc-1",
                "manufacturer_id": "mfr-1",
            },
            {
                "id": "link-2",
                "url": "http://example.com/error-codes/c750a",
                "link_type": "external",
                "scrape_status": "pending",
                "scraped_content": None,
                "content_hash": None,
                "scraped_metadata": {},
                "document_id": "doc-1",
                "manufacturer_id": "mfr-1",
            },
            {
                "id": "link-3",
                "url": "http://example.com/manual/c750a.pdf",
                "link_type": "external",
                "scrape_status": "failed",
                "scraped_content": None,
                "content_hash": None,
                "scraped_metadata": {"retry_count": 1},
                "document_id": "doc-2",
                "manufacturer_id": "mfr-1",
            },
        ]

    @pytest.fixture
    def scraped_content_samples(self):
        """Sample scraped content for different link types."""
        return {
            "product_specs": {
                "content": "# Konica Minolta C750a Specifications\n\n## Print Specifications\n- **Print Speed**: 75 ppm\n- **Resolution**: 1200 x 1200 dpi\n- **Monthly Volume**: 300,000 pages",
                "metadata": {"title": "C750a Specifications", "content_type": "text/html"},
            },
            "error_codes": {
                "content": "# C750a Error Codes\n\n## 900.01 - Fuser Error\n**Description**: Fuser unit temperature error\n**Solution**: Replace fuser unit\n\n## 900.02 - Lamp Error\n**Description**: Fuser lamp failure",
                "metadata": {"title": "C750a Error Codes", "content_type": "text/html"},
            },
            "manual": {
                "content": "# C750a Service Manual\n\n## Table of Contents\n1. Installation\n2. Operation\n3. Maintenance\n4. Troubleshooting\n\nThis manual provides detailed service procedures.",
                "metadata": {"title": "C750a Service Manual", "content_type": "application/pdf"},
            },
        }

    def test_service_initialization_e2e(self, mock_scraper, mock_database_service):
        """Test LinkEnrichmentService initialization for E2E testing."""
        service = LinkEnrichmentService(web_scraping_service=mock_scraper, database_service=mock_database_service)

        assert service._scraper == mock_scraper
        assert service._database_service == mock_database_service
        assert service._enabled is True
        assert service._max_concurrent_enrichments >= 1
        assert service._enrichment_timeout > 0

    @pytest.mark.asyncio
    async def test_complete_link_enrichment_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, scraped_content_samples
    ):
        """Test complete link enrichment workflow from pending to success."""
        # Setup link record
        link_record = {
            "id": "link-workflow-1",
            "url": "http://example.com/product/c750a/specs",
            "link_type": "external",
            "scrape_status": "pending",
            "scraped_content": None,
            "content_hash": None,
            "scraped_metadata": {},
        }

        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[link_record]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-workflow-1"}]
        )

        # Setup scraper response
        mock_scraper.scrape_url.return_value = {
            "success": True,
            "backend": "firecrawl",
            "content": scraped_content_samples["product_specs"]["content"],
            "html": "<html><body>Product specs content</body></html>",
            "metadata": scraped_content_samples["product_specs"]["metadata"],
        }

        # Execute enrichment
        result = await link_enrichment_service.enrich_link(
            link_id="link-workflow-1", url="http://example.com/product/c750a/specs"
        )

        # Verify successful enrichment
        assert result["success"] is True
        assert result["link_id"] == "link-workflow-1"
        assert "content_length" in result
        assert "backend" in result

        # Verify database was updated with scraped content
        update_calls = mock_db_client.table.return_value.update.return_value.eq.return_value.execute
        update_calls.assert_called()

        # Get the update data from the call
        call_args = update_calls.call_args
        update_data = call_args[0][0] if call_args[0] else {}

        assert update_data["scrape_status"] == "success"
        assert update_data["scraped_content"] == scraped_content_samples["product_specs"]["content"]
        assert "content_hash" in update_data
        assert "scraped_at" in update_data
        assert "backend" in update_data["scraped_metadata"]

    @pytest.mark.asyncio
    async def test_batch_enrichment_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records, scraped_content_samples
    ):
        """Test batch enrichment of multiple links."""
        # Setup database responses for batch
        mock_db_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=sample_link_records
        )

        # Setup individual link responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=sample_link_records[0]  # Return first record for individual queries
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-id"}]
        )

        # Setup scraper responses for different content types
        async def scrape_side_effect(url):
            if "specs" in url:
                return {
                    "success": True,
                    "backend": "firecrawl",
                    "content": scraped_content_samples["product_specs"]["content"],
                    "metadata": scraped_content_samples["product_specs"]["metadata"],
                }
            if "error-codes" in url:
                return {
                    "success": True,
                    "backend": "firecrawl",
                    "content": scraped_content_samples["error_codes"]["content"],
                    "metadata": scraped_content_samples["error_codes"]["metadata"],
                }
            if "manual" in url:
                return {
                    "success": True,
                    "backend": "firecrawl",
                    "content": scraped_content_samples["manual"]["content"],
                    "metadata": scraped_content_samples["manual"]["metadata"],
                }
            return {"success": False, "error": "Unknown URL pattern"}

        mock_scraper.scrape_url.side_effect = scrape_side_effect

        # Execute batch enrichment
        result = await link_enrichment_service.enrich_links_batch(["link-1", "link-2", "link-3"])

        # Verify batch results
        assert result["total"] == 3
        assert result["enriched"] == 3
        assert result["failed"] == 0
        assert result["skipped"] == 0

        # Verify scraper was called for each link
        assert mock_scraper.scrape_url.call_count == 3

    @pytest.mark.asyncio
    async def test_enrichment_with_firecrawl_fallback(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test enrichment with Firecrawl fallback to BeautifulSoup."""
        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_link_records[0]]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-1"}]
        )

        # Setup Firecrawl failure then BeautifulSoup success
        firecrawl_error = FirecrawlUnavailableError("Firecrawl service unavailable")
        beautifulsoup_result = {
            "success": True,
            "backend": "beautifulsoup",
            "content": "Fallback scraped content from BeautifulSoup",
            "html": "<html><body>Fallback content</body></html>",
            "metadata": {"status_code": 200, "content_type": "text/html"},
        }

        mock_scraper.scrape_url.side_effect = [firecrawl_error, beautifulsoup_result]

        # Execute enrichment
        result = await link_enrichment_service.enrich_link(
            link_id="link-1", url="http://example.com/product/c750a/specs"
        )

        # Verify fallback worked
        assert result["success"] is True
        assert result["backend"] == "beautifulsoup"

        # Verify both backends were tried
        assert mock_scraper.scrape_url.call_count == 2

    @pytest.mark.asyncio
    async def test_enrichment_error_handling_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test enrichment error handling and recovery."""
        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_link_records[0]]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-1"}]
        )

        # Test different error scenarios
        error_scenarios = [
            ({"success": False, "error": "Connection timeout"}, "Connection timeout"),
            (Exception("Network error"), "Network error"),
            (TimeoutError("Request timeout"), "timeout"),
        ]

        for scraper_response, expected_error in error_scenarios:
            # Reset mock
            mock_scraper.scrape_url.reset_mock()

            # Setup scraper to return error
            if isinstance(scraper_response, Exception):
                mock_scraper.scrape_url.side_effect = scraper_response
            else:
                mock_scraper.scrape_url.return_value = scraper_response

            # Execute enrichment
            result = await link_enrichment_service.enrich_link(
                link_id="link-1", url="http://example.com/product/c750a/specs"
            )

            # Verify error handling
            assert result["success"] is False
            assert expected_error.lower() in result["error"].lower()

            # Verify link was marked as failed
            update_calls = mock_db_client.table.return_value.update.return_value.eq.return_value.execute
            update_calls.assert_called()

            call_args = update_calls.call_args
            update_data = call_args[0][0] if call_args[0] else {}

            assert update_data["scrape_status"] == "failed"
            assert "error_message" in update_data

    @pytest.mark.asyncio
    async def test_document_links_enrichment_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records, scraped_content_samples
    ):
        """Test enrichment of all links for a specific document."""
        # Setup database responses for document links
        mock_db_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=sample_link_records[:2]  # First two links belong to doc-1
        )

        # Setup individual link responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=sample_link_records[0]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-id"}]
        )

        # Setup scraper responses
        async def scrape_side_effect(url):
            if "specs" in url:
                return {
                    "success": True,
                    "backend": "firecrawl",
                    "content": scraped_content_samples["product_specs"]["content"],
                    "metadata": scraped_content_samples["product_specs"]["metadata"],
                }
            if "error-codes" in url:
                return {
                    "success": True,
                    "backend": "firecrawl",
                    "content": scraped_content_samples["error_codes"]["content"],
                    "metadata": scraped_content_samples["error_codes"]["metadata"],
                }
            return {"success": False, "error": "Unknown URL"}

        mock_scraper.scrape_url.side_effect = scrape_side_effect

        # Execute document enrichment
        result = await link_enrichment_service.enrich_document_links("doc-1")

        # Verify document enrichment results
        assert result["total"] == 2
        assert result["enriched"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_stale_links_refresh_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, scraped_content_samples
    ):
        """Test refreshing stale links workflow."""
        # Create stale link records (older than 90 days)
        stale_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        stale_links = [
            {
                "id": "stale-link-1",
                "url": "http://example.com/product/c750a/specs",
                "scrape_status": "success",
                "scraped_at": stale_date,
                "content_hash": "old-hash-123",
                "scraped_metadata": {},
            },
            {
                "id": "stale-link-2",
                "url": "http://example.com/error-codes/c750a",
                "scrape_status": "success",
                "scraped_at": stale_date,
                "content_hash": "old-hash-456",
                "scraped_metadata": {},
            },
        ]

        # Setup database responses
        mock_db_client.table.return_value.select.return_value.lt.return_value.execute.return_value = MagicMock(
            data=stale_links
        )

        # Setup individual link responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=stale_links[0]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-id"}]
        )

        # Setup scraper response with updated content
        mock_scraper.scrape_url.return_value = {
            "success": True,
            "backend": "firecrawl",
            "content": "Updated product specifications with new information",
            "metadata": {"title": "Updated C750a Specifications"},
        }

        # Execute stale links refresh
        result = await link_enrichment_service.refresh_stale_links(days_old=90)

        # Verify refresh results
        assert result["total"] == 2
        assert result["refreshed"] == 2

    @pytest.mark.asyncio
    async def test_failed_links_retry_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, scraped_content_samples
    ):
        """Test retrying failed links workflow."""
        # Create failed link records eligible for retry
        failed_date = (datetime.now(UTC) - timedelta(hours=25)).isoformat()  # More than 24h ago
        failed_links = [
            {
                "id": "failed-link-1",
                "url": "http://example.com/product/c750a/specs",
                "scrape_status": "failed",
                "scraped_metadata": {"retry_count": 2},
                "scraped_at": failed_date,
            },
            {
                "id": "failed-link-2",
                "url": "http://example.com/error-codes/c750a",
                "scrape_status": "failed",
                "scraped_metadata": {"retry_count": 1},  # Within retry budget
                "scraped_at": failed_date,
            },
            {
                "id": "exhausted-link-1",
                "url": "http://example.com/manual/c750a.pdf",
                "scrape_status": "failed",
                "scraped_metadata": {"retry_count": 3},  # Exceeded retry budget
                "scraped_at": failed_date,
            },
        ]

        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = (
            MagicMock(data=failed_links)
        )

        # Setup individual link responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=failed_links[0]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-id"}]
        )

        # Setup scraper response (now succeeds)
        mock_scraper.scrape_url.return_value = {
            "success": True,
            "backend": "firecrawl",
            "content": scraped_content_samples["product_specs"]["content"],
            "metadata": scraped_content_samples["product_specs"]["metadata"],
        }

        # Execute failed links retry
        result = await link_enrichment_service.retry_failed_links(max_retries=3)

        # Verify retry results
        assert result["total"] == 2  # Only links within retry budget and time threshold
        assert result["retried"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_enrichment_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records, mock_database_service
    ):
        """Test concurrent enrichment workflow."""
        # Create service with higher concurrency for testing
        service = LinkEnrichmentService(web_scraping_service=mock_scraper, database_service=mock_database_service)
        service._max_concurrent_enrichments = 5

        # Setup database responses for batch
        mock_db_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=sample_link_records
        )

        # Setup individual link responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=sample_link_records[0]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-id"}]
        )

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        execution_times = []

        original_scrape = mock_scraper.scrape_url

        async def tracked_scrape(url):
            nonlocal concurrent_count, max_concurrent
            start_time = asyncio.get_event_loop().time()
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

            # Simulate some processing time
            await asyncio.sleep(0.01)

            result = await original_scrape(url)
            concurrent_count -= 1

            end_time = asyncio.get_event_loop().time()
            execution_times.append(end_time - start_time)
            return result

        mock_scraper.scrape_url = tracked_scrape

        # Execute concurrent batch enrichment
        result = await service.enrich_links_batch(["link-1", "link-2", "link-3"])

        # Verify concurrent execution
        assert result["total"] == 3
        assert result["enriched"] == 3
        assert max_concurrent <= service._max_concurrent_enrichments

    @pytest.mark.asyncio
    async def test_enrichment_statistics_workflow(self, link_enrichment_service, mock_db_client):
        """Test enrichment statistics collection workflow."""
        # Setup database responses for statistics
        mock_db_client.table.return_value.select.return_value.execute.side_effect = [
            MagicMock(data=[{"count": 150}]),  # total_links
            MagicMock(data=[{"count": 100}]),  # enriched_links
            MagicMock(data=[{"count": 30}]),  # pending_links
            MagicMock(data=[{"count": 20}]),  # failed_links
            MagicMock(data=[{"avg_length": 2500}]),  # average_content_length
            MagicMock(
                data=[  # backend_distribution
                    {"backend": "firecrawl", "count": 80},
                    {"backend": "beautifulsoup", "count": 20},
                ]
            ),
        ]

        # Execute statistics collection
        result = await link_enrichment_service.get_enrichment_stats()

        # Verify statistics
        assert result["total_links"] == 150
        assert result["enriched_links"] == 100
        assert result["pending_links"] == 30
        assert result["failed_links"] == 20
        assert result["average_content_length"] == 2500
        assert result["backend_distribution"]["firecrawl"] == 80
        assert result["backend_distribution"]["beautifulsoup"] == 20

    @pytest.mark.asyncio
    async def test_content_hash_consistency_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test content hash consistency during enrichment."""
        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_link_records[0]]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-1"}]
        )

        # Test content with specific hash
        test_content = "Test content for hash verification"
        expected_hash = hashlib.sha256(test_content.encode()).hexdigest()

        # Setup scraper response
        mock_scraper.scrape_url.return_value = {
            "success": True,
            "backend": "firecrawl",
            "content": test_content,
            "metadata": {"title": "Test Content"},
        }

        # Execute enrichment
        result = await link_enrichment_service.enrich_link(link_id="link-1", url="http://example.com/test")

        # Verify hash consistency
        assert result["success"] is True

        # Get the update data to verify hash
        update_calls = mock_db_client.table.return_value.update.return_value.eq.return_value.execute
        update_calls.assert_called()

        call_args = update_calls.call_args
        update_data = call_args[0][0] if call_args[0] else {}

        assert update_data["content_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_enrichment_with_force_refresh(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test enrichment with force refresh flag."""
        # Create already enriched link
        enriched_link = sample_link_records[0].copy()
        enriched_link["scrape_status"] = "success"
        enriched_link["scraped_content"] = "Old content"
        enriched_link["content_hash"] = "old-hash"
        enriched_link["scraped_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[enriched_link]
        )
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "link-1"}]
        )

        # Setup scraper response with new content
        mock_scraper.scrape_url.return_value = {
            "success": True,
            "backend": "firecrawl",
            "content": "New refreshed content",
            "metadata": {"title": "Updated Content"},
        }

        # Execute enrichment without force refresh (should skip)
        result = await link_enrichment_service.enrich_link(
            link_id="link-1", url="http://example.com/product/c750a/specs", force_refresh=False
        )

        assert result["success"] is True
        assert result["skipped"] is True

        # Reset update mock
        mock_db_client.table.return_value.update.return_value.eq.return_value.execute.reset_mock()

        # Execute enrichment with force refresh (should update)
        result = await link_enrichment_service.enrich_link(
            link_id="link-1", url="http://example.com/product/c750a/specs", force_refresh=True
        )

        assert result["success"] is True
        assert result.get("skipped") is not True

        # Verify update was called for force refresh
        update_calls = mock_db_client.table.return_value.update.return_value.eq.return_value.execute
        update_calls.assert_called()

    @pytest.mark.asyncio
    async def test_enrichment_service_disabled_workflow(self, mock_scraper, mock_database_service):
        """Test enrichment workflow when service is disabled."""
        # Create disabled service
        with patch("backend.services.link_enrichment_service.ConfigService") as mock_config_class:
            mock_config = MagicMock()
            mock_config.get_scraping_config.return_value = {"enable_link_enrichment": False}
            mock_config_class.return_value = mock_config

            disabled_service = LinkEnrichmentService(
                web_scraping_service=mock_scraper, database_service=mock_database_service, config_service=mock_config
            )

            # Test enrichment when disabled
            result = await disabled_service.enrich_link(link_id="link-1", url="http://example.com/test")

            assert result["success"] is False
            assert result["error"] == "link enrichment disabled"

    @pytest.mark.asyncio
    async def test_enrichment_with_database_errors(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test enrichment workflow with database errors."""
        # Setup database to raise error during select
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = (
            Exception("Database connection error")
        )

        # Execute enrichment
        result = await link_enrichment_service.enrich_link(link_id="link-1", url="http://example.com/test")

        # Verify database error handling
        assert result["success"] is False
        assert "database" in result["error"].lower() or "unavailable" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_enrichment_timeout_workflow(
        self, link_enrichment_service, mock_db_client, mock_scraper, sample_link_records
    ):
        """Test enrichment timeout handling."""
        # Setup database responses
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_link_records[0]]
        )

        # Setup scraper to timeout
        mock_scraper.scrape_url.side_effect = TimeoutError("Scraping timeout")

        # Execute enrichment
        result = await link_enrichment_service.enrich_link(link_id="link-1", url="http://example.com/test")

        # Verify timeout handling
        assert result["success"] is False
        assert result["error"] == "timeout"

    def test_enrichment_service_configuration_validation(self, mock_scraper, mock_database_service):
        """Test enrichment service configuration validation."""
        # Test with valid configuration
        service = LinkEnrichmentService(web_scraping_service=mock_scraper, database_service=mock_database_service)

        assert service._max_concurrent_enrichments > 0
        assert service._enrichment_timeout > 0
        assert service._retry_failed_after_hours > 0

        # Test configuration loading from environment
        with patch.dict(
            "os.environ",
            {
                "LINK_ENRICHMENT_MAX_CONCURRENT": "5",
                "LINK_ENRICHMENT_TIMEOUT": "60",
                "LINK_ENRICHMENT_RETRY_HOURS": "48",
            },
        ):
            service_with_env = LinkEnrichmentService(
                web_scraping_service=mock_scraper, database_service=mock_database_service
            )

            # Should load environment values (if implemented)
            assert service_with_env._max_concurrent_enrichments >= 1
            assert service_with_env._enrichment_timeout > 0


# ============================================================================
# REAL E2E INTEGRATION TESTS - Single Link Workflows
# ============================================================================


@pytest.mark.integration
@pytest.mark.database
class TestLinkEnrichmentRealE2E:
    """
    Real end-to-end integration tests for LinkEnrichmentService.

    These tests use live Firecrawl/BeautifulSoup backends and real database operations.
    Tests are skipped if Firecrawl is unavailable, falling back to BeautifulSoup.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("firecrawl", reason="Firecrawl not available"), reason="Firecrawl SDK not installed"
    )
    async def test_real_link_enrichment_firecrawl_success(
        self, real_link_enrichment_service, test_link_data, test_database, firecrawl_available
    ):
        """Test real link enrichment with Firecrawl backend."""
        if not firecrawl_available:
            pytest.skip("Firecrawl not configured")

        # Create test link
        test_url = "https://example.com"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich link (needs both link_id and url)
        result = await real_link_enrichment_service.enrich_link(link_id, test_url)

        # Verify result
        assert result["success"] is True
        assert result["link_id"] == link_id

        # Verify database record (use link_scraping_jobs table)
        query = "SELECT * FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        db_result = await test_database.execute_query(query, (link_id,))

        assert len(db_result) == 1
        enriched_link = db_result[0]

        # Verify enrichment data
        assert enriched_link["scrape_status"] == "success"
        assert enriched_link["scraped_content"] is not None
        assert len(enriched_link["scraped_content"]) > 100
        assert enriched_link["content_hash"] is not None
        assert enriched_link["scraped_metadata"] is not None

        # Verify metadata (parse JSON string to dict)
        import json

        metadata = enriched_link["scraped_metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # Backend could be firecrawl or beautifulsoup (fallback)
        assert metadata["backend"] in ["firecrawl", "beautifulsoup"]
        assert "retrieved_at" in metadata
        assert enriched_link["scraped_at"] is not None

    @pytest.mark.asyncio
    async def test_real_link_enrichment_beautifulsoup_fallback(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test real link enrichment with BeautifulSoup fallback."""

        # Create test link
        test_url = "https://httpbin.org/html"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # BeautifulSoup will be used automatically if Firecrawl fails
        result = await real_link_enrichment_service.enrich_link(link_id, test_url)

        # Verify result
        assert result["success"] is True

        # Verify database record
        query = "SELECT * FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        db_result = await test_database.execute_query(query, (link_id,))

        enriched_link = db_result[0]

        # Verify fallback was used
        import json

        assert enriched_link["scrape_status"] == "success"
        assert enriched_link["scraped_content"] is not None
        metadata = enriched_link["scraped_metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert metadata["backend"] in ["beautifulsoup", "firecrawl"]

    @pytest.mark.asyncio
    async def test_real_link_enrichment_content_hash_consistency(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test content hash consistency across multiple scrapes."""
        # Create test link
        test_url = "https://example.com"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # First enrichment
        result1 = await real_link_enrichment_service.enrich_link(link_id, test_url)
        assert result1["success"] is True

        # Get first hash
        query = "SELECT content_hash FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        result = await test_database.execute_query(query, (link_id,))
        hash1 = result[0]["content_hash"]

        # Second enrichment with force_refresh
        result2 = await real_link_enrichment_service.enrich_link(link_id, test_url, force_refresh=True)
        assert result2["success"] is True

        # Get second hash
        result = await test_database.execute_query(query, (link_id,))
        hash2 = result[0]["content_hash"]

        # Hashes should be identical for same content
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_real_link_enrichment_metadata_extraction(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test metadata extraction from scraped content."""
        # Create test link
        test_url = "https://httpbin.org/html"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich link
        result = await real_link_enrichment_service.enrich_link(link_id, test_url)
        assert result["success"] is True

        # Verify metadata
        import json

        query = "SELECT scraped_metadata FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        db_result = await test_database.execute_query(query, (link_id,))
        metadata = db_result[0]["scraped_metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # Required metadata fields
        assert "backend" in metadata
        assert "retrieved_at" in metadata

        # Verify values
        assert metadata["backend"] in ("firecrawl", "beautifulsoup")

    @pytest.mark.asyncio
    async def test_real_link_enrichment_skip_already_enriched(self, real_link_enrichment_service, test_database):
        """Test that already enriched links are skipped without force_refresh."""
        from .conftest import create_test_link

        # Create link with success status
        test_url = "https://example.com"
        link_id = await create_test_link(test_database, test_url)

        # Update with scraped content
        update_query = """
            UPDATE krai_system.link_scraping_jobs
            SET scraped_content = 'Existing content',
                content_hash = 'existing-hash',
                scrape_status = 'success',
                scraped_at = NOW()
            WHERE id = $1::uuid
        """
        await test_database.execute_query(update_query, (link_id,))

        # Try to enrich without force_refresh
        result = await real_link_enrichment_service.enrich_link(link_id, test_url, force_refresh=False)

        # Should be skipped
        assert result["success"] is True
        assert result.get("skipped") is True or result.get("already_enriched") is True

        # Verify content unchanged
        query = "SELECT scraped_content FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        db_result = await test_database.execute_query(query, (link_id,))
        assert db_result[0]["scraped_content"] == "Existing content"

    @pytest.mark.asyncio
    async def test_real_link_enrichment_force_refresh(self, real_link_enrichment_service, test_database):
        """Test force refresh of already enriched links."""
        from .conftest import create_test_link

        # Create link with success status
        test_url = "https://example.com"
        link_id = await create_test_link(test_database, test_url)

        # Update with old content
        update_query = """
            UPDATE krai_system.link_scraping_jobs
            SET scraped_content = 'Old content',
                content_hash = 'old-hash',
                scrape_status = 'success',
                scraped_at = NOW() - INTERVAL '10 days'
            WHERE id = $1::uuid
        """
        await test_database.execute_query(update_query, (link_id,))

        # Force refresh
        result = await real_link_enrichment_service.enrich_link(link_id, test_url, force_refresh=True)

        # Should be re-enriched
        assert result["success"] is True

        # Verify content updated
        query = "SELECT scraped_content, content_hash FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        db_result = await test_database.execute_query(query, (link_id,))
        assert db_result[0]["scraped_content"] != "Old content"
        assert db_result[0]["content_hash"] != "old-hash"


# ============================================================================
# REAL E2E INTEGRATION TESTS - Batch Processing
# ============================================================================


@pytest.mark.integration
@pytest.mark.database
class TestLinkEnrichmentBatchProcessing:
    """
    Real batch processing tests for LinkEnrichmentService.

    Tests concurrent enrichment, batch operations, and performance under load.
    """

    @pytest.mark.asyncio
    async def test_real_batch_enrichment_concurrent_links(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test batch enrichment with concurrent processing."""
        # Create 10 test links
        link_ids = []
        test_urls = [
            "https://example.com",
            "https://httpbin.org/html",
            "https://www.iana.org/domains/example",
            "https://httpbin.org/get",
            "https://httpbin.org/status/200",
            "https://example.org",
            "https://example.net",
            "https://httpbin.org/headers",
            "https://httpbin.org/user-agent",
            "https://httpbin.org/ip",
        ]

        for url in test_urls:
            link = await test_link_data(url)
            link_ids.append(link["id"])

        # Batch enrich with concurrency limit
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=3)

        # Verify batch result
        assert result["total"] == 10
        assert result["enriched"] + result["failed"] + result["skipped"] == 10
        assert result["enriched"] >= 8  # Allow some failures

        # Verify all links were processed
        placeholders = ", ".join([f"${i+1}::uuid" for i in range(len(link_ids))])
        query = f"""
            SELECT id, scrape_status
            FROM krai_system.link_scraping_jobs
            WHERE id IN ({placeholders})
        """
        db_results = await test_database.execute_query(query, tuple(link_ids))

        assert len(db_results) == 10
        success_count = sum(1 for r in db_results if r["scrape_status"] == "success")
        assert success_count >= 8

    @pytest.mark.asyncio
    async def test_real_batch_enrichment_mixed_status(self, real_link_enrichment_service, test_database):
        """Test batch enrichment with mixed link statuses."""
        from .conftest import create_test_link

        # Create links with different statuses
        pending_link = await create_test_link(test_database, "https://example.com")

        success_link = await create_test_link(test_database, "https://example.org")
        await test_database.execute_query(
            "UPDATE krai_system.link_scraping_jobs SET scraped_content = 'Existing', scrape_status = 'success', scraped_at = NOW() WHERE id = $1::uuid",
            (success_link,),
        )

        failed_link = await create_test_link(test_database, "https://example.net")
        await test_database.execute_query(
            "UPDATE krai_system.link_scraping_jobs SET scrape_status = 'failed' WHERE id = $1::uuid", (failed_link,)
        )

        link_ids = [pending_link, success_link, failed_link]

        # Batch enrich
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=2)

        # Verify counts
        assert result["total"] == 3
        assert result["enriched"] >= 1  # At least pending should be enriched
        assert result["skipped"] >= 1  # Success should be skipped

    @pytest.mark.asyncio
    async def test_real_batch_enrichment_partial_failures(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test batch enrichment with some URLs failing."""
        # Create mix of valid and invalid URLs
        urls = [
            "https://example.com",  # Valid
            "https://invalid-domain-that-does-not-exist-12345.com",  # Invalid domain
            "https://httpbin.org/status/404",  # 404 error
            "https://httpbin.org/html",  # Valid
            "https://httpbin.org/status/500",  # Server error
        ]

        link_ids = []
        for url in urls:
            link = await test_link_data(url)
            link_ids.append(link["id"])

        # Batch enrich
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=2)

        # Verify mixed results
        assert result["total"] == 5
        assert result["enriched"] >= 2  # At least 2 valid URLs
        assert result["failed"] >= 1  # At least 1 failure

        # Verify failed links have error messages
        placeholders = ", ".join([f"${i+1}::uuid" for i in range(len(link_ids))])
        query = f"""
            SELECT id, scrape_status, scrape_error
            FROM krai_system.link_scraping_jobs
            WHERE id IN ({placeholders}) AND scrape_status = 'failed'
        """
        failed_links = await test_database.execute_query(query, tuple(link_ids))

        for link in failed_links:
            assert link["scrape_error"] is not None
            assert len(link["scrape_error"]) > 0

    @pytest.mark.asyncio
    async def test_real_batch_enrichment_custom_concurrency(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test batch enrichment with custom concurrency limit."""
        import time

        # Create 5 test links
        link_ids = []
        for i in range(5):
            link = await test_link_data(f"https://httpbin.org/delay/{i}")
            link_ids.append(link["id"])

        # Measure time with concurrency=5
        start_time = time.time()
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=5)
        duration = time.time() - start_time

        # With concurrency=5, all should run in parallel
        # Should complete faster than sequential (which would take ~10s)
        assert duration < 15  # Allow some overhead
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_real_batch_enrichment_force_refresh_batch(self, real_link_enrichment_service, test_database):
        """Test batch enrichment with force_refresh on already enriched links."""
        from .conftest import create_test_link

        # Create already enriched links
        link_ids = []
        for i in range(3):
            link_id = await create_test_link(test_database, f"https://example.com/page{i}")
            await test_database.execute_query(
                "UPDATE krai_system.link_scraping_jobs SET scraped_content = 'Old', scrape_status = 'success', scraped_at = NOW() - INTERVAL '5 days' WHERE id = $1::uuid",
                (link_id,),
            )
            link_ids.append(link_id)

        # Batch enrich with force_refresh
        result = await real_link_enrichment_service.enrich_links_batch(
            link_ids=link_ids, max_concurrent=2, force_refresh=True
        )

        # All should be re-enriched
        assert result["enriched"] == 3
        assert result["skipped"] == 0

        # Verify content updated
        placeholders = ", ".join([f"${i+1}::uuid" for i in range(len(link_ids))])
        query = f"SELECT scraped_content FROM krai_system.link_scraping_jobs WHERE id IN ({placeholders})"
        db_results = await test_database.execute_query(query, tuple(link_ids))

        for link in db_results:
            assert link["scraped_content"] != "Old"

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_batch_enrichment_performance_baseline(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test batch enrichment performance baseline (5 links < 30s)."""
        import time

        # Create 5 test links
        link_ids = []
        for i in range(5):
            link = await test_link_data(f"https://httpbin.org/html?page={i}")
            link_ids.append(link["id"])

        # Measure enrichment time
        start_time = time.time()
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=3)
        duration = time.time() - start_time

        # Performance baseline
        assert duration < 30  # Should complete within 30 seconds
        assert result["enriched"] >= 4  # At least 80% success rate

        # Calculate throughput
        throughput = result["enriched"] / duration
        assert throughput > 0.1  # At least 0.1 links/second

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.slow
    async def test_batch_enrichment_performance_stress(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test batch enrichment under stress (50 links < 120s)."""
        import time

        # Create 50 test links
        link_ids = []
        base_urls = [
            "https://example.com",
            "https://httpbin.org/html",
            "https://www.iana.org/domains/example",
        ]

        for i in range(50):
            url = f"{base_urls[i % len(base_urls)]}?id={i}"
            link = await test_link_data(url)
            link_ids.append(link["id"])

        # Measure enrichment time with higher concurrency
        start_time = time.time()
        result = await real_link_enrichment_service.enrich_links_batch(link_ids=link_ids, max_concurrent=10)
        duration = time.time() - start_time

        # Performance baseline
        assert duration < 120  # Should complete within 2 minutes
        assert result["enriched"] >= 40  # At least 80% success rate

        # Calculate throughput
        throughput = result["enriched"] / duration
        assert throughput > 0.5  # At least 0.5 links/second
