"""Factory helpers for creating and registering the AuthService."""

from backend.services.auth_service import AuthService
from backend.services.database_factory import create_database_adapter


def create_auth_service() -> AuthService:
    """Instantiate AuthService using the configured database service."""
    db_service = create_database_adapter()
    return AuthService(db_service)


async def create_and_initialize_auth_service() -> AuthService:
    """Create and initialize AuthService with database connection."""
    auth_service = create_auth_service()
    await auth_service.initialize()
    return auth_service
