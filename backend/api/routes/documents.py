"""
Document CRUD API routes.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from math import ceil
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from api.dependencies.database import get_database_pool
from api.middleware.auth_middleware import require_permission
from api.middleware.rate_limit_middleware import limiter, rate_limit_search, rate_limit_standard, rate_limit_upload
from api.routes.response_models import ErrorResponse, SuccessResponse
from models.document import (
    CANONICAL_STAGES,
    DocumentCreateRequest,
    DocumentFilterParams,
    DocumentListResponse,
    DocumentResponse,
    DocumentSortParams,
    DocumentStageDetail,
    DocumentStageStatusResponse,
    DocumentStatsResponse,
    DocumentUpdateRequest,
    PaginationParams,
    SortOrder,
    StageStatus,
)

LOGGER = logging.getLogger("krai.api.documents")

router = APIRouter(prefix="/documents", tags=["documents"])


class MessagePayload(BaseModel):
    """Payload carrying a textual message."""

    message: str


def _apply_document_filters(query: Any, filters: DocumentFilterParams) -> Any:
    """Apply filter parameters to the database query."""
    if filters.manufacturer_id:
        query = query.eq("manufacturer_id", filters.manufacturer_id)
    if filters.product_id:
        query = query.eq("product_id", filters.product_id)
    if filters.document_type:
        query = query.eq("document_type", filters.document_type)
    if filters.language:
        query = query.eq("language", filters.language)
    if filters.processing_status:
        query = query.eq("processing_status", filters.processing_status)
    if filters.search:
        search = filters.search
        query = query.or_(f"filename.ilike.%{search}%," f"manufacturer.ilike.%{search}%," f"series.ilike.%{search}%")
    return query


def _apply_sorting(query: Any, sort: DocumentSortParams) -> Any:
    """Apply sorting parameters to the database query."""
    return query.order(sort.sort_by, desc=sort.sort_order == SortOrder.DESC)


def _apply_pagination(query: Any, pagination: PaginationParams) -> Any:
    """Apply pagination parameters to the database query."""
    start_index = (pagination.page - 1) * pagination.page_size
    end_index = start_index + pagination.page_size - 1
    return query.range(start_index, end_index)


def _calculate_total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 1
    return ceil(total / page_size)


def _error_response(
    error: str,
    detail: str | None = None,
    error_code: str | None = None,
) -> dict[str, str | None]:
    return ErrorResponse(error=error, detail=detail, error_code=error_code).dict()


def _log_and_raise(
    status_code: int,
    message: str,
    *,
    error: str = "Error",
    error_code: str | None = None,
) -> None:
    LOGGER.error(message)
    raise HTTPException(
        status_code=status_code,
        detail=_error_response(error=error, detail=message, error_code=error_code),
    )


@router.get(
    "",
    response_model=SuccessResponse[DocumentListResponse],
)
@limiter.limit(rate_limit_search)
async def list_documents(
    request: Request,
    pagination: PaginationParams = Depends(),
    filters: DocumentFilterParams = Depends(),
    sort: DocumentSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("documents:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentListResponse]:
    """List documents with pagination, filtering, and sorting."""
    try:
        # Build SQL query with filters and pagination
        where_clauses = []
        params = []
        param_count = 0

        # Apply filters
        if filters.manufacturer_id:
            param_count += 1
            where_clauses.append(f"manufacturer_id = ${param_count}")
            params.append(filters.manufacturer_id)

        if filters.processing_status:
            param_count += 1
            where_clauses.append(f"processing_status = ${param_count}")
            params.append(filters.processing_status)

        where_clause = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Apply sorting
        order_clause = f" ORDER BY {sort.sort_by} {sort.sort_order.value}"

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        limit_clause = f" LIMIT {pagination.page_size} OFFSET {offset}"

        # Execute query
        query = f"""
            SELECT *, COUNT(*) OVER() as total_count
            FROM krai_core.documents
            {where_clause}
            {order_clause}
            {limit_clause}
        """

        async with pool.acquire() as conn:
            result = await conn.fetch(query, *params)

        # Get total count from first row or execute separate count query
        total_count = 0
        if result:
            total_count = result[0].get("total_count", len(result))
        else:
            # Fallback count query
            count_query = f"SELECT COUNT(*) as count FROM krai_core.documents{where_clause}"
            async with pool.acquire() as conn:
                count_result = await conn.fetch(count_query, *params)
            total_count = count_result[0].get("count", 0) if count_result else 0

        return SuccessResponse(
            data=DocumentListResponse(
                documents=result or [],
                total=total_count,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=ceil(total_count / pagination.page_size) if pagination.page_size > 0 else 0,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/by-document/{document_id}",
    response_model=SuccessResponse[DocumentListResponse],
)
@limiter.limit(rate_limit_search)
async def get_error_codes_by_document(
    request: Request,
    document_id: str,
    pagination: PaginationParams = Depends(),
    filters: DocumentFilterParams = Depends(),
    sort: DocumentSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("documents:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentListResponse]:
    """List error codes by document with pagination, filtering, and sorting."""
    try:
        # For now, return empty response as this seems to be an error codes by document endpoint
        # This would need to be properly implemented based on the actual requirements
        return SuccessResponse(
            data=DocumentListResponse(
                documents=[],
                total=0,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=0,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
)
@limiter.limit(rate_limit_standard)
async def get_document(
    request: Request,
    document_id: str,
    current_user: dict[str, Any] = Depends(require_permission("documents:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentResponse]:
    """Retrieve a single document by ID."""
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT * FROM krai_core.documents WHERE id = $1 LIMIT 1", document_id)

        if not result:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Document not found", "DOCUMENT_NOT_FOUND"),
            )

        LOGGER.info("Retrieved document %s", document_id)
        return SuccessResponse(data=DocumentResponse(**dict(result)))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "",
    response_model=SuccessResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(rate_limit_upload)
async def create_document(
    request: Request,
    payload: DocumentCreateRequest,
    current_user: dict[str, Any] = Depends(require_permission("documents:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentResponse]:
    """Create a new document record."""
    try:
        # Detect duplicate file hash
        async with pool.acquire() as conn:
            duplicate_check = await conn.fetchrow(
                "SELECT id FROM krai_core.documents WHERE file_hash = $1 LIMIT 1", payload.file_hash
            )

        if duplicate_check:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=_error_response(
                    "Conflict",
                    "Document with this hash already exists",
                    error_code="DOCUMENT_DUPLICATE",
                ),
            )

        now = datetime.now(UTC).isoformat()
        document_dict = payload.dict(exclude_none=True)
        document_dict["created_at"] = now
        document_dict["updated_at"] = now

        # Build INSERT query dynamically
        columns = list(document_dict.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = list(document_dict.values())

        query = f"INSERT INTO krai_core.documents ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        async with pool.acquire() as conn:
            result = await conn.fetchrow(query, *values)

        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to create document"),
            )

        result_dict = dict(result)
        document_id = result_dict["id"]
        LOGGER.info("Created document %s", document_id)

        # Audit log
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO krai_system.audit_log (table_name, record_id, operation, changed_by, new_values) VALUES ($1, $2, $3, $4, $5::jsonb)",
                    "documents",
                    document_id,
                    "INSERT",
                    current_user.get("id"),
                    json.dumps(document_dict),
                )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log insert failed for document %s: %s", document_id, audit_exc)

        return SuccessResponse(data=DocumentResponse(**result))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.put(
    "/{document_id}",
    response_model=SuccessResponse[DocumentResponse],
)
@limiter.limit(rate_limit_standard)
async def update_document(
    request: Request,
    document_id: str,
    payload: DocumentUpdateRequest,
    current_user: dict[str, Any] = Depends(require_permission("documents:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentResponse]:
    """Update an existing document."""
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM krai_core.documents WHERE id = $1 LIMIT 1", document_id)

        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Document not found", "DOCUMENT_NOT_FOUND"),
            )

        existing_dict = dict(existing)
        update_payload = payload.dict(exclude_unset=True, exclude_none=True)
        update_payload["updated_at"] = datetime.now(UTC).isoformat()

        # Build UPDATE query dynamically
        set_clauses = []
        params = []
        param_count = 0

        for key, value in update_payload.items():
            param_count += 1
            set_clauses.append(f"{key} = ${param_count}")
            params.append(value)

        param_count += 1
        params.append(document_id)

        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                f"UPDATE krai_core.documents SET {', '.join(set_clauses)} WHERE id = ${param_count} RETURNING *",
                *params,
            )

        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to update document"),
            )

        LOGGER.info("Updated document %s", document_id)

        # Audit log
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO krai_system.audit_log (table_name, record_id, operation, changed_by, old_values, new_values) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)",
                    "documents",
                    document_id,
                    "UPDATE",
                    current_user.get("id"),
                    json.dumps(existing_dict),
                    json.dumps(update_payload),
                )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log update failed for document %s: %s", document_id, audit_exc)

        return SuccessResponse(data=DocumentResponse(**result))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.delete(
    "/{document_id}",
    response_model=SuccessResponse[MessagePayload],
)
@limiter.limit(rate_limit_standard)
async def delete_document(
    request: Request,
    document_id: str,
    current_user: dict[str, Any] = Depends(require_permission("documents:delete")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[MessagePayload]:
    """Delete a document by ID."""
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM krai_core.documents WHERE id = $1 LIMIT 1", document_id)

        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Document not found", "DOCUMENT_NOT_FOUND"),
            )

        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM krai_system.processing_queue WHERE document_id = $1", document_id)
            await conn.execute("DELETE FROM krai_system.link_scraping_jobs WHERE document_id = $1", document_id)
            await conn.execute("DELETE FROM krai_content.videos WHERE document_id = $1", document_id)
            await conn.execute("DELETE FROM krai_core.documents WHERE id = $1", document_id)
        LOGGER.info("Deleted document %s", document_id)

        # Audit log
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO krai_system.audit_log (table_name, record_id, operation, changed_by, old_values) VALUES ($1, $2, $3, $4, $5::jsonb)",
                    "documents",
                    document_id,
                    "DELETE",
                    current_user.get("id"),
                    json.dumps(dict(existing)),
                )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log delete failed for document %s: %s", document_id, audit_exc)

        return SuccessResponse(data=MessagePayload(message="Document deleted successfully"))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/stats",
    response_model=SuccessResponse[DocumentStatsResponse],
)
@limiter.limit(rate_limit_search)
async def get_document_stats(
    request: Request,
    current_user: dict[str, Any] = Depends(require_permission("documents:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentStatsResponse]:
    """Return aggregated document statistics."""
    try:
        async with pool.acquire() as conn:
            total_result = await conn.fetch("SELECT COUNT(*) as count FROM krai_core.documents")
        total_documents = total_result[0].get("count", 0) if total_result else 0

        async with pool.acquire() as conn:
            type_result = await conn.fetch(
                "SELECT document_type, COUNT(*) as count FROM krai_core.documents GROUP BY document_type"
            )
        by_type: dict[str, int] = {
            item.get("document_type"): int(item.get("count", 0))
            for item in type_result or []
            if item.get("document_type")
        }

        async with pool.acquire() as conn:
            status_result = await conn.fetch(
                "SELECT processing_status, COUNT(*) as count FROM krai_core.documents GROUP BY processing_status"
            )
        by_status: dict[str, int] = {
            item.get("processing_status"): int(item.get("count", 0))
            for item in status_result or []
            if item.get("processing_status")
        }

        async with pool.acquire() as conn:
            manufacturer_result = await conn.fetch(
                "SELECT manufacturer, COUNT(*) as count FROM krai_core.documents GROUP BY manufacturer"
            )
        by_manufacturer: dict[str, int] = {
            item.get("manufacturer"): int(item.get("count", 0))
            for item in manufacturer_result or []
            if item.get("manufacturer")
        }

        LOGGER.info(
            "Document stats computed totals=%s types=%s statuses=%s manufacturers=%s",
            total_documents,
            len(by_type),
            len(by_status),
            len(by_manufacturer),
        )

        return SuccessResponse(
            data=DocumentStatsResponse(
                total_documents=total_documents,
                by_type=by_type,
                by_status=by_status,
                by_manufacturer=by_manufacturer,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


def _parse_stage_status(stage_status_jsonb: dict[str, Any] | None) -> dict[str, DocumentStageDetail]:
    """Parse stage_status JSONB into structured DocumentStageDetail objects."""
    if isinstance(stage_status_jsonb, str):
        try:
            stage_status_jsonb = json.loads(stage_status_jsonb)
        except json.JSONDecodeError:
            stage_status_jsonb = {}

    stages = {}

    for stage_name in CANONICAL_STAGES:
        if stage_status_jsonb and stage_name in stage_status_jsonb:
            raw_stage_data = stage_status_jsonb[stage_name]
            if isinstance(raw_stage_data, str):
                stage_data = {"status": raw_stage_data}
            elif isinstance(raw_stage_data, dict):
                stage_data = raw_stage_data
            else:
                stage_data = {}

            # Parse status
            status_str = stage_data.get("status", "pending")
            try:
                stage_status = StageStatus(status_str)
            except ValueError:
                stage_status = StageStatus.PENDING

            # Calculate duration if both timestamps exist
            duration_seconds = None
            started_at = stage_data.get("started_at")
            completed_at = stage_data.get("completed_at")
            if started_at and completed_at:
                try:
                    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    duration_seconds = (end - start).total_seconds()
                except (ValueError, AttributeError):
                    pass

            stages[stage_name] = DocumentStageDetail(
                status=stage_status,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                progress=stage_data.get("progress", 100 if stage_status == StageStatus.COMPLETED else 0),
                error=stage_data.get("error"),
                metadata=stage_data.get("metadata", {}),
            )
        else:
            # Default to pending for stages not in JSONB
            stages[stage_name] = DocumentStageDetail(status=StageStatus.PENDING, progress=0)

    return stages


@router.get(
    "/{document_id}/stages",
    response_model=SuccessResponse[DocumentStageStatusResponse],
)
@limiter.limit(rate_limit_standard)
async def get_document_stages(
    request: Request,
    response: Response,
    document_id: str,
    current_user: dict[str, Any] = Depends(require_permission("documents:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[DocumentStageStatusResponse]:
    """Get stage-level processing status for a document."""
    try:
        # Query document with stage_status
        query = """
            SELECT id, filename, stage_status, updated_at,
                   krai_core.get_document_progress(id) as overall_progress,
                   krai_core.get_current_stage(id) as current_stage
            FROM krai_core.documents
            WHERE id = $1
        """
        async with pool.acquire() as conn:
            result = await conn.fetchrow(query, document_id)

        if not result:
            _log_and_raise(
                status.HTTP_404_NOT_FOUND,
                f"Document {document_id} not found",
                error="Document not found",
                error_code="DOCUMENT_NOT_FOUND",
            )

        doc = dict(result)
        stage_status_jsonb = doc.get("stage_status", {})

        # Parse stages
        stages = _parse_stage_status(stage_status_jsonb)

        # Check if any failed stages can be retried
        can_retry = any(stage.status == StageStatus.FAILED for stage in stages.values())

        # Get overall progress (default to 0 if function returns None)
        overall_progress = doc.get("overall_progress") or 0.0

        # Get current stage (default to first stage if None)
        current_stage = doc.get("current_stage") or CANONICAL_STAGES[0]

        LOGGER.info(
            "Retrieved stage status for document=%s progress=%.1f%% current_stage=%s",
            document_id,
            overall_progress,
            current_stage,
        )

        return SuccessResponse(
            data=DocumentStageStatusResponse(
                document_id=str(doc["id"]),
                filename=doc["filename"],
                overall_progress=overall_progress,
                current_stage=current_stage,
                stages=stages,
                can_retry=can_retry,
                last_updated=(
                    doc["updated_at"].isoformat() if isinstance(doc["updated_at"], datetime) else doc["updated_at"]
                ),
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Failed to get document stages for document_id=%s", document_id)
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "/{document_id}/stages/{stage_name}/retry",
    response_model=SuccessResponse[MessagePayload],
)
@limiter.limit(rate_limit_standard)
async def retry_document_stage(
    request: Request,
    document_id: str,
    stage_name: str,
    current_user: dict[str, Any] = Depends(require_permission("documents:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[MessagePayload]:
    """Retry a failed stage for a document."""
    try:
        # Validate stage name
        if stage_name not in CANONICAL_STAGES:
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid stage name: {stage_name}",
                error="Invalid stage name",
                error_code="INVALID_STAGE_NAME",
            )

        # Check if document exists and stage is failed
        query = """
            SELECT id, filename, stage_status
            FROM krai_core.documents
            WHERE id = $1
        """
        async with pool.acquire() as conn:
            result = await conn.fetchrow(query, document_id)

        if not result:
            _log_and_raise(
                status.HTTP_404_NOT_FOUND,
                f"Document {document_id} not found",
                error="Document not found",
                error_code="DOCUMENT_NOT_FOUND",
            )

        doc = dict(result)
        stage_status_jsonb = doc.get("stage_status", {})

        # Check if stage is failed
        stage_data = stage_status_jsonb.get(stage_name, {})
        if stage_data.get("status") != "failed":
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Stage {stage_name} is not in failed state",
                error="Stage not failed",
                error_code="STAGE_NOT_FAILED",
            )

        # Reset stage to pending
        update_query = """
            UPDATE krai_core.documents
            SET stage_status = jsonb_set(
                COALESCE(stage_status, '{}'::jsonb),
                $1,
                $2
            ),
            updated_at = NOW()
            WHERE id = $3
        """

        reset_stage_data = {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "progress": 0,
            "error": None,
            "metadata": {},
        }

        async with pool.acquire() as conn:
            await conn.execute(update_query, [stage_name], reset_stage_data, document_id)  # JSONB path  # New value

        # Enqueue in processing queue
        enqueue_query = """
            INSERT INTO krai_system.processing_queue (document_id, task_type, priority, status)
            VALUES ($1, $2, 5, 'pending')
        """
        async with pool.acquire() as conn:
            await conn.execute(enqueue_query, document_id, stage_name)

        LOGGER.info(
            "Stage retry triggered: document=%s stage=%s user=%s",
            document_id,
            stage_name,
            current_user.get("id", "unknown"),
        )

        # TODO: Broadcast WebSocket event STAGE_RETRY_TRIGGERED
        # This will be implemented in the WebSocket service integration

        return SuccessResponse(
            data=MessagePayload(message=f"Stage '{stage_name}' retry triggered for document {doc['filename']}")
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Failed to retry stage: document_id=%s stage=%s", document_id, stage_name)
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
