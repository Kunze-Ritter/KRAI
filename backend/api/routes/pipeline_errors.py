"""
FastAPI router for Pipeline Error management endpoints.
"""

import logging
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.api.dependencies.database import get_database_adapter
from backend.api.middleware.auth_middleware import require_permission
from backend.api.routes.response_models import ErrorResponse, SuccessResponse
from backend.core.retry_engine import RetryOrchestrator
from backend.core.types import ProcessingContext
from backend.models.pipeline_error import (
    MarkErrorResolvedRequest,
    PipelineErrorListResponse,
    PipelineErrorResponse,
    RetryStageRequest,
)
from backend.services.database_adapter import DatabaseAdapter
from backend.services.error_logging_service import ErrorLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline Errors"])

limiter = Limiter(key_func=get_remote_address)
rate_limit_standard = "100/minute"

_error_logger_instance: ErrorLogger | None = None
_retry_orchestrator_instance: RetryOrchestrator | None = None


def get_error_logger(adapter: DatabaseAdapter = Depends(get_database_adapter)) -> ErrorLogger:
    """Dependency injection for ErrorLogger singleton."""
    global _error_logger_instance
    if _error_logger_instance is None:
        _error_logger_instance = ErrorLogger(db_adapter=adapter, log_file_path="logs/pipeline.log")
    return _error_logger_instance


def get_retry_orchestrator(
    adapter: DatabaseAdapter = Depends(get_database_adapter), error_logger: ErrorLogger = Depends(get_error_logger)
) -> RetryOrchestrator:
    """Dependency injection for RetryOrchestrator singleton."""
    global _retry_orchestrator_instance
    if _retry_orchestrator_instance is None:
        _retry_orchestrator_instance = RetryOrchestrator(db_adapter=adapter, error_logger=error_logger)
    return _retry_orchestrator_instance


@router.get("/errors", response_model=SuccessResponse[PipelineErrorListResponse])
@limiter.limit(rate_limit_standard)
async def list_pipeline_errors(
    request: Request,
    document_id: str | None = Query(None, description="Filter by document ID"),
    stage_name: str | None = Query(None, description="Filter by stage name"),
    error_type: str | None = Query(None, description="Filter by error type"),
    status: str | None = Query(None, description="Filter by status"),
    date_from: datetime | None = Query(None, description="Filter errors from this date"),
    date_to: datetime | None = Query(None, description="Filter errors until this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
    current_user: dict = Depends(require_permission("monitoring:write")),
):
    """
    List pipeline errors with filtering and pagination.

    Requires 'monitoring:write' permission.
    """
    try:
        logger.info(f"Listing pipeline errors - page={page}, page_size={page_size}, filters={locals()}")

        where_clauses = []
        params = []
        param_counter = 1

        if document_id:
            where_clauses.append(f"document_id = ${param_counter}")
            params.append(document_id)
            param_counter += 1

        if stage_name:
            where_clauses.append(f"stage_name = ${param_counter}")
            params.append(stage_name)
            param_counter += 1

        if error_type:
            where_clauses.append(f"error_type = ${param_counter}")
            params.append(error_type)
            param_counter += 1

        if status:
            where_clauses.append(f"status = ${param_counter}")
            params.append(status)
            param_counter += 1

        if date_from:
            where_clauses.append(f"created_at >= ${param_counter}")
            params.append(date_from)
            param_counter += 1

        if date_to:
            where_clauses.append(f"created_at <= ${param_counter}")
            params.append(date_to)
            param_counter += 1

        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        count_query = f"""
            SELECT COUNT(*) as total
            FROM krai_system.pipeline_errors
            {where_clause}
        """

        count_result = await adapter.fetch_one(count_query, params)
        total = count_result["total"] if count_result else 0
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        offset = (page - 1) * page_size

        query = f"""
            SELECT
                error_id,
                document_id,
                stage_name,
                error_type,
                error_category,
                error_message,
                stack_trace,
                context,
                retry_count,
                max_retries,
                status,
                severity,
                is_transient,
                correlation_id,
                created_at,
                updated_at,
                resolved_at,
                resolved_by,
                resolution_notes
            FROM krai_system.pipeline_errors
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """

        params.extend([page_size, offset])

        rows = await adapter.fetch_all(query, params)

        errors = [PipelineErrorResponse(**row) for row in rows]

        response_data = PipelineErrorListResponse(
            errors=errors, total=total, page=page, page_size=page_size, total_pages=total_pages
        )

        logger.info(f"Successfully retrieved {len(errors)} errors (total: {total})")

        return SuccessResponse(success=True, message=f"Retrieved {len(errors)} pipeline errors", data=response_data)

    except Exception as e:
        logger.error(f"Error listing pipeline errors: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(success=False, error="Failed to retrieve pipeline errors", details=str(e)).dict(),
        )


@router.get("/errors/{error_id}", response_model=SuccessResponse[PipelineErrorResponse])
@limiter.limit(rate_limit_standard)
async def get_pipeline_error(
    request: Request,
    error_id: str,
    error_logger: ErrorLogger = Depends(get_error_logger),
    current_user: dict = Depends(require_permission("monitoring:write")),
):
    """
    Get detailed error information by error_id.

    Requires 'monitoring:write' permission.
    """
    try:
        logger.info(f"Retrieving pipeline error: {error_id}")

        error_data = await error_logger.get_error_by_id(error_id)

        if not error_data:
            logger.warning(f"Pipeline error not found: {error_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    success=False, error="Pipeline error not found", details=f"No error found with ID: {error_id}"
                ).dict(),
            )

        error_response = PipelineErrorResponse(**error_data)

        logger.info(f"Successfully retrieved error: {error_id}")

        return SuccessResponse(success=True, message="Pipeline error retrieved successfully", data=error_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving pipeline error {error_id}: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(success=False, error="Failed to retrieve pipeline error", details=str(e)).dict(),
        )


@router.post("/retry-stage", response_model=SuccessResponse[dict])
@limiter.limit(rate_limit_standard)
async def retry_stage(
    req: Request,
    request: RetryStageRequest,
    adapter: DatabaseAdapter = Depends(get_database_adapter),
    orchestrator: RetryOrchestrator = Depends(get_retry_orchestrator),
    error_logger: ErrorLogger = Depends(get_error_logger),
    current_user: dict = Depends(require_permission("monitoring:write")),
):
    """
    Trigger manual retry for a failed stage.

    Requires 'monitoring:write' permission.
    """
    try:
        logger.info(f"Retry stage requested - document_id={request.document_id}, stage={request.stage_name}")

        doc_query = """
            SELECT document_id, file_path, filename, file_hash
            FROM krai_core.documents
            WHERE document_id = $1
        """
        document = await adapter.fetch_one(doc_query, [request.document_id])

        if not document:
            logger.warning(f"Document not found: {request.document_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    success=False,
                    error="Document not found",
                    details=f"No document found with ID: {request.document_id}",
                ).dict(),
            )

        error_query = """
            SELECT error_id, retry_count, status, correlation_id
            FROM krai_system.pipeline_errors
            WHERE document_id = $1 AND stage_name = $2
            ORDER BY created_at DESC
            LIMIT 1
        """
        error_data = await adapter.fetch_one(error_query, [request.document_id, request.stage_name])

        if not error_data:
            logger.warning(f"No error found for document {request.document_id} at stage {request.stage_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    success=False,
                    error="No failed stage found",
                    details=f"No error found for document {request.document_id} at stage {request.stage_name}",
                ).dict(),
            )

        if error_data["status"] not in ["failed", "resolved"]:
            logger.warning(f"Stage is already retrying: {request.stage_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    success=False, error="Stage is already retrying", details=f"Current status: {error_data['status']}"
                ).dict(),
            )

        ProcessingContext(
            document_id=request.document_id,
            file_path=document["file_path"],
            filename=document["filename"],
            file_hash=document["file_hash"],
        )

        retry_attempt = error_data["retry_count"] + 1
        correlation_id = error_data.get("correlation_id") or f"manual_retry_{request.document_id}_{request.stage_name}"

        # TODO: Implement stage processor registry to map stage_name to actual processor callable
        # For now, return 501 Not Implemented as manual retry requires processor integration
        logger.warning(f"Manual retry not yet implemented - stage processor registry required for {request.stage_name}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=ErrorResponse(
                success=False,
                error="Manual retry not yet implemented",
                details=f"Stage processor registry required to retry {request.stage_name}. Use automatic retry via pipeline instead.",
            ).dict(),
        )

        await error_logger.update_error_status(error_id=error_data["error_id"], new_status="retrying")

        logger.info(
            f"Stage retry triggered successfully - document_id={request.document_id}, stage={request.stage_name}"
        )

        return SuccessResponse(
            success=True,
            message="Stage retry triggered successfully",
            data={
                "document_id": request.document_id,
                "stage_name": request.stage_name,
                "retry_attempt": retry_attempt,
                "correlation_id": correlation_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering stage retry: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(success=False, error="Failed to trigger stage retry", details=str(e)).dict(),
        )


@router.post("/mark-error-resolved", response_model=SuccessResponse[dict])
@limiter.limit(rate_limit_standard)
async def mark_error_resolved(
    req: Request,
    request: MarkErrorResolvedRequest,
    error_logger: ErrorLogger = Depends(get_error_logger),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
    current_user: dict = Depends(require_permission("monitoring:write")),
):
    """
    Mark an error as resolved manually.

    Requires 'monitoring:write' permission.
    """
    try:
        logger.info(f"Marking error as resolved: {request.error_id}")

        check_query = """
            SELECT error_id, status
            FROM krai_system.pipeline_errors
            WHERE error_id = $1
        """
        error_data = await adapter.fetch_one(check_query, [request.error_id])

        if not error_data:
            logger.warning(f"Error not found: {request.error_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    success=False, error="Error not found", details=f"No error found with ID: {request.error_id}"
                ).dict(),
            )

        user_id = current_user.get("user_id", "unknown")

        await error_logger.mark_error_resolved(error_id=request.error_id, resolved_by=user_id, notes=request.notes)

        logger.info(f"Error marked as resolved: {request.error_id} by user {user_id}")

        return SuccessResponse(
            success=True,
            message="Error marked as resolved",
            data={"error_id": request.error_id, "resolved_by": user_id, "resolved_at": datetime.utcnow().isoformat()},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking error as resolved: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(success=False, error="Failed to mark error as resolved", details=str(e)).dict(),
        )
