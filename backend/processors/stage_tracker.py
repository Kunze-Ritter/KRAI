"""
Stage Status Tracker

Helper class for tracking processing stages per document.
Enables parallel processing and detailed monitoring.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from backend.core.base_processor import Stage
from backend.services.database_adapter import DatabaseAdapter


class StageTracker:
    """
    Track processing stages for documents

    Stages:
    - upload
    - text_extraction
    - image_processing
    - classification
    - metadata_extraction
    - storage
    - embedding
    - search_indexing

    Status values:
    - pending: Not started yet
    - processing: Currently running
    - completed: Successfully finished
    - failed: Error occurred
    - skipped: Not applicable for this document
    """

    STAGES = [stage.value for stage in Stage]

    def __init__(self, database_adapter: DatabaseAdapter, websocket_callback: Callable | None = None):
        """Initialize tracker with optional WebSocket callback."""
        self.adapter = database_adapter
        self.logger = logging.getLogger("krai.stage_tracker")
        self.websocket_callback = websocket_callback
        self._rpc_enabled = True
        self._rpc_disabled_reason: str | None = None

    @staticmethod
    def _make_json_safe(value: Any) -> Any:
        """Recursively convert values to JSON-serializable types."""
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): StageTracker._make_json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [StageTracker._make_json_safe(v) for v in value]
        return value

    def _normalize_stage(self, stage_name: str | Stage) -> str:
        if isinstance(stage_name, Stage):
            return stage_name.value
        return str(stage_name)

    def _maybe_disable_rpc(self, exc: Exception, function_name: str) -> bool:
        """Disable DB RPC stage tracking if functions are missing.

        Returns True if RPC has been disabled due to this exception.
        """
        if not self._rpc_enabled:
            return False

        msg = str(exc)
        if "does not exist" in msg and function_name.startswith("krai_core."):
            self._rpc_enabled = False
            self._rpc_disabled_reason = msg
            self.logger.warning(
                "StageTracker RPC disabled (missing DB function). Tracking will continue without DB updates. "
                "Apply migration: database/migrations/10_stage_status_tracking.sql. Reason: %s",
                msg,
            )
            return True

        return False

    async def start_stage(self, document_id: str, stage_name: str | Stage) -> bool:
        """
        Mark stage as started

        Args:
            document_id: Document UUID
            stage_name: Name of the stage

        Returns:
            True if successful
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            await self.adapter.execute_rpc(
                "krai_core.start_stage", {"p_document_id": document_id, "p_stage_name": stage}
            )

            # Broadcast processor state change via WebSocket
            if self.websocket_callback:
                try:
                    from backend.api.websocket import broadcast_processor_state_change

                    # Map stage_name to processor_name
                    stage_to_processor = {
                        "upload": "UploadProcessor",
                        "text_extraction": "TextProcessor",
                        "table_extraction": "TableProcessor",
                        "svg_processing": "SVGProcessor",
                        "image_processing": "ImageProcessor",
                        "visual_embedding": "VisualEmbeddingProcessor",
                        "link_extraction": "LinkProcessor",
                        "chunk_prep": "ChunkPrepProcessor",
                        "classification": "ClassificationProcessor",
                        "metadata_extraction": "MetadataProcessor",
                        "parts_extraction": "PartsProcessor",
                        "series_detection": "SeriesDetectionProcessor",
                        "storage": "StorageProcessor",
                        "embedding": "EmbeddingProcessor",
                        "search_indexing": "SearchIndexingProcessor",
                    }
                    processor_name = stage_to_processor.get(stage, f"{stage}Processor")
                    asyncio.create_task(
                        broadcast_processor_state_change(
                            processor_name=processor_name,
                            stage_name=stage,
                            status="processing",
                            document_id=document_id,
                        )
                    )
                except Exception as ws_error:
                    self.logger.warning(f"Failed to broadcast processor state change: {ws_error}")

            return True
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.start_stage"):
                return True
            self.logger.error("Error starting stage %s for document %s: %s", stage, document_id, e, exc_info=True)
            return False

    async def update_progress(
        self, document_id: str, stage_name: str | Stage, progress: float, metadata: dict | None = None
    ) -> bool:
        """
        Update stage progress

        Args:
            document_id: Document UUID
            stage_name: Name of the stage
            progress: Progress percentage (0-100). Fractions (0-1] are
                automatically converted to percentages and logged.
            metadata: Additional metadata (e.g., pages_processed)

        Returns:
            True if successful
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            metadata = metadata or {}
            metadata = self._make_json_safe(metadata)
            normalized_progress = progress

            if normalized_progress is None:
                self.logger.warning(
                    "Received None progress for stage '%s' on document '%s'; defaulting to 0.", stage_name, document_id
                )
                normalized_progress = 0.0

            if 0 < normalized_progress <= 1:
                self.logger.warning(
                    "Progress for stage '%s' on document '%s' provided as fraction %.4f;" " scaling to percentage.",
                    stage_name,
                    document_id,
                    normalized_progress,
                )
                normalized_progress = normalized_progress * 100
                metadata.setdefault("progress_scale_adjusted", True)

            normalized_progress = max(0.0, min(100.0, float(normalized_progress)))

            await self.adapter.execute_rpc(
                "krai_core.update_stage_progress",
                {
                    "p_document_id": document_id,
                    "p_stage_name": stage,
                    "p_progress": normalized_progress,
                    "p_metadata": metadata,
                },
            )
            return True
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.update_stage_progress"):
                return True
            self.logger.error("Error updating progress for stage '%s' on document '%s': %s", stage_name, document_id, e)
            return False

    # Alias for consistency
    async def update_stage_progress(
        self, document_id: str, stage_name: str | Stage, progress: float, metadata: dict | None = None
    ) -> bool:
        """Alias for update_progress"""
        return await self.update_progress(document_id, stage_name, progress, metadata)

    async def complete_stage(self, document_id: str, stage_name: str, metadata: dict | None = None) -> bool:
        """
        Mark stage as completed

        Args:
            document_id: Document UUID
            stage_name: Name of the stage
            metadata: Additional metadata about completion

        Returns:
            True if successful
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            metadata = metadata or {}
            metadata = self._make_json_safe(metadata)
            await self.adapter.execute_rpc(
                "krai_core.complete_stage",
                {"p_document_id": document_id, "p_stage_name": stage, "p_metadata": metadata},
            )

            # Broadcast WebSocket events
            if self.websocket_callback:
                try:
                    from backend.api.websocket import broadcast_processor_state_change
                    from backend.models.monitoring import WebSocketEvent

                    # Broadcast stage completion event
                    asyncio.create_task(
                        self.websocket_callback(WebSocketEvent.STAGE_COMPLETED, stage, document_id, "completed")
                    )

                    # Broadcast processor state change
                    stage_to_processor = {
                        "upload": "UploadProcessor",
                        "text_extraction": "TextProcessor",
                        "table_extraction": "TableProcessor",
                        "svg_processing": "SVGProcessor",
                        "image_processing": "ImageProcessor",
                        "visual_embedding": "VisualEmbeddingProcessor",
                        "link_extraction": "LinkProcessor",
                        "chunk_prep": "ChunkPrepProcessor",
                        "classification": "ClassificationProcessor",
                        "metadata_extraction": "MetadataProcessor",
                        "parts_extraction": "PartsProcessor",
                        "series_detection": "SeriesDetectionProcessor",
                        "storage": "StorageProcessor",
                        "embedding": "EmbeddingProcessor",
                        "search_indexing": "SearchIndexingProcessor",
                    }
                    processor_name = stage_to_processor.get(stage, f"{stage}Processor")
                    asyncio.create_task(
                        broadcast_processor_state_change(
                            processor_name=processor_name, stage_name=stage, status="idle", document_id=None
                        )
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to broadcast stage completion: {e}")

            return True
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.complete_stage"):
                return True
            self.logger.error("Error completing stage %s for document %s: %s", stage, document_id, e, exc_info=True)
            return False

    async def fail_stage(self, document_id: str, stage_name: str, error: str, metadata: dict | None = None) -> bool:
        """
        Mark stage as failed

        Args:
            document_id: Document UUID
            stage_name: Name of the stage
            error: Error message
            metadata: Additional error metadata

        Returns:
            True if successful
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            metadata = metadata or {}
            metadata = self._make_json_safe(metadata)
            await self.adapter.execute_rpc(
                "krai_core.fail_stage",
                {"p_document_id": document_id, "p_stage_name": stage, "p_error": error, "p_metadata": metadata},
            )

            # Broadcast WebSocket events
            if self.websocket_callback:
                try:
                    from backend.api.websocket import broadcast_processor_state_change
                    from backend.models.monitoring import WebSocketEvent

                    # Broadcast stage failure event
                    asyncio.create_task(
                        self.websocket_callback(WebSocketEvent.STAGE_FAILED, stage, document_id, "failed")
                    )

                    # Broadcast processor state change
                    stage_to_processor = {
                        "upload": "UploadProcessor",
                        "text_extraction": "TextProcessor",
                        "table_extraction": "TableProcessor",
                        "svg_processing": "SVGProcessor",
                        "image_processing": "ImageProcessor",
                        "visual_embedding": "VisualEmbeddingProcessor",
                        "link_extraction": "LinkProcessor",
                        "chunk_prep": "ChunkPrepProcessor",
                        "classification": "ClassificationProcessor",
                        "metadata_extraction": "MetadataProcessor",
                        "parts_extraction": "PartsProcessor",
                        "series_detection": "SeriesDetectionProcessor",
                        "storage": "StorageProcessor",
                        "embedding": "EmbeddingProcessor",
                        "search_indexing": "SearchIndexingProcessor",
                    }
                    processor_name = stage_to_processor.get(stage, f"{stage}Processor")
                    asyncio.create_task(
                        broadcast_processor_state_change(
                            processor_name=processor_name, stage_name=stage, status="failed", document_id=document_id
                        )
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to broadcast stage failure: {e}")

            return True
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.fail_stage"):
                return True
            self.logger.error(
                "Error marking stage %s as failed for document %s: %s", stage, document_id, e, exc_info=True
            )
            return False

    async def skip_stage(self, document_id: str, stage_name: str, reason: str = "Not applicable") -> bool:
        """
        Mark stage as skipped

        Args:
            document_id: Document UUID
            stage_name: Name of the stage
            reason: Reason for skipping

        Returns:
            True if successful
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            await self.adapter.execute_rpc(
                "krai_core.skip_stage", {"p_document_id": document_id, "p_stage_name": stage, "p_reason": reason}
            )
            return True
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.skip_stage"):
                return True
            self.logger.error("Error skipping stage %s for document %s: %s", stage, document_id, e, exc_info=True)
            return False

    async def get_progress(self, document_id: str) -> float:
        """
        Get overall document progress (0-100)

        Args:
            document_id: Document UUID

        Returns:
            Progress percentage
        """
        try:
            if not self._rpc_enabled:
                return 0.0
            result = await self.adapter.execute_rpc("krai_core.get_document_progress", {"p_document_id": document_id})

            if result is not None:
                return float(result)
            return 0.0
        except Exception as e:
            self._maybe_disable_rpc(e, "krai_core.get_document_progress")
            self.logger.error("Error getting progress for document %s: %s", document_id, e, exc_info=True)
            return 0.0

    async def get_current_stage(self, document_id: str) -> str:
        """
        Get current processing stage

        Args:
            document_id: Document UUID

        Returns:
            Stage name or 'completed'
        """
        try:
            if not self._rpc_enabled:
                return "unknown"
            result = await self.adapter.execute_rpc("krai_core.get_current_stage", {"p_document_id": document_id})

            if result:
                return result
            return "upload"
        except Exception as e:
            self._maybe_disable_rpc(e, "krai_core.get_current_stage")
            self.logger.error("Error getting current stage for document %s: %s", document_id, e, exc_info=True)
            return "unknown"

    async def can_start_stage(self, document_id: str, stage_name: str) -> bool:
        """
        Check if stage can be started (prerequisites met)

        Args:
            document_id: Document UUID
            stage_name: Name of the stage

        Returns:
            True if stage can start
        """
        stage = self._normalize_stage(stage_name)

        if not self._rpc_enabled:
            return True

        try:
            result = await self.adapter.execute_rpc(
                "krai_core.can_start_stage", {"p_document_id": document_id, "p_stage_name": stage}
            )

            return bool(result) if result is not None else False
        except Exception as e:
            if self._maybe_disable_rpc(e, "krai_core.can_start_stage"):
                return True
            self.logger.error(
                "Error checking if stage %s can start for document %s: %s", stage, document_id, e, exc_info=True
            )
            return False

    async def get_stage_status(self, document_id: str) -> dict[str, Any]:
        """
        Get complete stage status for a document

        Args:
            document_id: Document UUID

        Returns:
            Dictionary with all stage statuses
        """
        try:
            result = await self.adapter.execute_query(
                "SELECT stage_status FROM krai_core.documents WHERE id = $1", [document_id]
            )

            if result and len(result) > 0:
                return result[0].get("stage_status", {})
            return {}
        except Exception as e:
            self.logger.error("Error getting stage status for document %s: %s", document_id, e, exc_info=True)
            return {}

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get processing statistics for all stages

        Returns:
            Dictionary with statistics per stage
        """
        try:
            result = await self.adapter.execute_query("SELECT * FROM krai_core.vw_stage_statistics")

            if result:
                return {
                    stage["stage_name"]: {
                        "pending": stage["pending_count"],
                        "processing": stage["processing_count"],
                        "completed": stage["completed_count"],
                        "failed": stage["failed_count"],
                        "skipped": stage["skipped_count"],
                        "avg_duration": stage["avg_duration_seconds"],
                    }
                    for stage in result
                }
            return {}
        except Exception as e:
            self.logger.error("Error getting stage statistics: %s", e, exc_info=True)
            return {}


# Context manager for automatic stage tracking
class StageContext:
    """
    Context manager for automatic stage tracking

    Usage:
        tracker = StageTracker(supabase)
        with StageContext(tracker, document_id, 'text_extraction') as ctx:
            # Do processing
            ctx.update_progress(50, {'pages': 2000})
            # Stage automatically marked as completed on success
            # Or failed if exception occurs
    """

    def __init__(self, tracker: StageTracker, document_id: str, stage_name: str | Stage):
        self.tracker = tracker
        self.document_id = document_id
        tracker_stage = tracker._normalize_stage(stage_name)
        self.stage_name = tracker_stage
        self.metadata = {}

    async def __aenter__(self):
        """Start stage"""
        await self.tracker.start_stage(self.document_id, self.stage_name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Complete or fail stage"""
        if exc_type is None:
            # Success
            await self.tracker.complete_stage(self.document_id, self.stage_name, self.metadata)
        else:
            # Failure
            await self.tracker.fail_stage(self.document_id, self.stage_name, str(exc_val), self.metadata)
        return False  # Don't suppress exception

    async def update_progress(self, progress: float, metadata: dict | None = None):
        """Update progress during processing"""
        if metadata:
            self.metadata.update(metadata)
        await self.tracker.update_progress(self.document_id, self.stage_name, progress, metadata)

    def set_metadata(self, key: str, value: Any):
        """Set metadata value"""
        self.metadata[key] = value
