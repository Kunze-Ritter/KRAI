"""Unit tests for APIKeyService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from services.api_key_service import APIKeyService


class StubAdapter:
    """Simple adapter mock capturing queries and returning queued responses."""

    def __init__(self, responses: list[list[dict]] | None = None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, list[Any]]] = []

    async def execute_query(self, query: str, params: list[Any] | tuple[Any, ...]):
        self.calls.append((query, list(params)))
        if self.responses:
            return self.responses.pop(0)
        return []


@pytest.fixture(autouse=True)
def override_security_config(monkeypatch):
    class DummyConfig:
        API_KEY_ROTATION_DAYS = 90
        API_KEY_GRACE_PERIOD_DAYS = 7

    monkeypatch.setattr("services.api_key_service.get_security_config", lambda: DummyConfig)
    return DummyConfig


@pytest.mark.anyio
async def test_generate_api_key_uses_prefix():
    service = APIKeyService(adapter=StubAdapter())
    api_key = service.generate_api_key()
    assert api_key.startswith("krai_live_")


@pytest.mark.anyio
async def test_create_api_key_stores_hash_and_returns_metadata():
    now = datetime.now(UTC)
    adapter = StubAdapter(
        responses=[
            [
                {
                    "id": "key-1",
                    "name": "CI Bot",
                    "permissions": ["documents:read"],
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                    "expires_at": now + timedelta(days=90),
                    "last_used_at": None,
                    "revoked": False,
                }
            ]
        ]
    )
    service = APIKeyService(adapter=adapter)

    result = await service.create_api_key(
        user_id="user-123",
        name="CI Bot",
        permissions=["documents:read"],
    )

    assert result["id"] == "key-1"
    assert result["name"] == "CI Bot"
    assert result["key"].startswith("krai_live_")
    hashed_param = adapter.calls[0][1][2]
    assert hashed_param == service._hash_key(result["key"])


@pytest.mark.anyio
async def test_rotate_api_key_resets_revocation_flags():
    now = datetime.now(UTC)
    adapter = StubAdapter(
        responses=[
            [
                {
                    "id": "key-1",
                    "name": "CI Bot",
                    "permissions": ["documents:read"],
                    "version": 2,
                    "created_at": now,
                    "updated_at": now,
                    "expires_at": now + timedelta(days=90),
                    "last_used_at": None,
                    "revoked": False,
                }
            ]
        ]
    )
    service = APIKeyService(adapter=adapter)

    result = await service.rotate_api_key("key-1", "user-123")

    assert result["version"] == 2
    assert result["revoked"] is False
    hashed_param = adapter.calls[0][1][0]
    assert hashed_param == service._hash_key(result["key"])


@pytest.mark.anyio
async def test_validate_api_key_updates_last_used_timestamp():
    expires = datetime.now(UTC) + timedelta(days=1)
    adapter = StubAdapter(
        responses=[
            [
                {
                    "id": "key-1",
                    "user_id": "user-123",
                    "permissions": ["documents:read"],
                    "expires_at": expires,
                    "revoked": False,
                }
            ]
        ]
    )
    service = APIKeyService(adapter=adapter)

    validated = await service.validate_api_key("krai_live_test")

    assert validated is not None
    assert adapter.calls[1][0].startswith("UPDATE krai_system.api_keys SET last_used_at")
    assert adapter.calls[1][1] == ["key-1"]


@pytest.mark.anyio
async def test_validate_api_key_rejects_revoked_records():
    adapter = StubAdapter(
        responses=[
            [
                {
                    "id": "key-1",
                    "user_id": "user-123",
                    "permissions": [],
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                    "revoked": True,
                }
            ]
        ]
    )
    service = APIKeyService(adapter=adapter)

    validated = await service.validate_api_key("krai_live_test")

    assert validated is None
    assert len(adapter.calls) == 1  # No last_used update


@pytest.mark.anyio
async def test_cleanup_expired_keys_uses_grace_period(Config=override_security_config):
    adapter = StubAdapter()
    service = APIKeyService(adapter=adapter)

    await service.cleanup_expired_keys()

    assert adapter.calls[0][1][0] == 7
