"""
Authentication Middleware

This module provides middleware for JWT authentication and authorization.
It handles token validation, permission checks, and user context injection.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.dependencies.auth import get_auth_service
from config.auth_config import (
    ACCESS_TOKEN,
    CLAIM_EMAIL,
    CLAIM_EXP,
    CLAIM_JTI,
    CLAIM_ROLE,
    CLAIM_TOKEN_TYPE,
    CLAIM_USER_ID,
    REFRESH_TOKEN,
    get_jwt_config,
    get_jwt_validator,
)
from models.user import UserRole, UserStatus
from services.auth_service import AuthService

# Create security scheme for JWT tokens
security = HTTPBearer()


class AuthMiddleware:
    """
    Authentication middleware for FastAPI applications.
    Handles JWT validation, permission checks, and user context injection.
    """

    def __init__(self, auth_service: AuthService):
        """Initialize the middleware with an AuthService instance."""
        self.auth_service = auth_service
        self.jwt_config = get_jwt_config()
        self.jwt_validator = get_jwt_validator()

    async def __call__(
        self, request: Request, required_permissions: list[str] = None, allow_expired: bool = False
    ) -> dict[str, Any]:
        """
        Main middleware method for request authentication and authorization.

        Args:
            request: The incoming HTTP request
            required_permissions: List of permissions required to access the endpoint
            allow_expired: Whether to allow expired tokens (for refresh token flows)

        Returns:
            Dict containing user claims if authentication is successful

        Raises:
            HTTPException: If authentication or authorization fails
        """
        # Get token from Authorization header
        credentials: HTTPAuthorizationCredentials = await self._get_credentials(request)
        token = credentials.credentials

        # Validate token and get claims
        claims = await self._validate_token(token, allow_expired)

        # Check if token is blacklisted
        if await self.auth_service.is_token_blacklisted(claims[CLAIM_JTI]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is active
        user = await self.auth_service._get_user_by_id(claims[CLAIM_USER_ID])
        if not user or not user.is_active or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check required permissions
        if required_permissions:
            for permission in required_permissions:
                if not await self.auth_service.has_permission(claims[CLAIM_USER_ID], permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required: {', '.join(required_permissions)}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

        # Add user info to request state
        request.state.user = {
            "id": claims[CLAIM_USER_ID],
            "email": claims[CLAIM_EMAIL],
            "role": claims[CLAIM_ROLE],
            "permissions": await self.auth_service.get_user_permissions(claims[CLAIM_USER_ID]),
        }

        return claims

    async def _get_credentials(self, request: Request) -> HTTPAuthorizationCredentials:
        """Extract and validate credentials from the Authorization header."""
        try:
            return await security(request)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def _validate_token(self, token: str, allow_expired: bool = False) -> dict[str, Any]:
        """Validate JWT token and return its claims."""
        try:
            # Decode and validate token
            claims = self.jwt_validator.decode(
                token,
                self.jwt_config.public_key,
                algorithms=[self.jwt_config.algorithm],
                options={"verify_exp": not allow_expired},
            )

            # Check token type
            if claims.get(CLAIM_TOKEN_TYPE) not in [ACCESS_TOKEN, REFRESH_TOKEN]:
                raise ValueError("Invalid token type")

            # Check if token is expired (if not allowing expired tokens)
            if not allow_expired and claims.get(CLAIM_EXP) < datetime.now(UTC).timestamp():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return claims

        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )


# Dependency for protected endpoints
def get_current_user(required_permissions: list[str] = None, allow_expired: bool = False):
    """
    Dependency for endpoints that require authentication.

    Args:
        required_permissions: List of permissions required to access the endpoint
        allow_expired: Whether to allow expired tokens (for refresh token flows)
    """

    async def _get_current_user(
        request: Request, auth_service: AuthService = Depends(get_auth_service)
    ) -> dict[str, Any]:
        auth_middleware = AuthMiddleware(auth_service)
        await auth_middleware(request, required_permissions, allow_expired)
        return request.state.user

    return _get_current_user


# Role-based access control
def require_role(roles: list[UserRole]):
    """
    Dependency for endpoints that require specific user roles.

    Args:
        roles: List of roles that are allowed to access the endpoint
    """

    async def _require_role(request: Request, auth_service: AuthService = Depends(get_auth_service)) -> dict[str, Any]:
        # First, authenticate the user
        auth_middleware = AuthMiddleware(auth_service)
        claims = await auth_middleware(request)

        # Check if user has required role
        user_role = claims.get(CLAIM_ROLE)
        if user_role not in [role.value for role in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join([role.value for role in roles])}",
            )

        return claims

    return _require_role


# Admin-only access
require_admin = require_role([UserRole.ADMIN])


# Permission-based access
def require_permission(permission: str):
    """
    Dependency for endpoints that require a specific permission.

    Args:
        permission: The permission required to access the endpoint
    """
    return get_current_user(required_permissions=[permission])


# Public endpoint marker
def public():
    """
    Explicitly mark an endpoint as public (no authentication required).
    This is primarily for documentation purposes.
    """

    def decorator(func):
        return func

    return decorator
