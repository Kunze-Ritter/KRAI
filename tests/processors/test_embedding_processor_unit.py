"""Unit tests for EmbeddingProcessor internals.

These tests exercise configuration reporting, adaptive batching logic and
the `search_similar` helper without making real HTTP or Supabase calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.processors.embedding_processor import EmbeddingProcessor

pytestmark = [pytest.mark.processor, pytest.mark.embedding]


class DummyEmbeddingProcessor(EmbeddingProcessor):
    """EmbeddingProcessor variant that never talks to real Ollama.

    - `_check_ollama` is forced to return True.
    - Tests are expected to monkeypatch `_generate_embedding` where
      embedding values matter.
    - Ignores any persisted batch-size state so unit tests are
      deterministic across environments.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        requested_batch_size = kwargs.get("batch_size", 100)
        super().__init__(*args, **kwargs)
        # Force the batch size used in tests to the constructor value,
        # independent of any persisted state from previous runs.
        self.batch_size = requested_batch_size

    def _check_ollama(self) -> bool:  # type: ignore[override]
        return True


class TestEmbeddingProcessorConfiguration:
    """Configuration and status reporting behaviour."""

    def test_get_configuration_status_fields(self) -> None:
        """Status dict exposes expected keys and reflects constructor args."""

        supabase_stub = SimpleNamespace()
        processor = DummyEmbeddingProcessor(
            supabase_client=supabase_stub,
            ollama_url="http://test-ollama",
            model_name="test-embedding-model",
            batch_size=42,
            embedding_dimension=512,
            enable_embeddings_v2=True,
        )

        status = processor.get_configuration_status()

        assert status["is_configured"] is True
        assert status["ollama_available"] is True
        assert status["ollama_url"] == "http://test-ollama"
        assert status["model_name"] == "test-embedding-model"
        assert status["batch_size"] == 42
        assert status["embedding_dimension"] == 512
        assert status["embeddings_v2_enabled"] is True

    def test_is_configured_requires_supabase_and_ollama(self) -> None:
        """If Supabase client is missing, processor is not configured."""

        processor = DummyEmbeddingProcessor(supabase_client=None)
        # _check_ollama is forced to True, but supabase_client is None
        assert processor.ollama_available is True
        assert processor.is_configured() is False


class TestAdaptiveBatching:
    """Tests for adaptive batch size logic based on batch latency."""

    def test_increase_batch_size_when_latency_low(self) -> None:
        """Batch size grows when latency is below lower target bound."""

        supabase_stub = SimpleNamespace()
        processor = DummyEmbeddingProcessor(
            supabase_client=supabase_stub,
            batch_size=10,
            min_batch_size=5,
            max_batch_size=50,
            batch_adjust_step=5,
        )

        original = processor.batch_size
        # Simulate very fast batch
        processor._adjust_batch_size(latency=processor.target_latency_lower / 4)
        assert processor.batch_size > original
        assert processor.batch_size <= processor.max_batch_size

    def test_decrease_batch_size_when_latency_high(self) -> None:
        """Batch size shrinks when latency is above upper target bound."""

        supabase_stub = SimpleNamespace()
        processor = DummyEmbeddingProcessor(
            supabase_client=supabase_stub,
            batch_size=40,
            min_batch_size=5,
            max_batch_size=50,
            batch_adjust_step=5,
        )

        original = processor.batch_size
        # Simulate very slow batch
        processor._adjust_batch_size(latency=processor.target_latency_upper * 4)
        assert processor.batch_size < original
        assert processor.batch_size >= processor.min_batch_size


class TestSearchSimilar:
    """Behaviour of the `search_similar` helper around RPC usage."""

    def test_search_similar_calls_rpc_with_expected_params(self, monkeypatch: Any) -> None:
        """search_similar generates a query embedding and calls match_chunks RPC."""

        class StubSupabase:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def rpc(self, function_name: str, params: dict[str, Any]):
                self.calls.append({"name": function_name, "params": params})

                class _Result:
                    def __init__(self) -> None:
                        self.data = [
                            {
                                "chunk_id": "chunk-1",
                                "content": "paper jam in tray 2",
                                "similarity": 0.92,
                                "metadata": {"chunk_type": "text"},
                            }
                        ]

                    def execute(self) -> _Result:
                        # Mimic Supabase RPC behaviour: .execute() returns an
                        # object with a .data attribute.
                        return self

                return _Result()

        supabase = StubSupabase()
        processor = DummyEmbeddingProcessor(supabase_client=supabase)

        # Avoid real HTTP by forcing a deterministic embedding
        monkeypatch.setattr(
            processor,
            "_generate_embedding",
            lambda text: [0.1] * processor.embedding_dimension,
        )

        results = processor.search_similar(
            query_text="paper jam tray 2",
            limit=5,
            similarity_threshold=0.5,
        )

        # RPC should have been called once with match_chunks
        assert len(supabase.calls) == 1
        call = supabase.calls[0]
        assert call["name"] == "match_chunks"
        params = call["params"]
        assert "query_embedding" in params
        assert params["match_threshold"] == 0.5
        assert params["match_count"] == 5

        # And the result from the stub should be surfaced unchanged
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-1"
        assert "similarity" in results[0]


class TestJsonHelper:
    """Smoke tests for the internal JSON-compatibility helper."""

    def test_make_json_safe_handles_uuid_and_datetime(self) -> None:
        from datetime import datetime
        from uuid import uuid4

        raw = {
            "id": uuid4(),
            "created_at": datetime.utcnow(),
            "nested": {"values": [uuid4(), datetime.utcnow()]},
        }

        safe = EmbeddingProcessor._make_json_safe(raw)

        assert isinstance(safe["id"], str)
        assert isinstance(safe["created_at"], str)
        assert isinstance(safe["nested"]["values"][0], str)
        assert isinstance(safe["nested"]["values"][1], str)
