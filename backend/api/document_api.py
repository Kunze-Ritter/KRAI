"""
Document API for KR-AI-Engine
FastAPI endpoints for document processing
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile

from api.middleware.auth_middleware import require_permission
from api.routes.response_models import (
    DocumentStatusResponse,
    StageListResponse,
    StageProcessingRequest,
    StageProcessingResponse,
    StageStatusResponse,
    SuccessResponse,
    ThumbnailGenerationRequest,
    ThumbnailGenerationResponse,
    VideoProcessingRequest,
    VideoProcessingResponse,
)
from core.base_processor import ProcessingContext, Stage
from core.data_models import DocumentType, DocumentUploadResponse
from models.document import (
    CANONICAL_STAGES,
    DocumentFilterParams,
    DocumentListResponse,
    DocumentResponse,
    DocumentSortParams,
    DocumentStageDetail,
    DocumentStageStatusResponse,
    PaginationParams,
    SortOrder,
    StageStatus,
)
from pipeline.master_pipeline import KRMasterPipeline
from processors.thumbnail_processor import ThumbnailProcessor
from processors.upload_processor import UploadProcessor
from services.ai_service import AIService
from services.database_adapter import DatabaseAdapter
from services.object_storage_service import ObjectStorageService
from services.video_enrichment_service import VideoEnrichmentService


class DocumentAPI:
    """
    Document API for KR-AI-Engine

    Uses MasterPipeline for full production processing with all optimizations:
    - Pre-compiled regex patterns (60x faster error code enrichment)
    - LLM-based product extraction (configurable via LLM_MAX_PAGES)
    - OCR optimization (2x faster, no duplicate calls)
    - Series detection and product type mapping
    - Image processing with computer vision
    - Embeddings generation
    - Object storage integration (MinIO, S3, R2, etc.)

    Endpoints:
    - POST /documents/upload: Upload document
    - GET /documents/{document_id}: Get document info
    - GET /documents/{document_id}/status: Get processing status
    - POST /documents/{document_id}/reprocess: Reprocess document
    """

    def __init__(
        self,
        database_service: DatabaseAdapter,
        storage_service: ObjectStorageService,
        ai_service: AIService,
        video_enrichment_service: VideoEnrichmentService | None = None,
    ):
        self.database_service = database_service
        self.storage_service = storage_service
        self.ai_service = ai_service
        self.video_enrichment_service = video_enrichment_service
        self.logger = logging.getLogger("krai.api.document")
        self._setup_logging()

        # Initialize upload processor (for initial file handling)
        self.upload_processor = UploadProcessor(database_service)

        # Wire performance collector to standalone processors and pipeline
        # Import performance_service from main module
        performance_collector = None
        try:
            from backend.main import performance_service

            performance_collector = performance_service
            if performance_service:
                if hasattr(self.upload_processor, "set_performance_collector"):
                    self.upload_processor.set_performance_collector(performance_service)
        except ImportError:
            # performance_service not available (e.g., in tests)
            pass

        # Initialize pipeline and processors for stage-based processing
        # Pass performance_collector so pipeline uses the same global instance
        self.pipeline = KRMasterPipeline(
            database_adapter=database_service,
            force_continue_on_errors=True,
            performance_collector=performance_collector,
        )
        self.thumbnail_processor = ThumbnailProcessor(database_service, storage_service)

        # Wire performance collector to thumbnail processor
        if performance_collector and hasattr(self.thumbnail_processor, "set_performance_collector"):
            self.thumbnail_processor.set_performance_collector(performance_collector)

        # Create router
        self.router = APIRouter(prefix="/documents", tags=["documents"])
        self._setup_routes()

    def _setup_logging(self):
        """Setup logging for document API"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - DocumentAPI - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _setup_routes(self):
        """Setup API routes"""

        @self.router.get("", response_model=SuccessResponse[DocumentListResponse])
        async def list_documents(
            request: Request,
            pagination: PaginationParams = Depends(),
            filters: DocumentFilterParams = Depends(),
            sort: DocumentSortParams = Depends(),
            current_user: dict[str, Any] = Depends(require_permission("documents:read")),
        ) -> SuccessResponse[DocumentListResponse]:
            """List documents with pagination, filtering, and sorting (PostgreSQL-backed)."""

            try:
                conditions: list[str] = []
                params: dict[str, Any] = {}

                if filters.manufacturer_id:
                    conditions.append("manufacturer_id = :manufacturer_id")
                    params["manufacturer_id"] = filters.manufacturer_id
                if filters.document_type:
                    conditions.append("document_type = :document_type")
                    params["document_type"] = filters.document_type
                if filters.language:
                    conditions.append("language = :language")
                    params["language"] = filters.language
                if filters.processing_status:
                    conditions.append("processing_status = :processing_status")
                    params["processing_status"] = filters.processing_status
                if filters.manual_review_required is not None:
                    conditions.append("manual_review_required = :manual_review_required")
                    params["manual_review_required"] = filters.manual_review_required
                if filters.search:
                    conditions.append("(filename ILIKE :search OR manufacturer ILIKE :search OR series ILIKE :search)")
                    params["search"] = f"%{filters.search}%"
                if filters.has_failed_stages is not None:
                    if filters.has_failed_stages:
                        conditions.append(
                            "EXISTS (SELECT 1 FROM jsonb_each(stage_status) WHERE value->>'status' = 'failed')"
                        )
                    else:
                        conditions.append(
                            "NOT EXISTS (SELECT 1 FROM jsonb_each(stage_status) WHERE value->>'status' = 'failed')"
                        )
                if filters.has_incomplete_stages is not None:
                    if filters.has_incomplete_stages:
                        conditions.append(
                            "EXISTS (SELECT 1 FROM jsonb_each(stage_status) WHERE value->>'status' IN ('pending', 'processing'))"
                        )
                    else:
                        conditions.append(
                            "NOT EXISTS (SELECT 1 FROM jsonb_each(stage_status) WHERE value->>'status' IN ('pending', 'processing'))"
                        )
                if filters.stage_name:
                    conditions.append("stage_status ? :stage_name")
                    params["stage_name"] = filters.stage_name

                where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

                order_direction = "DESC" if sort.sort_order == SortOrder.DESC else "ASC"
                order_clause = f" ORDER BY {sort.sort_by} {order_direction}"

                offset = (pagination.page - 1) * pagination.page_size
                params["limit"] = pagination.page_size
                params["offset"] = offset

                base_select = """
                    SELECT
                        id,
                        filename,
                        filename AS original_filename,
                        COALESCE(file_size, 0) AS file_size,
                        COALESCE(file_hash, '') AS file_hash,
                        COALESCE(storage_path, '') AS storage_path,
                        COALESCE(storage_path, '') AS storage_url,
                        COALESCE(document_type, 'service_manual') AS document_type,
                        language,
                        version,
                        publish_date,
                        page_count,
                        word_count,
                        character_count,
                        processing_status,
                        confidence_score,
                        manual_review_required,
                        manual_review_notes,
                        stage_status,
                        manufacturer,
                        series,
                        COALESCE(models, ARRAY[]::text[]) AS models,
                        created_at,
                        updated_at,
                        manufacturer_id,
                        NULL::uuid AS product_id
                    FROM krai_core.documents
                """

                list_query = base_select + where_clause + order_clause + " LIMIT :limit OFFSET :offset"
                rows = await self.database_service.fetch_all(list_query, params)

                count_query = "SELECT COUNT(*) AS count FROM krai_core.documents" + where_clause
                count_row = await self.database_service.fetch_one(count_query, params)
                total = int(count_row["count"]) if count_row and "count" in count_row else 0

                documents = [DocumentResponse(**dict(row)) for row in (rows or [])]
                total_pages = max(1, (total + pagination.page_size - 1) // pagination.page_size) if total else 1

                payload = DocumentListResponse(
                    documents=documents,
                    total=total,
                    page=pagination.page,
                    page_size=pagination.page_size,
                    total_pages=total_pages,
                )

                return SuccessResponse(data=payload)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Failed to list documents: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/upload", response_model=DocumentUploadResponse)
        async def upload_document(
            request: Request,
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            document_type: DocumentType | None = None,
            language: str = "en",
        ):
            """Upload and process document"""
            try:
                # Read file content
                file_content = await file.read()

                # Persist uploaded file so UploadProcessor can validate and hash it
                upload_root = Path("/app/temp/uploads")
                upload_root.mkdir(parents=True, exist_ok=True)
                stored_path = upload_root / file.filename
                stored_path.write_bytes(file_content)

                # Create processing context
                from core.base_processor import ProcessingContext

                context = ProcessingContext(
                    document_id="",  # Will be set by upload processor
                    file_path=str(stored_path),  # Local path for upload processor
                    file_hash="",  # Will be set by upload processor
                    document_type=document_type.value if document_type else "service_manual",
                    manufacturer=None,
                    model=None,
                    series=None,
                    version=None,
                    language=language,
                )

                # Process upload
                result = await self.upload_processor.safe_process(context)

                if not result.success:
                    raise HTTPException(status_code=400, detail=f"Upload failed: {result.error.message}")

                document_id = result.data.get("document_id")

                if document_id:
                    try:
                        uploader_username = request.headers.get("X-Uploader-Username")
                        uploader_user_id = request.headers.get("X-Uploader-UserId")
                        uploader_source = request.headers.get("X-Uploader-Source") or "laravel-admin"

                        uploaded_by = {
                            "username": uploader_username,
                            "user_id": uploader_user_id,
                            "source": uploader_source,
                            "uploaded_at": datetime.utcnow().isoformat(),
                        }

                        existing_metadata_rows = await self.database_service.execute_query(
                            "SELECT extracted_metadata FROM krai_core.documents WHERE id = :document_id",
                            {"document_id": document_id},
                        )

                        existing_metadata: dict[str, Any] = {}
                        if existing_metadata_rows:
                            raw_metadata = existing_metadata_rows[0].get("extracted_metadata")
                            if isinstance(raw_metadata, dict):
                                existing_metadata = raw_metadata

                        if not isinstance(existing_metadata, dict):
                            existing_metadata = {}

                        upload_block = existing_metadata.get("upload") or {}
                        upload_block["uploaded_by"] = uploaded_by
                        existing_metadata["upload"] = upload_block

                        await self.database_service.update_document(
                            document_id,
                            {"extracted_metadata": existing_metadata},
                        )
                    except Exception as meta_error:
                        self.logger.error(f"Failed to update upload metadata for document {document_id}: {meta_error}")

                # Start background processing
                background_tasks.add_task(
                    self._process_document_background, result.data["document_id"], file_content, file.filename
                )

                return DocumentUploadResponse(
                    document_id=result.data["document_id"],
                    status="pending",
                    message="Document uploaded successfully. Processing started.",
                    processing_time=result.processing_time,
                )

            except Exception as e:
                self.logger.error(f"Document upload failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}")
        async def get_document(document_id: str):
            """Get document information"""
            try:
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                return {
                    "document_id": document.id,
                    "filename": document.filename,
                    "file_size": document.file_size,
                    "document_type": document.document_type,
                    "processing_status": document.processing_status,
                    "manufacturer": document.manufacturer,
                    "series": document.series,
                    "models": document.models,
                    "version": document.version,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                }
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Failed to get document {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/status", response_model=SuccessResponse[DocumentStatusResponse])
        async def get_document_status(document_id: str):
            """Get document processing status"""
            try:
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Get processing queue status
                queue_items = await self.database_service.get_pending_queue_items("all")
                processing_status = DocumentStatusResponse(
                    document_status=document.processing_status,
                    queue_position=len([item for item in queue_items if item.document_id == document_id]),
                    total_queue_items=len(queue_items),
                )

                return SuccessResponse(data=processing_status)
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Failed to get document status {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/{document_id}/reprocess")
        async def reprocess_document(document_id: str):
            """Reprocess document"""
            try:
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Reset processing status
                await self.database_service.update_document(document_id, {"processing_status": "pending"})

                # Add to processing queue
                from core.data_models import ProcessingQueueModel

                queue_item = ProcessingQueueModel(
                    document_id=document_id, processor_name="upload_processor", status="pending", priority=1
                )
                await self.database_service.create_processing_queue_item(queue_item)

                return {"message": "Document queued for reprocessing", "document_id": document_id, "status": "pending"}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Failed to reprocess document {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/chunks")
        async def get_document_chunks(document_id: str, limit: int = 100, offset: int = 0):
            """Get document chunks"""
            try:
                # This would typically query the database for chunks
                # For now, return a placeholder
                return {"document_id": document_id, "chunks": [], "total_count": 0, "limit": limit, "offset": offset}

            except Exception as e:
                self.logger.error(f"Failed to get document chunks {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/images")
        async def get_document_images(document_id: str):
            """Get document images"""
            try:
                # This would typically query the database for images
                # For now, return a placeholder
                return {"document_id": document_id, "images": [], "total_count": 0}
            except Exception as e:
                self.logger.error(f"Failed to get document images {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # ===== STAGE-BASED PROCESSING ENDPOINTS =====

        @self.router.post("/{document_id}/process/stage/{stage_name}")
        async def process_single_stage(
            document_id: str,
            stage_name: str,
            current_user: dict[str, Any] = Depends(require_permission("documents:write")),
        ):
            """Process a single stage for a document"""
            try:
                # Validate stage name
                valid_stages = [stage.value for stage in Stage]
                if stage_name not in valid_stages:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid stage: {stage_name}. Valid stages: {valid_stages}"
                    )

                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Process single stage
                import time

                start_time = time.time()

                result = await self.pipeline.run_single_stage(document_id, stage_name)

                processing_time = time.time() - start_time

                return {
                    "success": result.get("success", False),
                    "stage": stage_name,
                    "data": result.get("data", {}),
                    "processing_time": processing_time,
                    "error": result.get("error"),
                }

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Stage processing failed for {document_id}/{stage_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/{document_id}/process/stages", response_model=StageProcessingResponse)
        async def process_multiple_stages(
            document_id: str,
            request: StageProcessingRequest,
            current_user: dict[str, Any] = Depends(require_permission("documents:write")),
        ):
            """Process multiple stages for a document"""
            try:
                # Validate all stage names
                valid_stages = [stage.value for stage in Stage]
                invalid_stages = [s for s in request.stages if s not in valid_stages]
                if invalid_stages:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid stages: {invalid_stages}. Valid stages: {valid_stages}"
                    )

                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Process stages
                # Map stop_on_error to pipeline's force_continue_on_errors
                original_force_continue = self.pipeline.force_continue_on_errors
                self.pipeline.force_continue_on_errors = not request.stop_on_error

                try:
                    result = await self.pipeline.run_stages(document_id, request.stages)
                finally:
                    # Restore original setting
                    self.pipeline.force_continue_on_errors = original_force_continue

                # Convert stage results to match StageResult model
                stage_results = []
                for stage_result in result.get("stage_results", []):
                    stage_results.append(
                        {
                            "stage": stage_result.get("stage", "unknown"),
                            "success": stage_result.get("success", False),
                            "data": stage_result.get("data"),
                            "error": stage_result.get("error"),
                            "processing_time": stage_result.get("processing_time", 0.0),
                        }
                    )

                return StageProcessingResponse(
                    success=result.get("success", False),
                    total_stages=len(request.stages),
                    successful=result.get("successful", 0),
                    failed=result.get("failed", 0),
                    stage_results=stage_results,
                    success_rate=result.get("success_rate", 0.0),
                )

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Multiple stage processing failed for {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/stages", response_model=SuccessResponse[DocumentStageStatusResponse])
        async def get_document_stages(
            document_id: str, current_user: dict[str, Any] = Depends(require_permission("documents:read"))
        ):
            """Get detailed stage-level processing status for a document"""
            try:
                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Get raw stage status from database
                from processors.stage_tracker import StageTracker

                tracker = StageTracker(self.database_service, websocket_callback=None)
                raw_stage_status = await tracker.get_stage_status(document_id)

                # Build stages dictionary with DocumentStageDetail for each canonical stage
                stages: dict[str, DocumentStageDetail] = {}
                for stage_name in CANONICAL_STAGES:
                    stage_data = raw_stage_status.get(stage_name, {})

                    # Map status string to StageStatus enum
                    status_str = stage_data.get("status", "pending")
                    try:
                        status = StageStatus(status_str)
                    except ValueError:
                        status = StageStatus.PENDING

                    stages[stage_name] = DocumentStageDetail(
                        status=status,
                        started_at=stage_data.get("started_at"),
                        completed_at=stage_data.get("completed_at"),
                        duration_seconds=stage_data.get("duration_seconds"),
                        progress=int(stage_data.get("progress", 0)),
                        error=stage_data.get("error"),
                        metadata=stage_data.get("metadata", {}),
                    )

                # Calculate overall progress
                overall_progress = await tracker.get_progress(document_id)

                # Get current stage
                current_stage = await tracker.get_current_stage(document_id)

                # Determine if any stages can be retried (failed stages)
                can_retry = any(stage.status == StageStatus.FAILED for stage in stages.values())

                # Get last updated timestamp
                last_updated = (
                    document.updated_at.isoformat()
                    if hasattr(document, "updated_at")
                    else datetime.utcnow().isoformat()
                )

                response = DocumentStageStatusResponse(
                    document_id=document_id,
                    filename=document.filename,
                    overall_progress=overall_progress,
                    current_stage=current_stage,
                    stages=stages,
                    can_retry=can_retry,
                    last_updated=last_updated,
                )

                return SuccessResponse(data=response)

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Failed to get document stages for {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/stages/available", response_model=StageListResponse)
        async def get_available_stages(
            document_id: str, current_user: dict[str, Any] = Depends(require_permission("documents:read"))
        ):
            """Get list of available processing stages"""
            try:
                stages = self.pipeline.get_available_stages()
                return StageListResponse(stages=stages, total=len(stages))
            except Exception as e:
                self.logger.error(f"Failed to get available stages: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/{document_id}/stages/{stage_name}/retry")
        async def retry_document_stage(
            document_id: str,
            stage_name: str,
            current_user: dict[str, Any] = Depends(require_permission("documents:write")),
        ):
            """Retry a failed stage for a document"""
            try:
                # Validate stage name
                valid_stages = [stage.value for stage in Stage]
                if stage_name not in valid_stages:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid stage: {stage_name}. Valid stages: {valid_stages}"
                    )

                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Run the single stage (this will reset and re-run it)
                import time

                start_time = time.time()

                result = await self.pipeline.run_single_stage(document_id, stage_name)

                processing_time = time.time() - start_time

                return SuccessResponse(
                    data={
                        "message": f"Stage {stage_name} retry completed",
                        "success": result.get("success", False),
                        "stage": stage_name,
                        "processing_time": processing_time,
                        "error": result.get("error"),
                    }
                )

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Stage retry failed for {document_id}/{stage_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/{document_id}/stages/status", response_model=StageStatusResponse)
        async def get_stage_status(
            document_id: str, current_user: dict[str, Any] = Depends(require_permission("documents:read"))
        ):
            """Get processing status for all stages of a document (legacy endpoint)"""
            try:
                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    return StageStatusResponse(
                        document_id=document_id, stage_status={}, found=False, error="Document not found"
                    )

                # Get stage status
                status = await self.pipeline.get_stage_status(document_id)

                return StageStatusResponse(
                    document_id=document_id,
                    stage_status=status.get("stage_status", {}),
                    found=status.get("found", True),
                    error=status.get("error"),
                )
            except Exception as e:
                self.logger.error(f"Failed to get stage status for {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/{document_id}/process/video", response_model=VideoProcessingResponse)
        async def process_video(
            document_id: str,
            request: VideoProcessingRequest,
            current_user: dict[str, Any] = Depends(require_permission("documents:write")),
        ):
            """Enrich video from URL and link to document"""
            try:
                if not self.video_enrichment_service:
                    raise HTTPException(status_code=503, detail="Video enrichment service not available")

                # Check if document exists
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Enrich video
                result = await self.video_enrichment_service.enrich_video_url(
                    url=str(request.video_url), document_id=document_id, manufacturer_id=request.manufacturer_id
                )

                if result.get("success"):
                    return VideoProcessingResponse(
                        success=True,
                        video_id=result.get("video_id"),
                        title=result.get("title"),
                        platform=result.get("platform"),
                        thumbnail_url=result.get("thumbnail_url"),
                        duration=result.get("duration"),
                        channel_title=result.get("channel_title"),
                    )
                return VideoProcessingResponse(success=False, error=result.get("error", "Video enrichment failed"))

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Video processing failed for {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/{document_id}/process/thumbnail", response_model=ThumbnailGenerationResponse)
        async def generate_thumbnail(
            document_id: str,
            request: ThumbnailGenerationRequest = ThumbnailGenerationRequest(),
            current_user: dict[str, Any] = Depends(require_permission("documents:write")),
        ):
            """Generate thumbnail for document"""
            try:
                # Get document info
                document = await self.database_service.get_document(document_id)
                if not document:
                    raise HTTPException(status_code=404, detail="Document not found")

                # Get file path
                file_path = getattr(document, "storage_path", None)
                if not file_path:
                    raise HTTPException(status_code=400, detail="Document has no file path for thumbnail generation")

                # Create processing context
                context = ProcessingContext(
                    document_id=document_id,
                    file_path=file_path,
                    file_hash="",  # Will be derived if needed
                    document_type=getattr(document, "document_type", "service_manual"),
                    processing_config={"size": request.size, "page": request.page},
                )

                # Generate thumbnail
                result = await self.thumbnail_processor.process(context)

                if result.success:
                    return ThumbnailGenerationResponse(
                        success=True,
                        thumbnail_url=result.data.get("thumbnail_url"),
                        size=result.data.get("size"),
                        file_size=result.data.get("file_size"),
                    )
                return ThumbnailGenerationResponse(success=False, error=result.error)

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Thumbnail generation failed for {document_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _process_document_background(self, document_id: str, file_content: bytes, filename: str):
        """Background document processing using stage-based MasterPipeline flow"""
        try:
            self.logger.info(f"Starting background processing for document {document_id}")

            # Save file temporarily
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file_content)
                temp_file_path = Path(temp_file.name)

            try:
                # Use existing pipeline instance instead of creating new one
                # This leverages the same KRMasterPipeline instance created in DocumentAPI constructor
                self.logger.info("Using stage-based pipeline flow for background processing...")

                # Use stage-based pipeline flow instead of legacy process_document
                # Define the canonical list of stages for complete processing
                stages = [
                    Stage.TEXT_EXTRACTION.value,
                    Stage.TABLE_EXTRACTION.value,
                    Stage.SVG_PROCESSING.value,
                    Stage.IMAGE_PROCESSING.value,
                    Stage.VISUAL_EMBEDDING.value,
                    Stage.LINK_EXTRACTION.value,
                    Stage.CHUNK_PREPROCESSING.value,
                    Stage.CLASSIFICATION.value,
                    Stage.METADATA_EXTRACTION.value,
                    Stage.PARTS_EXTRACTION.value,
                    Stage.SERIES_DETECTION.value,
                    Stage.STORAGE.value,
                    Stage.EMBEDDING.value,
                    Stage.SEARCH_INDEXING.value,
                ]

                self.logger.info(f"Running {len(stages)} stages for document {document_id}")

                result = await self.pipeline.run_stages(document_id, stages)

                if result.get("success", False):
                    self.logger.info(f"âœ… Document {document_id} processed successfully")
                    self.logger.info(f"   Successful stages: {result.get('successful', 0)}")
                    self.logger.info(f"   Failed stages: {result.get('failed', 0)}")
                else:
                    self.logger.error(f"âŒ Document {document_id} processing failed")
                    for stage_result in result.get("stage_results", []):
                        if not stage_result.get("success", False):
                            self.logger.error(
                                f"   Stage {stage_result.get('stage')} failed: {stage_result.get('error')}"
                            )

            finally:
                # Clean up temporary file
                if temp_file_path.exists():
                    temp_file_path.unlink()

        except Exception as e:
            self.logger.error(f"Background processing failed for document {document_id}: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            # Update document status to failed
            try:
                await self.database_service.update_document(document_id, {"processing_status": "failed"})
            except:
                pass
