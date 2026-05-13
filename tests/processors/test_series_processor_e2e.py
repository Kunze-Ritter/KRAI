import sys
import types
from types import SimpleNamespace
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
@pytest.mark.e2e
@pytest.mark.asyncio
class TestSeriesProcessorE2E:
    async def _create_processor_with_product(self, mock_database_adapter, manufacturer_name: str, model_number: str):
        manufacturer_id = "manu-1"
        product_id = "prod-1"

        if not hasattr(mock_database_adapter, "manufacturers"):
            mock_database_adapter.manufacturers = {}
        if not hasattr(mock_database_adapter, "products"):
            mock_database_adapter.products = {}
        if not hasattr(mock_database_adapter, "product_series"):
            mock_database_adapter.product_series = {}

        mock_database_adapter.manufacturers[manufacturer_id] = {
            "id": manufacturer_id,
            "name": manufacturer_name,
        }
        mock_database_adapter.products[product_id] = {
            "id": product_id,
            "model_number": model_number,
            "manufacturer_id": manufacturer_id,
            "series_id": None,
        }

        processor = SeriesProcessor(database_adapter=mock_database_adapter)

        mock_database_adapter.get_manufacturer = AsyncMock(
            return_value=mock_database_adapter.manufacturers[manufacturer_id]
        )
        mock_database_adapter.get_product = AsyncMock(return_value=mock_database_adapter.products[product_id])
        mock_database_adapter.update_product = AsyncMock(return_value=True)

        async def fake_get_series_by_name_and_pattern(manufacturer_id: str, series_name: str, model_pattern: str):
            for s in mock_database_adapter.product_series.values():
                if (
                    s["manufacturer_id"] == manufacturer_id
                    and s["series_name"] == series_name
                    and s["model_pattern"] == model_pattern
                ):
                    return s
            return None

        async def fake_create_series(series_dict):
            series_id = f"series-{len(mock_database_adapter.product_series)+1}"
            stored = dict(series_dict)
            stored["id"] = series_id
            mock_database_adapter.product_series[series_id] = stored
            return stored

        mock_database_adapter.get_product_series_by_name_and_pattern = AsyncMock(
            side_effect=fake_get_series_by_name_and_pattern
        )
        mock_database_adapter.create_product_series = AsyncMock(side_effect=fake_create_series)

        return processor, product_id, manufacturer_id

    async def test_process_product_detects_series_and_links(self, mock_database_adapter):
        processor, product_id, manufacturer_id = await self._create_processor_with_product(
            mock_database_adapter,
            manufacturer_name="HP",
            model_number="M404n",
        )

        result = await processor.process_product(product_id)

        assert result is not None
        assert result["series_detected"] is True
        assert result["product_linked"] is True
        assert result["series_id"]

        updated = mock_database_adapter.products[product_id]
        assert updated["series_id"] == result["series_id"]

    async def test_process_product_uses_existing_series(self, mock_database_adapter):
        processor, product_id, manufacturer_id = await self._create_processor_with_product(
            mock_database_adapter,
            manufacturer_name="HP",
            model_number="M404n",
        )

        series_data = detect_series("M404n", "HP")
        existing_id = "series-existing"
        mock_database_adapter.product_series[existing_id] = {
            "id": existing_id,
            "manufacturer_id": manufacturer_id,
            "series_name": series_data["series_name"],
            "model_pattern": series_data.get("model_pattern"),
            "series_description": series_data.get("series_description"),
        }

        async def fake_get_series_by_name_and_pattern(manufacturer_id: str, series_name: str, model_pattern: str):
            return mock_database_adapter.product_series[existing_id]

        processor.adapter.get_product_series_by_name_and_pattern = AsyncMock(
            side_effect=fake_get_series_by_name_and_pattern
        )
        processor.adapter.create_product_series = AsyncMock()

        result = await processor.process_product(product_id)

        assert result is not None
        assert result["series_detected"] is True
        assert result["series_created"] is False
        assert result["series_id"] == existing_id
        processor.adapter.create_product_series.assert_not_awaited()

    async def test_process_all_products_batch_processing(self, mock_database_adapter):
        manufacturer_id = "manu-1"
        mock_database_adapter.manufacturers[manufacturer_id] = {"id": manufacturer_id, "name": "HP"}

        for i in range(3):
            product_id = f"prod-{i}"
            mock_database_adapter.products[product_id] = {
                "id": product_id,
                "model_number": "M404n",
                "manufacturer_id": manufacturer_id,
                "series_id": None,
            }

        processor = SeriesProcessor(database_adapter=mock_database_adapter)

        async def fake_get_products_without_series(manufacturer_id: str | None = None):
            return list(mock_database_adapter.products.values())

        async def fake_get_manufacturer(manufacturer_id: str):
            return mock_database_adapter.manufacturers[manufacturer_id]

        async def fake_get_series_by_name_and_pattern(manufacturer_id: str, series_name: str, model_pattern: str):
            for s in mock_database_adapter.product_series.values():
                if (
                    s["manufacturer_id"] == manufacturer_id
                    and s["series_name"] == series_name
                    and s["model_pattern"] == model_pattern
                ):
                    return s
            return None

        async def fake_create_series(series_dict):
            series_id = f"series-{len(mock_database_adapter.product_series)+1}"
            stored = dict(series_dict)
            stored["id"] = series_id
            mock_database_adapter.product_series[series_id] = stored
            return stored

        mock_database_adapter.get_products_without_series = AsyncMock(side_effect=fake_get_products_without_series)
        mock_database_adapter.get_manufacturer = AsyncMock(side_effect=fake_get_manufacturer)
        mock_database_adapter.get_product_series_by_name_and_pattern = AsyncMock(
            side_effect=fake_get_series_by_name_and_pattern
        )
        mock_database_adapter.create_product_series = AsyncMock(side_effect=fake_create_series)
        mock_database_adapter.update_product = AsyncMock(return_value=True)

        stats = await processor.process_all_products()

        assert stats["products_processed"] == 3
        assert stats["series_detected"] >= 1
        assert stats["products_linked"] == 3
        assert stats["errors"] == 0

    async def test_process_product_with_no_series_detected(self, mock_database_adapter):
        processor, product_id, manufacturer_id = await self._create_processor_with_product(
            mock_database_adapter,
            manufacturer_name="HP",
            model_number="XX1",  # unlikely to match known patterns
        )

        # Force detector to return None
        async def no_series(*_args, **_kwargs):
            return None

        processor.adapter.get_product_series_by_name_and_pattern = AsyncMock(return_value=None)
        # Monkeypatch module-level detect_series used by SeriesProcessor
        from backend.processors import series_processor as sp_mod

        original_detect = sp_mod.detect_series
        sp_mod.detect_series = lambda *_a, **_k: None
        try:
            result = await processor.process_product(product_id)
        finally:
            sp_mod.detect_series = original_detect

        assert result is not None
        assert result["series_detected"] is False
        assert result["product_linked"] is False

    async def test_get_series_products_and_manufacturer_series(self, mock_database_adapter):
        manufacturer_id = "manu-1"
        mock_database_adapter.manufacturers[manufacturer_id] = {"id": manufacturer_id, "name": "HP"}

        series_id = "series-1"
        mock_database_adapter.product_series[series_id] = {
            "id": series_id,
            "manufacturer_id": manufacturer_id,
            "series_name": "LaserJet Pro",
            "model_pattern": "M4xx",
            "series_description": "HP LaserJet Pro M400 series",
        }

        for i in range(2):
            product_id = f"prod-{i}"
            mock_database_adapter.products[product_id] = {
                "id": product_id,
                "model_number": "M404n",
                "manufacturer_id": manufacturer_id,
                "series_id": series_id,
            }

        processor = SeriesProcessor(database_adapter=mock_database_adapter)

        async def fake_get_series_by_manufacturer(manufacturer_id: str):
            return list(mock_database_adapter.product_series.values())

        mock_database_adapter.get_product_series_by_manufacturer = AsyncMock(
            side_effect=fake_get_series_by_manufacturer
        )

        series_products = await processor.get_series_products(series_id)
        assert len(series_products) == 2

        manufacturer_series = await processor.get_manufacturer_series(manufacturer_id)
        assert len(manufacturer_series) == 1
        assert manufacturer_series[0]["product_count"] == 2

    async def test_process_with_processing_context_wrapper(self, mock_database_adapter):
        processor, product_id, manufacturer_id = await self._create_processor_with_product(
            mock_database_adapter,
            manufacturer_name="HP",
            model_number="M404n",
        )

        context = SimpleNamespace(product_id=product_id)
        result = await processor.process(context)
        assert result.success is True
        assert result.data["series_detected"] is True
        assert result.metadata["product_id"] == product_id
