"""
Monitoring API - Real-time monitoring of pipeline stages and hardware usage
"""

from datetime import datetime
from typing import Any

import psutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.middleware.auth_middleware import require_permission
from backend.models.monitoring import (
    ActiveDocument,
    ActivityEntry,
    AlertListResponse,
    AlertRule,
    AlertSeverity,
    CreateAlertRule,
    DataQualityResponse,
    FailureEntry,
    PerformanceMetricsResponse,
    PipelineActivityResponse,
    PipelineStatusResponse,
    ProcessorHealthResponse,
    QueueStatusResponse,
    StageErrorLogsResponse,
    StageQueueResponse,
)
from backend.services.alert_service import AlertService
from backend.services.metrics_service import MetricsService
from backend.services.performance_service import PerformanceCollector

router = APIRouter()


# Global service instances will be initialized by app.py
# These functions are used as dependencies
async def get_metrics_service() -> MetricsService:
    """Get metrics service instance from app.py."""
    from backend.api.app import get_metrics_service as app_get_metrics

    return await app_get_metrics()


async def get_alert_service() -> AlertService:
    """Get alert service instance from app.py."""
    from backend.api.app import get_alert_service as app_get_alert

    return await app_get_alert()


async def get_performance_collector() -> PerformanceCollector:
    """Get performance collector instance from app.py."""
    from backend.api.app import get_performance_collector as app_get_performance

    return await app_get_performance()


class StageStatus(BaseModel):
    stage_name: str
    documents_processed: int
    is_active: bool
    last_activity: str
    current_document: str = ""


class HardwareStatus(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    gpu_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0


class PipelineStatus(BaseModel):
    total_documents: int
    documents_completed: int
    documents_in_progress: int
    current_stages: list[StageStatus]
    hardware: HardwareStatus
    processing_speed: float  # documents per minute
    estimated_completion: str


# Global monitoring data
monitoring_data = {
    "stages": {
        "upload": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "text": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "image": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "classification": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "metadata": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "storage": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "embedding": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
        "search": {"processed": 0, "active": False, "last_activity": "", "current_doc": ""},
    },
    "total_documents": 0,
    "documents_completed": 0,
    "start_time": None,
    "last_update": None,
}


def update_stage_status(stage_name: str, document_name: str = "", completed: bool = False):
    """Update stage status - called by pipeline workers"""
    global monitoring_data

    if stage_name in monitoring_data["stages"]:
        stage_data = monitoring_data["stages"][stage_name]
        stage_data["active"] = True
        stage_data["last_activity"] = datetime.now().strftime("%H:%M:%S")

        if document_name:
            stage_data["current_doc"] = document_name

        if completed:
            stage_data["processed"] += 1
            stage_data["active"] = False
            stage_data["current_doc"] = ""

            # Update total completed
            monitoring_data["documents_completed"] = sum(
                stage["processed"] for stage in monitoring_data["stages"].values()
            )

        monitoring_data["last_update"] = datetime.now()


def get_hardware_status() -> HardwareStatus:
    """Get current hardware status"""
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # RAM usage
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    ram_used_gb = (ram.total - ram.available) / 1024 / 1024 / 1024
    ram_total_gb = ram.total / 1024 / 1024 / 1024

    # GPU usage (simplified - would need nvidia-ml-py for real GPU monitoring)
    gpu_percent = 0.0
    gpu_memory_used_mb = 0.0
    gpu_memory_total_mb = 8192.0  # RTX 2000 has 8GB VRAM

    return HardwareStatus(
        cpu_percent=cpu_percent,
        ram_percent=ram_percent,
        ram_used_gb=ram_used_gb,
        ram_total_gb=ram_total_gb,
        gpu_percent=gpu_percent,
        gpu_memory_used_mb=gpu_memory_used_mb,
        gpu_memory_total_mb=gpu_memory_total_mb,
    )


def calculate_processing_speed() -> float:
    """Calculate documents per minute"""
    global monitoring_data

    if not monitoring_data["start_time"]:
        return 0.0

    elapsed_minutes = (datetime.now() - monitoring_data["start_time"]).total_seconds() / 60
    if elapsed_minutes == 0:
        return 0.0

    return monitoring_data["documents_completed"] / elapsed_minutes


def estimate_completion() -> str:
    """Estimate completion time"""
    global monitoring_data

    if monitoring_data["documents_completed"] == 0:
        return "Unknown"

    speed = calculate_processing_speed()
    if speed == 0:
        return "Unknown"

    remaining = monitoring_data["total_documents"] - monitoring_data["documents_completed"]
    minutes_remaining = remaining / speed

    if minutes_remaining < 60:
        return f"{minutes_remaining:.1f} minutes"
    hours = minutes_remaining / 60
    return f"{hours:.1f} hours"


@router.get("/status", response_model=PipelineStatus)
async def get_pipeline_status(current_user: dict[str, Any] = Depends(require_permission("monitoring:read"))):
    """Get current pipeline status (DEPRECATED: Use /pipeline instead)"""
    global monitoring_data

    # Get hardware status
    hardware = get_hardware_status()

    # Build stage status list
    current_stages = []
    for stage_name, stage_data in monitoring_data["stages"].items():
        current_stages.append(
            StageStatus(
                stage_name=stage_name,
                documents_processed=stage_data["processed"],
                is_active=stage_data["active"],
                last_activity=stage_data["last_activity"],
                current_document=stage_data["current_doc"],
            )
        )

    # Calculate documents in progress
    documents_in_progress = sum(1 for stage in monitoring_data["stages"].values() if stage["active"])

    return PipelineStatus(
        total_documents=monitoring_data["total_documents"],
        documents_completed=monitoring_data["documents_completed"],
        documents_in_progress=documents_in_progress,
        current_stages=current_stages,
        hardware=hardware,
        processing_speed=calculate_processing_speed(),
        estimated_completion=estimate_completion(),
    )


@router.get("/stages", response_model=list[StageStatus])
async def get_stage_status(current_user: dict[str, Any] = Depends(require_permission("monitoring:read"))):
    """Get detailed stage status (DEPRECATED: Use /pipeline instead)"""
    global monitoring_data

    stages = []
    for stage_name, stage_data in monitoring_data["stages"].items():
        stages.append(
            StageStatus(
                stage_name=stage_name,
                documents_processed=stage_data["processed"],
                is_active=stage_data["active"],
                last_activity=stage_data["last_activity"],
                current_document=stage_data["current_doc"],
            )
        )

    return stages


@router.get("/hardware", response_model=HardwareStatus)
async def get_hardware_status_endpoint(current_user: dict[str, Any] = Depends(require_permission("monitoring:read"))):
    """Get current hardware status (DEPRECATED: Use /metrics instead)"""
    return get_hardware_status()


@router.post("/reset")
async def reset_monitoring(current_user: dict[str, Any] = Depends(require_permission("monitoring:write"))):
    """Reset monitoring data (DEPRECATED: Admin only)"""
    global monitoring_data

    for stage_data in monitoring_data["stages"].values():
        stage_data["processed"] = 0
        stage_data["active"] = False
        stage_data["last_activity"] = ""
        stage_data["current_doc"] = ""

    monitoring_data["total_documents"] = 0
    monitoring_data["documents_completed"] = 0
    monitoring_data["start_time"] = datetime.now()
    monitoring_data["last_update"] = datetime.now()

    return {"message": "Monitoring data reset"}


@router.post("/start")
async def start_monitoring(
    total_documents: int, current_user: dict[str, Any] = Depends(require_permission("monitoring:write"))
):
    """Start monitoring for a batch (DEPRECATED: Admin only)"""
    global monitoring_data

    monitoring_data["total_documents"] = total_documents
    monitoring_data["start_time"] = datetime.now()
    monitoring_data["last_update"] = datetime.now()

    return {"message": f"Started monitoring for {total_documents} documents"}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitoring_active": monitoring_data["start_time"] is not None,
    }


# New monitoring endpoints


@router.get("/pipeline", response_model=PipelineStatusResponse)
async def get_pipeline_monitoring(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get comprehensive pipeline monitoring data."""
    pipeline_metrics = await metrics_svc.get_pipeline_metrics()
    stage_metrics = await metrics_svc.get_stage_metrics()
    hardware_status = await metrics_svc.get_hardware_metrics()

    return PipelineStatusResponse(
        pipeline_metrics=pipeline_metrics,
        stage_metrics=stage_metrics,
        hardware_status=hardware_status,
    )


# SQL constants extracted for testability — they query only tables we know exist.

ACTIVE_DOCUMENTS_SQL = """
    SELECT
        id::text AS document_id,
        filename,
        processing_status,
        stage_status,
        updated_at
    FROM krai_core.documents
    WHERE processing_status IN ('processing', 'pending')
    ORDER BY updated_at DESC NULLS LAST
    LIMIT $1
"""

RECENT_ACTIVITY_SQL = """
    SELECT
        document_id::text AS document_id,
        stage_name,
        status,
        started_at,
        completed_at,
        updated_at,
        error_message
    FROM krai_system.stage_tracking
    ORDER BY updated_at DESC NULLS LAST
    LIMIT $1
"""

RECENT_FAILURES_SQL = """
    SELECT
        error_id::text AS error_id,
        document_id::text AS document_id,
        stage_name,
        error_type,
        error_message,
        created_at
    FROM krai_system.pipeline_errors
    ORDER BY created_at DESC NULLS LAST
    LIMIT $1
"""


def _derive_current_stage_and_progress(stage_status_jsonb: Any) -> tuple[str | None, float]:
    """Return (current_stage, progress) from a documents.stage_status JSONB blob.

    Tolerates both structured payloads ({"stage": {"status": "completed"}})
    and legacy flat strings ({"stage": "completed"}). progress is the fraction
    of stages in 'completed' or 'skipped' state.
    """
    import json as _json

    if isinstance(stage_status_jsonb, str):
        try:
            stage_status_jsonb = _json.loads(stage_status_jsonb)
        except _json.JSONDecodeError:
            stage_status_jsonb = {}
    if not isinstance(stage_status_jsonb, dict) or not stage_status_jsonb:
        return None, 0.0

    completed = 0
    current_stage: str | None = None
    for stage_name, entry in stage_status_jsonb.items():
        status = entry.get("status") if isinstance(entry, dict) else entry
        status = (status or "").lower()
        if status in ("completed", "skipped"):
            completed += 1
        elif current_stage is None and status in ("processing", "running", "pending", "failed"):
            current_stage = stage_name

    total = len(stage_status_jsonb)
    progress = round(completed / total, 4) if total else 0.0
    return current_stage, progress


@router.get("/pipeline-activity", response_model=PipelineActivityResponse)
async def get_pipeline_activity(
    active_limit: int = 20,
    activity_limit: int = 50,
    failures_limit: int = 20,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Single source of truth for the Filament Pipeline Status page.

    Aggregates pipeline_metrics + active_documents + recent_activity +
    recent_failures from existing tables (krai_core.documents,
    krai_system.stage_tracking, krai_system.pipeline_errors).
    """
    pipeline_metrics = await metrics_svc.get_pipeline_metrics()

    async with metrics_svc.pool.acquire() as conn:
        active_rows = await conn.fetch(ACTIVE_DOCUMENTS_SQL, active_limit)
        activity_rows = await conn.fetch(RECENT_ACTIVITY_SQL, activity_limit)
        failure_rows = await conn.fetch(RECENT_FAILURES_SQL, failures_limit)

    active_documents: list[ActiveDocument] = []
    for row in active_rows:
        current_stage, progress = _derive_current_stage_and_progress(row.get("stage_status"))
        active_documents.append(
            ActiveDocument(
                document_id=row["document_id"],
                filename=row.get("filename") or "",
                processing_status=row.get("processing_status") or "unknown",
                current_stage=current_stage,
                progress=progress,
                updated_at=row.get("updated_at"),
            )
        )

    recent_activity: list[ActivityEntry] = []
    for row in activity_rows:
        timestamp = row.get("updated_at") or row.get("started_at") or row.get("completed_at")
        recent_activity.append(
            ActivityEntry(
                timestamp=timestamp,
                type="stage",
                document_id=row.get("document_id"),
                stage_name=row.get("stage_name"),
                status=row.get("status") or "unknown",
                message=row.get("error_message"),
            )
        )

    recent_failures: list[FailureEntry] = []
    for row in failure_rows:
        recent_failures.append(
            FailureEntry(
                error_id=row["error_id"],
                document_id=row.get("document_id"),
                stage_name=row.get("stage_name"),
                error_message=row.get("error_message"),
                error_type=row.get("error_type"),
                created_at=row.get("created_at"),
            )
        )

    return PipelineActivityResponse(
        pipeline_metrics=pipeline_metrics,
        active_documents=active_documents,
        recent_activity=recent_activity,
        recent_failures=recent_failures,
    )


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue_monitoring(
    limit: int = 100,
    status_filter: str | None = None,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get queue monitoring data."""
    queue_metrics = await metrics_svc.get_queue_metrics()
    queue_items = await metrics_svc.get_queue_items(limit, status_filter)

    return QueueStatusResponse(
        queue_metrics=queue_metrics,
        queue_items=queue_items,
    )


@router.get("/metrics")
async def get_aggregated_metrics(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict[str, Any]:
    """Get aggregated metrics for all systems."""
    pipeline_metrics = await metrics_svc.get_pipeline_metrics()
    queue_metrics = await metrics_svc.get_queue_metrics()
    hardware_metrics = await metrics_svc.get_hardware_metrics()

    return {
        "pipeline": pipeline_metrics.model_dump(),
        "queue": queue_metrics.model_dump(),
        "hardware": hardware_metrics.model_dump(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/data-quality", response_model=DataQualityResponse)
async def get_data_quality_metrics(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get data quality metrics."""
    return await metrics_svc.get_data_quality_metrics()


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    performance_collector: PerformanceCollector = Depends(get_performance_collector),
):
    """Get performance metrics with baseline comparison."""
    from backend.models.monitoring import PerformanceMetrics

    # Get all baselines from the performance collector
    baselines = await performance_collector.get_all_baselines()

    # Convert baselines to PerformanceMetrics objects
    stages = []
    improvements = []

    for baseline in baselines:
        stage_metrics = PerformanceMetrics(
            stage_name=baseline.get("stage_name", "unknown"),
            baseline_avg_seconds=baseline.get("baseline_avg_seconds"),
            current_avg_seconds=baseline.get("current_avg_seconds"),
            baseline_p50_seconds=baseline.get("baseline_p50_seconds"),
            current_p50_seconds=baseline.get("current_p50_seconds"),
            baseline_p95_seconds=baseline.get("baseline_p95_seconds"),
            current_p95_seconds=baseline.get("current_p95_seconds"),
            baseline_p99_seconds=baseline.get("baseline_p99_seconds"),
            current_p99_seconds=baseline.get("current_p99_seconds"),
            improvement_percentage=baseline.get("improvement_percentage"),
            measurement_date=baseline.get("measurement_date"),
        )
        stages.append(stage_metrics)

        # Collect improvement percentages for overall calculation
        if baseline.get("improvement_percentage") is not None:
            improvements.append(baseline["improvement_percentage"])

    # Calculate overall improvement as average of all stage improvements
    overall_improvement = None
    if improvements:
        overall_improvement = sum(improvements) / len(improvements)

    return PerformanceMetricsResponse(
        overall_improvement=overall_improvement,
        stages=stages,
        timestamp=datetime.utcnow(),
    )


# Processor-level monitoring endpoints


@router.get("/processors", response_model=ProcessorHealthResponse)
async def get_processor_health(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get processor health status for all stages."""
    processors = await metrics_svc.get_processor_health()
    return ProcessorHealthResponse(processors=processors)


@router.get("/stages/{stage_name}/queue", response_model=StageQueueResponse)
async def get_stage_queue(
    stage_name: str,
    limit: int = 50,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get queue items for a specific stage."""
    return await metrics_svc.get_stage_queue(stage_name, limit)


@router.get("/stages/{stage_name}/errors", response_model=StageErrorLogsResponse)
async def get_stage_errors(
    stage_name: str,
    limit: int = 100,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
):
    """Get error logs for a specific stage."""
    return await metrics_svc.get_stage_errors(stage_name, limit)


@router.post("/stages/{stage_name}/retry")
async def retry_stage_processing(
    stage_name: str,
    document_id: str,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:write")),
    metrics_svc: MetricsService = Depends(get_metrics_service),
) -> dict[str, Any]:
    """Retry a failed stage for a document."""
    success = await metrics_svc.retry_stage(document_id, stage_name)

    if not success:
        raise HTTPException(status_code=404, detail="Document or stage not found, or stage not in failed state")

    return {"success": True, "message": f"Stage {stage_name} retry triggered for document {document_id}"}


# Alert endpoints


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    limit: int = 50,
    severity: AlertSeverity | None = None,
    acknowledged: bool | None = None,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    alert_svc: AlertService = Depends(get_alert_service),
):
    """List alerts with optional filtering."""
    return await alert_svc.get_alerts(limit, severity, acknowledged)


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:write")),
    alert_svc: AlertService = Depends(get_alert_service),
) -> dict[str, Any]:
    """Acknowledge an alert."""
    user_id = current_user.get("id", "unknown")
    success = await alert_svc.acknowledge_alert(alert_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"success": True, "message": "Alert acknowledged"}


@router.delete("/alerts/{alert_id}")
async def dismiss_alert(
    alert_id: str,
    current_user: dict[str, Any] = Depends(require_permission("monitoring:write")),
    alert_svc: AlertService = Depends(get_alert_service),
) -> dict[str, Any]:
    """Dismiss (delete) an alert."""
    success = await alert_svc.dismiss_alert(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"success": True, "message": "Alert dismissed"}


# Alert rules endpoints


@router.get("/alert-rules", response_model=list[AlertRule])
async def list_alert_rules(
    current_user: dict[str, Any] = Depends(require_permission("monitoring:read")),
    alert_svc: AlertService = Depends(get_alert_service),
):
    """List all alert rules."""
    return await alert_svc.load_alert_rules()


@router.post("/alert-rules")
async def create_alert_rule(
    rule: CreateAlertRule,
    current_user: dict[str, Any] = Depends(require_permission("alerts:manage")),
    alert_svc: AlertService = Depends(get_alert_service),
) -> dict[str, Any]:
    """Create new alert rule (requires alerts:manage permission)."""
    rule_id = await alert_svc.add_alert_rule(rule)
    return {"success": True, "rule_id": rule_id}


@router.put("/alert-rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    updates: dict[str, Any],
    current_user: dict[str, Any] = Depends(require_permission("alerts:manage")),
    alert_svc: AlertService = Depends(get_alert_service),
) -> dict[str, Any]:
    """Update alert rule (requires alerts:manage permission)."""
    success = await alert_svc.update_alert_rule(rule_id, updates)

    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return {"success": True}


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    current_user: dict[str, Any] = Depends(require_permission("alerts:manage")),
    alert_svc: AlertService = Depends(get_alert_service),
) -> dict[str, Any]:
    """Delete alert rule (requires alerts:manage permission)."""
    success = await alert_svc.delete_alert_rule(rule_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    return {"success": True}
