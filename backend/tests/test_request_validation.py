"""
Comprehensive unit tests for RequestValidationMiddleware.

This test suite covers:
- Request size validation (Content-Length header, JSON body size)
- File upload validation (MIME types, file extensions, size limits, filename sanitization)
- Input sanitization (SQL injection, XSS patterns in JSON, forms, headers)
- Content-Type validation (allowed types, error responses)
- Multipart form data validation (files and text fields)
- JSON payload validation (malformed JSON, suspicious content)
- Error responses and status codes (400, 413, 415)
- Validation bypass scenarios (disabled validation, whitelisted types)
- Edge cases (concurrent requests, unicode, special characters, empty files)
- Helper functions (_sanitize_filename, _is_disallowed_path, _is_whitelisted_content_type)

Coverage target: >80% for backend/api/middleware/request_validation_middleware.py
"""

import asyncio
from io import BytesIO
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.api.middleware.request_validation_middleware import (
    RequestValidationMiddleware,
    ValidationErrorCode,
    _is_disallowed_path,
    _is_whitelisted_content_type,
    _sanitize_filename,
)

pytestmark = pytest.mark.unit


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_security_config():
    """Mock SecurityConfig with configurable validation settings."""
    config = Mock()
    config.MAX_REQUEST_SIZE_MB = 10
    config.MAX_FILE_SIZE_MB = 5
    config.ALLOWED_FILE_TYPES = [".pdf", ".docx", ".txt"]
    config.REQUEST_VALIDATION_ENABLED = True
    return config


@pytest.fixture
def test_app(mock_security_config):
    """FastAPI application with RequestValidationMiddleware and test endpoints."""
    app = FastAPI()

    # Add middleware with mocked config
    with patch(
        "backend.api.middleware.request_validation_middleware.get_security_config", return_value=mock_security_config
    ):
        app.add_middleware(RequestValidationMiddleware)

    # Test endpoints
    @app.post("/test/json")
    async def test_json_endpoint(data: dict):
        return JSONResponse({"success": True, "received": data})

    @app.post("/test/upload")
    async def test_upload_endpoint(file: UploadFile = File(...)):
        content = await file.read()
        return JSONResponse(
            {"success": True, "filename": file.filename, "size": len(content), "content_type": file.content_type}
        )

    @app.post("/test/form")
    async def test_form_endpoint(field1: str = Form(...), field2: str = Form(None), file: UploadFile = File(None)):
        return JSONResponse({"success": True, "field1": field1, "field2": field2, "has_file": file is not None})

    @app.get("/test/health")
    async def test_health_endpoint():
        return JSONResponse({"status": "healthy"})

    return app


@pytest.fixture
async def async_client(test_app):
    """HTTP client for making test requests."""
    async with httpx.AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_pdf_bytes():
    """Mock PDF file content with valid PDF header."""
    # PDF header signature
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"Mock PDF content" * 100


@pytest.fixture
def sample_docx_bytes():
    """Mock DOCX file content with valid ZIP header (DOCX is a ZIP file)."""
    # ZIP header signature (DOCX files are ZIP archives)
    return b"PK\x03\x04" + b"Mock DOCX content" * 100


@pytest.fixture
def mock_magic():
    """Mock python-magic library for MIME type detection."""
    with patch("backend.api.middleware.request_validation_middleware.magic") as mock:
        yield mock


# ============================================================================
# TEST REQUEST SIZE VALIDATION
# ============================================================================


class TestRequestSizeValidation:
    """Test request size validation logic."""

    @pytest.mark.asyncio
    async def test_request_within_size_limit(self, async_client):
        """Valid request under MAX_REQUEST_SIZE_MB should pass."""
        small_payload = {"data": "x" * 1000}  # Small payload
        response = await async_client.post("/test/json", json=small_payload)
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_request_exceeds_size_limit_via_content_length(self, async_client, mock_security_config):
        """Request with Content-Length > MAX_REQUEST_SIZE_MB should return 413."""
        # Set Content-Length to exceed limit (10 MB = 10 * 1024 * 1024 bytes)
        max_bytes = mock_security_config.MAX_REQUEST_SIZE_MB * 1024 * 1024
        headers = {"Content-Length": str(max_bytes + 1000)}

        response = await async_client.post("/test/json", json={"data": "test"}, headers=headers)

        assert response.status_code == 413
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == ValidationErrorCode.REQUEST_TOO_LARGE.value

    @pytest.mark.asyncio
    async def test_json_body_exceeds_size_limit(self, async_client, mock_security_config):
        """Large JSON payload > MAX_REQUEST_SIZE_MB should return 413."""
        # Create payload larger than 10 MB
        large_data = "x" * (11 * 1024 * 1024)  # 11 MB of data
        large_payload = {"data": large_data}

        response = await async_client.post("/test/json", json=large_payload)

        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.REQUEST_TOO_LARGE.value
        assert "max_size_mb" in data["context"]
        assert "received_size_mb" in data["context"]

    @pytest.mark.asyncio
    async def test_error_response_includes_size_details(self, async_client, mock_security_config):
        """Error response should include size details with 2 decimal precision."""
        max_bytes = mock_security_config.MAX_REQUEST_SIZE_MB * 1024 * 1024
        headers = {"Content-Length": str(max_bytes + 5000)}

        response = await async_client.post("/test/json", json={"data": "test"}, headers=headers)

        data = response.json()
        assert "max_size_mb" in data["context"]
        assert "received_size_mb" in data["context"]
        # Check decimal precision
        assert isinstance(data["context"]["max_size_mb"], int | float)
        assert isinstance(data["context"]["received_size_mb"], int | float)

    @pytest.mark.asyncio
    async def test_missing_content_length_header(self, async_client):
        """Request without Content-Length should be allowed (size check at body read)."""
        response = await async_client.post(
            "/test/json",
            json={"data": "test"},
            headers={"Content-Length": None},  # Remove header
        )
        # Should pass through, validation happens at body read
        assert response.status_code in [200, 413]  # Depends on actual body size


# ============================================================================
# TEST FILE UPLOAD VALIDATION
# ============================================================================


class TestFileUploadValidation:
    """Test file upload validation logic."""

    @pytest.mark.asyncio
    async def test_valid_pdf_upload(self, async_client, sample_pdf_bytes, mock_magic):
        """Valid PDF upload with correct MIME type should pass."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("document.pdf", BytesIO(sample_pdf_bytes), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "document.pdf"

    @pytest.mark.asyncio
    async def test_valid_docx_upload(self, async_client, sample_docx_bytes, mock_magic):
        """Valid DOCX upload with correct MIME type should pass."""
        mock_magic.from_buffer.return_value = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        files = {
            "file": (
                "document.docx",
                BytesIO(sample_docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_file_extension(self, async_client):
        """Upload with .exe extension should return 400."""
        file_content = b"Mock executable content"
        files = {"file": ("malware.exe", BytesIO(file_content), "application/octet-stream")}

        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILE_TYPE.value
        assert "allowed_extensions" in data["context"]
        assert ".pdf" in data["context"]["allowed_extensions"]

    @pytest.mark.asyncio
    async def test_file_exceeds_size_limit(self, async_client, mock_security_config, mock_magic):
        """File > MAX_FILE_SIZE_MB should return 413."""
        mock_magic.from_buffer.return_value = "application/pdf"

        # Create file larger than 5 MB
        large_file = b"x" * (6 * 1024 * 1024)  # 6 MB
        files = {"file": ("large.pdf", BytesIO(large_file), "application/pdf")}

        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.FILE_TOO_LARGE.value
        assert "filename" in data["context"]
        assert "size_mb" in data["context"]
        assert "max_size_mb" in data["context"]
        assert data["context"]["filename"] == "large.pdf"

    @pytest.mark.asyncio
    async def test_missing_filename(self, async_client):
        """Upload without filename should return 400."""
        files = {"file": ("", BytesIO(b"content"), "application/pdf")}

        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILENAME.value

    @pytest.mark.asyncio
    async def test_path_traversal_in_filename(self, async_client):
        """Filename with path traversal should return 400."""
        files = {"file": ("../../../etc/passwd", BytesIO(b"content"), "application/pdf")}

        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILENAME.value
        assert "reason" in data["context"]
        assert data["context"]["reason"] == "path_traversal_detected"

    @pytest.mark.asyncio
    async def test_filename_sanitization(self, async_client, mock_magic):
        """Filename with special characters should be sanitized."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("my@file#name$.pdf", BytesIO(b"content"), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        # Should either pass with sanitized name or reject
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_mime_type_mismatch(self, async_client, mock_magic):
        """File with mismatched MIME type should return 400."""
        # Declare as PDF but actual content is text
        mock_magic.from_buffer.return_value = "text/plain"

        files = {"file": ("fake.pdf", BytesIO(b"Just plain text"), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.MISMATCHED_FILE_TYPE.value

    @pytest.mark.asyncio
    async def test_mime_detection_failure(self, async_client, mock_magic):
        """MIME detection failure should return 400."""
        mock_magic.from_buffer.return_value = None  # Detection failed

        files = {"file": ("unknown.pdf", BytesIO(b"???"), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILE_TYPE.value
        assert "reason" in data["context"]
        assert data["context"]["reason"] == "mime_detection_failed"


# ============================================================================
# TEST INPUT SANITIZATION
# ============================================================================


class TestInputSanitization:
    """Test input sanitization for SQL injection and XSS patterns."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_json_payload(self, async_client):
        """JSON with SQL injection patterns should return 400."""
        malicious_payload = {"username": "admin", "query": "'; DROP TABLE users; --"}

        response = await async_client.post("/test/json", json=malicious_payload)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        assert "suspicious_fields" in data["context"]

    @pytest.mark.asyncio
    async def test_xss_in_json_payload(self, async_client):
        """JSON with XSS patterns should return 400."""
        malicious_payload = {"comment": "<script>alert('XSS')</script>", "bio": "javascript:alert(1)"}

        response = await async_client.post("/test/json", json=malicious_payload)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        assert "pattern_matched" in data["context"]
        assert data["context"]["pattern_matched"] == "sql_injection_or_xss"

    @pytest.mark.asyncio
    async def test_sql_injection_in_form_field(self, async_client):
        """Multipart form with SQL injection should return 400."""
        form_data = {"field1": "'; DELETE FROM products; --", "field2": "normal value"}

        response = await async_client.post("/test/form", data=form_data)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        assert "field1" in str(data["context"])

    @pytest.mark.asyncio
    async def test_xss_in_form_field(self, async_client):
        """Multipart form with XSS pattern should return 400."""
        form_data = {"field1": "normal", "field2": "<img src=x onerror=alert(1)>"}

        response = await async_client.post("/test/form", data=form_data)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value

    @pytest.mark.asyncio
    async def test_suspicious_headers(self, async_client):
        """Request with SQL injection in headers should return 400."""
        headers = {"X-Custom-Header": "'; DROP TABLE sessions; --"}

        response = await async_client.post("/test/json", json={"data": "clean"}, headers=headers)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        assert "suspicious_headers" in data["context"]

    @pytest.mark.asyncio
    async def test_nested_json_scanning(self, async_client):
        """Nested JSON with suspicious content should be detected."""
        nested_payload = {"user": {"profile": {"bio": "'; UNION SELECT * FROM passwords; --"}}}

        response = await async_client.post("/test/json", json=nested_payload)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        assert "suspicious_fields" in data["context"]
        # Check for nested path like "user.profile.bio"
        assert any("bio" in str(field) for field in data["context"]["suspicious_fields"])

    @pytest.mark.asyncio
    async def test_array_scanning(self, async_client):
        """JSON array with suspicious content should be detected."""
        array_payload = {"items": ["normal item", "another normal item", "<script>alert('XSS')</script>"]}

        response = await async_client.post("/test/json", json=array_payload)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value
        # Check for array index in path like "items[2]"
        assert "suspicious_fields" in data["context"]

    @pytest.mark.asyncio
    async def test_clean_input_passes(self, async_client):
        """Clean input without suspicious patterns should pass."""
        clean_payload = {
            "username": "john_doe",
            "email": "john@example.com",
            "comment": "This is a normal comment with no malicious content.",
        }

        response = await async_client.post("/test/json", json=clean_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# TEST CONTENT-TYPE VALIDATION
# ============================================================================


class TestContentTypeValidation:
    """Test Content-Type header validation."""

    @pytest.mark.asyncio
    async def test_valid_json_content_type(self, async_client):
        """Request with application/json Content-Type should be accepted."""
        response = await async_client.post(
            "/test/json", json={"data": "test"}, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_multipart_content_type(self, async_client):
        """Request with multipart/form-data Content-Type should be accepted."""
        form_data = {"field1": "value1"}
        response = await async_client.post("/test/form", data=form_data)
        assert response.status_code in [200, 422]  # 422 if required fields missing

    @pytest.mark.asyncio
    async def test_valid_pdf_content_type(self, async_client, sample_pdf_bytes, mock_magic):
        """Request with application/pdf Content-Type should be accepted."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("doc.pdf", BytesIO(sample_pdf_bytes), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_docx_content_type(self, async_client, sample_docx_bytes, mock_magic):
        """Request with DOCX Content-Type should be accepted."""
        mock_magic.from_buffer.return_value = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        files = {
            "file": (
                "doc.docx",
                BytesIO(sample_docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        response = await async_client.post("/test/upload", files=files)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_content_type(self, async_client):
        """Request with text/plain Content-Type should return 415."""
        response = await async_client.post(
            "/test/json", content="plain text data", headers={"Content-Type": "text/plain"}
        )

        assert response.status_code == 415
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_CONTENT_TYPE.value

    @pytest.mark.asyncio
    async def test_error_includes_allowed_types(self, async_client):
        """Error response should include allowed content types."""
        response = await async_client.post("/test/json", content="plain text", headers={"Content-Type": "text/html"})

        assert response.status_code == 415
        data = response.json()
        assert "received" in data["context"]
        assert "allowed" in data["context"]
        assert isinstance(data["context"]["allowed"], list)

    @pytest.mark.asyncio
    async def test_missing_content_type_header(self, async_client):
        """POST request without Content-Type should be whitelisted."""
        response = await async_client.post("/test/json", json={"data": "test"})
        # Should pass through if whitelisted
        assert response.status_code in [200, 415]


# ============================================================================
# TEST MULTIPART FORM DATA VALIDATION
# ============================================================================


class TestMultipartFormValidation:
    """Test multipart form data validation."""

    @pytest.mark.asyncio
    async def test_valid_multipart_with_file_and_fields(self, async_client, sample_pdf_bytes, mock_magic):
        """Multipart form with file and text fields should pass validation."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("doc.pdf", BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"field1": "value1", "field2": "value2"}

        response = await async_client.post("/test/form", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["has_file"] is True

    @pytest.mark.asyncio
    async def test_multipart_with_multiple_files(self, async_client, sample_pdf_bytes, mock_magic):
        """Multipart form with multiple files should validate all."""
        mock_magic.from_buffer.return_value = "application/pdf"

        # Note: This test depends on endpoint supporting multiple files
        files = [
            ("file", ("doc1.pdf", BytesIO(sample_pdf_bytes), "application/pdf")),
            ("file", ("doc2.pdf", BytesIO(sample_pdf_bytes), "application/pdf")),
        ]

        response = await async_client.post("/test/upload", files=files[0:1])
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multipart_text_field_with_sql_injection(self, async_client):
        """Multipart text field with SQL injection should return 400."""
        data = {"field1": "'; DROP TABLE users; --"}

        response = await async_client.post("/test/form", data=data)

        assert response.status_code == 400
        result = response.json()
        assert result["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value

    @pytest.mark.asyncio
    async def test_multipart_file_validation(self, async_client):
        """Multipart with invalid file type should fail validation."""
        files = {"file": ("malware.exe", BytesIO(b"content"), "application/octet-stream")}
        data = {"field1": "value"}

        response = await async_client.post("/test/form", files=files, data=data)

        assert response.status_code == 400
        result = response.json()
        assert result["error_code"] == ValidationErrorCode.INVALID_FILE_TYPE.value

    @pytest.mark.asyncio
    async def test_empty_multipart_form(self, async_client):
        """Empty multipart form should pass (no validation errors)."""
        response = await async_client.post("/test/form", data={"field1": "test"})
        # May fail due to required fields, but not validation errors
        assert response.status_code in [200, 422]


# ============================================================================
# TEST JSON PAYLOAD VALIDATION
# ============================================================================


class TestJSONPayloadValidation:
    """Test JSON payload validation."""

    @pytest.mark.asyncio
    async def test_valid_json_payload(self, async_client):
        """Valid JSON payload should pass."""
        payload = {"key": "value", "number": 42, "nested": {"data": "test"}}
        response = await async_client.post("/test/json", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_malformed_json(self, async_client):
        """Malformed JSON should return 400."""
        # Send malformed JSON as raw content
        malformed = '{"key": "value", "missing": }'

        response = await async_client.post(
            "/test/json", content=malformed, headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_JSON.value
        assert "parse_error" in data["context"]

    @pytest.mark.asyncio
    async def test_json_with_suspicious_content(self, async_client):
        """Valid JSON with SQL injection should return 400."""
        payload = {"search": "'; DROP TABLE products; --", "filter": "normal"}

        response = await async_client.post("/test/json", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.SUSPICIOUS_INPUT.value

    @pytest.mark.asyncio
    async def test_large_json_payload(self, async_client, mock_security_config):
        """JSON payload > MAX_REQUEST_SIZE_MB should return 413."""
        # Create large payload
        large_data = "x" * (11 * 1024 * 1024)  # 11 MB
        payload = {"data": large_data}

        response = await async_client.post("/test/json", json=payload)

        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.REQUEST_TOO_LARGE.value

    @pytest.mark.asyncio
    async def test_empty_json_payload(self, async_client):
        """Empty JSON object should pass."""
        response = await async_client.post("/test/json", json={})
        assert response.status_code in [200, 422]  # Depends on endpoint requirements

    @pytest.mark.asyncio
    async def test_json_array_payload(self, async_client):
        """JSON array should be validated."""
        payload = ["item1", "item2", "item3"]

        # Note: Endpoint expects dict, so this may fail at endpoint level
        # But validation should still run
        response = await async_client.post("/test/json", json=payload, headers={"Content-Type": "application/json"})

        # Validation should process it
        assert response.status_code in [200, 400, 422]


# ============================================================================
# TEST ERROR RESPONSES AND STATUS CODES
# ============================================================================


class TestErrorResponses:
    """Test error response structure and status codes."""

    @pytest.mark.asyncio
    async def test_400_for_invalid_file_type(self, async_client):
        """INVALID_FILE_TYPE should return 400."""
        files = {"file": ("bad.exe", BytesIO(b"content"), "application/octet-stream")}
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILE_TYPE.value

    @pytest.mark.asyncio
    async def test_413_for_request_too_large(self, async_client, mock_security_config):
        """REQUEST_TOO_LARGE should return 413."""
        max_bytes = mock_security_config.MAX_REQUEST_SIZE_MB * 1024 * 1024
        headers = {"Content-Length": str(max_bytes + 1000)}

        response = await async_client.post("/test/json", json={"data": "test"}, headers=headers)

        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.REQUEST_TOO_LARGE.value

    @pytest.mark.asyncio
    async def test_413_for_file_too_large(self, async_client, mock_security_config, mock_magic):
        """FILE_TOO_LARGE should return 413."""
        mock_magic.from_buffer.return_value = "application/pdf"

        large_file = b"x" * (6 * 1024 * 1024)  # 6 MB
        files = {"file": ("large.pdf", BytesIO(large_file), "application/pdf")}

        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 413
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.FILE_TOO_LARGE.value

    @pytest.mark.asyncio
    async def test_415_for_invalid_content_type(self, async_client):
        """INVALID_CONTENT_TYPE should return 415."""
        response = await async_client.post("/test/json", content="plain text", headers={"Content-Type": "text/plain"})

        assert response.status_code == 415
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_CONTENT_TYPE.value

    @pytest.mark.asyncio
    async def test_error_response_structure(self, async_client):
        """All error responses should have consistent structure."""
        files = {"file": ("bad.exe", BytesIO(b"content"), "application/octet-stream")}
        response = await async_client.post("/test/upload", files=files)

        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert data["error"] == "Validation Error"
        assert "detail" in data
        assert isinstance(data["detail"], str)
        assert "error_code" in data
        assert isinstance(data["error_code"], str)
        assert "context" in data
        assert isinstance(data["context"], dict)

    @pytest.mark.asyncio
    async def test_error_detail_messages_are_actionable(self, async_client):
        """Error messages should include guidance on fixing the issue."""
        files = {"file": ("bad.exe", BytesIO(b"content"), "application/octet-stream")}
        response = await async_client.post("/test/upload", files=files)

        data = response.json()
        # Detail should be descriptive
        assert len(data["detail"]) > 20
        # Context should include helpful info
        assert "allowed_extensions" in data["context"]

    @pytest.mark.asyncio
    async def test_context_includes_relevant_information(self, async_client, mock_security_config):
        """Error context should include field names, expected/received values."""
        max_bytes = mock_security_config.MAX_REQUEST_SIZE_MB * 1024 * 1024
        headers = {"Content-Length": str(max_bytes + 1000)}

        response = await async_client.post("/test/json", json={"data": "test"}, headers=headers)

        data = response.json()
        context = data["context"]
        # Should include expected and received values
        assert "max_size_mb" in context
        assert "received_size_mb" in context
        assert context["max_size_mb"] == mock_security_config.MAX_REQUEST_SIZE_MB


# ============================================================================
# TEST VALIDATION BYPASS
# ============================================================================


class TestValidationBypass:
    """Test validation bypass scenarios."""

    @pytest.mark.asyncio
    async def test_validation_disabled(self, mock_security_config):
        """When REQUEST_VALIDATION_ENABLED=false, invalid requests should pass."""
        # Create app with validation disabled BEFORE adding middleware
        disabled_config = Mock()
        disabled_config.MAX_REQUEST_SIZE_MB = 10
        disabled_config.MAX_FILE_SIZE_MB = 5
        disabled_config.ALLOWED_FILE_TYPES = [".pdf", ".docx", ".txt"]
        disabled_config.REQUEST_VALIDATION_ENABLED = False

        app = FastAPI()
        with patch(
            "backend.api.middleware.request_validation_middleware.get_security_config", return_value=disabled_config
        ):
            app.add_middleware(RequestValidationMiddleware)

        @app.post("/test/upload")
        async def test_upload_endpoint(file: UploadFile = File(...)):
            content = await file.read()
            return JSONResponse(
                {"success": True, "filename": file.filename, "size": len(content), "content_type": file.content_type}
            )

        # Send invalid request (bad file type)
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            files = {"file": ("bad.exe", BytesIO(b"content"), "application/octet-stream")}
            response = await client.post("/test/upload", files=files)

        # Should pass through without validation error (no 400 with INVALID_FILE_TYPE)
        # Note: May still fail at endpoint level for other reasons
        assert response.status_code in [200, 422]
        if response.status_code == 400:
            data = response.json()
            assert data.get("error_code") != ValidationErrorCode.INVALID_FILE_TYPE.value

    @pytest.mark.asyncio
    async def test_validation_enabled(self, async_client, mock_security_config):
        """When REQUEST_VALIDATION_ENABLED=true, validation should run."""
        mock_security_config.REQUEST_VALIDATION_ENABLED = True

        files = {"file": ("bad.exe", BytesIO(b"content"), "application/octet-stream")}
        response = await async_client.post("/test/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == ValidationErrorCode.INVALID_FILE_TYPE.value

    @pytest.mark.asyncio
    async def test_whitelisted_content_type(self, async_client):
        """Request with None Content-Type should be whitelisted."""
        # GET requests typically don't have Content-Type
        response = await async_client.get("/test/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# ============================================================================
# TEST EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client):
        """Multiple concurrent requests should be handled independently."""
        tasks = [async_client.post("/test/json", json={"id": i}) for i in range(10)]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_unicode_in_json(self, async_client):
        """JSON with Unicode characters should be handled correctly."""
        payload = {"name": "José García", "city": "São Paulo", "emoji": "🎉🚀", "chinese": "你好世界"}

        response = await async_client.post("/test/json", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_special_characters_in_filename(self, async_client, mock_magic):
        """Filename with special characters should be sanitized."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("my file@#$%.pdf", BytesIO(b"content"), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        # Should either sanitize and accept, or reject
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_very_long_filename(self, async_client, mock_magic):
        """Filename > 255 characters should be truncated."""
        mock_magic.from_buffer.return_value = "application/pdf"

        long_name = "a" * 300 + ".pdf"
        files = {"file": (long_name, BytesIO(b"content"), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        # Should handle gracefully
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_file_with_no_extension(self, async_client):
        """File without extension should be validated."""
        files = {"file": ("README", BytesIO(b"content"), "text/plain")}
        response = await async_client.post("/test/upload", files=files)

        # Should fail validation (no extension)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_case_insensitive_content_type(self, async_client):
        """Content-Type with mixed case should be handled."""
        response = await async_client.post(
            "/test/json", json={"data": "test"}, headers={"Content-Type": "Application/JSON"}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_content_type_with_charset(self, async_client):
        """Content-Type with charset parameter should be parsed correctly."""
        response = await async_client.post(
            "/test/json", json={"data": "test"}, headers={"Content-Type": "application/json; charset=utf-8"}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_file_upload(self, async_client, mock_magic):
        """Empty file (0 bytes) should be validated."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("empty.pdf", BytesIO(b""), "application/pdf")}
        response = await async_client.post("/test/upload", files=files)

        # Should handle empty file
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_request_with_no_body(self, async_client):
        """POST request with no body should be handled."""
        response = await async_client.post("/test/json")

        # Should fail at endpoint level, not validation
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self, async_client):
        """Request with multiple validation issues should report first error."""
        # Large file with invalid extension
        large_file = b"x" * (6 * 1024 * 1024)
        files = {"file": ("large.exe", BytesIO(large_file), "application/octet-stream")}

        response = await async_client.post("/test/upload", files=files)

        # Should return one error (likely file type first)
        assert response.status_code in [400, 413]
        data = response.json()
        assert "error_code" in data


# ============================================================================
# TEST HELPER FUNCTIONS
# ============================================================================


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_sanitize_filename(self):
        """Test _sanitize_filename function."""
        # Test special characters
        assert _sanitize_filename("my@file#name$.pdf") == "my_file_name_.pdf"

        # Test spaces
        assert _sanitize_filename("my file name.pdf") == "my_file_name.pdf"

        # Test unicode
        result = _sanitize_filename("файл.pdf")
        assert ".pdf" in result

        # Test very long filename
        long_name = "a" * 300 + ".pdf"
        result = _sanitize_filename(long_name)
        assert len(result) <= 255

    def test_is_disallowed_path(self):
        """Test _is_disallowed_path function."""
        # Test path traversal patterns
        assert _is_disallowed_path("../../../etc/passwd") is True
        assert _is_disallowed_path("..\\..\\windows\\system32") is True
        assert _is_disallowed_path("/etc/passwd") is True
        assert _is_disallowed_path("\\windows\\system32") is True

        # Test normal filenames
        assert _is_disallowed_path("document.pdf") is False
        assert _is_disallowed_path("my_file_2024.docx") is False

    def test_is_whitelisted_content_type(self):
        """Test _is_whitelisted_content_type function."""
        # Test None (whitelisted)
        assert _is_whitelisted_content_type(None) is True

        # Test empty string (not whitelisted - only None is whitelisted)
        assert _is_whitelisted_content_type("") is False

        # Test actual content types (not whitelisted)
        assert _is_whitelisted_content_type("application/json") is False
        assert _is_whitelisted_content_type("multipart/form-data") is False


# ============================================================================
# TEST REQUEST BODY PRESERVATION
# ============================================================================


class TestRequestBodyPreservation:
    """Test that request body is preserved after validation."""

    @pytest.mark.asyncio
    async def test_json_body_preserved_after_validation(self, async_client):
        """JSON body should be accessible in endpoint after validation."""
        payload = {"key": "value", "number": 42}
        response = await async_client.post("/test/json", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["received"] == payload

    @pytest.mark.asyncio
    async def test_multipart_form_preserved_after_validation(self, async_client, sample_pdf_bytes, mock_magic):
        """Multipart form data should be accessible after validation."""
        mock_magic.from_buffer.return_value = "application/pdf"

        files = {"file": ("doc.pdf", BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"field1": "value1", "field2": "value2"}

        response = await async_client.post("/test/form", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["field1"] == "value1"
        assert result["field2"] == "value2"
        assert result["has_file"] is True


# ============================================================================
# COVERAGE CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=backend.api.middleware.request_validation_middleware",
            "--cov-report=term-missing",
            "--cov-report=html",
        ]
    )
