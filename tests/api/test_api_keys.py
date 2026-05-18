"""API key management endpoint tests with dependency overrides."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app import app, get_database_adapter
from api.routes import api_keys as api_keys_module
from api.routes.api_keys import require_api_keys_permission


class StubAPIKeyService:
    """Lightweight stub capturing API key operations for tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        now = datetime.now(UTC)
        self.sample_key: dict[str, Any] = {
            "id": "key-123",
            "name": "CI Bot",
            "permissions": ["documents:read"],
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(days=90),
            "last_used_at": None,
            "revoked": False,
        }

    async def list_user_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        self.calls.append(("list_user_api_keys", (user_id,)))
        return [self.sample_key]

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: list[str],
        expires_in_days: int | None,
    ) -> dict[str, Any]:
        self.calls.append(("create_api_key", (user_id, name, tuple(permissions), expires_in_days)))
        return {**self.sample_key, "key": "krai_live_created"}

    async def rotate_api_key(self, key_id: str, user_id: str) -> dict[str, Any]:
        self.calls.append(("rotate_api_key", (key_id, user_id)))
        return {**self.sample_key, "key": "krai_live_rotated", "version": self.sample_key["version"] + 1}

    async def revoke_api_key(self, key_id: str, user_id: str) -> None:
        self.calls.append(("revoke_api_key", (key_id, user_id)))


@pytest.fixture()
def api_keys_client(monkeypatch):
    """Yield TestClient with API key service + permissions overridden."""

    stub_service = StubAPIKeyService()

    def fake_get_database_adapter():
        return object()

    app.dependency_overrides[get_database_adapter] = fake_get_database_adapter
    app.dependency_overrides[require_api_keys_permission] = lambda: {
        "id": "user-123",
        "role": "admin",
        "permissions": ["api_keys:manage"],
    }

    monkeypatch.setattr(api_keys_module, "_get_service", lambda adapter: stub_service)

    with TestClient(app) as client:
        yield client, stub_service

    app.dependency_overrides.pop(get_database_adapter, None)
    app.dependency_overrides.pop(require_api_keys_permission, None)


@pytest.mark.parametrize("path", ["/api/v1/api-keys", "/api/v1/api-keys/?user_id=other-user"])
def test_list_api_keys_returns_payload(api_keys_client, path):
    client, stub = api_keys_client

    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["keys"][0]["id"] == stub.sample_key["id"]
    assert stub.calls[-1][0] == "list_user_api_keys"


def test_create_api_key_returns_secret(api_keys_client):
    client, stub = api_keys_client

    response = client.post(
        "/api/v1/api-keys",
        json={"name": "CI Bot", "permissions": ["documents:read"], "expires_in_days": 30},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["key"].startswith("krai_live_")
    assert stub.calls[-1][0] == "create_api_key"


def test_rotate_api_key_accepts_admin_override(api_keys_client):
    client, stub = api_keys_client

    response = client.post(
        "/api/v1/api-keys/key-123/rotate",
        params={"user_id": "override-user"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["version"] == stub.sample_key["version"] + 1
    assert stub.calls[-1] == ("rotate_api_key", ("key-123", "override-user"))


def test_revoke_api_key_returns_confirmation(api_keys_client):
    client, stub = api_keys_client

    response = client.post("/api/v1/api-keys/key-123/revoke")

    assert response.status_code == 200
    assert response.json()["data"] == {"id": "key-123", "revoked": True, "user_id": "user-123"}
    assert stub.calls[-1] == ("revoke_api_key", ("key-123", "user-123"))
