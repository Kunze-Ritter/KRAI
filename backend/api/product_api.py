"""PostgreSQL-backed Product API routes for KR-AI-Engine."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from api.middleware.auth_middleware import require_permission
from api.routes.response_models import SuccessResponse
from models.document import PaginationParams
from models.product import ProductFilterParams, ProductListResponse, ProductResponse, ProductSortParams, SortOrder
from services.database_adapter import DatabaseAdapter


class ProductAPI:
    """Product list and lookup API backed by PostgreSQL."""

    def __init__(self, database_service: DatabaseAdapter) -> None:
        self.database_service = database_service
        self.logger = logging.getLogger("krai.api.products.pg")
        self.router = APIRouter(prefix="/products", tags=["products"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("", response_model=SuccessResponse[ProductListResponse])
        async def list_products(
            request: Request,
            pagination: PaginationParams = Depends(),
            filters: ProductFilterParams = Depends(),
            sort: ProductSortParams = Depends(),
            current_user: dict[str, Any] = Depends(require_permission("products:read")),
        ) -> SuccessResponse[ProductListResponse]:
            """List products with pagination, filtering, and sorting (PostgreSQL-backed)."""

            try:
                conditions: list[str] = []
                params: dict[str, Any] = {}

                if filters.manufacturer_id:
                    conditions.append("manufacturer_id = :manufacturer_id")
                    params["manufacturer_id"] = filters.manufacturer_id
                if filters.series_id:
                    conditions.append("series_id = :series_id")
                    params["series_id"] = filters.series_id
                if filters.product_type:
                    conditions.append("product_type = :product_type")
                    params["product_type"] = filters.product_type
                if filters.launch_date_from:
                    conditions.append("launch_date >= :launch_date_from")
                    params["launch_date_from"] = filters.launch_date_from
                if filters.launch_date_to:
                    conditions.append("launch_date <= :launch_date_to")
                    params["launch_date_to"] = filters.launch_date_to
                if filters.end_of_life_date_from:
                    conditions.append("end_of_life_date >= :eol_date_from")
                    params["eol_date_from"] = filters.end_of_life_date_from
                if filters.end_of_life_date_to:
                    conditions.append("end_of_life_date <= :eol_date_to")
                    params["eol_date_to"] = filters.end_of_life_date_to
                if filters.min_price is not None:
                    conditions.append("msrp_usd >= :min_price")
                    params["min_price"] = filters.min_price
                if filters.max_price is not None:
                    conditions.append("msrp_usd <= :max_price")
                    params["max_price"] = filters.max_price
                if filters.print_technology:
                    conditions.append("print_technology = :print_technology")
                    params["print_technology"] = filters.print_technology
                if filters.network_capable is not None:
                    conditions.append("network_capable = :network_capable")
                    params["network_capable"] = filters.network_capable
                if filters.search:
                    conditions.append(
                        "(model_number ILIKE :search OR model_name ILIKE :search OR product_type ILIKE :search)"
                    )
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
                        parent_id,
                        manufacturer_id,
                        series_id,
                        model_number,
                        model_name,
                        product_type,
                        launch_date,
                        end_of_life_date,
                        msrp_usd,
                        weight_kg,
                        dimensions_mm,
                        color_options,
                        connectivity_options,
                        print_technology,
                        max_print_speed_ppm,
                        max_resolution_dpi,
                        max_paper_size,
                        duplex_capable,
                        network_capable,
                        mobile_print_support,
                        supported_languages,
                        energy_star_certified,
                        warranty_months,
                        service_manual_url,
                        parts_catalog_url,
                        driver_download_url,
                        firmware_version,
                        option_dependencies,
                        replacement_parts,
                        common_issues,
                        created_at,
                        updated_at
                    FROM krai_core.products_backup
                """

                list_query = base_select + where_clause + order_clause + " LIMIT :limit OFFSET :offset"
                rows = await self.database_service.fetch_all(list_query, params)

                count_query = "SELECT COUNT(*) AS count FROM krai_core.products_backup" + where_clause
                count_row = await self.database_service.fetch_one(count_query, params)
                total = int(count_row["count"]) if count_row and "count" in count_row else 0

                products = [ProductResponse(**dict(row)) for row in rows or []]

                total_pages = max(1, ceil(total / pagination.page_size)) if total else 1

                payload = ProductListResponse(
                    products=products,
                    total=total,
                    page=pagination.page,
                    page_size=pagination.page_size,
                    total_pages=total_pages,
                )

                return SuccessResponse(data=payload)
            except HTTPException:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.error("Failed to list products: %s", exc)
                raise HTTPException(status_code=500, detail=str(exc))

        # Simple in-memory product types endpoint, mirroring legacy behavior
        @self.router.get("/types", response_model=SuccessResponse[dict[str, list[str]]])
        async def get_product_types(
            request: Request,
            current_user: dict[str, Any] = Depends(require_permission("products:read")),
        ) -> SuccessResponse[dict[str, list[str]]]:
            """Return the canonical list of allowed product types from backend.constants.product_types."""
            from backend.constants.product_types import ALLOWED_PRODUCT_TYPES

            product_types = sorted(ALLOWED_PRODUCT_TYPES)
            return SuccessResponse(data={"product_types": product_types})
