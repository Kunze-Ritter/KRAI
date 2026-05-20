"""Pydantic models for error code management APIs."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator, validator

from backend.models.document import DocumentResponse, SortOrder
from backend.models.manufacturer import ManufacturerResponse
from backend.models.validators import (
    ensure_allowed_fields,
    sanitize_string,
    validate_error_code,
    validate_no_sql_injection,
    validate_uuid,
)

ALLOWED_SEARCH_FIELDS = {"error_code", "error_description", "solution_text"}


class SeverityLevel(str, Enum):
    """Enumerates severity levels for error codes."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ExtractionMethod(str, Enum):
    """Enumerates extraction sources for error codes."""

    MANUAL = "manual"
    OCR = "ocr"
    LLM = "llm"
    HYBRID = "hybrid"


class ErrorCodeBase(BaseModel):
    """Base shared attributes for error codes."""

    chunk_id: str | None = Field(None, description="Identifier of the originating chunk.")
    document_id: str | None = Field(None, description="Identifier of the document associated with the error code.")
    manufacturer_id: str | None = Field(None, description="Identifier of the manufacturer related to the error.")
    error_code: str | None = Field(
        None,
        max_length=20,
        description="Short error code identifier (e.g., E23).",
    )
    error_description: str | None = Field(None, description="Detailed description of the error condition.")
    solution_text: str | None = Field(None, description="Suggested remediation steps for resolving the error.")
    page_number: int | None = Field(None, ge=0, description="Document page number where the error was found.")
    confidence_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for automatically extracted error codes (0-1).",
    )
    extraction_method: ExtractionMethod | None = Field(None, description="Source method used to derive the error code.")
    requires_technician: bool | None = Field(None, description="Whether technician intervention is required.")
    requires_parts: bool | None = Field(None, description="Whether hardware parts are required to resolve the error.")
    estimated_fix_time_minutes: int | None = Field(
        None,
        ge=0,
        description="Estimated time to resolve the error in minutes.",
    )
    severity_level: SeverityLevel | None = Field(None, description="Categorised severity of the error.")
    ai_notes: str | None = Field(
        None,
        description="Supplementary notes produced by AI assisted extraction or analysis.",
    )

    model_config = ConfigDict(from_attributes=True)

    @validator("chunk_id", "document_id", "manufacturer_id")
    def validate_related_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("error_code", pre=True)
    def sanitize_error_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        sanitized = sanitize_string(value)
        return validate_error_code(sanitized)

    @validator("error_description", "solution_text", "ai_notes", pre=True)
    def sanitize_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        sanitized = sanitize_string(value)
        validate_no_sql_injection(sanitized)
        return sanitized


class ErrorCodeCreateRequest(ErrorCodeBase):
    """Payload for creating a new error code."""

    error_code: str = Field(..., max_length=20)
    error_description: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_relationships(cls, values: ErrorCodeCreateRequest) -> ErrorCodeCreateRequest:
        if not any([values.chunk_id, values.document_id, values.manufacturer_id]):
            raise ValueError("At least one of chunk_id, document_id, or manufacturer_id must be provided.")
        if not values.error_code.strip():
            raise ValueError("error_code must not be empty.")
        return values

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "SC542",
                "error_description": "Fusing unit temperature error.",
                "solution_text": "Check the thermistor and reset the fusing unit.",
                "severity_level": "high",
                "requires_technician": True,
                "document_id": "doc-123",
                "manufacturer_id": "mfg-789",
                "confidence_score": 0.92,
                "extraction_method": "llm",
            }
        }
    )


class ErrorCodeUpdateRequest(ErrorCodeBase):
    """Payload for updating an existing error code."""

    error_code: str | None = Field(None, max_length=20)

    @model_validator(mode="after")
    def validate_optional_fields(cls, values: ErrorCodeUpdateRequest) -> ErrorCodeUpdateRequest:
        if values.error_code is not None and not values.error_code.strip():
            raise ValueError("error_code must not be empty if provided.")
        if values.chunk_id is None and values.document_id is None and values.manufacturer_id is None:
            # Updates may intentionally remove relations, so only enforce when all fields missing
            pass
        return values

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_description": "Updated instructions for technicians.",
                "solution_text": "Replace thermal fuse and reset controller.",
                "severity_level": "critical",
                "estimated_fix_time_minutes": 45,
            }
        }
    )


class ErrorCodeFilterParams(BaseModel):
    """Query parameters for filtering error codes."""

    manufacturer_id: str | None = Field(None, description="Filter by manufacturer ID.")
    document_id: str | None = Field(None, description="Filter by document ID.")
    chunk_id: str | None = Field(None, description="Filter by chunk ID.")
    error_code: str | None = Field(None, description="Filter by exact error code identifier.")
    severity_level: SeverityLevel | None = Field(None, description="Filter by severity classification.")
    requires_technician: bool | None = Field(None, description="Filter by technician requirement.")
    requires_parts: bool | None = Field(None, description="Filter by parts requirement.")
    search: str | None = Field(
        None,
        description="Full-text search across error_code, error_description, and solution_text.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "manufacturer_id": "mfg-789",
                "severity_level": "high",
                "requires_technician": True,
                "search": "paper jam",
            }
        }
    )

    @validator("manufacturer_id", "document_id", "chunk_id")
    def validate_filter_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("error_code", pre=True)
    def sanitize_error_code_filter(cls, value: str | None) -> str | None:
        if value is None:
            return value
        sanitized = sanitize_string(value)
        return validate_error_code(sanitized)

    @validator("search")
    def validate_search(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) > 200:
            raise ValueError("search must be 200 characters or less")
        validate_no_sql_injection(value)
        return value


class ErrorCodeSortParams(BaseModel):
    """Sorting options for error code listings."""

    sort_by: str = Field(
        "created_at",
        description="Column to sort by, e.g. created_at, severity_level, error_code.",
    )
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort direction: asc or desc.")


class ErrorCodeResponse(ErrorCodeBase):
    """Represents an error code record."""

    id: str = Field(..., description="Unique error code identifier.")
    error_code: str = Field(..., max_length=20)
    error_description: str = Field(...)
    created_at: str | None = Field(None, description="Timestamp when the error code was created.")
    updated_at: str | None = Field(None, description="Timestamp when the error code was last updated.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "err-001",
                "error_code": "SC542",
                "error_description": "Fusing unit temperature error.",
                "solution_text": "Reset the fusing unit after inspection.",
                "severity_level": "high",
                "requires_technician": True,
                "requires_parts": False,
                "estimated_fix_time_minutes": 30,
                "created_at": "2024-10-05T12:34:56Z",
            }
        }
    )


class ChunkExcerpt(BaseModel):
    """Represents related chunk context."""

    text_chunk: str | None = Field(None, description="Extracted text chunk associated with the error code.")
    page_start: int | None = Field(None, ge=0, description="Starting page number.")
    page_end: int | None = Field(None, ge=0, description="Ending page number.")

    model_config = ConfigDict(from_attributes=True)


class ErrorCodeWithRelationsResponse(ErrorCodeResponse):
    """Error code response enriched with related resources."""

    document: DocumentResponse | None = Field(None, description="Associated document details if available.")
    manufacturer: ManufacturerResponse | None = Field(None, description="Associated manufacturer details if available.")
    chunk: ChunkExcerpt | None = Field(None, description="Related chunk snippet providing additional context.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "err-001",
                "error_code": "SC542",
                "error_description": "Fusing unit temperature error.",
                "severity_level": "high",
                "document": {"id": "doc-123", "title": "Service Manual"},
                "manufacturer": {"id": "mfg-789", "name": "Lexmark"},
                "chunk": {
                    "text_chunk": "Error SC542 indicates the fusing unit has overheated...",
                    "page_start": 12,
                    "page_end": 13,
                },
            }
        }
    )


class ErrorCodeListResponse(BaseModel):
    """Paginated error code listing."""

    error_codes: list[ErrorCodeResponse] = Field(..., description="List of error codes.")
    total: int = Field(..., ge=0, description="Total number of matching records.")
    page: int = Field(..., ge=1, description="Current page number.")
    page_size: int = Field(..., ge=1, description="Number of records per page.")
    total_pages: int = Field(..., ge=1, description="Total number of pages based on the current page size.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_codes": [
                    {
                        "id": "err-001",
                        "error_code": "SC542",
                        "error_description": "Fusing unit temperature error.",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 25,
                "total_pages": 1,
            }
        }
    )


class ErrorCodeSearchRequest(BaseModel):
    """Payload for multi-source error code search."""

    query: str = Field(..., min_length=1, description="Search query string.")
    search_in: list[str] = Field(
        default_factory=lambda: ["error_code", "error_description", "solution_text"],
        description="Fields to search across.",
    )
    manufacturer_id: str | None = Field(None, description="Filter by manufacturer ID.")
    severity_level: SeverityLevel | None = Field(None, description="Filter search by severity level.")
    limit: PositiveInt = Field(20, description="Maximum number of search results to return (default 20).")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "paper jam",
                "search_in": ["error_description", "solution_text"],
                "manufacturer_id": "mfg-789",
                "limit": 10,
            }
        }
    )

    @validator("manufacturer_id")
    def validate_manufacturer(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("query")
    def sanitize_query(cls, value: str) -> str:
        sanitized = sanitize_string(value)
        if len(sanitized) > 200:
            raise ValueError("query must be 200 characters or less")
        return validate_no_sql_injection(sanitized)

    @validator("search_in")
    def validate_search_in(cls, value: list[str]) -> list[str]:
        allowed = ensure_allowed_fields(value, ALLOWED_SEARCH_FIELDS, "search_in")
        if not allowed:
            raise ValueError("search_in must include at least one field")
        return allowed


class ErrorCodeSearchResponse(BaseModel):
    """Response structure for multi-source search."""

    results: list[ErrorCodeWithRelationsResponse] = Field(
        default_factory=list, description="Search results with related entities."
    )
    total: int = Field(..., ge=0, description="Total number of matches returned.")
    query: str = Field(..., description="Echoed search query string.")
    search_duration_ms: int = Field(..., ge=0, description="Duration of the search execution in milliseconds.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [],
                "total": 0,
                "query": "paper jam",
                "search_duration_ms": 45,
            }
        }
    )
