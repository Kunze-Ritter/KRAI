"""
ProductResearcher Service

Researches products on the internet, scrapes product pages, analyzes with LLM,
and stores product information in the database.

Features:
- Web search (Tavily API or direct URL construction)
- Web scraping (Firecrawl with BeautifulSoup fallback)
- LLM analysis (Ollama)
- Caching (90-day cache)
- OEM detection and cross-referencing
"""

import asyncio
import json
import logging
import os
from typing import Any

from backend.services.database_adapter import DatabaseAdapter
from backend.services.web_scraping_service import WebScrapingService

logger = logging.getLogger(__name__)


class ProductResearcher:
    """
    Service for researching products on the internet.

    Workflow:
    1. Search for product information (Tavily or direct URLs)
    2. Scrape product pages (Firecrawl/BeautifulSoup)
    3. Analyze content with LLM (Ollama)
    4. Cache results in database
    5. Return structured product information
    """

    def __init__(
        self,
        database_service: DatabaseAdapter,
        web_scraping_service: WebScrapingService,
        ollama_url: str = "http://krai-ollama:11434",
    ):
        """
        Initialize ProductResearcher.

        Args:
            database_service: Database service for data persistence
            web_scraping_service: Web scraping service (Firecrawl/BeautifulSoup)
            ollama_url: Ollama API URL for LLM analysis
        """
        self.database = database_service
        self.scraper = web_scraping_service
        self.ollama_url = ollama_url
        self._cache_days = 90

        # Check for Tavily API
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.use_tavily = bool(self.tavily_api_key)

        if self.use_tavily:
            try:
                from tavily import TavilyClient

                self.tavily_client = TavilyClient(api_key=self.tavily_api_key)
                logger.info("Tavily API initialized for web search")
            except ImportError:
                logger.warning("Tavily SDK not installed, using direct URL construction")
                self.use_tavily = False
        else:
            logger.info("Tavily API key not found, using direct URL construction")

    async def research_product(
        self,
        manufacturer: str,
        model: str,
        product_type: str | None = None,
        use_tavily: bool | None = None,
        force_refresh: bool = False,
        max_urls: int = 5,
    ) -> dict[str, Any]:
        """
        Research a product on the internet.

        Args:
            manufacturer: Product manufacturer (e.g., "Konica Minolta")
            model: Product model (e.g., "bizhub C450i")
            product_type: Optional product type (e.g., "MFP", "Printer")
            use_tavily: Override Tavily usage (default: auto-detect)
            force_refresh: Force refresh even if cached
            max_urls: Maximum URLs to scrape

        Returns:
            Dictionary with research results:
            {
                'success': bool,
                'manufacturer': str,
                'model': str,
                'series_name': str,
                'specifications': dict,
                'confidence': float,
                'source_urls': list,
                'cached': bool,
                'error': str (if failed)
            }
        """
        try:
            # Check cache first
            if not force_refresh:
                cached = await self._get_cached_research(manufacturer, model)
                if cached:
                    logger.info(f"Cache hit for {manufacturer} {model}")
                    cached["cached"] = True
                    return cached

            # Determine search method
            use_tavily_search = use_tavily if use_tavily is not None else self.use_tavily

            # Step 1: Search for product URLs
            logger.info(f"Searching for {manufacturer} {model}")
            search_result = await self._search_product(manufacturer, model, product_type, use_tavily_search, max_urls)

            if not search_result["success"]:
                return {
                    "success": False,
                    "manufacturer": manufacturer,
                    "model": model,
                    "error": search_result.get("error", "Search failed"),
                }

            urls = search_result["urls"]
            if not urls:
                return {"success": False, "manufacturer": manufacturer, "model": model, "error": "No URLs found"}

            # Step 2: Scrape product pages
            logger.info(f"Scraping {len(urls)} URLs for {manufacturer} {model}")
            scraped_content = await self._scrape_multiple_urls(urls[:max_urls])

            if not scraped_content:
                return {"success": False, "manufacturer": manufacturer, "model": model, "error": "No content scraped"}

            # Step 3: Analyze with LLM
            logger.info(f"Analyzing content for {manufacturer} {model}")
            analysis = await self._analyze_with_llm(scraped_content, manufacturer, model)

            if not analysis["success"]:
                return {
                    "success": False,
                    "manufacturer": manufacturer,
                    "model": model,
                    "error": analysis.get("error", "LLM analysis failed"),
                }

            # Step 4: Cache results
            result = {
                "success": True,
                "manufacturer": manufacturer,
                "model": model,
                "series_name": analysis.get("series_name", ""),
                "specifications": analysis.get("specifications", {}),
                "confidence": analysis.get("confidence", 0.0),
                "source_urls": urls[:max_urls],
                "cached": False,
            }

            await self._cache_research(manufacturer, model, result)

            logger.info(f"Research complete for {manufacturer} {model} (confidence: {result['confidence']:.2f})")
            return result

        except Exception as e:
            logger.error(f"Error researching {manufacturer} {model}: {e}", exc_info=True)
            return {"success": False, "manufacturer": manufacturer, "model": model, "error": str(e)}

    async def _search_product(
        self, manufacturer: str, model: str, product_type: str | None, use_tavily: bool, max_results: int
    ) -> dict[str, Any]:
        """
        Search for product URLs.

        Uses Tavily API if available, otherwise constructs direct URLs.
        """
        try:
            if use_tavily and self.use_tavily:
                return await self._search_with_tavily(manufacturer, model, product_type, max_results)
            return await self._search_direct(manufacturer, model, product_type)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"success": False, "error": str(e)}

    async def _search_with_tavily(
        self, manufacturer: str, model: str, product_type: str | None, max_results: int
    ) -> dict[str, Any]:
        """Search using Tavily API."""
        try:
            query = f"{manufacturer} {model}"
            if product_type:
                query += f" {product_type}"
            query += " specifications datasheet"

            # Tavily search is synchronous
            response = await asyncio.to_thread(
                self.tavily_client.search, query=query, max_results=max_results, search_depth="advanced"
            )

            urls = [result["url"] for result in response.get("results", [])]
            snippets = [result.get("content", "") for result in response.get("results", [])]

            return {"success": True, "urls": urls, "snippets": snippets, "method": "tavily"}
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return {"success": False, "error": str(e)}

    async def _search_direct(self, manufacturer: str, model: str, product_type: str | None) -> dict[str, Any]:
        """Construct direct URLs based on manufacturer."""
        urls = []

        # Manufacturer-specific URL patterns
        manufacturer_lower = manufacturer.lower()
        model_clean = model.replace(" ", "-").lower()

        if "konica" in manufacturer_lower or "minolta" in manufacturer_lower:
            urls.extend(
                [
                    f"https://www.konicaminolta.eu/eu-en/hardware/{model_clean}",
                    f"https://www.konicaminolta.com/us-en/hardware/{model_clean}",
                    f"https://www.konicaminolta.eu/eu-en/search?q={model}",
                ]
            )
        elif "canon" in manufacturer_lower:
            urls.extend(
                [
                    f"https://www.canon.com/products/{model_clean}",
                    f"https://www.canon-europe.com/business-printers-and-faxes/{model_clean}",
                    f"https://www.canon.com/search?q={model}",
                ]
            )
        elif "hp" in manufacturer_lower or "hewlett" in manufacturer_lower:
            urls.extend(
                [
                    f"https://www.hp.com/us-en/shop/pdp/{model_clean}",
                    f"https://support.hp.com/us-en/product/{model_clean}",
                    f"https://www.hp.com/search?q={model}",
                ]
            )
        elif "ricoh" in manufacturer_lower:
            urls.extend(
                [
                    f"https://www.ricoh.com/products/{model_clean}",
                    f"https://www.ricoh-europe.com/products/{model_clean}",
                    f"https://www.ricoh.com/search?q={model}",
                ]
            )
        elif "xerox" in manufacturer_lower:
            urls.extend(
                [
                    f"https://www.xerox.com/en-us/office/{model_clean}",
                    f"https://www.support.xerox.com/{model_clean}",
                    f"https://www.xerox.com/search?q={model}",
                ]
            )
        else:
            # Generic search URLs
            urls.extend(
                [
                    f"https://www.google.com/search?q={manufacturer}+{model}+specifications",
                    f"https://www.bing.com/search?q={manufacturer}+{model}+datasheet",
                ]
            )

        return {"success": True, "urls": urls[:5], "method": "direct"}  # Limit to 5 URLs

    async def _scrape_multiple_urls(self, urls: list[str], max_concurrent: int = 3) -> str:
        """
        Scrape multiple URLs concurrently.

        Returns combined content from all successful scrapes.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> str | None:
            async with semaphore:
                try:
                    result = await self.scraper.scrape_url(url)
                    if result.get("success"):
                        return result.get("content", "")
                    return None
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    return None

        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine successful results
        combined_content = []
        for result in results:
            if isinstance(result, str) and result:
                combined_content.append(result)

        return "\n\n---\n\n".join(combined_content)

    async def _analyze_with_llm(self, content: str, manufacturer: str, model: str, timeout: int = 30) -> dict[str, Any]:
        """
        Analyze scraped content with Ollama LLM.

        Extracts:
        - Series name
        - Specifications
        - Confidence score
        """
        try:
            # Truncate content if too long (max 8000 chars)
            if len(content) > 8000:
                content = content[:8000] + "..."

            prompt = f"""Analyze the following product information for {manufacturer} {model}.

Extract and return ONLY a JSON object with this structure:
{{
    "series_name": "product series name",
    "specifications": {{
        "print_speed": "value",
        "paper_size": "value",
        "memory": "value",
        "storage": "value",
        "connectivity": "value"
    }},
    "confidence": 0.0-1.0
}}

Product Information:
{content}

Return ONLY the JSON object, no other text."""

            # Call Ollama API
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": os.getenv("MODEL_NAME", "llama3.2:latest"), "prompt": prompt, "stream": False},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response,
            ):
                if response.status != 200:
                    return {"success": False, "error": f"Ollama API error: {response.status}"}

                data = await response.json()
                llm_response = data.get("response", "")

                # Parse JSON from response
                try:
                    # Extract JSON from response (might have extra text)
                    json_start = llm_response.find("{")
                    json_end = llm_response.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = llm_response[json_start:json_end]
                        analysis = json.loads(json_str)

                        return {
                            "success": True,
                            "series_name": analysis.get("series_name", ""),
                            "specifications": analysis.get("specifications", {}),
                            "confidence": float(analysis.get("confidence", 0.5)),
                        }
                    return {"success": False, "error": "No JSON found in LLM response"}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    return {"success": False, "error": f"JSON parse error: {e}"}

        except TimeoutError:
            return {"success": False, "error": "LLM analysis timeout"}
        except Exception as e:
            logger.error(f"LLM analysis error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_cached_research(self, manufacturer: str, model: str) -> dict[str, Any] | None:
        """Get cached research results if available and not expired."""
        try:
            query = """
                SELECT research_data, cached_at, cache_valid_until
                FROM krai_intelligence.product_research_cache
                WHERE manufacturer = $1 AND model = $2
                AND cache_valid_until > NOW()
                LIMIT 1
            """

            result = await self.database.execute_query(query, manufacturer, model)

            if result and len(result) > 0:
                cache_entry = result[0]
                research_data = cache_entry["research_data"]
                research_data["cached"] = True
                research_data["cached_at"] = cache_entry["cached_at"]
                return research_data

            return None
        except Exception as e:
            logger.error(f"Error retrieving cache: {e}")
            return None

    async def _cache_research(self, manufacturer: str, model: str, research_data: dict[str, Any]) -> bool:
        """Cache research results in database."""
        try:
            # Remove 'cached' flag from data before storing
            data_to_cache = {k: v for k, v in research_data.items() if k != "cached"}

            query = f"""
                INSERT INTO krai_intelligence.product_research_cache
                (manufacturer, model, research_data, cached_at, cache_valid_until)
                VALUES ($1, $2, $3, NOW(), NOW() + INTERVAL '{self._cache_days} days')
                ON CONFLICT (manufacturer, model)
                DO UPDATE SET
                    research_data = EXCLUDED.research_data,
                    cached_at = NOW(),
                    cache_valid_until = NOW() + INTERVAL '{self._cache_days} days'
            """

            await self.database.execute_query(query, manufacturer, model, json.dumps(data_to_cache))

            logger.info(f"Cached research for {manufacturer} {model}")
            return True
        except Exception as e:
            logger.error(f"Error caching research: {e}")
            return False

    async def scrape_product_page(self, url: str, backend: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """
        Scrape a single product page.

        Args:
            url: URL to scrape
            backend: Force specific backend ('firecrawl' or 'beautifulsoup')
            timeout: Timeout in seconds

        Returns:
            Dictionary with scraping results
        """
        try:
            return await self.scraper.scrape_url(url, options={"timeout": timeout})
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {"success": False, "error": str(e)}

    async def discover_product_urls(
        self, manufacturer: str, base_url: str, search_term: str, max_urls: int = 10
    ) -> dict[str, Any]:
        """
        Discover product URLs using Firecrawl map_urls.

        Args:
            manufacturer: Manufacturer name
            base_url: Base URL to crawl
            search_term: Search term to filter URLs
            max_urls: Maximum URLs to discover

        Returns:
            Dictionary with discovered URLs
        """
        try:
            # Use Firecrawl map_urls if available
            if hasattr(self.scraper, "map_urls"):
                return await self.scraper.map_urls(base_url, search_term=search_term, max_urls=max_urls)
            return {"success": False, "error": "URL discovery not supported by current scraping backend"}
        except Exception as e:
            logger.error(f"Error discovering URLs: {e}")
            return {"success": False, "error": str(e)}

    async def analyze_product_content(
        self, content: str, manufacturer: str, model: str, timeout: int = 30
    ) -> dict[str, Any]:
        """
        Analyze product content with LLM (public method for testing).

        Args:
            content: Content to analyze
            manufacturer: Manufacturer name
            model: Model name
            timeout: Timeout in seconds

        Returns:
            Analysis results
        """
        return await self._analyze_with_llm(content, manufacturer, model, timeout)

    async def research_product_complete(
        self, manufacturer: str, model: str, use_firecrawl: bool = True, **kwargs
    ) -> dict[str, Any]:
        """
        Complete product research workflow (public method for testing).

        Alias for research_product with explicit backend selection.
        """
        return await self.research_product(manufacturer=manufacturer, model=model, **kwargs)
