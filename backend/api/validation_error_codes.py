"""
Validation Error Codes and Response Helpers

This module provides standardized error codes and helper functions for creating
consistent validation error responses across the API. All validation errors
follow a common structure with error codes, detailed messages, and contextual
information to help clients understand and fix validation issues.

Error Response Structure:
    {
        "success": false,
        "error": "Validation Error",
        "detail": "Human-readable error message with guidance",
        "error_code": "INVALID_FILE_TYPE",
        "context": {
            "field": "file",
            "expected": [".pdf", ".docx"],
            "received": ".exe"
        }
    }

Usage:
    from backend.api.validation_error_codes import ValidationErrorCode, create_validation_error_response

    return create_validation_error_response(
        error_code=ValidationErrorCode.INVALID_FILE_TYPE,
        detail="File type '.exe' is not supported. Allowed types: .pdf, .docx",
        context={
            "filename": "document.exe",
            "extension": ".exe",
            "allowed_extensions": [".pdf", ".docx"]
        }
    )
"""

from enum import Enum
from typing import Any

from fastapi.responses import JSONResponse


class ValidationErrorCode(str, Enum):
    """
    Standardized validation error codes for API request validation.

    Each error code represents a specific validation failure type and is used
    to provide machine-readable error identification for API clients.
    """

    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    """
    Triggered when: File extension is not in the allowed types list

    Context fields:
        - filename: str - Name of the uploaded file
        - extension: str - File extension that was rejected
        - allowed_extensions: list[str] - List of allowed file extensions

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "File type '.exe' is not supported. Allowed types: .pdf, .docx. Please upload a file with one of the supported extensions.",
            "error_code": "INVALID_FILE_TYPE",
            "context": {
                "filename": "document.exe",
                "extension": ".exe",
                "allowed_extensions": [".pdf", ".docx"]
            }
        }
    """

    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    """
    Triggered when: Uploaded file exceeds maximum size limit

    Context fields:
        - filename: str - Name of the uploaded file
        - size_mb: float - Actual file size in megabytes
        - max_size_mb: int - Maximum allowed size in megabytes

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "File size 150.5MB exceeds the maximum allowed size of 100MB. Please reduce the file size or split into smaller files.",
            "error_code": "FILE_TOO_LARGE",
            "context": {
                "filename": "large_document.pdf",
                "size_mb": 150.5,
                "max_size_mb": 100
            }
        }
    """

    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    """
    Triggered when: Request body exceeds maximum size limit

    Context fields:
        - max_size_mb: int - Maximum allowed request size in megabytes
        - received_size_mb: float - Actual request size in megabytes

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Request size 120.3MB exceeds the maximum allowed size of 100MB. Please reduce the request size.",
            "error_code": "REQUEST_TOO_LARGE",
            "context": {
                "max_size_mb": 100,
                "received_size_mb": 120.3
            }
        }
    """

    SUSPICIOUS_INPUT = "SUSPICIOUS_INPUT"
    """
    Triggered when: Input contains SQL injection or XSS patterns

    Context fields:
        - field: str (optional) - Specific field containing suspicious input
        - suspicious_fields: list[str] (optional) - List of fields with suspicious content
        - suspicious_headers: list[str] (optional) - List of headers with suspicious content
        - pattern_matched: str - Type of pattern detected (e.g., "sql_injection", "xss")

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Input in field 'query' contains potentially malicious patterns. Please remove special characters or SQL/script syntax.",
            "error_code": "SUSPICIOUS_INPUT",
            "context": {
                "field": "query",
                "pattern_matched": "sql_injection"
            }
        }
    """

    INVALID_CONTENT_TYPE = "INVALID_CONTENT_TYPE"
    """
    Triggered when: Content-Type header is not supported

    Context fields:
        - received: str - Content-Type header value received
        - allowed: list[str] - List of allowed Content-Type values

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Content-Type 'text/plain' is not supported. Allowed types: application/json, multipart/form-data.",
            "error_code": "INVALID_CONTENT_TYPE",
            "context": {
                "received": "text/plain",
                "allowed": ["application/json", "multipart/form-data"]
            }
        }
    """

    INVALID_JSON = "INVALID_JSON"
    """
    Triggered when: Request body contains malformed JSON

    Context fields:
        - parse_error: str - JSON parsing error message

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Request body contains invalid JSON. Please check your JSON syntax.",
            "error_code": "INVALID_JSON",
            "context": {
                "parse_error": "Expecting ',' delimiter: line 5 column 10 (char 89)"
            }
        }
    """

    INVALID_FILENAME = "INVALID_FILENAME"
    """
    Triggered when: Filename is missing, contains path traversal, or invalid characters

    Context fields:
        - filename: str (optional) - The invalid filename
        - reason: str - Reason for rejection (e.g., "filename_required", "path_traversal_detected")

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Filename '../../../etc/passwd' contains path traversal sequences. Please use a simple filename without directory paths.",
            "error_code": "INVALID_FILENAME",
            "context": {
                "filename": "../../../etc/passwd",
                "reason": "path_traversal_detected"
            }
        }
    """

    MISMATCHED_FILE_TYPE = "MISMATCHED_FILE_TYPE"
    """
    Triggered when: Declared Content-Type doesn't match detected MIME type

    Context fields:
        - filename: str - Name of the uploaded file
        - declared_type: str - Content-Type declared in request
        - detected_type: str - MIME type detected from file content

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "File 'document.pdf' has mismatched type. Declared as 'application/pdf' but detected as 'text/plain'. Please ensure file type matches content.",
            "error_code": "MISMATCHED_FILE_TYPE",
            "context": {
                "filename": "document.pdf",
                "declared_type": "application/pdf",
                "detected_type": "text/plain"
            }
        }
    """

    FIELD_VALIDATION_ERROR = "FIELD_VALIDATION_ERROR"
    """
    Triggered when: Pydantic field validation fails

    Context fields:
        - fields: list[dict] - Array of field error objects, each containing:
            - field: str - Field path (e.g., "body.email")
            - type: str - Error type (e.g., "value_error.email")
            - message: str - Error message
            - constraints: dict (optional) - Validation constraints (min/max length, pattern, etc.)

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Request validation failed for 2 field(s). Please check the field errors in context.",
            "error_code": "FIELD_VALIDATION_ERROR",
            "context": {
                "fields": [
                    {
                        "field": "body.email",
                        "type": "value_error.email",
                        "message": "value is not a valid email address",
                        "constraints": {"pattern": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"}
                    },
                    {
                        "field": "body.age",
                        "type": "value_error.number.not_ge",
                        "message": "ensure this value is greater than or equal to 0",
                        "constraints": {"ge": 0}
                    }
                ]
            }
        }
    """

    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    """
    Triggered when: Required field is not provided in request

    Context fields:
        - field: str - Name of the missing required field
        - location: str - Where the field was expected (e.g., "body", "query", "header")

    Example response:
        {
            "success": false,
            "error": "Validation Error",
            "detail": "Required field 'email' is missing from request body. Please provide this field.",
            "error_code": "MISSING_REQUIRED_FIELD",
            "context": {
                "field": "email",
                "location": "body"
            }
        }
    """


def format_field_context(
    field: str, expected: Any, received: Any, constraints: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Format field-level validation context for error responses.

    Args:
        field: Name of the field that failed validation
        expected: Expected value or type
        received: Actual value received
        constraints: Optional validation constraints (min/max, pattern, etc.)

    Returns:
        Dictionary containing formatted field context

    Example:
        >>> format_field_context("age", "integer >= 0", -5, {"ge": 0})
        {
            "field": "age",
            "expected": "integer >= 0",
            "received": -5,
            "constraints": {"ge": 0}
        }
    """
    context = {"field": field, "expected": expected, "received": received}

    if constraints:
        context["constraints"] = constraints

    return context


def create_validation_error_response(
    error_code: ValidationErrorCode, detail: str, context: dict[str, Any] | None = None, status_code: int = 400
) -> JSONResponse:
    """
    Create a standardized validation error response.

    This function generates a consistent error response structure that includes
    a machine-readable error code, human-readable detail message, and optional
    contextual information to help clients understand and fix the validation error.

    Args:
        error_code: Validation error code from ValidationErrorCode enum
        detail: Human-readable error message with actionable guidance
        context: Optional dictionary containing validation context (field names,
                expected values, constraints, etc.)
        status_code: HTTP status code (default: 400)

    Returns:
        JSONResponse with standardized error structure

    Example:
        >>> create_validation_error_response(
        ...     error_code=ValidationErrorCode.INVALID_FILE_TYPE,
        ...     detail="File type '.exe' is not supported. Allowed types: .pdf, .docx",
        ...     context={
        ...         "filename": "document.exe",
        ...         "extension": ".exe",
        ...         "allowed_extensions": [".pdf", ".docx"]
        ...     }
        ... )
        JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Validation Error",
                "detail": "File type '.exe' is not supported...",
                "error_code": "INVALID_FILE_TYPE",
                "context": {...}
            }
        )
    """
    response_content = {"success": False, "error": "Validation Error", "detail": detail, "error_code": error_code.value}

    if context is not None:
        response_content["context"] = context

    return JSONResponse(status_code=status_code, content=response_content)
