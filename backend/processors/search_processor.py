"""Search Processor - Finalize document indexing for search readiness."""

from __future__ import annotations

import time
from typing import Any

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage

from .search_analytics import SearchAnalytics
from .stage_tracker import StageTracker


class SearchProcessor(BaseProcessor):
    """Stage 10 processor: ensure document is ready for search & log analytics."""

    def __init__(self, database_adapter=None, ai_service=None):
        super().__init__(name="search_processor")
        self.stage = Stage.SEARCH_INDEXING
        self.database_adapter = database_adapter
        self.ai_service = ai_service  # Reserved for future semantic scoring

        # Initialize StageTracker with database adapter
        if database_adapter:
            from .stage_tracker import StageTracker

            self.stage_tracker: StageTracker | None = StageTracker(database_adapter)
        else:
            self.stage_tracker = None
            self.logger.warning("SearchProcessor initialized without database adapter")

        # Initialize SearchAnalytics with database adapter

        self.analytics = SearchAnalytics(database_adapter)

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Finalize search indexing for the provided processing context."""
        document_id = str(context.document_id)

        if not self.database_adapter:
            self.logger.error("SearchProcessor requires a database adapter")
            return self._create_result(False, "Database adapter not configured", {})

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            start_time = time.time()

            if self.stage_tracker:
                await self.stage_tracker.start_stage(document_id, self.stage)

            try:
                chunks_count = await self._count_records("vw_chunks", document_id)
                embeddings_count = await self._count_records("vw_embeddings", document_id)
                links_count = await self._count_records("vw_links", document_id)
                videos_count = await self._count_records("vw_videos", document_id)

                if embeddings_count == 0 and chunks_count > 0:
                    adapter.warning("Embeddings missing - search results may be limited")

                await self._update_document_flags(document_id, embeddings_ready=embeddings_count > 0, adapter=adapter)

                processing_time = time.time() - start_time

                self.analytics.log_document_indexed(
                    document_id=document_id,
                    chunks_count=chunks_count,
                    embeddings_count=embeddings_count,
                    processing_time_seconds=processing_time,
                )

                stage_metadata = {
                    "chunks_indexed": chunks_count,
                    "embeddings_indexed": embeddings_count,
                    "links_indexed": links_count,
                    "videos_indexed": videos_count,
                    "processing_time_seconds": round(processing_time, 2),
                }

                if self.stage_tracker:
                    await self.stage_tracker.complete_stage(document_id, self.stage, stage_metadata)

                return self._create_result(success=True, message="Search indexing completed", data=stage_metadata)

            except Exception as exc:
                adapter.error("Search indexing failed: %s", exc)
                self.logger.error(f"Search indexing failed: {exc}")
                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(document_id, self.stage, error=str(exc))
                return self._create_result(False, f"Search indexing error: {exc}", {})

    async def _count_records(self, view_name: str, document_id: str) -> int:
        """Return exact count of records for a document in the given view."""
        try:
            query = f"SELECT COUNT(*) as count FROM {view_name} WHERE document_id = $1"
            result = await self.database_adapter.execute_query(query, [document_id])
            return result[0]["count"] if result else 0
        except Exception as exc:
            self.logger.debug(f"Failed counting records in {view_name}: {exc}")
            return 0

    async def _update_document_flags(self, document_id: str, embeddings_ready: bool, adapter=None) -> None:
        """Update document level flags to signal search readiness."""
        try:
            # search_ready: bound parameter
            # search_ready_at: use SQL NOW() when embeddings exist (not a bound string literal)
            set_clauses: list[str] = []
            params: list[Any] = []
            param_index = 1

            set_clauses.append(f"search_ready = ${param_index}")
            params.append(embeddings_ready)
            param_index += 1

            if embeddings_ready:
                # Use SQL function NOW() in SET clause - no bound parameter
                set_clauses.append("search_ready_at = NOW()")

            if set_clauses:
                params.append(document_id)
                query = f"UPDATE vw_documents SET {', '.join(set_clauses)} WHERE id = ${param_index}"
                await self.database_adapter.execute_query(query, params)

        except Exception as exc:
            logger = adapter if adapter else self.logger
            logger.debug("Failed updating document search flags: %s", exc)

    def _create_result(self, success: bool, message: str, data: dict) -> ProcessingResult:
        """Create a processing result object using BaseProcessor helpers"""
        if success:
            return self.create_success_result(data=data, metadata={"message": message})
        error = ProcessingError(message, self.name, "SEARCH_INDEXING_ERROR")
        return self.create_error_result(error=error, metadata={})
