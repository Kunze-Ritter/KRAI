"""
Product Configuration Validator

Validates MFP configurations based on:
- Required accessories
- Incompatibilities
- Dependencies
- Prerequisites
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CompatibilityType(Enum):
    """Types of product relationships"""

    COMPATIBLE = "compatible"
    REQUIRED = "required"
    REQUIRES = "requires"
    CONFLICTS = "conflicts"
    RECOMMENDED = "recommended"
    ALTERNATIVE = "alternative"
    PREREQUISITE = "prerequisite"


@dataclass
class ValidationError:
    """Configuration validation error"""

    error_type: str
    message: str
    product_1: str | None = None
    product_2: str | None = None
    severity: str = "error"  # error, warning, info


@dataclass
class ProductRelationship:
    """Relationship between two products"""

    product_id: str
    related_product_id: str
    relationship_type: CompatibilityType
    notes: str | None = None
    priority: int = 0


class ConfigurationValidator:
    """
    Validates product configurations

    Example usage:
        validator = ConfigurationValidator()
        validator.add_relationship("C4080", "MK-746", CompatibilityType.COMPATIBLE)
        validator.add_relationship("MK-746", "MK-730", CompatibilityType.REQUIRES)
        validator.add_relationship("SD-506", "SD-513", CompatibilityType.CONFLICTS)

        errors = validator.validate_configuration("C4080", ["MK-746", "MK-730"])
    """

    def __init__(self):
        """Initialize validator"""
        self.relationships: list[ProductRelationship] = []
        self.products: dict[str, dict[str, Any]] = {}

    def add_product(
        self,
        model_number: str,
        product_type: str,
        specifications: dict[str, Any] | None = None,
    ):
        """Register a product"""
        self.products[model_number] = {
            "model_number": model_number,
            "product_type": product_type,
            "specifications": specifications or {},
        }

    def add_relationship(
        self,
        product_1: str,
        product_2: str,
        relationship_type: CompatibilityType,
        notes: str | None = None,
        priority: int = 0,
    ):
        """Add a relationship between two products"""
        self.relationships.append(
            ProductRelationship(
                product_id=product_1,
                related_product_id=product_2,
                relationship_type=relationship_type,
                notes=notes,
                priority=priority,
            )
        )

    def get_relationships(
        self,
        product: str,
        relationship_type: CompatibilityType | None = None,
    ) -> list[ProductRelationship]:
        """Get all relationships for a product"""
        matches = []
        for rel in self.relationships:
            if (rel.product_id == product or rel.related_product_id == product) and (
                relationship_type is None or rel.relationship_type == relationship_type
            ):
                matches.append(rel)
        return matches

    def get_required_accessories(self, product: str) -> list[str]:
        """Get all required accessories for a product"""
        required = []
        for rel in self.relationships:
            # Check both REQUIRES (product requires accessory) and REQUIRED/PREREQUISITE
            if rel.product_id == product and rel.relationship_type in [
                CompatibilityType.REQUIRED,
                CompatibilityType.REQUIRES,
                CompatibilityType.PREREQUISITE,
            ]:
                required.append(rel.related_product_id)
        return required

    def get_incompatible_products(self, product: str) -> list[str]:
        """Get all incompatible products"""
        incompatible = []
        for rel in self.relationships:
            if rel.relationship_type == CompatibilityType.CONFLICTS:
                if rel.product_id == product:
                    incompatible.append(rel.related_product_id)
                elif rel.related_product_id == product:
                    incompatible.append(rel.product_id)
        return incompatible

    def check_compatibility(
        self,
        product_1: str,
        product_2: str,
    ) -> tuple[bool, str | None]:
        """
        Check if two products are compatible

        Returns:
            (is_compatible, reason)
        """
        for rel in self.relationships:
            # Check both directions
            if (
                (rel.product_id == product_1 and rel.related_product_id == product_2)
                or (rel.product_id == product_2 and rel.related_product_id == product_1)
            ) and rel.relationship_type == CompatibilityType.CONFLICTS:
                return False, rel.notes or "Products conflict with each other"

        return True, None

    def validate_configuration(
        self,
        base_product: str,
        accessories: list[str],
    ) -> tuple[bool, list[ValidationError]]:
        """
        Validate a complete configuration

        Args:
            base_product: Base product model number (e.g., "C4080")
            accessories: List of accessory model numbers

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check if base product exists
        if base_product not in self.products:
            errors.append(
                ValidationError(
                    error_type="unknown_product",
                    message=f"Base product '{base_product}' not found",
                    product_1=base_product,
                    severity="error",
                )
            )
            return False, errors

        # Check if all accessories exist
        for accessory in accessories:
            if accessory not in self.products:
                errors.append(
                    ValidationError(
                        error_type="unknown_accessory",
                        message=f"Accessory '{accessory}' not found",
                        product_1=accessory,
                        severity="warning",
                    )
                )

        # Check for required accessories
        required = self.get_required_accessories(base_product)
        for req in required:
            if req not in accessories:
                errors.append(
                    ValidationError(
                        error_type="missing_required",
                        message=f"Required accessory '{req}' is missing",
                        product_1=base_product,
                        product_2=req,
                        severity="error",
                    )
                )

        # Check for conflicts between accessories
        for i, acc1 in enumerate(accessories):
            for acc2 in accessories[i + 1 :]:
                compatible, reason = self.check_compatibility(acc1, acc2)
                if not compatible:
                    errors.append(
                        ValidationError(
                            error_type="conflict",
                            message=reason or f"'{acc1}' conflicts with '{acc2}'",
                            product_1=acc1,
                            product_2=acc2,
                            severity="error",
                        )
                    )

        # Check for transitive requirements
        # (e.g., if MK-746 requires MK-730, and user added MK-746 but not MK-730)
        accessories_set = set(accessories)
        for accessory in accessories:
            required_for_accessory = self.get_required_accessories(accessory)
            for req in required_for_accessory:
                if req not in accessories_set:
                    errors.append(
                        ValidationError(
                            error_type="missing_dependency",
                            message=f"'{accessory}' requires '{req}' but it's not included",
                            product_1=accessory,
                            product_2=req,
                            severity="error",
                        )
                    )

        # Configuration is valid if no errors with severity="error"
        is_valid = not any(e.severity == "error" for e in errors)

        return is_valid, errors

    def suggest_alternatives(
        self,
        product: str,
        excluded_products: list[str] | None = None,
    ) -> list[str]:
        """
        Suggest alternative products

        Args:
            product: Product to find alternatives for
            excluded_products: Products to exclude from suggestions

        Returns:
            List of alternative product model numbers
        """
        alternatives = []
        excluded_products = excluded_products or []

        for rel in self.relationships:
            if rel.relationship_type == CompatibilityType.ALTERNATIVE:
                if rel.product_id == product and rel.related_product_id not in excluded_products:
                    alternatives.append(rel.related_product_id)
                elif rel.related_product_id == product and rel.product_id not in excluded_products:
                    alternatives.append(rel.product_id)

        return alternatives

    def get_recommended_accessories(self, product: str) -> list[str]:
        """Get recommended accessories for a product"""
        recommended = []
        for rel in self.relationships:
            if rel.product_id == product and rel.relationship_type == CompatibilityType.RECOMMENDED:
                recommended.append(rel.related_product_id)
        return recommended

    def generate_report(
        self,
        base_product: str,
        accessories: list[str],
    ) -> dict[str, Any]:
        """
        Generate a comprehensive validation report

        Returns:
            Dictionary with validation results and suggestions
        """
        is_valid, errors = self.validate_configuration(base_product, accessories)

        report = {
            "base_product": base_product,
            "accessories": accessories,
            "is_valid": is_valid,
            "errors": [
                {
                    "type": e.error_type,
                    "message": e.message,
                    "severity": e.severity,
                    "products": [e.product_1, e.product_2],
                }
                for e in errors
            ],
            "required_missing": [],
            "conflicts": [],
            "recommendations": [],
        }

        # Categorize errors
        for error in errors:
            if error.error_type in ["missing_required", "missing_dependency"]:
                report["required_missing"].append({"accessory": error.product_2, "reason": error.message})
            elif error.error_type == "conflict":
                report["conflicts"].append(
                    {"product_1": error.product_1, "product_2": error.product_2, "reason": error.message}
                )

        # Add recommendations
        recommended = self.get_recommended_accessories(base_product)
        for rec in recommended:
            if rec not in accessories:
                report["recommendations"].append({"accessory": rec, "reason": "Recommended for optimal performance"})

        return report


# Example usage
if __name__ == "__main__":
    # Create validator
    validator = ConfigurationValidator()

    # Register products
    validator.add_product("C4080", "printer")
    validator.add_product("MK-746", "finisher")
    validator.add_product("MK-730", "finisher_bracket")
    validator.add_product("SD-506", "finisher")
    validator.add_product("SD-513", "finisher")
    validator.add_product("PF-602m", "feeder")

    # Define relationships
    validator.add_relationship("C4080", "MK-746", CompatibilityType.COMPATIBLE)
    validator.add_relationship(
        "MK-746", "MK-730", CompatibilityType.REQUIRES, notes="MK-746 requires MK-730 mounting bracket"
    )
    validator.add_relationship(
        "SD-506", "SD-513", CompatibilityType.CONFLICTS, notes="Cannot install both saddle finishers"
    )
    validator.add_relationship(
        "C4080",
        "PF-602m",
        CompatibilityType.RECOMMENDED,
        notes="High-capacity feeder recommended for high-volume printing",
    )

    # Test 1: Valid configuration
    print("Test 1: Valid configuration")
    is_valid, errors = validator.validate_configuration("C4080", ["MK-746", "MK-730"])
    print(f"Valid: {is_valid}, Errors: {len(errors)}")

    # Test 2: Missing required accessory
    print("\nTest 2: Missing required accessory")
    is_valid, errors = validator.validate_configuration("C4080", ["MK-746"])
    print(f"Valid: {is_valid}")
    for error in errors:
        print(f"  - {error.message}")

    # Test 3: Conflicting accessories
    print("\nTest 3: Conflicting accessories")
    is_valid, errors = validator.validate_configuration("C4080", ["SD-506", "SD-513"])
    print(f"Valid: {is_valid}")
    for error in errors:
        print(f"  - {error.message}")

    # Test 4: Full report
    print("\nTest 4: Full report")
    report = validator.generate_report("C4080", ["MK-746"])
    print(f"Valid: {report['is_valid']}")
    print(f"Errors: {len(report['errors'])}")
    print(f"Recommendations: {report['recommendations']}")
