"""PostgreSQL-backed Manufacturer API routes for KR-AI-Engine."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.middleware.auth_middleware import require_permission
from backend.api.routes.response_models import SuccessResponse
from backend.models.document import PaginationParams
from backend.models.manufacturer import (
    ManufacturerFilterParams,
    ManufacturerListResponse,
    ManufacturerResponse,
    ManufacturerSortParams,
    SortOrder,
)
from backend.services.database_adapter import DatabaseAdapter


class ManufacturerAPI:
    """Manufacturer list API backed by PostgreSQL."""

    def __init__(self, database_service: DatabaseAdapter) -> None:
        self.database_service = database_service
        self.logger = logging.getLogger("krai.api.manufacturers.pg")
        self.router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("", response_model=SuccessResponse[ManufacturerListResponse])
        async def list_manufacturers(
            request: Request,
            pagination: PaginationParams = Depends(),
            filters: ManufacturerFilterParams = Depends(),
            sort: ManufacturerSortParams = Depends(),
            current_user: dict[str, Any] = Depends(require_permission("manufacturers:read")),
        ) -> SuccessResponse[ManufacturerListResponse]:
            """List manufacturers with pagination, filtering, and sorting (PostgreSQL-backed)."""

            try:
                conditions: list[str] = []
                params: dict[str, Any] = {}

                if filters.country:
                    conditions.append("country = :country")
                    params["country"] = filters.country
                if filters.is_competitor is not None:
                    conditions.append("is_competitor = :is_competitor")
                    params["is_competitor"] = filters.is_competitor
                if filters.founded_year_from is not None:
                    conditions.append("founded_year >= :founded_year_from")
                    params["founded_year_from"] = filters.founded_year_from
                if filters.founded_year_to is not None:
                    conditions.append("founded_year <= :founded_year_to")
                    params["founded_year_to"] = filters.founded_year_to
                if filters.search:
                    conditions.append("(name ILIKE :search OR short_name ILIKE :search OR country ILIKE :search)")
                    params["search"] = f"%{filters.search}%"

                where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

                order_direction = "DESC" if sort.sort_order == SortOrder.DESC else "ASC"
                order_clause = f" ORDER BY {sort.sort_by} {order_direction}"

                offset = (pagination.page - 1) * pagination.page_size
                params["limit"] = pagination.page_size
                params["offset"] = offset

                base_select = """
                    SELECT
                        id,
                        name,
                        short_name,
                        country,
                        founded_year,
                        website,
                        support_email,
                        support_phone,
                        logo_url,
                        is_competitor,
                        market_share_percent,
                        annual_revenue_usd,
                        employee_count,
                        headquarters_address,
                        stock_symbol,
                        primary_business_segment,
                        created_at,
                        updated_at
                    FROM krai_core.manufacturers
                """

                list_query = base_select + where_clause + order_clause + " LIMIT :limit OFFSET :offset"
                rows = await self.database_service.fetch_all(list_query, params)

                count_query = "SELECT COUNT(*) AS count FROM krai_core.manufacturers" + where_clause
                count_row = await self.database_service.fetch_one(count_query, params)
                total = int(count_row["count"]) if count_row and "count" in count_row else 0

                manufacturers = [ManufacturerResponse(**dict(row)) for row in rows or []]
                total_pages = max(1, ceil(total / pagination.page_size)) if total else 1

                payload = ManufacturerListResponse(
                    manufacturers=manufacturers,
                    total=total,
                    page=pagination.page,
                    page_size=pagination.page_size,
                    total_pages=total_pages,
                )

                return SuccessResponse(data=payload)
            except HTTPException:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.error("Failed to list manufacturers: %s", exc)
                raise HTTPException(status_code=500, detail=str(exc))
