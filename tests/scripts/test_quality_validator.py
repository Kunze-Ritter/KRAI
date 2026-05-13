import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts.quality_validator import QualityValidator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "processors"))
import conftest as processors_conftest


@pytest.fixture
async def mock_db_adapter():
    """Create MockDatabaseAdapter instance from tests/processors/conftest.py."""
    fixture_factory = processors_conftest.mock_database_adapter
    raw_factory = getattr(fixture_factory, "__wrapped__", fixture_factory)
    adapter_generator = raw_factory()
    adapter = await adapter_generator.__anext__()
    try:
        yield adapter
    finally:
        try:
            await adapter_generator.__anext__()
        except StopAsyncIteration:
            pass


@pytest.fixture
def test_thresholds():
    return {
        "min_chunks": 100,
        "min_images": 10,
        "min_error_codes": 5,
        "min_embedding_coverage": 0.95,
        "min_products": 1,
        "min_parts": 0,
    }


@pytest.mark.asyncio
async def test_check_correctness_with_valid_products(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    mock_db_adapter.fetch_all = AsyncMock(return_value=[{"model_number": "HP E877", "manufacturer": "HP Inc."}])

    result = await validator._check_correctness(["doc-1"])

    assert result["products_count"] == 1
    assert result["model_detected"] is True
    assert result["manufacturer_detected"] is True
    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_check_correctness_with_no_products(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    mock_db_adapter.fetch_all = AsyncMock(return_value=[])

    result = await validator._check_correctness(["doc-1"])

    assert result["products_count"] == 0
    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_check_relationships_with_valid_links(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    mock_db_adapter.fetch_one = AsyncMock(return_value={"doc_count": 2, "product_count": 1})

    result = await validator._check_relationships(["doc-1", "doc-2"])

    assert result["linked_documents"] == 2
    assert result["linked_products"] == 1
    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_check_relationships_with_no_links(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    mock_db_adapter.fetch_one = AsyncMock(return_value={"doc_count": 0, "product_count": 0})

    result = await validator._check_relationships(["doc-1", "doc-2"])

    assert result["linked_documents"] == 0
    assert result["linked_products"] == 0
    assert result["status"] == "FAIL"


@pytest.mark.asyncio
async def test_check_completeness_parts_manufacturer_based(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)

    async def fetch_one_side_effect(query, _params):
        if "krai_intelligence.chunks" in query:
            return {"count": 100}
        if "krai_content.images" in query:
            return {"count": 10}
        if "krai_intelligence.error_codes" in query:
            return {"count": 5}
        if "FROM krai_parts.parts_catalog pc" in query:
            return {"count": 50}
        return {"count": 0}

    mock_db_adapter.fetch_one = AsyncMock(side_effect=fetch_one_side_effect)

    result = await validator._check_completeness(["doc-1"])

    assert result["parts"]["count"] == 50
    assert result["parts"]["parts_query_method"] == "manufacturer_based"
    assert result["parts"]["status"] == "PASS"


@pytest.mark.asyncio
async def test_check_completeness_parts_fallback_zero(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)

    async def fetch_one_side_effect(query, _params):
        if "krai_intelligence.chunks" in query:
            return {"count": 100}
        if "krai_content.images" in query:
            return {"count": 10}
        if "krai_intelligence.error_codes" in query:
            return {"count": 5}
        if "FROM krai_parts.parts_catalog pc" in query:
            raise RuntimeError("simulated query failure")
        return {"count": 0}

    mock_db_adapter.fetch_one = AsyncMock(side_effect=fetch_one_side_effect)

    result = await validator._check_completeness(["doc-1"])

    assert result["parts"]["count"] == 0
    assert result["parts"]["parts_query_method"] == "fallback_zero"
    assert result["parts"]["status"] == "PASS"


@pytest.mark.asyncio
async def test_validate_overall_pass(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    validator._check_completeness = AsyncMock(return_value={"status": "PASS"})
    validator._check_correctness = AsyncMock(return_value={"status": "PASS"})
    validator._check_embeddings = AsyncMock(return_value={"status": "PASS"})
    validator._check_relationships = AsyncMock(return_value={"status": "PASS"})
    validator._check_stage_status = AsyncMock(return_value={"status": "PASS"})

    result = await validator.validate(["doc-1"])

    assert result["status"] == "PASS"


@pytest.mark.asyncio
async def test_validate_overall_fail(mock_db_adapter, test_thresholds):
    validator = QualityValidator(mock_db_adapter, test_thresholds)
    validator._check_completeness = AsyncMock(return_value={"status": "PASS"})
    validator._check_correctness = AsyncMock(return_value={"status": "FAIL"})
    validator._check_embeddings = AsyncMock(return_value={"status": "PASS"})
    validator._check_relationships = AsyncMock(return_value={"status": "PASS"})
    validator._check_stage_status = AsyncMock(return_value={"status": "PASS"})

    result = await validator.validate(["doc-1"])

    assert result["status"] == "FAIL"
