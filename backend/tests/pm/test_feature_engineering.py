"""
Unit tests for FeatureEngineer.

Tests feature extraction, caching, and encoding logic.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from backend.pm.features.feature_engineer import FeatureEngineer
from backend.pm.models.ticket import ServiceTicketFeatures


@pytest.fixture
def mock_db_adapter() -> Mock:
    """Provide mock database adapter."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_extract_features_basic(mock_db_adapter: Mock) -> None:
    """Test basic feature extraction for a single ticket."""
    # Setup: Mock fetch_one for ticket and problem frequency
    mock_db_adapter.fetch_one.side_effect = [
        {  # extract_features ticket lookup
            "id": "tk-001",
            "problem_short": "Fuser Error",
            "problem_long": "Fuser unit failed",
            "error_codes": ["E1", "E2"],
            "replaced_parts": ["Fuser Unit", "Thermistor"],
            "repair_time_minutes": 45.5,
            "manufacturer_id": "HP",
            "metadata": {},
        },
        {"cnt": 12},  # _get_problem_frequency
    ]

    # Mock fetch_all for cache initialization (need exactly 10 error codes)
    mock_db_adapter.fetch_all.side_effect = [
        [{"problem_short": "Fuser Error", "cnt": 12}],  # get_top_problems
        [  # _get_top10_error_codes (exactly 10)
            {"code": "E1", "cnt": 8},
            {"code": "E2", "cnt": 5},
            {"code": "E3", "cnt": 4},
            {"code": "E4", "cnt": 3},
            {"code": "E5", "cnt": 2},
            {"code": "E6", "cnt": 2},
            {"code": "E7", "cnt": 1},
            {"code": "E8", "cnt": 1},
            {"code": "E9", "cnt": 1},
            {"code": "E10", "cnt": 1},
        ],
        [{"manufacturer_id": "HP"}],  # _get_manufacturer_map
    ]

    engineer = FeatureEngineer(mock_db_adapter)
    features = await engineer.extract_features("tk-001")

    assert isinstance(features, ServiceTicketFeatures)
    assert features.ticket_id == "tk-001"
    assert features.repair_time_minutes == 45.5
    assert features.part_replacement_count == 2
    assert features.error_code_count == 2
    assert features.problem_frequency == 12
    assert len(features.error_code_top10) == 10


@pytest.mark.asyncio
async def test_extract_features_missing_ticket(mock_db_adapter: Mock) -> None:
    """Test that missing ticket raises ValueError."""
    mock_db_adapter.fetch_one.return_value = None

    engineer = FeatureEngineer(mock_db_adapter)

    with pytest.raises(ValueError, match="not found"):
        await engineer.extract_features("nonexistent")


@pytest.mark.asyncio
async def test_extract_features_batch(mock_db_adapter: Mock) -> None:
    """Test batch feature extraction."""
    # Mock fetch_all for cache initialization and batch query
    mock_db_adapter.fetch_all.side_effect = [
        # get_top_problems
        [{"problem_short": "Problem A", "cnt": 10}],
        # _get_top10_error_codes (exactly 10 codes)
        [
            {"code": "E1", "cnt": 5},
            {"code": "E2", "cnt": 4},
            {"code": "E3", "cnt": 3},
            {"code": "E4", "cnt": 2},
            {"code": "E5", "cnt": 2},
            {"code": "E6", "cnt": 1},
            {"code": "E7", "cnt": 1},
            {"code": "E8", "cnt": 1},
            {"code": "E9", "cnt": 1},
            {"code": "E10", "cnt": 1},
        ],
        # _get_manufacturer_map
        [{"manufacturer_id": "HP"}],
        # Main fetch_all for ticket IDs in extract_features_batch
        [{"id": "tk-001"}, {"id": "tk-002"}],
    ]

    # Mock fetch_one for individual tickets and problem frequency
    mock_db_adapter.fetch_one.side_effect = [
        {  # tk-001 ticket
            "id": "tk-001",
            "problem_short": "Problem A",
            "error_codes": ["E1"],
            "replaced_parts": ["Part1"],
            "repair_time_minutes": 30.0,
            "manufacturer_id": "HP",
            "metadata": {},
        },
        {"cnt": 10},  # tk-001 problem frequency
        {  # tk-002 ticket
            "id": "tk-002",
            "problem_short": "Problem A",
            "error_codes": ["E1"],
            "replaced_parts": ["Part1"],
            "repair_time_minutes": 35.0,
            "manufacturer_id": "HP",
            "metadata": {},
        },
        {"cnt": 10},  # tk-002 problem frequency
    ]

    engineer = FeatureEngineer(mock_db_adapter)
    features_list = await engineer.extract_features_batch(limit=2)

    assert len(features_list) == 2
    assert features_list[0].ticket_id == "tk-001"
    assert features_list[1].ticket_id == "tk-002"
    assert len(features_list[0].error_code_top10) == 10


@pytest.mark.asyncio
async def test_get_top_problems(mock_db_adapter: Mock) -> None:
    """Test retrieving top problems."""
    mock_db_adapter.fetch_all.return_value = [
        {"problem_short": "Problem A", "cnt": 20},
        {"problem_short": "Problem B", "cnt": 15},
    ]

    engineer = FeatureEngineer(mock_db_adapter)
    top_problems = await engineer.get_top_problems(top_n=2)

    assert len(top_problems) == 2
    assert "Problem A" in top_problems
    assert "Problem B" in top_problems


@pytest.mark.asyncio
async def test_encode_error_codes(mock_db_adapter: Mock) -> None:
    """Test error code one-hot encoding."""
    engineer = FeatureEngineer(mock_db_adapter)
    engineer._top_error_codes = ["E1", "E2", "E3"]

    # Test with codes present
    encoding = engineer._encode_error_codes(["E1", "E3"])
    assert encoding == [1, 0, 1]

    # Test with no codes
    encoding = engineer._encode_error_codes([])
    assert encoding == [0, 0, 0]


@pytest.mark.asyncio
async def test_manufacturer_encoding(mock_db_adapter: Mock) -> None:
    """Test manufacturer ID encoding."""
    mock_db_adapter.fetch_all.side_effect = [
        [{"problem_short": "Problem", "cnt": 1}],  # get_top_problems
        [  # _get_top10_error_codes (exactly 10 codes)
            {"code": "E1", "cnt": 1},
            {"code": "E2", "cnt": 1},
            {"code": "E3", "cnt": 1},
            {"code": "E4", "cnt": 1},
            {"code": "E5", "cnt": 1},
            {"code": "E6", "cnt": 1},
            {"code": "E7", "cnt": 1},
            {"code": "E8", "cnt": 1},
            {"code": "E9", "cnt": 1},
            {"code": "E10", "cnt": 1},
        ],
        [{"manufacturer_id": "HP"}, {"manufacturer_id": "Konica"}],  # _get_manufacturer_map
    ]

    mock_db_adapter.fetch_one.side_effect = [
        {  # extract_features ticket lookup
            "id": "tk-001",
            "problem_short": "Problem",
            "error_codes": ["E1"],
            "replaced_parts": [],
            "repair_time_minutes": 30.0,
            "manufacturer_id": "Konica",
            "metadata": {},
        },
        {"cnt": 1},  # _get_problem_frequency
    ]

    engineer = FeatureEngineer(mock_db_adapter)
    features = await engineer.extract_features("tk-001")

    # Konica should be encoded as 2 (second in map)
    assert features.manufacturer_encoded == 2
    assert len(features.error_code_top10) == 10
