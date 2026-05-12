"""Request validation middleware for size, content-type, and upload checks."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any

import magic
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.validation_error_codes import ValidationErrorCode, create_validation_error_response
from config.security_config import get_security_config

logger = logging.getLogger("krai.request_validation")
# Keep SQLi-focused signatures and avoid wildcard MIME false-positives
# (e.g. Accept: */* from Docker health checks).
_sql_pattern = re.compile(r"(;\s*drop|union\s+select|--|exec\s|xp_)", re.I)
_xss_pattern = re.compile(r"(<script|javascript:|onerror=|onload=|onclick=)", re.I)

ALLOWED_CONTENT_TYPES = {
    "application/json",
    "multipart/form-data",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return sanitized[:255]


def _is_disallowed_path(name: str) -> bool:
    lowered = name.lower()
    return ".." in lowered or lowered.startswith(("/", "\\"))


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates request size, headers, and uploads."""

    def __init__(self, app):
        super().__init__(app)
        self.config = get_security_config()
        self.max_request_bytes = self.config.MAX_REQUEST_SIZE_MB * 1024 * 1024
        self.max_file_bytes = self.config.MAX_FILE_SIZE_MB * 1024 * 1024
        self.allowed_extensions = set(self.config.ALLOWED_FILE_TYPES)
        self.enabled = self.config.REQUEST_VALIDATION_ENABLED

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)

        if _is_whitelisted_content_type(request.headers.get("content-type")):
            pass

        enforce_size = self._check_content_length(request)
        if enforce_size is not None:
            return enforce_size

        enforce_blacklist = self._check_blacklist(request)
        if enforce_blacklist is not None:
            return enforce_blacklist

        if request.method in {"POST", "PUT", "PATCH"}:
            validation_response = await self._validate_body(request)
            if validation_response is not None:
                return validation_response

        return await call_next(request)

    def _check_content_length(self, request: Request) -> Response | None:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            size = int(content_length)
            if size > self.max_request_bytes:
                logger.warning("Request too large from %s: %s bytes", request.client, size)
                size_mb = size / (1024 * 1024)
                return create_validation_error_response(
                    error_code=ValidationErrorCode.REQUEST_TOO_LARGE,
                    detail=f"Request size {size_mb:.2f}MB exceeds the maximum allowed size of {self.config.MAX_REQUEST_SIZE_MB}MB. Please reduce the request size.",
                    context={"max_size_mb": self.config.MAX_REQUEST_SIZE_MB, "received_size_mb": round(size_mb, 2)},
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
        return None

    # Headers whose values legitimately contain patterns like "--" (e.g. multipart boundary)
    _SAFE_HEADERS = frozenset({"content-type", "accept", "accept-encoding", "accept-language", "cookie"})

    def _check_blacklist(self, request: Request) -> Response | None:
        suspicious_headers = [
            header
            for header, value in request.headers.items()
            if header.lower() not in self._SAFE_HEADERS and _sql_pattern.search(value or "")
        ]
        if suspicious_headers:
            logger.warning("Suspicious headers detected from %s", request.client)
            return create_validation_error_response(
                error_code=ValidationErrorCode.SUSPICIOUS_INPUT,
                detail=f"Request headers contain potentially malicious patterns. Please remove special characters or SQL/script syntax from headers: {', '.join(suspicious_headers)}.",
                context={"suspicious_headers": suspicious_headers, "pattern_matched": "sql_injection"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None

    async def _validate_body(self, request: Request) -> Response | None:
        content_type = request.headers.get("content-type", "").lower()
        if "multipart/form-data" in content_type:
            # Multipart parsing consumes the request stream. Upload endpoints
            # already perform file-type/size/PDF validation in the processor.
            return None
        if "application/json" in content_type:
            return await self._validate_json(request)
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            allowed_types = ", ".join(ALLOWED_CONTENT_TYPES)
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_CONTENT_TYPE,
                detail=f"Content-Type '{content_type}' is not supported. Allowed types: {allowed_types}. Please use one of the supported content types.",
                context={"received": content_type, "allowed": list(ALLOWED_CONTENT_TYPES)},
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        return None

    async def _validate_json(self, request: Request) -> Response | None:
        body = await request.body()
        if len(body) > self.max_request_bytes:
            size_mb = len(body) / (1024 * 1024)
            return create_validation_error_response(
                error_code=ValidationErrorCode.REQUEST_TOO_LARGE,
                detail=f"JSON payload size {size_mb:.2f}MB exceeds the maximum allowed size of {self.config.MAX_REQUEST_SIZE_MB}MB. Please reduce the payload size.",
                context={"max_size_mb": self.config.MAX_REQUEST_SIZE_MB, "received_size_mb": round(size_mb, 2)},
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_JSON,
                detail="Request body contains invalid JSON. Please check your JSON syntax and ensure it is properly formatted.",
                context={"parse_error": str(e)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        suspicious = self._scan_payload(data)
        if suspicious:
            fields_str = ", ".join(suspicious)
            return create_validation_error_response(
                error_code=ValidationErrorCode.SUSPICIOUS_INPUT,
                detail=f"Input in fields [{fields_str}] contains potentially malicious patterns. Please remove special characters or SQL/script syntax.",
                context={"suspicious_fields": suspicious, "pattern_matched": "sql_injection_or_xss"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        request._body = body  # type: ignore[attr-defined]
        return None

    async def _validate_multipart(self, request: Request) -> Response | None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename"):
                response = self._validate_upload(value.filename, value.content_type, await value.read())
                if response:
                    return response
                value.file.seek(0)
            elif isinstance(value, str):
                if _sql_pattern.search(value) or _xss_pattern.search(value):
                    return create_validation_error_response(
                        error_code=ValidationErrorCode.SUSPICIOUS_INPUT,
                        detail=f"Input in field '{key}' contains potentially malicious patterns. Please remove special characters or SQL/script syntax.",
                        context={"field": key, "pattern_matched": "sql_injection_or_xss"},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
        return None

    def _validate_upload(self, filename: str, content_type: str, data: bytes) -> Response | None:
        if not filename:
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_FILENAME,
                detail="Filename is required for file uploads. Please provide a valid filename.",
                context={"reason": "filename_required"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if _is_disallowed_path(filename):
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_FILENAME,
                detail=f"Filename '{filename}' contains path traversal sequences or invalid characters. Please use a simple filename without directory paths.",
                context={"filename": filename, "reason": "path_traversal_detected"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        sanitized = _sanitize_filename(filename)
        ext = f".{sanitized.split('.')[-1].lower()}" if "." in sanitized else ""
        if ext not in self.allowed_extensions:
            allowed_str = ", ".join(sorted(self.allowed_extensions))
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_FILE_TYPE,
                detail=f"File type '{ext}' is not supported. Allowed types: {allowed_str}. Please upload a file with one of the supported extensions.",
                context={"filename": filename, "extension": ext, "allowed_extensions": list(self.allowed_extensions)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if len(data) > self.max_file_bytes:
            size_mb = len(data) / (1024 * 1024)
            return create_validation_error_response(
                error_code=ValidationErrorCode.FILE_TOO_LARGE,
                detail=f"File size {size_mb:.2f}MB exceeds the maximum allowed size of {self.config.MAX_FILE_SIZE_MB}MB. Please reduce the file size or split into smaller files.",
                context={
                    "filename": filename,
                    "size_mb": round(size_mb, 2),
                    "max_size_mb": self.config.MAX_FILE_SIZE_MB,
                },
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        mime = magic.from_buffer(data[:2048], mime=True)
        if not mime:
            return create_validation_error_response(
                error_code=ValidationErrorCode.INVALID_FILE_TYPE,
                detail=f"Unable to detect file type for '{filename}'. The file may be corrupted or in an unsupported format.",
                context={"filename": filename, "reason": "mime_detection_failed"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if mime != content_type:
            return create_validation_error_response(
                error_code=ValidationErrorCode.MISMATCHED_FILE_TYPE,
                detail=f"File '{filename}' has mismatched type. Declared as '{content_type}' but detected as '{mime}'. Please ensure the file type matches its content.",
                context={"filename": filename, "declared_type": content_type, "detected_type": mime},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _scan_payload(self, data: Any, path: str = "") -> Iterable[str]:
        suspicious_fields = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                suspicious_fields.extend(self._scan_payload(value, new_path))
        elif isinstance(data, list):
            for idx, value in enumerate(data):
                new_path = f"{path}[{idx}]"
                suspicious_fields.extend(self._scan_payload(value, new_path))
        elif isinstance(data, str) and (_sql_pattern.search(data) or _xss_pattern.search(data)):
            suspicious_fields.append(path)
        return suspicious_fields


def _is_whitelisted_content_type(content_type: str | None) -> bool:
    return content_type is None
