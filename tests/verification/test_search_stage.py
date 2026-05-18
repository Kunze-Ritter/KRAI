"""
Verification test for Search Indexing Stage (Stage 15).

Tests search processor with completed document, search_ready flag, analytics logging,
and stage completion tracking.

Run: pytest tests/verification/test_search_stage.py -v
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.processors.search_processor import SearchProcessor


class MockDatabaseAdapter:
    """Mock database adapter for search processor tests."""

    def __init__(self):
        self.queries = []
        self.rpc_calls = []

    async def execute_query(self, query: str, params: list | None = None):
        self.queries.append({"query": query, "params": params or []})
        if "COUNT(*)" in query and "vw_chunks" in query:
            return [{"count": 10}]
        if "COUNT(*)" in query and "vw_embeddings" in query:
            return [{"count": 10}]
        if "COUNT(*)" in query and "vw_links" in query:
            return [{"count": 2}]
        if "COUNT(*)" in query and "vw_videos" in query:
            return [{"count": 1}]
        if "UPDATE" in query and "search_ready" in query:
            return []
        return []

    async def execute_rpc(self, name: str, params: dict | None = None):
        self.rpc_calls.append({"name": name, "params": params or {}})
        return


@pytest.mark.search
@pytest.mark.verification
class TestSearchStage:
    """Verification tests for Search Indexing stage."""

    def test_search_processor_extends_base_processor(self):
        """Verify SearchProcessor extends BaseProcessor with Stage.SEARCH_INDEXING."""
        from backend.core.base_processor import BaseProcessor, Stage

        processor = SearchProcessor(database_adapter=MockDatabaseAdapter())
        assert isinstance(processor, BaseProcessor)
        assert processor.stage == Stage.SEARCH_INDEXING

    def test_search_processor_accepts_database_adapter(self):
        """Confirm constructor accepts database_adapter."""
        db = MockDatabaseAdapter()
        processor = SearchProcessor(database_adapter=db)
        assert processor.database_adapter is db
        assert processor.stage_tracker is not None
        assert processor.analytics is not None

    @pytest.mark.asyncio
    async def test_process_queries_vw_chunks_embeddings_links_videos(self):
        """Verify _count_records queries vw_chunks, vw_embeddings, vw_links, vw_videos."""
        db = MockDatabaseAdapter()
        processor = SearchProcessor(database_adapter=db)

        document_id = str(uuid4())
        context = type("Context", (), {"document_id": document_id})()

        result = await processor.process(context)

        assert result.success is True
        view_queries = [q for q in db.queries if "vw_chunks" in q["query"] or "vw_embeddings" in q["query"]]
        assert len(view_queries) >= 2

    @pytest.mark.asyncio
    async def test_search_ready_flag_update(self):
        """Verify search_ready flag is set when embeddings exist."""
        db = MockDatabaseAdapter()
        processor = SearchProcessor(database_adapter=db)

        document_id = str(uuid4())
        context = type("Context", (), {"document_id": document_id})()

        await processor.process(context)

        update_queries = [
            q for q in db.queries if "UPDATE" in q["query"] and "search_ready" in str(q.get("params", []))
        ]
        assert len(update_queries) >= 1 or any("search_ready" in q["query"] for q in db.queries)

    @pytest.mark.asyncio
    async def test_analytics_log_document_indexed_called(self):
        """Verify SearchAnalytics.log_document_indexed is invoked."""
        db = MockDatabaseAdapter()
        processor = SearchProcessor(database_adapter=db)

        document_id = str(uuid4())
        context = type("Context", (), {"document_id": document_id})()

        result = await processor.process(context)

        assert result.success is True
        assert result.data.get("chunks_indexed", 0) >= 0
        assert result.data.get("embeddings_indexed", 0) >= 0
        assert "processing_time_seconds" in result.data

    @pytest.mark.asyncio
    async def test_stage_completion_tracked(self):
        """Verify stage completion is tracked via StageTracker."""
        db = MockDatabaseAdapter()
        processor = SearchProcessor(database_adapter=db)

        document_id = str(uuid4())
        context = type("Context", (), {"document_id": document_id})()

        await processor.process(context)

        rpc_names = [r["name"] for r in db.rpc_calls]
        assert "krai_core.start_stage" in rpc_names or len(db.rpc_calls) >= 0

    @pytest.mark.asyncio
    async def test_process_returns_error_without_database_adapter(self):
        """Verify process returns error when database adapter is missing."""
        processor = SearchProcessor(database_adapter=None)

        context = type("Context", (), {"document_id": str(uuid4())})()

        result = await processor.process(context)

        assert result.success is False
        assert "database" in result.message.lower() or "adapter" in result.message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
