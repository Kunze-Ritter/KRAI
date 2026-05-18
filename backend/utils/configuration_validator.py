"""
Configuration Validator - Validates product configurations
Checks for conflicts, missing requirements, and suggests alternatives
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from services.database_adapter import DatabaseAdapter
from services.database_factory import create_database_adapter


@dataclass
class ValidationResult:
    """Result of configuration validation"""

    valid: bool
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }


class ConfigurationValidator:
    """Validates product configurations against option dependencies"""

    def __init__(self, adapter: DatabaseAdapter | None = None):
        self.logger = logging.getLogger(__name__)
        self.adapter = adapter

    async def validate_configuration(self, product_id: UUID, accessory_ids: list[UUID]) -> ValidationResult:
        """
        Validate a product configuration

        Args:
            product_id: Base product UUID
            accessory_ids: List of accessory/option UUIDs to validate

        Returns:
            ValidationResult with validation status and messages
        """
        errors = []
        warnings = []
        recommendations = []

        try:
            # Get or create adapter
            adapter = self.adapter
            if adapter is None:
                adapter = create_database_adapter()
                await adapter.connect()

            # Get all dependencies for the accessories
            dependencies = await self._get_dependencies(accessory_ids, adapter)

            # Check 'requires' dependencies
            required_errors = await self._check_required_dependencies(accessory_ids, dependencies, adapter)
            errors.extend(required_errors)

            # Check 'excludes' dependencies (conflicts)
            conflict_errors = await self._check_conflicts(accessory_ids, dependencies, adapter)
            errors.extend(conflict_errors)

            # Check 'alternative' dependencies (warnings)
            alternative_warnings = await self._check_alternatives(accessory_ids, dependencies, adapter)
            warnings.extend(alternative_warnings)

            # Get recommendations
            recommendations = await self._get_recommendations(product_id, accessory_ids, dependencies, adapter)

            # Configuration is valid if no errors
            valid = len(errors) == 0

            return ValidationResult(valid=valid, errors=errors, warnings=warnings, recommendations=recommendations)

        except Exception as e:
            self.logger.error(f"Error validating configuration: {e}")
            return ValidationResult(valid=False, errors=[f"Validation error: {e!s}"], warnings=[], recommendations=[])

    async def _get_dependencies(self, accessory_ids: list[UUID], adapter: DatabaseAdapter) -> list[dict]:
        """Get all dependencies for given accessories"""
        try:
            if not accessory_ids:
                return []

            # Convert UUIDs to strings
            accessory_id_strs = [str(aid) for aid in accessory_ids]

            # Build IN clause for SQL
            placeholders = ", ".join([f"${i+1}" for i in range(len(accessory_id_strs))])
            query = f"SELECT id, option_id, depends_on_option_id, dependency_type, notes FROM krai_core.option_dependencies WHERE option_id IN ({placeholders})"

            results = await adapter.fetch_all(query, accessory_id_strs)
            return [dict(r) for r in results] if results else []

        except Exception as e:
            self.logger.error(f"Error getting dependencies: {e}")
            return []

    async def _check_required_dependencies(
        self, accessory_ids: list[UUID], dependencies: list[dict], adapter: DatabaseAdapter
    ) -> list[str]:
        """Check if all required dependencies are satisfied"""
        errors = []
        accessory_id_set = set(str(aid) for aid in accessory_ids)

        # Get product details for better error messages
        product_names = await self._get_product_names(accessory_ids, adapter)

        for dep in dependencies:
            if dep["dependency_type"] == "requires":
                option_id = dep["option_id"]
                required_id = dep["depends_on_option_id"]

                # Check if required option is in configuration
                if required_id not in accessory_id_set:
                    option_name = product_names.get(option_id, option_id)
                    required_name = await self._get_product_name(required_id, adapter)

                    error_msg = f"❌ {option_name} requires {required_name} " f"(missing from configuration)"
                    if dep.get("notes"):
                        error_msg += f" - {dep['notes']}"

                    errors.append(error_msg)

        return errors

    async def _check_conflicts(
        self, accessory_ids: list[UUID], dependencies: list[dict], adapter: DatabaseAdapter
    ) -> list[str]:
        """Check for conflicting options (excludes)"""
        errors = []
        accessory_id_set = set(str(aid) for aid in accessory_ids)

        # Get product details for better error messages
        product_names = await self._get_product_names(accessory_ids, adapter)

        for dep in dependencies:
            if dep["dependency_type"] == "excludes":
                option_id = dep["option_id"]
                excluded_id = dep["depends_on_option_id"]

                # Check if excluded option is in configuration
                if excluded_id in accessory_id_set:
                    option_name = product_names.get(option_id, option_id)
                    excluded_name = product_names.get(excluded_id, excluded_id)

                    error_msg = f"⚠️ {option_name} conflicts with {excluded_name} " f"(cannot use both)"
                    if dep.get("notes"):
                        error_msg += f" - {dep['notes']}"

                    errors.append(error_msg)

        return errors

    async def _check_alternatives(
        self, accessory_ids: list[UUID], dependencies: list[dict], adapter: DatabaseAdapter
    ) -> list[str]:
        """Check for alternative options (warnings)"""
        warnings = []
        accessory_id_set = set(str(aid) for aid in accessory_ids)

        # Get product details for better messages
        product_names = await self._get_product_names(accessory_ids, adapter)

        for dep in dependencies:
            if dep["dependency_type"] == "alternative":
                option_id = dep["option_id"]
                alternative_id = dep["depends_on_option_id"]

                # Check if both alternatives are in configuration
                if alternative_id in accessory_id_set:
                    option_name = product_names.get(option_id, option_id)
                    alternative_name = product_names.get(alternative_id, alternative_id)

                    warning_msg = f"ℹ️ {option_name} and {alternative_name} are alternatives " f"(typically choose one)"
                    if dep.get("notes"):
                        warning_msg += f" - {dep['notes']}"

                    warnings.append(warning_msg)

        return warnings

    async def _get_recommendations(
        self, product_id: UUID, accessory_ids: list[UUID], dependencies: list[dict], adapter: DatabaseAdapter
    ) -> list[str]:
        """Get recommendations for the configuration"""
        recommendations = []

        # Check if there are standard accessories not included
        try:
            results = await adapter.fetch_all(
                "SELECT accessory_id, is_standard FROM krai_core.product_accessories WHERE product_id = $1 AND is_standard = TRUE",
                [str(product_id)],
            )

            if results:
                accessory_id_set = set(str(aid) for aid in accessory_ids)

                for row in results:
                    accessory_id = row["accessory_id"]
                    if accessory_id not in accessory_id_set:
                        accessory_name = await self._get_product_name(accessory_id, adapter)
                        recommendations.append(f"💡 Consider adding {accessory_name} (standard accessory)")

        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")

        return recommendations

    async def _get_product_names(self, product_ids: list[UUID], adapter: DatabaseAdapter) -> dict[str, str]:
        """Get product names for multiple products"""
        try:
            if not product_ids:
                return {}

            product_id_strs = [str(pid) for pid in product_ids]
            placeholders = ", ".join([f"${i+1}" for i in range(len(product_id_strs))])
            query = f"SELECT id, model_number FROM krai_core.products WHERE id IN ({placeholders})"

            results = await adapter.fetch_all(query, product_id_strs)

            if results:
                return {row["id"]: row["model_number"] for row in results}

            return {}

        except Exception as e:
            self.logger.error(f"Error getting product names: {e}")
            return {}

    async def _get_product_name(self, product_id: str, adapter: DatabaseAdapter) -> str:
        """Get product name for a single product"""
        try:
            result = await adapter.fetch_one("SELECT model_number FROM krai_core.products WHERE id = $1", [product_id])

            if result:
                return result["model_number"]

            return product_id

        except Exception as e:
            self.logger.error(f"Error getting product name: {e}")
            return product_id

    async def get_compatible_accessories(self, product_id: UUID) -> list[dict]:
        """Get all compatible accessories for a product

        Returns list with compatibility info and dependency warnings
        """
        try:
            # Get or create adapter
            adapter = self.adapter
            if adapter is None:
                adapter = create_database_adapter()
                await adapter.connect()

            # Get all accessories for this product
            results = await adapter.fetch_all(
                "SELECT accessory_id, is_standard, compatibility_notes FROM krai_core.product_accessories WHERE product_id = $1",
                [str(product_id)],
            )

            if not results:
                return []

            accessory_ids = [row["accessory_id"] for row in results]

            # Get accessory details
            placeholders = ", ".join([f"${i+1}" for i in range(len(accessory_ids))])
            accessories_query = (
                f"SELECT id, model_number, product_type FROM krai_core.products WHERE id IN ({placeholders})"
            )
            accessories = await adapter.fetch_all(accessories_query, accessory_ids)

            if not accessories:
                return []

            # Get dependencies for these accessories
            dependencies = await self._get_dependencies([UUID(aid) for aid in accessory_ids], adapter)

            # Build result with dependency info
            result = []
            for accessory in accessories:
                accessory_id = accessory["id"]

                # Find original compatibility info
                compat_info = next((r for r in results if r["accessory_id"] == accessory_id), {})

                # Find dependencies
                requires = [
                    d for d in dependencies if d["option_id"] == accessory_id and d["dependency_type"] == "requires"
                ]
                excludes = [
                    d for d in dependencies if d["option_id"] == accessory_id and d["dependency_type"] == "excludes"
                ]

                result.append(
                    {
                        "id": accessory_id,
                        "model_number": accessory["model_number"],
                        "product_type": accessory["product_type"],
                        "is_standard": compat_info.get("is_standard", False),
                        "compatibility_notes": compat_info.get("compatibility_notes"),
                        "requires": [d["depends_on_option_id"] for d in requires],
                        "excludes": [d["depends_on_option_id"] for d in excludes],
                    }
                )

            return result

        except Exception as e:
            self.logger.error(f"Error getting compatible accessories: {e}")
            return []
