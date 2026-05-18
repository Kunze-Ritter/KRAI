"""
Features Service for KR-AI-Engine
Handles features extraction and inheritance from series to products
"""

import logging
from datetime import datetime
from typing import Any

from .ai_service import AIService


class FeaturesService:
    """
    Features service for KR-AI-Engine

    Handles:
    - Series features extraction
    - Product features extraction
    - Features inheritance (Serie → Produkt)
    - Features-based search
    """

    def __init__(self, ai_service: AIService, database_service):
        self.ai_service = ai_service
        self.database_service = database_service
        self.logger = logging.getLogger("krai.features")
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for features service"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - Features - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    async def extract_series_features(self, document_text: str, manufacturer: str, series: str) -> dict[str, Any]:
        """
        Extract global features for product series

        Args:
            document_text: Document text content
            manufacturer: Manufacturer name
            series: Product series name

        Returns:
            Series features dictionary
        """
        try:
            # Use AI to extract series features
            features_result = await self.ai_service.extract_features(document_text, manufacturer, series)

            series_features = {
                "key_features": features_result.get("series_features", {}),
                "target_market": features_result.get("target_market", "Unknown"),
                "price_range": features_result.get("price_range", "Unknown"),
                "common_features": features_result.get("key_features", []),
                "series_description": f"Product series: {series}",
            }

            self.logger.info(f"Extracted series features for {manufacturer} {series}")
            return series_features

        except Exception as e:
            self.logger.error(f"Failed to extract series features: {e}")
            return {
                "key_features": {},
                "target_market": "Unknown",
                "price_range": "Unknown",
                "common_features": [],
                "series_description": f"Product series: {series}",
            }

    async def extract_product_features(self, document_text: str, manufacturer: str, model: str) -> dict[str, Any]:
        """
        Extract model-specific features

        Args:
            document_text: Document text content
            manufacturer: Manufacturer name
            model: Product model name

        Returns:
            Product features dictionary
        """
        try:
            # Use AI to extract product features
            features_result = await self.ai_service.extract_features(document_text, manufacturer, model)

            product_features = features_result.get("product_features", {})

            # Ensure boolean features are properly typed
            boolean_features = {
                "duplex_capable": product_features.get("duplex_capable", False),
                "network_capable": product_features.get("network_capable", False),
                "mobile_print_support": product_features.get("mobile_print_support", False),
                "energy_star_certified": product_features.get("energy_star_certified", False),
            }

            # Ensure list features are properly typed
            list_features = {
                "color_options": product_features.get("color_options", []),
                "connectivity_options": product_features.get("connectivity_options", []),
            }

            # Ensure numeric features
            numeric_features = {"warranty_months": product_features.get("warranty_months", 12)}

            # Combine all features
            all_features = {**boolean_features, **list_features, **numeric_features}

            self.logger.info(f"Extracted product features for {manufacturer} {model}")
            return all_features

        except Exception as e:
            self.logger.error(f"Failed to extract product features: {e}")
            return {
                "duplex_capable": False,
                "network_capable": False,
                "mobile_print_support": False,
                "energy_star_certified": False,
                "color_options": [],
                "connectivity_options": [],
                "warranty_months": 12,
            }

    async def get_series_features(self, series_id: str) -> dict[str, Any]:
        """
        Get series features by ID

        Args:
            series_id: Product series ID

        Returns:
            Series features
        """
        try:
            # This would typically query the database
            # For now, return a placeholder
            return {"series_id": series_id, "key_features": {}, "target_market": "Unknown", "price_range": "Unknown"}

        except Exception as e:
            self.logger.error(f"Failed to get series features: {e}")
            return {}

    async def get_product_features(self, product_id: str) -> dict[str, Any]:
        """
        Get product features by ID

        Args:
            product_id: Product ID

        Returns:
            Product features
        """
        try:
            # This would typically query the database
            # For now, return a placeholder
            return {
                "product_id": product_id,
                "duplex_capable": False,
                "network_capable": False,
                "mobile_print_support": False,
                "energy_star_certified": False,
            }

        except Exception as e:
            self.logger.error(f"Failed to get product features: {e}")
            return {}

    async def get_effective_features(self, series_id: str, product_id: str) -> dict[str, Any]:
        """
        Get effective features with inheritance (Serie → Produkt)

        Args:
            series_id: Product series ID
            product_id: Product ID

        Returns:
            Effective features (series + product)
        """
        try:
            # Get series features
            series_features = await self.get_series_features(series_id)

            # Get product features
            product_features = await self.get_product_features(product_id)

            # Series features as base
            effective_features = series_features.copy()

            # Product features override series features
            effective_features.update(product_features)

            self.logger.info(f"Effective features calculated for series {series_id}, product {product_id}")
            return effective_features

        except Exception as e:
            self.logger.error(f"Failed to get effective features: {e}")
            return {}

    async def search_by_features(self, features_query: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Search products by features

        Args:
            features_query: Features search criteria

        Returns:
            List of matching products
        """
        try:
            # This would typically perform a database query
            # For now, return a placeholder
            return [
                {
                    "product_id": "example_id",
                    "model": "Example Model",
                    "manufacturer": "Example Manufacturer",
                    "features": features_query,
                }
            ]

        except Exception as e:
            self.logger.error(f"Failed to search by features: {e}")
            return []

    async def extract_features(self, document_text: str, manufacturer: str, series: str) -> dict[str, Any]:
        """
        Extract features from document (main entry point)

        Args:
            document_text: Document text content
            manufacturer: Manufacturer name
            series: Product series name

        Returns:
            Features extraction result
        """
        try:
            # Extract series features
            series_features = await self.extract_series_features(document_text, manufacturer, series)

            # Extract product features (using series as base)
            product_features = await self.extract_product_features(document_text, manufacturer, series)

            result = {
                "series_features": series_features,
                "product_features": product_features,
                "extraction_timestamp": datetime.utcnow().isoformat(),
            }

            self.logger.info(f"Features extracted for {manufacturer} {series}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to extract features: {e}")
            return {
                "series_features": {},
                "product_features": {},
                "extraction_timestamp": datetime.utcnow().isoformat(),
            }
