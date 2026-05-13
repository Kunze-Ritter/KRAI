"""Video CRUD and enrichment API routes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from math import ceil
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.dependencies.database import get_database_pool
from api.middleware.auth_middleware import require_permission
from api.middleware.rate_limit_middleware import limiter, rate_limit_search, rate_limit_standard, rate_limit_upload
from api.routes.response_models import ErrorResponse, SuccessResponse
from models.document import DocumentResponse, PaginationParams, SortOrder
from models.manufacturer import ManufacturerResponse
from models.product import ProductResponse, ProductSeriesResponse
from models.video import (
    VideoCreateRequest,
    VideoEnrichmentRequest,
    VideoEnrichmentResponse,
    VideoFilterParams,
    VideoListResponse,
    VideoResponse,
    VideoSortParams,
    VideoUpdateRequest,
    VideoWithRelationsResponse,
)
from services.video_enrichment_service import VideoEnrichmentService

LOGGER = logging.getLogger("krai.api.videos")

router = APIRouter(prefix="/videos", tags=["videos"])


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


def _calculate_total_pages(total: int, page_size: int) -> int:
    return ceil(total / page_size) if total > 0 else 1


async def _fetch_document(pool: asyncpg.Pool, document_id: str | None) -> DocumentResponse | None:
    if not document_id:
        return None
    async with pool.acquire() as conn:
        result = await conn.fetchrow("SELECT * FROM krai_core.documents WHERE id = $1 LIMIT 1", document_id)
    if not result:
        return None
    return DocumentResponse(**dict(result))


async def _fetch_manufacturer(pool: asyncpg.Pool, manufacturer_id: str | None) -> ManufacturerResponse | None:
    if not manufacturer_id:
        return None
    async with pool.acquire() as conn:
        result = await conn.fetchrow("SELECT * FROM krai_core.manufacturers WHERE id = $1 LIMIT 1", manufacturer_id)
    if not result:
        return None
    return ManufacturerResponse(**dict(result))


async def _fetch_series(pool: asyncpg.Pool, series_id: str | None) -> ProductSeriesResponse | None:
    if not series_id:
        return None
    async with pool.acquire() as conn:
        result = await conn.fetchrow("SELECT * FROM krai_core.product_series WHERE id = $1 LIMIT 1", series_id)
    if not result:
        return None
    return ProductSeriesResponse(**dict(result))


async def _fetch_linked_products(pool: asyncpg.Pool, video_id: str) -> list[ProductResponse]:
    async with pool.acquire() as conn:
        links = await conn.fetch("SELECT product_id FROM krai_content.video_products WHERE video_id = $1", video_id)
    if not links:
        return []

    product_ids = [link["product_id"] for link in links]

    # Build IN query with proper parameter binding
    placeholders = ",".join([f"${i+1}" for i in range(len(product_ids))])
    async with pool.acquire() as conn:
        products = await conn.fetch(f"SELECT * FROM krai_core.products WHERE id IN ({placeholders})", *product_ids)
    return [ProductResponse(**dict(p)) for p in products] or []


async def _validate_foreign_keys(
    pool: asyncpg.Pool,
    *,
    manufacturer_id: str | None = None,
    series_id: str | None = None,
    document_id: str | None = None,
) -> None:
    if manufacturer_id:
        async with pool.acquire() as conn:
            manufacturer = await conn.fetchrow(
                "SELECT id FROM krai_core.manufacturers WHERE id = $1 LIMIT 1", manufacturer_id
            )
        if not manufacturer:
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Manufacturer with ID {manufacturer_id} not found",
                error="Invalid Manufacturer",
                error_code="MANUFACTURER_NOT_FOUND",
            )
    if series_id:
        async with pool.acquire() as conn:
            series = await conn.fetchrow("SELECT id FROM krai_core.product_series WHERE id = $1 LIMIT 1", series_id)
        if not series:
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Product series with ID {series_id} not found",
                error="Invalid Series",
                error_code="SERIES_NOT_FOUND",
            )
    if document_id:
        async with pool.acquire() as conn:
            document = await conn.fetchrow("SELECT id FROM krai_core.documents WHERE id = $1 LIMIT 1", document_id)
        if not document:
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Document with ID {document_id} not found",
                error="Invalid Document",
                error_code="DOCUMENT_NOT_FOUND",
            )


async def _build_relations(
    pool: asyncpg.Pool,
    record: dict[str, Any],
    include_relations: bool,
) -> VideoWithRelationsResponse:
    video = VideoResponse(**record)
    if not include_relations:
        return VideoWithRelationsResponse(**video.dict())

    return VideoWithRelationsResponse(
        **video.dict(),
        document=await _fetch_document(pool, record.get("document_id")),
        manufacturer=await _fetch_manufacturer(pool, record.get("manufacturer_id")),
        series=await _fetch_series(pool, record.get("series_id")),
        linked_products=await _fetch_linked_products(pool, record["id"]),
    )


async def _insert_audit_log(
    pool: asyncpg.Pool,
    *,
    record_id: str,
    operation: str,
    changed_by: str | None,
    new_values: dict[str, Any] | None = None,
    old_values: dict[str, Any] | None = None,
) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO krai_system.audit_log (table_name, record_id, operation, changed_by, new_values, old_values) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)",
                "videos",
                record_id,
                operation,
                changed_by,
                json.dumps(new_values) if new_values else None,
                json.dumps(old_values) if old_values else None,
            )
    except Exception as audit_exc:  # pragma: no cover
        LOGGER.warning("Audit log insert failed for video %s: %s", record_id, audit_exc)


async def _deduplicate_video(
    pool: asyncpg.Pool,
    payload: VideoCreateRequest,
) -> dict[str, Any] | None:
    if payload.youtube_id:
        async with pool.acquire() as conn:
            duplicate = await conn.fetchrow(
                "SELECT * FROM krai_content.videos WHERE youtube_id = $1 LIMIT 1", payload.youtube_id
            )
        if duplicate:
            return dict(duplicate)

    async with pool.acquire() as conn:
        duplicate = await conn.fetchrow(
            "SELECT * FROM krai_content.videos WHERE video_url = $1 LIMIT 1", str(payload.video_url)
        )
    return dict(duplicate) if duplicate else None


def _detect_content_type(filename: str) -> str | None:
    if "." not in filename:
        return None
    extension = filename.rsplit(".", 1)[1].lower()
    mapping = {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
        "webm": "video/webm",
    }
    return mapping.get(extension)


def _deserialize_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _serialize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return metadata


@router.get("", response_model=SuccessResponse[VideoListResponse])
@limiter.limit(rate_limit_search)
async def list_videos(
    request: Request,
    pagination: PaginationParams = Depends(),
    filters: VideoFilterParams = Depends(),
    sort: VideoSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("videos:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[VideoListResponse]:
    try:
        # Build SQL query with filters and pagination
        where_clauses = []
        params = []
        param_count = 0

        # Apply filters
        if filters.document_id:
            param_count += 1
            where_clauses.append(f"document_id = ${param_count}")
            params.append(filters.document_id)

        if filters.manufacturer_id:
            param_count += 1
            where_clauses.append(f"manufacturer_id = ${param_count}")
            params.append(filters.manufacturer_id)

        if filters.video_type:
            param_count += 1
            where_clauses.append(f"video_type = ${param_count}")
            params.append(filters.video_type.value)

        if filters.has_transcript is not None:
            param_count += 1
            where_clauses.append(f"has_transcript = ${param_count}")
            params.append(filters.has_transcript)

        if filters.has_ai_summary is not None:
            param_count += 1
            where_clauses.append(f"has_ai_summary = ${param_count}")
            params.append(filters.has_ai_summary)

        if filters.search:
            param_count += 1
            where_clauses.append(
                f"(title ILIKE ${param_count} OR description ILIKE ${param_count} OR ai_summary ILIKE ${param_count} OR transcript_text ILIKE ${param_count})"
            )
            search_term = f"%{filters.search}%"
            params.extend([search_term, search_term, search_term, search_term])
            param_count += 3

        where_clause = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Apply sorting
        order_direction = "DESC" if sort.sort_order == SortOrder.DESC else "ASC"
        order_clause = f" ORDER BY {sort.sort_by} {order_direction}"

        # Apply pagination
        offset = (pagination.page - 1) * pagination.page_size
        limit_clause = f" LIMIT {pagination.page_size} OFFSET {offset}"

        # Execute query
        query = f"""
            SELECT *, COUNT(*) OVER() as total_count
            FROM krai_content.videos
            {where_clause}
            {order_clause}
            {limit_clause}
        """

        async with pool.acquire() as conn:
            result = await conn.fetch(query, *params)

        # Get total count from first row or execute separate count query
        total = 0
        if result:
            total = result[0].get("total_count", len(result))
        else:
            # Fallback count query
            count_query = f"SELECT COUNT(*) as count FROM krai_content.videos{where_clause}"
            async with pool.acquire() as conn:
                count_result = await conn.fetch(count_query, *params)
            total = count_result[0].get("count", 0) if count_result else 0

        LOGGER.info(
            "Listed videos page=%s size=%s total=%s",
            pagination.page,
            pagination.page_size,
            total,
        )

        payload = VideoListResponse(
            videos=[VideoResponse(**dict(item)) for item in result or []],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=_calculate_total_pages(total, pagination.page_size),
        )
        return SuccessResponse(data=payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/{video_id}",
    response_model=SuccessResponse[VideoWithRelationsResponse],
)
@limiter.limit(rate_limit_standard)
async def get_video(
    request: Request,
    video_id: str,
    include_relations: bool = Query(False),
    current_user: dict[str, Any] = Depends(require_permission("videos:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[VideoWithRelationsResponse]:
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT * FROM krai_content.videos WHERE id = $1 LIMIT 1", video_id)
        if not result:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Video not found", "VIDEO_NOT_FOUND"),
            )

        enriched = await _build_relations(pool, dict(result), include_relations)
        return SuccessResponse(data=enriched)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "",
    response_model=SuccessResponse[VideoResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(rate_limit_upload)
async def create_video(
    request: Request,
    payload: VideoCreateRequest,
    current_user: dict[str, Any] = Depends(require_permission("videos:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[VideoResponse]:
    try:
        await _validate_foreign_keys(
            pool,
            manufacturer_id=payload.manufacturer_id,
            series_id=payload.series_id,
            document_id=payload.document_id,
        )

        duplicate = await _deduplicate_video(pool, payload)
        if duplicate:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=_error_response(
                    "Conflict",
                    "Video already exists with the provided identifier or URL.",
                    "VIDEO_DUPLICATE",
                ),
            )

        now = datetime.now(UTC).isoformat()
        record_dict = payload.model_dump(exclude_none=True)
        record_dict["created_at"] = now
        record_dict["updated_at"] = now

        # Build INSERT query dynamically
        columns = list(record_dict.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = list(record_dict.values())

        query = f"INSERT INTO krai_content.videos ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        async with pool.acquire() as conn:
            result = await conn.fetchrow(query, *values)

        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to create video"),
            )

        result_dict = dict(result)
        video_id = result_dict["id"]
        LOGGER.info("Created video %s", video_id)
        await _insert_audit_log(
            pool,
            record_id=video_id,
            operation="INSERT",
            changed_by=current_user.get("id"),
            new_values=result_dict,
        )
        return SuccessResponse(data=VideoResponse(**result_dict))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.put(
    "/{video_id}",
    response_model=SuccessResponse[VideoResponse],
)
@limiter.limit(rate_limit_standard)
async def update_video(
    request: Request,
    video_id: str,
    payload: VideoUpdateRequest,
    current_user: dict[str, Any] = Depends(require_permission("videos:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[VideoResponse]:
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM krai_content.videos WHERE id = $1 LIMIT 1", video_id)
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Video not found", "VIDEO_NOT_FOUND"),
            )

        existing_dict = dict(existing)
        update_payload = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not update_payload:
            return SuccessResponse(data=VideoResponse(**existing_dict))

        await _validate_foreign_keys(
            pool,
            manufacturer_id=update_payload.get("manufacturer_id"),
            series_id=update_payload.get("series_id"),
            document_id=update_payload.get("document_id"),
        )

        update_payload["updated_at"] = datetime.now(UTC).isoformat()

        # Build dynamic UPDATE query
        set_clauses = []
        params = []
        param_count = 0

        for key, value in update_payload.items():
            param_count += 1
            set_clauses.append(f"{key} = ${param_count}")
            params.append(value)

        param_count += 1
        params.append(video_id)

        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                f"UPDATE krai_content.videos SET {', '.join(set_clauses)} WHERE id = ${param_count} RETURNING *",
                *params,
            )

        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to update video"),
            )

        result_dict = dict(result)
        LOGGER.info("Updated video %s", video_id)
        await _insert_audit_log(
            pool,
            record_id=video_id,
            operation="UPDATE",
            changed_by=current_user.get("id"),
            new_values=result_dict,
            old_values=existing_dict,
        )
        return SuccessResponse(data=VideoResponse(**result_dict))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "/enrich",
    response_model=SuccessResponse[VideoEnrichmentResponse],
)
@limiter.limit(rate_limit_upload)
async def enrich_video(
    request: Request,
    payload: VideoEnrichmentRequest,
    current_user: dict[str, Any] = Depends(require_permission("videos:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[VideoEnrichmentResponse]:
    try:
        service = VideoEnrichmentService()
        result = await service.enrich_video_url(
            url=str(payload.video_url),
            document_id=payload.document_id,
            manufacturer_id=payload.manufacturer_id,
        )
        success = bool(result.get("saved")) or bool(result.get("database_id"))
        response_payload = VideoEnrichmentResponse(
            success=success and "error" not in result,
            video_id=result.get("database_id"),
            title=result.get("title"),
            platform=result.get("platform"),
            duration=result.get("duration"),
            error=result.get("error"),
        )
        return SuccessResponse(data=response_payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
