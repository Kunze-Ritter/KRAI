"""E2E-style tests for SearchProcessor using MockDatabaseAdapter.

These tests execute the full search indexing stage, including record
counting and analytics wiring, while stubbing out the actual
SearchAnalytics persistence layer so no real database is required.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.search_processor import SearchProcessor

pytestmark = [pytest.mark.processor, pytest.mark.search]


class TestSearchProcessorE2E:
    """End-to-end indexing behaviour with analytics stubbed."""

    @pytest.mark.asyncio
    async def test_end_to_end_indexing_with_analytics_stub(
        self,
        mock_database_adapter,
    ) -> None:
        """Counts and analytics metadata reflect adapter contents."""

        document_id = str(uuid4())

        # Prime adapter stores with deterministic data
        mock_database_adapter.chunks["chunk-1"] = {
            "id": "chunk-1",
            "document_id": document_id,
        }
        mock_database_adapter.chunks["chunk-2"] = {
            "id": "chunk-2",
            "document_id": document_id,
        }

        # Embeddings with document_id in metadata for counting
        mock_database_adapter.embeddings_v2["emb-1"] = {
            "id": "emb-1",
            "source_id": "chunk-1",
            "source_type": "text",
            "embedding": [0.1, 0.2, 0.3],
            "model_name": "test-model",
            "embedding_context": "paper jam in tray 2",
            "metadata": {"document_id": document_id},
        }

        mock_database_adapter.links["link-1"] = {
            "id": "link-1",
            "document_id": document_id,
        }
        mock_database_adapter.videos["video-1"] = {
            "id": "video-1",
            "document_id": document_id,
        }

        processor = SearchProcessor(database_adapter=mock_database_adapter)

        # Stub SearchAnalytics.log_document_indexed to avoid asyncio.run issues
        analytics_calls: dict[str, Any] = {}

        def fake_log_document_indexed(
            *,
            document_id: str,
            chunks_count: int,
            embeddings_count: int,
            processing_time_seconds: float,
        ) -> bool:
            analytics_calls["document_id"] = document_id
            analytics_calls["chunks_count"] = chunks_count
            analytics_calls["embeddings_count"] = embeddings_count
            analytics_calls["processing_time_seconds"] = processing_time_seconds
            return True

        processor.analytics.log_document_indexed = fake_log_document_indexed  # type: ignore[assignment]

        ctx = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/search_e2e.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)

        assert result.success is True
        assert result.message == "Search indexing completed"

        data = result.data
        assert data["chunks_indexed"] == 2
        assert data["embeddings_indexed"] == 1
        assert data["links_indexed"] == 1
        assert data["videos_indexed"] == 1

        # Analytics stub should have seen the same counts
        assert analytics_calls["document_id"] == document_id
        assert analytics_calls["chunks_count"] == data["chunks_indexed"]
        assert analytics_calls["embeddings_count"] == data["embeddings_indexed"]
        assert analytics_calls["processing_time_seconds"] >= 0.0
