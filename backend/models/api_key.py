"""Pydantic models for API key management APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, validator

from backend.models.validators import ensure_min_length, sanitize_string, validate_uuid


class APIKeyBase(BaseModel):
    """Shared fields for API keys."""

    name: str = Field(..., description="Friendly label for the API key")
    permissions: list[str] = Field(
        default_factory=list,
        description="Permission identifiers granted to the API key",
    )
    expires_in_days: int | None = Field(None, ge=1, le=365, description="Override for expiration in days")

    @validator("name")
    def validate_name(cls, value: str) -> str:
        sanitized = sanitize_string(value)
        ensure_min_length(sanitized, 3, "name")
        return sanitized

    @validator("permissions", each_item=True)
    def validate_permissions(cls, value: str) -> str:
        sanitized = sanitize_string(value)
        ensure_min_length(sanitized, 2, "permission value")
        return sanitized


class APIKeyCreateRequest(APIKeyBase):
    """Payload for creating API keys."""

    user_id: str | None = Field(None, description="Optional user ID (admins only)")

    @validator("user_id")
    def validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)


class APIKeyRotateRequest(BaseModel):
    """Payload for API key rotation."""

    user_id: str | None = Field(None, description="Optional user ID to scope rotation")

    @validator("user_id")
    def validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)


class APIKeyRevokeRequest(APIKeyRotateRequest):
    """Payload for revoking API keys."""


class APIKeyResponse(BaseModel):
    """Representation of an API key record (without raw secret)."""

    id: str
    name: str
    permissions: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked: bool

    class Config:
        json_schema_extra = {
            "example": {
                "id": "c5fb3b3c-9b0c-4b18-8545-0232da7e864f",
                "name": "Monitoring bot",
                "permissions": ["documents:read"],
                "version": 1,
                "created_at": "2025-11-19T10:00:00Z",
                "updated_at": "2025-11-19T10:00:00Z",
                "expires_at": "2026-02-17T10:00:00Z",
                "last_used_at": None,
                "revoked": False,
            }
        }


class APIKeyWithSecretResponse(APIKeyResponse):
    """Response returned after create/rotate that includes the secret value."""

    key: str = Field(..., description="Plaintext API key (displayed once)")


class APIKeyListResponse(BaseModel):
    """Envelope for list responses."""

    keys: list[APIKeyResponse]

    class Config:
        json_schema_extra = {
            "example": {
                "keys": [APIKeyResponse.Config.json_schema_extra["example"]],
            }
        }
