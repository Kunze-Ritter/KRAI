"""
Data Models for KR-AI-Engine
Pydantic models for all data structures in the processing pipeline
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Document type enumeration"""

    SERVICE_MANUAL = "service_manual"
    PARTS_CATALOG = "parts_catalog"
    TECHNICAL_BULLETIN = "technical_bulletin"
    CPMD_DATABASE = "cpmd_database"
    USER_MANUAL = "user_manual"
    INSTALLATION_GUIDE = "installation_guide"
    TROUBLESHOOTING_GUIDE = "troubleshooting_guide"


class ProcessingStatus(str, Enum):
    """Processing status enumeration"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"  # legacy alias used in DB; treated as in_progress
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImageType(str, Enum):
    """Image type enumeration"""

    DIAGRAM = "diagram"
    SCREENSHOT = "screenshot"
    PHOTO = "photo"
    CHART = "chart"
    SCHEMATIC = "schematic"
    FLOWCHART = "flowchart"


class ChunkType(str, Enum):
    """Chunk type enumeration"""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    LIST = "list"
    CODE = "code"
    ERROR_CODE = "error_code"
    PROCEDURE = "procedure"


# Core Document Models
class DocumentModel(BaseModel):
    """Document model for krai_core.documents"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str | None = None
    file_size: int
    file_hash: str
    storage_path: str | None = None  # Database only - no Object Storage
    storage_url: str | None = None  # Database only - no Object Storage
    document_type: DocumentType
    language: str = "en"
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    manufacturer: str | None = None
    manufacturer_id: str | None = None
    series: str | None = None
    models: list[str] = Field(default_factory=list)
    version: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        use_enum_values = True


class ManufacturerModel(BaseModel):
    """Manufacturer model for krai_core.manufacturers"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    website: str | None = None
    country: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductSeriesModel(BaseModel):
    """Product series model for krai_core.product_series"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    manufacturer_id: str
    series_name: str
    series_code: str | None = None
    launch_date: datetime | None = None
    end_of_life_date: datetime | None = None
    target_market: str | None = None
    price_range: str | None = None
    key_features: dict[str, Any] = Field(default_factory=dict)  # JSONB
    series_description: str | None = None
    marketing_name: str | None = None
    successor_series_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductModel(BaseModel):
    """Product model for krai_core.products"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    manufacturer_id: str
    series_id: str
    model_number: str
    model_name: str
    product_type: str
    launch_date: datetime | None = None
    end_of_life_date: datetime | None = None
    msrp_usd: float | None = None
    weight_kg: float | None = None
    dimensions_mm: dict[str, float] = Field(default_factory=dict)  # JSONB
    color_options: list[str] = Field(default_factory=list)
    connectivity_options: list[str] = Field(default_factory=list)
    print_technology: str | None = None
    max_print_speed_ppm: int | None = None
    max_resolution_dpi: int | None = None
    max_paper_size: str | None = None
    duplex_capable: bool = False
    network_capable: bool = False
    mobile_print_support: bool = False
    supported_languages: list[str] = Field(default_factory=list)
    energy_star_certified: bool = False
    warranty_months: int | None = None
    service_manual_url: str | None = None
    parts_catalog_url: str | None = None
    driver_download_url: str | None = None
    firmware_version: str | None = None
    option_dependencies: dict[str, Any] = Field(default_factory=dict)  # JSONB
    replacement_parts: dict[str, Any] = Field(default_factory=dict)  # JSONB
    common_issues: dict[str, Any] = Field(default_factory=dict)  # JSONB
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Content Models
class ChunkModel(BaseModel):
    """Chunk model for krai_intelligence.chunks"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    content: str
    chunk_type: ChunkType
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    confidence_score: float = 0.0
    language: str = "en"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ImageModel(BaseModel):
    """Image model for krai_content.images"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    filename: str
    original_filename: str
    storage_path: str  # Object Storage path
    storage_url: str  # Object Storage URL
    svg_storage_url: str | None = None
    original_svg_content: str | None = None
    is_vector_graphic: bool = False
    has_png_derivative: bool = True
    file_size: int
    image_format: str
    width_px: int
    height_px: int
    page_number: int
    image_index: int
    image_type: ImageType
    ai_description: str | None = "Technical image"  # Default value
    ai_confidence: float = 0.5  # Default to 0.5 when Vision AI not used
    contains_text: bool = False
    ocr_text: str | None = None
    ocr_confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)
    file_hash: str
    figure_number: str | None = None  # Figure reference (e.g., "1", "2.1")
    figure_context: str | None = None  # Context text around figure
    manual_description: str | None = None  # Manual description override
    chunk_id: str | None = None  # Link to chunk if extracted from chunk

    # Phase 2: Context extraction fields
    context_caption: str | None = None  # Extracted caption/description
    page_header: str | None = None  # Page header text
    figure_reference: str | None = None  # Figure reference like "Fig. 1.2"
    related_error_codes: list[str] = Field(default_factory=list)  # Error codes in context
    related_products: list[str] = Field(default_factory=list)  # Product models in context
    surrounding_paragraphs: list[str] = Field(default_factory=list)  # Text around image
    context_embedding: list[float] | None = None  # Context embedding vector

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Intelligence Models
class IntelligenceChunkModel(BaseModel):
    """Intelligence chunk model for krai_intelligence.chunks"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    text_chunk: str
    chunk_index: int
    page_start: int
    page_end: int
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)  # JSONB
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingModel(BaseModel):
    """Embedding model for krai_intelligence.embeddings"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str
    embedding: list[float]  # 768-dimensional vector
    model_name: str
    model_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorCodeModel(BaseModel):
    """Error code model for krai_intelligence.error_codes"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    manufacturer_id: str | None = None
    error_code: str
    error_description: str = "No description available"
    solution_customer_text: str | None = None  # Level 1: basic user steps
    solution_agent_text: str | None = None  # Level 2: call-center / 2nd level
    solution_technician_text: str | None = None  # Level 3: on-site technician (preferred)
    page_number: int
    confidence_score: float = 0.0
    extraction_method: str
    requires_parts: bool = False
    estimated_fix_time_minutes: int | None = None
    severity_level: str = "low"
    parent_code: str | None = None
    is_category: bool = False
    chunk_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SearchAnalyticsModel(BaseModel):
    """Search analytics model for krai_intelligence.search_analytics"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    results_count: int
    processing_time_ms: float
    user_id: str | None = None
    session_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# System Models
class ProcessingQueueModel(BaseModel):
    """Processing queue model for krai_system.processing_queue"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    processor_name: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditLogModel(BaseModel):
    """Audit log model for krai_system.audit_log"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str
    entity_type: str
    entity_id: str
    user_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)  # JSONB
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SystemMetricsModel(BaseModel):
    """System metrics model for krai_system.system_metrics"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str
    metric_value: float
    metric_unit: str
    tags: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Defect Detection Models
class PrintDefectModel(BaseModel):
    """Print defect model for krai_content.print_defects"""

    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))
    image_id: str
    defect_type: str
    confidence: float
    suggested_solutions: list[str] = Field(default_factory=list)
    estimated_fix_time: str | None = None
    required_parts: list[str] = Field(default_factory=list)
    difficulty_level: str = "easy"
    related_error_codes: list[str] = Field(default_factory=list)
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# API Models
class DocumentUploadRequest(BaseModel):
    """Document upload request model"""

    filename: str
    file_content: bytes
    document_type: DocumentType | None = None
    language: str = "en"


class DocumentUploadResponse(BaseModel):
    """Document upload response model"""

    document_id: str
    status: ProcessingStatus
    message: str
    processing_time: float | None = None


class SearchRequest(BaseModel):
    """Search request model"""

    query: str
    document_types: list[DocumentType] | None = None
    manufacturers: list[str] | None = None
    models: list[str] | None = None
    limit: int = 10
    offset: int = 0


class SearchResponse(BaseModel):
    """Search response model"""

    results: list[dict[str, Any]]
    total_count: int
    processing_time_ms: float
    query: str


class DefectDetectionRequest(BaseModel):
    """Defect detection request model"""

    image_content: bytes
    image_format: str = "png"
    description: str | None = None


class DefectDetectionResponse(BaseModel):
    """Defect detection response model"""

    defect_type: str
    confidence: float
    suggested_solutions: list[str]
    estimated_fix_time: str | None = None
    required_parts: list[str] = Field(default_factory=list)
    difficulty_level: str = "easy"
    related_error_codes: list[str] = Field(default_factory=list)


# Multimodal Search Models
class MultimodalSearchRequest(BaseModel):
    """Multimodal search request model"""

    query: str
    content_types: list[str] = Field(default=["text", "image", "video", "table"], description="Content types to search")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)
    include_context: bool = Field(default=True)
    enable_two_stage: bool = Field(default=True)
    filters: dict[str, Any] = Field(default_factory=dict)


class MultimodalSearchResponse(BaseModel):
    """Multimodal search response model"""

    query: str
    results: list[dict[str, Any]]
    total_count: int
    processing_time_ms: float
    content_type_counts: dict[str, int]
    two_stage_used: bool
    context_enriched: bool


class TwoStageSearchRequest(BaseModel):
    """Two-stage search request model"""

    query: str
    first_stage_limit: int = Field(default=50, ge=10, le=200)
    final_limit: int = Field(default=10, ge=1, le=50)
    content_types: list[str] = Field(default=["text", "image"], description="Content types for two-stage")
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    rerank_enabled: bool = Field(default=True)
    context_boost: float = Field(default=0.2, ge=0.0, le=1.0)


class TwoStageSearchResponse(BaseModel):
    """Two-stage search response model"""

    query: str
    first_stage_count: int
    final_results: list[dict[str, Any]]
    total_count: int
    processing_time_ms: float
    reranking_time_ms: float
    threshold_used: float
