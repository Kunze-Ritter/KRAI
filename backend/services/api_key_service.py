"""API key management service with rotation support."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta

import asyncpg

from config.security_config import get_security_config

logger = logging.getLogger("krai.api_keys")


class APIKeyService:
    """Service for API key CRUD, validation, and rotation."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.config = get_security_config()

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_key_prefix() -> str:
        return "krai_live_"

    def generate_api_key(self) -> str:
        random_part = secrets.token_urlsafe(32)
        return f"{self._generate_key_prefix()}{random_part}"

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> dict[str, str]:
        permissions = permissions or []
        raw_key = self.generate_api_key()
        key_hash = self._hash_key(raw_key)
        expires_days = expires_in_days or self.config.API_KEY_ROTATION_DAYS
        expires_at = datetime.now(UTC) + timedelta(days=expires_days)

        query = """
            INSERT INTO krai_system.api_keys (
                user_id,
                name,
                key_hash,
                permissions,
                version,
                created_at,
                updated_at,
                expires_at,
                revoked,
                revoked_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, NOW(), NOW(), $6, FALSE, NULL)
            RETURNING id, name, permissions, version, created_at, updated_at, expires_at, last_used_at, revoked
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                query,
                user_id,
                name,
                key_hash,
                json.dumps(permissions),
                1,
                expires_at,
            )
        logger.info("Created API key %s for user %s", record["id"], user_id)
        return {
            "id": record["id"],
            "key": raw_key,
            "name": record["name"],
            "permissions": record["permissions"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "expires_at": record["expires_at"],
            "last_used_at": record.get("last_used_at"),
            "version": record["version"],
            "revoked": record["revoked"],
        }

    async def list_user_api_keys(self, user_id: str) -> list[dict[str, str]]:
        query = """
            SELECT id, name, permissions, version, created_at, updated_at, expires_at, last_used_at, revoked
            FROM krai_system.api_keys
            WHERE user_id = $1
            ORDER BY created_at DESC
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    async def revoke_api_key(self, key_id: str, user_id: str | None = None) -> None:
        query = """
            UPDATE krai_system.api_keys
            SET revoked = TRUE, revoked_at = NOW()
            WHERE id = $1
            AND ($2 IS NULL OR user_id = $2)
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, key_id, user_id)
        logger.info("Revoked API key %s", key_id)

    async def validate_api_key(self, raw_key: str) -> dict[str, str] | None:
        key_hash = self._hash_key(raw_key)
        query = """
            SELECT id, user_id, permissions, expires_at, revoked
            FROM krai_system.api_keys
            WHERE key_hash = $1
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, key_hash)
        if not record:
            return None
        record = dict(record)
        if record["revoked"]:
            logger.warning("Attempt to use revoked API key %s", record["id"])
            return None
        if record["expires_at"] < datetime.now(UTC):
            logger.warning("Attempt to use expired API key %s", record["id"])
            return None
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE krai_system.api_keys SET last_used_at = NOW() WHERE id = $1",
                record["id"],
            )
        return record

    async def rotate_api_key(self, key_id: str, user_id: str) -> dict[str, str]:
        new_key = self.generate_api_key()
        key_hash = self._hash_key(new_key)
        expires_at = datetime.now(UTC) + timedelta(days=self.config.API_KEY_ROTATION_DAYS)
        query = """
            UPDATE krai_system.api_keys
            SET
                key_hash = $1,
                version = version + 1,
                created_at = NOW(),
                updated_at = NOW(),
                expires_at = $2,
                revoked = FALSE,
                revoked_at = NULL
            WHERE id = $3 AND user_id = $4
            RETURNING id, name, permissions, version, created_at, updated_at, expires_at, last_used_at, revoked
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, key_hash, expires_at, key_id, user_id)
        logger.info("Rotated API key %s for user %s", key_id, user_id)
        return {
            "id": record["id"],
            "key": new_key,
            "name": record["name"],
            "permissions": record["permissions"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "expires_at": record["expires_at"],
            "last_used_at": record.get("last_used_at"),
            "version": record["version"],
            "revoked": record["revoked"],
        }

    async def cleanup_expired_keys(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM krai_system.api_keys WHERE expires_at < NOW() - make_interval(days => $1)",
                self.config.API_KEY_GRACE_PERIOD_DAYS,
            )
        logger.info("Cleaned up expired API keys")
