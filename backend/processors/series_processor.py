"""Series Processor

Detects and creates product series, links products to series.
"""

from backend.core.base_processor import BaseProcessor, Stage
from backend.utils.series_detector import detect_series

from .imports import get_database_adapter


class SeriesProcessor(BaseProcessor):
    """Detect and create product series."""

    def __init__(self, database_adapter=None):
        """Initialize series processor"""
        super().__init__(name="series_processor")
        self.stage = Stage.SERIES_DETECTION
        self.adapter = database_adapter or get_database_adapter()
        # Expose adapter under BaseProcessor-expected attribute names.
        self.db_adapter = self.adapter
        self.database_service = self.adapter
        self.logger.info("SeriesProcessor initialized")

    async def process_all_products(self) -> dict:
        """
        Process all products to detect and link series

        Returns:
            Dict with statistics
        """
        stats = {"products_processed": 0, "series_detected": 0, "series_created": 0, "products_linked": 0, "errors": 0}

        with self.logger_context(stage=self.stage) as adapter:
            try:
                products = await self.adapter.get_products_without_series()
                adapter.info("Processing %s products without series", len(products))

                for product in products:
                    stats["products_processed"] += 1

                    try:
                        result = await self._process_product(product, adapter)
                        if result:
                            stats["series_detected"] += 1
                            if result["series_created"]:
                                stats["series_created"] += 1
                            if result["product_linked"]:
                                stats["products_linked"] += 1
                    except Exception as e:
                        adapter.error("Error processing product %s: %s", product.get("id"), e)
                        stats["errors"] += 1

                adapter.info("Series processing complete: %s", stats)
                return stats

            except Exception as e:
                adapter.error("Error in series processing: %s", e)
                stats["errors"] += 1
                return stats

    async def process_product(self, product_id: str) -> dict | None:
        """
        Process a single product to detect and link series

        Args:
            product_id: UUID of product

        Returns:
            Dict with result or None
        """
        with self.logger_context(stage=self.stage, product_id=product_id) as adapter:
            try:
                product = await self.adapter.get_product(product_id)

                if not product:
                    adapter.warning("Product %s not found", product_id)
                    return None
                return await self._process_product(product, adapter)

            except Exception as e:
                adapter.error("Error processing product %s: %s", product_id, e)
                return None

    async def _process_product(self, product: dict, adapter) -> dict | None:
        """
        Process a product to detect and link series

        Args:
            product: Product data with manufacturer

        Returns:
            Dict with series_id, series_created, product_linked
        """
        model_number = product.get("model_number")
        manufacturer_id = product.get("manufacturer_id")

        if not model_number or not manufacturer_id:
            return None

        # Get manufacturer name from manufacturers table
        try:
            manufacturer = await self.adapter.get_manufacturer(manufacturer_id)
            manufacturer_name = manufacturer.get("name", "") if manufacturer else ""
        except Exception as e:
            adapter.warning("Could not get manufacturer name for %s: %s", manufacturer_id, e)
            manufacturer_name = ""

        # Don't detect series if manufacturer is unknown (prevents false matches)
        if not manufacturer_name:
            adapter.warning("Skipping series detection for %s - manufacturer unknown", model_number)
            return {"series_detected": False, "series_created": False, "product_linked": False}

        # Detect series
        series_data = detect_series(model_number, manufacturer_name)
        if not series_data:
            adapter.debug("No series detected for %s %s", manufacturer_name, model_number)
            return {"series_detected": False, "series_created": False, "product_linked": False}

        adapter.info("Detected series for %s: %s", model_number, series_data["series_name"])

        # Get or create series
        series_id, series_created = await self._get_or_create_series(
            manufacturer_id=manufacturer_id, series_data=series_data, adapter=adapter
        )

        if not series_id:
            return None

        # Link product to series
        product_linked = await self._link_product_to_series(
            product_id=product["id"], series_id=series_id, adapter=adapter
        )

        return {
            "series_id": series_id,
            "series_name": series_data["series_name"],
            "series_detected": True,
            "series_created": series_created,
            "product_linked": product_linked,
        }

    async def process(self, context) -> dict:
        """Async wrapper for BaseProcessor interface to process a single product. No-ops when product_id is missing (e.g. document-level pipeline)."""
        product_id = getattr(context, "product_id", None)
        if not product_id:
            with self.logger_context(stage=self.stage) as adapter:
                adapter.debug("Skipping series detection: no product_id in context (document-level pipeline)")
            return self.create_success_result(
                {"series_detected": False, "series_created": False, "product_linked": False},
                metadata={"stage": self.stage.value, "skipped": "no product_id"},
            )

        with self.logger_context(stage=self.stage, product_id=product_id) as adapter:
            result = await self.process_product(product_id)
            if result is None:
                metadata = {"product_id": str(product_id), "stage": self.stage.value}
                error = {
                    "series_detected": False,
                    "series_created": False,
                    "product_linked": False,
                }
                processing_result = self.create_success_result(error, metadata=metadata)
                return processing_result

            metadata = {
                "product_id": str(product_id),
                "stage": self.stage.value,
                "series_detected": result.get("series_detected", False),
                "series_created": result.get("series_created", False),
                "product_linked": result.get("product_linked", False),
            }
            return self.create_success_result(result, metadata=metadata)

    async def _get_or_create_series(self, manufacturer_id: str, series_data: dict, adapter) -> tuple[str | None, bool]:
        """
        Get existing series or create new one

        Args:
            manufacturer_id: Manufacturer UUID
            series_data: Series information from detector

        Returns:
            Tuple of (series_id, was_created)
        """
        series_name = series_data["series_name"]

        try:
            # Check if series exists (by series_name + model_pattern)
            model_pattern = series_data.get("model_pattern")
            existing = await self.adapter.get_product_series_by_name_and_pattern(
                manufacturer_id=manufacturer_id, series_name=series_name, model_pattern=model_pattern
            )

            if existing:
                adapter.debug("Series '%s' (%s) already exists", series_name, model_pattern)
                return existing["id"], False

            # Create new series
            new_series = {
                "manufacturer_id": manufacturer_id,
                "series_name": series_name,  # Marketing name (e.g., "LaserJet")
                "model_pattern": series_data.get("model_pattern"),  # Technical pattern (e.g., "M4xx")
                "series_description": series_data.get("series_description"),
            }

            series = await self.adapter.create_product_series(new_series)

            if series:
                series_id = series["id"]
                adapter.info("Created series '%s' with ID %s", series_name, series_id)
                return series_id, True

            return None, False

        except Exception as e:
            error_str = str(e)
            if "23505" in error_str or "duplicate key" in error_str.lower():
                adapter.debug("Series '%s' already exists (duplicate key), fetching existing...", series_name)
                try:
                    existing = await self.adapter.get_product_series_by_name_and_pattern(
                        manufacturer_id=manufacturer_id, series_name=series_name, model_pattern=model_pattern
                    )
                    if existing:
                        return existing["id"], False
                except Exception as fetch_error:
                    adapter.warning(
                        "Failed to fetch existing series '%s' after duplicate key: %s", series_name, fetch_error
                    )

            adapter.error("Error creating series '%s': %s", series_name, e)
            return None, False

    async def _link_product_to_series(self, product_id: str, series_id: str, adapter) -> bool:
        """
        Link product to series

        Args:
            product_id: Product UUID
            series_id: Series UUID

        Returns:
            True if successful
        """
        try:
            await self.adapter.update_product(product_id, {"series_id": series_id})
            adapter.debug("Linked product %s to series %s", product_id, series_id)
            return True
        except Exception as e:
            adapter.error("Error linking product %s to series %s: %s", product_id, series_id, e)
            return False

    async def get_series_products(self, series_id: str) -> list:
        """
        Get all products in a series

        Args:
            series_id: Series UUID

        Returns:
            List of products
        """
        try:
            products = await self.adapter.get_products_by_series(series_id)
            return products

        except Exception as e:
            self.logger.error(f"Error getting products for series {series_id}: {e}")
            return []

    async def get_manufacturer_series(self, manufacturer_id: str) -> list:
        """
        Get all series for a manufacturer

        Args:
            manufacturer_id: Manufacturer UUID

        Returns:
            List of series with product counts
        """
        try:
            # Get series
            series_list = await self.adapter.get_product_series_by_manufacturer(manufacturer_id)

            # Add product count to each series
            for series in series_list:
                products = await self.get_series_products(series["id"])
                series["product_count"] = len(products)

            return series_list

        except Exception as e:
            self.logger.error(f"Error getting series for manufacturer {manufacturer_id}: {e}")
            return []


async def main():
    """Test series processor"""
    import sys

    processor = SeriesProcessor()

    if len(sys.argv) > 1:
        # Process specific product
        product_id = sys.argv[1]
        result = await processor.process_product(product_id)

        if result:
            print("\nSeries Detection Complete!")
            print(f"Series: {result['series_name']}")
            print(f"Series ID: {result['series_id']}")
            print(f"Series Created: {result['series_created']}")
            print(f"Product Linked: {result['product_linked']}")
        else:
            print("No series detected for this product")
    else:
        # Process all products
        stats = await processor.process_all_products()

        print("\nSeries Processing Complete!")
        print(f"Products processed: {stats['products_processed']}")
        print(f"Series detected: {stats['series_detected']}")
        print(f"Series created: {stats['series_created']}")
        print(f"Products linked: {stats['products_linked']}")
        print(f"Errors: {stats['errors']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
