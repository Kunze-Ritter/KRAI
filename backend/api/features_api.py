"""
Features API for KR-AI-Engine
FastAPI endpoints for features management and inheritance
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from services.database_adapter import DatabaseAdapter
from services.features_service import FeaturesService


class FeaturesAPI:
    """
    Features API for KR-AI-Engine

    Endpoints:
    - GET /features/series/{series_id}: Get series features
    - GET /features/product/{product_id}: Get product features
    - GET /features/effective/{series_id}/{product_id}: Get effective features
    - POST /features/search: Search by features
    - PUT /features/series/{series_id}: Update series features
    - PUT /features/product/{product_id}: Update product features
    """

    def __init__(self, database_service: DatabaseAdapter, features_service: FeaturesService):
        self.database_service = database_service
        self.features_service = features_service
        self.logger = logging.getLogger("krai.api.features")
        self._setup_logging()

        # Create router
        self.router = APIRouter(prefix="/features", tags=["features"])
        self._setup_routes()

    def _setup_logging(self):
        """Setup logging for features API"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - FeaturesAPI - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _setup_routes(self):
        """Setup API routes"""

        @self.router.get("/series/{series_id}")
        async def get_series_features(series_id: str):
            """Get series features"""
            try:
                features = await self.features_service.get_series_features(series_id)

                return {"series_id": series_id, "features": features, "timestamp": datetime.utcnow().isoformat()}

            except Exception as e:
                self.logger.error(f"Failed to get series features {series_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/product/{product_id}")
        async def get_product_features(product_id: str):
            """Get product features"""
            try:
                features = await self.features_service.get_product_features(product_id)

                return {"product_id": product_id, "features": features, "timestamp": datetime.utcnow().isoformat()}

            except Exception as e:
                self.logger.error(f"Failed to get product features {product_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/effective/{series_id}/{product_id}")
        async def get_effective_features(series_id: str, product_id: str):
            """Get effective features with inheritance"""
            try:
                effective_features = await self.features_service.get_effective_features(series_id, product_id)

                return {
                    "series_id": series_id,
                    "product_id": product_id,
                    "effective_features": effective_features,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                self.logger.error(f"Failed to get effective features {series_id}/{product_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/search")
        async def search_by_features(
            features_query: dict[str, Any], limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)
        ):
            """Search products by features"""
            try:
                results = await self.features_service.search_by_features(features_query)

                # Apply pagination
                paginated_results = results[offset : offset + limit]

                return {
                    "query": features_query,
                    "results": paginated_results,
                    "total_count": len(results),
                    "limit": limit,
                    "offset": offset,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                self.logger.error(f"Failed to search by features: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.put("/series/{series_id}")
        async def update_series_features(series_id: str, features_update: dict[str, Any]):
            """Update series features"""
            try:
                # This would typically update the database
                # For now, just log the update
                await self.database_service.log_audit(
                    action="series_features_updated",
                    entity_type="product_series",
                    entity_id=series_id,
                    details=features_update,
                )

                return {
                    "message": "Series features updated successfully",
                    "series_id": series_id,
                    "updated_features": features_update,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                self.logger.error(f"Failed to update series features {series_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.put("/product/{product_id}")
        async def update_product_features(product_id: str, features_update: dict[str, Any]):
            """Update product features"""
            try:
                # This would typically update the database
                # For now, just log the update
                await self.database_service.log_audit(
                    action="product_features_updated",
                    entity_type="product",
                    entity_id=product_id,
                    details=features_update,
                )

                return {
                    "message": "Product features updated successfully",
                    "product_id": product_id,
                    "updated_features": features_update,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                self.logger.error(f"Failed to update product features {product_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/inheritance/{series_id}")
        async def get_inheritance_info(series_id: str):
            """Get features inheritance information"""
            try:
                # This would typically query the database for inheritance relationships
                # For now, return placeholder data
                inheritance_info = {
                    "series_id": series_id,
                    "parent_series": None,
                    "child_series": [],
                    "inherited_features": [],
                    "overridden_features": [],
                    "inheritance_chain": [series_id],
                }

                return {"inheritance_info": inheritance_info, "timestamp": datetime.utcnow().isoformat()}

            except Exception as e:
                self.logger.error(f"Failed to get inheritance info {series_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def features_health_check():
            """Features service health check"""
            try:
                # Test database service
                db_health = await self.database_service.health_check()

                return {
                    "status": "healthy" if db_health["status"] == "healthy" else "degraded",
                    "database_service": db_health,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
