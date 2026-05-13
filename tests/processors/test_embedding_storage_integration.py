"""Integration tests for legacy vs embeddings_v2 embedding storage.

These tests rely on E2EEmbeddingProcessor writing directly into the
MockDatabaseAdapter in-memory stores, and then assert that the legacy
chunk/embedding view and the new embeddings_v2 representation stay in
sync for both metadata and similarity search behaviour.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.embedding_processor import EmbeddingProcessor
from backend.processors.stage_tracker import StageTracker

pytestmark = [pytest.mark.processor, pytest.mark.embedding]


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


class TestEmbeddingStorageIntegration:
    """Integration-style checks for legacy vs embeddings_v2 storage."""

    @pytest.mark.asyncio
    async def test_embeddings_are_present_in_legacy_and_v2_with_consistent_metadata(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_chunks_with_content,
    ) -> None:
        document_id = sample_chunks_with_content[0]["document_id"]

        # Prepare a small slice of chunks for storage
        processor_chunks: list[dict[str, Any]] = []
        for chunk in sample_chunks_with_content[:8]:
            processor_chunks.append(
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

        processor = E2EEmbeddingProcessor(
            database_adapter=mock_database_adapter,
            batch_size=4,
        )
        processor._generate_embedding = (  # type: ignore[assignment]
            lambda text: mock_embedding_service._generate_embedding(text)
        )

        context = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/embed_storage_integration.pdf",
            document_type="service_manual",
        )
        context.chunks = processor_chunks  # type: ignore[attr-defined]

        result = await processor.process(context)

        assert result["success"] is True
        assert result["embeddings_created"] == len(processor_chunks)

        # For each chunk, verify legacy (chunks + legacy_embeddings) and v2 are aligned
        for chunk in processor_chunks:
            chunk_id = chunk["chunk_id"]

            stored_chunk = mock_database_adapter.chunks.get(chunk_id)
            assert stored_chunk is not None
            assert stored_chunk["document_id"] == document_id
            assert stored_chunk["chunk_index"] == chunk["chunk_index"]
            assert stored_chunk["chunk_type"] == chunk["chunk_type"]

            chunk_meta = stored_chunk.get("metadata") or {}
            assert chunk_meta.get("document_id") == document_id

            legacy_entry = mock_database_adapter.legacy_embeddings.get(chunk_id)
            assert legacy_entry is not None
            assert legacy_entry["source_type"] == "text"
            legacy_meta = legacy_entry.get("metadata") or {}
            assert legacy_meta.get("document_id") == document_id
            assert legacy_meta.get("chunk_type", "text") == chunk["chunk_type"]

            v2_matches = [
                emb for emb in mock_database_adapter.embeddings_v2.values() if emb.get("source_id") == chunk_id
            ]
            assert len(v2_matches) == 1
            v2_entry = v2_matches[0]
            assert v2_entry["source_type"] == "text"
            v2_meta = v2_entry.get("metadata") or {}
            assert v2_meta.get("document_id") == document_id
            assert v2_meta.get("chunk_type", "text") == chunk["chunk_type"]

            # Embedding vectors should be identical in legacy and v2 representations
            assert legacy_entry["embedding"] == v2_entry["embedding"]

    @pytest.mark.asyncio
    async def test_similarity_search_results_are_consistent_between_legacy_and_v2(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_chunks_with_content,
    ) -> None:
        document_id = sample_chunks_with_content[0]["document_id"]

        # Embed a small set of chunks
        processor_chunks: list[dict[str, Any]] = []
        for chunk in sample_chunks_with_content[:6]:
            processor_chunks.append(
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

        processor = E2EEmbeddingProcessor(
            database_adapter=mock_database_adapter,
            batch_size=3,
        )
        processor._generate_embedding = (  # type: ignore[assignment]
            lambda text: mock_embedding_service._generate_embedding(text)
        )

        context = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/embed_storage_similarity.pdf",
            document_type="service_manual",
        )
        context.chunks = processor_chunks  # type: ignore[attr-defined]

        result = await processor.process(context)
        assert result["success"] is True

        # Use one of the embedded texts as the query to guarantee a strong match
        query_text = processor_chunks[0]["text"]
        query_vec = mock_embedding_service._generate_embedding(query_text)

        # New system: embeddings_v2 via MockDatabaseAdapter.search_embeddings
        v2_results = await mock_database_adapter.search_embeddings(
            query_embedding=query_vec,
            limit=5,
            match_threshold=0.0,
            match_count=5,
            document_id=document_id,
        )
        v2_chunk_ids = [item["chunk_id"] for item in v2_results]
        assert v2_chunk_ids, "Expected at least one result from embeddings_v2 search"

        # Legacy system: rank legacy_embeddings using the same cosine metric
        def _cosine(a: list[float], b: list[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = 0.0
            norm_a = 0.0
            norm_b = 0.0
            for x, y in zip(a, b):
                dot += x * y
                norm_a += x * x
                norm_b += y * y
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a**0.5 * norm_b**0.5)

        legacy_rank: list[dict[str, Any]] = []
        for chunk_id, entry in mock_database_adapter.legacy_embeddings.items():
            metadata = entry.get("metadata") or {}
            if metadata.get("document_id") != document_id:
                continue
            score = _cosine(query_vec, entry["embedding"])
            legacy_rank.append({"chunk_id": chunk_id, "score": score})

        assert legacy_rank, "Expected at least one legacy embedding for document"

        legacy_rank.sort(key=lambda r: r["score"], reverse=True)
        legacy_chunk_ids = [item["chunk_id"] for item in legacy_rank[:5]]

        # Top results from both systems should agree for this deterministic query
        assert v2_chunk_ids[0] == processor_chunks[0]["chunk_id"]
        assert legacy_chunk_ids[0] == processor_chunks[0]["chunk_id"]
        assert legacy_chunk_ids[:3] == v2_chunk_ids[:3]
