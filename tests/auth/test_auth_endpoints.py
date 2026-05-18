"""
Tests for authentication API endpoints.
"""

import sys
from pathlib import Path

from fastapi import status

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Now import from backend

# Test data
LOGIN_DATA = {"username": "test@example.com", "password": "TestPass123!"}  # Can be email or username

REGISTER_DATA = {
    "email": "newuser@example.com",
    "username": "newuser",
    "password": "NewPass123!",
    "first_name": "New",
    "last_name": "User",
}


class TestAuthEndpoints:
    """Test cases for authentication endpoints."""

    def test_register(self, test_app):
        """Test user registration."""
        # Delete test user if exists
        test_app.delete(f"/api/v1/auth/register?email={REGISTER_DATA['email']}")

        # Register new user
        response = test_app.post("/api/v1/auth/register", json=REGISTER_DATA)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == REGISTER_DATA["email"]
        assert data["username"] == REGISTER_DATA["username"]
        assert data["first_name"] == REGISTER_DATA["first_name"]
        assert data["last_name"] == REGISTER_DATA["last_name"]
        assert "id" in data
        assert "hashed_password" not in data

        # Clean up
        test_app.delete(f"/api/v1/users/{data['id']}")

    def test_register_existing_email(self, test_app, test_user):
        """Test registration with existing email."""
        response = test_app.post(
            "/api/v1/auth/register",
            json={
                "email": test_user["email"],
                "username": "differentuser",
                "password": "Password123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.text

    def test_register_existing_username(self, test_app, test_user):
        """Test registration with existing username."""
        response = test_app.post(
            "/api/v1/auth/register",
            json={
                "email": "different@example.com",
                "username": test_user["username"],
                "password": "Password123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already registered" in response.text

    def test_login_success_email(self, test_app, test_user):
        """Test successful login with email."""
        response = test_app.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": TEST_USER["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_login_success_username(self, test_app, test_user):
        """Test successful login with username."""
        response = test_app.post(
            "/api/v1/auth/login",
            data={"username": test_user["username"], "password": TEST_USER["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, test_app, test_user):
        """Test login with invalid credentials."""
        response = test_app.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": "wrongpassword"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email or password" in response.text

    def test_refresh_token(self, test_app, test_user):
        """Test token refresh."""
        # First login to get refresh token
        login_response = test_app.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": TEST_USER["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = test_app.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh_token  # Token rotation

    def test_logout(self, test_app, test_user, user_access_token):
        """Test user logout."""
        response = test_app.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {user_access_token}"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Successfully logged out"

        # Verify token is blacklisted
        response = test_app.get("/api/v1/users/me", headers={"Authorization": f"Bearer {user_access_token}"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user(self, test_app, test_user, user_access_token):
        """Test getting current user info."""
        response = test_app.get("/api/v1/users/me", headers={"Authorization": f"Bearer {user_access_token}"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(test_user["id"])
        assert data["email"] == test_user["email"]
        assert "hashed_password" not in data

    def test_protected_route_unauthorized(self, test_app):
        """Test accessing protected route without token."""
        response = test_app.get("/api/v1/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_route_invalid_token(self, test_app):
        """Test accessing protected route with invalid token."""
        response = test_app.get("/api/v1/users/me", headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_route_expired_token(self, test_app, expired_token):
        """Test accessing protected route with expired token."""
        response = test_app.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token has expired" in response.text

    def test_admin_route_access_denied(self, test_app, user_access_token):
        """Test regular user accessing admin route."""
        response = test_app.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {user_access_token}"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_route_success(self, test_app, admin_access_token):
        """Test admin accessing admin route."""
        response = test_app.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_access_token}"})
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)

    def test_change_password(self, test_app, test_user, user_access_token):
        """Test changing password."""
        new_password = "NewPassword123!"
        response = test_app.put(
            "/api/v1/users/me/password",
            json={
                "current_password": TEST_USER["password"],
                "new_password": new_password,
                "confirm_password": new_password,
            },
            headers={"Authorization": f"Bearer {user_access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Password updated successfully"

        # Verify login with new password works
        login_response = test_app.post(
            "/api/v1/auth/login",
            data={"username": test_user["email"], "password": new_password},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert login_response.status_code == status.HTTP_200_OK

        # Change password back for other tests
        test_app.put(
            "/api/v1/users/me/password",
            json={
                "current_password": new_password,
                "new_password": TEST_USER["password"],
                "confirm_password": TEST_USER["password"],
            },
            headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
        )

    def test_change_password_wrong_current(self, test_app, user_access_token):
        """Test changing password with wrong current password."""
        response = test_app.put(
            "/api/v1/users/me/password",
            json={
                "current_password": "wrongpassword",
                "new_password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            },
            headers={"Authorization": f"Bearer {user_access_token}"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Current password is incorrect" in response.text
