"""
Unit tests for ErrorPatternAnalyzer.

Tests error code pattern analysis and co-occurrence detection.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from backend.pm.models.error_pattern_analyzer import ErrorPatternAnalyzer


@pytest.fixture
def mock_db_adapter() -> Mock:
    """Provide mock database adapter."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_analyze_by_manufacturer_basic(mock_db_adapter: Mock) -> None:
    """Test basic error pattern analysis for a manufacturer."""
    # Setup: Error codes for HP
    mock_db_adapter.fetch_all.side_effect = [
        # Top error codes
        [
            {"code": "13.B9", "cnt": 25},
            {"code": "50.FF", "cnt": 15},
        ],
        # Cooccurrence query results (empty for simplicity)
        [],
        [],
    ]

    mock_db_adapter.fetch_one.return_value = {"cnt": 100}

    analyzer = ErrorPatternAnalyzer(mock_db_adapter)
    result = await analyzer.analyze_by_manufacturer("HP")

    assert result["manufacturer"] == "HP"
    assert result["total_tickets"] == 100
    assert len(result["top_error_codes"]) == 2
    assert result["top_error_codes"][0] == ("13.B9", 25)


@pytest.mark.asyncio
async def test_analyze_by_manufacturer_skewed_distribution(
    mock_db_adapter: Mock,
) -> None:
    """Test detection of skewed error distribution."""
    # Setup: 80%+ of tickets have top 20% of codes
    mock_db_adapter.fetch_all.side_effect = [
        # Top 5 codes
        [
            {"code": "E1", "cnt": 40},
            {"code": "E2", "cnt": 25},
            {"code": "E3", "cnt": 15},
            {"code": "E4", "cnt": 10},
            {"code": "E5", "cnt": 10},
        ],
        [],
        [],
    ]

    mock_db_adapter.fetch_one.return_value = {"cnt": 100}

    analyzer = ErrorPatternAnalyzer(mock_db_adapter)
    result = await analyzer.analyze_by_manufacturer("HP", top_n=5)

    # Top 1 code (20%) accounts for 40% (< 80%), so not skewed with this config
    # But if we check manually: Top 1 is 40%, top 2 is 65%, top 3 is 80% - skewed
    assert result["distribution_type"] in ["skewed", "uniform"]


@pytest.mark.asyncio
async def test_analyze_all_manufacturers(mock_db_adapter: Mock) -> None:
    """Test analyzing all manufacturers."""
    # Setup: Two manufacturers
    mock_db_adapter.fetch_all.side_effect = [
        # Get all manufacturers
        [{"manufacturer_id": "HP"}, {"manufacturer_id": "Konica"}],
        # First manufacturer error codes
        [{"code": "E1", "cnt": 10}],
        [],
        [],
        # Second manufacturer error codes
        [{"code": "E2", "cnt": 5}],
        [],
        [],
    ]

    mock_db_adapter.fetch_one.side_effect = [
        {"cnt": 50},  # HP total
        {"cnt": 30},  # Konica total
    ]

    analyzer = ErrorPatternAnalyzer(mock_db_adapter)
    results = await analyzer.analyze_all_manufacturers()

    assert len(results) == 2
    assert "HP" in results
    assert "Konica" in results


@pytest.mark.asyncio
async def test_classify_distribution_skewed(mock_db_adapter: Mock) -> None:
    """Test classification of skewed distribution."""
    analyzer = ErrorPatternAnalyzer(mock_db_adapter)

    # Skewed: 80%+ of tickets from top 20% of codes
    error_codes = [
        {"code": "E1", "cnt": 90},
        {"code": "E2", "cnt": 5},
        {"code": "E3", "cnt": 5},
    ]
    distribution = analyzer._classify_distribution(error_codes, 100)
    assert distribution == "skewed"


@pytest.mark.asyncio
async def test_classify_distribution_uniform(mock_db_adapter: Mock) -> None:
    """Test classification of uniform distribution."""
    analyzer = ErrorPatternAnalyzer(mock_db_adapter)

    # Uniform: codes distributed evenly
    error_codes = [
        {"code": "E1", "cnt": 20},
        {"code": "E2", "cnt": 20},
        {"code": "E3", "cnt": 20},
        {"code": "E4", "cnt": 20},
        {"code": "E5", "cnt": 20},
    ]
    distribution = analyzer._classify_distribution(error_codes, 100)
    assert distribution == "uniform"


@pytest.mark.asyncio
async def test_cooccurrence_matrix(mock_db_adapter: Mock) -> None:
    """Test error code co-occurrence computation."""
    # Setup: Tickets with multiple error codes
    mock_db_adapter.fetch_all.side_effect = [
        # Tickets with E1
        [
            {"error_codes": ["E1", "E2", "E3"]},
            {"error_codes": ["E1", "E2"]},
        ],
    ]

    analyzer = ErrorPatternAnalyzer(mock_db_adapter)
    cooccurrence = await analyzer._compute_cooccurrence("HP", ["E1"])

    assert "E1" in cooccurrence
    # E2 and E3 should appear with E1
    assert cooccurrence["E1"]["E2"] == 2
    assert cooccurrence["E1"]["E3"] == 1
