"""
Search Analytics Tracker - Stage 8 Completion
Track search queries, performance metrics, and usage analytics.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from .logger import get_logger


class SearchAnalytics:
    """
    Search Analytics Tracker

    Tracks:
    - Search queries and results
    - Query performance metrics
    - User search patterns
    - Popular queries
    """

    def __init__(self, database_adapter=None):
        """
        Initialize search analytics

        Args:
            database_adapter: Database adapter for database operations
        """
        self.database_adapter = database_adapter
        self.logger = get_logger()

    def _run_async_write(self, coro) -> bool:
        if not self.database_adapter:
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        try:
            if loop and loop.is_running():
                task = loop.create_task(coro)
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)
                return True
            asyncio.run(coro)
            return True
        except Exception as exc:
            self.logger.debug(f"Failed to schedule analytics write: {exc}")
            return False

    def track_search_query(
        self,
        query: str,
        results_count: int,
        response_time_ms: float,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> bool:
        """
        Track a search query

        Args:
            query: Search query text
            results_count: Number of results returned
            response_time_ms: Response time in milliseconds
            user_id: Optional user ID
            filters: Optional filters applied
            document_id: Optional document filter

        Returns:
            True if tracked successfully
        """
        if not self.database_adapter:
            self.logger.debug("Database adapter not configured, skipping analytics")
            return False

        try:
            record = {
                "query": query,
                "results_count": results_count,
                "response_time_ms": response_time_ms,
                "user_id": user_id,
                "filters": filters or {},
                "document_id": document_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Store in krai_intelligence.search_analytics
            query = "INSERT INTO search_analytics (query, results_count, response_time_ms, user_id, filters, document_id, timestamp) VALUES ($1, $2, $3, $4, $5, $6, $7)"
            params = [
                record["query"],
                record["results_count"],
                record["response_time_ms"],
                record["user_id"],
                record["filters"],
                record["document_id"],
                record["timestamp"],
            ]

            self._run_async_write(self.database_adapter.execute_query(query, params))

            self.logger.debug(f"Tracked search query: {query[:50]}...")
            return True

        except Exception as e:
            self.logger.warning(f"Failed to track search query: {e}")
            return False

    def get_popular_queries(self, limit: int = 10, time_window_days: int = 30) -> list[dict[str, Any]]:
        """
        Get most popular search queries

        Args:
            limit: Number of queries to return
            time_window_days: Time window in days

        Returns:
            List of popular queries with counts
        """
        if not self.database_adapter:
            return []

        try:
            # This would aggregate queries
            # For now, return empty list
            # TODO: Implement with SQL aggregation
            return []

        except Exception as e:
            self.logger.error(f"Failed to get popular queries: {e}")
            return []

    def get_search_metrics(self, document_id: str | None = None, time_window_days: int = 30) -> dict[str, Any]:
        """
        Get search performance metrics

        Args:
            document_id: Optional filter by document
            time_window_days: Time window in days

        Returns:
            Dictionary with metrics
        """
        if not self.database_adapter:
            return {"total_queries": 0, "avg_response_time_ms": 0.0, "avg_results_count": 0.0, "success_rate": 0.0}

        try:
            # This would calculate metrics from search_analytics table
            # For now, return mock metrics
            # TODO: Implement with SQL aggregation

            metrics = {
                "total_queries": 0,
                "avg_response_time_ms": 0.0,
                "avg_results_count": 0.0,
                "success_rate": 1.0,
                "time_window_days": time_window_days,
            }

            if document_id:
                metrics["document_id"] = document_id

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to get search metrics: {e}")
            return {}

    def log_document_indexed(
        self, document_id: str, chunks_count: int, embeddings_count: int, processing_time_seconds: float
    ) -> bool:
        """
        Log that a document was indexed for search

        Args:
            document_id: Document ID
            chunks_count: Number of chunks created
            embeddings_count: Number of embeddings generated
            processing_time_seconds: Processing time

        Returns:
            True if logged successfully
        """
        if not self.database_adapter:
            return False

        try:
            record = {
                "event_type": "document_indexed",
                "document_id": document_id,
                "metadata": {
                    "chunks_count": chunks_count,
                    "embeddings_count": embeddings_count,
                    "processing_time_seconds": processing_time_seconds,
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }

            query = (
                "INSERT INTO search_analytics (event_type, document_id, metadata, timestamp) VALUES ($1, $2, $3, $4)"
            )
            params = [record["event_type"], record["document_id"], record["metadata"], record["timestamp"]]

            self._run_async_write(self.database_adapter.execute_query(query, params))

            self.logger.info(f"✅ Document {document_id} indexed for search")
            self.logger.info(f"   Chunks: {chunks_count}, Embeddings: {embeddings_count}")
            self.logger.info(f"   Time: {processing_time_seconds:.1f}s")

            return True

        except Exception as exc:
            self.logger.debug(f"Failed to log document indexed: {exc}")
            return False


class SearchAnalyticsDecorator:
    """
    Decorator to add analytics tracking to search functions

    Usage:
        @SearchAnalyticsDecorator(supabase)
        def my_search_function(query):
            # ... search logic
            return results
    """

    def __init__(self, database_adapter=None):
        self.analytics = SearchAnalytics(database_adapter)

    def __call__(self, func):
        """Decorate search function with analytics"""

        def wrapper(*args, **kwargs):
            import time

            # Get query from args/kwargs
            query = args[0] if args else kwargs.get("query", kwargs.get("query_text", ""))

            # Time the search
            start_time = time.time()
            results = func(*args, **kwargs)
            end_time = time.time()

            # Track analytics
            response_time_ms = (end_time - start_time) * 1000
            results_count = len(results) if isinstance(results, list) else 0

            self.analytics.track_search_query(
                query=str(query),
                results_count=results_count,
                response_time_ms=response_time_ms,
                document_id=kwargs.get("document_id"),
            )

            return results

        return wrapper
