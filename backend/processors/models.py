"""
Data models for processor V2

Pydantic models for type safety and validation.
"""

import os
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

from backend.constants.product_types import ALLOWED_PRODUCT_TYPES


class ExtractedProduct(BaseModel):
    """Product extracted from document"""

    model_number: str = Field(..., min_length=3, max_length=100)
    product_series: str | None = Field(None, description="Product series/family (e.g., LaserJet, AccurioPress)")
    product_type: str = Field(
        ..., description="Product type identifier, must match allowed list in backend.constants.product_types"
    )
    manufacturer_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_page: int | None = None
    extraction_method: str = Field(default="regex")
    quality_flag: str = Field(
        default="normal",
        pattern="^(normal|low_confidence|rejected)$",
        description="Quality indicator for downstream filtering",
    )

    # Specifications (JSONB - flexible storage)
    specifications: dict[str, Any] = Field(
        default_factory=dict, description="All specifications in flexible JSONB format"
    )

    # Computed property for display name
    @property
    def display_name(self) -> str:
        """Generate display name from series + model_number"""
        if self.product_series:
            return f"{self.product_series} {self.model_number}"
        return self.model_number

    # Helper properties for common specs (backward compatibility)
    @property
    def max_print_speed_ppm(self) -> int | None:
        return self.specifications.get("max_print_speed_ppm")

    @property
    def max_resolution_dpi(self) -> int | None:
        return self.specifications.get("max_resolution_dpi")

    @property
    def duplex_capable(self) -> bool | None:
        return self.specifications.get("duplex_capable")

    @validator("model_number")
    def validate_model_number(cls, v):
        """Ensure model number is not a filename"""
        if "." in v or "_" in v or "/" in v or "\\" in v:
            raise ValueError("Model number appears to be a filename")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Model number must contain both letters and numbers")
        return v

    @validator("product_type")
    def validate_product_type(cls, v: str) -> str:
        """Ensure product_type matches shared allow-list"""
        if v not in ALLOWED_PRODUCT_TYPES:
            raise ValueError(f"Unsupported product_type '{v}'. Must be one of: {sorted(ALLOWED_PRODUCT_TYPES)}")
        return v


class ExtractedPart(BaseModel):
    """Part/spare part extracted from parts catalog - Manufacturer inherited from document"""

    part_number: str = Field(..., min_length=3, max_length=100)
    part_name: str | None = Field(None, max_length=255)
    part_description: str | None = None
    part_category: str | None = Field(None, max_length=100)
    # manufacturer_name removed - always inherited from document
    unit_price_usd: float | None = Field(None, ge=0.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    pattern_name: str | None = Field(None, description="Which pattern matched this part")
    page_number: int | None = None
    context: str | None = Field(None, max_length=500, description="Surrounding text context")
    metadata: dict[str, Any] = Field(default_factory=dict)

    # NEW: Linking to error codes and products
    related_error_codes: list[str] = Field(default_factory=list, description="Error codes that mention this part")
    related_products: list[str] = Field(default_factory=list, description="Products this part is compatible with")
    chunk_id: str | None = None  # Link to chunk for images (like error codes)

    @validator("part_number")
    def validate_part_number(cls, v):
        """Ensure part number is valid"""
        if not v or len(v.strip()) < 3:
            raise ValueError("Part number too short")
        return v.strip().upper()


class ExtractedErrorCode(BaseModel):
    """Error code extracted from document or video"""

    # Flexible pattern for various error code formats:
    # - 10.20 or 10.20.30 (Konica Minolta, Xerox)
    # - E826 (HP alphanumeric)
    # - 59.F0 (HP hex)
    # - C-2801 (Canon)
    error_code: str = Field(..., pattern=r"^[A-Z]?-?\d{1,3}[\.\-]?[A-Za-z0-9]{1,4}([\.\-][A-Za-z0-9]{1,4})?$")
    error_description: str = Field(..., min_length=10)  # Reduced from 20 to 10 (e.g., "Power line A1 error" = 19 chars)
    solution_customer_text: str | None = None  # Level 1: basic user steps
    solution_agent_text: str | None = None  # Level 2: call-center / 2nd level
    solution_technician_text: str | None = None  # Level 3: on-site technician (preferred)
    context_text: str = Field(..., min_length=50)  # Reduced from 100 to 50 for more flexibility
    confidence: float = Field(..., ge=0.0, le=1.0)
    page_number: int
    extraction_method: str = Field(default="regex_pattern")
    requires_parts: bool = False
    severity_level: str = Field(default="medium", pattern="^(low|medium|high|critical)$")

    # NEW: Product and video linking
    product_id: str | None = None
    video_id: str | None = None
    chunk_id: str | None = None  # Link to intelligence chunk for images
    manufacturer_name: str | None = Field(
        default=None, description="Brand manufacturer name used for extraction (e.g., Konica Minolta)"
    )
    effective_manufacturer: str | None = Field(
        default=None, description="OEM manufacturer actually used for validation/patterns"
    )
    quality_flag: str = Field(
        default="normal",
        pattern="^(normal|low_confidence|rejected)$",
        description="Quality indicator for downstream filtering",
    )
    parent_code: str | None = Field(
        default=None, description="Parent error code category (e.g., '13.B9' for '13.B9.Az')"
    )
    is_category: bool = Field(default=False, description="True if this is a category entry, not a specific error code")

    @validator("error_description")
    def validate_description(cls, v):
        """Ensure description is not generic"""
        generic_phrases = ["error code", "refer to manual", "see documentation", "contact support"]
        # If description is short and contains generic phrase, reject
        if len(v) < 30:
            for phrase in generic_phrases:
                if phrase in v.lower():
                    raise ValueError(f"Description too generic: contains '{phrase}'")
        return v


class TextChunk(BaseModel):
    """Text chunk for embedding"""

    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    text: str = Field(..., min_length=30)  # Reduced to allow valuable short chunks
    chunk_index: int
    page_start: int
    page_end: int
    chunk_type: str = Field(default="text")
    metadata: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str | None = None

    @validator("text")
    def validate_text(cls, v):
        """Ensure text is meaningful (reduced from 50 to 30 to preserve short but valuable content)"""
        if os.getenv("DEBUG_ALLOW_SHORT_CHUNKS", "false").lower() == "true":
            return v.strip()

        if len(v.strip()) < 30:
            raise ValueError("Chunk text too short after stripping (min 30 chars)")
        return v.strip()


class DocumentMetadata(BaseModel):
    """Document metadata"""

    document_id: UUID
    title: str | None = None
    author: str | None = None
    creation_date: datetime | None = None
    page_count: int = Field(..., gt=0)
    file_size_bytes: int = Field(..., gt=0)
    mime_type: str = Field(default="application/pdf")
    language: str = Field(default="en")
    language_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence score (0-1) for detected language"
    )
    document_type: str = Field(..., pattern="^(service_manual|parts_catalog|user_guide|troubleshooting)$")
    engine_used: str = Field(default="pymupdf", description="Primary engine used for text extraction")
    fallback_used: str | None = Field(default=None, description="Fallback extraction path used, if any")
    pages_failed: int = Field(default=0, ge=0, description="Number of pages that failed primary text extraction")


class ProcessingResult(BaseModel):
    """Result of document processing"""

    document_id: UUID
    success: bool
    metadata: DocumentMetadata
    chunks: list[TextChunk] = Field(default_factory=list)
    products: list[ExtractedProduct] = Field(default_factory=list)
    parts: list[ExtractedPart] = Field(default_factory=list)
    error_codes: list[ExtractedErrorCode] = Field(default_factory=list)
    versions: list["ExtractedVersion"] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    videos: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    processing_time_seconds: float
    statistics: dict[str, Any] = Field(default_factory=dict)

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for logging"""
        return {
            "document_id": str(self.document_id),
            "success": self.success,
            "chunks_created": len(self.chunks),
            "products_extracted": len(self.products),
            "parts_extracted": len(self.parts),
            "error_codes_extracted": len(self.error_codes),
            "versions_extracted": len(self.versions),
            "links_extracted": len(self.links),
            "videos_extracted": len(self.videos),
            "validation_errors": len(self.validation_errors),
            "avg_product_confidence": (
                sum(p.confidence for p in self.products) / len(self.products) if self.products else 0
            ),
            "avg_part_confidence": sum(p.confidence for p in self.parts) / len(self.parts) if self.parts else 0,
            "avg_error_code_confidence": (
                sum(e.confidence for e in self.error_codes) / len(self.error_codes) if self.error_codes else 0
            ),
            "avg_version_confidence": (
                sum(v.confidence for v in self.versions) / len(self.versions) if self.versions else 0
            ),
            "processing_time": f"{self.processing_time_seconds:.2f}s",
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for pipeline consumption"""
        return {
            "success": self.success,
            "document_id": str(self.document_id),
            "metadata": {
                "page_count": self.metadata.page_count,
                "file_size_bytes": self.metadata.file_size_bytes,
                "title": self.metadata.title,
                "author": self.metadata.author,
                "word_count": sum(len(chunk.text.split()) for chunk in self.chunks),
                "char_count": sum(len(chunk.text) for chunk in self.chunks),
            },
            "chunks": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "chunk_type": chunk.chunk_type,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                }
                for chunk in self.chunks
            ],
            "products": [
                {
                    "model_number": p.model_number,
                    "product_series": p.product_series,
                    "product_type": p.product_type,
                    "manufacturer_name": p.manufacturer_name,
                    "confidence": p.confidence,
                    "quality_flag": p.quality_flag,
                    "extraction_method": p.extraction_method,
                    "specifications": p.specifications,
                }
                for p in self.products
            ],
            "error_codes": [
                {
                    "error_code": e.error_code,
                    "error_description": e.error_description,
                    "solution_customer_text": e.solution_customer_text,
                    "solution_agent_text": e.solution_agent_text,
                    "solution_technician_text": e.solution_technician_text,
                    "confidence": e.confidence,
                    "quality_flag": e.quality_flag,
                    "page_number": e.page_number,
                    "severity_level": e.severity_level,
                }
                for e in self.error_codes
            ],
            "versions": [
                {
                    "version_string": v.version_string,
                    "version_type": v.version_type,
                    "confidence": v.confidence,
                }
                for v in self.versions
            ],
            "images": [],  # Will be added by master pipeline
            "statistics": self.statistics,
            "processing_time": self.processing_time_seconds,
        }


class ExtractedVersion(BaseModel):
    """Version extracted from document"""

    version_string: str = Field(..., min_length=1, max_length=50)
    version_type: str = Field(
        ...,
        pattern="^(edition|date|firmware|version|revision)$",
        description="Type of version: edition, date, firmware, version, revision",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    extraction_method: str = Field(default="pattern_matching")
    page_number: int | None = None
    context: str | None = Field(None, max_length=200, description="Surrounding context")

    @validator("version_string")
    def validate_version_string(cls, v):
        """Ensure version string is reasonable"""
        if len(v.strip()) < 1:
            raise ValueError("Version string cannot be empty")
        # Remove excessive whitespace
        return " ".join(v.split())


class ValidationError(BaseModel):
    """Validation error details"""

    field: str
    value: Any
    error_message: str
    severity: str = Field(default="error", pattern="^(warning|error|critical)$")

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.error_message} (value: {self.value})"
