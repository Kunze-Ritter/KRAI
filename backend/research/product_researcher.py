"""
AI-Powered Product Researcher
==============================

Automatically researches products online to extract:
- Product specifications
- Series information
- OEM relationships
- Lifecycle data

Uses:
- Web search (Tavily API or SerpAPI)
- Web scraping (Firecrawl or BeautifulSoup)
- LLM analysis (Ollama)

Firecrawl provides JavaScript rendering and LLM-ready Markdown output for improved analysis quality.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from services.config_service import ConfigService
from services.db_pool import get_pool
from services.web_scraping_service import WebScrapingService, create_web_scraping_service

logger = logging.getLogger(__name__)


class ProductResearcher:
    """
    AI-powered product researcher that extracts specs from manufacturer websites
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        cache_days: int = 90,
        scraping_backend: str | None = None,
        config_service: ConfigService | None = None,
        mock_mode: bool = False,
    ):
        """
        Initialize researcher

        Args:
            ollama_url: Ollama API URL
            model: LLM model to use
            cache_days: Days to cache research results
        """
        self.ollama_url = ollama_url
        self.model = model
        self.cache_days = cache_days
        self.config_service = config_service
        self.mock_mode = mock_mode

        # Search API (Tavily preferred, fallback to direct search)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.use_tavily = bool(self.tavily_api_key)

        # Scraping configuration
        if self.mock_mode:
            os.environ.setdefault("SCRAPING_MOCK_MODE", "true")

        self.scraping_service: WebScrapingService | None = None
        self.scraping_backend: str = "legacy"
        selected_backend = scraping_backend or os.getenv("SCRAPING_BACKEND", "beautifulsoup")

        try:
            self.scraping_service = create_web_scraping_service(
                backend=selected_backend,
                config_service=config_service,
            )
            backend_info = self.scraping_service.get_backend_info()
            self.scraping_backend = backend_info.get("backend", "legacy")
        except Exception as exc:
            logger.warning("Failed to initialise WebScrapingService (%s). Using legacy scraping.", exc)
            self.scraping_service = None

        logger.info(
            "ProductResearcher initialized (search: %s, scraping: %s)",
            "Tavily" if self.use_tavily else "Direct",
            self.scraping_backend,
        )

    async def research_product(
        self, manufacturer: str, model_number: str, force_refresh: bool = False
    ) -> dict[str, Any] | None:
        """
        Research product online and extract specifications

        Args:
            manufacturer: Manufacturer name
            model_number: Model number
            force_refresh: Force new research (ignore cache)

        Returns:
            Dictionary with research results or None
        """
        logger.info(f"Researching: {manufacturer} {model_number}")

        # Check cache first
        if not force_refresh:
            cached = await self._get_cached_research(manufacturer, model_number)
            if cached:
                logger.info(f"✓ Using cached research (confidence: {cached.get('confidence', 0):.2f})")
                return cached

        # Step 1: Web search
        search_results = self._web_search(manufacturer, model_number)
        if not search_results:
            logger.warning(f"No search results found for {manufacturer} {model_number}")
            return None

        # Step 2: Scrape content
        scraped_content = self._scrape_urls(search_results["urls"][:3])  # Top 3 results
        if not scraped_content:
            logger.warning(f"Could not scrape content for {manufacturer} {model_number}")
            return None

        # Step 3: LLM analysis
        analysis = self._llm_analyze(
            manufacturer=manufacturer,
            model_number=model_number,
            content=scraped_content,
            source_urls=search_results["urls"],
        )

        if not analysis:
            logger.warning(f"LLM analysis failed for {manufacturer} {model_number}")
            return None

        # Step 4: Save to cache
        await self._save_to_cache(manufacturer, model_number, analysis)

        logger.info(f"✓ Research complete (confidence: {analysis.get('confidence', 0):.2f})")
        return analysis

    async def _get_cached_research(self, manufacturer: str, model_number: str) -> dict | None:
        """Get cached research results"""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT * FROM krai_core.product_research_cache WHERE manufacturer = $1 AND model_number = $2 AND cache_valid_until > NOW()",
                    manufacturer,
                    model_number,
                )
                return dict(result) if result else None
        except Exception as e:
            logger.debug(f"Cache lookup failed: {e}")
            return None

    def _web_search(self, manufacturer: str, model_number: str) -> dict | None:
        """
        Search web for product information

        Returns:
            Dict with 'urls' and 'snippets'
        """
        query = f"{manufacturer} {model_number} specifications datasheet"

        if self.use_tavily:
            return self._tavily_search(query)
        return self._direct_search(query, manufacturer, model_number)

    def _tavily_search(self, query: str) -> dict | None:
        """Search using Tavily API"""
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": self.tavily_api_key, "query": query, "max_results": 5, "include_raw_content": False},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "urls": [r["url"] for r in data.get("results", [])],
                    "snippets": [r.get("content", "") for r in data.get("results", [])],
                }
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")

        return None

    def _direct_search(self, query: str, manufacturer: str, model_number: str) -> dict | None:
        """Direct search (construct URLs based on manufacturer)."""

        manufacturer_domains = {
            "konica minolta": "konicaminolta.com",
            "hp": "hp.com",
            "canon": "canon.com",
            "xerox": "xerox.com",
            "ricoh": "ricoh.com",
            "lexmark": "lexmark.com",
            "brother": "brother.com",
            "epson": "epson.com",
            "kyocera": "kyocera.com",
            "sharp": "sharp.com",
            "toshiba": "toshiba.com",
            "oki": "oki.com",
        }

        manufacturer_lower = manufacturer.lower()
        domain = manufacturer_domains.get(manufacturer_lower)

        if not domain:
            logger.warning("No known domain for manufacturer: %s", manufacturer)
            return None

        model_clean = re.sub(r"[^a-zA-Z0-9-]", "", model_number.lower())
        urls = [
            f"https://www.{domain}/products/{model_clean}",
            f"https://www.{domain}/en/products/{model_clean}",
            f"https://www.{domain}/us/products/{model_clean}",
        ]

        discovery_urls = self._discover_urls(f"https://www.{domain}", model_number)
        combined_urls: list[str] = []
        for url in urls + discovery_urls:
            if url not in combined_urls:
                combined_urls.append(url)

        return {"urls": combined_urls, "snippets": []}

    def _scrape_urls(self, urls: list[str]) -> str:
        """Scrape content from URLs, preferring async scraping service."""

        if not urls:
            return ""

        if not self.scraping_service:
            logger.debug("Scraping service unavailable; using legacy BeautifulSoup scraping")
            return self._scrape_urls_legacy(urls)

        try:
            content = self._run_async(self._scrape_urls_async(urls))
            if content:
                return content
        except Exception as exc:
            logger.warning("Async scraping failed (%s); using legacy fallback", exc)

        return self._scrape_urls_legacy(urls)

    def _scrape_urls_legacy(self, urls: list[str]) -> str:
        """Legacy synchronous BeautifulSoup scraping implementation."""

        all_content: list[str] = []
        for url in urls:
            try:
                logger.debug("Scraping (legacy): %s", url)
                response = requests.get(
                    url,
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, "html.parser")
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                text = soup.get_text(separator="\n", strip=True)
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)

                if len(text) > 10000:
                    text = text[:10000]

                all_content.append(text)
            except Exception as exc:
                logger.debug("Failed to scrape %s using legacy method: %s", url, exc)
                continue

        return "\n\n---\n\n".join(all_content)

    async def _scrape_urls_async(self, urls: list[str]) -> str:
        """Scrape URLs concurrently using async web scraping service."""

        if not self.scraping_service:
            return ""

        results = await asyncio.gather(
            *(self.scraping_service.scrape_url(url) for url in urls),
            return_exceptions=True,
        )

        contents: list[str] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.warning("Async scrape exception for %s: %s", url, result)
                continue

            if not result.get("success"):
                logger.warning(
                    "Scrape failed for %s using %s: %s",
                    url,
                    result.get("backend"),
                    result.get("error"),
                )
                continue

            backend = result.get("backend")
            logger.debug("Scraped %s using %s backend", url, backend)
            content = result.get("content") or ""
            if content:
                if len(content) > 30000:
                    content = content[:30000]
                contents.append(content)

        combined = "\n\n---\n\n".join(contents)
        if len(combined) > 30000:
            combined = combined[:30000]
        return combined

    def _run_async(self, coro: Any) -> Any:
        """Run async coroutine with graceful event loop handling."""

        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            if "event loop" in str(exc).lower() and "running" in str(exc).lower():
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(coro)
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()
            raise

    def _llm_analyze(self, manufacturer: str, model_number: str, content: str, source_urls: list[str]) -> dict | None:
        """Analyze scraped content with LLM."""

        prompt = f"""You are a technical product analyst. Analyze the following content about a printer/MFP product and extract structured information.

Product: {manufacturer} {model_number}

Content:
{content[:12000]}

Extract the following information in JSON format:

{{
    "series_name": "Product series name (e.g., 'bizhub i-Series', 'LaserJet Pro')",
    "series_description": "Brief description of the series",
    "product_type": "One of: laser_printer, inkjet_printer, laser_multifunction, inkjet_multifunction, production_printer, etc.",
    "specifications": {{
        "speed_mono": 75,
        "speed_color": 75,
        "resolution": "1200x1200 dpi",
        "paper_sizes": ["A4", "A3", "Letter"],
        "duplex": "automatic",
        "memory": "8192 MB",
        "storage": "256 GB SSD",
        "connectivity": ["USB 2.0", "Ethernet", "WiFi"],
        "scan_speed": "240 ipm",
        "monthly_duty": 300000
    }},
    "physical_specs": {{
        "dimensions": {{"width": 615, "depth": 685, "height": 1193, "unit": "mm"}},
        "weight": 145.5,
        "weight_unit": "kg",
        "power_consumption": 1500,
        "power_unit": "W"
    }},
    "oem_manufacturer": "OEM manufacturer if rebrand (or null)",
    "oem_notes": "Notes about OEM relationship",
    "launch_year": 2023,
    "confidence": 0.85
}}

IMPORTANT:
- Content may be provided in Markdown format with structured headings and lists. Use this structure to improve accuracy.
- Only include information you find in the content
- Use null for missing information
- Be conservative with confidence score
- Focus on technical specifications

Return ONLY the JSON, no other text.
"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2000,
                    },
                },
                timeout=120,
            )

            if response.status_code != 200:
                logger.error("Ollama API error: %s", response.status_code)
                return None

            result = response.json()
            response_text = result.get("response", "")

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not json_match:
                logger.error("No JSON found in LLM response")
                return None

            analysis = json.loads(json_match.group())
            analysis["source_urls"] = source_urls
            analysis["research_date"] = datetime.now().isoformat()
            analysis["scraping_backend"] = self.scraping_backend
            analysis["content_format"] = "markdown" if self.scraping_backend == "firecrawl" else "text"

            return analysis

        except Exception as exc:
            logger.error("LLM analysis failed: %s", exc)
            return None

    def _discover_urls(self, manufacturer_url: str, model_number: str) -> list[str]:
        """Discover additional URLs on manufacturer site using scraping service."""

        if not self.scraping_service or not manufacturer_url:
            return []

        backend_info: dict[str, Any] = {}
        try:
            backend_info = self.scraping_service.get_backend_info() or {}
        except Exception as exc:
            logger.debug("Failed to fetch backend info for URL discovery: %s", exc)

        capabilities = backend_info.get("capabilities") if isinstance(backend_info, dict) else None
        capability_map = {} if not isinstance(capabilities, dict) else capabilities
        capability_list = []
        if isinstance(capabilities, list | tuple | set):
            capability_list = list(capabilities)
        elif isinstance(capabilities, dict):
            capability_list = [name for name, enabled in capabilities.items() if enabled]

        has_url_mapping = (
            (isinstance(capabilities, dict) and bool(capability_map.get("url_mapping")))
            or ("url_mapping" in capability_list)
            or ("map_urls" in capability_list)
        )

        map_urls_callable = getattr(self.scraping_service, "map_urls", None)
        if not callable(map_urls_callable) and not has_url_mapping:
            logger.debug("Scraping backend lacks map_urls capability; skipping URL discovery")
            return []

        if not callable(map_urls_callable):
            logger.debug("Scraping service missing callable map_urls; skipping URL discovery")
            return []

        options = {
            "search": re.escape(model_number),
            "limit": 5,
        }

        try:
            result = self._run_async(self.scraping_service.map_urls(manufacturer_url, options=options))
            if not result.get("success"):
                logger.debug(
                    "URL discovery failed for %s: %s",
                    manufacturer_url,
                    result.get("error"),
                )
                return []

            urls = result.get("urls", [])
            filtered: list[str] = []
            model_lower = model_number.lower()
            for url in urls:
                if model_lower in url.lower() and url not in filtered:
                    filtered.append(url)

            if filtered:
                logger.info(
                    "Discovered %d URLs for %s via %s",
                    len(filtered),
                    model_number,
                    self.scraping_backend,
                )
            return filtered
        except Exception as exc:
            logger.debug("URL discovery exception for %s: %s", manufacturer_url, exc)
            return []

    def get_scraping_info(self) -> dict[str, Any]:
        """Return scraping backend diagnostic information."""

        info: dict[str, Any] = {
            "backend": self.scraping_backend,
            "service_available": bool(self.scraping_service),
        }

        if self.scraping_service:
            backend_info = self.scraping_service.get_backend_info()
            info.update(backend_info)
        else:
            info["capabilities"] = ["legacy_scrape"]
            info["fallback_count"] = 0

        return info

    async def _save_to_cache(self, manufacturer: str, model_number: str, analysis: dict):
        """Save research results to cache"""
        try:
            cache_valid_until = (datetime.now() + timedelta(days=self.cache_days)).isoformat()
            launch_date = f"{analysis.get('launch_year')}-01-01" if analysis.get("launch_year") else None

            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO krai_core.product_research_cache
                       (manufacturer, model_number, series_name, series_description, specifications,
                        physical_specs, oem_manufacturer, oem_notes, product_type, launch_date,
                        confidence, source_urls, cache_valid_until, verified)
                       VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10, $11, $12::jsonb, $13, $14)
                       ON CONFLICT (manufacturer, model_number)
                       DO UPDATE SET
                           series_name = EXCLUDED.series_name,
                           series_description = EXCLUDED.series_description,
                           specifications = EXCLUDED.specifications,
                           physical_specs = EXCLUDED.physical_specs,
                           oem_manufacturer = EXCLUDED.oem_manufacturer,
                           oem_notes = EXCLUDED.oem_notes,
                           product_type = EXCLUDED.product_type,
                           launch_date = EXCLUDED.launch_date,
                           confidence = EXCLUDED.confidence,
                           source_urls = EXCLUDED.source_urls,
                           cache_valid_until = EXCLUDED.cache_valid_until
                    """,
                    manufacturer,
                    model_number,
                    analysis.get("series_name"),
                    analysis.get("series_description"),
                    json.dumps(analysis.get("specifications", {})),
                    json.dumps(analysis.get("physical_specs", {})),
                    analysis.get("oem_manufacturer"),
                    analysis.get("oem_notes"),
                    analysis.get("product_type"),
                    launch_date,
                    analysis.get("confidence", 0.0),
                    json.dumps(analysis.get("source_urls", [])),
                    cache_valid_until,
                    False,
                )

            logger.info("✓ Saved research to cache")

        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")


if __name__ == "__main__":
    # Test mode
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        # Initialize
        researcher = ProductResearcher()

        # Test cases
        test_products = [
            ("Konica Minolta", "C750i"),
            ("HP", "LaserJet Pro M454dw"),
            ("Canon", "imageRUNNER ADVANCE C5550i"),
        ]

        if len(sys.argv) > 2:
            # Command line: python product_researcher.py "Konica Minolta" "C750i"
            manufacturer = sys.argv[1]
            model = sys.argv[2]
            test_products = [(manufacturer, model)]

        for manufacturer, model in test_products:
            print(f"\n{'='*80}")
            print(f"Researching: {manufacturer} {model}")
            print("=" * 80)

            result = await researcher.research_product(manufacturer, model)

            if result:
                print("\n✅ Research successful!")
                print(f"Confidence: {result.get('confidence', 0):.2f}")
                print(f"\nSeries: {result.get('series_name')}")
                print(f"Type: {result.get('product_type')}")
                print("\nSpecifications:")
                print(json.dumps(result.get("specifications", {}), indent=2))
            else:
                print("\n❌ Research failed")

    asyncio.run(main())
