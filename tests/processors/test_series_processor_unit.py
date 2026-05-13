import sys
import types
from unittest.mock import AsyncMock

import pytest

import backend.core.base_processor as backend_base_processor
import backend.utils.series_detector as backend_series_detector

# Ensure legacy imports in series_processor resolve correctly during tests
core_pkg = types.ModuleType("core")
core_pkg.base_processor = backend_base_processor
sys.modules.setdefault("core", core_pkg)
sys.modules.setdefault("core.base_processor", backend_base_processor)

utils_pkg = types.ModuleType("utils")
utils_pkg.series_detector = backend_series_detector
sys.modules.setdefault("utils", utils_pkg)
sys.modules.setdefault("utils.series_detector", backend_series_detector)

from backend.processors.series_processor import SeriesProcessor  # noqa: E402
from backend.utils.series_detector import detect_series  # noqa: E402


@pytest.mark.series
class TestSeriesDetectorUnit:
    """Unit tests for detect_series() patterns across manufacturers."""

    def test_detect_series_hp_laserjet(self):
        result = detect_series("M404n", "HP")
        assert result is not None
        assert "laserjet" in result["series_name"].lower()

    def test_detect_series_hp_officejet(self):
        result = detect_series("OfficeJet Pro 9015", "HP")
        assert result is not None
        assert "officejet" in result["series_name"].lower()

    def test_detect_series_konica_minolta_bizhub(self):
        result = detect_series("C4080", "Konica Minolta")
        assert result is not None
        assert "bizhub" in result["series_name"].lower()

    def test_detect_series_canon_imagerunner(self):
        result = detect_series("ADVANCE C5560", "Canon")
        assert result is not None
        assert "imagerunner" in result["series_name"].lower()

    def test_detect_series_lexmark_cx(self):
        result = detect_series("CX833", "Lexmark")
        assert result is not None
        assert "cx" in result["series_name"].lower() or "series" in result["series_name"].lower()

    def test_detect_series_kyocera_taskalfa(self):
        result = detect_series("5053ci", "Kyocera")
        assert result is not None

    def test_detect_series_ricoh_im(self):
        result = detect_series("IM C6000", "Ricoh")
        assert result is not None
        assert "im" in result["series_name"].lower()

    def test_detect_series_xerox_versalink(self):
        result = detect_series("C7025", "Xerox")
        assert result is not None
        assert "versalink" in result["series_name"].lower()

    def test_detect_series_no_match_returns_generic(self):
        result = detect_series("ZZ999", "Unknown")
        assert result is not None
        assert result["series_name"]

    def test_detect_series_confidence_with_context(self):
        context = "HP LaserJet Pro M404n service manual"
        result = detect_series("M404n", "HP", context=context)
        assert result is not None
        assert 0.0 <= result.get("confidence", 0.0) <= 1.0


@pytest.mark.series
@pytest.mark.asyncio
class TestSeriesProcessorHelpers:
    """Unit tests for SeriesProcessor helper methods."""

    async def _create_processor(self, mock_database_adapter) -> SeriesProcessor:
        processor = SeriesProcessor(database_adapter=mock_database_adapter)
        # Patch adapter methods we rely on to be AsyncMocks for precise assertions
        mock_database_adapter.get_product_series_by_name_and_pattern = AsyncMock()
        mock_database_adapter.create_product_series = AsyncMock()
        mock_database_adapter.update_product = AsyncMock(return_value=True)
        mock_database_adapter.get_manufacturer = AsyncMock()
        return processor

    async def test_get_or_create_series_creates_new(self, mock_database_adapter):
        processor = await self._create_processor(mock_database_adapter)

        async def fake_get_series(**_kwargs):
            return None

        async def fake_create_series(series_dict: dict) -> dict:
            stored = dict(series_dict)
            stored["id"] = "series-123"
            return stored

        processor.adapter.get_product_series_by_name_and_pattern.side_effect = fake_get_series
        processor.adapter.create_product_series.side_effect = fake_create_series

        series_data = {
            "series_name": "LaserJet Pro M4xx",
            "model_pattern": "M4xx",
            "series_description": "HP LaserJet Pro M400 series",
        }

        series_id, created = await processor._get_or_create_series(
            manufacturer_id="manu-1",
            series_data=series_data,
            adapter=processor._logger_adapter,
        )

        assert series_id == "series-123"
        assert created is True
        processor.adapter.create_product_series.assert_awaited_once()

    async def test_get_or_create_series_returns_existing(self, mock_database_adapter):
        processor = await self._create_processor(mock_database_adapter)

        existing = {"id": "series-existing", "series_name": "Existing", "model_pattern": "M4xx"}

        async def fake_get_series(**_kwargs):
            return existing

        processor.adapter.get_product_series_by_name_and_pattern.side_effect = fake_get_series

        series_data = {
            "series_name": "Existing",
            "model_pattern": "M4xx",
            "series_description": "Existing series",
        }

        series_id, created = await processor._get_or_create_series(
            manufacturer_id="manu-1",
            series_data=series_data,
            adapter=processor._logger_adapter,
        )

        assert series_id == existing["id"]
        assert created is False
        processor.adapter.create_product_series.assert_not_awaited()

    async def test_get_or_create_series_handles_duplicate_key_error(self, mock_database_adapter):
        processor = await self._create_processor(mock_database_adapter)

        async def duplicate_create(_series_dict):
            raise Exception("duplicate key value violates unique constraint (23505)")

        existing = {"id": "series-dup", "series_name": "Dup", "model_pattern": "M4xx"}

        async def fake_get_series(**_kwargs):
            return existing

        processor.adapter.create_product_series.side_effect = duplicate_create
        processor.adapter.get_product_series_by_name_and_pattern.side_effect = fake_get_series

        series_data = {
            "series_name": "Dup",
            "model_pattern": "M4xx",
            "series_description": "Duplicate series",
        }

        series_id, created = await processor._get_or_create_series(
            manufacturer_id="manu-1",
            series_data=series_data,
            adapter=processor._logger_adapter,
        )

        assert series_id == existing["id"]
        assert created is False

    async def test_link_product_to_series_updates_product(self, mock_database_adapter):
        processor = await self._create_processor(mock_database_adapter)

        product_id = "prod-1"
        series_id = "series-1"

        linked = await processor._link_product_to_series(
            product_id=product_id,
            series_id=series_id,
            adapter=processor._logger_adapter,
        )

        assert linked is True
        processor.adapter.update_product.assert_awaited_once_with(
            product_id,
            {"series_id": series_id},
        )
