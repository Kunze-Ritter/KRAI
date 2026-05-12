"""
Document processing endpoints — stage control, reprocess, status.
Mounted under /api/v1 in app.py.
All responses wrapped in SuccessResponse. Laravel reads $data['data'][...].
"""

from __future__ import annotations

import json
import logging

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from api.dependencies.database import get_database_pool
from api.middleware.auth_middleware import require_permission
from api.routes.response_models import (
    DocumentProcessingStatusResponse,
    StageListResponse,
    StageProcessingRequest,
    StageProcessingResponse,
    SuccessResponse,
    ThumbnailGenerationRequest,
    VideoProcessingRequest,
)
from core.types import ProcessingContext
from models.document import CANONICAL_STAGES
from processors.thumbnail_processor import ThumbnailProcessor
from services.video_enrichment_service import VideoEnrichmentService

logger = logging.getLogger("krai.api.document_processing")

router = APIRouter(tags=["document-processing"])


@router.get("/stages/names")
async def get_stage_names(
    _: dict = Depends(require_permission("documents:read")),
) -> SuccessResponse[StageListResponse]:
    """Return the global list of canonical stage names (not document-scoped)."""
    return SuccessResponse(data=StageListResponse(stages=CANONICAL_STAGES, total=len(CANONICAL_STAGES)))


def _entry_status_value(entry) -> str:
    """Read a stage_status entry — structured dict or legacy flat string —
    and return the plain status string (lowercased, with 'running' → 'processing')."""
    if isinstance(entry, dict):
        raw = entry.get("status", "")
    else:
        raw = str(entry or "")
    raw = raw.lower()
    return "processing" if raw == "running" else raw


def _summarize_stage_status(stage_status: dict) -> dict:
    """Count stages by status across the union of CANONICAL_STAGES + any extra
    stages present in the JSONB (e.g. video_enrichment).
    """
    summary = {"completed": 0, "processing": 0, "failed": 0, "pending": 0, "skipped": 0}
    seen = set()
    for stage_name, entry in stage_status.items():
        seen.add(stage_name)
        bucket = _entry_status_value(entry)
        if bucket in summary:
            summary[bucket] += 1
        else:
            summary["pending"] += 1
    # Account for canonical stages not yet present in the JSONB as 'pending'
    for stage in CANONICAL_STAGES:
        if stage not in seen:
            summary["pending"] += 1
            seen.add(stage)
    summary["total"] = sum(v for k, v in summary.items() if k != "total")
    return summary


@router.get("/documents/{document_id}/status")
async def get_document_status(
    document_id: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:read")),
) -> SuccessResponse[DocumentProcessingStatusResponse]:
    """Return document processing status. Derives current_stage/progress/summary
    from stage_status JSONB and queue position from krai_system.processing_queue."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, processing_status, stage_status FROM krai_core.documents WHERE id = $1",
            document_id,
        )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    raw_stage_status: dict = {}
    if row["stage_status"]:
        raw = row["stage_status"]
        try:
            raw_stage_status = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            logger.warning("Malformed stage_status JSONB for document %s — treating as empty", document_id)
            raw_stage_status = {}

    # Derive current_stage: first canonical stage that is not completed/skipped
    current_stage: str | None = None
    completed_count = 0
    for stage in CANONICAL_STAGES:
        bucket = _entry_status_value(raw_stage_status.get(stage, ""))
        if bucket in ("completed", "skipped"):
            completed_count += 1
        else:
            current_stage = stage
            break
    progress = round(completed_count / len(CANONICAL_STAGES), 4) if CANONICAL_STAGES else 0.0

    stage_summary = _summarize_stage_status(raw_stage_status)

    # Queue position: ahead of this document in the pending queue
    async with pool.acquire() as conn:
        queue_position = (
            await conn.fetchval(
                """
            SELECT COUNT(*) FROM krai_system.processing_queue
            WHERE status = 'pending'
              AND created_at < COALESCE(
                  (SELECT MIN(created_at) FROM krai_system.processing_queue
                   WHERE document_id = $1::uuid AND status = 'pending'),
                  NOW()
              )
            """,
                document_id,
            )
            or 0
        )
        total_queue_items = (
            await conn.fetchval("SELECT COUNT(*) FROM krai_system.processing_queue WHERE status = 'pending'") or 0
        )

    return SuccessResponse(
        data=DocumentProcessingStatusResponse(
            document_id=document_id,
            status=row["processing_status"] or "unknown",
            current_stage=current_stage,
            progress=progress,
            queue_position=int(queue_position),
            total_queue_items=int(total_queue_items),
            stage_summary=stage_summary,
        )
    )


async def _run_pipeline_stages(document_id: str, stages: list[str], pipeline) -> None:
    """Background task: run pipeline stages for a document."""
    try:
        await pipeline.run_stages(document_id, stages)
    except Exception as exc:
        logger.error("Background pipeline failed for %s: %s", document_id, exc, exc_info=True)


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:write")),
):
    """Reset document state and trigger full pipeline reprocessing."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM krai_core.documents WHERE id = $1", document_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        await conn.execute(
            "UPDATE krai_core.documents SET processing_status = 'pending', stage_status = '{}'::jsonb WHERE id = $1",
            document_id,
        )
        try:
            await conn.execute("DELETE FROM krai_system.stage_tracking WHERE document_id = $1", document_id)
        except Exception as exc:
            logger.debug("Could not delete stage_tracking for %s (table may not exist): %s", document_id, exc)
        try:
            await conn.execute("DELETE FROM krai_system.completion_markers WHERE document_id = $1", document_id)
        except Exception as exc:
            logger.debug("Could not delete completion_markers for %s (table may not exist): %s", document_id, exc)

    pipeline = request.app.state.pipeline
    background_tasks.add_task(_run_pipeline_stages, document_id, CANONICAL_STAGES, pipeline)

    return SuccessResponse(data={"message": "Reprocessing queued", "document_id": document_id, "status": "pending"})


@router.post("/documents/{document_id}/process/stage/{stage_name}")
async def process_single_stage(
    document_id: str,
    stage_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:write")),
):
    """Queue a single pipeline stage as a background task."""
    if stage_name not in CANONICAL_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown stage '{stage_name}'. Valid: {', '.join(CANONICAL_STAGES)}",
        )
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM krai_core.documents WHERE id = $1", document_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    pipeline = request.app.state.pipeline
    background_tasks.add_task(_run_pipeline_stages, document_id, [stage_name], pipeline)

    return SuccessResponse(data={"stage": stage_name, "status": "queued", "document_id": document_id})


@router.post("/documents/{document_id}/process/stages")
async def process_multiple_stages(
    document_id: str,
    body: StageProcessingRequest,
    request: Request,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:write")),
) -> SuccessResponse[StageProcessingResponse]:
    """Run multiple pipeline stages synchronously and return aggregated results."""
    invalid_stages = [stage for stage in body.stages if stage not in CANONICAL_STAGES]
    if invalid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown stages: {', '.join(invalid_stages)}. Valid: {', '.join(CANONICAL_STAGES)}",
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM krai_core.documents WHERE id = $1", document_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    pipeline = request.app.state.pipeline
    original_force_continue = getattr(pipeline, "force_continue_on_errors", True)
    pipeline.force_continue_on_errors = not body.stop_on_error
    try:
        raw_result = await pipeline.run_stages(document_id, body.stages)
    finally:
        pipeline.force_continue_on_errors = original_force_continue

    raw_stage_results = raw_result.get("stage_results", [])
    stage_results = []
    for index, item in enumerate(raw_stage_results):
        if isinstance(item, dict):
            normalized = dict(item)
            if index < len(body.stages):
                normalized.setdefault("stage", body.stages[index])
            normalized.setdefault("success", False)
            normalized.setdefault("processing_time", 0.0)
            stage_results.append(normalized)
        else:
            stage_results.append(item)
    total_stages = len(body.stages)
    successful = int(raw_result.get("successful", sum(1 for item in stage_results if item.get("success"))))
    failed = int(raw_result.get("failed", max(total_stages - successful, 0)))
    success_rate = successful / total_stages if total_stages else 0.0

    return SuccessResponse(
        data=StageProcessingResponse(
            success=bool(raw_result.get("success", failed == 0)),
            total_stages=total_stages,
            successful=successful,
            failed=failed,
            stage_results=stage_results,
            success_rate=success_rate,
        )
    )


@router.post("/documents/{document_id}/process/video")
async def process_video(
    document_id: str,
    body: VideoProcessingRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:write")),
):
    """Enrich a single video URL and return the resulting metadata."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM krai_core.documents WHERE id = $1", document_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    service = VideoEnrichmentService()
    result = await service.enrich_video_url(
        str(body.video_url),
        document_id=document_id,
        manufacturer_id=body.manufacturer_id,
    )

    if result.get("error") and not result.get("video_id"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result["error"]),
        )

    return SuccessResponse(
        data={
            "video_id": result.get("video_id"),
            "title": result.get("title"),
            "platform": result.get("platform"),
            "thumbnail_url": result.get("thumbnail_url"),
            "duration": result.get("duration"),
            "channel_title": result.get("channel_title"),
        }
    )


@router.post("/documents/{document_id}/process/thumbnail")
async def process_thumbnail(
    document_id: str,
    body: ThumbnailGenerationRequest,
    request: Request,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _: dict = Depends(require_permission("documents:write")),
):
    """Generate a thumbnail for the document and persist it to object storage."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, storage_path, document_type FROM krai_core.documents WHERE id = $1",
            document_id,
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage_service = request.app.state.storage_service
    if storage_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage not available",
        )

    storage_path = row["storage_path"] or ""
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no file path for thumbnail generation",
        )

    processor = ThumbnailProcessor(request.app.state.db_adapter, storage_service)
    context = ProcessingContext(
        document_id=document_id,
        file_path=storage_path,
        file_hash="",
        document_type=row["document_type"] or "service_manual",
        language="en",
        processing_config={
            "size": body.size or [300, 400],
            "page": body.page or 0,
        },
    )
    result = await processor.process(context)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result.error),
        )

    data = result.data or {}
    return SuccessResponse(
        data={
            "thumbnail_url": data.get("thumbnail_url"),
            "size": data.get("size") or body.size or [300, 400],
            "file_size": data.get("file_size"),
        }
    )
