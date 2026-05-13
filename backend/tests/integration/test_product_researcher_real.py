"""
Real integration tests for ProductResearcher service.

Tests complete product research workflows with live web scraping and LLM analysis.
"""

import asyncio
from datetime import datetime

import pytest


@pytest.mark.integration
@pytest.mark.database
class TestProductResearcherWebSearch:
    """
    Real web search and scraping tests for ProductResearcher.

    Tests Tavily search, direct search, and URL discovery workflows.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("tavily", reason="Tavily not available"), reason="Tavily SDK not installed"
    )
    async def test_real_product_research_tavily_search(self, real_product_researcher, test_database):
        """Test real product research with Tavily API search."""
        import os

        if not os.getenv("TAVILY_API_KEY"):
            pytest.skip("Tavily API key not configured")

        # Research a real product
        result = await real_product_researcher.research_product(
            manufacturer="Konica Minolta", model="bizhub C450i", use_tavily=True
        )

        # Verify search results
        assert result["success"] is True
        assert "urls" in result
        assert len(result["urls"]) > 0

        # Verify snippets if available
        if "snippets" in result:
            assert len(result["snippets"]) > 0

    @pytest.mark.asyncio
    async def test_real_product_research_direct_search(self, real_product_researcher, test_database):
        """Test product research with direct URL construction."""
        # Research without Tavily (direct search)
        result = await real_product_researcher.research_product(
            manufacturer="Canon", model="imageRUNNER ADVANCE C5560i", use_tavily=False
        )

        # Verify URL construction
        assert result["success"] is True
        assert "urls" in result
        assert len(result["urls"]) > 0

        # URLs should be manufacturer-specific
        for url in result["urls"]:
            assert "canon" in url.lower() or "imagerunner" in url.lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("firecrawl", reason="Firecrawl not available"), reason="Firecrawl SDK not installed"
    )
    async def test_real_product_research_url_discovery(
        self, real_product_researcher, test_database, firecrawl_available
    ):
        """Test URL discovery using Firecrawl map_urls."""
        if not firecrawl_available:
            pytest.skip("Firecrawl not configured")

        # Discover URLs on manufacturer website
        result = await real_product_researcher.discover_product_urls(
            manufacturer="HP", base_url="https://www.hp.com", search_term="LaserJet Enterprise"
        )

        # Verify URL discovery
        assert result["success"] is True
        assert "discovered_urls" in result
        assert len(result["discovered_urls"]) > 0


@pytest.mark.integration
@pytest.mark.database
class TestProductResearcherScraping:
    """
    Real scraping integration tests for ProductResearcher.

    Tests Firecrawl scraping, BeautifulSoup fallback, and async operations.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("firecrawl", reason="Firecrawl not available"), reason="Firecrawl SDK not installed"
    )
    async def test_real_product_research_firecrawl_scraping(
        self, real_product_researcher, test_database, firecrawl_available
    ):
        """Test real Firecrawl scraping for product research."""
        if not firecrawl_available:
            pytest.skip("Firecrawl not configured")

        # Scrape a product page
        result = await real_product_researcher.scrape_product_page(
            url="https://example.com/products", backend="firecrawl"
        )

        # Verify Firecrawl scraping
        assert result["success"] is True
        assert result["backend"] == "firecrawl"
        assert "content" in result
        assert len(result["content"]) > 100

        # Firecrawl should return Markdown
        assert "# " in result["content"] or "## " in result["content"] or "**" in result["content"]

    @pytest.mark.asyncio
    async def test_real_product_research_beautifulsoup_fallback(self, real_product_researcher, test_database):
        """Test BeautifulSoup fallback for product scraping."""
        from conftest import simulate_firecrawl_failure

        # Simulate Firecrawl failure
        async with simulate_firecrawl_failure(real_product_researcher._web_scraping_service):
            result = await real_product_researcher.scrape_product_page(url="https://httpbin.org/html")

        # Verify fallback
        assert result["success"] is True
        assert result["backend"] == "beautifulsoup"
        assert "content" in result
        assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_real_product_research_async_scraping(self, real_product_researcher, test_database):
        """Test async scraping of multiple URLs."""
        urls = ["https://example.com", "https://httpbin.org/html", "https://www.iana.org/domains/example"]

        # Scrape multiple URLs concurrently
        results = await real_product_researcher.scrape_multiple_urls(urls=urls, max_concurrent=3)

        # Verify concurrent scraping
        assert len(results) == 3
        success_count = sum(1 for r in results if r["success"])
        assert success_count >= 2  # At least 2 should succeed

        # Verify each result has content
        for result in results:
            if result["success"]:
                assert "content" in result
                assert len(result["content"]) > 0

    @pytest.mark.asyncio
    async def test_real_product_research_scraping_timeout(self, real_product_researcher, test_database):
        """Test timeout handling during scraping."""
        # Scrape slow endpoint with short timeout
        result = await real_product_researcher.scrape_product_page(url="https://httpbin.org/delay/10", timeout=5)

        # Verify timeout handling
        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()


@pytest.mark.integration
@pytest.mark.database
class TestProductResearcherLLMAnalysis:
    """
    Real LLM analysis tests for ProductResearcher.

    Tests Ollama LLM analysis, JSON parsing, and confidence scoring.
    """

    @pytest.mark.asyncio
    async def test_real_product_research_llm_analysis(self, real_product_researcher, test_database):
        """Test real LLM analysis with Ollama."""
        # Sample product content
        content = """
        # Konica Minolta bizhub C450i

        ## Specifications
        - Print Speed: 45 ppm (color and B&W)
        - Paper Size: A6 to SRA3
        - Memory: 8 GB
        - Storage: 256 GB SSD
        - Duplex: Standard

        ## Features
        - Multi-function: Print, Copy, Scan, Fax
        - Touchscreen: 10.1" tablet-style
        - Network: Gigabit Ethernet, Wi-Fi
        """

        # Analyze with LLM
        result = await real_product_researcher.analyze_product_content(
            content=content, manufacturer="Konica Minolta", model="bizhub C450i"
        )

        # Verify LLM analysis
        assert result["success"] is True
        assert "series_name" in result
        assert "specifications" in result
        assert "confidence" in result

        # Verify confidence score
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["confidence"] > 0.5  # Should be confident with good content

        # Verify specifications extracted
        specs = result["specifications"]
        assert isinstance(specs, dict)
        assert len(specs) > 0

    @pytest.mark.asyncio
    async def test_real_product_research_llm_analysis_markdown_content(self, real_product_researcher, test_database):
        """Test LLM analysis with Firecrawl Markdown content."""
        # Markdown content (Firecrawl format)
        content = """
        # Canon imageRUNNER ADVANCE C5560i

        **High-Performance Color MFP**

        ## Key Specifications
        - **Print Speed**: 60 ppm (color), 60 ppm (B&W)
        - **Paper Capacity**: 7,700 sheets maximum
        - **Finishing**: Stapling, Hole Punching, Booklet Making

        ## Technology
        - MEAP Platform for custom applications
        - uniFLOW integration
        - Advanced security features
        """

        # Analyze Markdown content
        result = await real_product_researcher.analyze_product_content(
            content=content, manufacturer="Canon", model="imageRUNNER ADVANCE C5560i"
        )

        # Verify better analysis with structured Markdown
        assert result["success"] is True
        assert result["confidence"] > 0.6  # Higher confidence with structured content

        # Verify series detection
        assert "imagerunner" in result["series_name"].lower() or "advance" in result["series_name"].lower()

    @pytest.mark.asyncio
    async def test_real_product_research_llm_analysis_insufficient_data(self, real_product_researcher, test_database):
        """Test LLM analysis with insufficient content."""
        # Minimal content
        content = "Product page. Contact us for details."

        # Analyze insufficient content
        result = await real_product_researcher.analyze_product_content(
            content=content, manufacturer="Unknown", model="Unknown Model"
        )

        # Verify low confidence
        assert result["success"] is True
        assert result["confidence"] < 0.5  # Low confidence with insufficient data

    @pytest.mark.asyncio
    async def test_real_product_research_llm_analysis_timeout(self, real_product_researcher, test_database):
        """Test LLM analysis timeout handling."""
        # Very long content that might timeout
        content = "Product specifications. " * 10000

        # Analyze with short timeout
        result = await real_product_researcher.analyze_product_content(
            content=content, manufacturer="Test", model="Test Model", timeout=5
        )

        # Verify timeout handling
        if not result["success"]:
            assert "error" in result
            assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()


@pytest.mark.integration
@pytest.mark.database
class TestProductResearcherCaching:
    """
    Real caching tests for ProductResearcher.

    Tests cache hit/miss, expiry, and force refresh.
    """

    @pytest.mark.asyncio
    async def test_real_product_research_cache_hit(self, real_product_researcher, test_database):
        """Test cache hit for previously researched product."""
        # First research (cache miss)
        result1 = await real_product_researcher.research_product(manufacturer="HP", model="LaserJet Enterprise M507")

        # Second research (cache hit)
        result2 = await real_product_researcher.research_product(manufacturer="HP", model="LaserJet Enterprise M507")

        # Verify cache hit
        assert result2["success"] is True
        assert result2.get("cached") is True or result2.get("from_cache") is True

    @pytest.mark.asyncio
    async def test_real_product_research_cache_miss(self, real_product_researcher, test_database):
        """Test cache miss for new product."""
        # Research new product
        result = await real_product_researcher.research_product(
            manufacturer="Lexmark",
            model=f"CX920de-{datetime.now().timestamp()}",  # Unique model
        )

        # Verify cache miss (new research)
        assert result["success"] is True
        assert result.get("cached") is False or "cached" not in result

    @pytest.mark.asyncio
    async def test_real_product_research_cache_expiry(self, real_product_researcher, test_database):
        """Test cache expiry for old research data."""
        # Create old cache entry
        cache_query = """
            INSERT INTO krai_intelligence.product_research_cache
            (manufacturer, model, research_data, cached_at, cache_valid_until)
            VALUES ($1, $2, $3, NOW() - INTERVAL '95 days', NOW() - INTERVAL '5 days')
        """

        await test_database.execute_query(
            cache_query, "Xerox", "VersaLink C405", {"series_name": "VersaLink", "specifications": {}}
        )

        # Research (should ignore expired cache)
        result = await real_product_researcher.research_product(manufacturer="Xerox", model="VersaLink C405")

        # Verify new research performed
        assert result["success"] is True
        assert result.get("cached") is False or result.get("cache_expired") is True

    @pytest.mark.asyncio
    async def test_real_product_research_force_refresh(self, real_product_researcher, test_database):
        """Test force refresh ignores cache."""
        # First research
        result1 = await real_product_researcher.research_product(manufacturer="Brother", model="HL-L8360CDW")

        # Force refresh (ignore cache)
        result2 = await real_product_researcher.research_product(
            manufacturer="Brother", model="HL-L8360CDW", force_refresh=True
        )

        # Verify new research performed
        assert result2["success"] is True
        assert result2.get("cached") is False


@pytest.mark.integration
@pytest.mark.database
class TestProductResearcherCompleteWorkflows:
    """
    Complete end-to-end workflow tests for ProductResearcher.

    Tests full research workflows with all components integrated.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("firecrawl", reason="Firecrawl not available"), reason="Firecrawl SDK not installed"
    )
    async def test_real_product_research_complete_workflow_firecrawl(
        self, real_product_researcher, test_database, firecrawl_available
    ):
        """Test complete product research workflow with Firecrawl."""
        if not firecrawl_available:
            pytest.skip("Firecrawl not configured")

        # Complete research workflow
        result = await real_product_researcher.research_product_complete(
            manufacturer="Ricoh", model="IM C6000", use_firecrawl=True
        )

        # Verify complete workflow
        assert result["success"] is True
        assert "series_name" in result
        assert "specifications" in result
        assert "confidence" in result
        assert "source_urls" in result

        # Verify all fields populated
        assert result["series_name"] is not None
        assert len(result["specifications"]) > 0
        assert result["confidence"] > 0.0
        assert len(result["source_urls"]) > 0

    @pytest.mark.asyncio
    async def test_real_product_research_complete_workflow_beautifulsoup(self, real_product_researcher, test_database):
        """Test complete workflow with BeautifulSoup fallback."""
        from conftest import simulate_firecrawl_failure

        # Complete workflow with fallback
        async with simulate_firecrawl_failure(real_product_researcher._web_scraping_service):
            result = await real_product_researcher.research_product_complete(
                manufacturer="Epson", model="WorkForce Pro WF-C579R"
            )

        # Verify workflow completed with fallback
        assert result["success"] is True
        assert "series_name" in result
        assert "specifications" in result

    @pytest.mark.asyncio
    async def test_real_product_research_multiple_manufacturers(self, real_product_researcher, test_database):
        """Test research for different manufacturers."""
        manufacturers = [
            ("Konica Minolta", "bizhub C360i"),
            ("Canon", "imageRUNNER ADVANCE C3530i"),
            ("HP", "Color LaserJet Enterprise M555"),
        ]

        results = []
        for manufacturer, model in manufacturers:
            result = await real_product_researcher.research_product(manufacturer=manufacturer, model=model)
            results.append(result)

        # Verify all researches completed
        assert len(results) == 3
        success_count = sum(1 for r in results if r["success"])
        assert success_count >= 2  # At least 2 should succeed

    @pytest.mark.asyncio
    async def test_real_product_research_different_product_types(self, real_product_researcher, test_database):
        """Test research for different product types."""
        products = [
            ("HP", "LaserJet Pro M404dn", "Printer"),
            ("Canon", "imageRUNNER ADVANCE DX C5870i", "MFP"),
            ("Ricoh", "Pro C7200", "Production Printer"),
        ]

        results = []
        for manufacturer, model, product_type in products:
            result = await real_product_researcher.research_product(
                manufacturer=manufacturer, model=model, product_type=product_type
            )
            results.append(result)

        # Verify all types handled
        assert len(results) == 3
        success_count = sum(1 for r in results if r["success"])
        assert success_count >= 2

    @pytest.mark.asyncio
    async def test_real_product_research_search_failure_recovery(self, real_product_researcher, test_database):
        """Test graceful error handling when search fails."""
        # Research with invalid/non-existent product
        result = await real_product_researcher.research_product(
            manufacturer="NonExistentManufacturer", model="InvalidModel12345"
        )

        # Verify graceful failure
        assert result["success"] is False
        assert "error" in result
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_real_product_research_scraping_failure_recovery(self, real_product_researcher, test_database):
        """Test error handling when scraping fails."""
        # Mock scraping failure
        original_scrape = real_product_researcher._web_scraping_service.scrape_url

        async def failing_scrape(url, options=None):
            raise Exception("Scraping failed")

        real_product_researcher._web_scraping_service.scrape_url = failing_scrape

        try:
            result = await real_product_researcher.research_product(manufacturer="Test", model="Test Model")

            # Verify error handling
            assert result["success"] is False
            assert "error" in result
        finally:
            real_product_researcher._web_scraping_service.scrape_url = original_scrape

    @pytest.mark.asyncio
    async def test_real_product_research_llm_failure_recovery(self, real_product_researcher, test_database):
        """Test error handling when LLM analysis fails."""
        # Mock LLM failure
        original_analyze = real_product_researcher.analyze_product_content

        async def failing_analyze(content, manufacturer, model, **kwargs):
            raise Exception("LLM analysis failed")

        real_product_researcher.analyze_product_content = failing_analyze

        try:
            result = await real_product_researcher.research_product(manufacturer="Test", model="Test Model")

            # Verify error handling
            assert result["success"] is False
            assert "error" in result
        finally:
            real_product_researcher.analyze_product_content = original_analyze

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_product_research_performance_baseline(self, real_product_researcher, test_database):
        """Test single product research performance baseline (<60s)."""
        import time

        # Measure research time
        start_time = time.time()
        result = await real_product_researcher.research_product(manufacturer="Kyocera", model="TASKalfa 3554ci")
        duration = time.time() - start_time

        # Performance baseline
        assert duration < 60  # Should complete within 60 seconds
        assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_product_research_concurrent_requests(self, real_product_researcher, test_database):
        """Test concurrent product research requests."""
        # Research 3 products concurrently
        tasks = [
            real_product_researcher.research_product("Sharp", "MX-3071"),
            real_product_researcher.research_product("Toshiba", "e-STUDIO 5008A"),
            real_product_researcher.research_product("OKI", "MC873dn"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no race conditions
        assert len(results) == 3
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        assert success_count >= 2  # At least 2 should succeed
