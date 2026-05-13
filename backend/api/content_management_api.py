"""
Content Management API
Endpoints for video enrichment and link checking
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Request/Response Models
class VideoEnrichmentRequest(BaseModel):
    limit: int | None = Field(None, description="Limit number of videos to process")
    force: bool = Field(False, description="Re-process already enriched videos")


class SingleVideoEnrichmentRequest(BaseModel):
    url: str = Field(..., description="Video URL to enrich")
    document_id: str | None = Field(None, description="Document ID to associate with")
    manufacturer_id: str | None = Field(None, description="Manufacturer ID")


class VideoEnrichmentResponse(BaseModel):
    status: str
    message: str
    enriched_count: int
    error_count: int
    started_at: str
    task_id: str | None = None


class LinkCheckRequest(BaseModel):
    limit: int | None = Field(None, description="Limit number of links to check")
    check_only: bool = Field(True, description="Check only without fixing")
    check_inactive: bool = Field(False, description="Also check inactive links")


class LinkCheckResponse(BaseModel):
    status: str
    message: str
    checked_count: int
    working_count: int
    broken_count: int
    fixed_count: int
    error_count: int
    started_at: str
    task_id: str | None = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class ContentManagementAPI:
    """Content Management API with video enrichment and link checking"""

    def __init__(self, database_service=None, video_enrichment_service=None, link_checker_service=None):
        self.database_service = database_service
        self.video_enrichment_service = video_enrichment_service
        self.link_checker_service = link_checker_service
        self.router = APIRouter(prefix="/content", tags=["Content Management"])
        self._setup_routes()

        # Task tracking
        self.tasks = {}

    def _setup_routes(self):
        """Setup API routes"""

        @self.router.post("/videos/enrich", response_model=VideoEnrichmentResponse)
        async def enrich_videos(request: VideoEnrichmentRequest, background_tasks: BackgroundTasks):
            """
            Enrich video links with metadata from YouTube, Vimeo, and Brightcove

            This endpoint runs video enrichment in the background and returns immediately.
            Use the task_id to check progress.
            """
            try:
                if not self.video_enrichment_service:
                    raise HTTPException(status_code=503, detail="Video enrichment service not available")

                # Generate task ID
                task_id = f"video_enrich_{datetime.utcnow().timestamp()}"

                # Add to background tasks
                background_tasks.add_task(
                    self._run_video_enrichment, task_id=task_id, limit=request.limit, force=request.force
                )

                # Store task
                self.tasks[task_id] = {
                    "status": "queued",
                    "type": "video_enrichment",
                    "started_at": datetime.utcnow().isoformat(),
                }

                return VideoEnrichmentResponse(
                    status="queued",
                    message="Video enrichment started in background",
                    enriched_count=0,
                    error_count=0,
                    started_at=datetime.utcnow().isoformat(),
                    task_id=task_id,
                )

            except Exception as e:
                logger.error(f"Error starting video enrichment: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/videos/enrich/sync", response_model=VideoEnrichmentResponse)
        async def enrich_videos_sync(request: VideoEnrichmentRequest):
            """
            Enrich video links synchronously (waits for completion)

            Use this for small batches. For large batches, use the async endpoint.
            """
            try:
                if not self.video_enrichment_service:
                    raise HTTPException(status_code=503, detail="Video enrichment service not available")

                started_at = datetime.utcnow().isoformat()

                # Run enrichment
                result = await self.video_enrichment_service.process_videos(limit=request.limit, force=request.force)

                return VideoEnrichmentResponse(
                    status="completed",
                    message=f"Enriched {result['enriched']} videos",
                    enriched_count=result["enriched"],
                    error_count=result["errors"],
                    started_at=started_at,
                )

            except Exception as e:
                logger.error(f"Error in video enrichment: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/videos/enrich/single")
        async def enrich_single_video(request: SingleVideoEnrichmentRequest):
            """
            Enrich a single video URL synchronously

            Accepts a video URL and enriches it immediately.
            """
            try:
                if not self.video_enrichment_service:
                    raise HTTPException(status_code=503, detail="Video enrichment service not available")

                # Enrich the single video URL
                result = await self.video_enrichment_service.enrich_video_url(
                    url=request.url, document_id=request.document_id, manufacturer_id=request.manufacturer_id
                )

                if result.get("error"):
                    return {"success": False, "error": result["error"], "platform": result.get("platform")}

                return {
                    "success": True,
                    "video_id": result.get("video_id"),
                    "title": result.get("title"),
                    "platform": result.get("platform"),
                    "duration": result.get("duration"),
                    "channel_title": result.get("channel_title"),
                    "description": result.get("description"),
                    "thumbnail_url": result.get("thumbnail_url"),
                    "video_url": result.get("url"),
                }

            except Exception as e:
                logger.error(f"Error enriching single video: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/links/check", response_model=LinkCheckResponse)
        async def check_links(request: LinkCheckRequest, background_tasks: BackgroundTasks):
            """
            Check links for validity and optionally fix broken ones

            This endpoint runs link checking in the background and returns immediately.
            Use the task_id to check progress.
            """
            try:
                if not self.link_checker_service:
                    raise HTTPException(status_code=503, detail="Link checker service not available")

                # Generate task ID
                task_id = f"link_check_{datetime.utcnow().timestamp()}"

                # Add to background tasks
                background_tasks.add_task(
                    self._run_link_checker,
                    task_id=task_id,
                    limit=request.limit,
                    check_only=request.check_only,
                    check_inactive=request.check_inactive,
                )

                # Store task
                self.tasks[task_id] = {
                    "status": "queued",
                    "type": "link_check",
                    "started_at": datetime.utcnow().isoformat(),
                }

                return LinkCheckResponse(
                    status="queued",
                    message="Link checking started in background",
                    checked_count=0,
                    working_count=0,
                    broken_count=0,
                    fixed_count=0,
                    error_count=0,
                    started_at=datetime.utcnow().isoformat(),
                    task_id=task_id,
                )

            except Exception as e:
                logger.error(f"Error starting link check: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/links/check/sync", response_model=LinkCheckResponse)
        async def check_links_sync(request: LinkCheckRequest):
            """
            Check links synchronously (waits for completion)

            Use this for small batches. For large batches, use the async endpoint.
            """
            try:
                if not self.link_checker_service:
                    raise HTTPException(status_code=503, detail="Link checker service not available")

                started_at = datetime.utcnow().isoformat()

                # Run link check
                result = await self.link_checker_service.check_links(
                    limit=request.limit, check_only=request.check_only, check_inactive=request.check_inactive
                )

                return LinkCheckResponse(
                    status="completed",
                    message=f"Checked {result['checked']} links",
                    checked_count=result["checked"],
                    working_count=result["working"],
                    broken_count=result["broken"],
                    fixed_count=result["fixed"],
                    error_count=result["errors"],
                    started_at=started_at,
                )

            except Exception as e:
                logger.error(f"Error in link check: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
        async def get_task_status(task_id: str):
            """Get status of a background task"""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            return TaskStatusResponse(task_id=task_id, **self.tasks[task_id])

        @self.router.get("/tasks")
        async def list_tasks():
            """List all background tasks"""
            return {"tasks": self.tasks, "count": len(self.tasks)}

    async def _run_video_enrichment(self, task_id: str, limit: int | None, force: bool):
        """Background task for video enrichment"""
        try:
            self.tasks[task_id]["status"] = "running"

            result = await self.video_enrichment_service.process_videos(limit=limit, force=force)

            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["result"] = result
            self.tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            logger.error(f"Error in video enrichment task {task_id}: {e}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["error"] = str(e)
            self.tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()

    async def _run_link_checker(self, task_id: str, limit: int | None, check_only: bool, check_inactive: bool):
        """Background task for link checking"""
        try:
            self.tasks[task_id]["status"] = "running"

            result = await self.link_checker_service.check_links(
                limit=limit, check_only=check_only, check_inactive=check_inactive
            )

            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["result"] = result
            self.tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            logger.error(f"Error in link check task {task_id}: {e}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["error"] = str(e)
            self.tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
