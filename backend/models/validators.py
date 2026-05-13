"""Reusable validation helpers for API models."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

import validators as url_validators

from config.security_config import get_security_config

_reserved_windows_names = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_sql_pattern = re.compile(r"(;\s*drop|union\s+select|--|/\*|\*/|exec\s|xp_)", re.I)
_xss_pattern = re.compile(r"(<script|javascript:|onerror=|onload=|onclick=)", re.I)
_allowed_filename_pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
_security_config = get_security_config()


def sanitize_string(value: str) -> str:
    """Normalize whitespace and strip control characters."""
    normalized = re.sub(r"\s+", " ", value.strip())
    return normalized


def truncate_string(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def validate_filename(value: str) -> str:
    if not value:
        raise ValueError("Filename cannot be empty")
    sanitized = value.strip().lower()
    if any(part in _reserved_windows_names for part in sanitized.split(".")):
        raise ValueError("Filename uses reserved device name")
    if ".." in value or value.startswith(("/", "\\")):
        raise ValueError("Filename contains invalid path traversal characters")
    if not _allowed_filename_pattern.match(value):
        raise ValueError("Filename contains unsupported characters")
    return value


def validate_file_hash(value: str) -> str:
    if not re.fullmatch(r"[a-fA-F0-9]{64}", value):
        raise ValueError("file_hash must be a SHA-256 hex string")
    return value


def validate_uuid(value: str) -> str:
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("Value must be a valid UUID") from exc
    return value


def validate_url(value: str) -> str:
    if not url_validators.url(value):
        raise ValueError("Invalid URL format")
    if not value.startswith(("http://", "https://")):
        raise ValueError("URL must use http or https scheme")
    return value


def validate_no_sql_injection(value: str) -> str:
    if value and _sql_pattern.search(value):
        raise ValueError("Input contains disallowed SQL patterns")
    return value


def validate_no_xss(value: str) -> str:
    if value and _xss_pattern.search(value):
        raise ValueError("Input contains potential XSS patterns")
    return value


def validate_manufacturer_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9 _-]{2,100}", value):
        raise ValueError("Manufacturer name must be 2-100 characters (letters, numbers, space, - or _)")
    return value


def validate_error_code(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", value):
        raise ValueError("Error code must be 1-50 characters (alphanumeric, ., _, -)")
    return value


def validate_password_strength(password: str) -> str:
    cfg = _security_config
    min_length = max(cfg.PASSWORD_MIN_LENGTH, 8)
    if len(password) < min_length:
        raise ValueError(f"Password must be at least {min_length} characters long")
    rules: list[tuple[bool, str, str]] = [
        (cfg.PASSWORD_REQUIRE_UPPERCASE, r"[A-Z]", "uppercase letter"),
        (cfg.PASSWORD_REQUIRE_LOWERCASE, r"[a-z]", "lowercase letter"),
        (cfg.PASSWORD_REQUIRE_NUMBER, r"[0-9]", "number"),
        (cfg.PASSWORD_REQUIRE_SPECIAL, r"[^A-Za-z0-9]", "special character"),
    ]
    missing: list[str] = []
    for required, pattern, label in rules:
        if required and not re.search(pattern, password):
            missing.append(label)
    if missing:
        raise ValueError("Password missing: " + ", ".join(missing))
    return password


def ensure_min_length(value: str, minimum: int, field_name: str) -> str:
    if len(value) < minimum:
        raise ValueError(f"{field_name} must be at least {minimum} characters")
    return value


def ensure_max_length(value: str, maximum: int, field_name: str) -> str:
    if len(value) > maximum:
        raise ValueError(f"{field_name} must be at most {maximum} characters")
    return value


def ensure_allowed_fields(value: Iterable[str], allowed: Iterable[str], field_name: str) -> list[str]:
    allowed_set = set(allowed)
    invalid = [item for item in value if item not in allowed_set]
    if invalid:
        raise ValueError(f"{field_name} contains invalid entries: {', '.join(invalid)}")
    return list(value)
