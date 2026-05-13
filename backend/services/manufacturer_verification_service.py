"""
Manufacturer Verification Service

Web-based verification service for manufacturer, model, and parts information.
Uses Firecrawl to verify manufacturer from model numbers, discover parts, and retrieve specifications.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

from backend.services.web_scraping_service import WebScrapingService
from backend.utils.manufacturer_normalizer import normalize_manufacturer


class ManufacturerVerificationService:
    """
    Web-based verification service for manufacturer, model, and parts information.

    Uses Firecrawl to:
    1. Verify manufacturer from model number searches
    2. Verify model specifications and variants
    3. Discover parts and accessories for products
    4. Retrieve hardware specifications

    Features:
    - Firecrawl integration for web scraping
    - Result caching (90-day cache)
    - Confidence scoring
    - Fallback to BeautifulSoup if Firecrawl unavailable
    """

    def __init__(
        self,
        database_service=None,
        web_scraping_service: WebScrapingService | None = None,
        cache_days: int = 90,
        min_confidence: float = 0.7,
        max_retries: int = 3,
        timeout: int = 30,
        enable_cache: bool = True,
    ):
        """
        Initialize manufacturer verification service

        Args:
            database_service: Database service for cache storage
            web_scraping_service: Web scraping service (Firecrawl)
            cache_days: Number of days to cache results (default: 90)
            min_confidence: Minimum confidence threshold (default: 0.7)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30)
            enable_cache: Enable result caching (default: True)
        """
        self.database_service = database_service
        if web_scraping_service:
            self.web_scraping_service = web_scraping_service
        else:
            # Import here to avoid circular dependency
            from backend.services.web_scraping_service import create_web_scraping_service

            self.web_scraping_service = create_web_scraping_service()
        self.cache_days = cache_days
        self.min_confidence = min_confidence
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_cache = enable_cache

        # Manufacturer name mapping (alternative names -> database names)
        self.manufacturer_name_mapping = {
            "HP Inc.": "Hewlett Packard",
            "HP": "Hewlett Packard",
            "Hewlett-Packard": "Hewlett Packard",
            "Brother Industries": "Brother",
            "Konica Minolta Business Solutions": "Konica Minolta",
        }

        # Common manufacturer domains for targeted searches
        self.manufacturer_domains = {
            "HP Inc.": ["hp.com", "support.hp.com"],
            "Hewlett Packard": ["hp.com", "support.hp.com"],  # Mapped from HP Inc.
            "Canon": ["canon.com", "usa.canon.com"],
            "Epson": ["epson.com", "epson.co.uk"],
            "Brother": ["brother.com", "brother-usa.com"],
            "Lexmark": ["lexmark.com", "support.lexmark.com"],
            "Ricoh": ["ricoh.com", "ricoh-usa.com"],
            "Konica Minolta": ["konicaminolta.com", "konicaminolta.us"],
            "Xerox": ["xerox.com", "support.xerox.com"],
            "Kyocera": ["kyoceradocumentsolutions.com", "kyoceradocumentsolutions.us"],
        }

        # URL patterns for product pages (Strategy 1: Direct URL construction)
        self.product_url_patterns = {
            "HP Inc.": [
                "https://support.hp.com/us-en/product/hp-{model_slug}/{product_id}",
                "https://support.hp.com/us-en/drivers/printers/hp-{model_slug}",
                "https://www.hp.com/us-en/printers/{model_slug}.html",
            ],
            "Hewlett Packard": [  # Mapped from HP Inc.
                "https://support.hp.com/us-en/product/hp-{model_slug}/{product_id}",
                "https://support.hp.com/us-en/drivers/printers/hp-{model_slug}",
                "https://www.hp.com/us-en/printers/{model_slug}.html",
            ],
            "Canon": [
                "https://www.canon.de/printers/{model_slug}/",
                "https://www.canon.de/support/products/{model}.html",
                "https://www.usa.canon.com/support/p/{model}",
            ],
            "Epson": [
                "https://epson.com/Support/Printers/{model}",
                "https://www.epson.de/produkte/drucker/{model_slug}",
            ],
            "Brother": [
                "https://www.brother-usa.com/products/{model}",
                "https://support.brother.com/g/b/producttop.aspx?c=us&lang=en&prod={model}",
            ],
            "Konica Minolta": [
                "https://www.konicaminolta.eu/eu-en/hardware/{model_slug}",
                "https://www.konicaminolta.com/us-en/business/products/office-equipment/{model_slug}",
            ],
            "Lexmark": [
                "https://support.lexmark.com/en_us/printer/{model}.html",
            ],
            "Ricoh": [
                "https://www.ricoh.com/products/pd/printer/{model_slug}",
            ],
            "Xerox": [
                "https://www.xerox.com/en-us/office/{model_slug}",
                "https://www.support.xerox.com/en-us/product/{model}",
            ],
            "Kyocera": [
                "https://www.kyoceradocumentsolutions.com/en/products/{model_slug}.html",
            ],
        }

        # Google Custom Search API configuration (optional)
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

        # Perplexity AI API configuration (optional)
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")

    async def verify_manufacturer(self, model_number: str, hints: list[str] | None = None) -> dict[str, Any]:
        """
        Verify manufacturer from model number using web search

        Args:
            model_number: Product model number
            hints: Optional hints (filename, title, etc.)

        Returns:
            {
                'manufacturer': str,
                'confidence': float,
                'source_url': str,
                'cached': bool
            }
        """
        # Check cache first
        if self.enable_cache:
            cached = await self._get_from_cache("manufacturer", model_number=model_number)
            if cached:
                cached["cached"] = True
                return cached

        # Build search query
        search_query = f"{model_number} manufacturer"
        if hints:
            # Add hints to improve search accuracy
            search_query += f" {' '.join([h for h in hints if h])}"

        try:
            # Search for manufacturer information
            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"

            # Use Firecrawl to scrape search results
            scrape_result = await self.web_scraping_service.scrape_url(url=search_url)

            if not scrape_result or not scrape_result.get("success"):
                return self._create_empty_result("manufacturer")

            # Extract manufacturer from scraped content
            content = scrape_result.get("markdown", "") or scrape_result.get("html", "")
            manufacturer, confidence, source_url = self._extract_manufacturer_from_content(content, model_number)

            if manufacturer:
                result = {
                    "manufacturer": manufacturer,
                    "confidence": confidence,
                    "source_url": source_url,
                    "cached": False,
                }

                # Cache the result
                if self.enable_cache and confidence >= self.min_confidence:
                    await self._save_to_cache(
                        "manufacturer",
                        model_number=model_number,
                        data=result,
                        confidence=confidence,
                        source_url=source_url,
                    )

                return result

        except Exception as e:
            print(f"Error verifying manufacturer for {model_number}: {e}")

        return self._create_empty_result("manufacturer")

    async def verify_model(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """
        Verify model exists and extract specifications

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            {
                'exists': bool,
                'specifications': dict,
                'confidence': float,
                'cached': bool
            }
        """
        # Check cache first
        if self.enable_cache:
            cached = await self._get_from_cache("model", manufacturer=manufacturer, model_number=model_number)
            if cached:
                cached["cached"] = True
                return cached

        # Build search query
        search_query = f"{manufacturer} {model_number} specifications"

        try:
            # Get manufacturer domains for targeted search
            domains = self.manufacturer_domains.get(manufacturer, [])
            if domains:
                search_query += f" site:{domains[0]}"

            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"

            # Scrape search results
            scrape_result = await self.web_scraping_service.scrape_url(url=search_url)

            if not scrape_result or not scrape_result.get("success"):
                return self._create_empty_result("model")

            # Extract specifications from content
            content = scrape_result.get("markdown", "")
            specifications, confidence = self._extract_specifications(content, model_number)

            result = {
                "exists": bool(specifications),
                "specifications": specifications,
                "confidence": confidence,
                "cached": False,
            }

            # Cache the result
            if self.enable_cache and confidence >= self.min_confidence:
                await self._save_to_cache(
                    "model", manufacturer=manufacturer, model_number=model_number, data=result, confidence=confidence
                )

            return result

        except Exception as e:
            print(f"Error verifying model {manufacturer} {model_number}: {e}")

        return self._create_empty_result("model")

    async def discover_parts(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """
        Discover parts and accessories for a product

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            {
                'parts': List[dict],
                'confidence': float,
                'cached': bool
            }
        """
        # Check cache first
        if self.enable_cache:
            cached = await self._get_from_cache("parts", manufacturer=manufacturer, model_number=model_number)
            if cached:
                cached["cached"] = True
                return cached

        # Build search query
        search_query = f"{manufacturer} {model_number} parts accessories"

        try:
            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"

            # Scrape search results
            scrape_result = await self.web_scraping_service.scrape_url(url=search_url)

            if not scrape_result or not scrape_result.get("success"):
                return self._create_empty_result("parts")

            # Extract parts from content
            content = scrape_result.get("markdown", "")
            parts, confidence = self._extract_parts(content, model_number)

            result = {"parts": parts, "confidence": confidence, "cached": False}

            # Cache the result
            if self.enable_cache and confidence >= self.min_confidence:
                await self._save_to_cache(
                    "parts", manufacturer=manufacturer, model_number=model_number, data=result, confidence=confidence
                )

            return result

        except Exception as e:
            print(f"Error discovering parts for {manufacturer} {model_number}: {e}")

        return self._create_empty_result("parts")

    async def get_hardware_specs(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """
        Get hardware specifications for a product

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            {
                'specifications': dict,
                'confidence': float,
                'cached': bool
            }
        """
        # Check cache first
        if self.enable_cache:
            cached = await self._get_from_cache("specs", manufacturer=manufacturer, model_number=model_number)
            if cached:
                cached["cached"] = True
                return cached

        # Build search query for hardware specs
        search_query = f"{manufacturer} {model_number} hardware specifications memory storage"

        try:
            # Get manufacturer domains for targeted search
            domains = self.manufacturer_domains.get(manufacturer, [])
            if domains:
                search_query += f" site:{domains[0]}"

            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"

            # Scrape search results
            scrape_result = await self.web_scraping_service.scrape_url(url=search_url)

            if not scrape_result or not scrape_result.get("success"):
                return self._create_empty_result("specs")

            # Extract hardware specs from content
            content = scrape_result.get("markdown", "")
            specifications, confidence = self._extract_hardware_specs(content, model_number)

            result = {"specifications": specifications, "confidence": confidence, "cached": False}

            # Cache the result
            if self.enable_cache and confidence >= self.min_confidence:
                await self._save_to_cache(
                    "specs", manufacturer=manufacturer, model_number=model_number, data=result, confidence=confidence
                )

            return result

        except Exception as e:
            print(f"Error getting hardware specs for {manufacturer} {model_number}: {e}")

        return self._create_empty_result("specs")

    def _extract_manufacturer_from_content(
        self, content: str, model_number: str
    ) -> tuple[str | None, float, str | None]:
        """
        Extract manufacturer name from scraped content

        Returns:
            (manufacturer_name, confidence, source_url)
        """
        if not content:
            return None, 0.0, None

        # Common manufacturer patterns in search results
        manufacturer_patterns = [
            r"(?:by|from|manufacturer[:\s]+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+" + re.escape(model_number),
            r"(?:HP|Canon|Epson|Brother|Lexmark|Ricoh|Konica\s+Minolta|Xerox|Kyocera)",
        ]

        manufacturers_found = {}

        for pattern in manufacturer_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                manufacturer = match.group(1) if match.lastindex else match.group(0)
                manufacturer = manufacturer.strip()

                # Normalize manufacturer name
                normalized = normalize_manufacturer(manufacturer)
                if normalized:
                    manufacturers_found[normalized] = manufacturers_found.get(normalized, 0) + 1

        if not manufacturers_found:
            return None, 0.0, None

        # Get most frequent manufacturer
        manufacturer = max(manufacturers_found, key=manufacturers_found.get)
        occurrences = manufacturers_found[manufacturer]

        # Calculate confidence based on occurrences
        confidence = min(0.5 + (occurrences * 0.1), 1.0)

        # Try to extract source URL
        source_url = self._extract_source_url(content)

        return manufacturer, confidence, source_url

    def _extract_specifications(self, content: str, model_number: str) -> tuple[dict[str, Any], float]:
        """Extract product specifications from content"""
        specifications = {}
        confidence = 0.0

        if not content:
            return specifications, confidence

        # Look for specification patterns
        spec_patterns = {
            "print_speed": r"(?:print\s+speed|ppm)[:\s]+(\d+)",
            "resolution": r"(?:resolution|dpi)[:\s]+(\d+\s*x\s*\d+)",
            "paper_size": r"(?:paper\s+size|media)[:\s]+([A-Z0-9,\s]+)",
            "connectivity": r"(?:connectivity|interface)[:\s]+([A-Za-z0-9,\s/]+)",
        }

        for key, pattern in spec_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specifications[key] = match.group(1).strip()
                confidence += 0.2

        # Check if model number appears in content
        if model_number.lower() in content.lower():
            confidence += 0.3

        confidence = min(confidence, 1.0)

        return specifications, confidence

    def _extract_parts(self, content: str, model_number: str) -> tuple[list[dict[str, Any]], float]:
        """Extract parts information from content"""
        parts = []
        confidence = 0.0

        if not content:
            return parts, confidence

        # Look for part number patterns
        part_patterns = [
            r"(?:part\s+(?:number|#)|p/n)[:\s]+([A-Z0-9-]+)",
            r"([A-Z0-9]{5,})\s+(?:toner|drum|fuser|roller)",
        ]

        parts_found = set()

        for pattern in part_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                part_number = match.group(1).strip()
                if part_number not in parts_found:
                    parts_found.add(part_number)
                    parts.append({"part_number": part_number, "type": "unknown"})

        if parts:
            confidence = min(0.5 + (len(parts) * 0.1), 1.0)

        return parts, confidence

    def _extract_hardware_specs(self, content: str, model_number: str) -> tuple[dict[str, Any], float]:
        """Extract hardware specifications from content"""
        specifications = {}
        confidence = 0.0

        if not content:
            return specifications, confidence

        # Look for hardware spec patterns
        hw_patterns = {
            "memory": r"(?:memory|ram)[:\s]+(\d+\s*(?:MB|GB))",
            "storage": r"(?:storage|hard\s+drive|hdd|ssd)[:\s]+(\d+\s*(?:MB|GB|TB))",
            "processor": r"(?:processor|cpu)[:\s]+([A-Za-z0-9\s]+)",
            "network": r"(?:network|ethernet)[:\s]+([A-Za-z0-9/\s]+)",
        }

        for key, pattern in hw_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specifications[key] = match.group(1).strip()
                confidence += 0.2

        # Check if model number appears in content
        if model_number.lower() in content.lower():
            confidence += 0.3

        confidence = min(confidence, 1.0)

        return specifications, confidence

    def _extract_source_url(self, content: str) -> str | None:
        """Extract source URL from content"""
        # Look for URL patterns
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        match = re.search(url_pattern, content)
        return match.group(0) if match else None

    async def _get_from_cache(
        self, verification_type: str, manufacturer: str | None = None, model_number: str | None = None
    ) -> dict[str, Any] | None:
        """Get verification result from cache"""
        if not self.database_service or not hasattr(self.database_service, "client"):
            return None

        try:
            # Generate cache key
            cache_key = self._generate_cache_key(verification_type, manufacturer, model_number)

            # Query cache table
            if not hasattr(self.database_service, "client") or self.database_service.client is None:
                return None

            result = (
                self.database_service.client.schema("krai_intelligence")
                .from_("manufacturer_verification_cache")
                .select("*")
                .eq("cache_key", cache_key)
                .execute()
            )

            if result.data and len(result.data) > 0:
                cache_entry = result.data[0]

                # Check if cache is still valid
                cache_valid_until = datetime.fromisoformat(cache_entry["cache_valid_until"].replace("Z", "+00:00"))
                if datetime.now(cache_valid_until.tzinfo) < cache_valid_until:
                    # Cache is valid, return data
                    return cache_entry["verification_data"]

        except Exception as e:
            print(f"Error reading from cache: {e}")

        return None

    async def _save_to_cache(
        self,
        verification_type: str,
        data: dict[str, Any],
        confidence: float,
        manufacturer: str | None = None,
        model_number: str | None = None,
        source_url: str | None = None,
    ):
        """Save verification result to cache"""
        if not self.database_service or not hasattr(self.database_service, "client"):
            return

        try:
            # Generate cache key
            cache_key = self._generate_cache_key(verification_type, manufacturer, model_number)

            # Calculate cache validity
            cache_valid_until = datetime.utcnow() + timedelta(days=self.cache_days)

            # Prepare cache entry
            cache_entry = {
                "verification_type": verification_type,
                "cache_key": cache_key,
                "manufacturer": manufacturer,
                "model_number": model_number,
                "verification_data": data,
                "confidence": confidence,
                "source_url": source_url,
                "cache_valid_until": cache_valid_until.isoformat(),
            }

            # Upsert to cache table
            if not hasattr(self.database_service, "client") or self.database_service.client is None:
                return

            self.database_service.client.schema("krai_intelligence").from_("manufacturer_verification_cache").upsert(
                cache_entry, on_conflict="cache_key"
            ).execute()

        except Exception as e:
            print(f"Error saving to cache: {e}")

    def _generate_cache_key(
        self, verification_type: str, manufacturer: str | None = None, model_number: str | None = None
    ) -> str:
        """Generate cache key from verification parameters"""
        key_parts = [verification_type]
        if manufacturer:
            key_parts.append(manufacturer.lower())
        if model_number:
            key_parts.append(model_number.lower())

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _create_empty_result(self, verification_type: str) -> dict[str, Any]:
        """Create empty result for failed verification"""
        if verification_type == "manufacturer":
            return {"manufacturer": None, "confidence": 0.0, "source_url": None, "cached": False}
        if verification_type == "model":
            return {"exists": False, "specifications": {}, "confidence": 0.0, "cached": False}
        if verification_type == "parts":
            return {"parts": [], "confidence": 0.0, "cached": False}
        if verification_type == "specs":
            return {"specifications": {}, "confidence": 0.0, "cached": False}

        return {}

    async def discover_product_page(
        self, manufacturer: str, model_number: str, save_to_db: bool = True
    ) -> dict[str, Any]:
        """
        Discover official product page URL using multiple strategies

        Strategy 1: Try URL patterns (fast, reliable)
        Strategy 2: Perplexity AI (AI-powered search with citations)
        Strategy 3: Google Custom Search API (if API key available)
        Strategy 4: Web scraping fallback (current method)

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number
            save_to_db: Automatically save discovered product to database (default: True)

        Returns:
            {
                'url': str,
                'source': str,  # 'pattern', 'perplexity', 'google_api', 'scraping'
                'confidence': float,
                'verified': bool,  # True if URL was verified to exist
                'answer': str,  # AI-generated answer (Perplexity only)
                'product_id': str  # UUID if saved to DB
            }
        """
        # Use manufacturer name as-is (no mapping needed - HP Inc. is the correct name)

        # Strategy 1: Try URL patterns (TEMPORARILY DISABLED - Firecrawl timeouts)
        # pattern_result = await self._try_url_patterns(manufacturer, model_number)
        # if pattern_result:
        #     if save_to_db:
        #         await self._save_product_to_db(manufacturer, model_number, pattern_result)
        #     return pattern_result

        print("Skipping URL patterns (Firecrawl timeouts), trying alternative strategies...")

        # Strategy 2: Google Custom Search API (if configured) - FASTEST & MOST RELIABLE
        print(f"Google API configured: {bool(self.google_api_key and self.google_search_engine_id)}")
        if self.google_api_key and self.google_search_engine_id:
            print(f"Trying Google Custom Search API for {manufacturer} {model_number}...")
            api_result = await self._google_custom_search(manufacturer, model_number)
            if api_result:
                print(f"✅ Found via Google API: {api_result['url']}")

                # Extract specifications from the discovered URL (optional - don't fail if scraping fails)
                try:
                    print("🔍 Extracting specifications from URL...")
                    specs = await self.extract_specifications_from_url(api_result["url"], manufacturer, model_number)
                    if specs:
                        api_result["specifications"] = specs
                        print(f"✅ Extracted {len(specs)} specification fields")
                    else:
                        print("⚠️  No specifications extracted (scraping returned empty)")
                except Exception as e:
                    print(f"⚠️  Could not extract specifications: {e}")
                    # Continue without specs - URL discovery is still successful

                if save_to_db:
                    await self._save_product_to_db(manufacturer, model_number, api_result)
                return api_result
            print("Google API: No results found")

        # Strategy 3: Perplexity AI (if configured) - AI-POWERED FALLBACK
        print(f"Perplexity API Key configured: {bool(self.perplexity_api_key)}")
        if self.perplexity_api_key:
            perplexity_result = await self._perplexity_search(manufacturer, model_number)
            if perplexity_result:
                # Extract specifications from the discovered URL (optional - don't fail if scraping fails)
                try:
                    print("🔍 Extracting specifications from URL...")
                    specs = await self.extract_specifications_from_url(
                        perplexity_result["url"], manufacturer, model_number
                    )
                    if specs:
                        perplexity_result["specifications"] = specs
                        print(f"✅ Extracted {len(specs)} specification fields")
                    else:
                        print("⚠️  No specifications extracted (scraping returned empty)")
                except Exception as e:
                    print(f"⚠️  Could not extract specifications: {e}")
                    # Continue without specs - URL discovery is still successful

                if save_to_db:
                    await self._save_product_to_db(manufacturer, model_number, perplexity_result)
                return perplexity_result

        # Strategy 4: Fallback to web scraping
        scraping_result = await self._scrape_for_product_page(manufacturer, model_number)
        if scraping_result and save_to_db:
            await self._save_product_to_db(manufacturer, model_number, scraping_result)
        return scraping_result

    async def _try_url_patterns(self, manufacturer: str, model_number: str) -> dict[str, Any] | None:
        """
        Try to construct product page URL from known patterns

        Returns URL if pattern exists and page is accessible
        """
        patterns = self.product_url_patterns.get(manufacturer, [])
        if not patterns:
            return None

        # Create model slug (lowercase, replace spaces with hyphens)
        model_slug = model_number.lower().replace(" ", "-").replace("_", "-")

        # Try each pattern
        for pattern in patterns:
            # Simple pattern substitution (product_id would need to be discovered separately)
            if "{product_id}" in pattern:
                continue  # Skip patterns requiring product_id for now

            url = pattern.format(model=model_number, model_slug=model_slug)

            # Verify URL exists
            try:
                # Try to scrape with redirect following
                result = await self.web_scraping_service.scrape_url(url)
                if result and result.get("success"):
                    content = result.get("content", "")
                    # Verify model number is mentioned in content (flexible matching)
                    model_variants = [
                        model_number.lower(),
                        model_number.replace(" ", "").lower(),
                        model_number.replace("-", "").lower(),
                        model_slug,
                    ]

                    content_lower = content.lower()
                    if any(variant in content_lower for variant in model_variants):
                        return {"url": url, "source": "pattern", "confidence": 0.9, "verified": True}
            except Exception:
                # Try lowercase variant of URL (Brother uses lowercase)
                if url != url.lower():
                    try:
                        url_lower = url.lower()
                        result = await self.web_scraping_service.scrape_url(url_lower)
                        if result and result.get("success"):
                            content = result.get("content", "")
                            model_variants = [model_number.lower(), model_number.replace(" ", "").lower(), model_slug]
                            content_lower = content.lower()
                            if any(variant in content_lower for variant in model_variants):
                                return {"url": url_lower, "source": "pattern", "confidence": 0.9, "verified": True}
                    except:
                        pass
                # URL doesn't exist or error accessing it
                continue

        return None

    async def _perplexity_search(self, manufacturer: str, model_number: str) -> dict[str, Any] | None:
        """
        Use Perplexity AI to find product page with AI-powered search

        Perplexity provides direct answers with citations/sources
        """
        print(f"Calling Perplexity AI for {manufacturer} {model_number}...")
        try:
            from perplexity import Perplexity

            print("Perplexity module imported successfully")

            # Initialize Perplexity client
            client = Perplexity(api_key=self.perplexity_api_key)

            # Construct search query - be more specific about US/EN sites
            domains = self.manufacturer_domains.get(manufacturer, [])

            # Prefer DE-DE sites with EN fallback
            preferred_sites = {
                "HP Inc.": "support.hp.com/de-de",
                "Canon": "canon.de",
                "Brother": "brother.de",
                "Epson": "epson.de",
                "Lexmark": "lexmark.de",
                "Ricoh": "ricoh.de",
                "Konica Minolta": "konicaminolta.de",
                "Xerox": "xerox.de",
                "Kyocera": "kyoceradocumentsolutions.de",
            }

            site_filter = f" site:{preferred_sites.get(manufacturer, domains[0] if domains else '')}"

            query = f"Was ist die EXAKTE offizielle {manufacturer} Support-Seite URL für das Drucker-Modell {model_number}? Suche nach der vollständigen Produktserie (z.B. 'E877z' nicht nur 'E877'). Die URL sollte die Modellnummer oder Serie-ID enthalten. Akzeptiere deutsche (.de, de-de) UND englische (us-en, en-us) Seiten. Gib NUR die direkte URL zur Treiber- oder Spezifikationsseite an."

            print(f"Sending query to Perplexity: {query[:100]}...")

            # Call Perplexity API
            response = client.chat.completions.create(
                model="sonar",  # Perplexity Sonar model with web search
                messages=[
                    {
                        "role": "system",
                        "content": f"Du bist ein hilfreicher Assistent, der offizielle Produktseiten findet. Akzeptiere deutsche Seiten (.de, de-de) UND englische Seiten (us-en, en-us) von {manufacturer} gleichwertig. Vermeide andere regionale Seiten (ng-en, fr-fr, es-es, jp-jp).",
                    },
                    {"role": "user", "content": query},
                ],
            )

            print("Perplexity API response received")

            # Extract answer and citations
            answer = response.choices[0].message.content
            citations = getattr(response, "citations", [])

            print(f"Answer: {answer[:200]}...")
            print(f"Citations count: {len(citations)}")

            # Extract URLs from citations first (most reliable)
            candidate_urls = []

            for citation in citations:
                if isinstance(citation, str):
                    candidate_urls.append(citation)
                elif isinstance(citation, dict) and "url" in citation:
                    candidate_urls.append(citation["url"])

            # Extract URLs from answer text
            import re

            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            found_urls = re.findall(url_pattern, answer)
            candidate_urls.extend(found_urls)

            # Score and rank URLs
            scored_urls = []
            for url in candidate_urls:
                score = 0
                url_lower = url.lower()

                # Check if URL is from manufacturer domain
                domain_match = False
                for domain in domains if domains else []:
                    if domain in url_lower:
                        domain_match = True
                        score += 10
                        break

                if not domain_match:
                    continue  # Skip non-manufacturer URLs

                # DE-DE and EN sites equally preferred
                if any(region in url_lower for region in [".de/", "de-de", ".de?", ".de#"]) or any(
                    region in url_lower for region in ["us-en", "usa.", "/us/", "/en-us/", "en-gb", ".com/en"]
                ):
                    score += 8

                # Avoid other regional sites
                if any(region in url_lower for region in ["ng-en", "fr-fr", "es-es", "jp-jp", "it-it", "nl-nl"]):
                    score -= 10

                # Prefer support/product pages
                if any(keyword in url_lower for keyword in ["support", "product", "driver", "specification", "spec"]):
                    score += 3

                # Prefer URLs with model number or series
                model_clean = model_number.lower().replace("-", "").replace(" ", "")
                url_clean = url_lower.replace("-", "").replace(" ", "")

                if model_clean in url_clean:
                    score += 5

                # Extra points for URLs with series IDs (e.g., /2101127729)
                if re.search(r"/\d{8,}", url):
                    score += 3

                # Extra points for "series" in URL
                if "series" in url_lower:
                    score += 2

                # Prefer "managed" or specific product lines
                if any(keyword in url_lower for keyword in ["managed", "enterprise", "pro", "mfp"]):
                    score += 2

                scored_urls.append((score, url))

            # Sort by score (highest first)
            scored_urls.sort(reverse=True, key=lambda x: x[0])

            # Return best URL with all alternatives
            if scored_urls and scored_urls[0][0] > 0:
                best_url = scored_urls[0][1]
                confidence = min(0.95, 0.70 + (scored_urls[0][0] / 100))

                # Include top 3 alternatives for transparency
                alternatives = [{"url": url, "score": score} for score, url in scored_urls[1:4]]

                return {
                    "url": best_url,
                    "source": "perplexity",
                    "confidence": confidence,
                    "verified": True,
                    "answer": answer,
                    "citations": citations,
                    "score": scored_urls[0][0],
                    "alternatives": alternatives,  # Top 3 alternative URLs
                }

        except Exception as e:
            print(f"Perplexity AI search error: {e}")

        return None

    async def _save_product_to_db(
        self, manufacturer: str, model_number: str, discovery_result: dict[str, Any]
    ) -> str | None:
        """
        Save discovered product to database with specifications

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number
            discovery_result: Result from product page discovery

        Returns:
            Product UUID if saved successfully, None otherwise
        """
        if not self.database_service:
            return None

        try:
            # Get manufacturer_id
            manufacturer_query = """
                SELECT id FROM krai_core.manufacturers
                WHERE name = %s
                LIMIT 1
            """
            manufacturer_result = await self.database_service.fetch_one(manufacturer_query, (manufacturer,))

            if not manufacturer_result:
                print(f"Manufacturer '{manufacturer}' not found in database")
                return None

            manufacturer_id = manufacturer_result["id"]

            # Check if product already exists
            product_check_query = """
                SELECT id, specifications, urls, metadata
                FROM krai_core.products
                WHERE manufacturer_id = %s AND model_number = %s
                LIMIT 1
            """
            existing_product = await self.database_service.fetch_one(
                product_check_query, (manufacturer_id, model_number)
            )

            # Prepare product data
            urls_data = {
                "product_page": discovery_result.get("url"),
                "source": discovery_result.get("source"),
                "discovered_at": datetime.utcnow().isoformat(),
                "verified": discovery_result.get("verified", False),
            }

            metadata_data = {
                "discovery_confidence": discovery_result.get("confidence", 0.0),
                "discovery_source": discovery_result.get("source"),
                "discovery_answer": discovery_result.get("answer"),
                "citations": discovery_result.get("citations", []),
                "score": discovery_result.get("score", 0),
            }

            specifications_data = {}

            # Extract specifications from Perplexity answer if available
            if discovery_result.get("answer"):
                answer = discovery_result.get("answer", "")
                # Try to extract specs from answer (basic extraction)
                if "ppm" in answer.lower():
                    import re

                    speed_match = re.search(r"(\d+)\s*ppm", answer.lower())
                    if speed_match:
                        specifications_data["print_speed_ppm"] = int(speed_match.group(1))

            if existing_product:
                # Update existing product
                product_id = existing_product["id"]

                # Merge with existing data (ensure they are dicts)
                existing_urls = existing_product.get("urls") or {}
                if isinstance(existing_urls, str):
                    existing_urls = {}

                existing_metadata = existing_product.get("metadata") or {}
                if isinstance(existing_metadata, str):
                    existing_metadata = {}

                existing_specs = existing_product.get("specifications") or {}
                if isinstance(existing_specs, str):
                    existing_specs = {}

                urls_data = {**existing_urls, **urls_data}
                metadata_data = {**existing_metadata, **metadata_data}
                specifications_data = {**existing_specs, **specifications_data}

                update_query = """
                    UPDATE krai_core.products
                    SET
                        urls = %s::jsonb,
                        metadata = %s::jsonb,
                        specifications = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """

                await self.database_service.fetch_one(
                    update_query,
                    (json.dumps(urls_data), json.dumps(metadata_data), json.dumps(specifications_data), product_id),
                )

                print(f"✅ Updated product in DB: {manufacturer} {model_number} (ID: {product_id})")
                discovery_result["product_id"] = str(product_id)
                return str(product_id)

            # Insert new product
            insert_query = """
                    INSERT INTO krai_core.products (
                        manufacturer_id,
                        model_number,
                        urls,
                        metadata,
                        specifications,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, NOW(), NOW())
                    RETURNING id
                """

            result = await self.database_service.fetch_one(
                insert_query,
                (
                    manufacturer_id,
                    model_number,
                    json.dumps(urls_data),
                    json.dumps(metadata_data),
                    json.dumps(specifications_data),
                ),
            )

            if result:
                product_id = result["id"]
                print(f"✅ Saved new product to DB: {manufacturer} {model_number} (ID: {product_id})")
                discovery_result["product_id"] = str(product_id)
                return str(product_id)

        except Exception as e:
            print(f"Error saving product to database: {e}")
            import traceback

            traceback.print_exc()

        return None

    async def extract_specifications_with_search(
        self, manufacturer: str, model_number: str, save_to_db: bool = True
    ) -> dict[str, Any]:
        """
        Extract specifications using Firecrawl Cloud API Search

        Searches for PUBLIC specification sources:
        - Product pages (support.hp.com, etc.)
        - Datasheets (publicly available PDFs)
        - Spec sheets

        Does NOT search for service manuals (behind login walls)

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number
            save_to_db: Save extracted specs to database (default: True)

        Returns:
            {
                'specifications': dict,
                'confidence': float,
                'sources': list,
                'product_id': str  # If saved to DB
            }
        """
        print(f"🔍 Extracting specifications for {manufacturer} {model_number} using Firecrawl Search...")

        # Build search queries (no "manual"!)
        search_queries = [
            f"{manufacturer} {model_number} specifications",
            f"{manufacturer} {model_number} datasheet",
            f"{manufacturer} {model_number} specs",
        ]

        all_specs = {}
        sources = []

        try:
            # Try each search query
            for query in search_queries:
                print(f"   Searching: {query}")

                # Use Firecrawl Cloud API Search
                search_results = await self._firecrawl_cloud_search(query, limit=3)

                if not search_results:
                    continue

                print(f"   Found {len(search_results)} results")

                # Extract specs from each result
                for result in search_results:
                    url = result.get("url", "")
                    markdown = result.get("markdown", "")

                    if not markdown:
                        continue

                    # Parse specifications from markdown
                    specs = self._parse_specifications_from_markdown(markdown, model_number)

                    if specs:
                        print(f"   ✅ Extracted {len(specs)} specs from {url[:50]}...")
                        all_specs.update(specs)
                        if url not in sources:
                            sources.append(url)

                # If we have good specs, no need to try more queries
                if len(all_specs) >= 5:
                    break

            # Calculate confidence based on source count and spec count
            confidence = min(0.95, 0.5 + (len(sources) * 0.1) + (len(all_specs) * 0.02))

            result = {
                "specifications": all_specs,
                "confidence": confidence,
                "sources": sources,
                "extracted_count": len(all_specs),
            }

            print(
                f"✅ Extracted {len(all_specs)} specifications from {len(sources)} sources (confidence: {confidence:.2f})"
            )

            # Save to database if requested
            if save_to_db and all_specs:
                product_id = await self._update_product_specifications(
                    manufacturer, model_number, all_specs, sources[0] if sources else None
                )
                if product_id:
                    result["product_id"] = product_id

            return result

        except Exception as e:
            print(f"❌ Error extracting specifications with search: {e}")
            import traceback

            traceback.print_exc()
            return {"specifications": {}, "confidence": 0.0, "sources": [], "error": str(e)}

    async def extract_specifications_with_agent(
        self, manufacturer: str, model_number: str, save_to_db: bool = True
    ) -> dict[str, Any]:
        """
        Extract specifications using Firecrawl Agent (AI-powered)

        Uses Firecrawl's /v2/agent endpoint to:
        - Automatically find best sources
        - Extract ALL model configurations (including speed upgrades)
        - Provide structured data with citations
        - Handle complex multi-variant products

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number
            save_to_db: Save extracted specs to database (default: True)

        Returns:
            {
                'model_configurations': list,  # All model variants
                'confidence': float,
                'sources': list,
                'credits_used': int,
                'product_id': str  # If saved to DB
            }
        """
        print(f"🤖 Extracting specifications for {manufacturer} {model_number} using Firecrawl Agent...")

        try:
            import asyncio
            import os

            import httpx

            firecrawl_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")
            api_key = os.getenv("FIRECRAWL_API_KEY", "")

            if not api_key or api_key == "fc-local-dev-key-not-required":
                print("⚠️  No valid Firecrawl API key - skipping agent")
                return {"model_configurations": [], "confidence": 0.0, "sources": [], "error": "No API key"}

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Define schema for structured output with nested hardware_specs and accessories
            schema = {
                "type": "object",
                "properties": {
                    "model_configurations": {
                        "type": "array",
                        "description": "All available model configurations and variants",
                        "items": {
                            "type": "object",
                            "properties": {
                                "model_name": {"type": "string", "description": "Full model name"},
                                "model_name_citation": {"type": "string", "description": "URL citation for model name"},
                                "variant_type": {
                                    "type": "string",
                                    "description": "Variant type: dn (Standard), z, Flow, etc.",
                                },
                                "variant_type_citation": {
                                    "type": "string",
                                    "description": "URL citation for variant type",
                                },
                                "hardware_specs": {
                                    "type": "object",
                                    "properties": {
                                        "print_speed": {
                                            "type": "string",
                                            "description": "Print speed with all upgrade options",
                                        },
                                        "print_speed_citation": {"type": "string"},
                                        "paper_capacity": {
                                            "type": "string",
                                            "description": "Standard and optional paper capacity",
                                        },
                                        "paper_capacity_citation": {"type": "string"},
                                        "dimensions": {"type": "string", "description": "Physical dimensions"},
                                        "dimensions_citation": {"type": "string"},
                                        "weight": {"type": "string", "description": "Weight"},
                                        "weight_citation": {"type": "string"},
                                        "other_technical_details": {
                                            "type": "object",
                                            "description": "Additional technical specifications",
                                            "properties": {
                                                "processor": {"type": "string"},
                                                "memory": {"type": "string"},
                                                "storage": {"type": "string"},
                                                "display": {"type": "string"},
                                                "connectivity": {"type": "string"},
                                                "scan_speed": {"type": "string"},
                                                "copy_speed": {"type": "string"},
                                                "duty_cycle": {"type": "string"},
                                                "recommended_monthly_volume": {"type": "string"},
                                                "power_consumption": {"type": "string"},
                                                "resolution": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                                "key_features": {
                                    "type": "array",
                                    "description": "Key features and capabilities of the model",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "feature_name": {"type": "string", "description": "Feature name"},
                                            "feature_name_citation": {"type": "string"},
                                            "description": {"type": "string", "description": "Feature description"},
                                            "description_citation": {"type": "string"},
                                            "is_flow_exclusive": {
                                                "type": "boolean",
                                                "description": "Whether feature is exclusive to Flow models",
                                            },
                                            "is_flow_exclusive_citation": {"type": "string"},
                                        },
                                        "required": ["feature_name", "description"],
                                    },
                                },
                                "accessories_and_supplies": {
                                    "type": "array",
                                    "description": "All compatible accessories, supplies, and parts",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "category": {
                                                "type": "string",
                                                "description": "Category: Speed Upgrades, Consumables, Finishing, Paper Handling, Customization, Connectivity, Storage, Security, Fax, Other Accessories",
                                            },
                                            "category_citation": {"type": "string"},
                                            "name": {"type": "string", "description": "Accessory name"},
                                            "name_citation": {"type": "string"},
                                            "part_number": {"type": "string", "description": "Part number"},
                                            "part_number_citation": {"type": "string"},
                                            "description": {"type": "string", "description": "Description"},
                                            "description_citation": {"type": "string"},
                                        },
                                        "required": ["category", "name", "part_number"],
                                    },
                                },
                            },
                            "required": ["model_name", "hardware_specs"],
                        },
                    }
                },
                "required": ["model_configurations"],
            }

            # Start agent job
            payload = {
                "prompt": f"Extract all {manufacturer} {model_number} model configurations with complete specifications, features, and accessories. For each variant, include: 1) Model name and variant type (dn/z/Flow), 2) Hardware specs (print speed with upgrade options, paper capacity, dimensions, weight, technical details), 3) Key features (scan features, security, software, document processing, copy features, print languages) with is_flow_exclusive flag, 4) All accessories and supplies with detailed categories (Toner Cartridges - Standard/High Yield, Maintenance Kits - Flow/DN Specific, Finishers, Paper Handling, Connectivity, Security, etc.). Provide citation URLs for each field.",
                "schema": schema,
                "maxCredits": 100,  # Allow more credits for complex products with many accessories
                "strictConstrainToURLs": False,  # Let agent find best sources
            }

            async with httpx.AsyncClient(timeout=300.0) as client:
                # Start agent job
                print("   Starting Firecrawl Agent job...")
                response = await client.post(f"{firecrawl_url}/v2/agent", json=payload, headers=headers)

                if response.status_code != 200:
                    print(f"⚠️  Agent job failed: HTTP {response.status_code}")
                    return {
                        "model_configurations": [],
                        "confidence": 0.0,
                        "sources": [],
                        "error": f"HTTP {response.status_code}",
                    }

                job_data = response.json()
                if not job_data.get("success"):
                    print(f"⚠️  Agent job failed: {job_data}")
                    return {
                        "model_configurations": [],
                        "confidence": 0.0,
                        "sources": [],
                        "error": "Job creation failed",
                    }

                job_id = job_data.get("id")
                print(f"   Job ID: {job_id}")
                print("   Waiting for agent to complete...")

                # Poll for completion
                max_attempts = 60  # 5 minutes max
                attempt = 0

                while attempt < max_attempts:
                    await asyncio.sleep(5)  # Wait 5 seconds between polls
                    attempt += 1

                    status_response = await client.get(f"{firecrawl_url}/v2/agent/{job_id}", headers=headers)

                    if status_response.status_code != 200:
                        print(f"⚠️  Status check failed: HTTP {status_response.status_code}")
                        continue

                    status_data = status_response.json()
                    status = status_data.get("status")

                    print(f"   Status: {status} (attempt {attempt}/{max_attempts})")

                    if status == "completed":
                        data = status_data.get("data", {})
                        credits_used = status_data.get("creditsUsed", 0)

                        model_configs = data.get("model_configurations", [])
                        print(f"✅ Agent completed! Found {len(model_configs)} model configurations")
                        print(f"   Credits used: {credits_used}")

                        # Extract sources from citations (nested structure)
                        sources = set()
                        for config in model_configs:
                            # Top-level citations
                            for field in ["model_name_citation", "variant_type_citation"]:
                                if config.get(field):
                                    sources.add(config[field])

                            # Hardware specs citations
                            hardware = config.get("hardware_specs", {})
                            for key, value in hardware.items():
                                if key.endswith("_citation") and value:
                                    sources.add(value)

                            # Key features citations
                            features = config.get("key_features", [])
                            for feature in features:
                                for key, value in feature.items():
                                    if key.endswith("_citation") and value:
                                        sources.add(value)

                            # Accessories citations
                            accessories = config.get("accessories_and_supplies", [])
                            for accessory in accessories:
                                for key, value in accessory.items():
                                    if key.endswith("_citation") and value:
                                        sources.add(value)

                        result = {
                            "model_configurations": model_configs,
                            "confidence": 0.95,  # Agent results are high confidence
                            "sources": list(sources),
                            "credits_used": credits_used,
                            "extracted_count": len(model_configs),
                        }

                        # Save to database if requested
                        if save_to_db and model_configs:
                            # Save primary configuration (first one)
                            primary_config = model_configs[0]
                            specs = self._convert_agent_config_to_specs(primary_config)

                            product_id = await self._update_product_specifications(
                                manufacturer, model_number, specs, primary_config.get("model_name_citation")
                            )

                            if product_id:
                                result["product_id"] = product_id

                                # Get manufacturer_id for parts catalog
                                manufacturer_id = await self._get_manufacturer_id(manufacturer)

                                # Save accessories to parts catalog and link to product
                                if manufacturer_id and primary_config.get("accessories_and_supplies"):
                                    accessories_count = await self._save_accessories_to_parts_catalog(
                                        product_id, manufacturer_id, primary_config["accessories_and_supplies"]
                                    )
                                    result["accessories_saved"] = accessories_count
                                    print(f"   💾 Saved {accessories_count} accessories to parts catalog")

                                # Store all configurations in metadata
                                await self._update_product_metadata(product_id, {"agent_configurations": model_configs})

                        return result

                    if status == "failed":
                        error = status_data.get("error", "Unknown error")
                        print(f"❌ Agent failed: {error}")
                        return {"model_configurations": [], "confidence": 0.0, "sources": [], "error": error}

                print("⚠️  Agent timeout - job did not complete in time")
                return {"model_configurations": [], "confidence": 0.0, "sources": [], "error": "Timeout"}

        except Exception as e:
            print(f"❌ Error extracting specifications with agent: {e}")
            import traceback

            traceback.print_exc()
            return {"model_configurations": [], "confidence": 0.0, "sources": [], "error": str(e)}

    def _convert_agent_config_to_specs(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Convert agent configuration to specification format for database storage

        Args:
            config: Agent configuration dictionary with hardware_specs and accessories_and_supplies

        Returns:
            Specifications dictionary
        """
        specs = {}

        # Extract hardware specs
        hardware = config.get("hardware_specs", {})

        # Map hardware fields to spec fields
        field_mapping = {
            "print_speed": "print_speed",
            "paper_capacity": "paper_capacity",
            "dimensions": "dimensions",
            "weight": "weight",
        }

        for agent_field, spec_field in field_mapping.items():
            if agent_field in hardware:
                specs[spec_field] = hardware[agent_field]

        # Handle other technical details
        if "other_technical_details" in hardware:
            tech = hardware["other_technical_details"]
            specs.update(
                {
                    "processor": tech.get("processor"),
                    "memory": tech.get("memory"),
                    "storage": tech.get("storage"),
                    "display": tech.get("display"),
                    "connectivity": tech.get("connectivity"),
                    "scan_speed": tech.get("scan_speed"),
                    "copy_speed": tech.get("copy_speed"),
                    "duty_cycle": tech.get("duty_cycle"),
                    "recommended_monthly_volume": tech.get("recommended_monthly_volume"),
                    "power_consumption": tech.get("power_consumption"),
                    "resolution": tech.get("resolution"),
                }
            )

        # Remove None values
        return {k: v for k, v in specs.items() if v is not None}

    async def _get_manufacturer_id(self, manufacturer_name: str) -> str:
        """
        Get manufacturer ID by name

        Args:
            manufacturer_name: Manufacturer name

        Returns:
            Manufacturer UUID or None
        """
        if not self.database_service:
            return None

        try:
            result = await self.database_service.fetch_one(
                """
                SELECT id FROM krai_core.manufacturers
                WHERE name = $1
                """,
                manufacturer_name,
            )
            return result["id"] if result else None
        except Exception as e:
            print(f"Error getting manufacturer ID: {e}")
            return None

    async def _save_accessories_to_parts_catalog(
        self, product_id: str, manufacturer_id: str, accessories: list[dict[str, Any]]
    ) -> int:
        """
        Save accessories to krai_parts.parts_catalog and link to product

        Args:
            product_id: Product UUID
            manufacturer_id: Manufacturer UUID
            accessories: List of accessory dictionaries from agent

        Returns:
            Number of accessories saved
        """
        if not self.database_service:
            return 0

        saved_count = 0

        try:
            for accessory in accessories:
                part_number = accessory.get("part_number")
                if not part_number:
                    continue

                # Check if part already exists
                existing = await self.database_service.fetch_one(
                    """
                    SELECT id FROM krai_parts.parts_catalog
                    WHERE part_number = $1 AND manufacturer_id = $2
                    """,
                    part_number,
                    manufacturer_id,
                )

                if not existing:
                    # Insert new part
                    part_id = await self.database_service.fetch_val(
                        """
                        INSERT INTO krai_parts.parts_catalog (
                            manufacturer_id, part_number, part_name,
                            part_description, part_category
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        manufacturer_id,
                        part_number,
                        accessory.get("name"),
                        accessory.get("description"),
                        accessory.get("category"),
                    )
                else:
                    part_id = existing["id"]

                # Link to product via krai_core.product_accessories
                await self.database_service.execute(
                    """
                    INSERT INTO krai_core.product_accessories (
                        product_id, accessory_part_id,
                        is_optional, compatibility_notes
                    )
                    VALUES ($1, $2, true, $3)
                    ON CONFLICT (product_id, accessory_part_id) DO NOTHING
                    """,
                    product_id,
                    part_id,
                    f"Category: {accessory.get('category', 'Unknown')}",
                )

                saved_count += 1

            return saved_count

        except Exception as e:
            print(f"Error saving accessories to parts catalog: {e}")
            import traceback

            traceback.print_exc()
            return saved_count

    async def _update_product_metadata(self, product_id: str, metadata: dict[str, Any]) -> bool:
        """
        Update product metadata in database
        """
        if not self.database_service:
            return False

        try:
            query = """
                UPDATE krai_core.products
                SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb,
                    updated_at = NOW()
                WHERE id = $2
            """

            await self.database_service.execute(query, metadata, product_id)

            return True

        except Exception as e:
            print(f"Error updating product metadata: {e}")
            return False

    async def _firecrawl_cloud_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search using Firecrawl Cloud API /v1/search endpoint

        Args:
            query: Search query
            limit: Number of results to return

        Returns:
            List of search results with markdown content
        """
        try:
            import os

            import httpx

            firecrawl_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")
            api_key = os.getenv("FIRECRAWL_API_KEY", "")

            if not api_key or api_key == "fc-local-dev-key-not-required":
                print("⚠️  No valid Firecrawl API key - skipping search")
                return []

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "query": query,
                "limit": limit,
                "lang": "en",
                "country": "us",
                "scrapeOptions": {
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                },
            }

            url = f"{firecrawl_url}/v1/search"

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("data", [])
                else:
                    print(f"⚠️  Firecrawl search failed: HTTP {response.status_code}")

        except Exception as e:
            print(f"⚠️  Firecrawl search error: {e}")

        return []

    def _parse_specifications_from_markdown(self, markdown: str, model_number: str) -> dict[str, Any]:
        """
        Parse specifications from markdown content

        Extracts common printer/MFP specifications:
        - Print speed (ppm)
        - Resolution (dpi)
        - Paper sizes
        - Memory, storage
        - Connectivity
        - Dimensions, weight
        - Power consumption
        """
        specs = {}

        if not markdown:
            return specs

        markdown_lower = markdown.lower()

        # Print Speed (ppm)
        import re

        # Color print speed
        color_speed_patterns = [
            r"(?:color|colour).*?(\d+)\s*ppm",
            r"(\d+)\s*ppm.*?(?:color|colour)",
            r"print\s+speed.*?color.*?(\d+)\s*ppm",
        ]
        for pattern in color_speed_patterns:
            match = re.search(pattern, markdown_lower)
            if match:
                specs["print_speed_color_ppm"] = int(match.group(1))
                break

        # Mono print speed
        mono_speed_patterns = [
            r"(?:mono|black|b/w|monochrome).*?(\d+)\s*ppm",
            r"(\d+)\s*ppm.*?(?:mono|black|b/w)",
            r"print\s+speed.*?(?:mono|black).*?(\d+)\s*ppm",
        ]
        for pattern in mono_speed_patterns:
            match = re.search(pattern, markdown_lower)
            if match:
                specs["print_speed_mono_ppm"] = int(match.group(1))
                break

        # If only one speed mentioned, use for both
        if "print_speed_color_ppm" not in specs and "print_speed_mono_ppm" not in specs:
            speed_match = re.search(r"(\d+)\s*ppm", markdown_lower)
            if speed_match:
                speed = int(speed_match.group(1))
                specs["print_speed_ppm"] = speed

        # Resolution
        resolution_patterns = [r"(\d+)\s*x\s*(\d+)\s*dpi", r"resolution.*?(\d+)\s*x\s*(\d+)", r"(\d{3,4})\s*dpi"]
        for pattern in resolution_patterns:
            match = re.search(pattern, markdown_lower)
            if match:
                if len(match.groups()) == 2:
                    specs["print_resolution_dpi"] = f"{match.group(1)} x {match.group(2)}"
                else:
                    specs["print_resolution_dpi"] = match.group(1)
                break

        # Memory
        memory_patterns = [
            r"(\d+)\s*gb\s+(?:ram|memory)",
            r"(?:ram|memory).*?(\d+)\s*gb",
            r"(\d+)\s*mb\s+(?:ram|memory)",
        ]
        for pattern in memory_patterns:
            match = re.search(pattern, markdown_lower)
            if match:
                value = int(match.group(1))
                if "gb" in pattern:
                    specs["memory_gb"] = value
                else:
                    specs["memory_mb"] = value
                break

        # Storage
        storage_patterns = [r"(\d+)\s*gb\s+(?:hdd|ssd|storage|hard\s+drive)", r"(?:hdd|ssd|storage).*?(\d+)\s*gb"]
        for pattern in storage_patterns:
            match = re.search(pattern, markdown_lower)
            if match:
                specs["storage_gb"] = int(match.group(1))
                break

        # Paper sizes
        paper_sizes = []
        if "a4" in markdown_lower:
            paper_sizes.append("A4")
        if "letter" in markdown_lower:
            paper_sizes.append("Letter")
        if "legal" in markdown_lower:
            paper_sizes.append("Legal")
        if "a5" in markdown_lower:
            paper_sizes.append("A5")
        if "a3" in markdown_lower:
            paper_sizes.append("A3")
        if paper_sizes:
            specs["paper_sizes"] = paper_sizes

        # Duplex
        if any(word in markdown_lower for word in ["automatic duplex", "auto duplex", "two-sided"]):
            specs["duplex"] = "automatic"
        elif "duplex" in markdown_lower:
            specs["duplex"] = "manual"

        # Connectivity
        connectivity = []
        if "usb" in markdown_lower:
            connectivity.append("USB")
        if any(word in markdown_lower for word in ["ethernet", "gigabit", "rj-45"]):
            connectivity.append("Ethernet")
        if any(word in markdown_lower for word in ["wifi", "wi-fi", "wireless", "802.11"]):
            connectivity.append("WiFi")
        if connectivity:
            specs["connectivity"] = connectivity

        # Dimensions (mm)
        dimension_match = re.search(r"(\d{3,4})\s*x\s*(\d{3,4})\s*x\s*(\d{3,4})\s*mm", markdown_lower)
        if dimension_match:
            specs["dimensions_mm"] = {
                "width": int(dimension_match.group(1)),
                "depth": int(dimension_match.group(2)),
                "height": int(dimension_match.group(3)),
            }

        # Weight
        weight_match = re.search(r"(\d+\.?\d*)\s*kg", markdown_lower)
        if weight_match:
            specs["weight_kg"] = float(weight_match.group(1))

        # Power consumption
        power_match = re.search(r"(\d+)\s*w(?:att)?", markdown_lower)
        if power_match:
            specs["power_consumption_w"] = int(power_match.group(1))

        return specs

    async def extract_specifications_from_url(
        self, product_url: str, manufacturer: str, model_number: str
    ) -> dict[str, Any]:
        """
        Extract specifications from a product page URL

        Args:
            product_url: URL of the product page
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            Dictionary of extracted specifications
        """
        try:
            # Scrape product page
            scrape_result = await self.web_scraping_service.scrape_url(product_url)

            if not scrape_result or not scrape_result.get("success"):
                print("⚠️  Could not scrape product page")
                return {}

            content = scrape_result.get("content", "")

            if not content:
                print("⚠️  No content extracted from page")
                return {}

            # Extract specifications using Perplexity AI if available
            if self.perplexity_api_key:
                specs = await self._extract_specs_with_perplexity(manufacturer, model_number, content)
            else:
                # Fallback: Basic regex extraction
                specs = self._extract_specs_basic(content)

            return specs

        except Exception as e:
            print(f"Error extracting specifications from URL: {e}")
            return {}

    async def extract_and_save_specifications(
        self, manufacturer: str, model_number: str, product_url: str | None = None
    ) -> dict[str, Any]:
        """
        Extract specifications from product page and save to database

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number
            product_url: Optional product page URL (will discover if not provided)

        Returns:
            {
                'specifications': dict,
                'product_id': str,
                'source_url': str,
                'extracted_at': str
            }
        """
        # Discover product page if not provided
        if not product_url:
            discovery_result = await self.discover_product_page(manufacturer, model_number, save_to_db=True)
            product_url = discovery_result.get("url")

            if not product_url:
                return {"specifications": {}, "error": "Could not find product page"}

        # Scrape product page for specifications
        try:
            scrape_result = await self.web_scraping_service.scrape_url(product_url)

            if not scrape_result or not scrape_result.get("success"):
                return {"specifications": {}, "error": "Could not scrape product page"}

            content = scrape_result.get("content", "")

            # Extract specifications using Perplexity AI
            if self.perplexity_api_key:
                specs = await self._extract_specs_with_perplexity(manufacturer, model_number, content)
            else:
                # Fallback: Basic regex extraction
                specs = self._extract_specs_basic(content)

            # Save specifications to database
            if self.database_service and specs:
                await self._update_product_specifications(manufacturer, model_number, specs, product_url)

            return {"specifications": specs, "source_url": product_url, "extracted_at": datetime.utcnow().isoformat()}

        except Exception as e:
            print(f"Error extracting specifications: {e}")
            return {"specifications": {}, "error": str(e)}

    async def _extract_specs_with_perplexity(
        self, manufacturer: str, model_number: str, page_content: str
    ) -> dict[str, Any]:
        """
        Use Perplexity AI to extract structured specifications from page content
        """
        try:
            from perplexity import Perplexity

            client = Perplexity(api_key=self.perplexity_api_key)

            # Truncate content to avoid token limits
            content_preview = page_content[:3000]

            query = f"""
            Extrahiere die technischen Spezifikationen für {manufacturer} {model_number} aus folgendem Text.

            Gib die Daten als strukturiertes JSON zurück mit folgenden Feldern (falls vorhanden):
            - print_speed_ppm (Druckgeschwindigkeit in Seiten pro Minute)
            - print_resolution_dpi (Druckauflösung in DPI)
            - paper_sizes (unterstützte Papierformate als Array)
            - connectivity (Verbindungsoptionen als Array: USB, Ethernet, WiFi, etc.)
            - memory_mb (Arbeitsspeicher in MB)
            - processor_mhz (Prozessor in MHz)
            - duplex (automatischer Duplexdruck: true/false)
            - color (Farbdruck: true/false)
            - monthly_duty_cycle (monatliche Druckleistung)

            Text:
            {content_preview}
            """

            response = client.chat.completions.create(
                model="sonar",
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein Experte für Drucker-Spezifikationen. Extrahiere nur verifizierte technische Daten. Gib die Antwort als valides JSON zurück.",
                    },
                    {"role": "user", "content": query},
                ],
            )

            answer = response.choices[0].message.content

            # Try to parse JSON from answer
            import re

            json_match = re.search(r"\{.*\}", answer, re.DOTALL)
            if json_match:
                specs = json.loads(json_match.group(0))
                return specs

            # Fallback: Parse from text
            return self._extract_specs_basic(answer)

        except Exception as e:
            print(f"Perplexity specs extraction error: {e}")
            return {}

    def _extract_specs_basic(self, content: str) -> dict[str, Any]:
        """
        Basic regex-based specification extraction
        """
        specs = {}
        content_lower = content.lower()

        # Print speed
        import re

        speed_match = re.search(r"(\d+)\s*(?:seiten|pages|ppm)", content_lower)
        if speed_match:
            specs["print_speed_ppm"] = int(speed_match.group(1))

        # Resolution
        resolution_match = re.search(r"(\d+)\s*x\s*(\d+)\s*dpi", content_lower)
        if resolution_match:
            specs["print_resolution_dpi"] = f"{resolution_match.group(1)}x{resolution_match.group(2)}"

        # Color
        if any(word in content_lower for word in ["farb", "color", "colour"]):
            specs["color"] = True
        elif any(word in content_lower for word in ["schwarzweiß", "schwarz-weiß", "monochrome", "black and white"]):
            specs["color"] = False

        # Duplex
        if any(word in content_lower for word in ["duplex", "beidseitig", "double-sided"]):
            specs["duplex"] = True

        # Connectivity
        connectivity = []
        if "usb" in content_lower:
            connectivity.append("USB")
        if any(word in content_lower for word in ["ethernet", "lan", "netzwerk"]):
            connectivity.append("Ethernet")
        if any(word in content_lower for word in ["wifi", "wlan", "wireless"]):
            connectivity.append("WiFi")
        if connectivity:
            specs["connectivity"] = connectivity

        return specs

    async def _update_product_specifications(
        self, manufacturer: str, model_number: str, specifications: dict[str, Any], source_url: str
    ) -> bool:
        """
        Update product specifications in database
        """
        try:
            # Get manufacturer_id
            manufacturer_query = """
                SELECT id FROM krai_core.manufacturers
                WHERE name = %s
                LIMIT 1
            """
            manufacturer_result = await self.database_service.fetch_one(manufacturer_query, (manufacturer,))

            if not manufacturer_result:
                return False

            manufacturer_id = manufacturer_result["id"]

            # Update or insert product
            upsert_query = """
                INSERT INTO krai_core.products (
                    manufacturer_id,
                    model_number,
                    specifications,
                    urls,
                    updated_at
                ) VALUES (
                    %s, %s, %s::jsonb,
                    jsonb_build_object('product_page', %s, 'extracted_at', NOW()),
                    NOW()
                )
                ON CONFLICT (manufacturer_id, model_number)
                DO UPDATE SET
                    specifications = krai_core.products.specifications || EXCLUDED.specifications,
                    urls = krai_core.products.urls || EXCLUDED.urls,
                    updated_at = NOW()
                RETURNING id
            """

            result = await self.database_service.fetch_one(
                upsert_query, (manufacturer_id, model_number, json.dumps(specifications), source_url)
            )

            if result:
                print(f"✅ Updated specifications for {manufacturer} {model_number}")
                return True

        except Exception as e:
            print(f"Error updating specifications: {e}")
            import traceback

            traceback.print_exc()

        return False

    async def _google_custom_search(self, manufacturer: str, model_number: str) -> dict[str, Any] | None:
        """
        Use Google Custom Search API to find product page

        Requires GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID environment variables
        """
        try:
            import httpx

            # Construct search query
            domains = self.manufacturer_domains.get(manufacturer, [])
            site_filter = f" site:{domains[0]}" if domains else ""
            query = f"{manufacturer} {model_number} specifications{site_filter}"

            # Call Google Custom Search API
            api_url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_search_engine_id,
                "q": query,
                "num": 3,  # Get top 3 results
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, params=params, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()
                items = data.get("items", [])

                if items:
                    # Return first result
                    first_result = items[0]
                    return {
                        "url": first_result["link"],
                        "source": "google_api",
                        "confidence": 0.85,
                        "verified": True,
                        "title": first_result.get("title", ""),
                        "snippet": first_result.get("snippet", ""),
                    }

        except Exception as e:
            print(f"Google Custom Search API error: {e}")

        return None

    async def _scrape_for_product_page(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """
        Fallback: Scrape Google search results to find product page

        This is the current method - extract URLs from search results
        """
        try:
            # Build search query
            domains = self.manufacturer_domains.get(manufacturer, [])
            site_filter = f" site:{domains[0]}" if domains else ""
            search_query = f"{manufacturer} {model_number} specifications{site_filter}"

            search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"

            # Scrape search results
            result = await self.web_scraping_service.scrape_url(search_url)

            if result and result.get("success"):
                content = result.get("content", "")

                # Extract URLs from content
                urls = self._extract_urls_from_content(content, manufacturer)

                if urls:
                    # Return first URL
                    return {
                        "url": urls[0],
                        "source": "scraping",
                        "confidence": 0.6,
                        "verified": False,  # Not verified, just extracted
                    }

        except Exception as e:
            print(f"Error scraping for product page: {e}")

        # Return empty result
        return {"url": None, "source": "none", "confidence": 0.0, "verified": False}

    def _extract_urls_from_content(self, content: str, manufacturer: str) -> list[str]:
        """Extract product page URLs from scraped content"""
        urls = []

        # Get manufacturer domains
        domains = self.manufacturer_domains.get(manufacturer, [])
        if not domains:
            return urls

        # Find URLs in content
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        found_urls = re.findall(url_pattern, content)

        # Filter URLs by manufacturer domain
        for url in found_urls:
            for domain in domains:
                if domain in url:
                    # Avoid search/shop pages, prefer support/product pages
                    if any(
                        keyword in url.lower()
                        for keyword in ["support", "product", "printer", "driver", "specification"]
                    ):
                        if url not in urls:
                            urls.append(url)

        return urls

    def _model_to_slug(self, model_number: str) -> str:
        """Convert model number to URL-friendly slug"""
        # Remove special characters, convert to lowercase
        slug = re.sub(r"[^\w\s-]", "", model_number.lower())
        # Replace spaces and underscores with hyphens
        slug = re.sub(r"[\s_]+", "-", slug)
        # Remove multiple consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
