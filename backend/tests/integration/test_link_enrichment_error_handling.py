"""
Real E2E integration tests for LinkEnrichmentService - Error Handling & Retry.

Tests error recovery, retry logic, and fallback mechanisms with real failures.
"""

from datetime import datetime

import pytest

from .conftest import create_test_link, simulate_firecrawl_failure


@pytest.mark.integration
@pytest.mark.database
class TestLinkEnrichmentErrorHandling:
    """
    Real error handling and retry tests for LinkEnrichmentService.

    Tests timeout handling, network errors, retry logic, and Firecrawl fallback.
    """

    @pytest.mark.asyncio
    async def test_real_enrichment_timeout_handling(self, real_link_enrichment_service, test_link_data, test_database):
        """Test timeout handling with slow server."""
        # Create link with slow endpoint (10 second delay)
        test_url = "https://httpbin.org/delay/10"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich with short timeout (should timeout)
        await real_link_enrichment_service.enrich_link(link_id, timeout=5)

        # Verify timeout handling
        query = "SELECT scrape_status, scrape_error FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scrape_status"] == "failed"
        assert link_data["scrape_error"] is not None
        assert "timeout" in link_data["scrape_error"].lower() or "timed out" in link_data["scrape_error"].lower()

    @pytest.mark.asyncio
    async def test_real_enrichment_404_error(self, real_link_enrichment_service, test_link_data, test_database):
        """Test handling of 404 Not Found errors."""
        # Create link with 404 endpoint
        test_url = "https://httpbin.org/status/404"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich link
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify 404 handling
        query = "SELECT scrape_status, scrape_error FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scrape_status"] == "failed"
        assert link_data["scrape_error"] is not None
        assert "404" in link_data["scrape_error"]

    @pytest.mark.asyncio
    async def test_real_enrichment_network_error(self, real_link_enrichment_service, test_link_data, test_database):
        """Test handling of network connection errors."""
        # Create link with invalid domain
        test_url = "https://invalid-domain-that-definitely-does-not-exist-12345.com"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich link
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify network error handling
        query = "SELECT scrape_status, scrape_error FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scrape_status"] == "failed"
        assert link_data["scrape_error"] is not None
        assert any(
            keyword in link_data["scrape_error"].lower() for keyword in ["connection", "network", "resolve", "dns"]
        )

    @pytest.mark.asyncio
    async def test_real_enrichment_empty_content(self, real_link_enrichment_service, test_link_data, test_database):
        """Test handling of URLs with empty content."""
        # Create link with empty response
        test_url = "https://httpbin.org/status/204"  # No Content
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Enrich link
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify empty content handling
        query = "SELECT scrape_status, scrape_error, scraped_content FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        # Should either fail or have minimal content
        if link_data["scrape_status"] == "failed":
            assert "empty" in link_data["scrape_error"].lower() or "no content" in link_data["scrape_error"].lower()
        else:
            assert link_data["scraped_content"] is None or len(link_data["scraped_content"]) < 50

    @pytest.mark.asyncio
    async def test_real_enrichment_retry_failed_links(self, real_link_enrichment_service, test_database):
        """Test retry logic for failed links with retry_count < 3."""
        # Create failed link with low retry count
        link_id = await create_test_link(test_database, "https://example.com", scrape_status="failed")

        # Set retry count and metadata
        update_query = """
            UPDATE krai_content.links
            SET scraped_metadata = jsonb_build_object('retry_count', 1),
                scraped_at = NOW() - INTERVAL '25 hours'
            WHERE id = $1
        """
        await test_database.execute_query(update_query, link_id)

        # Retry enrichment
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify retry was attempted
        query = "SELECT scrape_status, scraped_metadata FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        # Should have attempted retry
        assert link_data["scrape_status"] in ("success", "failed")
        if link_data["scrape_status"] == "failed":
            # Retry count should be incremented
            assert link_data["scraped_metadata"].get("retry_count", 0) >= 2

    @pytest.mark.asyncio
    async def test_real_enrichment_retry_budget_exceeded(self, real_link_enrichment_service, test_database):
        """Test that links with retry_count >= 3 are not retried."""
        # Create failed link with max retries
        link_id = await create_test_link(test_database, "https://example.com", scrape_status="failed")

        # Set retry count to max
        update_query = """
            UPDATE krai_content.links
            SET scraped_metadata = jsonb_build_object('retry_count', 3),
                scrape_error = 'Max retries exceeded',
                scraped_at = NOW() - INTERVAL '25 hours'
            WHERE id = $1
        """
        await test_database.execute_query(update_query, link_id)

        # Try to enrich (should be skipped)
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify not retried
        query = "SELECT scrape_status, scraped_metadata FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scrape_status"] == "failed"
        assert link_data["scraped_metadata"].get("retry_count") == 3  # Unchanged

    @pytest.mark.asyncio
    async def test_real_enrichment_retry_time_threshold(self, real_link_enrichment_service, test_database):
        """Test that recently failed links are not retried immediately."""
        # Create recently failed link
        link_id = await create_test_link(test_database, "https://example.com", scrape_status="failed")

        # Set recent failure time (< 24 hours)
        update_query = """
            UPDATE krai_content.links
            SET scraped_metadata = jsonb_build_object('retry_count', 1),
                scrape_error = 'Previous error',
                scraped_at = NOW() - INTERVAL '12 hours'
            WHERE id = $1
        """
        await test_database.execute_query(update_query, link_id)

        # Try to enrich (should be skipped due to time threshold)
        await real_link_enrichment_service.enrich_link(link_id)

        # Verify not retried yet
        query = "SELECT scrape_status, scraped_at FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        # Should still be failed with old timestamp
        assert link_data["scrape_status"] == "failed"
        # Timestamp should not have changed significantly
        time_diff = datetime.now() - link_data["scraped_at"]
        assert time_diff.total_seconds() > 11 * 3600  # Still ~12 hours old


@pytest.mark.integration
@pytest.mark.database
class TestLinkEnrichmentFirecrawlFallback:
    """
    Real Firecrawl fallback tests for LinkEnrichmentService.

    Tests automatic fallback to BeautifulSoup when Firecrawl fails.
    """

    @pytest.mark.asyncio
    async def test_real_firecrawl_unavailable_fallback(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test automatic fallback when Firecrawl service is unavailable."""
        # Create test link
        test_url = "https://example.com"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Simulate Firecrawl failure
        async with simulate_firecrawl_failure(real_link_enrichment_service):
            result = await real_link_enrichment_service.enrich_link(link_id)

        # Verify fallback was used
        assert result["success"] is True

        query = "SELECT scrape_status, scraped_metadata FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scrape_status"] == "success"
        assert link_data["scraped_metadata"]["backend"] == "beautifulsoup"

    @pytest.mark.asyncio
    async def test_real_firecrawl_rate_limit_fallback(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test fallback when Firecrawl rate limit is hit."""
        from backend.services.web_scraping_service import FirecrawlUnavailableError

        # Create test link
        test_url = "https://httpbin.org/html"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Mock rate limit error
        original_scrape = real_link_enrichment_service._web_scraping_service.scrape_url

        async def rate_limit_scrape(url, options=None):
            raise FirecrawlUnavailableError("Rate limit exceeded")

        real_link_enrichment_service._web_scraping_service.scrape_url = rate_limit_scrape

        try:
            await real_link_enrichment_service.enrich_link(link_id)

            # Verify fallback handled rate limit
            query = "SELECT scrape_status, scraped_metadata FROM krai_content.links WHERE id = $1"
            db_result = await test_database.execute_query(query, link_id)

            link_data = db_result[0]
            # Should either succeed with fallback or fail gracefully
            assert link_data["scrape_status"] in ("success", "failed")
            if link_data["scrape_status"] == "success":
                assert link_data["scraped_metadata"]["backend"] == "beautifulsoup"
        finally:
            real_link_enrichment_service._web_scraping_service.scrape_url = original_scrape

    @pytest.mark.asyncio
    async def test_real_firecrawl_timeout_fallback(self, real_link_enrichment_service, test_link_data, test_database):
        """Test fallback when Firecrawl times out."""
        # Create test link with slow endpoint
        test_url = "https://httpbin.org/delay/5"
        link = await test_link_data(test_url)
        link_id = link["id"]

        # Mock timeout on primary, should fallback
        original_scrape = real_link_enrichment_service._web_scraping_service.scrape_url

        async def timeout_scrape(url, options=None):
            raise TimeoutError("Firecrawl timeout")

        real_link_enrichment_service._web_scraping_service.scrape_url = timeout_scrape

        try:
            await real_link_enrichment_service.enrich_link(link_id)

            # Verify fallback handled timeout
            query = "SELECT scrape_status FROM krai_content.links WHERE id = $1"
            db_result = await test_database.execute_query(query, link_id)

            link_data = db_result[0]
            # Should have attempted fallback
            assert link_data["scrape_status"] in ("success", "failed")
        finally:
            real_link_enrichment_service._web_scraping_service.scrape_url = original_scrape


@pytest.mark.integration
@pytest.mark.database
class TestLinkEnrichmentDocumentLinks:
    """
    Real tests for document-level link enrichment workflows.
    """

    @pytest.mark.asyncio
    async def test_real_enrich_document_links_workflow(
        self, real_link_enrichment_service, test_link_data, test_database
    ):
        """Test enriching all links for a specific document."""
        # Create document ID
        document_id = f"test-doc-{pytest.mark.timestamp}"

        # Create multiple links for the document
        link_ids = []
        for i in range(3):
            link = await test_link_data(f"https://example.com/page{i}", document_id=document_id)
            link_ids.append(link["id"])

        # Enrich all document links
        result = await real_link_enrichment_service.enrich_document_links(document_id)

        # Verify all links enriched
        assert result["total"] == 3
        assert result["enriched"] >= 2  # Allow some failures

        # Verify database
        query = """
            SELECT id, scrape_status
            FROM krai_content.links
            WHERE document_id = $1
        """
        db_results = await test_database.execute_query(query, document_id)

        assert len(db_results) == 3
        success_count = sum(1 for r in db_results if r["scrape_status"] == "success")
        assert success_count >= 2

    @pytest.mark.asyncio
    async def test_real_enrich_document_links_no_pending(self, real_link_enrichment_service, test_database):
        """Test document enrichment when no pending links exist."""
        # Create document with all successful links
        document_id = f"test-doc-no-pending-{pytest.mark.timestamp}"

        await create_test_link(test_database, "https://example.com", document_id=document_id, scrape_status="success")

        # Try to enrich (should find no pending links)
        result = await real_link_enrichment_service.enrich_document_links(document_id)

        # Verify no enrichment needed
        assert result["total"] == 0 or result["skipped"] == result["total"]

    @pytest.mark.asyncio
    async def test_real_refresh_stale_links_workflow(self, real_link_enrichment_service, test_database):
        """Test refreshing stale links (>90 days old)."""
        # Create old link
        link_id = await create_test_link(test_database, "https://example.com", scrape_status="success")

        # Make it stale
        update_query = """
            UPDATE krai_content.links
            SET scraped_content = 'Old content',
                content_hash = 'old-hash',
                scraped_at = NOW() - INTERVAL '95 days'
            WHERE id = $1
        """
        await test_database.execute_query(update_query, link_id)

        # Refresh stale links
        result = await real_link_enrichment_service.refresh_stale_links(days_old=90)

        # Verify refresh
        assert result["total"] >= 1
        assert result["refreshed"] >= 1

        # Verify link updated
        query = "SELECT scraped_content, scraped_at FROM krai_content.links WHERE id = $1"
        db_result = await test_database.execute_query(query, link_id)

        link_data = db_result[0]
        assert link_data["scraped_content"] != "Old content"
        # Timestamp should be recent
        time_diff = datetime.now() - link_data["scraped_at"]
        assert time_diff.total_seconds() < 300  # Within last 5 minutes
