"""
Search API Routes - Multimodal and Two-stage Search

FastAPI routes for advanced search capabilities including:
- Multimodal search across text, images, videos, tables
- Two-stage search with reranking
- Context-aware result enrichment
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.api.middleware.auth_middleware import require_permission
from backend.core.data_models import (
    MultimodalSearchRequest,
    MultimodalSearchResponse,
    SearchRequest,
    SearchResponse,
    TwoStageSearchRequest,
    TwoStageSearchResponse,
)
from backend.services.ai_service import AIService
from backend.services.database_adapter import DatabaseAdapter
from backend.services.database_factory import create_database_adapter
from backend.services.multimodal_search_service import MultimodalSearchService

# Create router
router = APIRouter(prefix="/search", tags=["search"])


# Pydantic model for image context search request
class ImageContextSearchRequest(BaseModel):
    query: str
    threshold: float | None = 0.5
    limit: int | None = 5


# Dependencies (will be injected by app.py)
async def get_database_service() -> AsyncGenerator[DatabaseAdapter, None]:
    """Get database service instance"""
    # Fallback dependency for standalone route usage.
    database_service = create_database_adapter()
    await database_service.connect()
    try:
        yield database_service
    finally:
        await database_service.disconnect()


def get_ai_service() -> AIService:
    """Get AI service instance"""
    # This will be overridden by app.py with proper dependency injection
    return AIService()


def get_multimodal_search_service(
    database_service: DatabaseAdapter = Depends(get_database_service), ai_service: AIService = Depends(get_ai_service)
) -> MultimodalSearchService:
    """Get multimodal search service instance"""
    return MultimodalSearchService(database_service, ai_service)


# Standard Search Routes
@router.post("/", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    database_service: DatabaseAdapter = Depends(get_database_service),
    ai_service: AIService = Depends(get_ai_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Semantic search across documents

    Args:
        request: Search request with query and filters

    Returns:
        Search results with similarity scores
    """
    try:
        start_time = datetime.utcnow()

        # Generate embedding for query
        query_embedding = await ai_service.generate_embedding(request.query)

        # Search using database RPC function
        results = await database_service.vector_search(
            query_vector=query_embedding,
            limit=request.limit,
            offset=request.offset,
            filters={
                "document_types": [dt.value for dt in request.document_types] if request.document_types else None,
                "manufacturers": request.manufacturers,
                "models": request.models,
            },
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return SearchResponse(
            results=results.get("results", []),
            total_count=results.get("total_count", 0),
            processing_time_ms=processing_time,
            query=request.query,
        )

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def search_suggestions(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
    database_service: DatabaseAdapter = Depends(get_database_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Get search suggestions based on partial query

    Args:
        query: Partial search query
        limit: Maximum number of suggestions

    Returns:
        List of search suggestions
    """
    try:
        suggestions = await database_service.get_search_suggestions(query, limit)
        return {"query": query, "suggestions": suggestions}

    except Exception as e:
        logger.error(f"Search suggestions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Multimodal Search Routes
@router.post("/multimodal", response_model=MultimodalSearchResponse)
async def multimodal_search(
    request: MultimodalSearchRequest,
    search_service: MultimodalSearchService = Depends(get_multimodal_search_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Multimodal search across all content types

    Args:
        request: Multimodal search request

    Returns:
        Unified search results from multiple content types
    """
    try:
        start_time = datetime.utcnow()

        # Perform multimodal search
        results = await search_service.search_multimodal(
            query=request.query,
            content_types=request.content_types,
            threshold=request.threshold,
            limit=request.limit,
            include_context=request.include_context,
            enable_two_stage=request.enable_two_stage,
            filters=request.filters,
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return MultimodalSearchResponse(
            query=request.query,
            results=results.get("results", []),
            total_count=results.get("total_count", 0),
            processing_time_ms=processing_time,
            content_type_counts=results.get("content_type_counts", {}),
            two_stage_used=results.get("two_stage_used", False),
            context_enriched=results.get("context_enriched", False),
        )

    except Exception as e:
        logger.error(f"Multimodal search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/two-stage", response_model=TwoStageSearchResponse)
async def two_stage_search(
    request: TwoStageSearchRequest,
    search_service: MultimodalSearchService = Depends(get_multimodal_search_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Two-stage search with initial retrieval and reranking

    Args:
        request: Two-stage search request

    Returns:
        Reranked search results with performance metrics
    """
    try:
        start_time = datetime.utcnow()
        rerank_start = None

        # Perform two-stage search
        results = await search_service.search_two_stage(
            query=request.query,
            first_stage_limit=request.first_stage_limit,
            final_limit=request.final_limit,
            content_types=request.content_types,
            threshold=request.threshold,
            rerank_enabled=request.rerank_enabled,
            context_boost=request.context_boost,
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        reranking_time = results.get("reranking_time_ms", 0.0)

        return TwoStageSearchResponse(
            query=request.query,
            first_stage_count=results.get("first_stage_count", 0),
            final_results=results.get("final_results", []),
            total_count=len(results.get("final_results", [])),
            processing_time_ms=processing_time,
            reranking_time_ms=reranking_time,
            threshold_used=request.threshold,
        )

    except Exception as e:
        logger.error(f"Two-stage search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/images/context")
async def search_images_by_context(
    request: ImageContextSearchRequest,
    search_service: MultimodalSearchService = Depends(get_multimodal_search_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Context-aware image search

    Args:
        request: Image context search request with query, threshold, and limit

    Returns:
        Image results enriched with context and similarity scores
    """
    try:
        start_time = datetime.utcnow()

        # Perform context-aware image search
        results = await search_service.search_images_by_context(
            query=request.query, threshold=request.threshold, limit=request.limit
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Return the service response with additional metadata
        return {
            "query": request.query,
            "images": results.get("images", []),
            "total_count": results.get("total_count", 0),
            "processing_time_ms": processing_time,
            "threshold_used": request.threshold,
            "limit_used": request.limit,
            "context_enriched": True,
        }

    except Exception as e:
        logger.error(f"Context-aware image search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error Code Search
@router.get("/error-codes")
async def search_error_codes(
    query: str = Query(..., min_length=2),
    manufacturer: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    database_service: DatabaseAdapter = Depends(get_database_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Search error codes with optional manufacturer filter

    Args:
        query: Search query for error codes
        manufacturer: Optional manufacturer filter
        limit: Maximum number of results

    Returns:
        Error code search results
    """
    try:
        results = await database_service.search_error_codes(query=query, manufacturer=manufacturer, limit=limit)

        return {
            "query": query,
            "manufacturer": manufacturer,
            "results": results.get("results", []),
            "total_count": results.get("total_count", 0),
        }

    except Exception as e:
        logger.error(f"Error code search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Vector similarity search
@router.post("/vector")
async def vector_similarity_search(
    vector: list[float],
    limit: int = Query(10, ge=1, le=100),
    threshold: float = Query(0.5, ge=0.0, le=1.0),
    database_service: DatabaseAdapter = Depends(get_database_service),
    current_user: dict = Depends(require_permission("search:read")),
):
    """
    Search using raw vector similarity

    Args:
        vector: Embedding vector for similarity search
        limit: Maximum number of results
        threshold: Minimum similarity threshold

    Returns:
        Similar chunks based on vector similarity
    """
    try:
        if len(vector) != 768:  # Assuming 768-dimensional embeddings
            raise HTTPException(status_code=400, detail="Vector must be 768-dimensional")

        results = await database_service.vector_search(query_vector=vector, limit=limit, threshold=threshold)

        return {
            "vector_dimension": len(vector),
            "threshold": threshold,
            "results": results.get("results", []),
            "total_count": results.get("total_count", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector similarity search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Setup logging
logger = logging.getLogger("krai.api.search")
