"""E2E-style tests for EmbeddingProcessor using MockDatabaseAdapter.

Runs the embedding stage against in-memory stores only – no real Ollama or
Supabase. A small test subclass writes directly into the adapter.
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
    - Bypasses Supabase-specific `.table()` APIs entirely.
    """

    def __init__(self, database_adapter, **kwargs: Any) -> None:  # type: ignore[override]
        super().__init__(supabase_client=None, enable_embeddings_v2=True, **kwargs)
        self.database_adapter = database_adapter
        self.stage_tracker = StageTracker(database_adapter)
        self.ollama_available = True
        # Context embeddings and Supabase-backed multi-modal views are
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
        `embeddings_v2` without requiring Supabase or pgvector.
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


class TestEmbeddingProcessorE2E:
    """End-to-end style tests for Stage 7 embedding generation."""

    @pytest.mark.asyncio
    async def test_process_creates_embeddings_and_populates_adapter(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_chunks_with_content,
    ) -> None:
        """Happy path: all chunks are embedded and stored in mock adapter."""

        document_id = sample_chunks_with_content[0]["document_id"]

        # Adapt generic chunk fixtures into EmbeddingProcessor input format
        processor_chunks: list[dict[str, Any]] = []
        for chunk in sample_chunks_with_content[:10]:  # keep test small
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

        processor = E2EEmbeddingProcessor(database_adapter=mock_database_adapter, batch_size=8)

        # Use deterministic mock embeddings instead of real Ollama calls
        processor._generate_embedding = (  # type: ignore[assignment]
            lambda text: mock_embedding_service._generate_embedding(text)
        )

        context = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/embed_e2e.pdf",
            document_type="service_manual",
        )
        context.chunks = processor_chunks  # type: ignore[attr-defined]

        result = await processor.process(context)

        assert result["success"] is True
        assert result["embeddings_created"] == len(processor_chunks)
        assert result["failed_count"] == 0

        # Verify adapter-side counts reflect what the processor reports
        chunks_count = await mock_database_adapter.count_chunks_by_document(document_id)
        embeddings_count = await mock_database_adapter.count_embeddings_by_document(document_id)

        assert chunks_count == len(processor_chunks)
        assert embeddings_count == len(processor_chunks)

    @pytest.mark.asyncio
    async def test_partial_failure_reports_failed_chunks(
        self,
        mock_database_adapter,
        mock_embedding_service,
    ) -> None:
        """If one chunk fails to store, result is marked as partial_success."""

        document_id = str(uuid4())

        processor_chunks = [
            {
                "chunk_id": "chunk-ok",
                "text": "Paper jam in tray 2.",
                "chunk_index": 0,
                "chunk_type": "text",
                "page_start": 1,
                "page_end": 1,
                "metadata": {},
            },
            {
                "chunk_id": "chunk-fail",
                "text": "Network configuration settings.",
                "chunk_index": 1,
                "chunk_type": "text",
                "page_start": 1,
                "page_end": 1,
                "metadata": {},
            },
        ]

        processor = E2EEmbeddingProcessor(database_adapter=mock_database_adapter, batch_size=2)
        processor._generate_embedding = (  # type: ignore[assignment]
            lambda text: mock_embedding_service._generate_embedding(text)
        )

        original_store = processor._store_embedding

        def failing_store(
            chunk_id: str,
            document_id,
            embedding: list[float],
            chunk_data: dict[str, Any],
        ) -> bool:
            if chunk_id == "chunk-fail":
                return False
            return original_store(chunk_id, document_id, embedding, chunk_data)

        processor._store_embedding = failing_store  # type: ignore[assignment]

        context = ProcessingContext(
            document_id=document_id,
            file_path="/tmp/embed_partial.pdf",
            document_type="service_manual",
        )
        context.chunks = processor_chunks  # type: ignore[attr-defined]

        result = await processor.process(context)

        assert result["success"] is True
        assert result["partial_success"] is True
        assert result["embeddings_created"] == 1
        assert result["failed_count"] == 1
        assert len(result["failed_chunks"]) == 1
