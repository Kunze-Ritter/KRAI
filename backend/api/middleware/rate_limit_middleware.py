"""Rate limiting middleware utilities using slowapi.

Supports three-tier rate limiting with precedence:
1. API Key (highest priority): X-API-Key header → RATE_LIMIT_API_KEY (1000/min)
2. JWT User: Authenticated user → Endpoint-specific limits
3. IP Address (fallback): Client IP → IP-based limits (100/min)

API keys are validated via APIKeyService and take precedence over IP-based limits.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from config.security_config import get_security_config
from services.api_key_service import APIKeyService

logger = logging.getLogger("krai.rate_limit")
_security_config = get_security_config()


def _client_ip(request: Request) -> str:
    """Resolve client IP using forwarded headers fallback to remote address."""
    try:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Safety check for request.client
        if not request.client or not request.client.host:
            return "127.0.0.1"

        return get_remote_address(request)
    except Exception:
        return "127.0.0.1"


def _extract_api_key(request: Request) -> str | None:
    """Extract API key from X-API-Key header (case-insensitive).

    Returns:
        API key string if found, None otherwise
    """
    try:
        # Check standard X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key.strip()

        # Fallback to lowercase variant
        api_key = request.headers.get("x-api-key")
        if api_key:
            return api_key.strip()

        return None
    except Exception as e:
        logger.debug("Failed to extract API key: %s", e)
        return None


def _get_api_key_identifier(request: Request) -> str | None:
    """Check if request has a valid API key and return rate limit identifier.

    This function checks request.state.api_key_user_id which should be set
    by the APIKeyValidationMiddleware that runs before rate limiting.

    Returns:
        Rate limit key like 'apikey:{user_id}' if valid API key, None otherwise
    """
    try:
        # Check if API key was already validated by middleware
        api_key_user_id = getattr(request.state, "api_key_user_id", None)
        if api_key_user_id:
            return f"apikey:{api_key_user_id}"
        return None
    except Exception as e:
        logger.debug("Failed to get API key identifier: %s", e)
        return None


def _user_or_ip_key(request: Request) -> str:
    """Rate limit key with precedence: API key > JWT user > IP address.

    Precedence order:
    1. API Key: If X-API-Key header is valid → 'apikey:{user_id}'
    2. JWT User: If JWT token is valid → '{user_id}'
    3. IP Address: Fallback → client IP address
    """
    try:
        # Priority 1: Check for validated API key
        api_key_id = _get_api_key_identifier(request)
        if api_key_id:
            return api_key_id

        # Priority 2: Check for JWT authenticated user
        user = getattr(request.state, "user", None)
        if isinstance(user, dict):
            user_id = user.get("id")
            if user_id:
                return str(user_id)

        # Priority 3: Fall back to IP address
        return _client_ip(request)
    except Exception:
        return "unknown"


_STORAGE_URI = _security_config.rate_limit_storage_url or "memory://"
limiter = Limiter(
    key_func=_user_or_ip_key,
    storage_uri=_STORAGE_URI,
    headers_enabled=True,
)
limiter.enabled = _security_config.RATE_LIMIT_ENABLED

_WHITELIST = {ip.strip() for ip in _security_config.RATE_LIMIT_WHITELIST if ip.strip()}
_BLACKLIST = {ip.strip() for ip in _security_config.RATE_LIMIT_BLACKLIST if ip.strip()}


def rate_limit_exempt(*args, **kwargs) -> bool:
    """Skip rate limiting for whitelisted IPs or when disabled.

    SlowAPI may invoke request filters without passing a Request object, which
    previously caused a TypeError. We defensively accept arbitrary args/kwargs
    and only apply IP-based whitelisting when a Request is available.
    """

    # Global switch: if rate limiting is disabled, always exempt
    if not _security_config.RATE_LIMIT_ENABLED:
        return True

    # Try to extract Request from positional or keyword arguments
    request: Request | None = None
    if args and isinstance(args[0], Request):
        request = args[0]
    elif isinstance(kwargs.get("request"), Request):
        request = kwargs["request"]

    # Without a concrete Request, we cannot apply whitelist logic safely
    if request is None:
        return False

    return _client_ip(request) in _WHITELIST


# Register the exempt function with the limiter
limiter._request_filters.append(rate_limit_exempt)


class APIKeyValidationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API keys and stores user_id in request.state.

    This middleware runs before rate limiting to validate API keys.
    If a valid API key is found, it stores the user_id in request.state.api_key_user_id
    which is then used by the rate limiting key function.

    Invalid API keys are silently ignored (no error response) to avoid information disclosure.
    The request will fall back to IP-based rate limiting.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            # Extract API key from headers
            api_key = _extract_api_key(request)

            if api_key:
                # Get database pool from app state
                db_pool = getattr(request.app.state, "db_pool", None)

                if db_pool:
                    try:
                        # Validate API key using APIKeyService
                        api_key_service = APIKeyService(db_pool)
                        key_record = await api_key_service.validate_api_key(api_key)

                        if key_record:
                            # Store user_id in request.state for rate limiting
                            request.state.api_key_user_id = key_record.get("user_id")
                            # Store full API key info for later use by endpoints
                            request.state.api_key = key_record
                            logger.debug("Valid API key for user %s on %s", key_record.get("user_id"), request.url.path)
                        else:
                            # Invalid API key - log but don't block request
                            logger.warning(
                                "Invalid API key attempt from %s on %s", _client_ip(request), request.url.path
                            )
                    except Exception as e:
                        # API key validation failed - log and fall back to IP-based rate limiting
                        logger.error("API key validation error: %s", e, exc_info=True)
                else:
                    logger.warning("Database pool not available for API key validation")
        except Exception as e:
            # Catch-all to prevent middleware from breaking the request
            logger.error("APIKeyValidationMiddleware error: %s", e, exc_info=True)

        return await call_next(request)


class IPFilterMiddleware(BaseHTTPMiddleware):
    """Middleware that blocks blacklisted IPs before hitting routes."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        ip = _client_ip(request)
        if ip in _BLACKLIST:
            logger.warning("Rejected blacklisted IP %s for path %s", ip, request.url.path)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return await call_next(request)


def _rate_limit_value(attr: str) -> str:
    return getattr(_security_config, attr)


def rate_limit_auth() -> str:
    return _rate_limit_value("RATE_LIMIT_AUTH")


def rate_limit_upload() -> str:
    return _rate_limit_value("RATE_LIMIT_UPLOAD")


def rate_limit_search() -> str:
    return _rate_limit_value("RATE_LIMIT_SEARCH")


def rate_limit_standard() -> str:
    return _rate_limit_value("RATE_LIMIT_STANDARD")


def rate_limit_health() -> str:
    return _rate_limit_value("RATE_LIMIT_HEALTH")


# Dynamic rate limit functions that check for API key presence
def rate_limit_auth_dynamic(request: Request | None = None) -> str:
    return dynamic_rate_limit(rate_limit_auth)(request)


def rate_limit_upload_dynamic(request: Request | None = None) -> str:
    return dynamic_rate_limit(rate_limit_upload)(request)


def rate_limit_search_dynamic(request: Request | None = None) -> str:
    return dynamic_rate_limit(rate_limit_search)(request)


def rate_limit_standard_dynamic(request: Request | None = None) -> str:
    return dynamic_rate_limit(rate_limit_standard)(request)


def rate_limit_health_dynamic(request: Request | None = None) -> str:
    return dynamic_rate_limit(rate_limit_health)(request)


def rate_limit_api_key() -> str:
    return _rate_limit_value("RATE_LIMIT_API_KEY")


def dynamic_rate_limit(endpoint_limit_func: Callable[[], str]) -> Callable[[Request | None], str]:
    """Create a dynamic rate limit function that uses API key limits when available.

    Args:
        endpoint_limit_func: Function that returns the standard endpoint limit

    Returns:
        Callable that takes a Request and returns the appropriate rate limit string
    """

    def _get_limit(request: Request | None = None) -> str:
        # Check if request has a validated API key
        api_key_user_id = getattr(getattr(request, "state", None), "api_key_user_id", None)
        if api_key_user_id:
            # Use higher API key rate limit
            return rate_limit_api_key()
        # Fall back to standard endpoint limit
        return endpoint_limit_func()

    return _get_limit


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    ip = _client_ip(request)
    limit_desc = getattr(exc, "detail", "Too Many Requests")
    retry_after = getattr(exc, "retry_after", None)
    logger.warning("Rate limit exceeded for IP %s on %s: %s", ip, request.url.path, limit_desc)
    headers = {"Retry-After": str(retry_after)} if retry_after else {}
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Rate limit exceeded",
            "limit": limit_desc,
            "resource": str(request.url.path),
        },
        headers=headers,
    )
