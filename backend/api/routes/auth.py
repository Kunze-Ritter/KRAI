"""
Authentication and User Management Routes

Handles user authentication, registration, token management, and user administration
with role-based access control (RBAC) and permission management.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from backend.api.dependencies.auth import get_auth_service, set_auth_service
from backend.api.middleware.auth_middleware import get_current_user, require_permission
from backend.api.middleware.rate_limit_middleware import limiter, rate_limit_auth
from backend.config.auth_config import ACCESS_TOKEN
from backend.models.user import UserCreate, UserListResponse, UserLogin, UserRole, UserStatus, UserUpdate

# Import services and models
from backend.services.auth_service import AuthenticationError, AuthorizationError, AuthService, RateLimitError
from backend.services.database_adapter import DatabaseAdapter

logger = logging.getLogger("krai.api.auth")

# Setup router and security
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    try:
        # Check for forwarded headers first (if behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP if multiple are listed
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client and request.client.host:
            return request.client.host

        return "unknown"
    except Exception as e:
        logger.error(f"Error resolving client IP: {e}")
        return "unknown"


# Request/Response Models
class LoginRequest(UserLogin):
    """Login request model"""

    pass


class RegisterRequest(UserCreate):
    """User registration request model"""

    pass


class TokenRefreshRequest(BaseModel):
    """Token refresh request model"""

    refresh_token: str = Field(..., description="Valid refresh token")


class ChangePasswordRequest(BaseModel):
    """Change password request model"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")


class UserCreateRequest(UserCreate):
    """Create user request model (admin only)"""

    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    is_active: bool = Field(default=True, description="Whether the user is active")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="User status")


class UserUpdateRequest(UserUpdate):
    """Update user request model"""

    role: UserRole | None = Field(None, description="User role (admin only)")
    is_active: bool | None = Field(None, description="Whether the user is active")
    status: UserStatus | None = Field(None, description="User status")
    permissions: list[str] | None = Field(None, description="List of user permissions")


class TokenResponse(BaseModel):
    """Token response model"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str | None = Field(None, description="Refresh token (if requested)")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class AuthResponseModel(BaseModel):
    """Authentication response model"""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field("Authentication successful", description="Response message")
    data: dict[str, Any] | None = Field(None, description="Response data")


class UserListResponseModel(BaseModel):
    """User list response model"""

    success: bool = Field(True, description="Whether the operation was successful")
    data: UserListResponse = Field(..., description="Paginated user list")


class ErrorResponseModel(BaseModel):
    success: bool = False
    error: str
    detail: str | None = None
    error_code: str | None = None


# API Endpoints


@router.post(
    "/login",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "Login successful"},
        400: {"description": "Invalid request", "model": ErrorResponseModel},
        401: {"description": "Invalid credentials", "model": ErrorResponseModel},
        403: {"description": "Account not active or locked", "model": ErrorResponseModel},
        429: {"description": "Too many login attempts", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
@limiter.limit(rate_limit_auth)
async def login(request: Request, payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """
    Authenticate user and return access token

    - **username**: Username or email
    - **password**: User's password
    - **remember_me**: Whether to generate a refresh token (default: false)
    """
    print("DEBUG: Login endpoint called")
    try:
        # Get client IP for rate limiting
        client_ip = get_client_ip(request)
        print(f"DEBUG: Client IP resolved: {client_ip}")

        # Create login data
        login_data = UserLogin(username=payload.username, password=payload.password, remember_me=payload.remember_me)

        # Authenticate user
        auth_response = await service.authenticate_user(login_data, client_ip)

        # Return success response
        return {
            "success": True,
            "message": auth_response.message,
            "data": {
                "access_token": auth_response.access_token,
                "refresh_token": auth_response.refresh_token,
                "token_type": auth_response.token_type,
                "expires_in": auth_response.expires_in,
                "user": auth_response.user.dict() if auth_response.user else {},
            },
        }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponseModel(
                success=False, error="Authentication failed", detail=str(e), error_code="AUTH_001"
            ).dict(),
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ErrorResponseModel(
                success=False, error="Rate limit exceeded", detail=str(e), error_code="RATE_LIMIT_001"
            ).dict(),
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponseModel(
                success=False,
                error="Internal server error",
                detail="An unexpected error occurred",
                error_code="SERVER_001",
            ).dict(),
        )


@router.post(
    "/register",
    response_model=AuthResponseModel,
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid input data", "model": ErrorResponseModel},
        409: {"description": "Username or email already exists", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
@limiter.limit(rate_limit_auth)
async def register(request: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    """
    Register new user account
    """
    try:
        # Validate password confirmation
        if request.password != request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponseModel(
                    success=False, error="Validation error", detail="Passwords do not match"
                ).dict(),
            )

        # Create user data
        user_data = UserCreate(
            email=request.email,
            username=request.username,
            password=request.password,
            confirm_password=request.confirm_password,
            first_name=request.first_name,
            last_name=request.last_name,
            role=UserRole.VIEWER,  # Default role for self-registration
        )

        # Create user
        user = await service.create_user(user_data)

        # Generate tokens
        tokens = await service._generate_tokens(user.dict())

        return {
            "success": True,
            "message": "Registration successful",
            "data": {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "token_type": "bearer",
                "expires_in": tokens["expires_in"],
                "user": user.dict(),
            },
        }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponseModel(success=False, error="Validation error", detail=str(e)).dict(),
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponseModel(
                success=False, error="Internal server error", detail="Registration failed"
            ).dict(),
        )


@router.post(
    "/refresh-token",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid or expired refresh token", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
@limiter.limit(rate_limit_auth)
async def refresh_token(request: TokenRefreshRequest, service: AuthService = Depends(get_auth_service)):
    """
    Refresh access token using a valid refresh token

    - **refresh_token**: Valid refresh token
    """
    try:
        # Validate refresh token
        tokens = await service.refresh_access_token(request.refresh_token)

        return {
            "success": True,
            "message": "Token refreshed successfully",
            "data": {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "token_type": "bearer",
                "expires_in": tokens["expires_in"],
            },
        }

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to refresh token"},
        )


@router.get(
    "/me",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def get_current_user_info(current_user: dict = Depends(get_current_user())):
    """
    Get current user information

    Returns the authenticated user's profile information and permissions.
    """
    try:
        return {"success": True, "message": "User information retrieved successfully", "data": {"user": current_user}}
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to get user information"},
        )


@router.post(
    "/logout",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "Logout successful"},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
@limiter.limit("10/minute")
async def logout(
    request: Request, current_user: dict = Depends(get_current_user()), service: AuthService = Depends(get_auth_service)
):
    """
    Logout user and revoke the current access token

    This will add the current access token to the blacklist.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "error": "Invalid authorization header"},
            )

        token = auth_header.split(" ")[1]

        # Decode token to get JTI and expiration
        payload = await service.decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail={"success": False, "error": "Invalid or revoked token"}
            )
        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail={"success": False, "error": "Invalid token"}
            )

        # Add token to blacklist
        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        await service.add_to_blacklist(
            jti=jti, user_id=current_user["id"], token_type=ACCESS_TOKEN, expires_at=expires_at
        )

        return {"success": True, "message": "Successfully logged out"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"success": False, "error": "Logout failed"}
        )


@router.get(
    "/health",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "Health check successful"},
        500: {"description": "Service unavailable", "model": ErrorResponseModel},
    },
)
async def auth_health_check(service: AuthService = Depends(get_auth_service)):
    """
    Health check endpoint for authentication service

    Verifies that the authentication service is running and can access required resources.
    """
    try:
        # Check database connection
        await service._get_user_by_id("health-check")  # This will fail with 404 which is fine

        return {
            "success": True,
            "message": "Authentication service is healthy",
            "data": {"service": "auth", "status": "healthy", "timestamp": datetime.utcnow().isoformat()},
        }

    except Exception as e:
        logger.error(f"Auth health check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"success": False, "error": "Authentication service is unhealthy", "details": str(e)},
        )


# ============================================
# User Management Endpoints (Admin Only)
# ============================================


@router.get(
    "/users",
    response_model=UserListResponseModel,
    responses={
        200: {"description": "List of users retrieved successfully"},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_permission("users:manage")),
    service: AuthService = Depends(get_auth_service),
):
    """
    List all users with pagination (Admin only)

    - **page**: Page number (default: 1)
    - **page_size**: Number of items per page (default: 10, max: 100)
    """
    try:
        result = await service.list_users(current_user_id=current_user["id"], page=page, page_size=page_size)

        return {"success": True, "data": result.dict()}

    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to list users"},
        )


@router.post(
    "/users",
    response_model=AuthResponseModel,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid request", "model": ErrorResponseModel},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        409: {"description": "User already exists", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def create_user(
    user_data: UserCreateRequest,
    current_user: dict = Depends(require_permission("users:manage")),
    service: AuthService = Depends(get_auth_service),
):
    """
    Create a new user (Admin only)

    - **email**: User's email address
    - **username**: Unique username
    - **password**: Strong password
    - **first_name**: User's first name
    - **last_name**: User's last name
    - **role**: User role (default: USER)
    - **is_active**: Whether the user is active (default: true)
    - **status**: User status (default: ACTIVE)
    """
    try:
        # Create user
        user = await service.create_user(user_data)

        return {"success": True, "message": "User created successfully", "data": {"user": user.dict()}}

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Create user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to create user"},
        )


@router.get(
    "/users/{user_id}",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "User retrieved successfully"},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        404: {"description": "User not found", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def get_user(
    user_id: str = Path(..., description="User ID"),
    current_user: dict = Depends(get_current_user()),
    service: AuthService = Depends(get_auth_service),
):
    """
    Get user by ID

    Users can view their own profile, admins can view any profile.
    """
    try:
        # Allow users to view their own profile
        if user_id != current_user["id"] and not await service.has_permission(current_user["id"], "users:manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail={"success": False, "error": "Insufficient permissions"}
            )

        user = await service._get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"success": False, "error": "User not found"}
            )

        return {"success": True, "data": {"user": user.dict()}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"success": False, "error": "Failed to get user"}
        )


@router.put(
    "/users/{user_id}",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "Invalid request", "model": ErrorResponseModel},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        404: {"description": "User not found", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: dict = Depends(get_current_user()),
    service: AuthService = Depends(get_auth_service),
):
    """
    Update user information

    Users can update their own profile, admins can update any profile.
    """
    try:
        # Check if user exists
        existing_user = await service._get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"success": False, "error": "User not found"}
            )

        # Only allow admins to update other users
        if user_id != current_user["id"] and not await service.has_permission(current_user["id"], "users:manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail={"success": False, "error": "Insufficient permissions"}
            )

        # Update user
        updated_user = await service.update_user(
            user_id=user_id, update_data=user_data, current_user_id=current_user["id"]
        )

        return {"success": True, "message": "User updated successfully", "data": {"user": updated_user.dict()}}

    except (AuthenticationError, AuthorizationError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"success": False, "error": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to update user"},
        )


@router.delete(
    "/users/{user_id}",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "User deleted successfully"},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        404: {"description": "User not found", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_permission("users:manage")),
    service: AuthService = Depends(get_auth_service),
):
    """
    Delete a user (Admin only)

    This performs a soft delete by setting is_active=False.
    """
    try:
        # Don't allow users to delete themselves
        if user_id == current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "error": "Cannot delete your own account"},
            )

        # Delete user
        success = await service.delete_user(user_id, current_user["id"])
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"success": False, "error": "User not found"}
            )

        return {"success": True, "message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to delete user"},
        )


@router.post(
    "/users/{user_id}/change-password",
    response_model=AuthResponseModel,
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "Invalid request", "model": ErrorResponseModel},
        401: {"description": "Not authenticated", "model": ErrorResponseModel},
        403: {"description": "Insufficient permissions", "model": ErrorResponseModel},
        500: {"description": "Internal server error", "model": ErrorResponseModel},
    },
)
async def change_password(
    user_id: str,
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user()),
    service: AuthService = Depends(get_auth_service),
):
    """
    Change user password

    Users can change their own password, admins can change any user's password.
    """
    try:
        # Check if passwords match
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail={"success": False, "error": "Passwords do not match"}
            )

        # Only allow users to change their own password unless admin
        if user_id != current_user["id"] and not await service.has_permission(current_user["id"], "users:manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail={"success": False, "error": "Insufficient permissions"}
            )

        is_admin_changing_other = user_id != current_user["id"]
        if is_admin_changing_other:
            logger.warning(
                "Admin '%s' is changing password for user '%s'",
                current_user.get("email"),
                user_id,
            )

        # Update password
        update_data = UserUpdate(
            current_password=password_data.current_password if not is_admin_changing_other else None,
            new_password=password_data.new_password,
        )

        await service.update_user(user_id=user_id, update_data=update_data, current_user_id=current_user["id"])

        return {"success": True, "message": "Password changed successfully"}

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"success": False, "error": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": "Failed to change password"},
        )


def initialize_auth_routes(database_service: DatabaseAdapter):
    """Initialize authentication routes with database service"""
    set_auth_service(AuthService(database_service))
    return router
