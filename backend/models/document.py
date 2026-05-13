"""
Document API models for CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator

from core.data_models import DocumentType, ProcessingStatus
from models.validators import validate_file_hash, validate_filename, validate_no_sql_injection, validate_uuid


class PaginationParams(BaseModel):
    """Standard pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (starting at 1)")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "page": 1,
                "page_size": 25,
            }
        }


class SortOrder(str, Enum):
    """Supported sort orders."""

    ASC = "asc"
    DESC = "desc"


ALLOWED_DOCUMENT_SORT_FIELDS = {"created_at", "updated_at", "filename", "document_type"}


# Canonical stage names for document processing pipeline
CANONICAL_STAGES = [
    "upload",
    "text_extraction",
    "table_extraction",
    "svg_processing",
    "image_processing",
    "visual_embedding",
    "link_extraction",
    "chunk_prep",
    "classification",
    "metadata_extraction",
    "parts_extraction",
    "series_detection",
    "storage",
    "embedding",
    "search_indexing",
]


class StageStatus(str, Enum):
    """Stage processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentStageDetail(BaseModel):
    """Detailed status for a single processing stage."""

    status: StageStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    progress: int = Field(0, ge=0, le=100, description="Progress percentage (0-100)")
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "started_at": "2025-12-07T14:20:00Z",
                "completed_at": "2025-12-07T14:20:15Z",
                "duration_seconds": 15.3,
                "progress": 100,
                "error": None,
                "metadata": {"chunks_created": 42},
            }
        }


class DocumentStageStatusResponse(BaseModel):
    """Complete stage-level processing status for a document."""

    document_id: str
    filename: str
    overall_progress: float = Field(..., ge=0, le=100, description="Overall progress percentage (0-100)")
    current_stage: str
    stages: dict[str, DocumentStageDetail] = Field(..., description="Stage name -> stage detail mapping")
    can_retry: bool = Field(..., description="Whether any failed stages can be retried")
    last_updated: str

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "c7f1b804-1a7a-44f9-9c27-9c3f7253b5c1",
                "filename": "manual_123.pdf",
                "overall_progress": 73.3,
                "current_stage": "embedding",
                "stages": {
                    "upload": DocumentStageDetail.Config.json_schema_extra["example"],
                    "text_extraction": DocumentStageDetail.Config.json_schema_extra["example"],
                },
                "can_retry": False,
                "last_updated": "2025-12-07T14:20:15Z",
            }
        }


class DocumentCreateRequest(BaseModel):
    """Payload for document creation."""

    filename: str = Field(..., min_length=1, max_length=255)
    original_filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., ge=0, description="File size in bytes")
    file_hash: str = Field(..., min_length=10, max_length=128)
    storage_path: str = Field(..., min_length=1, max_length=512)
    storage_url: str = Field(..., min_length=1, max_length=1024)
    document_type: DocumentType
    language: str = Field(..., min_length=2, max_length=10)
    manufacturer: str | None = Field(None, max_length=255)
    series: str | None = Field(None, max_length=255)
    models: list[str] = Field(default_factory=list)
    version: str | None = Field(None, max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "documents/2025/10/manual_123.pdf",
                "original_filename": "manual_123.pdf",
                "file_size": 2456789,
                "file_hash": "f5f1f9bab41bb53efab5d7e9c9123456",
                "storage_path": "krai-core/documents/manual_123.pdf",
                "storage_url": "https://storage.example.com/manual_123.pdf",
                "document_type": "service_manual",
                "language": "en",
                "manufacturer": "Lexmark",
                "series": "CS920",
                "models": ["CS921", "CS922"],
                "version": "v1.2",
            }
        }

    @validator("filename", "original_filename")
    def validate_filenames(cls, value: str) -> str:
        return validate_filename(value)

    @validator("file_hash")
    def validate_hash(cls, value: str) -> str:
        return validate_file_hash(value)

    @validator("models", each_item=True)
    def validate_models(cls, value: str) -> str:
        if not value:
            raise ValueError("Model identifiers cannot be empty")
        return value


class DocumentUpdateRequest(BaseModel):
    """Payload for document updates."""

    document_type: DocumentType | None = None
    language: str | None = Field(None, min_length=2, max_length=10)
    manufacturer: str | None = Field(None, max_length=255)
    series: str | None = Field(None, max_length=255)
    models: list[str] | None = None
    version: str | None = Field(None, max_length=50)
    processing_status: ProcessingStatus | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    manual_review_required: bool | None = None
    manual_review_notes: str | None = Field(None, max_length=2000)

    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "service_manual",
                "language": "de",
                "processing_status": "completed",
                "confidence_score": 0.92,
                "manual_review_required": False,
                "manual_review_notes": "Verified by QA",
                "models": ["CS923"],
            }
        }

    @validator("models")
    def validate_models(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("Models list cannot be empty when provided")
        if any(not item for item in value):
            raise ValueError("Model identifiers cannot be empty")
        return value

    @validator("document_type", "language", "manufacturer", "series", "version", pre=True, always=True)
    def sanitize_strings(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @validator("processing_status")
    def validate_status(cls, value: ProcessingStatus | None) -> ProcessingStatus | None:
        return value


class DocumentFilterParams(BaseModel):
    """Supported filters for listing documents."""

    manufacturer_id: str | None = Field(None, description="Filter by manufacturer ID")
    product_id: str | None = Field(None, description="Filter by product ID")
    document_type: str | None = Field(None, description="Filter by document type")
    language: str | None = Field(None, description="Filter by language")
    processing_status: str | None = Field(None, description="Filter by processing status")
    manual_review_required: bool | None = Field(None, description="Filter by manual review requirement flag")
    search: str | None = Field(None, description="Full-text search query")
    has_failed_stages: bool | None = Field(None, description="Filter by documents with failed stages")
    has_incomplete_stages: bool | None = Field(None, description="Filter by documents with incomplete stages")
    stage_name: str | None = Field(None, description="Filter by specific stage name")

    class Config:
        json_schema_extra = {
            "example": {
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "document_type": "service_manual",
                "language": "en",
                "processing_status": "completed",
                "search": "CS920 calibration",
                "has_failed_stages": True,
                "stage_name": "embedding",
            }
        }

    @validator("manufacturer_id", "product_id")
    def validate_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_uuid(value)

    @validator("search")
    def validate_search(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) > 100:
            raise ValueError("search must be 100 characters or less")
        validate_no_sql_injection(value)
        return value

    @validator("document_type")
    def validate_document_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            DocumentType(value)
        except ValueError as exc:
            allowed = ", ".join(sorted(item.value for item in DocumentType))
            raise ValueError(f"document_type must be one of: {allowed}") from exc
        return value

    @validator("processing_status")
    def validate_processing_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ProcessingStatus(value)
        except ValueError as exc:
            allowed = ", ".join(sorted(item.value for item in ProcessingStatus))
            raise ValueError(f"processing_status must be one of: {allowed}") from exc
        return value

    @validator("stage_name")
    def validate_stage_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in CANONICAL_STAGES:
            raise ValueError(f"stage_name must be one of: {', '.join(CANONICAL_STAGES)}")
        return value


class DocumentSortParams(BaseModel):
    """Sorting parameters for documents."""

    sort_by: str = Field("created_at", description="Field name to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order: asc or desc")

    class Config:
        json_schema_extra = {
            "example": {
                "sort_by": "updated_at",
                "sort_order": "asc",
            }
        }

    @validator("sort_by")
    def validate_sort_by(cls, value: str) -> str:
        if value not in ALLOWED_DOCUMENT_SORT_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_DOCUMENT_SORT_FIELDS))
            raise ValueError(f"sort_by must be one of: {allowed}")
        return value

    @validator("sort_order", pre=True)
    def validate_sort_order(cls, value: str | SortOrder) -> SortOrder:
        try:
            return SortOrder(value)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in SortOrder)
            raise ValueError(f"sort_order must be one of: {allowed}") from exc


class DocumentResponse(BaseModel):
    """Document representation for API responses."""

    id: str
    filename: str
    original_filename: str
    file_size: int
    file_hash: str
    storage_path: str
    storage_url: str
    document_type: DocumentType
    language: str | None = None
    version: str | None = None
    publish_date: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    character_count: int | None = None
    processing_status: ProcessingStatus | None = None
    confidence_score: float | None = None
    manual_review_required: bool | None = None
    manual_review_notes: str | None = None
    stage_status: dict | None = None
    manufacturer: str | None = None
    series: str | None = None
    models: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    manufacturer_id: str | None = None
    product_id: str | None = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "c7f1b804-1a7a-44f9-9c27-9c3f7253b5c1",
                "filename": "documents/2025/10/manual_123.pdf",
                "original_filename": "manual_123.pdf",
                "file_size": 2456789,
                "file_hash": "f5f1f9bab41bb53efab5d7e9c9123456",
                "storage_path": "krai-core/documents/manual_123.pdf",
                "storage_url": "https://storage.example.com/manual_123.pdf",
                "document_type": "service_manual",
                "language": "en",
                "version": "v1.2",
                "publish_date": "2025-08-15T00:00:00Z",
                "page_count": 256,
                "word_count": 54000,
                "character_count": 325000,
                "processing_status": "completed",
                "confidence_score": 0.92,
                "manufacturer": "Lexmark",
                "series": "CS920",
                "models": ["CS921", "CS922"],
                "created_at": "2025-10-30T12:00:00Z",
                "updated_at": "2025-10-30T12:30:00Z",
                "manufacturer_id": "8dc1d2a5-8ef3-4dc1-90f9-1d4b7c6c1234",
                "product_id": "f214ab9d-6727-406d-bf4e-8e1f0346a123",
            }
        }

    @validator("models", pre=True, always=True)
    def ensure_models(cls, value: list[str] | None) -> list[str]:
        return value or []


class DocumentListResponse(BaseModel):
    """Paginated document list response."""

    documents: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "documents": [DocumentResponse.Config.json_schema_extra["example"]],
                "total": 150,
                "page": 1,
                "page_size": 10,
                "total_pages": 15,
            }
        }


class DocumentStatsResponse(BaseModel):
    """Aggregated document statistics."""

    total_documents: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_manufacturer: dict[str, int]

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 1500,
                "by_type": {
                    "service_manual": 820,
                    "parts_catalog": 430,
                    "user_manual": 250,
                },
                "by_status": {
                    "pending": 120,
                    "in_progress": 45,
                    "completed": 1285,
                    "failed": 50,
                },
                "by_manufacturer": {
                    "Lexmark": 340,
                    "Konica Minolta": 410,
                    "Canon": 280,
                },
            }
        }
