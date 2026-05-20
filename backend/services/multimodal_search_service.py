"""
Multimodal Search Service - Unified search across all content types

Provides unified search across text, images, videos, tables, and links using
context-aware embeddings and two-stage retrieval strategies.
"""

import logging
from typing import Any

from backend.services.ai_service import AIService
from backend.services.database_adapter import DatabaseAdapter


class MultimodalSearchService:
    """
    Unified multimodal search service with advanced retrieval strategies

    Provides search across all content types with two-stage image retrieval,
    result enrichment, and context-aware ranking.
    """

    def __init__(
        self,
        database_service: DatabaseAdapter,
        ai_service: AIService,
        reranking_service=None,  # RerankingService | None
        default_threshold: float = 0.5,
        default_limit: int = 10,
    ):
        """
        Initialize Multimodal Search Service

        Args:
            database_service: Database service for RPC function calls
            ai_service: AI service for embeddings and text generation
            reranking_service: Optional reranking service for post-retrieval reranking
            default_threshold: Default similarity threshold (0.0-1.0)
            default_limit: Default maximum number of results
        """
        self.database_service = database_service
        self.ai_service = ai_service
        self.reranking_service = reranking_service
        self.default_threshold = default_threshold
        self.default_limit = default_limit
        self.logger = logging.getLogger("krai.multimodal_search")

        self.logger.info(
            f"MultimodalSearchService initialized (threshold: {default_threshold}, " f"limit: {default_limit})"
        )

    async def search_multimodal(
        self,
        query: str,
        modalities: list[str] = ["text", "image", "video", "table", "link"],
        threshold: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Unified search across all content types

        Args:
            query: Search query
            modalities: List of modalities to search (default: all)
            threshold: Similarity threshold (default: 0.5)
            limit: Maximum number of results (default: 10)

        Returns:
            Dictionary with query, results, and metadata
        """
        import time

        start_time = time.time()

        try:
            # Generate query embedding
            query_embedding = await self.ai_service.generate_embeddings(query)

            # Expand fetch count when reranking is enabled
            fetch_limit = (
                self.reranking_service.candidates
                if self.reranking_service and self.reranking_service.enabled
                else (limit or self.default_limit)
            )

            # Call RPC function via database adapter
            results = await self.database_service.match_multimodal(
                query_embedding=query_embedding,
                match_threshold=threshold or self.default_threshold,
                match_count=fetch_limit,
            )

            # Filter by modalities if specified
            if modalities:
                results = [r for r in results if r["source_type"] in modalities]

            # Rerank results if reranking service is available and enabled
            if self.reranking_service and self.reranking_service.enabled and results:
                texts = [r.get("content", "") for r in results]
                top_n = limit or self.default_limit
                top_texts = self.reranking_service.rerank(query, texts, top_n=top_n)
                used_indices: set[int] = set()
                reranked_results = []
                for text in top_texts:
                    for i, candidate in enumerate(texts):
                        if i not in used_indices and candidate == text:
                            reranked_results.append(results[i])
                            used_indices.add(i)
                            break
                results = reranked_results

            # Enrich results with additional metadata
            enriched_results = await self._enrich_results(results)

            # Group results by modality
            results_by_modality = {}
            for result in enriched_results:
                modality = result["source_type"]
                if modality not in results_by_modality:
                    results_by_modality[modality] = []
                results_by_modality[modality].append(result)

            processing_time = (time.time() - start_time) * 1000

            response = {
                "query": query,
                "results": enriched_results,
                "results_by_modality": results_by_modality,
                "total_count": len(enriched_results),
                "modalities_searched": modalities,
                "processing_time_ms": round(processing_time, 2),
            }

            self.logger.info(
                f"Multimodal search completed: {len(enriched_results)} results " f"in {processing_time:.2f}ms"
            )

            return response

        except Exception as e:
            self.logger.error(f"Multimodal search failed: {e}")
            return {
                "query": query,
                "results": [],
                "results_by_modality": {},
                "total_count": 0,
                "modalities_searched": modalities,
                "processing_time_ms": 0,
                "error": str(e),
            }

    async def search_images_by_context(
        self, query: str, threshold: float | None = None, limit: int = 5
    ) -> dict[str, Any]:
        """
        Context-aware image search

        Args:
            query: Search query
            threshold: Similarity threshold (default: 0.5)
            limit: Maximum number of results (default: 5)

        Returns:
            Dictionary with query and image results
        """
        import time

        start_time = time.time()

        try:
            # Generate query embedding
            query_embedding = await self.ai_service.generate_embeddings(query)

            # Call RPC function for image search
            results = await self.database_service.match_images_by_context(
                query_embedding=query_embedding, match_threshold=threshold or self.default_threshold, match_count=limit
            )

            # Enrich results
            enriched_results = await self._enrich_image_results(results)

            processing_time = (time.time() - start_time) * 1000

            response = {
                "query": query,
                "images": enriched_results,
                "total_count": len(enriched_results),
                "processing_time_ms": round(processing_time, 2),
            }

            self.logger.info(
                f"Context-aware image search completed: {len(enriched_results)} results " f"in {processing_time:.2f}ms"
            )

            return response

        except Exception as e:
            self.logger.error(f"Image search failed: {e}")
            return {"query": query, "images": [], "total_count": 0, "processing_time_ms": 0, "error": str(e)}

    async def search_two_stage(
        self, query: str, text_limit: int = 5, image_limit: int = 5, threshold: float = 0.6
    ) -> dict[str, Any]:
        """
        Two-stage image retrieval for improved relevance

        Stage 1: Text search â†’ LLM answer generation
        Stage 2: Image search with expanded query context

        Args:
            query: Original search query
            text_limit: Maximum text chunks for LLM context (default: 5)
            image_limit: Maximum images to return (default: 5)
            threshold: Similarity threshold (default: 0.6)

        Returns:
            Dictionary with answer, images, and sources
        """
        import time

        start_time = time.time()

        try:
            # Stage 1: Text search + LLM response
            stage1_start = time.time()

            # Search text chunks
            text_results = await self.search_multimodal(
                query=query, modalities=["text"], limit=text_limit, threshold=threshold
            )

            # Generate answer with LLM
            context_chunks = [r["content"] for r in text_results["results"][:text_limit]]
            llm_response = await self.ai_service.generate_text(prompt=query, context=context_chunks)

            stage1_time = (time.time() - stage1_start) * 1000

            # Stage 2: Image search with expanded context
            stage2_start = time.time()

            # Expand query with LLM response
            expanded_query = f"{query} {llm_response[:200]}"

            # Search images with expanded context
            image_results = await self.search_images_by_context(
                query=expanded_query, limit=image_limit, threshold=threshold
            )

            stage2_time = (time.time() - stage2_start) * 1000
            total_time = (time.time() - start_time) * 1000

            response = {
                "query": query,
                "answer": llm_response,
                "images": image_results["images"],
                "text_sources": text_results["results"],
                "expanded_query": expanded_query,
                "timing": {
                    "stage1_ms": round(stage1_time, 2),
                    "stage2_ms": round(stage2_time, 2),
                    "total_ms": round(total_time, 2),
                },
                "statistics": {
                    "text_chunks_used": len(context_chunks),
                    "images_found": len(image_results["images"]),
                    "answer_length": len(llm_response),
                },
            }

            self.logger.info(
                f"Two-stage retrieval completed: {len(image_results['images'])} images, "
                f"answer length: {len(llm_response)} chars, "
                f"total time: {total_time:.2f}ms"
            )

            return response

        except Exception as e:
            self.logger.error(f"Two-stage retrieval failed: {e}")
            return {
                "query": query,
                "answer": "",
                "images": [],
                "text_sources": [],
                "expanded_query": query,
                "timing": {"stage1_ms": 0, "stage2_ms": 0, "total_ms": 0},
                "statistics": {"text_chunks_used": 0, "images_found": 0, "answer_length": 0},
                "error": str(e),
            }

    async def _enrich_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Enrich results with document names and manufacturer information

        Args:
            results: Raw results from RPC function

        Returns:
            Enriched results with additional metadata
        """
        enriched = []

        for result in results:
            try:
                # Add document name if source_id is available
                if "source_id" in result and result["source_type"] in ["text", "image"]:
                    document_info = await self._get_document_info(result["source_id"])
                    if document_info:
                        result["document_name"] = document_info.get("name")
                        result["manufacturer"] = document_info.get("manufacturer")

                # Add modality-specific metadata
                if result["source_type"] == "image":
                    result["display_type"] = "image"
                elif result["source_type"] == "video":
                    result["display_type"] = "video"
                elif result["source_type"] == "table":
                    result["display_type"] = "table"
                elif result["source_type"] == "link":
                    result["display_type"] = "link"
                else:
                    result["display_type"] = "text"

                enriched.append(result)

            except Exception as e:
                self.logger.warning(f"Failed to enrich result: {e}")
                enriched.append(result)

        return enriched

    async def _enrich_image_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Enrich image results with additional metadata

        Args:
            results: Raw image results from RPC function

        Returns:
            Enriched image results
        """
        enriched = []

        for result in results:
            try:
                # Add document information
                if "id" in result:
                    document_info = await self._get_image_document_info(result["id"])
                    if document_info:
                        result["document_name"] = document_info.get("document_name")
                        result["manufacturer"] = document_info.get("manufacturer")

                # Add display metadata
                result["display_type"] = "image"
                result["thumbnail_url"] = result.get("storage_url", "")

                enriched.append(result)

            except Exception as e:
                self.logger.warning(f"Failed to enrich image result: {e}")
                enriched.append(result)

        return enriched

    async def _get_document_info(self, source_id: str) -> dict[str, Any] | None:
        """
        Get document information from source_id

        Args:
            source_id: Source ID from search result

        Returns:
            Document information dictionary
        """
        try:
            # This would typically query the documents table
            # For now, return basic info
            return {"name": f"Document {source_id[:8]}", "manufacturer": None}
        except Exception as e:
            self.logger.debug(f"Failed to get document info for {source_id}: {e}")
            return None

    async def _get_image_document_info(self, image_id: str) -> dict[str, Any] | None:
        """
        Get document information for an image

        Args:
            image_id: Image ID

        Returns:
            Document information dictionary
        """
        try:
            # This would typically join images with documents
            # For now, return basic info
            return {"document_name": f"Document {image_id[:8]}", "manufacturer": None}
        except Exception as e:
            self.logger.debug(f"Failed to get image document info for {image_id}: {e}")
            return None

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for multimodal search service

        Returns:
            Health status information
        """
        try:
            # Test RPC functions
            test_embedding = [0.1] * 768  # Mock embedding

            # Test match_multimodal
            multimodal_results = await self.database_service.match_multimodal(
                query_embedding=test_embedding, match_threshold=0.5, match_count=1
            )

            # Test match_images_by_context
            image_results = await self.database_service.match_images_by_context(
                query_embedding=test_embedding, match_threshold=0.5, match_count=1
            )

            # Test AI service
            ai_test = await self.ai_service.generate_embeddings("test query")

            return {
                "status": "healthy",
                "services": {
                    "database_rpc": "ok" if multimodal_results is not None else "error",
                    "image_search": "ok" if image_results is not None else "error",
                    "ai_service": "ok" if ai_test is not None else "error",
                },
                "capabilities": {"multimodal_search": True, "image_search": True, "two_stage_retrieval": True},
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "services": {"database_rpc": "error", "image_search": "error", "ai_service": "error"},
            }
