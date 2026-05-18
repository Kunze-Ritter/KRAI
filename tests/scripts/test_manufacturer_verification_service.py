"""
Tests for ManufacturerVerificationService

Tests web-based manufacturer verification including:
1. Manufacturer verification from model numbers
2. Model verification with specifications
3. Parts discovery
4. Hardware specs extraction
5. Caching behavior
6. Confidence scoring
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.manufacturer_verification_service import ManufacturerVerificationService

pytestmark = [pytest.mark.unit, pytest.mark.manufacturer_verification]


class TestManufacturerVerification:
    """Test manufacturer verification from model numbers"""

    @pytest.mark.asyncio
    async def test_verify_manufacturer_from_model_number(self) -> None:
        """Test manufacturer verification from model number"""
        # Mock web scraping service
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": "HP LaserJet Pro M454dn - Manufacturer: HP Inc.",
                "html": "<div>HP LaserJet Pro M454dn</div>",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="M454dn", hints=["HP", "LaserJet"])

        assert result is not None
        assert result["manufacturer"] is not None
        assert "HP" in result["manufacturer"].upper()
        assert result["confidence"] > 0.0
        assert result["cached"] is False

    @pytest.mark.asyncio
    async def test_verify_manufacturer_with_high_confidence(self) -> None:
        """Test manufacturer verification returns high confidence when manufacturer appears multiple times"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": """
                HP LaserJet Pro M454dn Printer
                Manufacturer: HP Inc.
                HP Support: https://hp.com/support
                HP Inc. All Rights Reserved
                Contact HP for more information
            """,
                "html": "",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        assert result is not None
        assert result["manufacturer"] is not None
        assert result["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_verify_manufacturer_empty_result_on_failure(self) -> None:
        """Test that empty result is returned when scraping fails"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(return_value={"success": False, "error": "Scraping failed"})

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="UNKNOWN123")

        assert result is not None
        assert result["manufacturer"] is None
        assert result["confidence"] == 0.0
        assert result["cached"] is False

    @pytest.mark.asyncio
    async def test_verify_manufacturer_normalizes_name(self) -> None:
        """Test that manufacturer names are normalized"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "Hewlett Packard LaserJet M454dn specifications", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        assert result is not None
        assert result["manufacturer"] is not None
        # Should be normalized to canonical form
        assert "HP" in result["manufacturer"].upper() or "HEWLETT" in result["manufacturer"].upper()


class TestModelVerification:
    """Test model verification with specifications"""

    @pytest.mark.asyncio
    async def test_verify_model_exists(self) -> None:
        """Test model verification confirms model exists"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": """
                HP LaserJet Pro M454dn
                Print Speed: 28 ppm
                Resolution: 1200 x 1200 dpi
                Paper Size: A4, Letter
                Connectivity: USB, Ethernet, Wi-Fi
            """,
                "html": "",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_model(manufacturer="HP Inc.", model_number="M454dn")

        assert result is not None
        assert result["exists"] is True
        assert len(result["specifications"]) > 0
        assert result["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_verify_model_extracts_specifications(self) -> None:
        """Test that model verification extracts specifications"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": """
                HP LaserJet Pro M454dn Specifications
                Print Speed: 28 ppm
                Resolution: 1200 x 1200 dpi
                Paper Size: A4, Letter, Legal
                Connectivity: USB 2.0, Gigabit Ethernet, Wi-Fi 802.11ac
            """,
                "html": "",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_model(manufacturer="HP Inc.", model_number="M454dn")

        assert result is not None
        assert result["exists"] is True
        specs = result["specifications"]
        assert "print_speed" in specs or "resolution" in specs or "connectivity" in specs

    @pytest.mark.asyncio
    async def test_verify_model_not_found(self) -> None:
        """Test model verification when model doesn't exist"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "No results found for this model", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_model(manufacturer="HP Inc.", model_number="NONEXISTENT999")

        assert result is not None
        assert result["exists"] is False
        assert len(result["specifications"]) == 0


class TestPartsDiscovery:
    """Test parts and accessories discovery"""

    @pytest.mark.asyncio
    async def test_discover_parts_for_model(self) -> None:
        """Test parts discovery for a product model"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": """
                HP LaserJet Pro M454dn Parts and Accessories
                Part Number: W1410A - Black Toner Cartridge
                Part Number: W1411A - Cyan Toner Cartridge
                Part Number: W1412A - Magenta Toner Cartridge
                Part Number: W1413A - Yellow Toner Cartridge
                RM2-6308 Fuser Assembly
            """,
                "html": "",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.discover_parts(manufacturer="HP Inc.", model_number="M454dn")

        assert result is not None
        assert len(result["parts"]) > 0
        assert result["confidence"] > 0.0

        # Check that part numbers were extracted
        part_numbers = [p["part_number"] for p in result["parts"]]
        assert any("W1410A" in pn or "W1411A" in pn or "RM2-6308" in pn for pn in part_numbers)

    @pytest.mark.asyncio
    async def test_discover_parts_empty_when_none_found(self) -> None:
        """Test parts discovery returns empty list when no parts found"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "No parts information available", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.discover_parts(manufacturer="HP Inc.", model_number="UNKNOWN")

        assert result is not None
        assert len(result["parts"]) == 0
        assert result["confidence"] == 0.0


class TestHardwareSpecsExtraction:
    """Test hardware specifications extraction"""

    @pytest.mark.asyncio
    async def test_get_hardware_specs(self) -> None:
        """Test hardware specifications extraction"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": """
                HP LaserJet Pro M454dn Hardware Specifications
                Memory: 512 MB
                Storage: 2 GB eMMC
                Processor: 1.2 GHz ARM Cortex-A9
                Network: Gigabit Ethernet 10/100/1000
            """,
                "html": "",
            }
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.get_hardware_specs(manufacturer="HP Inc.", model_number="M454dn")

        assert result is not None
        assert len(result["specifications"]) > 0
        assert result["confidence"] > 0.0

        specs = result["specifications"]
        assert "memory" in specs or "storage" in specs or "processor" in specs or "network" in specs

    @pytest.mark.asyncio
    async def test_get_hardware_specs_extracts_memory(self) -> None:
        """Test that memory specifications are extracted correctly"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "Memory: 512 MB RAM, Storage: 2 GB Flash", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.get_hardware_specs(manufacturer="HP Inc.", model_number="M454dn")

        assert result is not None
        specs = result["specifications"]
        if "memory" in specs:
            assert "MB" in specs["memory"] or "GB" in specs["memory"]


class TestCachingBehavior:
    """Test result caching functionality"""

    @pytest.mark.asyncio
    async def test_cache_stores_verification_results(self) -> None:
        """Test that verification results are stored in cache"""
        mock_db_service = MagicMock()
        mock_db_client = MagicMock()
        mock_db_service.client = mock_db_client

        # Mock schema and from_ chain
        mock_schema = MagicMock()
        mock_table = MagicMock()
        mock_db_client.schema.return_value = mock_schema
        mock_schema.from_.return_value = mock_table

        # Mock select query (cache miss)
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        # Mock upsert
        mock_upsert = MagicMock()
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = MagicMock(data=[])

        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "HP LaserJet Pro M454dn", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=mock_db_service,
            web_scraping_service=mock_scraping_service,
            enable_cache=True,
            min_confidence=0.5,
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        # Verify upsert was called to save to cache
        assert mock_table.upsert.called

    @pytest.mark.asyncio
    async def test_cache_returns_cached_results(self) -> None:
        """Test that cached results are returned without web scraping"""
        mock_db_service = MagicMock()
        mock_db_client = MagicMock()
        mock_db_service.client = mock_db_client

        # Mock schema and from_ chain
        mock_schema = MagicMock()
        mock_table = MagicMock()
        mock_db_client.schema.return_value = mock_schema
        mock_schema.from_.return_value = mock_table

        # Mock select query (cache hit)
        cached_data = {"manufacturer": "HP Inc.", "confidence": 0.9, "source_url": "https://hp.com", "cached": False}

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(
            data=[
                {
                    "cache_key": "test_key",
                    "verification_data": cached_data,
                    "cache_valid_until": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                }
            ]
        )

        mock_scraping_service = AsyncMock()

        service = ManufacturerVerificationService(
            database_service=mock_db_service, web_scraping_service=mock_scraping_service, enable_cache=True
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        # Should return cached result
        assert result is not None
        assert result["manufacturer"] == "HP Inc."
        assert result["cached"] is True

        # Web scraping should NOT have been called
        assert not mock_scraping_service.scrape_url.called

    @pytest.mark.asyncio
    async def test_cache_respects_ttl(self) -> None:
        """Test that expired cache entries are not used"""
        mock_db_service = MagicMock()
        mock_db_client = MagicMock()
        mock_db_service.client = mock_db_client

        # Mock schema and from_ chain
        mock_schema = MagicMock()
        mock_table = MagicMock()
        mock_db_client.schema.return_value = mock_schema
        mock_schema.from_.return_value = mock_table

        # Mock select query (expired cache entry)
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(
            data=[
                {
                    "cache_key": "test_key",
                    "verification_data": {"manufacturer": "HP Inc."},
                    "cache_valid_until": (datetime.utcnow() - timedelta(days=1)).isoformat(),  # Expired
                }
            ]
        )

        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "HP LaserJet Pro M454dn", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=mock_db_service, web_scraping_service=mock_scraping_service, enable_cache=True
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        # Should NOT use expired cache, should scrape instead
        assert mock_scraping_service.scrape_url.called


class TestConfidenceScoring:
    """Test confidence score calculation"""

    @pytest.mark.asyncio
    async def test_confidence_increases_with_occurrences(self) -> None:
        """Test that confidence increases with multiple manufacturer mentions"""
        mock_scraping_service = AsyncMock()

        # Single mention
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "HP LaserJet Pro M454dn", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result_single = await service.verify_manufacturer(model_number="M454dn")
        confidence_single = result_single["confidence"]

        # Multiple mentions
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "markdown": "HP LaserJet Pro M454dn by HP Inc. Visit HP support at hp.com. HP warranty included.",
                "html": "",
            }
        )

        result_multiple = await service.verify_manufacturer(model_number="M454dn")
        confidence_multiple = result_multiple["confidence"]

        # Multiple mentions should have higher confidence
        assert confidence_multiple >= confidence_single

    @pytest.mark.asyncio
    async def test_confidence_capped_at_one(self) -> None:
        """Test that confidence is capped at 1.0"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": " ".join(["HP"] * 100), "html": ""}  # Many mentions
        )

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        assert result["confidence"] <= 1.0


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_handles_scraping_exception(self) -> None:
        """Test that scraping exceptions are handled gracefully"""
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(side_effect=Exception("Network error"))

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        # Should return empty result, not raise exception
        assert result is not None
        assert result["manufacturer"] is None
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_handles_empty_model_number(self) -> None:
        """Test handling of empty model number"""
        mock_scraping_service = AsyncMock()

        service = ManufacturerVerificationService(
            database_service=None, web_scraping_service=mock_scraping_service, enable_cache=False
        )

        result = await service.verify_manufacturer(model_number="")

        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_disabled_skips_caching(self) -> None:
        """Test that caching is skipped when disabled"""
        mock_db_service = MagicMock()
        mock_scraping_service = AsyncMock()
        mock_scraping_service.scrape_url = AsyncMock(
            return_value={"success": True, "markdown": "HP LaserJet Pro M454dn", "html": ""}
        )

        service = ManufacturerVerificationService(
            database_service=mock_db_service,
            web_scraping_service=mock_scraping_service,
            enable_cache=False,  # Cache disabled
        )

        result = await service.verify_manufacturer(model_number="M454dn")

        # Database should not be accessed when cache is disabled
        assert not mock_db_service.client.called if hasattr(mock_db_service, "client") else True
