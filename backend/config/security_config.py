"""Centralized security configuration for KRAI backend."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class SecurityConfig(BaseSettings):
    """Security configuration loaded from environment variables."""

    # CORS settings
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = Field(default_factory=lambda: ["*"])
    CORS_ALLOW_HEADERS: list[str] = Field(default_factory=lambda: ["*"])
    CORS_MAX_AGE: int = 3600

    # Rate limiting settings
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE: str = "redis"
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_UPLOAD: str = "10/hour"
    RATE_LIMIT_SEARCH: str = "60/minute"
    RATE_LIMIT_STANDARD: str = "100/minute"
    RATE_LIMIT_HEALTH: str = "300/minute"
    RATE_LIMIT_API_KEY: str = "1000/minute"
    RATE_LIMIT_WHITELIST: list[str] = Field(default_factory=list)
    RATE_LIMIT_BLACKLIST: list[str] = Field(default_factory=list)

    # Request validation settings
    MAX_REQUEST_SIZE_MB: int = 500
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_FILE_TYPES: list[str] = Field(default_factory=lambda: [".pdf", ".docx", ".png", ".jpg", ".jpeg"])
    REQUEST_VALIDATION_ENABLED: bool = True
    VALIDATION_STRICTNESS: str = "strict"

    # Security headers
    SECURITY_HEADERS_ENABLED: bool = True
    CSP_POLICY: str = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    HSTS_MAX_AGE: int = 31536000
    HSTS_INCLUDE_SUBDOMAINS: bool = True
    HSTS_PRELOAD: bool = False

    # Timeout settings
    REQUEST_TIMEOUT_SECONDS: int = 300
    UPLOAD_TIMEOUT_SECONDS: int = 600
    KEEPALIVE_TIMEOUT_SECONDS: int = 5

    # API key rotation settings
    API_KEY_ROTATION_ENABLED: bool = True
    API_KEY_ROTATION_DAYS: int = 90
    API_KEY_GRACE_PERIOD_DAYS: int = 7
    API_KEY_VERSION_LIMIT: int = 3

    # Password policy (mirrors env flags)
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = False
    PASSWORD_REQUIRE_LOWERCASE: bool = False
    PASSWORD_REQUIRE_NUMBER: bool = False
    PASSWORD_REQUIRE_SPECIAL: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # shared .env carries many unrelated vars; only parse our own

    @field_validator("RATE_LIMIT_STORAGE")
    def validate_rate_limit_storage(cls, value: str) -> str:
        if value not in {"redis", "memory"}:
            raise ValueError("RATE_LIMIT_STORAGE must be either 'redis' or 'memory'")
        return value

    @field_validator(
        "RATE_LIMIT_AUTH",
        "RATE_LIMIT_UPLOAD",
        "RATE_LIMIT_SEARCH",
        "RATE_LIMIT_STANDARD",
        "RATE_LIMIT_HEALTH",
        "RATE_LIMIT_API_KEY",
    )
    def validate_rate_limit_format(cls, value: str) -> str:
        if "/" not in value:
            raise ValueError("Rate limit format must be '<count>/<period>'")
        count, period = value.split("/", maxsplit=1)
        if not count.isdigit():
            raise ValueError("Rate limit count must be numeric")
        if period not in {"second", "minute", "hour", "day"} and not period.endswith(
            ("seconds", "minutes", "hours", "days")
        ):
            raise ValueError("Rate limit period must be second/minute/hour/day")
        return value

    @field_validator("ALLOWED_FILE_TYPES")
    def normalize_file_types(cls, values: list[str]) -> list[str]:
        normalized = []
        for ext in values:
            if not ext.startswith("."):
                raise ValueError("Allowed file types must start with '.'")
            normalized.append(ext.lower())
        return normalized

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    def parse_cors_origins(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("CORS_ALLOWED_ORIGINS")
    def ensure_cors_origins(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("At least one CORS origin must be configured")
        return values

    @property
    def cors_allowed_origins_str(self) -> list[str]:
        return self.CORS_ALLOWED_ORIGINS

    @property
    def rate_limit_storage_url(self) -> str | None:
        redis_url = os.getenv("REDIS_URL")
        if self.RATE_LIMIT_STORAGE == "redis" and redis_url:
            return redis_url
        return None


def get_cors_config(config: SecurityConfig | None = None) -> dict:
    cfg = config or get_security_config()
    return {
        "allow_origins": cfg.cors_allowed_origins_str,
        "allow_credentials": cfg.CORS_ALLOW_CREDENTIALS,
        "allow_methods": cfg.CORS_ALLOW_METHODS,
        "allow_headers": cfg.CORS_ALLOW_HEADERS,
        "max_age": cfg.CORS_MAX_AGE,
        "expose_headers": ["Content-Disposition"],
    }


def get_rate_limit_config(config: SecurityConfig | None = None) -> dict:
    cfg = config or get_security_config()
    return {
        "enabled": cfg.RATE_LIMIT_ENABLED,
        "storage": cfg.RATE_LIMIT_STORAGE,
        "limits": {
            "auth": cfg.RATE_LIMIT_AUTH,
            "upload": cfg.RATE_LIMIT_UPLOAD,
            "search": cfg.RATE_LIMIT_SEARCH,
            "standard": cfg.RATE_LIMIT_STANDARD,
            "health": cfg.RATE_LIMIT_HEALTH,
            "api_key": cfg.RATE_LIMIT_API_KEY,
        },
        "whitelist": cfg.RATE_LIMIT_WHITELIST,
        "blacklist": cfg.RATE_LIMIT_BLACKLIST,
    }


def is_production(config: SecurityConfig | None = None) -> bool:
    cfg = config or get_security_config()
    return os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower() == "production"


@lru_cache
def get_security_config() -> SecurityConfig:
    return SecurityConfig()
