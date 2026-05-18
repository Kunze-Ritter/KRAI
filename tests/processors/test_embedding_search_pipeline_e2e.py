"""Embedding + Search pipeline E2E tests.

Chains Stage 7 (EmbeddingProcessor) and Stage 10 (SearchProcessor) using the
in‑memory MockDatabaseAdapter. Verifies that record counts observed by the
search stage match what the embedding stage has written.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.embedding_processor import EmbeddingProcessor
from backend.processors.search_processor import SearchProcessor
from backend.processors.stage_tracker import StageTracker


class E2EEmbeddingProcessor(EmbeddingProcessor):
    """EmbeddingProcessor variant wired to MockDatabaseAdapter.

    - Avoids real Ollama calls by forcing `_check_ollama` to succeed.
    - Treats the adapter as the source of truth for chunks and embeddings.
    - Bypasses database-specific `.table()` APIs entirely.
    """

    def __init__(self, database_adapter, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(supabase_client=None, enable_embeddings_v2=True, **kwargs)
        self.database_adapter = database_adapter
        self.stage_tracker = StageTracker(database_adapter)
        self.ollama_available = True
        # Context embeddings and database-backed multi-modal views are
        # disabled for these focused tests.
        self.enable_context_embeddings = False

    def _check_ollama(self) -> bool:  # type: ignore[override]
        return True

    def is_configured(self) -> bool:  # type: ignore[override]
        return True

    def _store_embedding(  # type: ignore[override]
        self,
        chunk_id: str,
        document_id,
        embedding: list[float],
        chunk_data: dict[str, Any],
    ) -> bool:
        """Synchronously persist embedding into mock adapter stores.

        This simulates the behaviour of storing into `vw_chunks` and
        `embeddings_v2` without requiring PostgreSQL or pgvector.
        """

        doc_id_str = str(document_id)
        chunk_key = str(chunk_id)

        # Simulate vw_chunks entry
        self.database_adapter.chunks[chunk_key] = {
            "id": chunk_key,
            "document_id": doc_id_str,
            "chunk_index": chunk_data.get("chunk_index", 0),
            "content": chunk_data.get("text", ""),
            "page_start": chunk_data.get("page_start"),
            "page_end": chunk_data.get("page_end"),
            "chunk_type": chunk_data.get("chunk_type", "text"),
            "metadata": (chunk_data.get("metadata") or {}).copy(),
        }

        base_metadata = self.database_adapter.chunks[chunk_key]["metadata"]
        # Ensure document_id is present for downstream counting helpers
        base_metadata.setdefault("document_id", doc_id_str)

        # Simulate krai_intelligence.embeddings_v2 entry
        emb_id = str(uuid4())
        self.database_adapter.embeddings_v2[emb_id] = {
            "id": emb_id,
            "source_id": chunk_key,
            "source_type": "text",
            "embedding": embedding,
            "model_name": self.model_name,
            "embedding_context": chunk_data.get("text", "")[:500],
            "metadata": base_metadata.copy(),
        }

        # Track legacy-style mapping from chunk_id to embedding for tests
        self.database_adapter.legacy_embeddings[chunk_key] = {
            "id": emb_id,
            "embedding": embedding,
            "source_type": "text",
            "metadata": base_metadata.copy(),
        }

        return True


pytestmark = [pytest.mark.processor, pytest.mark.embedding, pytest.mark.search]


class TestEmbeddingSearchPipelineE2E:
    @pytest.mark.asyncio
    async def test_embedding_then_search_produces_consistent_counts(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_chunks_with_content,
    ) -> None:
        """Stage 7 followed by Stage 10 yields aligned counts and readiness."""

        document_id = sample_chunks_with_content[0]["document_id"]

        # Prepare text chunks for embedding stage
        embed_chunks: list[dict[str, Any]] = []
        for chunk in sample_chunks_with_content[:6]:
            embed_chunks.append(
                {
                    "chunk_id": chunk["id"],
                    "text": chunk["content"],
                    "chunk_index": chunk["chunk_index"],
                    "chunk_type": chunk["metadata"].get("chunk_type", "text"),
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "metadata": dict(chunk.get("metadata", {})),
                }
            )

        # --- Stage 7: EmbeddingProcessor ---
        embedding_processor = E2EEmbeddingProcessor(database_adapter=mock_database_adapter, batch_size=4)
        embedding_processor._generate_embedding = (  # type: ignore[assignment]
            lambda text: mock_embedding_service._generate_embedding(text)
        )

        embed_ctx = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/embed_search_pipeline.pdf",
            document_type="service_manual",
        )
        embed_ctx.chunks = embed_chunks  # type: ignore[attr-defined]

        embed_result = await embedding_processor.process(embed_ctx)

        assert embed_result["success"] is True
        assert embed_result["embeddings_created"] == len(embed_chunks)

        # --- Stage 10: SearchProcessor ---
        search_processor = SearchProcessor(database_adapter=mock_database_adapter)

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

        search_processor.analytics.log_document_indexed = fake_log_document_indexed  # type: ignore[assignment]

        search_ctx = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/search_pipeline.pdf",
            document_type="service_manual",
        )

        search_result = await search_processor.process(search_ctx)

        assert search_result.success is True
        assert search_result.message == "Search indexing completed"

        data = search_result.data
        assert data["chunks_indexed"] == len(embed_chunks)
        assert data["embeddings_indexed"] == len(embed_chunks)

        # Analytics stub should see the same counts
        assert analytics_calls["document_id"] == document_id
        assert analytics_calls["chunks_count"] == data["chunks_indexed"]
        assert analytics_calls["embeddings_count"] == data["embeddings_indexed"]

        # Our mock helper summarises readiness purely from in-memory counts
        status = await mock_database_adapter.get_document_search_status(document_id)
        assert status["search_ready"] is True
        assert status["chunks_count"] == len(embed_chunks)
        assert status["embeddings_count"] == len(embed_chunks)
