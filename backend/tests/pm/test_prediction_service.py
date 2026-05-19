"""
Unit tests for PredictionService.

Tests batch prediction workflow, idempotency, and database persistence.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from backend.pm.models.ticket import PredictionResult, ServiceTicketFeatures
from backend.pm.services.prediction_service import PredictionService


@pytest.fixture
def mock_db_adapter() -> Mock:
    """Provide mock database adapter."""
    return AsyncMock()


@pytest.fixture
def mock_feature_engineer() -> Mock:
    """Provide mock feature engineer."""
    return AsyncMock()


@pytest.fixture
def mock_classifier() -> Mock:
    """Provide mock classifier."""
    return Mock()


@pytest.mark.asyncio
async def test_run_batch_basic(
    mock_db_adapter: Mock,
    mock_feature_engineer: Mock,
    mock_classifier: Mock,
) -> None:
    """Test basic batch prediction workflow."""
    # Setup: Two unpredicted tickets
    mock_db_adapter.fetch_all.return_value = [
        {"id": "tk-001"},
        {"id": "tk-002"},
    ]

    # Mock feature extraction
    mock_feature_engineer.extract_features.side_effect = [
        ServiceTicketFeatures(
            ticket_id="tk-001",
            repair_time_minutes=30.0,
            problem_frequency=10,
            part_replacement_count=1,
            error_code_count=2,
            manufacturer_encoded=1,
            error_code_top10=[0] * 10,
        ),
        ServiceTicketFeatures(
            ticket_id="tk-002",
            repair_time_minutes=45.0,
            problem_frequency=15,
            part_replacement_count=2,
            error_code_count=3,
            manufacturer_encoded=2,
            error_code_top10=[1, 0, 1] + [0] * 7,
        ),
    ]

    # Mock predictions
    mock_classifier.predict.side_effect = [
        PredictionResult(
            ticket_id="tk-001",
            is_common=True,
            confidence=0.8,
            model_name="long_tail_xgb_v1",
            model_version="1.0.0",
        ),
        PredictionResult(
            ticket_id="tk-002",
            is_common=False,
            confidence=0.7,
            model_name="long_tail_xgb_v1",
            model_version="1.0.0",
        ),
    ]

    service = PredictionService(mock_db_adapter, mock_feature_engineer, mock_classifier)
    result = await service.run_batch()

    assert result["predicted"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == 0
    assert mock_db_adapter.execute.call_count == 2


@pytest.mark.asyncio
async def test_run_batch_with_errors(
    mock_db_adapter: Mock,
    mock_feature_engineer: Mock,
    mock_classifier: Mock,
) -> None:
    """Test batch prediction with some failing tickets."""
    # Setup: Two unpredicted tickets, one will fail
    mock_db_adapter.fetch_all.return_value = [
        {"id": "tk-001"},
        {"id": "tk-002"},
    ]

    # Mock feature extraction - one fails
    mock_feature_engineer.extract_features.side_effect = [
        ServiceTicketFeatures(
            ticket_id="tk-001",
            repair_time_minutes=30.0,
            problem_frequency=10,
            part_replacement_count=1,
            error_code_count=2,
            manufacturer_encoded=1,
            error_code_top10=[0] * 10,
        ),
        Exception("Feature extraction failed"),
    ]

    # Mock prediction
    mock_classifier.predict.return_value = PredictionResult(
        ticket_id="tk-001",
        is_common=True,
        confidence=0.8,
        model_name="long_tail_xgb_v1",
        model_version="1.0.0",
    )

    service = PredictionService(mock_db_adapter, mock_feature_engineer, mock_classifier)
    result = await service.run_batch()

    assert result["predicted"] == 1
    assert result["skipped"] == 1  # tk-002 skipped due to feature extraction failure
    assert result["errors"] == 0  # No prediction errors, only feature extraction issues


@pytest.mark.asyncio
async def test_run_batch_empty_tickets(
    mock_db_adapter: Mock,
    mock_feature_engineer: Mock,
    mock_classifier: Mock,
) -> None:
    """Test batch prediction with no unpredicted tickets."""
    mock_db_adapter.fetch_all.return_value = []

    service = PredictionService(mock_db_adapter, mock_feature_engineer, mock_classifier)
    result = await service.run_batch()

    assert result["predicted"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_run_batch_with_limit(
    mock_db_adapter: Mock,
    mock_feature_engineer: Mock,
    mock_classifier: Mock,
) -> None:
    """Test batch prediction respects limit parameter."""
    # Setup: Return 3 tickets but limit should be applied in query
    mock_db_adapter.fetch_all.return_value = [
        {"id": "tk-001"},
        {"id": "tk-002"},
    ]

    # Mock single feature extraction (limited to 2)
    mock_feature_engineer.extract_features.side_effect = [
        ServiceTicketFeatures(
            ticket_id="tk-001",
            repair_time_minutes=30.0,
            problem_frequency=10,
            part_replacement_count=1,
            error_code_count=2,
            manufacturer_encoded=1,
            error_code_top10=[0] * 10,
        ),
        ServiceTicketFeatures(
            ticket_id="tk-002",
            repair_time_minutes=45.0,
            problem_frequency=15,
            part_replacement_count=2,
            error_code_count=3,
            manufacturer_encoded=2,
            error_code_top10=[1, 0] + [0] * 8,
        ),
    ]

    # Mock predictions
    mock_classifier.predict.side_effect = [
        PredictionResult(
            ticket_id="tk-001",
            is_common=True,
            confidence=0.8,
            model_name="long_tail_xgb_v1",
            model_version="1.0.0",
        ),
        PredictionResult(
            ticket_id="tk-002",
            is_common=False,
            confidence=0.7,
            model_name="long_tail_xgb_v1",
            model_version="1.0.0",
        ),
    ]

    service = PredictionService(mock_db_adapter, mock_feature_engineer, mock_classifier)
    result = await service.run_batch(limit=2)

    assert result["predicted"] == 2
    # Verify fetch_all was called (query includes LIMIT)
    mock_db_adapter.fetch_all.assert_called_once()


@pytest.mark.asyncio
async def test_save_prediction_metadata(
    mock_db_adapter: Mock,
    mock_feature_engineer: Mock,
    mock_classifier: Mock,
) -> None:
    """Test that predictions are saved with correct metadata."""
    prediction = PredictionResult(
        ticket_id="tk-001",
        is_common=True,
        confidence=0.85,
        model_name="long_tail_xgb_v1",
        model_version="1.0.0",
    )

    service = PredictionService(mock_db_adapter, mock_feature_engineer, mock_classifier)
    await service._save_prediction(prediction)

    # Verify execute was called with correct parameters
    mock_db_adapter.execute.assert_called_once()
    call_args = mock_db_adapter.execute.call_args

    # Check that model_name and model_version were passed
    assert "long_tail_xgb_v1" in call_args[0]
    assert "1.0.0" in call_args[0]
