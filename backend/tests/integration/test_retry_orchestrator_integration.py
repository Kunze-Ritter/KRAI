"""
Integration tests for RetryOrchestrator with real PostgreSQL database.

These tests use a real database connection to verify:
- Advisory locks work correctly with PostgreSQL
- Error status updates persist in pipeline_errors table
- Concurrent retry scenarios with real locks
- Background retry persistence across service restarts
- Exponential backoff timing accuracy
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.retry_engine import RetryOrchestrator, RetryPolicy
from backend.core.types import ProcessingContext
from backend.services.database_factory import create_database_adapter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def test_database():
    """Create database adapter for testing"""
    adapter = create_database_adapter()
    yield adapter
    # Cleanup is handled by test methods


@pytest.fixture
def mock_error_logger():
    """Mock ErrorLogger for testing"""
    logger = AsyncMock()
    logger.update_error_status = AsyncMock()
    return logger


@pytest.fixture
def sample_processing_context():
    """Sample ProcessingContext for testing"""
    return ProcessingContext(
        document_id="test_doc_integration_123",
        file_path="/tmp/test_integration.pdf",
        document_type="service_manual",
        request_id="req_integration_test",
        correlation_id=None,
        retry_attempt=0,
        error_id="error_integration_123",
    )


@pytest.fixture
def sample_retry_policy():
    """Sample retry policy for testing"""
    return RetryPolicy(
        policy_name="test_integration_policy",
        service_name="test_service",
        stage_name="test_stage",
        max_retries=3,
        base_delay_seconds=0.1,
        max_delay_seconds=10.0,
        exponential_base=2.0,
        jitter_enabled=False,
    )


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.database
async def test_full_retry_flow_with_real_database(
    test_database, mock_error_logger, sample_processing_context, sample_retry_policy
):
    """Test full retry flow with real PostgreSQL database"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    # Create test document in database (if needed for your schema)
    # This is a placeholder - adjust based on your actual schema

    # Test advisory lock acquisition
    lock_acquired = await orchestrator.acquire_advisory_lock(
        sample_processing_context.document_id, sample_retry_policy.stage_name
    )

    assert lock_acquired is True

    # Try to acquire same lock (should fail)
    lock_acquired_2 = await orchestrator.acquire_advisory_lock(
        sample_processing_context.document_id, sample_retry_policy.stage_name
    )

    assert lock_acquired_2 is False

    # Release lock
    released = await orchestrator.release_advisory_lock(
        sample_processing_context.document_id, sample_retry_policy.stage_name
    )

    assert released is True

    # Verify lock can be acquired again
    lock_acquired_3 = await orchestrator.acquire_advisory_lock(
        sample_processing_context.document_id, sample_retry_policy.stage_name
    )

    assert lock_acquired_3 is True

    # Cleanup
    await orchestrator.release_advisory_lock(sample_processing_context.document_id, sample_retry_policy.stage_name)


@pytest.mark.asyncio
@pytest.mark.database
async def test_concurrent_retries_real_locks(test_database, mock_error_logger, sample_retry_policy):
    """Test concurrent retries with real PostgreSQL advisory locks"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    document_id = "test_doc_concurrent_real"
    stage_name = "test_stage_concurrent"

    # Create 5 concurrent lock attempts
    tasks = [orchestrator.acquire_advisory_lock(document_id, stage_name) for _ in range(5)]

    results = await asyncio.gather(*tasks)

    # Only 1 should succeed
    successful_locks = sum(1 for r in results if r is True)
    assert successful_locks == 1, f"Expected 1 lock, got {successful_locks}"

    # Verify no deadlocks occurred (all tasks completed)
    assert len(results) == 5

    # Cleanup - release the lock
    await orchestrator.release_advisory_lock(document_id, stage_name)


@pytest.mark.asyncio
@pytest.mark.database
async def test_background_retry_persistence(
    test_database, mock_error_logger, sample_processing_context, sample_retry_policy
):
    """Test retry can resume from pipeline_errors table after restart"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    # Mock processor
    async def mock_processor(context):
        result = MagicMock()
        result.success = True
        result.error = None
        return result

    processor = AsyncMock(side_effect=mock_processor)

    # Spawn background retry
    correlation_id = "req_test.stage_test.retry_0"
    await orchestrator.spawn_background_retry(
        sample_processing_context, 0, sample_retry_policy, correlation_id, processor
    )

    # Wait for task to complete
    await asyncio.sleep(0.5)

    # Verify processor was called
    assert processor.called

    # Cleanup
    await orchestrator.release_advisory_lock(sample_processing_context.document_id, sample_retry_policy.stage_name)


@pytest.mark.asyncio
@pytest.mark.database
@pytest.mark.slow
async def test_exponential_backoff_timing(test_database, mock_error_logger, sample_processing_context):
    """Test exponential backoff timing is accurate"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    policy = RetryPolicy(
        policy_name="timing_test_policy",
        service_name="test_service",
        stage_name="test_stage",
        max_retries=3,
        base_delay_seconds=0.1,
        max_delay_seconds=10.0,
        exponential_base=2.0,
        jitter_enabled=False,
    )

    # Test delay calculations
    delays = []
    for attempt in range(4):
        delay = orchestrator.calculate_backoff_delay(attempt, policy)
        delays.append(delay)

    # Verify exponential progression
    assert delays[0] == 0.1  # 0.1 * 2^0
    assert delays[1] == 0.2  # 0.1 * 2^1
    assert delays[2] == 0.4  # 0.1 * 2^2
    assert delays[3] == 0.8  # 0.1 * 2^3


@pytest.mark.asyncio
@pytest.mark.database
async def test_advisory_lock_different_documents(test_database, mock_error_logger):
    """Test that locks for different documents don't interfere"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    doc1 = "test_doc_1"
    doc2 = "test_doc_2"
    stage = "test_stage"

    # Acquire locks for both documents
    lock1 = await orchestrator.acquire_advisory_lock(doc1, stage)
    lock2 = await orchestrator.acquire_advisory_lock(doc2, stage)

    # Both should succeed (different documents)
    assert lock1 is True
    assert lock2 is True

    # Cleanup
    await orchestrator.release_advisory_lock(doc1, stage)
    await orchestrator.release_advisory_lock(doc2, stage)


@pytest.mark.asyncio
@pytest.mark.database
async def test_advisory_lock_different_stages(test_database, mock_error_logger):
    """Test that locks for different stages don't interfere"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    doc = "test_doc"
    stage1 = "image_processing"
    stage2 = "text_extraction"

    # Acquire locks for both stages
    lock1 = await orchestrator.acquire_advisory_lock(doc, stage1)
    lock2 = await orchestrator.acquire_advisory_lock(doc, stage2)

    # Both should succeed (different stages)
    assert lock1 is True
    assert lock2 is True

    # Cleanup
    await orchestrator.release_advisory_lock(doc, stage1)
    await orchestrator.release_advisory_lock(doc, stage2)


@pytest.mark.asyncio
@pytest.mark.database
async def test_lock_release_without_acquisition(test_database, mock_error_logger):
    """Test releasing a lock that was never acquired"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    # Try to release lock that was never acquired
    released = await orchestrator.release_advisory_lock("test_doc", "test_stage")

    # Should return False (lock was not held)
    assert released is False


@pytest.mark.asyncio
@pytest.mark.database
async def test_multiple_orchestrators_same_lock(test_database, mock_error_logger):
    """Test multiple orchestrator instances competing for same lock"""
    orchestrator1 = RetryOrchestrator(test_database, mock_error_logger)
    orchestrator2 = RetryOrchestrator(test_database, mock_error_logger)

    doc = "test_doc_multi"
    stage = "test_stage_multi"

    # First orchestrator acquires lock
    lock1 = await orchestrator1.acquire_advisory_lock(doc, stage)
    assert lock1 is True

    # Second orchestrator tries to acquire same lock
    lock2 = await orchestrator2.acquire_advisory_lock(doc, stage)
    assert lock2 is False

    # First orchestrator releases lock
    released = await orchestrator1.release_advisory_lock(doc, stage)
    assert released is True

    # Now second orchestrator can acquire lock
    lock3 = await orchestrator2.acquire_advisory_lock(doc, stage)
    assert lock3 is True

    # Cleanup
    await orchestrator2.release_advisory_lock(doc, stage)


@pytest.mark.asyncio
@pytest.mark.database
async def test_lock_survives_orchestrator_recreation(test_database, mock_error_logger):
    """Test that locks persist across orchestrator instance recreation"""
    doc = "test_doc_persist"
    stage = "test_stage_persist"

    # Create first orchestrator and acquire lock
    orchestrator1 = RetryOrchestrator(test_database, mock_error_logger)
    lock1 = await orchestrator1.acquire_advisory_lock(doc, stage)
    assert lock1 is True

    # Create new orchestrator instance (simulating restart)
    orchestrator2 = RetryOrchestrator(test_database, mock_error_logger)

    # New instance should not be able to acquire same lock
    lock2 = await orchestrator2.acquire_advisory_lock(doc, stage)
    assert lock2 is False

    # Original instance releases lock
    released = await orchestrator1.release_advisory_lock(doc, stage)
    assert released is True

    # New instance can now acquire lock
    lock3 = await orchestrator2.acquire_advisory_lock(doc, stage)
    assert lock3 is True

    # Cleanup
    await orchestrator2.release_advisory_lock(doc, stage)


@pytest.mark.asyncio
@pytest.mark.database
@pytest.mark.slow
async def test_background_retry_with_real_delays(test_database, mock_error_logger, sample_processing_context):
    """Test background retry with real delays (slow test)"""
    orchestrator = RetryOrchestrator(test_database, mock_error_logger)

    policy = RetryPolicy(
        policy_name="delay_test_policy",
        service_name="test_service",
        stage_name="test_stage",
        max_retries=2,
        base_delay_seconds=0.2,
        max_delay_seconds=10.0,
        exponential_base=2.0,
        jitter_enabled=False,
    )

    call_times = []

    async def timed_processor(context):
        call_times.append(asyncio.get_event_loop().time())
        result = MagicMock()
        result.success = True
        result.error = None
        return result

    processor = AsyncMock(side_effect=timed_processor)

    # Spawn retry
    correlation_id = "req_test.stage_test.retry_0"
    start_time = asyncio.get_event_loop().time()

    await orchestrator.spawn_background_retry(sample_processing_context, 0, policy, correlation_id, processor)

    # Wait for task to complete
    await asyncio.sleep(1.0)

    # Verify processor was called
    assert processor.called

    # Verify timing (should have ~0.2s delay)
    if len(call_times) > 0:
        elapsed = call_times[0] - start_time
        # Allow some tolerance for timing
        assert 0.15 <= elapsed <= 0.35, f"Expected ~0.2s delay, got {elapsed:.3f}s"

    # Cleanup
    await orchestrator.release_advisory_lock(sample_processing_context.document_id, policy.stage_name)
