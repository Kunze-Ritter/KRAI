"""
Tests for the AuthService class.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from jose import jwt

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Now import from backend


class TestAuthService:
    """Test cases for AuthService."""

    def test_create_user(self, auth_service):
        """Test creating a new user."""
        # Test data
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewPass123!",
            "first_name": "New",
            "last_name": "User",
        }

        # Create user
        user = auth_service.create_user(**user_data)

        # Verify user was created
        assert user["email"] == user_data["email"]
        assert user["username"] == user_data["username"]
        assert user["first_name"] == user_data["first_name"]
        assert user["last_name"] == user_data["last_name"]
        assert user["is_active"] is True
        assert user["is_verified"] is False
        assert user["role"] == "user"

        # Clean up
        auth_service.delete_user(user["id"])

    def test_authenticate_user_success(self, auth_service, test_user):
        """Test successful user authentication."""
        user = auth_service.authenticate_user(email=test_user["email"], password=TEST_USER["password"])
        assert user is not None
        assert user["email"] == test_user["email"]

    def test_authenticate_user_invalid_password(self, auth_service, test_user):
        """Test authentication with invalid password."""
        user = auth_service.authenticate_user(email=test_user["email"], password="wrongpassword")
        assert user is None

    def test_authenticate_user_nonexistent(self, auth_service):
        """Test authentication with non-existent email."""
        user = auth_service.authenticate_user(email="nonexistent@example.com", password="password")
        assert user is None

    def test_create_access_token(self, test_user):
        """Test access token creation."""
        token_data = {"sub": str(test_user["id"])}
        token = create_access_token(token_data)

        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == str(test_user["id"])
        assert "exp" in payload

    def test_create_refresh_token(self, test_user):
        """Test refresh token creation."""
        token_data = {"sub": str(test_user["id"])}
        token = create_refresh_token(token_data)

        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == str(test_user["id"])
        assert "exp" in payload

    def test_get_user(self, auth_service, test_user):
        """Test retrieving a user by ID."""
        user = auth_service.get_user(test_user["id"])
        assert user is not None
        assert user["id"] == test_user["id"]
        assert user["email"] == test_user["email"]

    def test_get_nonexistent_user(self, auth_service):
        """Test retrieving a non-existent user."""
        user = auth_service.get_user("00000000-0000-0000-0000-000000000000")
        assert user is None

    def test_update_user(self, auth_service, test_user):
        """Test updating a user."""
        update_data = {"first_name": "Updated", "last_name": "Name"}
        updated_user = auth_service.update_user(test_user["id"], **update_data)

        assert updated_user["first_name"] == update_data["first_name"]
        assert updated_user["last_name"] == update_data["last_name"]

        # Verify other fields remain unchanged
        assert updated_user["email"] == test_user["email"]
        assert updated_user["username"] == test_user["username"]

    def test_delete_user(self, auth_service):
        """Test deleting a user."""
        # Create a user to delete
        user_data = {
            "email": "todelete@example.com",
            "username": "todelete",
            "password": "DeleteMe123!",
            "first_name": "To",
            "last_name": "Delete",
        }
        user = auth_service.create_user(**user_data)

        # Delete the user
        result = auth_service.delete_user(user["id"])
        assert result is True

        # Verify user no longer exists
        assert auth_service.get_user(user["id"]) is None

    def test_verify_password(self, auth_service, test_user):
        """Test password verification."""
        assert auth_service.verify_password(TEST_USER["password"], test_user["hashed_password"]) is True

        assert auth_service.verify_password("wrongpassword", test_user["hashed_password"]) is False

    def test_get_password_hash(self, auth_service):
        """Test password hashing."""
        password = "TestPass123!"
        hashed = auth_service.get_password_hash(password)

        # Should be different from original
        assert hashed != password

        # Should be verifiable
        assert PWD_CONTEXT.verify(password, hashed)

    def test_blacklist_token(self, auth_service):
        """Test token blacklisting."""
        token = "test_token_123"
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        # Blacklist token
        result = auth_service.blacklist_token(token, expires_at)
        assert result is True

        # Check if token is blacklisted
        assert auth_service.is_token_blacklisted(token) is True

        # Clean up
        auth_service.unblacklist_token(token)

    def test_unblacklist_token(self, auth_service):
        """Test token unblacklisting."""
        token = "test_token_456"
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        # Blacklist token first
        auth_service.blacklist_token(token, expires_at)
        assert auth_service.is_token_blacklisted(token) is True

        # Unblacklist token
        result = auth_service.unblacklist_token(token)
        assert result is True
        assert auth_service.is_token_blacklisted(token) is False

    def test_is_token_blacklisted_nonexistent(self, auth_service):
        """Test checking non-existent token in blacklist."""
        assert auth_service.is_token_blacklisted("nonexistent_token") is False


# Helper function to get test user data
def get_test_user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123!",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_verified": True,
        "role": "user",
    }
