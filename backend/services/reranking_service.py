"""
RerankingService — CrossEncoder-based reranking for post-retrieval quality improvement.

Configuration (env vars):
  ENABLE_RERANKING   default: true   — set to false for no-op passthrough
  RERANKING_MODEL    default: cross-encoder/ms-marco-MiniLM-L-6-v2
  RERANKING_TOP_N    default: 5      — results returned after reranking
  RERANKING_CANDIDATES default: 20  — how many candidates to fetch before reranking
"""

import logging
import os

logger = logging.getLogger("krai.reranking")


class RerankingService:
    """
    Reranks a list of text candidates using a CrossEncoder model.

    Usage:
        svc = RerankingService()
        top_texts = svc.rerank(query, candidate_texts, top_n=5)

    Callers extract text from result objects before calling rerank(), then
    re-attach metadata by index after (index-based reconstruction pattern).
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_RERANKING", "true").lower() == "true"
        self.model_name = os.getenv("RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.default_top_n = int(os.getenv("RERANKING_TOP_N", "5"))
        self.candidates = int(os.getenv("RERANKING_CANDIDATES", "20"))
        self._model: object | None = None

        if self.enabled:
            self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            logger.info("RerankingService: loaded model %s", self.model_name)
        except Exception as e:
            logger.warning("RerankingService: failed to load model %s — reranking disabled: %s", self.model_name, e)
            self.enabled = False

    def rerank(self, query: str, texts: list[str], top_n: int | None = None) -> list[str]:
        """
        Rerank texts by relevance to query.

        Args:
            query: The search query.
            texts: Plain text strings to rerank (no metadata).
            top_n: How many top results to return. Defaults to RERANKING_TOP_N env var.

        Returns:
            Top-N strings sorted by CrossEncoder score, descending.
            When disabled, returns texts[:top_n] unchanged.
        """
        n = top_n if top_n is not None else self.default_top_n

        if not self.enabled or self._model is None or not texts:
            return texts[:n]

        try:
            pairs = [(query, t) for t in texts]
            scores = self._model.predict(pairs)
            ranked = sorted(zip(scores, texts), key=lambda x: x[0], reverse=True)
            return [text for _, text in ranked[:n]]
        except Exception as e:
            logger.warning("RerankingService.rerank failed, returning unranked: %s", e)
            return texts[:n]
