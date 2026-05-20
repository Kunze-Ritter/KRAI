"""Image CRUD and storage API routes."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from math import ceil
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel

from backend.api.dependencies.database import get_database_adapter, get_database_pool
from backend.api.middleware.auth_middleware import require_permission
from backend.api.routes.response_models import ErrorResponse, SuccessResponse
from backend.models.document import DocumentResponse, PaginationParams, SortOrder
from backend.models.image import (
    BucketType,
    ImageFilterParams,
    ImageListResponse,
    ImageResponse,
    ImageSortParams,
    ImageStatsResponse,
    ImageUpdateRequest,
    ImageUploadResponse,
    ImageWithRelationsResponse,
)
from backend.services.storage_factory import create_storage_service

LOGGER = logging.getLogger("krai.api.images")

router = APIRouter(prefix="/images", tags=["images"])

MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024


class MessagePayload(BaseModel):
    """Simple message payload for delete responses."""

    message: str
    deleted_from_storage: bool = False


ALLOWED_BUCKETS = {
    BucketType.DOCUMENT_IMAGES,
    BucketType.ERROR_IMAGES,
    BucketType.PARTS_IMAGES,
}


def _infer_bucket_type_from_url(storage_url: str | None) -> str:
    """Helper function to get public URL."""

    def get_public_url(bucket_type: str) -> str:
        var_name = f"OBJECT_STORAGE_PUBLIC_URL_{bucket_type.upper()}"
        return os.getenv(var_name, "")

    public_documents = get_public_url("documents")
    public_error = get_public_url("error")
    public_parts = get_public_url("parts")

    if storage_url and public_error and storage_url.startswith(public_error):
        return "error_images"
    if storage_url and public_parts and storage_url.startswith(public_parts):
        return "parts_images"
    if storage_url and public_documents and storage_url.startswith(public_documents):
        return "document_images"
    return "document_images"


def _guess_media_type(filename: str | None, image_format: str | None) -> str:
    if image_format:
        return f"image/{image_format.lower()}"
    if filename and "." in filename:
        extension = filename.rsplit(".", 1)[-1].lower()
        return f"image/{extension}"
    return "application/octet-stream"


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


async def _fetch_chunk(pool: asyncpg.Pool, chunk_id: str | None) -> dict[str, Any] | None:
    if not chunk_id:
        return None
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT text_chunk,page_start,page_end FROM krai_intelligence.chunks WHERE id = $1 LIMIT 1", chunk_id
        )
    if not result:
        return None
    return dict(result)


async def _build_relations(
    pool: asyncpg.Pool,
    record: dict[str, Any],
    include_relations: bool,
) -> ImageWithRelationsResponse:
    image = ImageResponse(**record)
    if not include_relations:
        return ImageWithRelationsResponse(**image.dict())

    return ImageWithRelationsResponse(
        **image.dict(),
        document=await _fetch_document(pool, record.get("document_id")),
        chunk=await _fetch_chunk(pool, record.get("chunk_id")),
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
                "images",
                record_id,
                operation,
                changed_by,
                json.dumps(new_values) if new_values else None,
                json.dumps(old_values) if old_values else None,
            )
    except Exception as audit_exc:  # pragma: no cover
        LOGGER.warning("Audit log insert failed for image %s: %s", record_id, audit_exc)


async def _validate_foreign_keys(
    pool: asyncpg.Pool,
    *,
    document_id: str | None = None,
    chunk_id: str | None = None,
) -> None:
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
    if chunk_id:
        async with pool.acquire() as conn:
            chunk = await conn.fetchrow("SELECT id FROM krai_intelligence.chunks WHERE id = $1 LIMIT 1", chunk_id)
        if not chunk:
            _log_and_raise(
                status.HTTP_400_BAD_REQUEST,
                f"Chunk with ID {chunk_id} not found",
                error="Invalid Chunk",
                error_code="CHUNK_NOT_FOUND",
            )


async def _deduplicate_hash(pool: asyncpg.Pool, file_hash: str | None) -> dict[str, Any] | None:
    if not file_hash:
        return None
    async with pool.acquire() as conn:
        result = await conn.fetchrow("SELECT * FROM krai_content.images WHERE file_hash = $1 LIMIT 1", file_hash)
    if not result:
        return None
    return dict(result)


def _map_bucket(bucket: str | None) -> BucketType:
    if not bucket:
        return BucketType.DOCUMENT_IMAGES
    try:
        candidate = BucketType(bucket)
        if candidate not in ALLOWED_BUCKETS:
            raise ValueError
        return candidate
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_error_response(
                "Invalid Bucket",
                f"Unsupported bucket type '{bucket}'.",
                "INVALID_BUCKET",
            ),
        )


def _decode_upload(file: UploadFile) -> bytes:
    content = file.file.read()
    file.file.seek(0)
    return content


def _determine_bucket(bucket: str | None) -> str:
    mapped = _map_bucket(bucket)
    return mapped.value


def _calculate_stats(records: list[dict[str, Any]]) -> ImageStatsResponse:
    by_type: dict[str, int] = {}
    by_document: dict[str, int] = {}
    total = len(records)
    with_ocr = 0
    with_ai = 0

    for record in records:
        image_type = record.get("image_type")
        if image_type:
            by_type[image_type] = by_type.get(image_type, 0) + 1
        document_id = record.get("document_id")
        if document_id:
            by_document[document_id] = by_document.get(document_id, 0) + 1
        if record.get("ocr_text"):
            with_ocr += 1
        if record.get("ai_description"):
            with_ai += 1

    return ImageStatsResponse(
        total_images=total,
        by_type=by_type,
        by_document=by_document,
        with_ocr_text=with_ocr,
        with_ai_description=with_ai,
    )


@router.get("", response_model=SuccessResponse[ImageListResponse])
async def list_images(
    pagination: PaginationParams = Depends(),
    filters: ImageFilterParams = Depends(),
    sort: ImageSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("images:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[ImageListResponse]:
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

        if filters.bucket_type:
            param_count += 1
            where_clauses.append(f"bucket_type = ${param_count}")
            params.append(filters.bucket_type.value)

        if filters.has_ocr_text is not None:
            param_count += 1
            where_clauses.append(f"has_ocr_text = ${param_count}")
            params.append(filters.has_ocr_text)

        if filters.has_ai_description is not None:
            param_count += 1
            where_clauses.append(f"has_ai_description = ${param_count}")
            params.append(filters.has_ai_description)

        if filters.search:
            search_term = f"%{filters.search}%"
            placeholders = []
            for _ in range(4):
                param_count += 1
                placeholders.append(f"${param_count}")
                params.append(search_term)
            where_clauses.append(
                f"(filename ILIKE {placeholders[0]} OR original_filename ILIKE {placeholders[1]} OR ai_description ILIKE {placeholders[2]} OR ocr_text ILIKE {placeholders[3]})"
            )

        if filters.file_size_min is not None:
            param_count += 1
            where_clauses.append(f"file_size >= ${param_count}")
            params.append(filters.file_size_min)

        if filters.file_size_max is not None:
            param_count += 1
            where_clauses.append(f"file_size <= ${param_count}")
            params.append(filters.file_size_max)

        if filters.date_from:
            param_count += 1
            where_clauses.append(f"created_at::date >= ${param_count}::date")
            params.append(filters.date_from)

        if filters.date_to:
            param_count += 1
            where_clauses.append(f"created_at::date <= ${param_count}::date")
            params.append(filters.date_to)

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
            FROM krai_content.images
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
            count_query = f"SELECT COUNT(*) as count FROM krai_content.images{where_clause}"
            async with pool.acquire() as conn:
                count_result = await conn.fetch(count_query, *params)
            total = count_result[0].get("count", 0) if count_result else 0

        LOGGER.info(
            "Listed images page=%s size=%s total=%s",
            pagination.page,
            pagination.page_size,
            total,
        )

        payload = ImageListResponse(
            images=[ImageResponse(**dict(item)) for item in result or []],
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
    "/{image_id}",
    response_model=SuccessResponse[ImageWithRelationsResponse],
)
async def get_image(
    image_id: str,
    include_relations: bool = Query(False),
    current_user: dict[str, Any] = Depends(require_permission("images:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[ImageWithRelationsResponse]:
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT * FROM krai_content.images WHERE id = $1 LIMIT 1", image_id)
        if not result:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Image not found", "IMAGE_NOT_FOUND"),
            )

        record = dict(result)
        enriched = await _build_relations(pool, record, include_relations)
        return SuccessResponse(data=enriched)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.put(
    "/{image_id}",
    response_model=SuccessResponse[ImageResponse],
)
async def update_image(
    image_id: str,
    payload: ImageUpdateRequest,
    current_user: dict[str, Any] = Depends(require_permission("images:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[ImageResponse]:
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM krai_content.images WHERE id = $1 LIMIT 1", image_id)
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Image not found", "IMAGE_NOT_FOUND"),
            )
        existing_dict = dict(existing)
        update_payload = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not update_payload:
            return SuccessResponse(data=ImageResponse(**existing_dict))

        await _validate_foreign_keys(
            pool,
            document_id=update_payload.get("document_id"),
            chunk_id=update_payload.get("chunk_id"),
        )

        # Build dynamic UPDATE query
        set_clauses = []
        params = []
        param_count = 0

        for key, value in update_payload.items():
            param_count += 1
            set_clauses.append(f"{key} = ${param_count}")
            params.append(value)

        param_count += 1
        params.append(image_id)

        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                f"UPDATE krai_content.images SET {', '.join(set_clauses)} WHERE id = ${param_count} RETURNING *",
                *params,
            )

        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to update image"),
            )

        result_dict = dict(result)
        LOGGER.info("Updated image %s", image_id)
        await _insert_audit_log(
            pool,
            record_id=image_id,
            operation="UPDATE",
            changed_by=current_user.get("id"),
            new_values=result_dict,
            old_values=existing_dict,
        )
        return SuccessResponse(data=ImageResponse(**result_dict))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.delete(
    "/{image_id}",
    response_model=SuccessResponse[MessagePayload],
)
async def delete_image(
    image_id: str,
    delete_from_storage: bool = Query(False, description="Also delete the backing object from object storage."),
    current_user: dict[str, Any] = Depends(require_permission("images:delete")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[MessagePayload]:
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM krai_content.images WHERE id = $1 LIMIT 1", image_id)
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Image not found", "IMAGE_NOT_FOUND"),
            )
        existing_dict = dict(existing)

        storage_deleted = False
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM krai_content.images WHERE id = $1", image_id)
        LOGGER.info("Deleted image %s", image_id)
        await _insert_audit_log(
            pool,
            record_id=image_id,
            operation="DELETE",
            changed_by=current_user.get("id"),
            old_values=existing_dict,
        )

        if delete_from_storage:
            storage_service = create_storage_service()

            try:
                await storage_service.connect()
                storage_url = existing_dict.get("storage_url", "") or ""
                storage_path = existing_dict.get("storage_path")
                bucket_type = _infer_bucket_type_from_url(storage_url)

                if storage_path:
                    try:
                        storage_deleted = await storage_service.delete_image(bucket_type, storage_path)
                    except Exception as delete_exc:  # pragma: no cover
                        LOGGER.warning(
                            "Failed to delete image %s from storage (%s/%s): %s",
                            image_id,
                            bucket_type,
                            storage_path,
                            delete_exc,
                        )
                else:
                    LOGGER.warning(
                        "Storage path missing for image %s; skipping storage deletion.",
                        image_id,
                    )
            except Exception as storage_exc:  # pragma: no cover
                LOGGER.warning(
                    "Object storage unavailable while deleting image %s: %s",
                    image_id,
                    storage_exc,
                )

        return SuccessResponse(
            data=MessagePayload(
                message="Image deleted successfully",
                deleted_from_storage=storage_deleted,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "/upload",
    response_model=SuccessResponse[ImageUploadResponse],
)
async def upload_image(
    file: UploadFile = File(...),
    document_id: str | None = None,
    alt_text: str | None = None,
    current_user: dict[str, Any] = Depends(require_permission("images:write")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> SuccessResponse[ImageUploadResponse]:
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=_error_response(
                    "Invalid File",
                    "Only image uploads are allowed.",
                    "INVALID_CONTENT_TYPE",
                ),
            )

        content = _decode_upload(file)
        file_size = len(content)

        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_error_response(
                    "Payload Too Large",
                    "Image exceeds 50MB limit.",
                    "FILE_TOO_LARGE",
                ),
            )

        storage_service = create_storage_service()

        try:
            await storage_service.connect()
        except Exception as exc:
            LOGGER.error("Failed to connect to object storage: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_error_response(
                    "Storage Unavailable",
                    "Image storage service is temporarily unavailable. Please try again later.",
                    "STORAGE_UNAVAILABLE",
                ),
            )

        storage_result = await storage_service.upload_image(
            content=content, filename=file.filename or "upload.bin", bucket_type="document_images", metadata={}
        )

        is_duplicate = storage_result.get("is_duplicate", False)
        file_hash = storage_result.get("file_hash")
        resolved_url = (
            storage_result.get("storage_url") or storage_result.get("public_url") or storage_result.get("url")
        )

        # Check for duplicates
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT id FROM krai_content.images WHERE file_hash = $1 LIMIT 1", file_hash)
        if existing:
            async with pool.acquire() as conn:
                existing_image = await conn.fetchrow(
                    "SELECT * FROM krai_content.images WHERE id = $1 LIMIT 1", existing["id"]
                )
            existing_dict = dict(existing_image)
            return SuccessResponse(
                data=ImageUploadResponse(
                    image_id=existing_dict["id"],
                    storage_url=existing_dict.get("storage_url"),
                    storage_path=existing_dict.get("storage_path"),
                    message="Image already exists (deduplicated)",
                    is_duplicate=True,
                )
            )

        storage_path = storage_result.get("storage_path") or storage_result.get("key")
        original_filename = file.filename or "upload.bin"
        image_format = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else None
        file_size = storage_result.get("size")

        image_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO krai_content.images (
                    id, filename, original_filename, storage_path, storage_url, file_size, image_format,
                    file_hash, document_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *
                """,
                image_id,
                storage_path or original_filename,
                original_filename,
                storage_path,
                resolved_url,
                file_size,
                image_format,
                file_hash,
                document_id,
                datetime.now(UTC).isoformat(),
            )

        result_dict = dict(result)
        await _insert_audit_log(
            pool,
            record_id=result_dict["id"],
            operation="CREATE",
            changed_by=current_user.get("id"),
            new_values=result_dict,
        )

        return SuccessResponse(
            data=ImageUploadResponse(
                image_id=result_dict["id"],
                storage_url=result_dict.get("storage_url"),
                storage_path=result_dict.get("storage_path"),
                message="Image uploaded successfully",
            )
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/{image_id}/download",
)
async def download_image(
    image_id: str,
    current_user: dict[str, Any] = Depends(require_permission("images:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, storage_url, storage_path, filename, image_format FROM krai_content.images WHERE id = $1 LIMIT 1",
                image_id,
            )
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Image not found", "IMAGE_NOT_FOUND"),
            )

        record = dict(existing)
        storage_path = record.get("storage_path")
        storage_url = record.get("storage_url") or ""

        bucket_type = _infer_bucket_type_from_url(storage_url)

        if not storage_path and storage_url:
            public_documents = os.getenv("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS", "")
            public_error = os.getenv("OBJECT_STORAGE_PUBLIC_URL_ERROR", "")
            public_parts = os.getenv("OBJECT_STORAGE_PUBLIC_URL_PARTS", "")

            prefix = ""
            if public_documents and storage_url.startswith(public_documents):
                prefix = public_documents
            elif public_error and storage_url.startswith(public_error):
                prefix = public_error
            elif public_parts and storage_url.startswith(public_parts):
                prefix = public_parts

            if prefix:
                trimmed = storage_url[len(prefix) :]
                if trimmed.startswith("/"):
                    trimmed = trimmed[1:]
                storage_path = trimmed or None

        if not storage_path:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=_error_response(
                    "Bad Request",
                    "Image does not have a storage path for download.",
                    "IMAGE_STORAGE_PATH_MISSING",
                ),
            )

        storage_service = create_storage_service()

        try:
            await storage_service.connect()
        except Exception as exc:
            LOGGER.error("Failed to connect to object storage for download: %s", exc)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_error_response(
                    "Storage Unavailable",
                    "Image storage service is temporarily unavailable. Please try again later.",
                    "STORAGE_UNAVAILABLE",
                ),
            )

        try:
            content = await storage_service.download_image(bucket_type, storage_path)
        except Exception as exc:  # pragma: no cover
            LOGGER.error(
                "Failed to download image %s from storage (%s/%s): %s",
                image_id,
                bucket_type,
                storage_path,
                exc,
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response(
                    "Server Error",
                    "Failed to download image from storage.",
                    "IMAGE_DOWNLOAD_FAILED",
                ),
            )

        media_type = _guess_media_type(record.get("filename"), record.get("image_format"))
        disposition_filename = record.get("filename") or f"{image_id}.bin"

        response = Response(content=content or b"", media_type=media_type)
        response.headers["Content-Disposition"] = f"attachment; filename={disposition_filename}"
        return response
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/by-document/{document_id}",
    response_model=SuccessResponse[ImageListResponse],
)
async def get_images_by_document(
    document_id: str,
    pagination: PaginationParams = Depends(),
    sort: ImageSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("images:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ImageListResponse]:
    try:
        # Build base query
        base_query = """
            SELECT
                i.id,
                i.filename,
                i.original_filename,
                i.storage_url,
                i.storage_path,
                i.file_size,
                i.file_hash,
                i.document_id,
                i.created_at,
                i.updated_at,
                COUNT(*) OVER() as total_count
            FROM krai_content.images i
            WHERE i.document_id = $1
        """

        params = [document_id]

        # Add sorting
        order_by = "ORDER BY " + sort.sort_by + (" DESC" if sort.sort_order == "desc" else " ASC")

        # Add pagination
        limit_clause = f"LIMIT {pagination.limit} OFFSET {(pagination.page - 1) * pagination.limit}"

        full_query = f"{base_query} {order_by} {limit_clause}"

        result = await adapter.execute_query(full_query, params)

        # Extract total count from first row
        total_count = result[0]["total_count"] if result else 0

        images = [ImageResponse(**row) for row in result]

        payload = ImageListResponse(
            images=images,
            total=total_count,
            page=pagination.page,
            page_size=pagination.limit,
            total_pages=(total_count + pagination.limit - 1) // pagination.limit,
        )
        return SuccessResponse(data=payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/stats",
    response_model=SuccessResponse[ImageStatsResponse],
)
async def get_image_stats(
    current_user: dict[str, Any] = Depends(require_permission("images:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ImageStatsResponse]:
    try:
        result = await adapter.execute_query("SELECT * FROM krai_content.images")
        records = result or []
        stats = _calculate_stats(records)
        return SuccessResponse(data=stats)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
