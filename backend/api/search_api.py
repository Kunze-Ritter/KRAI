"""
Search API for KR-AI-Engine
FastAPI endpoints for semantic search and vector operations
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
from backend.services.multimodal_search_service import MultimodalSearchService


# Pydantic model for image context search request
class ImageContextSearchRequest(BaseModel):
    query: str
    threshold: float | None = 0.5
    limit: int | None = 5


class SearchAPI:
    """
    Search API for KR-AI-Engine

    Endpoints:
    - POST /search: Semantic search
    - GET /search/suggestions: Search suggestions
    - POST /search/vector: Vector similarity search
    - GET /search/error-codes: Search error codes
    """

    def __init__(self, database_service: DatabaseAdapter, ai_service: AIService):
        self.database_service = database_service
        self.ai_service = ai_service
        self.multimodal_service = MultimodalSearchService(database_service, ai_service)
        self.logger = logging.getLogger("krai.api.search")
        self._setup_logging()

        # Create router
        self.router = APIRouter(prefix="/search", tags=["search"])
        self._setup_routes()

    def _setup_logging(self):
        """Setup logging for search API"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - SearchAPI - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _setup_routes(self):
        """Setup API routes"""

        @self.router.post("/", response_model=SearchResponse)
        async def semantic_search(request: SearchRequest):
            """Perform semantic search"""
            try:
                start_time = datetime.utcnow()

                # Generate query embedding
                query_embedding = await self.ai_service.generate_embeddings(request.query)

                # Perform vector search
                search_results = await self.database_service.vector_search(
                    query_embedding, limit=request.limit, threshold=0.7
                )

                # Process results
                processed_results = []
                for result in search_results:
                    processed_result = {
                        "chunk_id": result.get("id"),
                        "document_id": result.get("document_id"),
                        "content": result.get("text_chunk", ""),
                        "similarity_score": result.get("similarity", 0.0),
                        "page_start": result.get("page_start", 0),
                        "page_end": result.get("page_end", 0),
                        "metadata": result.get("metadata", {}),
                    }
                    processed_results.append(processed_result)

                # Filter by document types if specified
                if request.document_types:
                    # This would typically filter results by document type
                    pass

                # Filter by manufacturers if specified
                if request.manufacturers:
                    # This would typically filter results by manufacturer
                    pass

                # Filter by models if specified
                if request.models:
                    # This would typically filter results by model
                    pass

                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Log search analytics
                await self.database_service.log_audit(
                    action="semantic_search",
                    entity_type="search",
                    entity_id="",
                    details={
                        "query": request.query,
                        "results_count": len(processed_results),
                        "processing_time_ms": processing_time,
                        "filters": {
                            "document_types": request.document_types,
                            "manufacturers": request.manufacturers,
                            "models": request.models,
                        },
                    },
                )

                return SearchResponse(
                    results=processed_results,
                    total_count=len(processed_results),
                    processing_time_ms=processing_time,
                    query=request.query,
                )

            except Exception as e:
                self.logger.error(f"Semantic search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/suggestions")
        async def get_search_suggestions(q: str = Query(..., min_length=2)):
            """Get search suggestions"""
            try:
                # This would typically query a suggestions index
                # For now, return placeholder suggestions
                suggestions = [f"{q} error codes", f"{q} troubleshooting", f"{q} service manual", f"{q} parts catalog"]

                return {"query": q, "suggestions": suggestions}

            except Exception as e:
                self.logger.error(f"Failed to get search suggestions: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/vector")
        async def vector_similarity_search(
            query: str, limit: int = Query(10, ge=1, le=100), threshold: float = Query(0.7, ge=0.0, le=1.0)
        ):
            """Perform vector similarity search"""
            try:
                start_time = datetime.utcnow()

                # Generate query embedding
                query_embedding = await self.ai_service.generate_embeddings(query)

                # Perform vector search
                search_results = await self.database_service.vector_search(
                    query_embedding, limit=limit, threshold=threshold
                )

                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return {
                    "query": query,
                    "results": search_results,
                    "total_count": len(search_results),
                    "processing_time_ms": processing_time,
                    "threshold": threshold,
                }

            except Exception as e:
                self.logger.error(f"Vector search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/error-codes")
        async def search_error_codes(
            q: str = Query(..., min_length=1),
            manufacturer: str | None = Query(None),
            limit: int = Query(10, ge=1, le=100),
        ):
            """Search error codes in database"""
            try:
                # Extract error code from query (remove words like "Fehler", "Error", etc.)
                import re

                # Find patterns like: 10.00.33, C-1005, C9402, 100.01, etc.
                # Priority 1: Patterns with dots (like 10.00.33, 100.01)
                error_code_pattern = r"\b\d+(?:\.\d+)+\b"
                matches = re.findall(error_code_pattern, q, re.IGNORECASE)

                # Priority 2: Letter + optional dash + digits (like C-1005, C9402)
                if not matches:
                    error_code_pattern = r"\b[A-Z]-?\d{3,}\b"  # At least 3 digits
                    matches = re.findall(error_code_pattern, q, re.IGNORECASE)

                search_term = matches[0] if matches else q

                self.logger.info(f"Error code search: query='{q}' -> extracted='{search_term}'")

                # Build query
                # Use PostgreSQL query - search in public.error_codes view
                query_builder = (
                    self.database_service.client.table("vw_error_codes")
                    .select(
                        "error_code, error_description, solution_text, page_number, severity_level, confidence_score, "
                        "manufacturer_id, document_id"
                    )
                    .ilike("error_code", f"%{search_term}%")
                )

                # Execute query
                response = query_builder.order("confidence_score", desc=True).limit(limit).execute()

                # Get manufacturer and document names if needed
                manufacturer_ids = [row["manufacturer_id"] for row in response.data if row.get("manufacturer_id")]
                document_ids = [row["document_id"] for row in response.data if row.get("document_id")]

                manufacturers = {}
                documents = {}

                if manufacturer_ids:
                    mfr_response = (
                        self.database_service.client.table("vw_manufacturers")
                        .select("id, name")
                        .in_("id", manufacturer_ids)
                        .execute()
                    )
                    manufacturers = {m["id"]: m["name"] for m in mfr_response.data}

                if document_ids:
                    doc_response = (
                        self.database_service.client.table("vw_documents")
                        .select("id, filename")
                        .in_("id", document_ids)
                        .execute()
                    )
                    documents = {d["id"]: d["filename"] for d in doc_response.data}

                # Format results
                error_codes = []
                for row in response.data:
                    # Filter by manufacturer if specified
                    if manufacturer:
                        mfr_name = manufacturers.get(row.get("manufacturer_id"), "")
                        if manufacturer.lower() not in mfr_name.lower():
                            continue

                    error_codes.append(
                        {
                            "error_code": row.get("error_code"),
                            "description": row.get("error_description"),
                            "solution": row.get("solution_text"),
                            "manufacturer": manufacturers.get(row.get("manufacturer_id")),
                            "page_number": row.get("page_number"),
                            "severity_level": row.get("severity_level"),
                            "source_document": documents.get(row.get("document_id")),
                            "confidence": float(row["confidence_score"]) if row["confidence_score"] else 0.0,
                        }
                    )

                # Return array directly for n8n compatibility
                return error_codes

            except Exception as e:
                self.logger.error(f"Error code search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/parts")
        async def search_parts(
            q: str = Query(..., min_length=1),
            manufacturer: str | None = Query(None),
            limit: int = Query(10, ge=1, le=100),
        ):
            """Search parts in database"""
            try:
                # Build query
                query = """
                SELECT
                    p.part_number,
                    p.part_name,
                    p.description,
                    p.category,
                    p.price,
                    p.availability_status,
                    m.name as manufacturer,
                    d.filename as source_document
                FROM krai_parts.parts_catalog p
                LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
                LEFT JOIN krai_core.documents d ON p.document_id = d.id
                WHERE (p.part_number ILIKE %s OR p.part_name ILIKE %s OR p.description ILIKE %s)
                """

                search_pattern = f"%{q}%"
                params = [search_pattern, search_pattern, search_pattern]

                # Add manufacturer filter if specified
                if manufacturer:
                    query += " AND m.name ILIKE %s"
                    params.append(f"%{manufacturer}%")

                query += " ORDER BY p.part_number LIMIT %s"
                params.append(limit)

                # Execute query
                result = await self.database_service.execute_query(query, params)

                # Format results
                parts = []
                for row in result:
                    parts.append(
                        {
                            "part_number": row["part_number"],
                            "part_name": row["part_name"],
                            "description": row["description"],
                            "category": row["category"],
                            "price": float(row["price"]) if row["price"] else None,
                            "availability": row["availability_status"],
                            "manufacturer": row["manufacturer"],
                            "source_document": row["source_document"],
                        }
                    )

                return {"query": q, "parts": parts, "total_count": len(parts), "manufacturer_filter": manufacturer}

            except Exception as e:
                self.logger.error(f"Parts search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/videos")
        async def search_videos(
            q: str = Query(..., min_length=1),
            manufacturer: str | None = Query(None),
            limit: int = Query(10, ge=1, le=100),
        ):
            """Search videos in database"""
            try:
                # Build query
                query = """
                SELECT
                    v.video_id,
                    v.title,
                    v.description,
                    v.url,
                    v.duration,
                    v.published_at,
                    v.channel_title,
                    m.name as manufacturer
                FROM krai_content.videos v
                LEFT JOIN krai_core.manufacturers m ON v.manufacturer_id = m.id
                WHERE (v.title ILIKE %s OR v.description ILIKE %s)
                """

                search_pattern = f"%{q}%"
                params = [search_pattern, search_pattern]

                # Add manufacturer filter if specified
                if manufacturer:
                    query += " AND m.name ILIKE %s"
                    params.append(f"%{manufacturer}%")

                query += " ORDER BY v.published_at DESC NULLS LAST LIMIT %s"
                params.append(limit)

                # Execute query
                result = await self.database_service.execute_query(query, params)

                # Format results
                videos = []
                for row in result:
                    videos.append(
                        {
                            "video_id": row["video_id"],
                            "title": row["title"],
                            "description": row["description"],
                            "url": row["url"],
                            "duration": row["duration"],
                            "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                            "channel": row["channel_title"],
                            "manufacturer": row["manufacturer"],
                        }
                    )

                return {"query": q, "videos": videos, "total_count": len(videos), "manufacturer_filter": manufacturer}

            except Exception as e:
                self.logger.error(f"Videos search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/multimodal", response_model=MultimodalSearchResponse)
        async def multimodal_search(request: MultimodalSearchRequest):
            """Perform multimodal search across all content types"""
            try:
                start_time = datetime.utcnow()

                # Perform multimodal search
                results = await self.multimodal_service.search_multimodal(
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
                self.logger.error(f"Multimodal search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/two-stage", response_model=TwoStageSearchResponse)
        async def two_stage_search(request: TwoStageSearchRequest):
            """Perform two-stage search with reranking"""
            try:
                start_time = datetime.utcnow()

                # Perform two-stage search
                results = await self.multimodal_service.search_two_stage(
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
                self.logger.error(f"Two-stage search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/images/context")
        async def search_images_by_context(request: ImageContextSearchRequest):
            """Context-aware image search"""
            try:
                start_time = datetime.utcnow()

                # Perform context-aware image search
                results = await self.multimodal_service.search_images_by_context(
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
                self.logger.error(f"Context-aware image search failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def search_health_check():
            """Search service health check"""
            try:
                # Test AI service
                ai_health = await self.ai_service.health_check()

                # Test database service
                db_health = await self.database_service.health_check()

                return {
                    "status": (
                        "healthy"
                        if ai_health["status"] == "healthy" and db_health["status"] == "healthy"
                        else "degraded"
                    ),
                    "ai_service": ai_health,
                    "database_service": db_health,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
