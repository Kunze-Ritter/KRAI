"""Metrics aggregation service for monitoring."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from models.monitoring import (
    DataQualityResponse,
    DuplicateMetrics,
    HardwareStatus,
    PipelineMetrics,
    ProcessingMetrics,
    ProcessorHealthStatus,
    QueueItem,
    QueueMetrics,
    StageErrorLog,
    StageErrorLogsResponse,
    StageMetrics,
    StageQueueResponse,
    ValidationMetrics,
)
from processors.stage_tracker import StageTracker

LOGGER = logging.getLogger(__name__)


class MetricsService:
    """Service for aggregating and caching metrics."""

    CACHE_TTL_SECONDS = 5

    def __init__(self, pool: asyncpg.Pool, stage_tracker: StageTracker):
        """Initialize metrics service."""
        self.pool = pool
        self.stage_tracker = stage_tracker
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self.logger = LOGGER

    @staticmethod
    def safe_parse_datetime(value: Any, default: datetime | None = None) -> datetime | None:
        """Safely parse datetime from various formats, returning default on failure."""
        if value is None:
            return default
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return default

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp < timedelta(seconds=self.CACHE_TTL_SECONDS):
                self.logger.debug(f"Cache hit for key: {key}")
                return value
            self.logger.debug(f"Cache expired for key: {key}")
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Set cache value with timestamp."""
        self._cache[key] = (value, datetime.utcnow())
        # Cleanup old entries
        cutoff = datetime.utcnow() - timedelta(minutes=1)
        self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}

    def invalidate_cache(self, key: str | None = None) -> None:
        """Invalidate cache entry or entire cache."""
        if key:
            self._cache.pop(key, None)
            self.logger.debug(f"Cache invalidated for key: {key}")
        else:
            self._cache.clear()
            self.logger.debug("Entire cache invalidated")

    async def get_pipeline_metrics(self) -> PipelineMetrics:
        """Get pipeline metrics with caching (server-side aggregation)."""
        cached = self._get_cached("pipeline_metrics")
        if cached:
            return cached

        try:
            # Query aggregated view using asyncpg
            query = "SELECT * FROM public.vw_pipeline_metrics_aggregated LIMIT 1"
            async with self.pool.acquire() as conn:
                response = await conn.fetch(query)

            if not response or len(response) == 0:
                raise RuntimeError("No aggregated metrics available")

            data = response[0]

            # Calculate throughput from recent count
            current_throughput = float(data.get("recent_24h_count", 0)) / 24.0

            metrics = PipelineMetrics(
                total_documents=int(data.get("total_documents", 0)),
                documents_pending=int(data.get("documents_pending", 0)),
                documents_processing=int(data.get("documents_processing", 0)),
                documents_completed=int(data.get("documents_completed", 0)),
                documents_failed=int(data.get("documents_failed", 0)),
                success_rate=float(data.get("success_rate", 0.0)),
                avg_processing_time_seconds=0.0,  # Calculated separately if needed
                current_throughput_docs_per_hour=round(current_throughput, 2),
            )

            self._set_cache("pipeline_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get pipeline metrics: {e}", exc_info=True)
            # Return default values
            return PipelineMetrics(
                total_documents=0,
                documents_pending=0,
                documents_processing=0,
                documents_completed=0,
                documents_failed=0,
                success_rate=0.0,
                avg_processing_time_seconds=0.0,
                current_throughput_docs_per_hour=0.0,
            )

    async def get_stage_metrics(self) -> list[StageMetrics]:
        """Get stage-specific metrics with caching (server-side aggregation)."""
        cached = self._get_cached("stage_metrics")
        if cached:
            return cached

        try:
            # Query aggregated stage metrics view using asyncpg
            query = "SELECT * FROM public.vw_stage_metrics_aggregated"
            async with self.pool.acquire() as conn:
                stage_data = await conn.fetch(query)
            stage_data = stage_data or []

            metrics = []
            for stage in stage_data:
                stage_name = stage.get("stage_name", "unknown")
                completed = int(stage.get("completed_count", 0))
                failed = int(stage.get("failed_count", 0))
                total = int(stage.get("total_executions", 0))
                success_rate = (completed / total * 100) if total > 0 else 0.0

                # Get last activity and current document from stage_status
                activity_query = """
                    SELECT
                        MAX(updated_at) as last_activity,
                        COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
                        (SELECT document_id FROM krai_core.stage_status
                         WHERE stage_name = $1 AND status = 'processing'
                         LIMIT 1) as current_document_id
                    FROM krai_core.stage_status
                    WHERE stage_name = $1
                """
                async with self.pool.acquire() as conn:
                    activity_data = await conn.fetch(activity_query, stage_name)
                activity = activity_data[0] if activity_data else {}

                last_activity = activity.get("last_activity")
                processing_count = int(activity.get("processing_count", 0))
                current_document_id = activity.get("current_document_id")

                # Calculate is_active: True if processing_count > 0 OR last_activity < 60s
                is_active = processing_count > 0
                if not is_active and last_activity:
                    last_activity_dt = self.safe_parse_datetime(last_activity)
                    if last_activity_dt:
                        is_active = (datetime.utcnow() - last_activity_dt.replace(tzinfo=None)) < timedelta(seconds=60)

                # Get error count in last hour
                error_query = """
                    SELECT COUNT(*) as error_count
                    FROM krai_core.stage_status
                    WHERE stage_name = $1
                      AND status = 'failed'
                      AND updated_at > NOW() - INTERVAL '1 hour'
                """
                async with self.pool.acquire() as conn:
                    error_data = await conn.fetch(error_query, stage_name)
                error_count_last_hour = int(error_data[0].get("error_count", 0)) if error_data else 0

                metrics.append(
                    StageMetrics(
                        stage_name=stage_name,
                        pending_count=0,  # Not in aggregated view
                        processing_count=processing_count,
                        completed_count=completed,
                        failed_count=failed,
                        skipped_count=0,  # Not in aggregated view
                        avg_duration_seconds=round(float(stage.get("avg_duration_seconds", 0.0)), 2),
                        success_rate=round(success_rate, 2),
                        is_active=is_active,
                        last_activity=self.safe_parse_datetime(last_activity),
                        current_document_id=current_document_id,
                        error_count_last_hour=error_count_last_hour,
                    )
                )

            self._set_cache("stage_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get stage metrics: {e}", exc_info=True)
            return []

    async def get_queue_metrics(self) -> QueueMetrics:
        """Get queue metrics with caching (server-side aggregation)."""
        cached = self._get_cached("queue_metrics")
        if cached:
            return cached

        try:
            # Query aggregated view using asyncpg
            query = "SELECT * FROM public.vw_queue_metrics_aggregated LIMIT 1"
            async with self.pool.acquire() as conn:
                response = await conn.fetch(query)

            if not response or len(response) == 0:
                raise RuntimeError("No aggregated queue metrics available")

            data = response[0]

            # Get task type breakdown
            type_query = "SELECT task_type FROM krai_system.processing_queue"
            async with self.pool.acquire() as conn:
                type_response = await conn.fetch(type_query)
            by_task_type: dict[str, int] = {}
            for item in type_response or []:
                task_type = item.get("task_type", "unknown")
                by_task_type[task_type] = by_task_type.get(task_type, 0) + 1

            metrics = QueueMetrics(
                total_items=int(data.get("total_items", 0)),
                pending_count=int(data.get("pending_count", 0)),
                processing_count=int(data.get("processing_count", 0)),
                completed_count=int(data.get("completed_count", 0)),
                failed_count=int(data.get("failed_count", 0)),
                avg_wait_time_seconds=round(float(data.get("avg_processing_time_seconds", 0.0)), 2),
                by_task_type=by_task_type,
            )

            self._set_cache("queue_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get queue metrics: {e}", exc_info=True)
            return QueueMetrics(
                total_items=0,
                pending_count=0,
                processing_count=0,
                completed_count=0,
                failed_count=0,
                avg_wait_time_seconds=0.0,
                by_task_type={},
            )

    async def get_queue_items(self, limit: int = 100, status_filter: str | None = None) -> list[QueueItem]:
        """Get queue items with optional filtering."""
        try:
            # Build query dynamically
            conditions = []
            params = []
            param_count = 0

            if status_filter:
                param_count += 1
                conditions.append(f"status = ${param_count}")
                params.append(status_filter)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT * FROM krai_system.processing_queue
                {where_clause}
                ORDER BY priority DESC, scheduled_at
                LIMIT ${param_count + 1}
            """
            params.append(limit)

            async with self.pool.acquire() as conn:
                items = await conn.fetch(query, *params)
            items = items or []

            return [
                QueueItem(
                    id=str(item.get("id", "")),
                    task_type=item.get("task_type", "unknown"),
                    status=item.get("status", "unknown"),
                    priority=item.get("priority", 0),
                    document_id=item.get("document_id"),
                    scheduled_at=self.safe_parse_datetime(item.get("scheduled_at"), datetime.utcnow()),
                    started_at=self.safe_parse_datetime(item.get("started_at")),
                    retry_count=item.get("retry_count", 0),
                    error_message=item.get("error_message"),
                )
                for item in items
            ]

        except Exception as e:
            self.logger.error(f"Failed to get queue items: {e}", exc_info=True)
            return []

    async def get_duplicate_metrics(self) -> DuplicateMetrics:
        """Get duplicate detection metrics with caching."""
        cached = self._get_cached("duplicate_metrics")
        if cached:
            return cached

        try:
            # Query duplicates by file_hash
            async with self.pool.acquire() as conn:
                hash_duplicates = await conn.fetch(
                    "SELECT file_hash, COUNT(*) as count FROM krai_core.documents GROUP BY file_hash HAVING COUNT(*) > 1"
                )
                hash_duplicates = hash_duplicates or []

                # Query duplicates by filename
                filename_duplicates = await conn.fetch(
                    "SELECT filename, COUNT(*) as count FROM krai_core.documents GROUP BY filename HAVING COUNT(*) > 1"
                )
            filename_duplicates = filename_duplicates or []

            duplicate_documents = []
            for dup in hash_duplicates:
                duplicate_documents.append(
                    {
                        "file_hash": dup.get("file_hash"),
                        "count": dup.get("count", 0),
                        "filenames": dup.get("filenames", []),
                    }
                )

            metrics = DuplicateMetrics(
                total_duplicates=len(hash_duplicates) + len(filename_duplicates),
                duplicate_by_hash=len(hash_duplicates),
                duplicate_by_filename=len(filename_duplicates),
                duplicate_documents=duplicate_documents,
            )

            self._set_cache("duplicate_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get duplicate metrics: {e}", exc_info=True)
            return DuplicateMetrics(
                total_duplicates=0,
                duplicate_by_hash=0,
                duplicate_by_filename=0,
                duplicate_documents=[],
            )

    async def get_validation_metrics(self) -> ValidationMetrics:
        """Get validation error metrics with caching."""
        cached = self._get_cached("validation_metrics")
        if cached:
            return cached

        try:
            # Query documents with errors using asyncpg
            query = "SELECT id, filename, stage_status FROM krai_core.documents"
            async with self.pool.acquire() as conn:
                documents = await conn.fetch(query)
            documents = documents or []

            errors_by_stage: dict[str, int] = {}
            documents_with_errors = []

            for doc in documents:
                stage_status = doc.get("stage_status", {})
                if isinstance(stage_status, dict):
                    for stage, data in stage_status.items():
                        if isinstance(data, dict) and data.get("status") == "failed":
                            errors_by_stage[stage] = errors_by_stage.get(stage, 0) + 1
                            documents_with_errors.append(
                                {
                                    "document_id": str(doc.get("id", "")),
                                    "stage": stage,
                                    "error": data.get("error", "Unknown error"),
                                }
                            )

            metrics = ValidationMetrics(
                total_validation_errors=sum(errors_by_stage.values()),
                errors_by_stage=errors_by_stage,
                documents_with_errors=documents_with_errors[:50],  # Limit to 50
            )

            self._set_cache("validation_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get validation metrics: {e}", exc_info=True)
            return ValidationMetrics(
                total_validation_errors=0,
                errors_by_stage={},
                documents_with_errors=[],
            )

    async def get_processing_metrics(self) -> ProcessingMetrics:
        """Get processing performance metrics with caching."""
        cached = self._get_cached("processing_metrics")
        if cached:
            return cached

        try:
            # Query documents using asyncpg
            query = "SELECT * FROM public.vw_documents"
            async with self.pool.acquire() as conn:
                documents = await conn.fetch(query)
            documents = documents or []

            total_processed = len(documents)
            successful = sum(1 for d in documents if d.get("processing_status") == "completed")
            failed = sum(1 for d in documents if d.get("processing_status") == "failed")
            success_rate = (successful / total_processed * 100) if total_processed > 0 else 0.0

            # Calculate average processing time
            durations = []
            for doc in documents:
                if doc.get("stage_status") and isinstance(doc["stage_status"], dict):
                    for stage_data in doc["stage_status"].values():
                        if isinstance(stage_data, dict) and "duration_seconds" in stage_data:
                            durations.append(stage_data["duration_seconds"])
            avg_processing_time = sum(durations) / len(durations) if durations else 0.0

            # Aggregate by document type
            processing_by_type: dict[str, int] = {}
            for doc in documents:
                doc_type = doc.get("document_type", "unknown")
                processing_by_type[doc_type] = processing_by_type.get(doc_type, 0) + 1

            metrics = ProcessingMetrics(
                total_processed=total_processed,
                successful=successful,
                failed=failed,
                success_rate=round(success_rate, 2),
                avg_processing_time=round(avg_processing_time, 2),
                processing_by_type=processing_by_type,
            )

            self._set_cache("processing_metrics", metrics)
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get processing metrics: {e}", exc_info=True)
            return ProcessingMetrics(
                total_processed=0,
                successful=0,
                failed=0,
                success_rate=0.0,
                avg_processing_time=0.0,
                processing_by_type={},
            )

    async def get_data_quality_metrics(self) -> DataQualityResponse:
        """Get comprehensive data quality metrics."""
        duplicate_metrics = await self.get_duplicate_metrics()
        validation_metrics = await self.get_validation_metrics()
        processing_metrics = await self.get_processing_metrics()

        return DataQualityResponse(
            duplicate_metrics=duplicate_metrics,
            validation_metrics=validation_metrics,
            processing_metrics=processing_metrics,
        )

    async def get_hardware_metrics(self) -> HardwareStatus:
        """Get hardware status metrics with caching."""
        cached = self._get_cached("hardware_metrics")
        if cached:
            return cached

        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            ram_available_gb = ram.available / (1024**3)

            # Try to get GPU metrics
            gpu_available = False
            gpu_percent = None
            gpu_memory_used_gb = None
            gpu_memory_total_gb = None

            try:
                import pynvml

                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                gpu_available = True
                gpu_percent = float(gpu_util.gpu)
                gpu_memory_used_gb = gpu_info.used / (1024**3)
                gpu_memory_total_gb = gpu_info.total / (1024**3)
                pynvml.nvmlShutdown()
            except Exception:
                pass

            metrics = HardwareStatus(
                cpu_percent=round(cpu_percent, 2),
                ram_percent=round(ram_percent, 2),
                ram_available_gb=round(ram_available_gb, 2),
                gpu_available=gpu_available,
                gpu_percent=round(gpu_percent, 2) if gpu_percent is not None else None,
                gpu_memory_used_gb=round(gpu_memory_used_gb, 2) if gpu_memory_used_gb is not None else None,
                gpu_memory_total_gb=round(gpu_memory_total_gb, 2) if gpu_memory_total_gb is not None else None,
            )

            # Cache for 1 second (more frequent than other metrics)
            self._cache["hardware_metrics"] = (metrics, datetime.utcnow())
            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get hardware metrics: {e}", exc_info=True)
            return HardwareStatus(
                cpu_percent=0.0,
                ram_percent=0.0,
                ram_available_gb=0.0,
                gpu_available=False,
            )

    async def get_processor_health(self) -> list[ProcessorHealthStatus]:
        """Get processor health status for all stages with caching."""
        cached = self._get_cached("processor_health")
        if cached:
            return cached

        try:
            # Define all 15 stages with processor names
            stages = [
                ("upload", "UploadProcessor"),
                ("text_extraction", "TextProcessor"),
                ("table_extraction", "TableProcessor"),
                ("svg_processing", "SVGProcessor"),
                ("image_processing", "ImageProcessor"),
                ("visual_embedding", "VisualEmbeddingProcessor"),
                ("link_extraction", "LinkProcessor"),
                ("chunk_prep", "ChunkPrepProcessor"),
                ("classification", "ClassificationProcessor"),
                ("metadata_extraction", "MetadataProcessor"),
                ("parts_extraction", "PartsProcessor"),
                ("series_detection", "SeriesDetectionProcessor"),
                ("storage", "StorageProcessor"),
                ("embedding", "EmbeddingProcessor"),
                ("search_indexing", "SearchIndexingProcessor"),
            ]

            processors = []
            for stage_name, processor_name in stages:
                # Query stage status for this stage
                query = """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'processing') as documents_processing,
                        COUNT(*) FILTER (WHERE status = 'pending') as documents_in_queue,
                        MAX(updated_at) as last_activity,
                        (SELECT document_id FROM krai_core.stage_status
                         WHERE stage_name = $1 AND status = 'processing'
                         LIMIT 1) as current_document_id,
                        COUNT(*) FILTER (WHERE status = 'failed' AND updated_at > NOW() - INTERVAL '1 hour') as failed_last_hour,
                        COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '1 hour') as total_last_hour,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE status = 'completed') as avg_duration
                    FROM krai_core.stage_status
                    WHERE stage_name = $1
                """
                async with self.pool.acquire() as conn:
                    result = await conn.fetch(query, stage_name)
                data = result[0] if result else {}

                documents_processing = int(data.get("documents_processing", 0))
                documents_in_queue = int(data.get("documents_in_queue", 0))
                last_activity = data.get("last_activity")
                current_document_id = data.get("current_document_id")
                failed_last_hour = int(data.get("failed_last_hour", 0))
                total_last_hour = int(data.get("total_last_hour", 0))
                avg_duration = float(data.get("avg_duration", 0.0))

                # Calculate error rate
                error_rate_percent = (failed_last_hour / total_last_hour * 100) if total_last_hour > 0 else 0.0

                # Determine status
                if documents_processing > 0:
                    status = "running"
                elif error_rate_percent > 10:
                    status = "failed"
                elif error_rate_percent > 5:
                    status = "degraded"
                else:
                    status = "idle"

                # Calculate is_active
                is_active = documents_processing > 0
                if not is_active and last_activity:
                    last_activity_dt = self.safe_parse_datetime(last_activity)
                    if last_activity_dt:
                        is_active = (datetime.utcnow() - last_activity_dt.replace(tzinfo=None)) < timedelta(seconds=60)

                # Calculate health score (0-100)
                health_score = 100.0
                health_score -= error_rate_percent * 10  # Deduct based on error rate
                if avg_duration > 0:
                    # Deduct if processing time is unusually high (arbitrary threshold)
                    if avg_duration > 60:  # More than 60 seconds
                        health_score -= min((avg_duration - 60) / 60 * 5, 20)  # Max 20 point deduction
                health_score = max(0.0, min(100.0, health_score))

                processors.append(
                    ProcessorHealthStatus(
                        processor_name=processor_name,
                        stage_name=stage_name,
                        status=status,
                        is_active=is_active,
                        documents_processing=documents_processing,
                        documents_in_queue=documents_in_queue,
                        last_activity=self.safe_parse_datetime(last_activity),
                        current_document_id=current_document_id,
                        error_rate_percent=round(error_rate_percent, 2),
                        avg_processing_time_seconds=round(avg_duration, 2),
                        health_score=round(health_score, 2),
                    )
                )

            self._set_cache("processor_health", processors)
            return processors

        except Exception as e:
            self.logger.error(f"Failed to get processor health: {e}", exc_info=True)
            return []

    async def get_stage_queue(self, stage_name: str, limit: int = 50) -> StageQueueResponse:
        """Get queue items for a specific stage."""
        try:
            # Query stage_status for pending and processing items
            query = """
                SELECT
                    id,
                    document_id,
                    stage_name,
                    status,
                    created_at,
                    updated_at,
                    metadata
                FROM krai_core.stage_status
                WHERE stage_name = $1
                  AND status IN ('pending', 'processing')
                ORDER BY created_at
                LIMIT $2
            """
            async with self.pool.acquire() as conn:
                items_data = await conn.fetch(query, stage_name, limit)
            items_data = items_data or []

            # Convert to QueueItem format
            queue_items = []
            for item in items_data:
                metadata = item.get("metadata", {})
                queue_items.append(
                    QueueItem(
                        id=str(item.get("id", "")),
                        task_type=f"{stage_name}_processing",
                        status=item.get("status", "unknown"),
                        priority=metadata.get("priority", 5) if isinstance(metadata, dict) else 5,
                        document_id=item.get("document_id"),
                        scheduled_at=self.safe_parse_datetime(item.get("created_at"), datetime.utcnow()),
                        started_at=(
                            self.safe_parse_datetime(item.get("updated_at"))
                            if item.get("status") == "processing"
                            else None
                        ),
                        retry_count=metadata.get("retry_count", 0) if isinstance(metadata, dict) else 0,
                        error_message=None,
                    )
                )

            # Calculate metrics
            pending_count = sum(1 for item in items_data if item.get("status") == "pending")
            processing_count = sum(1 for item in items_data if item.get("status") == "processing")

            # Calculate average wait time
            wait_times = []
            for item in items_data:
                if item.get("status") == "pending" and item.get("created_at"):
                    created_at = self.safe_parse_datetime(item.get("created_at"))
                    if created_at:
                        wait_time = (datetime.utcnow() - created_at.replace(tzinfo=None)).total_seconds()
                        wait_times.append(wait_time)
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0.0

            # Get oldest item age
            oldest_item_age = max(wait_times) if wait_times else 0.0

            return StageQueueResponse(
                stage_name=stage_name,
                queue_items=queue_items,
                pending_count=pending_count,
                processing_count=processing_count,
                avg_wait_time_seconds=round(avg_wait_time, 2),
                oldest_item_age_seconds=round(oldest_item_age, 2),
            )

        except Exception as e:
            self.logger.error(f"Failed to get stage queue for {stage_name}: {e}", exc_info=True)
            return StageQueueResponse(
                stage_name=stage_name,
                queue_items=[],
                pending_count=0,
                processing_count=0,
                avg_wait_time_seconds=0.0,
                oldest_item_age_seconds=0.0,
            )

    async def get_stage_errors(self, stage_name: str, limit: int = 100) -> StageErrorLogsResponse:
        """Get error logs for a specific stage."""
        try:
            # Query failed stage_status entries
            query = """
                SELECT
                    id,
                    document_id,
                    stage_name,
                    status,
                    error,
                    metadata,
                    updated_at,
                    created_at
                FROM krai_core.stage_status
                WHERE stage_name = $1
                  AND status = 'failed'
                ORDER BY updated_at DESC
                LIMIT $2
            """
            async with self.pool.acquire() as conn:
                errors_data = await conn.fetch(query, stage_name, limit)
            errors_data = errors_data or []

            # Convert to StageErrorLog format
            errors = []
            for error in errors_data:
                metadata = error.get("metadata", {})
                retry_count = metadata.get("retry_count", 0) if isinstance(metadata, dict) else 0
                can_retry = retry_count < 3

                errors.append(
                    StageErrorLog(
                        id=str(error.get("id", "")),
                        document_id=error.get("document_id", ""),
                        stage_name=error.get("stage_name", ""),
                        error_message=error.get("error", "Unknown error"),
                        error_code=metadata.get("error_code") if isinstance(metadata, dict) else None,
                        stack_trace=metadata.get("stack_trace") if isinstance(metadata, dict) else None,
                        occurred_at=self.safe_parse_datetime(error.get("updated_at"), datetime.utcnow()),
                        retry_count=retry_count,
                        can_retry=can_retry,
                    )
                )

            # Calculate error rate for last 24 hours
            error_rate_query = """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    COUNT(*) as total_count
                FROM krai_core.stage_status
                WHERE stage_name = $1
                  AND updated_at > NOW() - INTERVAL '1 day'
            """
            async with self.pool.acquire() as conn:
                rate_data = await conn.fetch(error_rate_query, stage_name)
            rate = rate_data[0] if rate_data else {}
            failed_count = int(rate.get("failed_count", 0))
            total_count = int(rate.get("total_count", 0))
            error_rate_percent = (failed_count / total_count * 100) if total_count > 0 else 0.0

            return StageErrorLogsResponse(
                stage_name=stage_name,
                errors=errors,
                total_errors=len(errors),
                error_rate_percent=round(error_rate_percent, 2),
            )

        except Exception as e:
            self.logger.error(f"Failed to get stage errors for {stage_name}: {e}", exc_info=True)
            return StageErrorLogsResponse(
                stage_name=stage_name,
                errors=[],
                total_errors=0,
                error_rate_percent=0.0,
            )

    async def retry_stage(self, document_id: str, stage_name: str) -> bool:
        """Retry a failed stage for a document."""
        try:
            # Update stage_status to reset to pending
            query = """
                UPDATE krai_core.stage_status
                SET
                    status = 'pending',
                    error = NULL,
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{retry_count}',
                        (COALESCE((metadata->>'retry_count')::int, 0) + 1)::text::jsonb
                    ),
                    updated_at = NOW()
                WHERE document_id = $1
                  AND stage_name = $2
                  AND status = 'failed'
                RETURNING id
            """
            async with self.pool.acquire() as conn:
                result = await conn.fetch(query, document_id, stage_name)

            if result and len(result) > 0:
                self.logger.info(f"Retry triggered for document {document_id}, stage {stage_name}")
                # Invalidate relevant caches
                self.invalidate_cache("processor_health")
                self.invalidate_cache("stage_metrics")

                # Broadcast processor state change via WebSocket
                try:
                    from api.websocket import broadcast_processor_state_change

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
                    processor_name = stage_to_processor.get(stage_name, f"{stage_name}Processor")
                    await broadcast_processor_state_change(
                        processor_name=processor_name, stage_name=stage_name, status="pending", document_id=document_id
                    )
                except Exception as ws_error:
                    self.logger.warning(f"Failed to broadcast processor state change: {ws_error}")

                return True
            self.logger.warning(f"No failed stage found for document {document_id}, stage {stage_name}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to retry stage {stage_name} for document {document_id}: {e}", exc_info=True)
            return False
