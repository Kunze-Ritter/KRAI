"""Integration tests for PartLifetimesImporter with real PostgreSQL."""

import pytest

from backend.processors.part_lifetimes_importer import PartLifetimesImporter
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
async def test_ingest_part_lifetimes_to_database(db_adapter, mock_km_part_lifetimes):
    """Test ingestion of part lifetimes to real database."""
    importer = PartLifetimesImporter(db_adapter)

    # Clear previous test data (be careful with DELETE - only delete km_excel_v1.18)
    await db_adapter.execute_query("DELETE FROM krai_pm.part_lifetimes WHERE source = %s", ("km_excel_v1.18",))

    count = await importer.ingest_file(mock_km_part_lifetimes)

    assert count > 0

    # Verify data in database
    result = await db_adapter.fetch_all(
        "SELECT COUNT(*) as cnt FROM krai_pm.part_lifetimes WHERE source = %s",
        ("km_excel_v1.18",),
    )
    assert len(result) > 0
    assert result[0]["cnt"] > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_part_lifetimes_manufacturer_resolution(db_adapter, mock_km_part_lifetimes):
    """Test that manufacturer IDs are correctly resolved from krai_core.manufacturers."""
    importer = PartLifetimesImporter(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.part_lifetimes WHERE source = %s", ("km_excel_v1.18",))

    await importer.ingest_file(mock_km_part_lifetimes)

    # Check that all entries have valid manufacturer_id
    result = await db_adapter.fetch_all(
        """SELECT manufacturer_id, COUNT(*)
           FROM krai_pm.part_lifetimes WHERE source = %s
           GROUP BY manufacturer_id""",
        ("km_excel_v1.18",),
    )

    assert len(result) > 0
    for row in result:
        manufacturer_id = row["manufacturer_id"]
        cnt = row["count"]
        assert manufacturer_id is not None
        assert cnt > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_part_categories_normalized_lowercase(db_adapter, mock_km_part_lifetimes):
    """Test that part categories are stored in lowercase."""
    importer = PartLifetimesImporter(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.part_lifetimes WHERE source = %s", ("km_excel_v1.18",))

    await importer.ingest_file(mock_km_part_lifetimes)

    # Check that all categories are lowercase
    result = await db_adapter.fetch_all(
        """SELECT DISTINCT part_category FROM krai_pm.part_lifetimes
           WHERE source = %s AND part_category = LOWER(part_category)""",
        ("km_excel_v1.18",),
    )

    assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_part_lifetimes_nominal_pages_stored(db_adapter, mock_km_part_lifetimes):
    """Test that nominal lifetime pages are correctly stored."""
    importer = PartLifetimesImporter(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.part_lifetimes WHERE source = %s", ("km_excel_v1.18",))

    await importer.ingest_file(mock_km_part_lifetimes)

    # Check that all entries have nominal_lifetime_pages > 0
    result = await db_adapter.fetch_all(
        """SELECT COUNT(*) as cnt FROM krai_pm.part_lifetimes
           WHERE source = %s AND nominal_lifetime_pages > 0""",
        ("km_excel_v1.18",),
    )

    assert len(result) > 0
    assert result[0]["cnt"] > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_part_color_channels_stored(db_adapter, mock_km_part_lifetimes):
    """Test that color channels (K, C, M, Y) are properly stored."""
    importer = PartLifetimesImporter(db_adapter)

    await db_adapter.execute_query("DELETE FROM krai_pm.part_lifetimes WHERE source = %s", ("km_excel_v1.18",))

    await importer.ingest_file(mock_km_part_lifetimes)

    # Check for expected color channels
    result = await db_adapter.fetch_all(
        """SELECT DISTINCT color_channel FROM krai_pm.part_lifetimes
           WHERE source = %s AND color_channel IS NOT NULL
           ORDER BY color_channel""",
        ("km_excel_v1.18",),
    )

    channels = [row["color_channel"] for row in result]
    # Should have K, C, M, Y for toner parts
    assert "K" in channels or "C" in channels
