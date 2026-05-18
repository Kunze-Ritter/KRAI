# Authentication Test Suite

## 📋 Overview

This directory contains comprehensive tests for the KRAI authentication system, including:
- **Unit Tests**: Test individual AuthService methods
- **Integration Tests**: Test authentication API endpoints
- **Fixtures**: Shared test data and configuration

## 🏗️ Test Structure

```
tests/auth/
├── conftest.py              # Pytest fixtures and configuration
├── test_auth_service.py     # Unit tests for AuthService
├── test_auth_endpoints.py   # Integration tests for auth routes
└── README.md               # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Install test dependencies:**
   ```bash
   pip install pytest pytest-asyncio httpx
   ```

2. **Set up test database:**

   Option A: SQLite (Quick & Easy)
   ```bash
   # Add to .env.test
   TEST_DATABASE_URL=sqlite:///./test_auth.db
   ```

   Option B: PostgreSQL (Recommended)
   ```bash
   # Add to .env.test
   TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/krai_test
   ```

3. **Create test database schema:**
   ```bash
   # Run migrations on test database
   psql -U user -d krai_test -f database/migrations/02_extend_users_table.sql
   psql -U user -d krai_test -f database/migrations/03_token_blacklist_table.sql
   ```

### Running Tests

```bash
# Run all auth tests
pytest tests/auth/ -v

# Run specific test file
pytest tests/auth/test_auth_service.py -v

# Run specific test
pytest tests/auth/test_auth_service.py::TestAuthService::test_create_user -v

# Run with coverage
pytest tests/auth/ --cov=backend.services.auth_service --cov-report=html

# Run with detailed output
pytest tests/auth/ -v -s
```

## 📝 Test Coverage

### Unit Tests (test_auth_service.py)

- ✅ User creation and validation
- ✅ Password hashing and verification
- ✅ User authentication
- ✅ Token generation and validation
- ✅ Token blacklisting
- ✅ User retrieval and updates
- ✅ User deletion

### Integration Tests (test_auth_endpoints.py)

- ✅ User registration
- ✅ User login
- ✅ Token refresh
- ✅ User logout
- ✅ Protected route access
- ✅ Role-based access control
- ✅ Password change

## 🔧 Configuration

### Test Fixtures (conftest.py)

The test suite uses pytest fixtures for:
- **test_app**: FastAPI test client
- **db_service**: Database service with test database
- **auth_service**: Authentication service instance
- **test_user**: Regular test user
- **test_admin**: Admin test user
- **user_access_token**: Valid access token for test user
- **admin_access_token**: Valid access token for admin
- **expired_token**: Expired token for testing
- **invalid_token**: Invalid token for testing

### Environment Variables

Create a `.env.test` file for test-specific configuration:

```bash
# Database
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/krai_test

# JWT Configuration
JWT_PRIVATE_KEY=<your-test-private-key>
JWT_PUBLIC_KEY=<your-test-public-key>
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Test Settings
TESTING=true
DEBUG=true
```

## 🐛 Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'backend'**
   - Solution: The conftest.py adds the project root to sys.path automatically
   - Verify you're running pytest from the project root

2. **Database connection errors**
   - Ensure test database exists and is accessible
   - Check TEST_DATABASE_URL in .env.test
   - Verify database migrations have been applied

3. **Pydantic validation errors**
   - Ensure you're using Pydantic v2
   - Check that all model fields use `pattern` instead of `regex`

4. **JWT key errors**
   - Generate new JWT keys using the auth_config.py script
   - Add keys to .env.test file

### Current Known Issues

1. **Integration tests require real database**
   - The test fixtures currently expect a real database connection
   - Mock database support is planned for future updates

2. **Test isolation**
   - Tests may interfere with each other if run in parallel
   - Use `pytest tests/auth/ -n 1` to run sequentially

## 📚 Writing New Tests

### Example Unit Test

```python
def test_my_auth_feature(auth_service):
    """Test description."""
    # Arrange
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123!"
    }

    # Act
    result = auth_service.create_user(user_data)

    # Assert
    assert result["email"] == user_data["email"]
    assert "id" in result
```

### Example Integration Test

```python
def test_my_endpoint(test_app, user_access_token):
    """Test endpoint description."""
    # Arrange
    headers = {"Authorization": f"Bearer {user_access_token}"}

    # Act
    response = test_app.get("/api/v1/auth/me", headers=headers)

    # Assert
    assert response.status_code == 200
    assert "email" in response.json()
```

## 🎯 Next Steps

- [ ] Add test database setup script
- [ ] Implement mock database for faster unit tests
- [ ] Add performance benchmarks
- [ ] Add security penetration tests
- [ ] Integrate with CI/CD pipeline

## 📖 References

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [KRAI Authentication Docs](../../backend/docs/AUTHENTICATION.md)
