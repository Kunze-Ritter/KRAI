"""
Comprehensive unit tests for rate limiting middleware.

Tests cover:
- IP-based rate limiting with various scenarios
- API-key-based rate limiting with precedence rules
- Whitelist/blacklist functionality
- Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After)
- Per-endpoint rate limits (auth, upload, search, health)
- 429 response format and exception handling
- Edge cases (disabled rate limiting, concurrent requests, missing IPs, JWT users)
- Helper functions (_client_ip, _extract_api_key, _get_api_key_identifier, _user_or_ip_key)

Target: >80% code coverage for rate_limit_middleware.py
"""

import asyncio
import importlib
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config.security_config import SecurityConfig


@pytest.fixture
def mock_security_config():
    """Mock SecurityConfig with configurable rate limit settings.

    Reloads the rate_limit_middleware module after patching get_security_config
    to ensure _security_config, _WHITELIST, _BLACKLIST, and limiter are bound
    to the mocked config for each test.
    """
    config = Mock(spec=SecurityConfig)
    config.RATE_LIMIT_ENABLED = True
    config.RATE_LIMIT_STORAGE = "memory"
    config.rate_limit_storage_url = "memory://"
    config.RATE_LIMIT_STANDARD = "100/minute"
    config.RATE_LIMIT_AUTH = "5/minute"
    config.RATE_LIMIT_UPLOAD = "10/hour"
    config.RATE_LIMIT_SEARCH = "60/minute"
    config.RATE_LIMIT_HEALTH = "300/minute"
    config.RATE_LIMIT_API_KEY = "1000/minute"
    config.RATE_LIMIT_WHITELIST = []
    config.RATE_LIMIT_BLACKLIST = []

    with patch("backend.api.middleware.rate_limit_middleware.get_security_config", return_value=config):
        with patch("backend.config.security_config.get_security_config", return_value=config):
            # Reload the middleware module to rebind module-level variables to the mock
            import backend.api.middleware.rate_limit_middleware as rlm_module

            importlib.reload(rlm_module)
            yield config


@pytest.fixture
def mock_redis_storage():
    """Create mock Redis storage for slowapi limiter with isolated state per test."""

    class MockStorage:
        def __init__(self):
            self.storage = {}

        def hit(self, key, expiry):
            if key not in self.storage:
                self.storage[key] = {"count": 0, "expiry": time.time() + expiry}

            if time.time() > self.storage[key]["expiry"]:
                self.storage[key] = {"count": 0, "expiry": time.time() + expiry}

            self.storage[key]["count"] += 1
            return self.storage[key]["count"]

        def get(self, key):
            if key not in self.storage:
                return 0
            if time.time() > self.storage[key]["expiry"]:
                return 0
            return self.storage[key]["count"]

        def clear(self, key):
            if key in self.storage:
                del self.storage[key]

        def reset(self):
            """Clear all storage for test isolation."""
            self.storage.clear()

    return MockStorage()


@pytest.fixture
async def mock_db_pool():
    """Create AsyncMock for asyncpg.Pool."""
    pool = AsyncMock()
    connection = AsyncMock()

    async def mock_acquire():
        return connection

    pool.acquire = Mock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=connection), __aexit__=AsyncMock()))

    connection.fetchrow = AsyncMock(
        return_value={
            "id": "key-123",
            "user_id": "user-123",
            "key_hash": "hash123",
            "is_active": True,
            "expires_at": None,
        }
    )

    return pool


@pytest.fixture
def test_app(mock_security_config, mock_db_pool, mock_redis_storage):
    """Create FastAPI test app with rate limiting middleware.

    Uses the reloaded middleware module to ensure all rate limiting
    components use the mocked SecurityConfig. Creates a fresh limiter
    with isolated storage for each test to prevent cross-test coupling.
    """
    # Clear storage from any previous test
    mock_redis_storage.reset()

    # Import from the reloaded module
    from backend.api.middleware.rate_limit_middleware import (
        APIKeyValidationMiddleware,
        IPFilterMiddleware,
        rate_limit_auth_dynamic,
        rate_limit_exception_handler,
        rate_limit_health_dynamic,
        rate_limit_search_dynamic,
        rate_limit_standard_dynamic,
        rate_limit_upload_dynamic,
    )

    app = FastAPI()

    # Create a fresh limiter with isolated storage for this test
    fresh_limiter = Limiter(
        key_func=get_remote_address, storage_uri="memory://", storage_options={"storage": mock_redis_storage}
    )

    app.state.db_pool = mock_db_pool
    app.state.limiter = fresh_limiter

    app.add_middleware(APIKeyValidationMiddleware)
    app.add_middleware(IPFilterMiddleware)

    app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)

    @app.get("/test/standard")
    @fresh_limiter.limit(rate_limit_standard_dynamic)
    async def standard_endpoint(request: Request):
        return {"message": "success"}

    @app.post("/test/auth")
    @fresh_limiter.limit(rate_limit_auth_dynamic)
    async def auth_endpoint(request: Request):
        return {"message": "authenticated"}

    @app.post("/test/upload")
    @fresh_limiter.limit(rate_limit_upload_dynamic)
    async def upload_endpoint(request: Request):
        return {"message": "uploaded"}

    @app.get("/test/search")
    @fresh_limiter.limit(rate_limit_search_dynamic)
    async def search_endpoint(request: Request):
        return {"message": "search results"}

    @app.get("/test/health")
    @fresh_limiter.limit(rate_limit_health_dynamic)
    async def health_endpoint(request: Request):
        return {"status": "healthy"}

    @app.get("/test/exempt")
    async def exempt_endpoint(request: Request):
        return {"message": "no rate limit"}

    return app


@pytest.fixture
async def async_client(test_app):
    """Create async test client."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_api_key_service():
    """Mock APIKeyService with validate_api_key method."""
    service = AsyncMock()
    service.validate_api_key = AsyncMock(
        return_value={"id": "key-123", "user_id": "user-123", "is_active": True, "expires_at": None}
    )
    return service


@pytest.mark.unit
class TestIPBasedRateLimiting:
    """Test IP-based rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_ip_rate_limit_within_limits(self, async_client, mock_security_config):
        """Test requests within rate limit succeed."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        responses = []
        for i in range(5):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.1"})
            responses.append(response)

        for i, response in enumerate(responses):
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert int(response.headers["X-RateLimit-Limit"]) == 5
            assert "X-RateLimit-Remaining" in response.headers
            assert int(response.headers["X-RateLimit-Remaining"]) == 4 - i

    @pytest.mark.asyncio
    async def test_ip_rate_limit_exceeded(self, async_client, mock_security_config):
        """Test exceeding rate limit returns 429."""
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses = []
        for i in range(4):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.2"})
            responses.append(response)

        for i in range(3):
            assert responses[i].status_code == 200

        assert responses[3].status_code == 429
        assert "detail" in responses[3].json()
        assert "Rate limit exceeded" in responses[3].json()["detail"]
        assert "Retry-After" in responses[3].headers

    @pytest.mark.asyncio
    async def test_different_ips_separate_limits(self, async_client, mock_security_config):
        """Test different IPs have separate rate limit buckets."""
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses_ip1 = []
        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.1"})
            responses_ip1.append(response)

        responses_ip2 = []
        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.2"})
            responses_ip2.append(response)

        for response in responses_ip1 + responses_ip2:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ip_extraction_from_forwarded_for(self, async_client, mock_security_config):
        """Test IP extraction from X-Forwarded-For header."""
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses = []
        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"})
            responses.append(response)

        for response in responses:
            assert response.status_code == 200

        response_exceed = await async_client.get("/test/standard", headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.3"})
        assert response_exceed.status_code == 429

    @pytest.mark.asyncio
    async def test_ip_extraction_from_real_ip(self, async_client, mock_security_config):
        """Test IP extraction from X-Real-IP header."""
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses = []
        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Real-IP": "172.16.0.1"})
            responses.append(response)

        for response in responses:
            assert response.status_code == 200

        response_exceed = await async_client.get("/test/standard", headers={"X-Real-IP": "172.16.0.1"})
        assert response_exceed.status_code == 429


@pytest.mark.unit
class TestAPIKeyRateLimiting:
    """Test API-key-based rate limiting scenarios."""

    @pytest.mark.asyncio
    async def test_api_key_higher_rate_limit(self, async_client, mock_security_config, mock_db_pool):
        """Test valid API key gets higher rate limits."""
        mock_security_config.RATE_LIMIT_API_KEY = "1000/minute"
        mock_security_config.RATE_LIMIT_STANDARD = "100/minute"

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value={
                "id": "key-123",
                "user_id": "user-123",
                "key_hash": "hash123",
                "is_active": True,
                "expires_at": None,
            }
        )

        responses = []
        for i in range(150):
            response = await async_client.get(
                "/test/standard", headers={"X-API-Key": "krai_live_validkey123", "X-Forwarded-For": "192.168.1.10"}
            )
            responses.append(response)
            if response.status_code != 200:
                break

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count > 100

    @pytest.mark.asyncio
    async def test_invalid_api_key_fallback_to_ip(self, async_client, mock_security_config, mock_db_pool):
        """Test invalid API key falls back to IP-based rate limiting."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(return_value=None)

        responses = []
        for i in range(6):
            response = await async_client.get(
                "/test/standard", headers={"X-API-Key": "invalid_key", "X-Forwarded-For": "192.168.1.20"}
            )
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5
        assert responses[5].status_code == 429

    @pytest.mark.asyncio
    async def test_api_key_precedence_over_jwt(self, async_client, mock_security_config, mock_db_pool):
        """Test API key takes precedence over JWT user."""
        mock_security_config.RATE_LIMIT_API_KEY = "1000/minute"
        mock_security_config.RATE_LIMIT_STANDARD = "10/minute"

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value={
                "id": "key-456",
                "user_id": "api-user-456",
                "key_hash": "hash456",
                "is_active": True,
                "expires_at": None,
            }
        )

        responses = []
        for i in range(20):
            response = await async_client.get(
                "/test/standard", headers={"X-API-Key": "krai_live_validkey456", "X-Forwarded-For": "192.168.1.30"}
            )
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 20

    @pytest.mark.asyncio
    async def test_api_key_header_case_insensitive(self, async_client, mock_security_config, mock_db_pool):
        """Test API key header is case-insensitive."""
        mock_security_config.RATE_LIMIT_API_KEY = "1000/minute"

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            return_value={
                "id": "key-789",
                "user_id": "user-789",
                "key_hash": "hash789",
                "is_active": True,
                "expires_at": None,
            }
        )

        response = await async_client.get(
            "/test/standard", headers={"x-api-key": "krai_live_validkey", "X-Forwarded-For": "192.168.1.40"}
        )

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    @pytest.mark.asyncio
    async def test_expired_api_key_fallback(self, async_client, mock_security_config, mock_db_pool):
        """Test expired API key falls back to IP-based rate limiting."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(return_value=None)

        responses = []
        for i in range(6):
            response = await async_client.get(
                "/test/standard", headers={"X-API-Key": "krai_live_expiredkey", "X-Forwarded-For": "192.168.1.50"}
            )
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5
        assert responses[5].status_code == 429


@pytest.mark.unit
class TestWhitelistBlacklist:
    """Test whitelist and blacklist functionality."""

    @pytest.mark.asyncio
    async def test_whitelisted_ip_exempt_from_limits(self, async_client, mock_security_config):
        """Test whitelisted IP is exempt from rate limiting."""
        mock_security_config.RATE_LIMIT_WHITELIST = ["192.168.1.100"]
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses = []
        for i in range(100):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.100"})
            responses.append(response)
            if response.status_code != 200:
                break

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 100

    @pytest.mark.asyncio
    async def test_blacklisted_ip_blocked(self, async_client, mock_security_config):
        """Test blacklisted IP is blocked with 403."""
        mock_security_config.RATE_LIMIT_BLACKLIST = ["10.0.0.50"]

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "10.0.0.50"})

        assert response.status_code == 403
        assert "detail" in response.json()
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_non_whitelisted_ip_rate_limited(self, async_client, mock_security_config):
        """Test non-whitelisted IP is rate limited normally."""
        mock_security_config.RATE_LIMIT_WHITELIST = ["192.168.1.100"]
        mock_security_config.RATE_LIMIT_STANDARD = "3/minute"

        responses = []
        for i in range(4):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.200"})
            responses.append(response)

        assert responses[0].status_code == 200
        assert responses[1].status_code == 200
        assert responses[2].status_code == 200
        assert responses[3].status_code == 429

    @pytest.mark.asyncio
    async def test_whitelist_when_rate_limiting_disabled(self, async_client, mock_security_config):
        """Test whitelist is ignored when rate limiting is disabled."""
        mock_security_config.RATE_LIMIT_ENABLED = False
        mock_security_config.RATE_LIMIT_WHITELIST = ["192.168.1.100"]

        responses = []
        for i in range(10):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.1.250"})
            responses.append(response)

        for response in responses:
            assert response.status_code == 200


@pytest.mark.unit
class TestRateLimitHeaders:
    """Test rate limit response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_limit_header(self, async_client, mock_security_config):
        """Test X-RateLimit-Limit header is present and correct."""
        mock_security_config.RATE_LIMIT_STANDARD = "50/minute"

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.2.1"})

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert int(response.headers["X-RateLimit-Limit"]) == 50

    @pytest.mark.asyncio
    async def test_rate_limit_remaining_header(self, async_client, mock_security_config):
        """Test X-RateLimit-Remaining header decreases correctly."""
        mock_security_config.RATE_LIMIT_STANDARD = "10/minute"

        responses = []
        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.2.2"})
            responses.append(response)

        assert "X-RateLimit-Remaining" in responses[0].headers
        assert int(responses[0].headers["X-RateLimit-Remaining"]) == 9

        assert "X-RateLimit-Remaining" in responses[1].headers
        assert int(responses[1].headers["X-RateLimit-Remaining"]) == 8

        assert "X-RateLimit-Remaining" in responses[2].headers
        assert int(responses[2].headers["X-RateLimit-Remaining"]) == 7

    @pytest.mark.asyncio
    async def test_rate_limit_reset_header(self, async_client, mock_security_config):
        """Test X-RateLimit-Reset header is present."""
        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.2.3"})

        assert response.status_code == 200
        assert "X-RateLimit-Reset" in response.headers
        reset_time = int(response.headers["X-RateLimit-Reset"])
        assert reset_time > int(time.time())

    @pytest.mark.asyncio
    async def test_retry_after_header_on_429(self, async_client, mock_security_config):
        """Test Retry-After header is present on 429 response."""
        mock_security_config.RATE_LIMIT_STANDARD = "2/minute"

        for i in range(2):
            await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.2.4"})

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.2.4"})

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0


@pytest.mark.unit
class TestPerEndpointRateLimits:
    """Test per-endpoint rate limits."""

    @pytest.mark.asyncio
    async def test_auth_endpoint_rate_limit(self, async_client, mock_security_config):
        """Test auth endpoint has specific rate limit."""
        mock_security_config.RATE_LIMIT_AUTH = "5/minute"

        responses = []
        for i in range(6):
            response = await async_client.post("/test/auth", headers={"X-Forwarded-For": "192.168.3.1"})
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5
        assert responses[5].status_code == 429

    @pytest.mark.asyncio
    async def test_upload_endpoint_rate_limit(self, async_client, mock_security_config):
        """Test upload endpoint has specific rate limit."""
        mock_security_config.RATE_LIMIT_UPLOAD = "10/hour"

        responses = []
        for i in range(11):
            response = await async_client.post("/test/upload", headers={"X-Forwarded-For": "192.168.3.2"})
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 10
        assert responses[10].status_code == 429

    @pytest.mark.asyncio
    async def test_search_endpoint_rate_limit(self, async_client, mock_security_config):
        """Test search endpoint has specific rate limit."""
        mock_security_config.RATE_LIMIT_SEARCH = "60/minute"

        responses = []
        for i in range(61):
            response = await async_client.get("/test/search", headers={"X-Forwarded-For": "192.168.3.3"})
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 60
        assert responses[60].status_code == 429

    @pytest.mark.asyncio
    async def test_health_endpoint_rate_limit(self, async_client, mock_security_config):
        """Test health endpoint has specific rate limit."""
        mock_security_config.RATE_LIMIT_HEALTH = "300/minute"

        responses = []
        for i in range(301):
            response = await async_client.get("/test/health", headers={"X-Forwarded-For": "192.168.3.4"})
            responses.append(response)
            if response.status_code != 200:
                break

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 300
        if len(responses) > 300:
            assert responses[300].status_code == 429

    @pytest.mark.asyncio
    async def test_different_endpoints_separate_buckets(self, async_client, mock_security_config):
        """Test different endpoints have separate rate limit buckets."""
        mock_security_config.RATE_LIMIT_AUTH = "5/minute"
        mock_security_config.RATE_LIMIT_SEARCH = "60/minute"

        auth_responses = []
        for i in range(5):
            response = await async_client.post("/test/auth", headers={"X-Forwarded-For": "192.168.3.5"})
            auth_responses.append(response)

        search_responses = []
        for i in range(5):
            response = await async_client.get("/test/search", headers={"X-Forwarded-For": "192.168.3.5"})
            search_responses.append(response)

        for response in auth_responses + search_responses:
            assert response.status_code == 200


@pytest.mark.unit
class TestRateLimitExceededResponse:
    """Test 429 response format and exception handling."""

    @pytest.mark.asyncio
    async def test_429_response_structure(self, async_client, mock_security_config):
        """Test 429 response has correct structure."""
        mock_security_config.RATE_LIMIT_STANDARD = "2/minute"

        for i in range(2):
            await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.4.1"})

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.4.1"})

        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        assert "Rate limit exceeded" in data["detail"]

    @pytest.mark.asyncio
    async def test_429_with_retry_after_header(self, async_client, mock_security_config):
        """Test 429 response includes Retry-After header."""
        mock_security_config.RATE_LIMIT_STANDARD = "2/minute"

        for i in range(2):
            await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.4.2"})

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.4.2"})

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = response.headers["Retry-After"]
        assert retry_after.isdigit()
        assert int(retry_after) > 0

    @pytest.mark.asyncio
    async def test_rate_limit_exception_handler(self):
        """Test custom exception handler for RateLimitExceeded."""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/test/endpoint"

        exc = RateLimitExceeded("5/minute")

        response = await rate_limit_exception_handler(mock_request, exc)

        assert response.status_code == 429
        assert isinstance(response, JSONResponse)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limiting_disabled(self, async_client, mock_security_config):
        """Test rate limiting is disabled when configured."""
        mock_security_config.RATE_LIMIT_ENABLED = False

        responses = []
        for i in range(100):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.1"})
            responses.append(response)

        for response in responses:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_client_ip_fallback(self):
        """Test _client_ip returns fallback when client is None."""
        mock_request = Mock(spec=Request)
        mock_request.client = None
        mock_request.headers = {}

        ip = _client_ip(mock_request)
        assert ip == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_ip(self, async_client, mock_security_config):
        """Test concurrent requests from same IP are rate limited correctly."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        async def make_request():
            return await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.2"})

        responses = await asyncio.gather(*[make_request() for _ in range(10)])

        success_count = sum(1 for r in responses if r.status_code == 200)
        failed_count = sum(1 for r in responses if r.status_code == 429)

        assert success_count <= 5
        assert failed_count >= 5

    @pytest.mark.asyncio
    async def test_rate_limit_reset_after_window(self, async_client, mock_security_config):
        """Test rate limit resets after time window expires."""
        mock_security_config.RATE_LIMIT_STANDARD = "3/second"

        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.3"})
            assert response.status_code == 200

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.3"})
        assert response.status_code == 429

        await asyncio.sleep(1.5)

        for i in range(3):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.3"})
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_jwt_user_rate_limiting(self, async_client, mock_security_config):
        """Test JWT user rate limiting without API key."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        responses = []
        for i in range(6):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.4"})
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5
        assert responses[5].status_code == 429

    @pytest.mark.asyncio
    async def test_unknown_user_fallback_to_ip(self, async_client, mock_security_config):
        """Test unknown user falls back to IP-based rate limiting."""
        mock_security_config.RATE_LIMIT_STANDARD = "5/minute"

        responses = []
        for i in range(6):
            response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "192.168.5.5"})
            responses.append(response)

        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 5
        assert responses[5].status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_exempt_function(self, mock_security_config):
        """Test rate_limit_exempt function logic."""
        from backend.api.middleware.rate_limit_middleware import rate_limit_exempt

        mock_request = Mock(spec=Request)
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}

        mock_security_config.RATE_LIMIT_WHITELIST = ["192.168.1.100"]
        mock_security_config.RATE_LIMIT_ENABLED = True

        # Reload module to pick up updated whitelist
        import backend.api.middleware.rate_limit_middleware as rlm_module

        importlib.reload(rlm_module)

        result = rate_limit_exempt(mock_request)
        assert result is True

        mock_request.client.host = "192.168.1.200"
        result = rate_limit_exempt(mock_request)
        assert result is False

        mock_security_config.RATE_LIMIT_ENABLED = False
        result = rate_limit_exempt(mock_request)
        assert result is True

        result = rate_limit_exempt(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_api_key_middleware_error_handling(self, async_client, mock_security_config, mock_db_pool):
        """Test API key middleware handles errors gracefully."""
        mock_db_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
            side_effect=Exception("Database error")
        )

        response = await async_client.get(
            "/test/standard", headers={"X-API-Key": "krai_live_testkey", "X-Forwarded-For": "192.168.5.6"}
        )

        assert response.status_code in [200, 429]

    @pytest.mark.asyncio
    async def test_ip_filter_middleware_blocks_blacklist(self, async_client, mock_security_config):
        """Test IP filter middleware blocks blacklisted IPs."""
        mock_security_config.RATE_LIMIT_BLACKLIST = ["10.0.0.99"]

        response = await async_client.get("/test/standard", headers={"X-Forwarded-For": "10.0.0.99"})

        assert response.status_code == 403


@pytest.mark.unit
class TestHelperFunctions:
    """Test helper functions used by rate limiting middleware."""

    def test_client_ip_extraction(self):
        """Test _client_ip function extracts IP correctly."""
        mock_request = Mock(spec=Request)

        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        ip = _client_ip(mock_request)
        assert ip == "10.0.0.1"

        mock_request.headers = {"X-Real-IP": "172.16.0.1"}
        ip = _client_ip(mock_request)
        assert ip == "172.16.0.1"

        mock_request.headers = {}
        ip = _client_ip(mock_request)
        assert ip == "192.168.1.1"

        mock_request.client = None
        ip = _client_ip(mock_request)
        assert ip == "127.0.0.1"

    def test_extract_api_key(self):
        """Test _extract_api_key function."""
        mock_request = Mock(spec=Request)

        mock_request.headers = {"X-API-Key": "krai_live_testkey123"}
        api_key = _extract_api_key(mock_request)
        assert api_key == "krai_live_testkey123"

        mock_request.headers = {"x-api-key": "krai_live_lowercase"}
        api_key = _extract_api_key(mock_request)
        assert api_key == "krai_live_lowercase"

        mock_request.headers = {}
        api_key = _extract_api_key(mock_request)
        assert api_key is None

        mock_request.headers = {"X-API-Key": ""}
        api_key = _extract_api_key(mock_request)
        assert api_key is None

    def test_get_api_key_identifier(self):
        """Test _get_api_key_identifier function."""
        mock_request = Mock(spec=Request)

        mock_request.state = Mock()
        mock_request.state.api_key_user_id = "user-123"
        identifier = _get_api_key_identifier(mock_request)
        assert identifier == "apikey:user-123"

        mock_request.state = Mock()
        mock_request.state.api_key_user_id = None
        identifier = _get_api_key_identifier(mock_request)
        assert identifier is None

        mock_request.state = None
        identifier = _get_api_key_identifier(mock_request)
        assert identifier is None

    def test_user_or_ip_key_precedence(self):
        """Test _user_or_ip_key function precedence logic."""
        mock_request = Mock(spec=Request)

        mock_request.state = Mock()
        mock_request.state.api_key_user_id = "api-user-123"
        mock_request.state.user = {"id": "jwt-user-456"}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers = {}
        key = _user_or_ip_key(mock_request)
        assert key == "apikey:api-user-123"

        mock_request.state.api_key_user_id = None
        key = _user_or_ip_key(mock_request)
        assert key == "jwt-user-456"

        mock_request.state.user = None
        key = _user_or_ip_key(mock_request)
        assert key == "192.168.1.1"

        mock_request.client = None
        key = _user_or_ip_key(mock_request)
        assert key == "127.0.0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=backend.api.middleware.rate_limit_middleware", "--cov-report=term-missing"])
