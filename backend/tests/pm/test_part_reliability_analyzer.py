"""
Unit tests for PartReliabilityAnalyzer.

Tests warranty analysis, risk classification, and replacement frequency computation.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pm.models.part_reliability_analyzer import PartReliabilityAnalyzer


@pytest.fixture
def mock_db_adapter() -> MagicMock:
    """Create a mock DatabaseAdapter."""
    return MagicMock()


@pytest.fixture
def analyzer(mock_db_adapter: MagicMock) -> PartReliabilityAnalyzer:
    """Create a PartReliabilityAnalyzer with mocked DB."""
    return PartReliabilityAnalyzer(mock_db_adapter)


@pytest.mark.asyncio
async def test_analyze_by_manufacturer_basic(analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock) -> None:
    """Test basic manufacturer analysis with one part category."""
    mock_db_adapter.fetch_all = AsyncMock(
        return_value=[
            {
                "manufacturer_name": "Konica Minolta",
                "part_category": "drum",
                "total_replacements": 10,
                "avg_nominal_lifetime": 500000,
                "avg_actual_runtime": 200000.0,
                "avg_mismatch_ratio": 0.4,
                "warranty_eligible_count": 6,
                "warranty_rate_pct": 60.0,
                "total_repair_cost_eur": 1800.0,
            }
        ]
    )

    metrics = await analyzer.analyze_by_manufacturer("Konica Minolta")

    assert len(metrics) == 1
    assert metrics[0].manufacturer_name == "Konica Minolta"
    assert metrics[0].part_category == "drum"
    assert metrics[0].total_replacements == 10
    assert metrics[0].warranty_rate_pct == 60.0
    assert metrics[0].risk_level == "critical"
    assert metrics[0].mismatch_ratio == 0.4


@pytest.mark.asyncio
async def test_analyze_by_manufacturer_no_data(analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock) -> None:
    """Test manufacturer analysis with no data."""
    mock_db_adapter.fetch_all = AsyncMock(return_value=[])

    metrics = await analyzer.analyze_by_manufacturer("Unknown Manufacturer")

    assert len(metrics) == 0


@pytest.mark.asyncio
async def test_analyze_all_empty(analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock) -> None:
    """Test analyze_all with empty data."""
    mock_db_adapter.fetch_all = AsyncMock(return_value=[])
    mock_db_adapter.fetch_one = AsyncMock(
        return_value={"total_events": 0, "warranty_eligible": 0, "total_manufacturers": 0}
    )

    summary = await analyzer.analyze_all()

    assert summary.total_events == 0
    assert summary.warranty_eligible == 0
    assert summary.total_manufacturers == 0
    assert len(summary.by_manufacturer) == 0


@pytest.mark.asyncio
async def test_analyze_all_multiple_manufacturers(
    analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock
) -> None:
    """Test analyze_all with multiple manufacturers."""
    mock_db_adapter.fetch_all = AsyncMock(
        return_value=[
            {
                "manufacturer_name": "HP",
                "part_category": "toner",
                "total_replacements": 5,
                "avg_nominal_lifetime": 300000,
                "avg_actual_runtime": 250000.0,
                "avg_mismatch_ratio": 0.83,
                "warranty_eligible_count": 1,
                "warranty_rate_pct": 20.0,
                "total_repair_cost_eur": 300.0,
            },
            {
                "manufacturer_name": "Ricoh",
                "part_category": "drum",
                "total_replacements": 8,
                "avg_nominal_lifetime": 400000,
                "avg_actual_runtime": 150000.0,
                "avg_mismatch_ratio": 0.375,
                "warranty_eligible_count": 5,
                "warranty_rate_pct": 62.5,
                "total_repair_cost_eur": 1500.0,
            },
        ]
    )
    mock_db_adapter.fetch_one = AsyncMock(
        return_value={"total_events": 13, "warranty_eligible": 6, "total_manufacturers": 2}
    )

    summary = await analyzer.analyze_all()

    assert summary.total_events == 13
    assert summary.warranty_eligible == 6
    assert summary.total_manufacturers == 2
    assert "HP" in summary.by_manufacturer
    assert "Ricoh" in summary.by_manufacturer
    assert len(summary.by_manufacturer["HP"]) == 1
    assert len(summary.by_manufacturer["Ricoh"]) == 1
    assert summary.by_manufacturer["HP"][0].risk_level == "medium"
    assert summary.by_manufacturer["Ricoh"][0].risk_level == "critical"


@pytest.mark.asyncio
async def test_compute_replacement_frequency_basic(
    analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock
) -> None:
    """Test replacement frequency computation."""
    now = datetime.utcnow()
    past_date = datetime(2026, 1, 1)

    mock_db_adapter.fetch_one = AsyncMock(
        return_value={
            "replacement_count": 12,
            "nominal_lifetime_pages": 500000,
            "avg_actual_runtime_pages": 200000.0,
            "earliest_failure": past_date,
            "latest_failure": now,
        }
    )

    freq = await analyzer.compute_replacement_frequency("Konica Minolta", "drum")

    assert freq["replacement_count"] == 12
    assert freq["nominal_lifetime_pages"] == 500000
    assert freq["avg_actual_runtime_pages"] == 200000.0
    assert freq["implied_lifetime_days"] is not None
    assert freq["implied_lifetime_days"] > 0


@pytest.mark.asyncio
async def test_compute_replacement_frequency_no_data(
    analyzer: PartReliabilityAnalyzer, mock_db_adapter: MagicMock
) -> None:
    """Test replacement frequency with no data."""
    mock_db_adapter.fetch_one = AsyncMock(
        return_value={"replacement_count": 0, "earliest_failure": None, "latest_failure": None}
    )

    freq = await analyzer.compute_replacement_frequency("Unknown", "drum")

    assert freq["replacement_count"] == 0
    assert freq["nominal_lifetime_pages"] is None
    assert freq["avg_actual_runtime_pages"] is None
    assert freq["implied_lifetime_days"] is None


def test_classify_risk_critical() -> None:
    """Test risk classification for critical threshold (>50%)."""
    assert PartReliabilityAnalyzer.classify_risk(60.0) == "critical"
    assert PartReliabilityAnalyzer.classify_risk(75.0) == "critical"
    assert PartReliabilityAnalyzer.classify_risk(100.0) == "critical"


def test_classify_risk_high() -> None:
    """Test risk classification for high threshold (>30%, <=50%)."""
    assert PartReliabilityAnalyzer.classify_risk(40.0) == "high"
    assert PartReliabilityAnalyzer.classify_risk(50.0) == "high"


def test_classify_risk_medium() -> None:
    """Test risk classification for medium threshold (>15%, <=30%)."""
    assert PartReliabilityAnalyzer.classify_risk(20.0) == "medium"
    assert PartReliabilityAnalyzer.classify_risk(30.0) == "medium"


def test_classify_risk_low() -> None:
    """Test risk classification for low threshold (<=15%)."""
    assert PartReliabilityAnalyzer.classify_risk(0.0) == "low"
    assert PartReliabilityAnalyzer.classify_risk(10.0) == "low"
    assert PartReliabilityAnalyzer.classify_risk(15.0) == "low"


def test_classify_risk_unknown() -> None:
    """Test risk classification for unknown (None input)."""
    assert PartReliabilityAnalyzer.classify_risk(None) == "unknown"  # type: ignore
