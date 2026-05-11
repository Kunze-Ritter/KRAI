"""Pydantic models for monitoring and metrics."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Pipeline Monitoring Models
class PipelineMetrics(BaseModel):
    """Pipeline metrics for monitoring."""

    total_documents: int = Field(..., description="Total number of documents")
    documents_pending: int = Field(..., description="Documents pending processing")
    documents_processing: int = Field(..., description="Documents currently processing")
    documents_completed: int = Field(..., description="Documents completed successfully")
    documents_failed: int = Field(..., description="Documents that failed processing")
    success_rate: float = Field(..., description="Success rate percentage (0-100)")
    avg_processing_time_seconds: float = Field(..., description="Average processing time in seconds")
    current_throughput_docs_per_hour: float = Field(..., description="Current throughput in documents per hour")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_documents": 1000,
                "documents_pending": 50,
                "documents_processing": 10,
                "documents_completed": 920,
                "documents_failed": 20,
                "success_rate": 97.87,
                "avg_processing_time_seconds": 45.3,
                "current_throughput_docs_per_hour": 80.0,
            }
        },
    )


class StageMetrics(BaseModel):
    """Stage-specific metrics."""

    stage_name: str = Field(..., description="Name of the processing stage")
    pending_count: int = Field(..., description="Documents pending in this stage")
    processing_count: int = Field(..., description="Documents currently processing in this stage")
    completed_count: int = Field(..., description="Documents completed in this stage")
    failed_count: int = Field(..., description="Documents failed in this stage")
    skipped_count: int = Field(..., description="Documents skipped in this stage")
    avg_duration_seconds: float = Field(..., description="Average duration in seconds")
    success_rate: float = Field(..., description="Success rate percentage (0-100)")
    is_active: bool = Field(False, description="True if processing_count > 0 or last activity < 60s")
    last_activity: datetime | None = Field(None, description="Timestamp of last stage activity")
    current_document_id: str | None = Field(None, description="ID of currently processing document")
    error_count_last_hour: int = Field(0, description="Number of errors in last hour")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "stage_name": "text_extraction",
                "pending_count": 5,
                "processing_count": 2,
                "completed_count": 950,
                "failed_count": 10,
                "skipped_count": 3,
                "avg_duration_seconds": 12.5,
                "success_rate": 98.96,
                "is_active": True,
                "last_activity": "2025-12-07T14:30:00Z",
                "current_document_id": "doc-123",
                "error_count_last_hour": 2,
            }
        },
    )


class ProcessorHealthStatus(BaseModel):
    """Processor-level health status."""

    processor_name: str = Field(..., description="Processor name (e.g., 'UploadProcessor', 'TextProcessor')")
    stage_name: str = Field(..., description="Stage name (e.g., 'upload', 'text_extraction')")
    status: str = Field(..., description="Status: 'running', 'idle', 'failed', 'degraded'")
    is_active: bool = Field(..., description="True if processor is actively processing")
    documents_processing: int = Field(..., description="Number of documents currently processing")
    documents_in_queue: int = Field(..., description="Number of documents in queue")
    last_activity: datetime | None = Field(None, description="Timestamp of last activity")
    current_document_id: str | None = Field(None, description="ID of currently processing document")
    error_rate_percent: float = Field(..., description="Error rate in last hour (0-100)")
    avg_processing_time_seconds: float = Field(..., description="Average processing time in seconds")
    health_score: float = Field(..., description="Health score (0-100)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "processor_name": "TextProcessor",
                "stage_name": "text_extraction",
                "status": "running",
                "is_active": True,
                "documents_processing": 3,
                "documents_in_queue": 15,
                "last_activity": "2025-12-07T14:30:00Z",
                "current_document_id": "doc-456",
                "error_rate_percent": 2.5,
                "avg_processing_time_seconds": 12.3,
                "health_score": 95.0,
            }
        },
    )


class ProcessorHealthResponse(BaseModel):
    """Processor health response."""

    processors: list[ProcessorHealthStatus]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class StageQueueResponse(BaseModel):
    """Stage queue response."""

    stage_name: str = Field(..., description="Stage name")
    queue_items: list[QueueItem] = Field(..., description="Queue items")
    pending_count: int = Field(..., description="Number of pending items")
    processing_count: int = Field(..., description="Number of processing items")
    avg_wait_time_seconds: float = Field(..., description="Average wait time in seconds")
    oldest_item_age_seconds: float = Field(..., description="Age of oldest item in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class StageErrorLog(BaseModel):
    """Stage error log entry."""

    id: str = Field(..., description="Error log ID")
    document_id: str = Field(..., description="Document ID")
    stage_name: str = Field(..., description="Stage name")
    error_message: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code")
    stack_trace: str | None = Field(None, description="Stack trace")
    occurred_at: datetime = Field(..., description="When error occurred")
    retry_count: int = Field(..., description="Number of retries")
    can_retry: bool = Field(..., description="Whether retry is possible")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "error-001",
                "document_id": "doc-789",
                "stage_name": "text_extraction",
                "error_message": "OCR failed: Invalid PDF structure",
                "error_code": "OCR_FAILED",
                "stack_trace": "Traceback...",
                "occurred_at": "2025-12-07T14:25:00Z",
                "retry_count": 1,
                "can_retry": True,
            }
        },
    )


class StageErrorLogsResponse(BaseModel):
    """Stage error logs response."""

    stage_name: str = Field(..., description="Stage name")
    errors: list[StageErrorLog] = Field(..., description="Error logs")
    total_errors: int = Field(..., description="Total number of errors")
    error_rate_percent: float = Field(..., description="Error rate percentage (0-100)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class HardwareStatus(BaseModel):
    """Hardware status metrics."""

    cpu_percent: float = Field(..., description="CPU usage percentage")
    ram_percent: float = Field(..., description="RAM usage percentage")
    ram_available_gb: float = Field(..., description="Available RAM in GB")
    gpu_available: bool = Field(..., description="GPU availability")
    gpu_percent: float | None = Field(None, description="GPU usage percentage")
    gpu_memory_used_gb: float | None = Field(None, description="GPU memory used in GB")
    gpu_memory_total_gb: float | None = Field(None, description="Total GPU memory in GB")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "cpu_percent": 45.2,
                "ram_percent": 62.5,
                "ram_available_gb": 12.3,
                "gpu_available": True,
                "gpu_percent": 78.5,
                "gpu_memory_used_gb": 6.2,
                "gpu_memory_total_gb": 8.0,
            }
        },
    )


class PipelineStatusResponse(BaseModel):
    """Complete pipeline status response."""

    pipeline_metrics: PipelineMetrics
    stage_metrics: list[StageMetrics]
    hardware_status: HardwareStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# Pipeline activity (single source of truth for the Filament Pipeline Status page)


class ActiveDocument(BaseModel):
    """A document currently moving through the pipeline."""

    document_id: str
    filename: str
    processing_status: str
    current_stage: str | None = None
    progress: float = Field(0.0, ge=0.0, le=1.0)
    updated_at: datetime | None = None


class ActivityEntry(BaseModel):
    """A single recent stage transition."""

    timestamp: datetime | None = None
    type: str = Field(..., description="'stage' | 'failure'")
    document_id: str | None = None
    stage_name: str | None = None
    status: str
    message: str | None = None


class FailureEntry(BaseModel):
    """A single recent pipeline failure."""

    error_id: str
    document_id: str | None = None
    stage_name: str | None = None
    error_message: str | None = None
    error_type: str | None = None
    created_at: datetime | None = None


class PipelineActivityResponse(BaseModel):
    """Single source of truth for the Filament Pipeline Status page.

    Derived entirely from existing tables (krai_core.documents,
    krai_system.stage_tracking, krai_system.pipeline_errors) so the page no
    longer needs to merge three independent endpoints client-side.
    """

    pipeline_metrics: PipelineMetrics
    active_documents: list[ActiveDocument] = Field(default_factory=list)
    recent_activity: list[ActivityEntry] = Field(default_factory=list)
    recent_failures: list[FailureEntry] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# Queue Monitoring Models
class QueueItem(BaseModel):
    """Queue item details."""

    id: str = Field(..., description="Queue item ID")
    task_type: str = Field(..., description="Type of task")
    status: str = Field(..., description="Current status")
    priority: int = Field(..., description="Task priority")
    document_id: str | None = Field(None, description="Associated document ID")
    scheduled_at: datetime = Field(..., description="When task was scheduled")
    started_at: datetime | None = Field(None, description="When task started")
    retry_count: int = Field(0, description="Number of retries")
    error_message: str | None = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "task_type": "document_processing",
                "status": "pending",
                "priority": 5,
                "document_id": "doc-123",
                "scheduled_at": "2025-11-02T08:00:00Z",
                "started_at": None,
                "retry_count": 0,
                "error_message": None,
            }
        },
    )


class QueueMetrics(BaseModel):
    """Queue metrics."""

    total_items: int = Field(..., description="Total items in queue")
    pending_count: int = Field(..., description="Pending items")
    processing_count: int = Field(..., description="Currently processing items")
    completed_count: int = Field(..., description="Completed items")
    failed_count: int = Field(..., description="Failed items")
    avg_wait_time_seconds: float = Field(..., description="Average wait time in seconds")
    by_task_type: dict[str, int] = Field(..., description="Item count by task type")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_items": 150,
                "pending_count": 45,
                "processing_count": 10,
                "completed_count": 90,
                "failed_count": 5,
                "avg_wait_time_seconds": 125.5,
                "by_task_type": {"document_processing": 100, "batch_delete": 30, "batch_update": 20},
            }
        },
    )


class QueueStatusResponse(BaseModel):
    """Queue status response."""

    queue_metrics: QueueMetrics
    queue_items: list[QueueItem]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# Data Quality Models
class DuplicateMetrics(BaseModel):
    """Duplicate detection metrics."""

    total_duplicates: int = Field(..., description="Total duplicate documents")
    duplicate_by_hash: int = Field(..., description="Duplicates detected by file hash")
    duplicate_by_filename: int = Field(..., description="Duplicates detected by filename")
    duplicate_documents: list[dict[str, Any]] = Field(..., description="List of duplicate document details")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_duplicates": 15,
                "duplicate_by_hash": 12,
                "duplicate_by_filename": 3,
                "duplicate_documents": [
                    {"file_hash": "abc123", "count": 3, "filenames": ["doc1.pdf", "doc2.pdf", "doc3.pdf"]}
                ],
            }
        },
    )


class ValidationMetrics(BaseModel):
    """Validation error metrics."""

    total_validation_errors: int = Field(..., description="Total validation errors")
    errors_by_stage: dict[str, int] = Field(..., description="Error count by stage")
    documents_with_errors: list[dict[str, Any]] = Field(..., description="Documents with validation errors")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_validation_errors": 8,
                "errors_by_stage": {"text_extraction": 3, "classification": 2, "embedding": 3},
                "documents_with_errors": [
                    {"document_id": "doc-456", "stage": "text_extraction", "error": "OCR failed"}
                ],
            }
        },
    )


class ProcessingMetrics(BaseModel):
    """Processing performance metrics."""

    total_processed: int = Field(..., description="Total documents processed")
    successful: int = Field(..., description="Successfully processed documents")
    failed: int = Field(..., description="Failed documents")
    success_rate: float = Field(..., description="Success rate percentage (0-100)")
    avg_processing_time: float = Field(..., description="Average processing time in seconds")
    processing_by_type: dict[str, int] = Field(..., description="Processing count by document type")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_processed": 1000,
                "successful": 970,
                "failed": 30,
                "success_rate": 97.0,
                "avg_processing_time": 45.3,
                "processing_by_type": {"service_manual": 600, "user_guide": 300, "technical_spec": 100},
            }
        },
    )


class DataQualityResponse(BaseModel):
    """Data quality response."""

    duplicate_metrics: DuplicateMetrics
    validation_metrics: ValidationMetrics
    processing_metrics: ProcessingMetrics
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


# Alert Models
class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Alert types."""

    PROCESSING_FAILURE = "processing_failure"
    QUEUE_OVERFLOW = "queue_overflow"
    HARDWARE_THRESHOLD = "hardware_threshold"
    DATA_QUALITY = "data_quality"
    SYSTEM_ERROR = "system_error"


class AlertRule(BaseModel):
    """Alert rule configuration."""

    id: str | None = Field(None, description="Rule ID (auto-generated on creation)")
    name: str = Field(..., description="Rule name")
    alert_type: AlertType = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity")
    threshold_value: float = Field(..., description="Threshold value")
    threshold_operator: str = Field(..., description="Comparison operator (>, <, ==, >=, <=)")
    metric_key: str | None = Field(
        None, description="Specific metric to monitor (e.g., 'cpu', 'ram', 'duplicates', 'validation_errors')"
    )
    enabled: bool = Field(True, description="Whether rule is enabled")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "rule-001",
                "name": "High Failure Rate",
                "alert_type": "processing_failure",
                "severity": "high",
                "threshold_value": 10.0,
                "threshold_operator": ">",
                "enabled": True,
            }
        },
    )


class CreateAlertRule(BaseModel):
    """Alert rule creation DTO (without ID)."""

    name: str = Field(..., description="Rule name")
    alert_type: AlertType = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity")
    threshold_value: float = Field(..., description="Threshold value")
    threshold_operator: str = Field(..., description="Comparison operator (>, <, ==, >=, <=)")
    metric_key: str | None = Field(
        None, description="Specific metric to monitor (e.g., 'cpu', 'ram', 'duplicates', 'validation_errors')"
    )
    enabled: bool = Field(True, description="Whether rule is enabled")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "High Failure Rate",
                "alert_type": "processing_failure",
                "severity": "high",
                "threshold_value": 10.0,
                "threshold_operator": ">",
                "enabled": True,
            }
        },
    )


class Alert(BaseModel):
    """Alert instance."""

    id: str = Field(..., description="Alert ID")
    alert_type: AlertType = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    triggered_at: datetime = Field(..., description="When alert was triggered")
    acknowledged: bool = Field(False, description="Whether alert is acknowledged")
    acknowledged_at: datetime | None = Field(None, description="When alert was acknowledged")
    acknowledged_by: str | None = Field(None, description="User who acknowledged alert")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "alert-001",
                "alert_type": "processing_failure",
                "severity": "high",
                "title": "High Processing Failure Rate",
                "message": "Processing failure rate is 12.5%, exceeding threshold of 10%",
                "metadata": {"current_value": 12.5, "threshold": 10.0},
                "triggered_at": "2025-11-02T08:30:00Z",
                "acknowledged": False,
                "acknowledged_at": None,
                "acknowledged_by": None,
            }
        },
    )


class AlertListResponse(BaseModel):
    """Alert list response."""

    alerts: list[Alert]
    total: int = Field(..., description="Total number of alerts")
    unacknowledged_count: int = Field(..., description="Number of unacknowledged alerts")

    model_config = ConfigDict(from_attributes=True)


# WebSocket Models
class WebSocketEvent(str, Enum):
    """WebSocket event types."""

    PIPELINE_UPDATE = "pipeline_update"
    QUEUE_UPDATE = "queue_update"
    HARDWARE_UPDATE = "hardware_update"
    ALERT_TRIGGERED = "alert_triggered"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    PROCESSOR_STATE_CHANGE = "processor_state_change"


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str = Field(..., description="Message type")
    data: dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "type": "pipeline_update",
                "data": {"total_documents": 1000, "documents_completed": 920},
                "timestamp": "2025-11-02T08:30:00Z",
            }
        },
    )


class PerformanceMetrics(BaseModel):
    """Performance metrics for a single pipeline stage."""

    stage_name: str = Field(..., description="Name of the pipeline stage")
    baseline_avg_seconds: float | None = Field(None, description="Baseline average processing time in seconds")
    current_avg_seconds: float | None = Field(None, description="Current average processing time in seconds")
    baseline_p50_seconds: float | None = Field(None, description="Baseline P50 processing time in seconds")
    current_p50_seconds: float | None = Field(None, description="Current P50 processing time in seconds")
    baseline_p95_seconds: float | None = Field(None, description="Baseline P95 processing time in seconds")
    current_p95_seconds: float | None = Field(None, description="Current P95 processing time in seconds")
    baseline_p99_seconds: float | None = Field(None, description="Baseline P99 processing time in seconds")
    current_p99_seconds: float | None = Field(None, description="Current P99 processing time in seconds")
    improvement_percentage: float | None = Field(None, description="Performance improvement percentage")
    measurement_date: datetime | None = Field(None, description="Date of measurement")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "stage_name": "text_extraction",
                "baseline_avg_seconds": 2.5,
                "current_avg_seconds": 1.8,
                "baseline_p50_seconds": 2.3,
                "current_p50_seconds": 1.7,
                "baseline_p95_seconds": 3.2,
                "current_p95_seconds": 2.1,
                "baseline_p99_seconds": 4.1,
                "current_p99_seconds": 2.8,
                "improvement_percentage": 28.0,
                "measurement_date": "2025-01-23T08:00:00Z",
            }
        },
    )


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics endpoint."""

    overall_improvement: float | None = Field(None, description="Average improvement across all stages")
    stages: list[PerformanceMetrics] = Field(default_factory=list, description="Per-stage performance metrics")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "overall_improvement": 25.5,
                "stages": [
                    {
                        "stage_name": "text_extraction",
                        "baseline_avg_seconds": 2.5,
                        "current_avg_seconds": 1.8,
                        "improvement_percentage": 28.0,
                    }
                ],
                "timestamp": "2025-01-23T08:00:00Z",
            }
        },
    )
