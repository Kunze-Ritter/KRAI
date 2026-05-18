"""Integration tests for TicketIngestionProcessor with real PostgreSQL."""

import pytest

from backend.processors.ticket_ingestion_processor import TicketIngestionProcessor
from backend.services.database_factory import create_database_adapter


@pytest.fixture
async def db_adapter():
    """Create real database adapter."""
    adapter = create_database_adapter()
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ingest_km_anfragen_of_to_database(db_adapter, mock_km_excel_of):
    """Test ingestion of KM Office tickets to real database."""
    processor = TicketIngestionProcessor(db_adapter)

    # Clear previous test data
    await db_adapter.execute_query("DELETE FROM krai_pm.service_tickets WHERE source_system = %s", ("km_anfragen_of",))

    count = await processor.ingest_file(mock_km_excel_of, "km_anfragen_of")

    assert count == 100

    # Verify data in database
    result = await db_adapter.fetch_all(
        "SELECT COUNT(*) as cnt FROM krai_pm.service_tickets WHERE source_system = %s",
        ("km_anfragen_of",),
    )
    assert len(result) > 0
    assert result[0]["cnt"] >= 100


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ingest_km_anfragen_pp_to_database(db_adapter, mock_km_excel_pp):
    """Test ingestion of KM Production tickets to real database."""
    processor = TicketIngestionProcessor(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.service_tickets WHERE source_system = %s", ("km_anfragen_pp",))

    count = await processor.ingest_file(mock_km_excel_pp, "km_anfragen_pp")

    assert count == 50

    result = await db_adapter.fetch_all(
        "SELECT COUNT(*) as cnt FROM krai_pm.service_tickets WHERE source_system = %s",
        ("km_anfragen_pp",),
    )
    assert len(result) > 0
    assert result[0]["cnt"] >= 50


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ingest_km_anfragen_sol_to_database(db_adapter, mock_km_excel_sol):
    """Test ingestion of KM Solutions tickets to real database."""
    processor = TicketIngestionProcessor(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.service_tickets WHERE source_system = %s", ("km_anfragen_sol",))

    count = await processor.ingest_file(mock_km_excel_sol, "km_anfragen_sol")

    assert count == 30

    result = await db_adapter.fetch_all(
        "SELECT COUNT(*) as cnt FROM krai_pm.service_tickets WHERE source_system = %s",
        ("km_anfragen_sol",),
    )
    assert len(result) > 0
    assert result[0]["cnt"] >= 30


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ingest_duplicate_tickets_ignored(db_adapter, mock_km_excel_of):
    """Test that duplicate tickets are ignored (ON CONFLICT DO NOTHING)."""
    processor = TicketIngestionProcessor(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.service_tickets WHERE source_system = %s", ("km_anfragen_of",))

    # First ingest
    count1 = await processor.ingest_file(mock_km_excel_of, "km_anfragen_of")
    assert count1 == 100

    # Second ingest (same data)
    count2 = await processor.ingest_file(mock_km_excel_of, "km_anfragen_of")
    assert count2 == 100  # Should still insert 100 (mock doesn't change)

    # Total should be 100 (duplicates ignored)
    result = await db_adapter.fetch_all(
        "SELECT COUNT(*) as cnt FROM krai_pm.service_tickets WHERE source_system = %s",
        ("km_anfragen_of",),
    )
    assert len(result) > 0
    assert result[0]["cnt"] == 100


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ticket_error_codes_stored_as_array(db_adapter, mock_km_excel_of):
    """Test that error codes are stored as PostgreSQL array."""
    processor = TicketIngestionProcessor(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.service_tickets WHERE source_system = %s", ("km_anfragen_of",))

    await processor.ingest_file(mock_km_excel_of, "km_anfragen_of")

    # Fetch a ticket and check error_codes array
    result = await db_adapter.fetch_all(
        "SELECT error_codes FROM krai_pm.service_tickets WHERE source_system = %s LIMIT 1",
        ("km_anfragen_of",),
    )
    assert len(result) > 0
    assert isinstance(result[0]["error_codes"], list)
    assert len(result[0]["error_codes"]) > 0
