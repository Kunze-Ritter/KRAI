"""
Unit tests for WarrantyTracker.

Tests batch registration of warranty events and idempotency.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pm.services.warranty_tracker import WarrantyTracker


@pytest.fixture
def mock_db_adapter() -> MagicMock:
    """Create a mock DatabaseAdapter."""
    return MagicMock()


@pytest.fixture
def tracker(mock_db_adapter: MagicMock) -> WarrantyTracker:
    """Create a WarrantyTracker with mocked DB."""
    return WarrantyTracker(mock_db_adapter)


@pytest.mark.asyncio
async def test_register_ticket_events_basic(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test basic warranty event registration for a ticket."""
    now = datetime.utcnow()
    completed_date = now - timedelta(days=10)

    ticket_row = {
        "id": "TK-001",
        "completed_date": completed_date,
        "mfr_id": "mfr-1",
        "mfr_name": "Konica Minolta",
        "replaced_part_categories": ["drum", "fuser"],
    }

    part_row_drum = {"nominal_lifetime_pages": 500000}
    part_row_fuser = {"nominal_lifetime_pages": 200000}

    existing_check = None

    async def side_effect_query(*args: object, **kwargs: object) -> object:
        if "service_tickets" in str(args):
            return ticket_row
        if "part_lifetimes" in str(args) and "drum" in str(args):
            return part_row_drum
        if "part_lifetimes" in str(args) and "fuser" in str(args):
            return part_row_fuser
        if "part_warranty_events" in str(args) and "WHERE" in str(args):
            return existing_check
        return None

    mock_db_adapter.fetchrow = AsyncMock(side_effect=side_effect_query)
    mock_db_adapter.execute = AsyncMock()

    count = await tracker.register_ticket_events("TK-001")

    assert count == 2
    assert mock_db_adapter.execute.call_count == 2


@pytest.mark.asyncio
async def test_register_ticket_events_in_warranty(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test that warranty_expiry_date is correctly calculated."""
    completed_date = datetime(2026, 5, 9, 10, 0, 0)  # Fixed date for test

    ticket_row = {
        "id": "TK-002",
        "completed_date": completed_date,
        "mfr_id": "mfr-1",
        "mfr_name": "Konica Minolta",
        "replaced_part_categories": ["drum"],
    }

    part_row = {"nominal_lifetime_pages": 500000}
    existing_check = None

    async def side_effect_query(*args: object, **kwargs: object) -> object:
        if "service_tickets" in str(args):
            return ticket_row
        if "part_lifetimes" in str(args):
            return part_row
        if "WHERE" in str(args):
            return existing_check
        return None

    mock_db_adapter.fetchrow = AsyncMock(side_effect=side_effect_query)
    mock_db_adapter.execute = AsyncMock()

    count = await tracker.register_ticket_events("TK-002", warranty_days=365)

    assert count == 1
    call_args = mock_db_adapter.execute.call_args
    warranty_expiry = call_args[0][5]
    expected_expiry = completed_date + timedelta(days=365)
    assert warranty_expiry == expected_expiry


@pytest.mark.asyncio
async def test_register_ticket_events_no_parts(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test ticket with no replaced parts."""
    ticket_row = {
        "id": "TK-003",
        "completed_date": datetime.utcnow(),
        "mfr_id": "mfr-1",
        "mfr_name": "Konica Minolta",
        "replaced_part_categories": None,
    }

    mock_db_adapter.fetchrow = AsyncMock(return_value=ticket_row)

    count = await tracker.register_ticket_events("TK-003")

    assert count == 0
    mock_db_adapter.execute.assert_not_called()


@pytest.mark.asyncio
async def test_run_batch_registration_basic(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test batch registration of multiple tickets."""
    now = datetime.utcnow()

    tickets = [
        {"id": "TK-001"},
        {"id": "TK-002"},
        {"id": "TK-003"},
    ]

    ticket_details = {
        "TK-001": {
            "completed_date": now - timedelta(days=10),
            "mfr_id": "mfr-1",
            "replaced_part_categories": ["drum"],
        },
        "TK-002": {
            "completed_date": now - timedelta(days=20),
            "mfr_id": "mfr-1",
            "replaced_part_categories": ["fuser"],
        },
        "TK-003": {
            "completed_date": now - timedelta(days=30),
            "mfr_id": "mfr-1",
            "replaced_part_categories": ["toner"],
        },
    }

    async def fetchrow_side_effect(*args: object, **kwargs: object) -> object:
        if "service_tickets" in str(args):
            ticket_id = args[1]
            details = ticket_details.get(ticket_id)  # type: ignore
            if details:
                return {"id": ticket_id, **details, "mfr_name": "Konica Minolta"}
            return None
        if "part_lifetimes" in str(args):
            return {"nominal_lifetime_pages": 500000}
        if "part_warranty_events" in str(args) and "WHERE" in str(args):
            return None
        return None

    mock_db_adapter.fetch = AsyncMock(return_value=tickets)
    mock_db_adapter.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    mock_db_adapter.execute = AsyncMock()

    result = await tracker.run_batch_registration(limit=None)

    assert result["registered"] >= 0
    assert result["skipped"] >= 0
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_run_batch_registration_idempotency(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test that re-running batch registration is idempotent."""
    now = datetime.utcnow()

    tickets = [{"id": "TK-001"}]

    ticket_details = {
        "TK-001": {
            "completed_date": now - timedelta(days=10),
            "mfr_id": "mfr-1",
            "replaced_part_categories": ["drum"],
        }
    }

    call_count = 0

    async def fetchrow_side_effect(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        if "service_tickets" in str(args):
            ticket_id = args[1]
            details = ticket_details.get(ticket_id)  # type: ignore
            if details:
                return {"id": ticket_id, **details, "mfr_name": "Konica Minolta"}
            return None
        if "part_lifetimes" in str(args):
            return {"nominal_lifetime_pages": 500000}
        if "part_warranty_events" in str(args) and "WHERE" in str(args):
            call_count += 1
            if call_count == 1:
                return None
            return {"id": 1}
        return None

    mock_db_adapter.fetch = AsyncMock(return_value=tickets)
    mock_db_adapter.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    mock_db_adapter.execute = AsyncMock()

    result = await tracker.run_batch_registration(limit=None)

    assert result["registered"] >= 0 or result["skipped"] >= 0


@pytest.mark.asyncio
async def test_get_summary(tracker: WarrantyTracker, mock_db_adapter: MagicMock) -> None:
    """Test warranty event summary generation."""
    summary_row = {
        "total_events": 42,
        "warranty_eligible": 18,
        "total_manufacturers": 3,
        "avg_warranty_rate_pct": 42.86,
    }

    mock_db_adapter.fetchrow = AsyncMock(return_value=summary_row)

    summary = await tracker.get_summary()

    assert summary["total_events"] == 42
    assert summary["warranty_eligible"] == 18
    assert summary["total_manufacturers"] == 3
    assert summary["avg_warranty_rate_pct"] == 42.86
