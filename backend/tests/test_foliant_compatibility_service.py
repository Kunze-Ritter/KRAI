"""
Unit tests for Foliant compatibility service.

Tests validation of product-accessory configurations against compatibility rules.
"""

from typing import Any

import pytest

from backend.services.foliant_compatibility_service import FoliantCompatibilityService


class MockDatabaseAdapter:
    """Mock database adapter for testing."""

    def __init__(self) -> None:
        """Initialize mock adapter."""
        self.products: dict[str, dict[str, Any]] = {}
        self.compatibility_rules: dict[tuple[str, str], dict[str, Any]] = {}

    def query_one(self, query: str, params: tuple) -> dict[str, Any] | None:
        """Mock query_one method."""
        # Handle products query
        if "krai_core.products" in query and "WHERE" in query and len(params) == 1:
            product_id = params[0]
            return self.products.get(product_id)

        # Handle product_accessories query
        if "krai_core.product_accessories" in query and len(params) == 2:
            key = tuple(params)
            return self.compatibility_rules.get(key)

        return None


@pytest.fixture
def mock_adapter() -> MockDatabaseAdapter:
    """Provide mock database adapter."""
    return MockDatabaseAdapter()


@pytest.fixture
def service(mock_adapter: MockDatabaseAdapter) -> FoliantCompatibilityService:
    """Provide Foliant compatibility service with mocked adapter."""
    return FoliantCompatibilityService(adapter=mock_adapter)


def test_valid_configuration(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation of a valid product-accessory configuration."""
    # Setup: C257i product with two compatible accessories
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["FS-539"] = {
        "model_number": "FS-539",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }
    mock_adapter.products["DF-633"] = {
        "model_number": "DF-633",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }

    mock_adapter.compatibility_rules[("C257i", "FS-539")] = {
        "mounting_position": "side",
        "max_quantity": 2,
        "slot_number": "FS_SIDE_1",
        "requires_accessory_id": None,
    }
    mock_adapter.compatibility_rules[("C257i", "DF-633")] = {
        "mounting_position": "top",
        "max_quantity": 1,
        "slot_number": None,
        "requires_accessory_id": None,
    }

    # Test
    result = service.check_configuration_valid("C257i", ["FS-539", "DF-633"])

    # Verify
    assert result["valid"] is True
    assert len(result["conflicts"]) == 0
    assert "FS-539" in result["details"]
    assert "DF-633" in result["details"]
    assert result["details"]["FS-539"]["mounting_position"] == "side"
    assert result["details"]["DF-633"]["mounting_position"] == "top"


def test_missing_product(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation with non-existent product."""
    # Setup: no product in database
    result = service.check_configuration_valid("NONEXISTENT", ["FS-539"])

    # Verify
    assert result["valid"] is False
    assert any("not found" in conflict for conflict in result["conflicts"])


def test_missing_accessory(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation with non-existent accessory."""
    # Setup
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}

    # Test
    result = service.check_configuration_valid("C257i", ["NONEXISTENT"])

    # Verify
    assert result["valid"] is False
    assert any("not found" in conflict for conflict in result["conflicts"])


def test_incompatible_accessory(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation with accessory incompatible with product."""
    # Setup
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["FS-539"] = {
        "model_number": "FS-539",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }
    # No compatibility rule defined

    # Test
    result = service.check_configuration_valid("C257i", ["FS-539"])

    # Verify
    assert result["valid"] is False
    assert any("not compatible" in conflict for conflict in result["conflicts"])


def test_dependency_not_satisfied(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation where accessory dependency is not satisfied."""
    # Setup: RU-514 requires FS-539
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["RU-514"] = {
        "model_number": "RU-514",
        "product_type": "accessory",
        "requires_accessory_id": "FS-539",
    }

    mock_adapter.compatibility_rules[("C257i", "RU-514")] = {
        "mounting_position": "side",
        "max_quantity": 1,
        "slot_number": None,
        "requires_accessory_id": "FS-539",
    }

    # Test: RU-514 without FS-539
    result = service.check_configuration_valid("C257i", ["RU-514"])

    # Verify
    assert result["valid"] is False
    assert any("requires" in conflict for conflict in result["conflicts"])


def test_dependency_satisfied(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation where accessory dependency is satisfied."""
    # Setup: RU-514 requires FS-539
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["FS-539"] = {
        "model_number": "FS-539",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }
    mock_adapter.products["RU-514"] = {
        "model_number": "RU-514",
        "product_type": "accessory",
        "requires_accessory_id": "FS-539",
    }

    mock_adapter.compatibility_rules[("C257i", "FS-539")] = {
        "mounting_position": "side",
        "max_quantity": 2,
        "slot_number": None,
        "requires_accessory_id": None,
    }
    mock_adapter.compatibility_rules[("C257i", "RU-514")] = {
        "mounting_position": "side",
        "max_quantity": 2,
        "slot_number": None,
        "requires_accessory_id": "FS-539",
    }

    # Test: RU-514 with FS-539
    result = service.check_configuration_valid("C257i", ["FS-539", "RU-514"])

    # Verify
    assert result["valid"] is True
    assert len(result["conflicts"]) == 0


def test_quantity_exceeds_limit(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation where accessory quantity exceeds maximum."""
    # Setup: max 2 FS-539 per side, but we're adding 3
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["FS-539"] = {
        "model_number": "FS-539",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }

    mock_adapter.compatibility_rules[("C257i", "FS-539")] = {
        "mounting_position": "side",
        "max_quantity": 2,
        "slot_number": None,
        "requires_accessory_id": None,
    }

    # Note: In real scenario, we'd have 3 separate entries; here we simplify by passing 3 identical IDs
    # The service counts them in position_usage
    # For this test, we'll test the position check logic by having multiple accessories in same position
    result = service.check_configuration_valid("C257i", ["FS-539", "FS-539", "FS-539"])

    # Verify
    assert result["valid"] is False
    assert any("max is 2" in conflict for conflict in result["conflicts"])


def test_empty_accessory_list(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation with empty accessory list."""
    # Setup
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}

    # Test
    result = service.check_configuration_valid("C257i", [])

    # Verify: empty list should be valid (no conflicts)
    assert result["valid"] is True
    assert len(result["conflicts"]) == 0
    assert len(result["details"]) == 0


def test_multiple_positions(service: FoliantCompatibilityService, mock_adapter: MockDatabaseAdapter) -> None:
    """Test validation with accessories on different positions."""
    # Setup
    mock_adapter.products["C257i"] = {"model_number": "C257i", "product_type": "multifunction"}
    mock_adapter.products["FS-539"] = {
        "model_number": "FS-539",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }
    mock_adapter.products["DF-633"] = {
        "model_number": "DF-633",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }
    mock_adapter.products["RU-514"] = {
        "model_number": "RU-514",
        "product_type": "accessory",
        "requires_accessory_id": None,
    }

    # Side position: max 3
    mock_adapter.compatibility_rules[("C257i", "FS-539")] = {
        "mounting_position": "side",
        "max_quantity": 3,
        "slot_number": None,
        "requires_accessory_id": None,
    }
    # Top position: max 1
    mock_adapter.compatibility_rules[("C257i", "DF-633")] = {
        "mounting_position": "top",
        "max_quantity": 1,
        "slot_number": None,
        "requires_accessory_id": None,
    }
    # Bottom position: max 1
    mock_adapter.compatibility_rules[("C257i", "RU-514")] = {
        "mounting_position": "bottom",
        "max_quantity": 1,
        "slot_number": None,
        "requires_accessory_id": None,
    }

    # Test
    result = service.check_configuration_valid("C257i", ["FS-539", "DF-633", "RU-514"])

    # Verify
    assert result["valid"] is True
    assert len(result["conflicts"]) == 0
    assert result["details"]["FS-539"]["mounting_position"] == "side"
    assert result["details"]["DF-633"]["mounting_position"] == "top"
    assert result["details"]["RU-514"]["mounting_position"] == "bottom"
