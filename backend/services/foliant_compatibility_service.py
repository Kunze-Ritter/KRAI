"""
Foliant compatibility validation service.

Validates product-accessory configurations against compatibility rules stored in the database.
Implements mutual exclusivity checks for mounting positions and quantity constraints.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.database_adapter import DatabaseAdapter
from backend.services.database_factory import create_database_adapter

LOGGER = logging.getLogger("krai.services.foliant_compatibility")


class FoliantCompatibilityService:
    """Service for validating Foliant product-accessory compatibility."""

    def __init__(self, adapter: DatabaseAdapter | None = None) -> None:
        """Initialize the compatibility service with database adapter."""
        self.adapter = adapter or create_database_adapter()

    def check_configuration_valid(self, product_id: str, accessory_ids: list[str]) -> dict[str, Any]:
        """
        Validate a product-accessory configuration for compatibility.

        Checks:
        - Each accessory is compatible with the product
        - No mounting position constraints are violated
        - Quantity limits are respected
        - Dependency relationships are satisfied

        Args:
            product_id: Model number of the product (e.g., 'C257i')
            accessory_ids: List of accessory model numbers to check (e.g., ['FS-539', 'DF-633'])

        Returns:
            Dictionary with:
            - valid (bool): Whether configuration is valid
            - conflicts (list[str]): List of compatibility conflicts if any
            - details (dict): Detailed position and quantity information per accessory
        """
        conflicts: list[str] = []
        details: dict[str, Any] = {}

        # Validate product exists
        try:
            product = self.adapter.query_one(
                "SELECT model_number, product_type FROM krai_core.products WHERE model_number = %s",
                (product_id,),
            )
            if not product:
                conflicts.append(f"Product '{product_id}' not found")
                return {"valid": False, "conflicts": conflicts, "details": {}}
        except Exception as e:
            LOGGER.error("Error validating product %s: %s", product_id, e)
            conflicts.append(f"Error validating product: {e!s}")
            return {"valid": False, "conflicts": conflicts, "details": {}}

        # Track position usage for mutual exclusivity
        position_usage: dict[str, list[str]] = {}

        # Validate each accessory
        for accessory_id in accessory_ids:
            try:
                # Check if accessory exists
                accessory = self.adapter.query_one(
                    "SELECT model_number, product_type, requires_accessory_id FROM krai_core.products WHERE model_number = %s",
                    (accessory_id,),
                )

                if not accessory:
                    conflicts.append(f"Accessory '{accessory_id}' not found")
                    continue

                # Get compatibility rule for this product-accessory pair
                compat = self.adapter.query_one(
                    """
                    SELECT mounting_position, max_quantity, requires_accessory_id, slot_number
                    FROM krai_core.product_accessories
                    WHERE product_id = %s AND accessory_id = %s
                    """,
                    (product_id, accessory_id),
                )

                if not compat:
                    conflicts.append(f"Accessory '{accessory_id}' is not compatible with product '{product_id}'")
                    continue

                # Extract compatibility details
                mounting_position = compat.get("mounting_position") or "default"
                max_quantity = compat.get("max_quantity") or 1
                slot_number = compat.get("slot_number")
                required_accessory = compat.get("requires_accessory_id")

                # Check dependency: if this accessory requires another, that other must be in the list
                if required_accessory and required_accessory not in accessory_ids:
                    conflicts.append(
                        f"Accessory '{accessory_id}' requires '{required_accessory}' which is not in the configuration"
                    )

                # Track position usage for mutual exclusivity
                if mounting_position not in position_usage:
                    position_usage[mounting_position] = []
                position_usage[mounting_position].append(accessory_id)

                details[accessory_id] = {
                    "mounting_position": mounting_position,
                    "max_quantity": max_quantity,
                    "slot_number": slot_number,
                    "required_accessory": required_accessory,
                }

            except Exception as e:
                LOGGER.error("Error validating accessory %s: %s", accessory_id, e)
                conflicts.append(f"Error validating accessory '{accessory_id}': {e!s}")
                continue

        # Check mutual exclusivity: per position, count vs. max_quantity
        for position, accessories_in_position in position_usage.items():
            try:
                # Get the max quantity limit for this position (take from first accessory in this position)
                if accessories_in_position:
                    first_accessory = accessories_in_position[0]
                    compat = self.adapter.query_one(
                        """
                        SELECT max_quantity
                        FROM krai_core.product_accessories
                        WHERE product_id = %s AND accessory_id = %s
                        """,
                        (product_id, first_accessory),
                    )
                    max_qty = compat.get("max_quantity", 1) if compat else 1

                    # Check if quantity exceeds max
                    if len(accessories_in_position) > max_qty:
                        conflicts.append(
                            f"Position '{position}' has {len(accessories_in_position)} accessories but max is {max_qty}: "
                            f"{', '.join(accessories_in_position)}"
                        )
            except Exception as e:
                LOGGER.error("Error checking position mutual exclusivity for %s: %s", position, e)
                conflicts.append(f"Error checking position '{position}': {e!s}")

        is_valid = len(conflicts) == 0
        LOGGER.info(
            "Configuration check: product=%s accessories=%s valid=%s conflicts=%s",
            product_id,
            accessory_ids,
            is_valid,
            len(conflicts),
        )

        return {
            "valid": is_valid,
            "conflicts": conflicts,
            "details": details,
        }
