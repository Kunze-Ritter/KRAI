"""
Pydantic models for Pipeline Error API endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PipelineErrorResponse(BaseModel):
    """Response model for a single pipeline error."""

    error_id: str = Field(..., description="Unique error identifier")
    document_id: str = Field(..., description="Associated document ID")
    stage_name: str = Field(..., description="Pipeline stage name")
    error_type: str = Field(..., description="Error type/class name")
    error_category: str = Field(..., description="Error category (transient/permanent/unknown)")
    error_message: str = Field(..., description="Error message")
    stack_trace: str | None = Field(None, description="Full stack trace")
    context: dict | None = Field(None, description="Additional error context")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum allowed retries")
    status: str = Field(..., description="Error status (failed/retrying/resolved)")
    severity: str = Field(..., description="Error severity level")
    is_transient: bool = Field(..., description="Whether error is transient")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    created_at: datetime = Field(..., description="Error creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    resolved_at: datetime | None = Field(None, description="Resolution timestamp")
    resolved_by: str | None = Field(None, description="User who resolved the error")
    resolution_notes: str | None = Field(None, description="Resolution notes")

    class Config:
        from_attributes = True


class PipelineErrorListResponse(BaseModel):
    """Paginated list response for pipeline errors."""

    errors: list[PipelineErrorResponse] = Field(..., description="List of pipeline errors")
    total: int = Field(..., description="Total number of errors")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class RetryStageRequest(BaseModel):
    """Request model for retrying a failed stage."""

    document_id: str = Field(..., description="Document ID to retry")
    stage_name: str = Field(..., description="Stage name to retry")


class MarkErrorResolvedRequest(BaseModel):
    """Request model for marking an error as resolved."""

    error_id: str = Field(..., description="Error ID to mark as resolved")
    notes: str | None = Field(None, description="Optional resolution notes")


class PipelineErrorFilters(BaseModel):
    """Query parameters for filtering pipeline errors."""

    document_id: str | None = Field(None, description="Filter by document ID")
    stage_name: str | None = Field(None, description="Filter by stage name")
    error_type: str | None = Field(None, description="Filter by error type")
    status: str | None = Field(None, description="Filter by status")
    date_from: datetime | None = Field(None, description="Filter errors from this date")
    date_to: datetime | None = Field(None, description="Filter errors until this date")
