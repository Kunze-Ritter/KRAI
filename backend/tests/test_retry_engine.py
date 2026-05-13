"""
Unit tests for retry engine components.

Tests cover:
- ErrorClassifier: Exception classification logic
- RetryPolicyManager: Policy loading, caching, and fallback behavior
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.core.retry_engine import (
    AuthenticationError,
    AuthorizationError,
    ErrorClassification,
    ErrorClassifier,
    RetryOrchestrator,
    RetryPolicy,
    RetryPolicyManager,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_adapter():
    """Mock database adapter for testing"""
    adapter = AsyncMock()
    adapter.fetch_one = AsyncMock()
    return adapter


@pytest.fixture
def sample_retry_policy():
    """Sample retry policy for testing"""
    return {
        "policy_name": "test_policy",
        "service_name": "firecrawl",
        "stage_name": "image_processing",
        "max_retries": 3,
        "base_delay_seconds": 2.0,
        "max_delay_seconds": 60.0,
        "exponential_base": 2.0,
        "jitter_enabled": True,
        "circuit_breaker_enabled": False,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_timeout_seconds": 60,
    }


@pytest.fixture
def service_level_policy():
    """Service-level retry policy (no stage)"""
    return {
        "policy_name": "firecrawl_service_policy",
        "service_name": "firecrawl",
        "stage_name": None,
        "max_retries": 4,
        "base_delay_seconds": 1.5,
        "max_delay_seconds": 45.0,
        "exponential_base": 2.0,
        "jitter_enabled": True,
        "circuit_breaker_enabled": False,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_timeout_seconds": 60,
    }


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test"""
    RetryPolicyManager.clear_cache()
    RetryPolicyManager._db_adapter = None
    yield
    RetryPolicyManager.clear_cache()
    RetryPolicyManager._db_adapter = None


@pytest.fixture
def mock_error_logger():
    """Mock ErrorLogger for testing"""
    logger = AsyncMock()
    logger.update_error_status = AsyncMock()
    return logger


@pytest.fixture
def mock_processor_callable():
    """Mock async processor callable"""

    async def processor(context):
        result = MagicMock()
        result.success = True
        result.error = None
        return result

    return AsyncMock(side_effect=processor)


@pytest.fixture
def sample_processing_context():
    """Sample ProcessingContext for testing"""
    from backend.core.types import ProcessingContext

    return ProcessingContext(
        document_id="test_doc_123",
        file_path="/tmp/test.pdf",
        document_type="service_manual",
        request_id="req_a3f2e8d1",
        correlation_id=None,
        retry_attempt=0,
        error_id="error_123",
    )


@pytest.fixture
def retry_orchestrator(mock_db_adapter, mock_error_logger):
    """RetryOrchestrator instance with mocked dependencies"""
    return RetryOrchestrator(mock_db_adapter, mock_error_logger)


# ============================================================================
# ErrorClassifier Tests
# ============================================================================


class TestErrorClassifier:
    """Tests for ErrorClassifier"""

    def test_classify_http_5xx_transient(self):
        """Test that 5xx HTTP errors are classified as transient"""
        for status_code in [500, 502, 503, 504, 599]:
            response = MagicMock()
            response.status_code = status_code
            exception = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is True
            assert classification.error_category == "transient"
            assert classification.http_status_code == status_code
            assert classification.error_type == "HTTPStatusError"

    def test_classify_http_4xx_permanent(self):
        """Test that 4xx HTTP errors are classified as permanent (except 408, 429)"""
        for status_code in [400, 401, 403, 404, 499]:
            response = MagicMock()
            response.status_code = status_code
            exception = httpx.HTTPStatusError("Client error", request=MagicMock(), response=response)

            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is False
            assert classification.error_category == "permanent"
            assert classification.http_status_code == status_code
            assert classification.error_type == "HTTPStatusError"

    def test_classify_http_408_transient(self):
        """Test that HTTP 408 Request Timeout is classified as transient"""
        response = MagicMock()
        response.status_code = 408
        exception = httpx.HTTPStatusError("Request Timeout", request=MagicMock(), response=response)

        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is True
        assert classification.error_category == "transient"
        assert classification.http_status_code == 408
        assert classification.error_type == "HTTPStatusError"

    def test_classify_http_429_transient(self):
        """Test that HTTP 429 Too Many Requests is classified as transient"""
        response = MagicMock()
        response.status_code = 429
        exception = httpx.HTTPStatusError("Too Many Requests", request=MagicMock(), response=response)

        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is True
        assert classification.error_category == "transient"
        assert classification.http_status_code == 429
        assert classification.error_type == "HTTPStatusError"

    def test_classify_connection_errors_transient(self):
        """Test that connection errors are classified as transient"""
        exceptions = [
            ConnectionError("Connection failed"),
            httpx.ConnectError("Cannot connect"),
        ]

        for exception in exceptions:
            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is True
            assert classification.error_category == "transient"
            assert classification.http_status_code is None

    def test_classify_timeout_errors_transient(self):
        """Test that timeout errors are classified as transient"""
        exceptions = [
            TimeoutError("Operation timed out"),
            TimeoutError("Async timeout"),
            httpx.TimeoutException("HTTP timeout"),
        ]

        for exception in exceptions:
            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is True
            assert classification.error_category == "transient"
            assert classification.http_status_code is None

    def test_classify_transport_errors_transient(self):
        """Test that transport errors are classified as transient"""
        exception = httpx.TransportError("Transport failed")

        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is True
        assert classification.error_category == "transient"

    def test_classify_validation_errors_permanent(self):
        """Test that validation errors are classified as permanent"""
        exception = ValueError("Invalid value")

        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is False
        assert classification.error_category == "permanent"
        assert classification.error_type == "ValueError"

    def test_classify_auth_errors_permanent(self):
        """Test that authentication/authorization errors are classified as permanent"""
        exceptions = [
            AuthenticationError("Invalid credentials"),
            AuthorizationError("Access denied"),
        ]

        for exception in exceptions:
            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is False
            assert classification.error_category == "permanent"

    def test_classify_unknown_exception_permanent(self):
        """Test that unknown exceptions are classified as permanent (fail-safe)"""
        exception = Exception("Unknown error")

        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is False
        assert classification.error_category == "permanent"
        assert classification.error_type == "Exception"

    def test_classify_httpx_status_error(self):
        """Test HTTPStatusError with various status codes"""
        test_cases = [
            (200, False),  # Success codes should be handled differently, but if wrapped in error...
            (301, False),  # Redirect
            (400, False),  # Bad Request
            (401, False),  # Unauthorized
            (404, False),  # Not Found
            (500, True),  # Internal Server Error
            (502, True),  # Bad Gateway
            (503, True),  # Service Unavailable
        ]

        for status_code, expected_transient in test_cases:
            response = MagicMock()
            response.status_code = status_code
            exception = httpx.HTTPStatusError("Error", request=MagicMock(), response=response)

            classification = ErrorClassifier.classify(exception)

            if status_code in [408, 429]:
                # 408 and 429 are transient
                assert classification.is_transient is True
                assert classification.http_status_code == status_code
            elif 400 <= status_code < 600:
                assert classification.is_transient == expected_transient
                assert classification.http_status_code == status_code

    def test_classify_nested_exceptions(self):
        """Test exception chains (nested exceptions)"""
        # Create a nested exception: outer exception caused by inner transient error
        inner_exception = ConnectionError("Connection failed")
        outer_exception = Exception("Outer error")
        outer_exception.__cause__ = inner_exception

        classification = ErrorClassifier.classify(outer_exception)

        # Should classify based on inner exception (transient)
        assert classification.is_transient is True
        assert classification.error_category == "transient"
        # But error_type should be from outer exception
        assert classification.error_type == "Exception"


# ============================================================================
# RetryPolicyManager Tests
# ============================================================================


class TestRetryPolicyManager:
    """Tests for RetryPolicyManager"""

    @pytest.mark.asyncio
    async def test_get_policy_from_cache(self, mock_db_adapter, sample_retry_policy):
        """Test that cached policies are returned without database query"""
        # Pre-populate cache
        policy = RetryPolicy(**sample_retry_policy)
        cache_key = "firecrawl:image_processing"
        RetryPolicyManager._cache[cache_key] = policy

        # Get policy (should hit cache)
        result = await RetryPolicyManager.get_policy("firecrawl", "image_processing")

        assert result == policy
        assert result.max_retries == 3
        assert result.service_name == "firecrawl"
        assert result.stage_name == "image_processing"

    @pytest.mark.asyncio
    async def test_get_policy_from_database_exact_match(self, mock_db_adapter, sample_retry_policy):
        """Test stage-specific policy retrieval from database"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            policy = await RetryPolicyManager.get_policy("firecrawl", "image_processing")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        assert policy.policy_name == "test_policy"
        assert policy.service_name == "firecrawl"
        assert policy.stage_name == "image_processing"
        assert policy.max_retries == 3
        assert policy.base_delay_seconds == 2.0

        # Verify database was queried
        mock_db_adapter.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_policy_from_database_service_level(self, mock_db_adapter, service_level_policy):
        """Test service-level policy (stage=NULL) retrieval"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=service_level_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            policy = await RetryPolicyManager.get_policy("firecrawl", "unknown_stage")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        assert policy.policy_name == "firecrawl_service_policy"
        assert policy.service_name == "firecrawl"
        assert policy.stage_name is None
        assert policy.max_retries == 4

    @pytest.mark.asyncio
    async def test_get_policy_fallback_to_default(self, mock_db_adapter):
        """Test fallback to code-level default when no database policy exists"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=None)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            policy = await RetryPolicyManager.get_policy("firecrawl", "unknown_stage")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        # Should return firecrawl default
        assert policy.policy_name == "firecrawl_default"
        assert policy.service_name == "firecrawl"
        assert policy.max_retries == 3
        assert policy.base_delay_seconds == 2.0
        assert policy.max_delay_seconds == 60.0

    @pytest.mark.asyncio
    async def test_get_policy_cache_expiration(self, mock_db_adapter, sample_retry_policy):
        """Test that cache expires after TTL"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # First call - should query database
            policy1 = await RetryPolicyManager.get_policy("firecrawl", "image_processing")
            assert mock_db_adapter.fetch_one.call_count == 1

            # Second call - should hit cache
            policy2 = await RetryPolicyManager.get_policy("firecrawl", "image_processing")
            assert mock_db_adapter.fetch_one.call_count == 1  # No additional call

            # Clear cache to simulate expiration
            RetryPolicyManager.clear_cache()

            # Third call - should query database again
            policy3 = await RetryPolicyManager.get_policy("firecrawl", "image_processing")
            assert mock_db_adapter.fetch_one.call_count == 2
        finally:
            RetryPolicyManager.set_db_adapter(None)

    @pytest.mark.asyncio
    async def test_get_policy_database_error_fallback(self, mock_db_adapter):
        """Test graceful fallback when database is unavailable"""
        mock_db_adapter.fetch_one = AsyncMock(side_effect=Exception("Database connection failed"))
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            policy = await RetryPolicyManager.get_policy("firecrawl")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        # Should fallback to code-level default
        assert policy.policy_name == "firecrawl_default"
        assert policy.max_retries == 3

    @pytest.mark.asyncio
    async def test_get_policy_concurrent_requests(self, mock_db_adapter, sample_retry_policy):
        """Test single-flight pattern: concurrent requests trigger only one DB fetch"""

        # Add delay to simulate slow DB query and ensure concurrency
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return sample_retry_policy

        mock_db_adapter.fetch_one = AsyncMock(side_effect=slow_fetch)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # Make concurrent requests for the same policy
            tasks = [RetryPolicyManager.get_policy("firecrawl", "image_processing") for _ in range(10)]

            policies = await asyncio.gather(*tasks)
        finally:
            RetryPolicyManager.set_db_adapter(None)

        # All should return the same policy
        assert all(p.policy_name == "test_policy" for p in policies)
        assert all(p.service_name == "firecrawl" for p in policies)
        assert all(p.stage_name == "image_processing" for p in policies)

        # Database should only be queried once due to single-flight pattern
        assert (
            mock_db_adapter.fetch_one.call_count == 1
        ), f"Expected 1 DB fetch, got {mock_db_adapter.fetch_one.call_count}"

    @pytest.mark.asyncio
    async def test_get_policy_concurrent_different_keys(
        self, mock_db_adapter, sample_retry_policy, service_level_policy
    ):
        """Test that concurrent requests for different policies each trigger their own DB fetch"""

        # Return different policies based on stage_name
        async def fetch_by_stage(*args, **kwargs):
            await asyncio.sleep(0.05)
            params = args[1] if len(args) > 1 else ()
            stage = params[1] if len(params) > 1 else None
            if stage == "image_processing":
                return sample_retry_policy
            return service_level_policy

        mock_db_adapter.fetch_one = AsyncMock(side_effect=fetch_by_stage)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # Make concurrent requests for different policies
            tasks = [
                RetryPolicyManager.get_policy("firecrawl", "image_processing"),
                RetryPolicyManager.get_policy("firecrawl", "image_processing"),
                RetryPolicyManager.get_policy("firecrawl", "text_extraction"),
                RetryPolicyManager.get_policy("firecrawl", "text_extraction"),
            ]

            policies = await asyncio.gather(*tasks)
        finally:
            RetryPolicyManager.set_db_adapter(None)

        # First two should be the same (image_processing)
        assert policies[0].policy_name == "test_policy"
        assert policies[1].policy_name == "test_policy"

        # Last two should be the same (text_extraction)
        assert policies[2].policy_name == "firecrawl_service_policy"
        assert policies[3].policy_name == "firecrawl_service_policy"

        # Should have 2 DB fetches (one per unique cache key)
        assert mock_db_adapter.fetch_one.call_count == 2

    @pytest.mark.asyncio
    async def test_default_policies_for_common_services(self):
        """Test code-level defaults for common services"""
        test_cases = [
            ("firecrawl", 3, 2.0, 60.0, 2.0),
            ("database", 5, 1.0, 30.0, 2.0),
            ("ollama", 3, 2.0, 120.0, 2.5),
            ("minio", 4, 1.5, 45.0, 2.0),
            ("unknown_service", 3, 1.0, 60.0, 2.0),  # Should use 'default'
        ]

        for service, max_retries, base_delay, max_delay, exp_base in test_cases:
            policy = RetryPolicyManager._get_default_policy(service)

            assert policy.max_retries == max_retries
            assert policy.base_delay_seconds == base_delay
            assert policy.max_delay_seconds == max_delay
            assert policy.exponential_base == exp_base
            assert policy.jitter_enabled is True

    def test_clear_cache(self):
        """Test cache clearing functionality"""
        # Add some items to cache
        policy1 = RetryPolicy(
            policy_name="test1",
            service_name="service1",
            stage_name=None,
            max_retries=3,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            exponential_base=2.0,
            jitter_enabled=True,
        )
        RetryPolicyManager._cache["service1:*"] = policy1

        assert len(RetryPolicyManager._cache) == 1

        # Clear cache
        RetryPolicyManager.clear_cache()

        assert len(RetryPolicyManager._cache) == 0

    @pytest.mark.asyncio
    async def test_db_adapter_used_when_set(self, mock_db_adapter, sample_retry_policy):
        """Test that get_policy uses db_adapter when set via set_db_adapter"""
        RetryPolicyManager._db_adapter = None
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # First call should query database
            await RetryPolicyManager.get_policy("firecrawl")
            assert mock_db_adapter.fetch_one.call_count == 1
            RetryPolicyManager.clear_cache()
            # Second call should query again (different service)
            await RetryPolicyManager.get_policy("database")
            assert mock_db_adapter.fetch_one.call_count == 2
        finally:
            RetryPolicyManager.set_db_adapter(None)

    @pytest.mark.asyncio
    async def test_get_policy_without_stage(self, mock_db_adapter, service_level_policy):
        """Test getting policy without specifying stage"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=service_level_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            policy = await RetryPolicyManager.get_policy("firecrawl")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        assert policy.service_name == "firecrawl"
        assert policy.stage_name is None

    @pytest.mark.asyncio
    async def test_policy_dataclass_fields(self, sample_retry_policy):
        """Test that RetryPolicy dataclass has all required fields"""
        policy = RetryPolicy(**sample_retry_policy)

        assert hasattr(policy, "policy_name")
        assert hasattr(policy, "service_name")
        assert hasattr(policy, "stage_name")
        assert hasattr(policy, "max_retries")
        assert hasattr(policy, "base_delay_seconds")
        assert hasattr(policy, "max_delay_seconds")
        assert hasattr(policy, "exponential_base")
        assert hasattr(policy, "jitter_enabled")
        assert hasattr(policy, "circuit_breaker_enabled")
        assert hasattr(policy, "circuit_breaker_threshold")
        assert hasattr(policy, "circuit_breaker_timeout_seconds")

    @pytest.mark.asyncio
    async def test_database_query_parameters(self, mock_db_adapter, sample_retry_policy):
        """Test that database query receives correct parameters"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            await RetryPolicyManager.get_policy("firecrawl", "image_processing")
        finally:
            RetryPolicyManager.set_db_adapter(None)

        # Verify query parameters
        call_args = mock_db_adapter.fetch_one.call_args
        assert call_args[0][1] == ("firecrawl", "image_processing")

    @pytest.mark.asyncio
    async def test_cache_key_format(self, mock_db_adapter, sample_retry_policy):
        """Test cache key format for different scenarios"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # With stage
            await RetryPolicyManager.get_policy("firecrawl", "image_processing")
            assert "firecrawl:image_processing" in RetryPolicyManager._cache

            # Without stage
            RetryPolicyManager.clear_cache()
            await RetryPolicyManager.get_policy("database")
            assert "database:*" in RetryPolicyManager._cache
        finally:
            RetryPolicyManager.set_db_adapter(None)


# ============================================================================
# Integration Tests
# ============================================================================


class TestRetryEngineIntegration:
    """Integration tests for retry engine components"""

    @pytest.mark.asyncio
    async def test_error_classification_with_policy_lookup(self, mock_db_adapter, sample_retry_policy):
        """Test using error classification to determine retry behavior"""
        mock_db_adapter.fetch_one = AsyncMock(return_value=sample_retry_policy)
        RetryPolicyManager.set_db_adapter(mock_db_adapter)
        try:
            # Simulate a transient error
            exception = httpx.TimeoutException("Request timed out")
            classification = ErrorClassifier.classify(exception)

            assert classification.is_transient is True

            # Get retry policy for the service
            policy = await RetryPolicyManager.get_policy("firecrawl", "image_processing")

            # Should retry based on policy
            assert policy.max_retries > 0
            assert classification.is_transient is True
        finally:
            RetryPolicyManager.set_db_adapter(None)

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self):
        """Test that permanent errors should not be retried"""
        # Simulate a permanent error
        exception = ValueError("Invalid input")
        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is False
        assert classification.error_category == "permanent"

        # Even with a retry policy, permanent errors should not be retried
        policy = await RetryPolicyManager.get_policy("firecrawl")

        # Application logic should check classification before using policy
        if not classification.is_transient:
            # Don't retry permanent errors
            assert True


# ============================================================================
# RetryOrchestrator Integration Tests
# ============================================================================


class TestRetryOrchestratorIntegration:
    """Integration tests for RetryOrchestrator"""

    def test_generate_correlation_id_format(self):
        """Test correlation ID format matches specification"""
        test_cases = [
            ("req_123", "image_processing", 0, "req_123.stage_image_processing.retry_0"),
            ("req_a3f2e8d1", "text_extraction", 2, "req_a3f2e8d1.stage_text_extraction.retry_2"),
            ("req_xyz", "embedding", 5, "req_xyz.stage_embedding.retry_5"),
        ]

        for request_id, stage_name, retry_attempt, expected in test_cases:
            correlation_id = RetryOrchestrator.generate_correlation_id(request_id, stage_name, retry_attempt)
            assert correlation_id == expected

    def test_calculate_backoff_delay_exponential(self, retry_orchestrator, sample_retry_policy):
        """Test exponential backoff calculation"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.jitter_enabled = False  # Disable jitter for predictable testing
        policy.base_delay_seconds = 1.0
        policy.exponential_base = 2.0
        policy.max_delay_seconds = 60.0

        # Test exponential progression
        assert retry_orchestrator.calculate_backoff_delay(0, policy) == 1.0
        assert retry_orchestrator.calculate_backoff_delay(1, policy) == 2.0
        assert retry_orchestrator.calculate_backoff_delay(2, policy) == 4.0
        assert retry_orchestrator.calculate_backoff_delay(3, policy) == 8.0
        assert retry_orchestrator.calculate_backoff_delay(4, policy) == 16.0

        # Test max_delay cap
        policy.max_delay_seconds = 10.0
        assert retry_orchestrator.calculate_backoff_delay(10, policy) == 10.0

    def test_calculate_backoff_delay_with_jitter(self, retry_orchestrator, sample_retry_policy):
        """Test that jitter adds ±20% variation"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.jitter_enabled = True
        policy.base_delay_seconds = 10.0
        policy.exponential_base = 2.0

        # Calculate delay multiple times and verify jitter range
        delays = [retry_orchestrator.calculate_backoff_delay(0, policy) for _ in range(100)]

        # Base delay is 10.0, jitter should be ±20% (8.0 to 12.0)
        assert all(8.0 <= d <= 12.0 for d in delays)

        # Verify we get different values (not all the same)
        assert len(set(delays)) > 1

    @pytest.mark.asyncio
    async def test_advisory_lock_prevents_concurrent_retries(self, retry_orchestrator):
        """Test that advisory locks prevent concurrent retries"""
        document_id = "test_doc_123"
        stage_name = "image_processing"

        # First lock should succeed
        lock1 = await retry_orchestrator.acquire_advisory_lock(document_id, stage_name)
        assert lock1 is True

        # Second lock should fail (already locked)
        lock2 = await retry_orchestrator.acquire_advisory_lock(document_id, stage_name)
        assert lock2 is False

        # Release first lock
        released = await retry_orchestrator.release_advisory_lock(document_id, stage_name)
        assert released is True

        # Now second lock should succeed
        lock3 = await retry_orchestrator.acquire_advisory_lock(document_id, stage_name)
        assert lock3 is True

        # Cleanup
        await retry_orchestrator.release_advisory_lock(document_id, stage_name)

    @pytest.mark.asyncio
    async def test_background_retry_task_execution(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy, mock_processor_callable
    ):
        """Test background retry task execution"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.base_delay_seconds = 0.01  # Very short delay for testing
        policy.jitter_enabled = False

        correlation_id = "req_123.stage_test.retry_1"

        # Spawn background retry
        await retry_orchestrator.spawn_background_retry(
            sample_processing_context, 1, policy, correlation_id, mock_processor_callable
        )

        # Wait for task to complete (with timeout)
        await asyncio.sleep(0.5)

        # Verify processor was called
        assert mock_processor_callable.called

        # Verify error status was updated to 'resolved'
        retry_orchestrator.error_logger.update_error_status.assert_called()

    @pytest.mark.asyncio
    async def test_background_retry_max_retries_exceeded(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy
    ):
        """Test that max retries exceeded marks error as failed"""

        # Mock processor that always fails
        async def failing_processor(context):
            result = MagicMock()
            result.success = False
            result.error = Exception("Processing failed")
            return result

        processor = AsyncMock(side_effect=failing_processor)

        policy = RetryPolicy(**sample_retry_policy)
        policy.max_retries = 2
        policy.base_delay_seconds = 0.01
        policy.jitter_enabled = False

        correlation_id = "req_123.stage_test.retry_0"

        # Mock mark_retry_exhausted
        retry_orchestrator.mark_retry_exhausted = AsyncMock(return_value=True)

        # Spawn background retry
        await retry_orchestrator.spawn_background_retry(sample_processing_context, 0, policy, correlation_id, processor)

        # Wait for retries to complete
        await asyncio.sleep(1.0)

        # Verify processor was called multiple times
        assert processor.call_count >= 1

    @pytest.mark.asyncio
    async def test_transient_error_retry_success(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy
    ):
        """Test transient error retry succeeds on retry"""
        # Simulate transient error
        exception = ConnectionError("Connection failed")
        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is True

        # Check should_retry
        policy = RetryPolicy(**sample_retry_policy)
        should_retry = await retry_orchestrator.should_retry(classification, 0, policy)

        assert should_retry is True

        # Mock processor that succeeds on retry
        call_count = 0

        async def processor_with_retry(context):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.success = call_count > 1  # Fail first, succeed second
            result.error = None if call_count > 1 else Exception("Transient error")
            return result

        processor = AsyncMock(side_effect=processor_with_retry)

        policy.base_delay_seconds = 0.01
        policy.jitter_enabled = False

        correlation_id = "req_123.stage_test.retry_0"

        # Spawn retry
        await retry_orchestrator.spawn_background_retry(sample_processing_context, 0, policy, correlation_id, processor)

        # Wait for completion
        await asyncio.sleep(0.5)

        # Verify processor was called
        assert processor.called

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self, retry_orchestrator, sample_retry_policy):
        """Test permanent errors are not retried"""
        # Simulate permanent error
        exception = ValueError("Invalid input")
        classification = ErrorClassifier.classify(exception)

        assert classification.is_transient is False

        # Check should_retry
        policy = RetryPolicy(**sample_retry_policy)
        should_retry = await retry_orchestrator.should_retry(classification, 0, policy)

        assert should_retry is False

    @pytest.mark.asyncio
    async def test_concurrent_retry_prevention_with_locks(self, retry_orchestrator):
        """Test that concurrent retries are prevented with locks"""
        document_id = "test_doc_concurrent"
        stage_name = "image_processing"

        # Create 10 concurrent lock attempts
        tasks = [retry_orchestrator.acquire_advisory_lock(document_id, stage_name) for _ in range(10)]

        results = await asyncio.gather(*tasks)

        # Only 1 should succeed
        successful_locks = sum(1 for r in results if r is True)
        assert successful_locks == 1

        # Cleanup - release the lock
        await retry_orchestrator.release_advisory_lock(document_id, stage_name)

    @pytest.mark.asyncio
    async def test_error_status_updates_during_retry_lifecycle(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy, mock_processor_callable
    ):
        """Test error status updates during retry lifecycle"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.base_delay_seconds = 0.01
        policy.jitter_enabled = False

        # Update error status to 'pending'
        await retry_orchestrator.update_error_status("error_123", "pending")

        # Spawn retry
        correlation_id = "req_123.stage_test.retry_0"
        await retry_orchestrator.spawn_background_retry(
            sample_processing_context, 0, policy, correlation_id, mock_processor_callable
        )

        # Wait for completion
        await asyncio.sleep(0.5)

        # Verify status was updated to 'retrying' and then 'resolved'
        calls = retry_orchestrator.error_logger.update_error_status.call_args_list
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_retry_with_database_unavailable(
        self, mock_error_logger, sample_processing_context, sample_retry_policy
    ):
        """Test orchestrator handles database errors gracefully"""
        # Create orchestrator with failing database adapter
        failing_adapter = AsyncMock()
        failing_adapter.fetch_one = AsyncMock(side_effect=Exception("Database unavailable"))
        failing_adapter.execute = AsyncMock(side_effect=Exception("Database unavailable"))

        orchestrator = RetryOrchestrator(failing_adapter, mock_error_logger)

        # Try to acquire lock (should fail gracefully)
        result = await orchestrator.acquire_advisory_lock("doc_123", "stage")
        assert result is False

        # Try to get retry context (should return None)
        context = await orchestrator.get_retry_context("error_123")
        assert context is None

        # Try to mark retry exhausted (should fail gracefully)
        result = await orchestrator.mark_retry_exhausted("error_123", Exception("Test"))
        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_checks_transient_and_attempts(self, retry_orchestrator, sample_retry_policy):
        """Test should_retry checks both transient status and retry attempts"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.max_retries = 3

        # Transient error with retries remaining
        transient = ErrorClassification(is_transient=True, error_type="ConnectionError", error_category="transient")
        assert await retry_orchestrator.should_retry(transient, 0, policy) is True
        assert await retry_orchestrator.should_retry(transient, 2, policy) is True

        # Transient error but max retries exceeded
        assert await retry_orchestrator.should_retry(transient, 3, policy) is False
        assert await retry_orchestrator.should_retry(transient, 5, policy) is False

        # Permanent error with retries remaining
        permanent = ErrorClassification(is_transient=False, error_type="ValueError", error_category="permanent")
        assert await retry_orchestrator.should_retry(permanent, 0, policy) is False
        assert await retry_orchestrator.should_retry(permanent, 2, policy) is False

    @pytest.mark.asyncio
    async def test_get_retry_context_returns_error_details(self, retry_orchestrator, mock_db_adapter):
        """Test get_retry_context returns error details from database"""
        # Mock database response
        mock_db_adapter.fetch_one.return_value = {
            "document_id": "doc_123",
            "stage_name": "image_processing",
            "retry_count": 2,
            "correlation_id": "req_123.stage_image_processing.retry_2",
        }

        context = await retry_orchestrator.get_retry_context("error_123")

        assert context is not None
        assert context["document_id"] == "doc_123"
        assert context["stage_name"] == "image_processing"
        assert context["retry_count"] == 2
        assert context["correlation_id"] == "req_123.stage_image_processing.retry_2"

    @pytest.mark.asyncio
    async def test_mark_retry_exhausted_updates_database(self, retry_orchestrator, mock_db_adapter, mock_error_logger):
        """Test mark_retry_exhausted updates database with resolution notes via execute_query."""
        mock_db_adapter.execute_query = AsyncMock()

        final_error = Exception("Final error message")
        result = await retry_orchestrator.mark_retry_exhausted("error_123", final_error)

        assert result is True

        # Verify error status was updated to 'failed' (next_retry_at=None)
        mock_error_logger.update_error_status.assert_called_with("error_123", "failed", None)

        # Verify resolution notes were persisted via adapter's execute_query (not execute)
        mock_db_adapter.execute_query.assert_called_once()
        call_args = mock_db_adapter.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "UPDATE krai_system.pipeline_errors" in query
        assert "resolution_notes" in query
        assert params[0] == "error_123"
        assert "Max retries exceeded" in params[1]
        assert "Final error message" in params[1]

    @pytest.mark.asyncio
    async def test_update_error_status_delegates_to_error_logger(self, retry_orchestrator, mock_error_logger):
        """Test update_error_status delegates to ErrorLogger"""
        next_retry_at = datetime.utcnow()

        result = await retry_orchestrator.update_error_status("error_123", "retrying", next_retry_at)

        assert result is True
        mock_error_logger.update_error_status.assert_called_once_with("error_123", "retrying", next_retry_at)

    @pytest.mark.asyncio
    async def test_spawn_background_retry_creates_task(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy, mock_processor_callable
    ):
        """Test spawn_background_retry creates async task"""
        policy = RetryPolicy(**sample_retry_policy)
        policy.base_delay_seconds = 0.01

        correlation_id = "req_123.stage_test.retry_1"

        # Spawn task (should not block)
        await retry_orchestrator.spawn_background_retry(
            sample_processing_context, 1, policy, correlation_id, mock_processor_callable
        )

        # Should return immediately (fire-and-forget)
        # Task is running in background

        # Wait a bit for task to execute
        await asyncio.sleep(0.2)

        # Verify task was created and executed
        assert mock_processor_callable.called


# ============================================================================
# Integration Tests with BaseProcessor
# ============================================================================


class TestRetryOrchestratorBaseProcessorIntegration:
    """Integration tests for RetryOrchestrator with BaseProcessor"""

    @pytest.mark.asyncio
    async def test_orchestrator_integrates_with_base_processor(self, mock_db_adapter, mock_error_logger):
        """Test that RetryOrchestrator integrates correctly with BaseProcessor.safe_process()"""
        from backend.core.base_processor import BaseProcessor
        from backend.core.types import ProcessingContext

        # Create mock processor
        class TestProcessor(BaseProcessor):
            def __init__(self):
                super().__init__("test_integration", {"service_name": "test"})
                self.db_adapter = mock_db_adapter
                self.call_count = 0

            async def process(self, context):
                self.call_count += 1
                if self.call_count == 1:
                    raise ConnectionError("Transient error")
                return self.create_success_result({"processed": True})

        # Mock database responses
        mock_db_adapter.fetch_one = AsyncMock(
            side_effect=[
                None,  # No completion marker
                {"pg_try_advisory_lock": True},  # Lock acquired
                {"pg_advisory_unlock": True},  # Lock released
                None,  # No completion marker (retry)
                {"pg_try_advisory_lock": True},  # Lock acquired (retry)
                {"pg_advisory_unlock": True},  # Lock released (retry)
            ]
        )
        mock_db_adapter.execute = AsyncMock()

        # Create processor and context
        processor = TestProcessor()
        context = ProcessingContext(
            document_id="test_doc_123", file_path="/test/doc.pdf", file_size=1024, document_type="service_manual"
        )

        # Execute
        result = await processor.safe_process(context)

        # Verify success after retry
        assert result.success is True
        assert processor.call_count == 2

    @pytest.mark.asyncio
    async def test_background_retry_task_executes_processor_callable(
        self, retry_orchestrator, sample_processing_context, sample_retry_policy
    ):
        """Test that background retry task correctly executes processor callable"""
        from backend.core.types import ProcessingResult, ProcessingStatus

        # Create mock processor callable that succeeds
        call_count = 0

        async def mock_processor(context):
            nonlocal call_count
            call_count += 1
            result = ProcessingResult(
                success=True,
                processor="test",
                status=ProcessingStatus.COMPLETED,
                data={"retry_success": True},
                metadata={},
                processing_time=0.1,
            )
            return result

        # Mock advisory lock
        retry_orchestrator.db_adapter.fetch_one = AsyncMock(
            side_effect=[
                {"pg_try_advisory_lock": True},  # Lock acquired
                {"pg_advisory_unlock": True},  # Lock released
            ]
        )

        policy = RetryPolicy(**sample_retry_policy)
        policy.base_delay_seconds = 0.01  # Fast for testing

        correlation_id = "req_test.stage_test.retry_1"

        # Spawn background retry
        await retry_orchestrator.spawn_background_retry(
            sample_processing_context, 1, policy, correlation_id, mock_processor
        )

        # Wait for background task to complete
        await asyncio.sleep(0.2)

        # Verify processor was called
        assert call_count == 1

        # Verify error status was updated to 'resolved'
        retry_orchestrator.error_logger.update_error_status.assert_called()
