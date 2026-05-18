# Shared fixtures for API tests
import pytest
from httpx import AsyncClient

from backend.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def async_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# Example token fixture (replace with real token generation as needed)
@pytest.fixture
async def admin_token(async_client: AsyncClient):
    # Assuming there is a login endpoint that returns a JWT
    response = await async_client.post(
        "/api/v1/auth/login", json={"username": "admin@example.com", "password": "adminpass"}
    )
    data = response.json()
    return data.get("access_token")
