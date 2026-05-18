"""
Verification test for Embedding Stage (Stage 14).

Tests Ollama connection, embedding generation for sample text, 768-dim vector,
adaptive batching with large chunk set, and database storage.

Run: pytest tests/verification/test_embedding_stage.py -v

Requires: Ollama running with nomic-embed-text model (for integration tests)
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.processors.embedding_processor import EmbeddingProcessor


class MockDatabaseAdapter:
    """Mock database adapter for embedding storage tests."""

    def __init__(self):
        self.queries = []
        self.rpc_calls = []

    async def execute_query(self, query: str, params: list | None = None):
        self.queries.append({"query": query, "params": params or []})
        return []

    async def execute_rpc(self, name: str, params: dict | None = None):
        self.rpc_calls.append({"name": name, "params": params or {}})
        return


@pytest.mark.embedding
@pytest.mark.verification
class TestEmbeddingStage:
    """Verification tests for Embedding stage."""

    def test_embedding_processor_extends_base_processor(self):
        """Verify EmbeddingProcessor extends BaseProcessor with Stage.EMBEDDING."""
        from backend.core.base_processor import BaseProcessor, Stage

        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        assert isinstance(processor, BaseProcessor)
        assert processor.stage == Stage.EMBEDDING

    def test_embedding_processor_accepts_database_and_ollama_params(self):
        """Confirm constructor accepts database_adapter and ollama_url."""
        db = MockDatabaseAdapter()
        processor = EmbeddingProcessor(
            database_adapter=db,
            ollama_url="http://localhost:11434",
        )
        assert processor.database_adapter is db
        assert processor.ollama_url == "http://localhost:11434"

    def test_adaptive_batching_configuration(self):
        """Check adaptive batching (default 100 chunks/batch)."""
        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        assert processor.batch_size >= processor.min_batch_size
        assert processor.batch_size <= processor.max_batch_size
        assert processor.embedding_dimension == 768

    def test_model_name_is_nomic_embed_text(self):
        """Verify model name is nomic-embed-text (768 dimensions)."""
        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        assert "nomic-embed-text" in processor.model_name

    @pytest.mark.asyncio
    async def test_process_requires_document_id(self):
        """Verify process() raises ValueError when document_id is missing."""
        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        # Context without document_id attribute
        context = type("Context", (), {})()

        with pytest.raises(ValueError, match="document_id"):
            await processor.process(context)

    @pytest.mark.asyncio
    async def test_process_returns_error_when_no_chunks(self):
        """Verify process returns error when chunks are missing."""
        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        context = type("Context", (), {"document_id": str(uuid4())})()

        result = await processor.process(context)

        assert result.get("success") is False
        assert "chunks" in result.get("error", "").lower()
        assert result.get("embeddings_created", 0) == 0

    @pytest.mark.ollama
    @pytest.mark.skipif(
        os.getenv("OLLAMA_AVAILABLE", "false").lower() != "true",
        reason="Ollama not available - set OLLAMA_AVAILABLE=true to run",
    )
    def test_ollama_embedding_generation_768_dim(self):
        """Test Ollama generates 768-dim embedding (requires Ollama running)."""
        processor = EmbeddingProcessor(database_adapter=MockDatabaseAdapter())
        if not processor.ollama_available:
            pytest.skip("Ollama not available or model not installed")

        test_text = "This is a test sentence for embedding generation."
        embedding = processor._generate_embedding(test_text)

        assert embedding is not None
        assert len(embedding) == 768
        assert all(isinstance(v, (int, float)) for v in embedding[:5])

    @pytest.mark.ollama
    @pytest.mark.skipif(
        os.getenv("OLLAMA_AVAILABLE", "false").lower() != "true",
        reason="Ollama not available",
    )
    @pytest.mark.asyncio
    async def test_embedding_storage_in_unified_embeddings(self):
        """Verify embeddings stored in krai_intelligence.unified_embeddings."""
        db = MockDatabaseAdapter()
        processor = EmbeddingProcessor(database_adapter=db)

        # Mock embedding for storage test (skip Ollama call)
        chunk = {
            "chunk_id": str(uuid4()),
            "text": "Test chunk text",
            "chunk_type": "text",
            "page_start": 1,
            "page_end": 1,
            "chunk_index": 0,
        }
        embedding = [0.1] * 768  # Mock 768-dim vector

        stored = await processor._store_embedding(
            chunk_id=chunk["chunk_id"],
            document_id=uuid4(),
            embedding=embedding,
            chunk_data=chunk,
        )

        assert stored is True
        unified_insert = next(
            (q for q in db.queries if "unified_embeddings" in q["query"]),
            None,
        )
        assert unified_insert is not None
        assert "source_type" in unified_insert["query"] or "'text'" in str(unified_insert.get("params", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
