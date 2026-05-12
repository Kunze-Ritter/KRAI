"""Common response wrapper models for API routes."""

from __future__ import annotations

from typing import Any, ClassVar, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, HttpUrl
from pydantic.generics import GenericModel

T = TypeVar("T")


class DocumentStatusResponse(BaseModel):
    """Document processing status response."""

    document_status: str = Field(..., description="Current processing status of the document")
    queue_position: int = Field(..., description="Position in processing queue")
    total_queue_items: int = Field(..., description="Total number of items in queue")


class DocumentProcessingStatusResponse(BaseModel):
    """Processing status response for the new /api/v1/documents/{id}/status endpoint.
    Distinct from DocumentStatusResponse (which has field 'document_status')."""

    document_id: str
    status: str = Field(..., description="pending|processing|completed|failed")
    current_stage: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    queue_position: int = Field(default=0)
    total_queue_items: int = Field(default=0)
    stage_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Counts of stages by status: completed, processing, failed, pending, skipped, total",
    )


class SuccessResponse(GenericModel, Generic[T]):
    """Standard success response envelope."""

    success: Literal[True] = Field(default=True)
    data: T
    message: str | None = Field(
        None,
        description="Optional human-readable message providing additional context.",
    )

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "success": True,
                "data": {"id": "example-id", "name": "Example"},
                "message": "Operation completed successfully.",
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: Literal[False] = Field(default=False)
    error: str = Field(..., description="Short error type or key.")
    detail: str | None = Field(None, description="Detailed error description or remediation guidance.")
    error_code: str | None = Field(
        None,
        description="Stable machine-readable error code for programmatic handling.",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional contextual information about the error (field names, constraints, expected vs received values).",
    )

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "success": False,
                "error": "Validation Error",
                "detail": "File type '.exe' is not supported. Allowed types: .pdf, .docx. Please upload a file with one of the supported extensions.",
                "error_code": "INVALID_FILE_TYPE",
                "context": {"filename": "document.exe", "extension": ".exe", "allowed_extensions": [".pdf", ".docx"]},
            }
        }


# Stage-Based Processing Models


class StageProcessingRequest(BaseModel):
    """Request model for processing multiple stages"""

    stages: list[str] = Field(..., description="List of stage names to process")
    stop_on_error: bool = Field(default=True, description="Stop processing on first error")


class StageResult(BaseModel):
    """Result of a single stage processing"""

    stage: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    processing_time: float


class StageProcessingResponse(BaseModel):
    """Response for stage processing"""

    success: bool
    total_stages: int
    successful: int
    failed: int
    stage_results: list[StageResult]
    success_rate: float


class StageListResponse(BaseModel):
    """Response for available stages"""

    stages: list[str]
    total: int


class StageStatusResponse(BaseModel):
    """Response for stage status"""

    document_id: str
    stage_status: dict[str, str]  # {"text_extraction": "completed", ...}
    found: bool
    error: str | None = None


# Video Processing Models


class VideoProcessingRequest(BaseModel):
    """Request model for video enrichment"""

    video_url: HttpUrl = Field(..., description="YouTube/Vimeo/Brightcove video URL")
    manufacturer_id: str | None = Field(None, description="Manufacturer UUID")


class VideoProcessingResponse(BaseModel):
    """Response for video enrichment"""

    success: bool
    video_id: str | None = None
    title: str | None = None
    platform: str | None = None
    thumbnail_url: str | None = None
    duration: int | None = None
    channel_title: str | None = None
    error: str | None = None


# Thumbnail Generation Models


class ThumbnailGenerationRequest(BaseModel):
    """Request model for thumbnail generation"""

    size: list[int] | None = Field(default=[300, 400], description="Thumbnail size [width, height]")
    page: int | None = Field(default=0, description="Page number to render (0-indexed)")


class ThumbnailGenerationResponse(BaseModel):
    """Response for thumbnail generation"""

    success: bool
    thumbnail_url: str | None = None
    size: list[int] | None = None
    file_size: int | None = None
    error: str | None = None
