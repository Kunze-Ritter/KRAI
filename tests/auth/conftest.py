"""
Test configuration and fixtures for authentication tests.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.config.auth_config import ACCESS_TOKEN, JWT_ALGORITHM, jwt_validator

# Now import from backend
from backend.main import app
from backend.models.user import generate_jti
from backend.services.auth_service import AuthService
from backend.services.database_service import DatabaseService

# Test user data
TEST_USER = {
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPass123!",
    "first_name": "Test",
    "last_name": "User",
    "is_active": True,
    "is_verified": True,
    "role": "user",
}

TEST_ADMIN = {
    "email": "admin@example.com",
    "username": "admin",
    "password": "AdminPass123!",
    "first_name": "Admin",
    "last_name": "User",
    "is_active": True,
    "is_verified": True,
    "role": "admin",
}


@pytest.fixture(scope="module")
def test_app():
    """Test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def db_service():
    """Database service fixture with test database."""
    # Use a test database URL from environment or default
    test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
    db = DatabaseService(database_url=test_db_url)

    # Set up test data
    yield db

    # Clean up after tests
    # Note: In a real project, use transactions or a test database per test


@pytest.fixture(scope="module")
def auth_service(db_service):
    """Auth service fixture with test database."""
    return AuthService(db_service)


@pytest.fixture(scope="module")
def test_user(auth_service):
    """Create a test user."""
    # Delete if exists
    try:
        auth_service.delete_user_by_email(TEST_USER["email"])
    except:
        pass

    # Create test user
    user = auth_service.create_user(**TEST_USER)
    return user


@pytest.fixture(scope="module")
def test_admin(auth_service):
    """Create a test admin user."""
    # Delete if exists
    try:
        auth_service.delete_user_by_email(TEST_ADMIN["email"])
    except:
        pass

    # Create test admin
    admin = auth_service.create_user(**TEST_ADMIN)
    return admin


@pytest.fixture(scope="module")
def user_access_token(test_user):
    """Generate a valid access token for the test user."""
    payload = {
        "sub": str(test_user["id"]),
        "email": test_user["email"],
        "role": test_user.get("role", "viewer"),
        "token_type": ACCESS_TOKEN,
        "jti": generate_jti(),
    }
    return jwt_validator.encode_token(payload, ACCESS_TOKEN)


@pytest.fixture(scope="module")
def admin_access_token(test_admin):
    """Generate a valid access token for the test admin."""
    payload = {
        "sub": str(test_admin["id"]),
        "email": test_admin["email"],
        "role": test_admin.get("role", "admin"),
        "token_type": ACCESS_TOKEN,
        "jti": generate_jti(),
    }
    return jwt_validator.encode_token(payload, ACCESS_TOKEN)


@pytest.fixture(scope="module")
def expired_token():
    """Generate an expired access token."""
    # Create a token with past expiry
    import jwt as pyjwt

    from backend.config.auth_config import jwt_config

    payload = {
        "sub": "test_expired",
        "email": "expired@test.com",
        "role": "viewer",
        "token_type": ACCESS_TOKEN,
        "jti": generate_jti(),
        "exp": datetime.utcnow() - timedelta(minutes=5),
        "iat": datetime.utcnow() - timedelta(minutes=10),
    }
    return pyjwt.encode(payload, jwt_config.private_key, algorithm=JWT_ALGORITHM)


@pytest.fixture(scope="module")
def invalid_token():
    """Generate an invalid token."""
    return "invalid.token.string"
