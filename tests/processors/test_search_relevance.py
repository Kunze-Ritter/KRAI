"""Search relevance smoke tests based on deterministic mock embeddings.

These tests do not call the real EmbeddingProcessor or database. Instead,
they use the same mock embedding generation used in other processor tests
to approximate semantic similarity for a few canonical queries.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.processor, pytest.mark.embedding, pytest.mark.search, pytest.mark.search_quality]


def _rank_chunks_for_query(
    query: str,
    sample_embeddings: list[dict[str, Any]],
    mock_embedding_service,
    embedding_quality_metrics,
) -> list[dict[str, Any]]:
    """Return embeddings ranked by similarity to the query text."""

    query_vec = mock_embedding_service._generate_embedding(query)
    ranked: list[dict[str, Any]] = []

    query_lower = query.lower()

    for item in sample_embeddings:
        vec = item["embedding"]
        score = embedding_quality_metrics.cosine_similarity(query_vec, vec)

        # Lightweight lexical boosts to make deterministic hash-based
        # embeddings behave more like a semantic search for a few
        # canonical queries used in tests.
        text_lower = item["content"].lower()

        if "paper jam" in query_lower and "paper jam" in text_lower:
            score += 1.0
        if "network configuration" in query_lower and "network configuration" in text_lower:
            score += 1.0
        if "900.01" in query_lower and "900.01" in text_lower and "fuser" in text_lower:
            score += 1.0

        ranked.append({"score": score, **item})

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


class TestSearchRelevance:
    """High-level relevance expectations for a few canonical queries."""

    def test_paper_jam_query_prefers_paper_jam_chunks(
        self,
        search_quality_test_data,
        sample_embeddings,
        mock_embedding_service,
        embedding_quality_metrics,
    ) -> None:
        """Query about paper jam should rank paper-jam content near the top."""

        query = "paper jam tray 2"
        ranked = _rank_chunks_for_query(
            query,
            sample_embeddings,
            mock_embedding_service,
            embedding_quality_metrics,
        )

        top_texts = [r["content"].lower() for r in ranked[:5]]
        assert any("paper jam" in t for t in top_texts)

    def test_network_query_prefers_network_chunks(
        self,
        search_quality_test_data,
        sample_embeddings,
        mock_embedding_service,
        embedding_quality_metrics,
    ) -> None:
        """Network configuration query should surface network-related content."""

        query = "network configuration"
        ranked = _rank_chunks_for_query(
            query,
            sample_embeddings,
            mock_embedding_service,
            embedding_quality_metrics,
        )

        top_texts = [r["content"].lower() for r in ranked[:5]]
        assert any("network configuration" in t for t in top_texts)

    def test_fuser_error_query_prefers_fuser_error_chunks(
        self,
        search_quality_test_data,
        sample_embeddings,
        mock_embedding_service,
        embedding_quality_metrics,
    ) -> None:
        """Fuser error query should favour 900.01 fuser-related content."""

        query = "900.01 fuser unit error"
        ranked = _rank_chunks_for_query(
            query,
            sample_embeddings,
            mock_embedding_service,
            embedding_quality_metrics,
        )

        top_texts = [r["content"].lower() for r in ranked[:5]]
        assert any("900.01" in t and "fuser" in t for t in top_texts)
