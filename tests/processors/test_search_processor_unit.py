"""Unit tests for SearchProcessor internals.

These tests exercise record counting, basic success/error paths and
graceful handling of adapter failures using the MockDatabaseAdapter
fixture from ``conftest.py``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.search_processor import SearchProcessor

pytestmark = [pytest.mark.processor, pytest.mark.search]


class TestSearchProcessorConfiguration:
    """Configuration and error handling around missing adapters."""

    @pytest.mark.asyncio
    async def test_process_without_database_adapter(self) -> None:
        """If no database adapter is provided, process() returns an error result."""

        processor = SearchProcessor(database_adapter=None)
        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/dummy.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)

        assert result.success is False
        assert "Database adapter not configured" in result.message


class TestSearchProcessorCounts:
    """Happy-path tests using the MockDatabaseAdapter in-memory stores."""

    @pytest.mark.asyncio
    async def test_process_counts_records_and_returns_metadata(self, mock_database_adapter) -> None:
        """Counts in vw_chunks/vw_embeddings/vw_links/vw_videos are reflected in result.data."""

        document_id = str(uuid4())

        # Prime chunks (vw_chunks) via direct in-memory store
        mock_database_adapter.chunks["chunk-1"] = {
            "id": "chunk-1",
            "document_id": document_id,
        }

        # Prime embeddings_v2 with document_id in metadata so execute_query can see it
        await mock_database_adapter.create_embedding_v2(
            source_id="chunk-1",
            source_type="text",
            embedding=[0.1, 0.2, 0.3],
            model_name="test-model",
            embedding_context="paper jam in tray 2",
            metadata={"document_id": document_id},
        )

        # Prime a link and a video for completeness
        mock_database_adapter.links["link-1"] = {
            "id": "link-1",
            "document_id": document_id,
        }
        mock_database_adapter.videos["video-1"] = {
            "id": "video-1",
            "document_id": document_id,
        }

        processor = SearchProcessor(database_adapter=mock_database_adapter)

        ctx = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/doc.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)

        assert result.success is True
        assert result.message == "Search indexing completed"

        data = result.data
        assert data["chunks_indexed"] == 1
        assert data["embeddings_indexed"] >= 1
        assert data["links_indexed"] == 1
        assert data["videos_indexed"] == 1
        assert data["processing_time_seconds"] >= 0.0


class TestSearchProcessorErrorHandling:
    """execute_query failures should not raise uncaught exceptions."""

    @pytest.mark.asyncio
    async def test_execute_query_error_is_handled(self, mock_database_adapter, monkeypatch: Any) -> None:
        """If execute_query raises, process() still completes without raising.

        SearchProcessor is designed to swallow execute_query errors inside its
        helper methods (record counting and flag updates) and log them
        instead of failing the entire stage. This test verifies that no
        uncaught exception escapes and that a result object is returned.
        """

        async def failing_execute_query(query: str, params=None):  # type: ignore[override]
            raise RuntimeError("simulated database error")

        monkeypatch.setattr(mock_database_adapter, "execute_query", failing_execute_query)

        processor = SearchProcessor(database_adapter=mock_database_adapter)

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/doc.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)

        # Even though execute_query raises inside helpers, SearchProcessor
        # should handle these errors internally and still return a
        # successful result rather than propagating the exception.
        assert result.success is True
        assert result.message == "Search indexing completed"
