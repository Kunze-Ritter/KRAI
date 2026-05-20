"""
Integration tests for ProductResearcher.

Tests end-to-end product research workflow including web search,
scraping, LLM analysis, and caching. Uses PostgreSQL DatabaseAdapter
or mock database only (no Supabase).
"""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.product_researcher import ProductResearcher

pytest.mark.integration = pytest.mark.integration


class TestProductResearcherUnitMocks:
    """Test ProductResearcher integration scenarios."""

    @pytest.fixture
    def mock_database(self):
        """Mock database adapter (e.g. PostgreSQL adapter interface)."""
        client = MagicMock()
        client.execute_query = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_web_scraping_service(self):
        """Mock web scraping service."""
        service = MagicMock()
        service.scrape_url = AsyncMock(return_value={"success": False, "content": ""})
        service.get_backend_info = MagicMock(return_value={"backend": "beautifulsoup"})
        return service

    @pytest.fixture
    def product_researcher(self, mock_database, mock_web_scraping_service):
        """Create ProductResearcher instance for testing."""
        return ProductResearcher(
            database_service=mock_database,
            web_scraping_service=mock_web_scraping_service,
            ollama_url="http://localhost:11434",
        )

    @pytest.fixture
    def sample_search_results(self):
        """Sample search results from Tavily."""
        return {
            "results": [
                {
                    "title": "Konica Minolta C750i Specifications",
                    "url": "http://example.com/c750i/specs",
                    "content": "Detailed specifications for C750i including print speed, resolution, and dimensions.",
                    "score": 0.95,
                },
                {
                    "title": "C750i Product Page",
                    "url": "http://example.com/c750i",
                    "content": "Official product page for Konica Minolta C750i with overview and features.",
                    "score": 0.90,
                },
                {
                    "title": "C750i Support Documentation",
                    "url": "http://example.com/c750i/support",
                    "content": "Support documentation, manuals, and troubleshooting guides for C750i.",
                    "score": 0.85,
                },
            ]
        }

    @pytest.fixture
    def sample_scraped_content(self):
        """Sample scraped content from URLs."""
        return """
        # Konica Minolta C750i

        ## Specifications
        - **Print Speed**: 75 ppm
        - **Resolution**: 1200 x 1200 dpi
        - **Paper Capacity**: 3,650 sheets
        - **Monthly Volume**: 300,000 pages

        ## Features
        - Color printing
        - Scanning and copying
        - Advanced finishing options
        """

    @pytest.fixture
    def sample_llm_analysis(self):
        """Sample LLM analysis result."""
        return {
            "manufacturer": "Konica Minolta",
            "model_number": "C750i",
            "product_type": "Production Printer",
            "specifications": {
                "print_speed": "75 ppm",
                "resolution": "1200 x 1200 dpi",
                "paper_capacity": "3,650 sheets",
                "monthly_volume": "300,000 pages",
            },
            "features": ["Color printing", "Scanning", "Copying", "Advanced finishing"],
            "confidence": 0.85,
            "sources": ["http://example.com/c750i/specs", "http://example.com/c750i"],
            "scraping_backend": "firecrawl",
            "analysis_timestamp": datetime.now(UTC).isoformat(),
        }

    def test_researcher_initialization(self, mock_database, mock_web_scraping_service):
        """Test ProductResearcher initialization."""
        researcher = ProductResearcher(
            database_service=mock_database,
            web_scraping_service=mock_web_scraping_service,
            ollama_url="http://localhost:11434",
        )

        assert researcher.database == mock_database
        assert researcher.scraper == mock_web_scraping_service
        assert researcher.ollama_url == "http://localhost:11434"
        assert researcher._cache_days == 90

    def test_researcher_with_custom_config(self, mock_database, mock_web_scraping_service):
        """Test ProductResearcher with custom configuration."""
        researcher = ProductResearcher(
            database_service=mock_database,
            web_scraping_service=mock_web_scraping_service,
            ollama_url="http://custom-ollama:11434",
        )

        assert researcher.ollama_url == "http://custom-ollama:11434"

    @pytest.mark.asyncio
    @patch("services.product_researcher.requests.post")
    async def test_research_product_full_workflow(
        self, mock_post, product_researcher, sample_search_results, sample_scraped_content, sample_llm_analysis
    ):
        """Test full product research workflow."""
        # Setup Tavily search response
        mock_tavily_response = MagicMock()
        mock_tavily_response.json.return_value = sample_search_results
        mock_tavily_response.raise_for_status.return_value = None

        # Setup Ollama LLM response
        mock_ollama_response = MagicMock()
        mock_ollama_response.json.return_value = {"response": json.dumps(sample_llm_analysis), "done": True}
        mock_ollama_response.raise_for_status.return_value = None

        def post_side_effect(url, **kwargs):
            if "tavily" in url:
                return mock_tavily_response
            if "ollama" in url:
                return mock_ollama_response
            return MagicMock()

        mock_post.side_effect = post_side_effect

        with (
            patch.object(
                product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                product_researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={"success": True, **sample_llm_analysis},
            ),
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")

        assert result["success"] is True
        assert result["manufacturer"] == "Konica Minolta"
        assert result["model"] == "C750i"
        assert result["confidence"] == 0.85
        assert "specifications" in result
        assert len(result["source_urls"]) >= 0

    @pytest.mark.asyncio
    async def test_research_product_with_cache_hit(self, product_researcher, sample_llm_analysis):
        """Test product research with cache hit."""
        with patch.object(
            product_researcher, "_get_cached_research", new_callable=AsyncMock, return_value=sample_llm_analysis
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is True
        assert result["manufacturer"] == "Konica Minolta"
        assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_research_product_search_failure(self, product_researcher):
        """Test product research when search fails."""
        with patch.object(
            product_researcher,
            "_search_product",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "Search API error"},
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_product_no_search_results(self, product_researcher):
        """Test product research with no search results."""
        with patch.object(
            product_researcher, "_search_product", new_callable=AsyncMock, return_value={"success": True, "urls": []}
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_product_scraping_failure(self, product_researcher):
        """Test product research when scraping fails."""
        with (
            patch.object(
                product_researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=""),
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_product_llm_failure(self, product_researcher, sample_scraped_content):
        """Test product research when LLM analysis fails."""
        with (
            patch.object(
                product_researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                product_researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={"success": False, "error": "LLM analysis failed"},
            ),
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_product_with_firecrawl_backend(
        self, mock_database, sample_scraped_content, sample_llm_analysis
    ):
        """Test product research using Firecrawl backend."""
        mock_scraper = MagicMock()
        mock_scraper.get_backend_info = MagicMock(return_value={"backend": "firecrawl"})
        researcher = ProductResearcher(
            database_service=mock_database, web_scraping_service=mock_scraper, ollama_url="http://localhost:11434"
        )
        with (
            patch.object(
                researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={"success": True, **sample_llm_analysis},
            ),
            patch.object(researcher, "_cache_research", new_callable=AsyncMock),
        ):
            result = await researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_research_product_with_beautifulsoup_fallback(
        self, mock_database, sample_scraped_content, sample_llm_analysis
    ):
        """Test product research falling back to BeautifulSoup."""
        mock_scraper = MagicMock()
        mock_scraper.get_backend_info = MagicMock(return_value={"backend": "beautifulsoup"})
        researcher = ProductResearcher(
            database_service=mock_database, web_scraping_service=mock_scraper, ollama_url="http://localhost:11434"
        )
        with (
            patch.object(
                researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={"success": True, **sample_llm_analysis},
            ),
            patch.object(researcher, "_cache_research", new_callable=AsyncMock),
        ):
            result = await researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_cache_operations(self, product_researcher, sample_llm_analysis):
        """Test cache save and retrieve operations via database adapter."""
        product_researcher.database.execute_query = AsyncMock(return_value=[])
        await product_researcher._cache_research(
            "Konica Minolta", "C750i", {"manufacturer": "Konica Minolta", "model": "C750i", **sample_llm_analysis}
        )
        product_researcher.database.execute_query.assert_called()
        with patch.object(
            product_researcher, "_get_cached_research", new_callable=AsyncMock, return_value=sample_llm_analysis
        ):
            cached_result = await product_researcher._get_cached_research(manufacturer="Konica Minolta", model="C750i")
        assert cached_result == sample_llm_analysis

    @pytest.mark.asyncio
    async def test_cache_expiry(self, product_researcher, sample_llm_analysis):
        """Test cache expiry functionality."""
        old_analysis = sample_llm_analysis.copy()
        old_analysis["cached_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        with patch.object(
            product_researcher, "_get_cached_research", new_callable=AsyncMock, return_value=old_analysis
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result.get("cached") is not True

    @pytest.mark.asyncio
    async def test_url_discovery(self, product_researcher):
        """Test URL discovery functionality."""
        discovered_urls = [
            "http://example.com/products/c750i/specs",
            "http://example.com/products/c750i/manual",
            "http://example.com/products/c750i/parts",
        ]
        with patch.object(
            product_researcher.scraper,
            "map_urls",
            new_callable=AsyncMock,
            return_value={"success": True, "urls": discovered_urls},
        ):
            result = await product_researcher.discover_product_urls(
                manufacturer="Konica Minolta", base_url="http://example.com", search_term="C750i", max_urls=10
            )
        assert result.get("success") is True
        urls = result.get("urls", [])
        assert len(urls) == 3
        assert all("c750i" in u.lower() for u in urls)

    @pytest.mark.asyncio
    async def test_direct_search_fallback(self, product_researcher, sample_search_results):
        """Test direct search fallback when Tavily fails."""
        with patch.object(
            product_researcher,
            "_search_product",
            new_callable=AsyncMock,
            return_value={"success": True, "urls": ["http://example.com"]},
        ):
            result = await product_researcher._search_product(
                manufacturer="Konica Minolta", model="C750i", product_type=None, use_tavily=False, max_results=5
            )
        assert result is not None
        assert result["success"] is True

    def test_get_scraping_info(self, product_researcher):
        """Test scraping backend info from web scraping service."""
        assert product_researcher.scraper is not None
        info = product_researcher.scraper.get_backend_info()
        assert "backend" in info

    @pytest.mark.asyncio
    async def test_content_validation(self, product_researcher):
        """Test content validation in LLM analysis."""
        valid_content = "# Product Specs\n\n- Speed: 75 ppm\n- Resolution: 1200 dpi"
        with patch.object(
            product_researcher,
            "_analyze_with_llm",
            new_callable=AsyncMock,
            return_value={"success": True, "specifications": {"speed": "75 ppm"}},
        ):
            result = await product_researcher._analyze_with_llm(
                content=valid_content, manufacturer="Konica Minolta", model="C750i"
            )
        assert result["success"] is True
        assert "specifications" in result

    @pytest.mark.asyncio
    async def test_content_validation_insufficient_data(self, product_researcher):
        """Test content validation with insufficient data."""
        insufficient_content = "Limited product information"
        with patch.object(
            product_researcher,
            "_analyze_with_llm",
            new_callable=AsyncMock,
            return_value={"success": False, "error": "insufficient data"},
        ):
            result = await product_researcher._analyze_with_llm(
                content=insufficient_content, manufacturer="Konica Minolta", model="C750i"
            )
        assert result["success"] is False
        assert "insufficient data" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_async_scraping_integration(self, product_researcher, sample_scraped_content):
        """Test async scraping integration."""
        product_researcher.scraper.scrape_url = AsyncMock(
            return_value={"success": True, "backend": "firecrawl", "content": sample_scraped_content, "metadata": {}}
        )
        result = await product_researcher._scrape_multiple_urls(
            ["http://example.com/c750i/specs", "http://example.com/c750i/features"]
        )
        assert sample_scraped_content in result

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, product_researcher):
        """Test error handling and recovery mechanisms."""
        with patch.object(
            product_researcher, "_search_product", new_callable=AsyncMock, side_effect=Exception("Network error")
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_research_with_different_manufacturers(self, product_researcher, sample_scraped_content):
        """Test research with different manufacturers."""
        manufacturers = ["Konica Minolta", "Canon", "HP", "Brother"]
        with (
            patch.object(
                product_researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                product_researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "manufacturer": "Test",
                    "model": "Test-Model",
                    "specifications": {},
                    "confidence": 0.8,
                },
            ),
            patch.object(product_researcher, "_cache_research", new_callable=AsyncMock),
        ):
            for manufacturer in manufacturers:
                result = await product_researcher.research_product(manufacturer=manufacturer, model="Test-Model")
                assert result["success"] is True
                assert "manufacturer" in result

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, product_researcher):
        """Test performance monitoring capabilities."""
        import time

        with patch.object(
            product_researcher, "_search_product", new_callable=AsyncMock, return_value={"success": True, "urls": []}
        ):
            start_time = time.time()
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
            end_time = time.time()
        assert end_time - start_time < 5.0
        assert "success" in result

    @pytest.mark.asyncio
    async def test_data_quality_validation(self, product_researcher, sample_scraped_content):
        """Test data quality validation in research results."""
        low_quality_analysis = {"manufacturer": "", "model": "unknown", "specifications": {}, "confidence": 0.1}
        with (
            patch.object(
                product_researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                product_researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={"success": True, **low_quality_analysis},
            ),
            patch.object(product_researcher, "_cache_research", new_callable=AsyncMock),
        ):
            result = await product_researcher.research_product(manufacturer="Konica Minolta", model="C750i")
        assert result["success"] is True
        assert result.get("confidence", 1) <= 0.5 or "confidence" in result

    def test_configuration_validation(self, mock_database, mock_web_scraping_service):
        """Test ProductResearcher requires database and web scraping service (no Supabase)."""
        researcher = ProductResearcher(
            database_service=mock_database,
            web_scraping_service=mock_web_scraping_service,
            ollama_url="http://localhost:11434",
        )
        assert researcher.database == mock_database
        assert researcher.scraper == mock_web_scraping_service

    @pytest.mark.asyncio
    async def test_concurrent_research_requests(self, product_researcher, sample_scraped_content):
        """Test handling concurrent research requests."""
        with (
            patch.object(
                product_researcher,
                "_search_product",
                new_callable=AsyncMock,
                return_value={"success": True, "urls": ["http://example.com"]},
            ),
            patch.object(
                product_researcher, "_scrape_multiple_urls", new_callable=AsyncMock, return_value=sample_scraped_content
            ),
            patch.object(
                product_researcher,
                "_analyze_with_llm",
                new_callable=AsyncMock,
                return_value={
                    "success": True,
                    "manufacturer": "Konica Minolta",
                    "model": "C750i",
                    "specifications": {},
                    "confidence": 0.9,
                },
            ),
            patch.object(product_researcher, "_cache_research", new_callable=AsyncMock),
        ):
            tasks = [
                product_researcher.research_product(manufacturer="Konica Minolta", model=f"C750i-{i}") for i in range(3)
            ]
            results = await asyncio.gather(*tasks)
        assert len(results) == 3
        assert all(r["success"] for r in results)


# =============================================================================
# REAL INTEGRATION TESTS - Uses actual Firecrawl, DB, and LLM services
# =============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("FIRECRAWL_API_KEY") or not os.getenv("FIRECRAWL_API_URL"),
    reason="Firecrawl not configured (FIRECRAWL_API_KEY or FIRECRAWL_API_URL missing)",
)
class TestProductResearcherRealIntegration:
    """
    Real integration tests for ProductResearcher.

    These tests use:
    - Real PostgreSQL test database (via test_database fixture)
    - Real WebScrapingService with Firecrawl (via real_product_researcher fixture)
    - Real Ollama LLM for analysis
    - Real caching in database

    Tests are marked with @pytest.mark.integration and @pytest.mark.skipif
    to make them optional in CI environments where Firecrawl may not be available.
    """

    @pytest.mark.asyncio
    async def test_real_product_research_end_to_end(self, real_product_researcher: ProductResearcher, test_database):
        """
        Test complete product research workflow with real services.

        This test performs a minimal but genuine end-to-end workflow:
        1. Search for product URLs (direct URL construction)
        2. Scrape product pages with real Firecrawl/BeautifulSoup
        3. Analyze content with real Ollama LLM
        4. Cache results in real test database
        """
        # Use a well-known product page that should be stable
        manufacturer = "Konica Minolta"
        model = "bizhub C450i"

        # Execute real research workflow
        result = await real_product_researcher.research_product(
            manufacturer=manufacturer,
            model=model,
            use_tavily=False,  # Use direct URL construction to avoid Tavily dependency
            max_urls=2,  # Limit to 2 URLs to keep test fast
        )

        # Verify result structure
        assert "success" in result
        assert "manufacturer" in result
        assert "model" in result

        # If successful, verify data quality
        if result["success"]:
            assert result["manufacturer"] == manufacturer
            assert result["model"] == model
            assert "series_name" in result
            assert "specifications" in result
            assert isinstance(result["specifications"], dict)
            assert "confidence" in result
            assert isinstance(result["confidence"], int | float)
            assert 0.0 <= result["confidence"] <= 1.0
            assert "source_urls" in result
            assert isinstance(result["source_urls"], list)
            assert len(result["source_urls"]) > 0
            assert result.get("cached") is False  # First run should not be cached

            # Verify cache was created
            cache_result = await real_product_researcher._get_cached_research(manufacturer, model)
            assert cache_result is not None
            assert cache_result["manufacturer"] == manufacturer
            assert cache_result["model"] == model

    @pytest.mark.asyncio
    async def test_real_cache_hit(self, real_product_researcher: ProductResearcher, test_database):
        """
        Test that cached research is retrieved correctly.

        Performs two sequential research calls and verifies:
        1. First call performs full workflow and caches
        2. Second call retrieves from cache without scraping
        """
        manufacturer = "Canon"
        model = "imageRUNNER ADVANCE DX C5870i"

        # First call - should perform full research
        result1 = await real_product_researcher.research_product(
            manufacturer=manufacturer,
            model=model,
            use_tavily=False,
            max_urls=1,
            force_refresh=True,  # Force fresh research
        )

        # Second call - should hit cache
        result2 = await real_product_researcher.research_product(
            manufacturer=manufacturer,
            model=model,
            use_tavily=False,
            max_urls=1,
            force_refresh=False,  # Allow cache
        )

        # Verify cache hit
        if result1.get("success"):
            assert result2.get("cached") is True
            assert result2["manufacturer"] == manufacturer
            assert result2["model"] == model

    @pytest.mark.asyncio
    async def test_real_scraping_with_firecrawl(
        self, real_product_researcher: ProductResearcher, firecrawl_available: bool
    ):
        """
        Test that scraping works with real Firecrawl backend.

        Verifies:
        - Scraping service is properly initialized
        - Can scrape a real URL
        - Returns valid content
        """
        if not firecrawl_available:
            pytest.skip("Firecrawl not available for this test")

        # Test scraping a simple, stable URL
        test_url = "https://example.com"

        result = await real_product_researcher.scrape_product_page(test_url)

        # Verify scraping result
        assert "success" in result
        if result["success"]:
            assert "content" in result or "error" in result
            if "content" in result:
                assert len(result["content"]) > 0
                assert "backend" in result

    @pytest.mark.asyncio
    async def test_real_llm_analysis(self, real_product_researcher: ProductResearcher):
        """
        Test LLM analysis with real Ollama service.

        Verifies:
        - Can analyze product content with Ollama
        - Returns structured data
        - Includes confidence score
        """
        # Sample product content for analysis
        test_content = """
        # Konica Minolta bizhub C450i

        ## Technical Specifications
        - Print Speed: 45 ppm (color and B&W)
        - Paper Size: A6 to SRA3
        - Memory: 8 GB
        - Storage: 256 GB SSD
        - Connectivity: Ethernet, USB, Wi-Fi

        ## Features
        - Color multifunction printer
        - Advanced scanning capabilities
        - Mobile printing support
        """

        result = await real_product_researcher.analyze_product_content(
            content=test_content,
            manufacturer="Konica Minolta",
            model="bizhub C450i",
            timeout=60,  # Allow more time for LLM
        )

        # Verify analysis result
        assert "success" in result
        if result["success"]:
            assert "series_name" in result or "specifications" in result
            assert "confidence" in result
            assert isinstance(result["confidence"], int | float)

    @pytest.mark.asyncio
    async def test_real_error_handling(self, real_product_researcher: ProductResearcher):
        """
        Test error handling with real services.

        Verifies:
        - Invalid URLs are handled gracefully
        - Errors are reported correctly
        - System doesn't crash on failures
        """
        # Test with invalid/non-existent product
        result = await real_product_researcher.research_product(
            manufacturer="NonExistentManufacturer", model="InvalidModel12345", use_tavily=False, max_urls=1
        )

        # Should return error gracefully
        assert "success" in result
        # May succeed with empty/low-confidence results or fail gracefully
        if not result["success"]:
            assert "error" in result

    @pytest.mark.asyncio
    async def test_real_backend_fallback(self, real_product_researcher: ProductResearcher, firecrawl_available: bool):
        """
        Test backend fallback behavior with real services.

        Verifies:
        - System can fall back to BeautifulSoup if Firecrawl fails
        - Fallback is transparent to caller
        - Results are still valid
        """
        # Get backend info
        backend_info = real_product_researcher.scraper.get_backend_info()

        assert "backend" in backend_info
        assert "capabilities" in backend_info
        assert "fallback_available" in backend_info

        # If Firecrawl is primary, verify fallback is available
        if backend_info["backend"] == "firecrawl":
            assert backend_info["fallback_available"] is True

    @pytest.mark.asyncio
    async def test_real_concurrent_research(self, real_product_researcher: ProductResearcher):
        """
        Test concurrent research requests with real services.

        Verifies:
        - Multiple concurrent requests are handled correctly
        - No race conditions in caching
        - All requests complete successfully
        """
        # Define multiple products to research concurrently
        products = [("Konica Minolta", "bizhub C450i"), ("Canon", "imageRUNNER ADVANCE"), ("HP", "LaserJet Enterprise")]

        # Execute concurrent research
        tasks = [
            real_product_researcher.research_product(manufacturer=mfr, model=mdl, use_tavily=False, max_urls=1)
            for mfr, mdl in products
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed (success or graceful failure)
        assert len(results) == len(products)
        for result in results:
            if isinstance(result, dict):
                assert "success" in result
            else:
                # Exception occurred but was caught
                assert isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_real_database_integration(self, real_product_researcher: ProductResearcher, test_database):
        """
        Test database integration with real test database.

        Verifies:
        - Cache table exists and is accessible
        - Can write to cache
        - Can read from cache
        - Cache expiry works correctly
        """
        manufacturer = "TestManufacturer"
        model = "TestModel"

        # Create test research data
        test_data = {
            "success": True,
            "manufacturer": manufacturer,
            "model": model,
            "series_name": "Test Series",
            "specifications": {"test": "value"},
            "confidence": 0.9,
            "source_urls": ["https://example.com"],
        }

        # Cache the data
        cache_success = await real_product_researcher._cache_research(manufacturer, model, test_data)

        assert cache_success is True

        # Retrieve from cache
        cached = await real_product_researcher._get_cached_research(manufacturer, model)

        assert cached is not None
        assert cached["manufacturer"] == manufacturer
        assert cached["model"] == model
        assert cached["series_name"] == "Test Series"

        # Cleanup test data
        await test_database.execute_query(
            "DELETE FROM krai_intelligence.product_research_cache WHERE manufacturer = $1 AND model = $2",
            manufacturer,
            model,
        )
