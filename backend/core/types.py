"""
Core Type Definitions for KR-AI-Engine Pipeline

This module contains shared type definitions used across the pipeline to avoid
circular import dependencies between modules.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ProcessingStatus(Enum):
    """Processing status enumeration"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Stage(Enum):
    """Canonical stage names for pipeline processors."""

    UPLOAD = "upload"
    TEXT_EXTRACTION = "text_extraction"
    TABLE_EXTRACTION = "table_extraction"  # Stage 2b: Table Processor → krai_intelligence.structured_tables
    SVG_PROCESSING = "svg_processing"  # Stage 3a: SVG Processor → Convert vector graphics to PNG
    IMAGE_PROCESSING = "image_processing"
    VISUAL_EMBEDDING = "visual_embedding"  # Stage 3b: Visual Embedding Processor → krai_intelligence.unified_embeddings (source_type='image')
    LINK_EXTRACTION = "link_extraction"
    CHUNK_PREPROCESSING = "chunk_prep"
    CLASSIFICATION = "classification"
    METADATA_EXTRACTION = "metadata_extraction"
    PARTS_EXTRACTION = "parts_extraction"
    SERIES_DETECTION = "series_detection"
    STORAGE = "storage"
    EMBEDDING = "embedding"  # Stage 7: Embedding Processor → krai_intelligence.chunks (with embedding column) + unified_embeddings (source_type='text')
    SEARCH_INDEXING = "search_indexing"
    VIDEO_ENRICHMENT = "video_enrichment"


@dataclass
class ProcessingContext:
    """Context information for processing operations

    Extended with Phase 5 context extraction support:
    - page_texts: Page text from TextProcessor (key: page_number, value: text)
    - images/tables/links/videos: Extracted media with context metadata
    - pdf_path: Alias for file_path for clarity
    """

    document_id: str
    file_path: str
    document_type: str
    manufacturer: str | None = None
    model: str | None = None
    series: str | None = None
    version: str | None = None
    language: str = "en"
    processing_config: dict[str, Any] | None = None
    file_hash: str | None = None
    metadata: dict[str, Any] | None = None
    file_size: int | None = None
    # Phase 5: Context extraction fields
    page_texts: dict[int, str] | None = None  # Page text from TextProcessor
    pdf_path: str | None = None  # PDF path (alias for file_path)
    images: list[dict[str, Any]] | None = None  # Extracted images with context
    tables: list[dict[str, Any]] | None = None  # Extracted tables with context
    links: list[dict[str, Any]] | None = None  # Extracted links with context
    videos: list[dict[str, Any]] | None = None  # Extracted videos with context
    chunks: list[dict[str, Any]] | None = None  # Extracted text chunks for embedding/search stages
    # Retry and error tracking fields
    request_id: str | None = None  # Unique identifier for the processing request
    correlation_id: str | None = None  # Correlation ID for tracking across retries (format: req_id.stage_name.retry_N)
    retry_attempt: int = 0  # Current retry attempt number (0 = first attempt)
    error_id: str | None = None  # Unique error identifier from error logging system

    def __post_init__(self):
        if self.processing_config is None:
            self.processing_config = {}
        # Auto-populate pdf_path from file_path for clarity
        if self.pdf_path is None:
            self.pdf_path = self.file_path


class ProcessingError(Exception):
    """Custom exception for processing errors"""

    def __init__(self, message: str, processor: str, error_code: str | None = None):
        self.message = message
        self.processor = processor
        self.error_code = error_code
        super().__init__(f"[{processor}] {message}")


@dataclass
class ProcessingResult:
    """Result of a processing operation"""

    success: bool
    processor: str
    status: ProcessingStatus
    data: dict[str, Any]
    metadata: dict[str, Any]
    error: ProcessingError | None = None
    processing_time: float = 0.0
    timestamp: datetime | None = None
    error_id: str | None = None  # Unique error identifier from error logging system
    correlation_id: str | None = None  # Correlation ID for error tracking
    retry_attempt: int = 0  # Retry attempt number when this result was produced

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
