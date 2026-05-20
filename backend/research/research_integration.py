"""
Research Integration Helper
============================

Integrates ProductResearcher into existing pipeline and automatically applies
the configured web scraping backend (Firecrawl or BeautifulSoup).
"""

import json
import logging
from typing import Any
from uuid import UUID

from research.product_researcher import ProductResearcher

from backend.services.config_service import ConfigService
from backend.services.db_pool import get_pool

logger = logging.getLogger(__name__)


class ResearchIntegration:
    """
    Helper class to integrate research into product processing
    """

    def __init__(
        self,
        enabled: bool = True,
        config_service: ConfigService | None = None,
    ):
        """
        Initialize integration

        Args:
            enabled: Enable/disable research (can be controlled via env var)
            config_service: Optional configuration service for scraping settings
        """
        self.enabled = enabled
        self.config_service = config_service or ConfigService()
        self.researcher = ProductResearcher(config_service=self.config_service) if enabled else None

        logger.info(
            "ResearchIntegration initialized (enabled: %s, scraping: %s)",
            enabled,
            self.researcher.scraping_backend if self.researcher else "disabled",
        )

    async def enrich_product(
        self, product_id: UUID, manufacturer_name: str, model_number: str, current_confidence: float = 0.0
    ) -> bool:
        """
        Enrich product with online research

        Triggers research if:
        - Product has low confidence (< 0.7)
        - Product has no series
        - Product has no specs

        Args:
            product_id: Product UUID
            manufacturer_name: Manufacturer name
            model_number: Model number
            current_confidence: Current extraction confidence

        Returns:
            True if enriched, False otherwise
        """
        if not self.enabled or not self.researcher:
            return False

        # Get current product data
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                product_data = await conn.fetchrow(
                    "SELECT id, series_id, specifications, oem_manufacturer FROM krai_core.products WHERE id = $1",
                    str(product_id),
                )

            if not product_data:
                return False

            # Decide if research is needed
            needs_research = (
                current_confidence < 0.7  # Low confidence
                or not product_data.get("series_id")  # No series
                or not product_data.get("specifications")  # No specs
                or not product_data.get("oem_manufacturer")  # No OEM
            )

            if not needs_research:
                logger.debug(f"Product {model_number} doesn't need research")
                return False

            logger.info(f"🔍 Researching product: {manufacturer_name} {model_number}")

            # Perform research
            research = await self.researcher.research_product(manufacturer=manufacturer_name, model_number=model_number)

            if not research:
                logger.warning(f"Research failed for {manufacturer_name} {model_number}")
                return False

            # Update product with research results
            await self._apply_research_to_product(product_id, research)

            logger.info(f"✅ Product enriched with research (confidence: {research.get('confidence', 0):.2f})")
            return True

        except Exception as e:
            logger.error(f"Failed to enrich product: {e}")
            return False

    def get_scraping_stats(self) -> dict[str, Any]:
        """Return scraping backend statistics for monitoring."""

        if not self.researcher:
            return {
                "enabled": False,
                "backend": None,
                "scraping_info": {},
            }

        return {
            "enabled": self.enabled,
            "backend": self.researcher.scraping_backend,
            "scraping_info": self.researcher.get_scraping_info(),
        }

    async def _apply_research_to_product(self, product_id: UUID, research: dict[str, Any]):
        """
        Apply research results to product

        Updates:
        - specifications (JSONB)
        - oem_manufacturer
        - oem_notes
        - series (if found)
        """
        try:
            update_data = {}

            # Specifications
            if research.get("specifications"):
                update_data["specifications"] = research["specifications"]

            # Physical specs (merge into specifications)
            if research.get("physical_specs"):
                if "specifications" not in update_data:
                    update_data["specifications"] = {}
                update_data["specifications"]["physical"] = research["physical_specs"]

            # OEM info
            if research.get("oem_manufacturer"):
                update_data["oem_manufacturer"] = research["oem_manufacturer"]
                update_data["oem_relationship_type"] = "engine"
                update_data["oem_notes"] = research.get("oem_notes", "")

            # Product type (if more specific)
            if research.get("product_type"):
                update_data["product_type"] = research["product_type"]

            # Update product
            if update_data:
                # Build dynamic UPDATE query
                set_clauses = []
                params = []
                param_idx = 1

                for key, value in update_data.items():
                    if key == "specifications":
                        set_clauses.append(f"{key} = ${param_idx}::jsonb")
                        params.append(json.dumps(value))
                    else:
                        set_clauses.append(f"{key} = ${param_idx}")
                        params.append(value)
                    param_idx += 1

                params.append(str(product_id))
                query = f"UPDATE krai_core.products SET {', '.join(set_clauses)} WHERE id = ${param_idx}"

                pool = await get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(query, *params)
                logger.debug(f"Updated product {product_id} with {len(update_data)} fields")

            # Try to link series (if series_name found)
            if research.get("series_name"):
                await self._link_series(product_id, research["series_name"])

        except Exception as e:
            logger.error(f"Failed to apply research: {e}")

    async def _link_series(self, product_id: UUID, series_name: str):
        """
        Try to link product to series

        Creates series if it doesn't exist
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Check if series exists
                series = await conn.fetchrow(
                    "SELECT id FROM krai_core.product_series WHERE series_name = $1 LIMIT 1", series_name
                )

                if series:
                    # Link to existing series
                    series_id = series["id"]
                    await conn.execute(
                        "UPDATE krai_core.products SET series_id = $1 WHERE id = $2", series_id, str(product_id)
                    )
                    logger.debug(f"Linked product to existing series: {series_name}")
                else:
                    # Create new series
                    new_series = await conn.fetchrow(
                        "INSERT INTO krai_core.product_series (series_name, source) VALUES ($1, $2) RETURNING id",
                        series_name,
                        "online_research",
                    )

                    if new_series:
                        series_id = new_series["id"]
                        await conn.execute(
                            "UPDATE krai_core.products SET series_id = $1 WHERE id = $2", series_id, str(product_id)
                        )
                        logger.info(f"Created new series: {series_name}")

        except Exception as e:
            logger.debug(f"Could not link series: {e}")

    async def batch_enrich_products(self, limit: int = 100) -> dict[str, int]:
        """
        Batch enrich products that need research

        Args:
            limit: Maximum number of products to process

        Returns:
            Statistics dictionary
        """
        if not self.enabled or not self.researcher:
            return {"enriched": 0, "skipped": 0, "failed": 0}

        stats = {"enriched": 0, "skipped": 0, "failed": 0}

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Find products that need research
                # (no specs, no series, or low confidence)
                products = await conn.fetch(
                    "SELECT id, model_number, manufacturer_id, specifications, series_id FROM krai_core.products WHERE specifications IS NULL LIMIT $1",
                    limit,
                )

                if not products:
                    logger.info("No products need research")
                    return stats

                logger.info(f"Found {len(products)} products that need research")

                # Get manufacturer names
                manufacturer_ids = list(set(p["manufacturer_id"] for p in products if p.get("manufacturer_id")))
                manufacturers = {}

                for mfr_id in manufacturer_ids:
                    mfr = await conn.fetchrow("SELECT id, name FROM krai_core.manufacturers WHERE id = $1", mfr_id)
                    if mfr:
                        manufacturers[mfr_id] = mfr["name"]

            # Process each product
            for product in products:
                manufacturer_name = manufacturers.get(product.get("manufacturer_id"))
                if not manufacturer_name:
                    stats["skipped"] += 1
                    continue

                success = await self.enrich_product(
                    product_id=product["id"],
                    manufacturer_name=manufacturer_name,
                    model_number=product["model_number"],
                    current_confidence=0.5,
                )

                if success:
                    stats["enriched"] += 1
                else:
                    stats["failed"] += 1

            logger.info(f"Batch enrichment complete: {stats}")

        except Exception as e:
            logger.error(f"Batch enrichment failed: {e}")

        return stats


if __name__ == "__main__":
    # Test mode
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        integration = ResearchIntegration(enabled=True)

        # Batch enrich products
        print("Starting batch enrichment...")
        stats = await integration.batch_enrich_products(limit=10)

        print("\n✅ Batch enrichment complete:")
        print(f"   Enriched: {stats['enriched']}")
        print(f"   Skipped: {stats['skipped']}")
        print(f"   Failed: {stats['failed']}")

    asyncio.run(main())
