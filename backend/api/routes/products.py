"""Product CRUD and batch API routes."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from backend.api.dependencies.database import get_database_adapter
from backend.api.middleware.auth_middleware import require_permission
from backend.api.middleware.rate_limit_middleware import (
    limiter,
    rate_limit_search,
    rate_limit_standard,
    rate_limit_upload,
)
from backend.api.routes.response_models import ErrorResponse, SuccessResponse
from backend.constants.product_types import ALLOWED_PRODUCT_TYPES
from backend.models.document import PaginationParams
from backend.models.manufacturer import ManufacturerResponse
from backend.models.product import (
    ProductBatchCreateRequest,
    ProductBatchDeleteRequest,
    ProductBatchResponse,
    ProductBatchResult,
    ProductBatchUpdateRequest,
    ProductCreateRequest,
    ProductFilterParams,
    ProductListResponse,
    ProductResponse,
    ProductSeriesResponse,
    ProductSortParams,
    ProductStatsResponse,
    ProductUpdateRequest,
    ProductWithRelationsResponse,
    SortOrder,
)
from backend.services.database_adapter import DatabaseAdapter

LOGGER = logging.getLogger("krai.api.products")

router = APIRouter(prefix="/products", tags=["products"])


class MessagePayload(BaseModel):
    """Payload carrying a textual message."""

    message: str


class ProductTypesResponse(BaseModel):
    """Response payload listing all allowed product types."""

    product_types: list[str]


def _apply_product_filters(query: Any, filters: ProductFilterParams) -> Any:
    if filters.manufacturer_id:
        query = query.eq("manufacturer_id", filters.manufacturer_id)
    if filters.series_id:
        query = query.eq("series_id", filters.series_id)
    if filters.product_type:
        query = query.eq("product_type", filters.product_type)
    if filters.launch_date_from:
        query = query.gte("launch_date", filters.launch_date_from.isoformat())
    if filters.launch_date_to:
        query = query.lte("launch_date", filters.launch_date_to.isoformat())
    if filters.end_of_life_date_from:
        query = query.gte("end_of_life_date", filters.end_of_life_date_from.isoformat())
    if filters.end_of_life_date_to:
        query = query.lte("end_of_life_date", filters.end_of_life_date_to.isoformat())
    if filters.min_price is not None:
        query = query.gte("msrp_usd", filters.min_price)
    if filters.max_price is not None:
        query = query.lte("msrp_usd", filters.max_price)
    if filters.print_technology:
        query = query.eq("print_technology", filters.print_technology)
    if filters.network_capable is not None:
        query = query.eq("network_capable", filters.network_capable)
    if filters.search:
        search = filters.search
        query = query.or_(
            f"model_number.ilike.%{search}%," f"model_name.ilike.%{search}%," f"product_type.ilike.%{search}%"
        )
    return query


def _apply_sorting(query: Any, sort: ProductSortParams) -> Any:
    return query.order(sort.sort_by, desc=sort.sort_order == SortOrder.DESC)


def _apply_pagination(query: Any, pagination: PaginationParams) -> Any:
    start_index = (pagination.page - 1) * pagination.page_size
    end_index = start_index + pagination.page_size - 1
    return query.range(start_index, end_index)


def _error_response(
    error: str,
    detail: str | None = None,
    error_code: str | None = None,
) -> dict[str, str | None]:
    return ErrorResponse(error=error, detail=detail, error_code=error_code).dict()


def _log_and_raise(
    status_code: int,
    message: str,
    *,
    error: str = "Error",
    error_code: str | None = None,
) -> None:
    LOGGER.error(message)
    raise HTTPException(
        status_code=status_code,
        detail=_error_response(error=error, detail=message, error_code=error_code),
    )


def _calculate_total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 1
    return ceil(total / page_size)


def _build_product_relations(
    product: dict[str, Any],
    adapter: DatabaseAdapter,
    include_relations: bool,
) -> ProductWithRelationsResponse:
    product_payload: dict[str, Any] = {**product}
    if not include_relations:
        return ProductWithRelationsResponse(**product_payload)

    manufacturer_id = product.get("manufacturer_id")
    if manufacturer_id:
        manufacturer_resp = adapter.execute_query(
            "SELECT * FROM krai_core.manufacturers WHERE id = $1 LIMIT 1", [manufacturer_id]
        )
        manufacturer_data = manufacturer_resp[0] if manufacturer_resp else None
        if manufacturer_data:
            product_payload["manufacturer"] = ManufacturerResponse(**manufacturer_data)

    series_id = product.get("series_id")
    if series_id:
        series_resp = adapter.execute_query("SELECT * FROM krai_core.product_series WHERE id = $1 LIMIT 1", [series_id])
        series_data = series_resp[0] if series_resp else None
        if series_data:
            product_payload["series"] = ProductSeriesResponse(**series_data)

    parent_id = product.get("parent_id")
    if parent_id:
        parent_resp = adapter.execute_query("SELECT * FROM krai_core.products WHERE id = $1 LIMIT 1", [parent_id])
        parent_data = parent_resp[0] if parent_resp else None
        if parent_data:
            product_payload["parent_product"] = ProductResponse(**parent_data)

    return ProductWithRelationsResponse(**product_payload)


@router.get(
    "",
    response_model=SuccessResponse[ProductListResponse],
)
@limiter.limit(rate_limit_search)
async def list_products(
    request: Request,
    pagination: PaginationParams = Depends(),
    filters: ProductFilterParams = Depends(),
    sort: ProductSortParams = Depends(),
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductListResponse]:
    try:
        where_clauses = []
        params = []
        param_count = 0

        if filters.manufacturer_id:
            param_count += 1
            where_clauses.append(f"manufacturer_id = ${param_count}")
            params.append(filters.manufacturer_id)

        if filters.series_id:
            param_count += 1
            where_clauses.append(f"series_id = ${param_count}")
            params.append(filters.series_id)

        if filters.product_type:
            param_count += 1
            where_clauses.append(f"product_type = ${param_count}")
            params.append(filters.product_type.value)

        if filters.search:
            search_term = f"%{filters.search}%"
            n1, n2, n3 = param_count + 1, param_count + 2, param_count + 3
            where_clauses.append(f"(model_number ILIKE ${n1} OR model_name ILIKE ${n2} OR description ILIKE ${n3})")
            params.extend([search_term, search_term, search_term])
            param_count += 3

        where_clause = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        order_direction = "DESC" if sort.sort_order == SortOrder.DESC else "ASC"
        order_clause = f" ORDER BY {sort.sort_by} {order_direction}"

        offset = (pagination.page - 1) * pagination.page_size
        limit_clause = f" LIMIT {pagination.page_size} OFFSET {offset}"

        query = f"""
            SELECT *, COUNT(*) OVER() as total_count
            FROM krai_core.products
            {where_clause}
            {order_clause}
            {limit_clause}
        """

        result = await adapter.execute_query(query, params)

        total = 0
        if result:
            total = result[0].get("total_count", len(result))
        else:
            count_query = f"SELECT COUNT(*) as count FROM krai_core.products{where_clause}"
            count_result = await adapter.execute_query(count_query, params)
            total = count_result[0].get("count", 0) if count_result else 0

        LOGGER.info(
            "Listed products page=%s size=%s total=%s",
            pagination.page,
            pagination.page_size,
            total,
        )

        payload = ProductListResponse(
            products=[ProductResponse(**item) for item in result or []],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=_calculate_total_pages(total, pagination.page_size),
        )
        return SuccessResponse(data=payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/types",
    response_model=SuccessResponse[ProductTypesResponse],
)
@limiter.limit(rate_limit_search)
def get_product_types(
    request: Request,
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
) -> SuccessResponse[ProductTypesResponse]:
    """Return the canonical list of allowed product types."""

    product_types = sorted(ALLOWED_PRODUCT_TYPES)
    return SuccessResponse(data=ProductTypesResponse(product_types=product_types))


@router.get(
    "/{product_id}",
    response_model=SuccessResponse[ProductWithRelationsResponse],
)
@limiter.limit(rate_limit_standard)
async def get_product(
    request: Request,
    product_id: str,
    include_relations: bool = Query(False),
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductWithRelationsResponse]:
    try:
        result = await adapter.execute_query("SELECT * FROM krai_core.products WHERE id = $1 LIMIT 1", [product_id])
        if not result:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Product not found", "PRODUCT_NOT_FOUND"),
            )

        product = _build_product_relations(result[0], adapter, include_relations)
        LOGGER.info("Retrieved product %s include_relations=%s", product_id, include_relations)
        return SuccessResponse(data=product)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(rate_limit_upload)
async def create_product(
    request: Request,
    payload: ProductCreateRequest,
    current_user: dict[str, Any] = Depends(require_permission("products:write")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductResponse]:
    try:
        now = datetime.now(UTC).isoformat()
        product_dict = payload.dict(exclude_none=True)
        product_dict["created_at"] = now
        product_dict["updated_at"] = now

        result = await adapter.execute_query(
            """
                INSERT INTO krai_core.products (
                    model_number,
                    model_name,
                    product_type,
                    manufacturer_id,
                    series_id,
                    launch_date,
                    end_of_life_date,
                    msrp_usd,
                    print_technology,
                    network_capable,
                    description,
                    created_at,
                    updated_at
                ) VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9,
                    $10,
                    $11,
                    $12,
                    $13
                ) RETURNING *
            """,
            [
                product_dict["model_number"],
                product_dict["model_name"],
                product_dict["product_type"],
                product_dict["manufacturer_id"],
                product_dict["series_id"],
                product_dict["launch_date"],
                product_dict["end_of_life_date"],
                product_dict["msrp_usd"],
                product_dict["print_technology"],
                product_dict["network_capable"],
                product_dict["description"],
                product_dict["created_at"],
                product_dict["updated_at"],
            ],
        )
        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to create product"),
            )

        product_id = result[0]["id"]
        LOGGER.info("Created product %s", product_id)

        try:
            await adapter.execute_query(
                """
                    INSERT INTO krai_system.audit_log (
                        table_name,
                        record_id,
                        operation,
                        changed_by,
                        new_values
                    ) VALUES (
                        'products',
                        $1,
                        'INSERT',
                        $2,
                        $3
                    )
                """,
                [
                    product_id,
                    current_user.get("id"),
                    result[0],
                ],
            )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log insert failed for product %s: %s", product_id, audit_exc)

        return SuccessResponse(data=ProductResponse(**result[0]))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.put(
    "/{product_id}",
    response_model=SuccessResponse[ProductResponse],
)
@limiter.limit(rate_limit_standard)
async def update_product(
    request: Request,
    product_id: str,
    payload: ProductUpdateRequest,
    current_user: dict[str, Any] = Depends(require_permission("products:write")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductResponse]:
    try:
        existing = await adapter.execute_query("SELECT * FROM krai_core.products WHERE id = $1 LIMIT 1", [product_id])
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Product not found", "PRODUCT_NOT_FOUND"),
            )

        previous_record = existing[0]

        update_payload = payload.dict(exclude_unset=True, exclude_none=True)
        update_payload["updated_at"] = datetime.now(UTC).isoformat()

        result = await adapter.execute_query(
            """
                UPDATE krai_core.products
                SET
                    model_number = $1,
                    model_name = $2,
                    product_type = $3,
                    manufacturer_id = $4,
                    series_id = $5,
                    launch_date = $6,
                    end_of_life_date = $7,
                    msrp_usd = $8,
                    print_technology = $9,
                    network_capable = $10,
                    description = $11,
                    updated_at = $12
                WHERE id = $13
                RETURNING *
            """,
            [
                update_payload.get("model_number"),
                update_payload.get("model_name"),
                update_payload.get("product_type"),
                update_payload.get("manufacturer_id"),
                update_payload.get("series_id"),
                update_payload.get("launch_date"),
                update_payload.get("end_of_life_date"),
                update_payload.get("msrp_usd"),
                update_payload.get("print_technology"),
                update_payload.get("network_capable"),
                update_payload.get("description"),
                update_payload.get("updated_at"),
                product_id,
            ],
        )
        if not result:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_error_response("Server Error", "Failed to update product"),
            )

        LOGGER.info("Updated product %s", product_id)

        try:
            await adapter.execute_query(
                """
                    INSERT INTO krai_system.audit_log (
                        table_name,
                        record_id,
                        operation,
                        changed_by,
                        old_values,
                        new_values
                    ) VALUES (
                        'products',
                        $1,
                        'UPDATE',
                        $2,
                        $3,
                        $4
                    )
                """,
                [
                    product_id,
                    current_user.get("id"),
                    previous_record,
                    update_payload,
                ],
            )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log update failed for product %s: %s", product_id, audit_exc)

        return SuccessResponse(data=ProductResponse(**result[0]))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.delete(
    "/{product_id}",
    response_model=SuccessResponse[MessagePayload],
)
@limiter.limit(rate_limit_standard)
async def delete_product(
    request: Request,
    product_id: str,
    current_user: dict[str, Any] = Depends(require_permission("products:delete")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[MessagePayload]:
    try:
        existing = await adapter.execute_query("SELECT * FROM krai_core.products WHERE id = $1 LIMIT 1", [product_id])
        if not existing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=_error_response("Not Found", "Product not found", "PRODUCT_NOT_FOUND"),
            )

        await adapter.execute_query("DELETE FROM krai_core.products WHERE id = $1", [product_id])
        LOGGER.info("Deleted product %s", product_id)

        try:
            await adapter.execute_query(
                """
                    INSERT INTO krai_system.audit_log (
                        table_name,
                        record_id,
                        operation,
                        changed_by,
                        old_values
                    ) VALUES (
                        'products',
                        $1,
                        'DELETE',
                        $2,
                        $3
                    )
                """,
                [
                    product_id,
                    current_user.get("id"),
                    existing[0],
                ],
            )
        except Exception as audit_exc:  # pragma: no cover - defensive
            LOGGER.warning("Audit log delete failed for product %s: %s", product_id, audit_exc)

        return SuccessResponse(data=MessagePayload(message="Product deleted successfully"))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/stats",
    response_model=SuccessResponse[ProductStatsResponse],
)
@limiter.limit(rate_limit_search)
async def get_product_stats(
    request: Request,
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductStatsResponse]:
    try:
        total_result = await adapter.execute_query("SELECT COUNT(*) as count FROM krai_core.products")
        total_products = total_result[0].get("count", 0) if total_result else 0

        type_result = await adapter.execute_query(
            "SELECT product_type, COUNT(*) as count FROM krai_core.products GROUP BY product_type"
        )
        by_type = {
            item.get("product_type"): item.get("count", 0) for item in type_result or [] if item.get("product_type")
        }

        manufacturer_result = await adapter.execute_query(
            "SELECT manufacturer_id, COUNT(*) as count FROM krai_core.products GROUP BY manufacturer_id"
        )
        manufacturer_counts = {
            item.get("manufacturer_id"): item.get("count", 0)
            for item in manufacturer_result or []
            if item.get("manufacturer_id")
        }

        manufacturer_names: dict[str, str] = {}
        if manufacturer_counts:
            ids = list(manufacturer_counts.keys())
            placeholders = ",".join([f"${i+1}" for i in range(len(ids))])
            manufacturer_data_result = await adapter.execute_query(
                f"SELECT id, name FROM krai_core.manufacturers WHERE id IN ({placeholders})", ids
            )
            manufacturer_names = {item["id"]: item["name"] for item in manufacturer_data_result or [] if item.get("id")}

        by_manufacturer = {
            manufacturer_names.get(manufacturer_id, manufacturer_id): count
            for manufacturer_id, count in manufacturer_counts.items()
        }

        today = date.today().isoformat()
        active_result = await adapter.execute_query(
            "SELECT COUNT(*) as count FROM krai_core.products WHERE end_of_life_date IS NULL OR end_of_life_date > $1",
            [today],
        )
        active_products = active_result[0].get("count", 0) if active_result else 0

        discontinued_result = await adapter.execute_query(
            "SELECT COUNT(*) as count FROM krai_core.products WHERE end_of_life_date < $1", [today]
        )
        discontinued_products = discontinued_result[0].get("count", 0) if discontinued_result else 0

        LOGGER.info(
            "Product stats computed totals=%s types=%s manufacturers=%s",
            total_products,
            len(by_type),
            len(by_manufacturer),
        )

        stats = ProductStatsResponse(
            total_products=total_products,
            by_type=by_type,
            by_manufacturer=by_manufacturer,
            active_products=active_products,
            discontinued_products=discontinued_products,
        )
        return SuccessResponse(data=stats)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.post(
    "/batch/create",
    response_model=SuccessResponse[ProductBatchResponse],
)
@limiter.limit(rate_limit_upload)
async def batch_create_products(
    request: Request,
    payload: ProductBatchCreateRequest,
    current_user: dict[str, Any] = Depends(require_permission("products:write")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductBatchResponse]:
    results: list[ProductBatchResult] = []
    success_count = 0
    try:
        for product in payload.products:
            try:
                now = datetime.now(UTC).isoformat()
                product_dict = product.dict(exclude_none=True)
                product_dict["created_at"] = now
                product_dict["updated_at"] = now

                result = await adapter.execute_query(
                    """
                        INSERT INTO krai_core.products (
                            model_number,
                            model_name,
                            product_type,
                            manufacturer_id,
                            series_id,
                            launch_date,
                            end_of_life_date,
                            msrp_usd,
                            print_technology,
                            network_capable,
                            description,
                            created_at,
                            updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                        ) RETURNING *
                    """,
                    [
                        product_dict.get("model_number"),
                        product_dict.get("model_name"),
                        product_dict.get("product_type"),
                        product_dict.get("manufacturer_id"),
                        product_dict.get("series_id"),
                        product_dict.get("launch_date"),
                        product_dict.get("end_of_life_date"),
                        product_dict.get("msrp_usd"),
                        product_dict.get("print_technology"),
                        product_dict.get("network_capable"),
                        product_dict.get("description"),
                        product_dict.get("created_at"),
                        product_dict.get("updated_at"),
                    ],
                )

                if not result:
                    raise ValueError("Failed to insert product")

                product_id = result[0]["id"]
                results.append(ProductBatchResult(id=product_id, status="success"))
                success_count += 1

                try:
                    await adapter.execute_query(
                        """
                            INSERT INTO krai_system.audit_log (
                                table_name,
                                record_id,
                                operation,
                                changed_by,
                                new_values
                            ) VALUES (
                                'products', $1, 'INSERT', $2, $3
                            )
                        """,
                        [
                            product_id,
                            current_user.get("id"),
                            result[0],
                        ],
                    )
                except Exception as audit_exc:  # pragma: no cover - defensive
                    LOGGER.warning(
                        "Batch audit log insert failed for product %s: %s",
                        product_id,
                        audit_exc,
                    )
            except Exception as inner_exc:
                LOGGER.warning("Batch create failed for product %s: %s", product.model_number, inner_exc)
                results.append(
                    ProductBatchResult(
                        id=None,
                        status="failed",
                        error=str(inner_exc),
                    )
                )

        summary = ProductBatchResponse(
            success=success_count == len(payload.products),
            total=len(payload.products),
            successful=success_count,
            failed=len(payload.products) - success_count,
            results=results,
        )
        return SuccessResponse(data=summary)
    except HTTPException:
        raise
    except Exception as exc:
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.put(
    "/batch/update",
    response_model=SuccessResponse[ProductBatchResponse],
)
@limiter.limit(rate_limit_standard)
async def batch_update_products(
    request: Request,
    payload: ProductBatchUpdateRequest,
    current_user: dict[str, Any] = Depends(require_permission("products:write")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductBatchResponse]:
    results: list[ProductBatchResult] = []
    success_count = 0
    try:
        for item in payload.updates:
            try:
                update_data = item.update_data.dict(exclude_unset=True, exclude_none=True)
                if not update_data:
                    raise ValueError("No update data provided")
                update_data["updated_at"] = datetime.now(UTC).isoformat()

                # Build dynamic UPDATE query
                set_clauses = []
                params = []
                param_count = 0

                for key, value in update_data.items():
                    param_count += 1
                    set_clauses.append(f"{key} = ${param_count}")
                    params.append(value)

                param_count += 1  # For the WHERE clause
                params.append(item.id)

                query = f"""
                    UPDATE krai_core.products
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_count}
                    RETURNING *
                """

                result = await adapter.execute_query(query, params)

                if not result:
                    raise ValueError("Product not found or update failed")

                results.append(ProductBatchResult(id=item.id, status="success"))
                success_count += 1

                try:
                    await adapter.execute_query(
                        """
                            INSERT INTO krai_system.audit_log (
                                table_name,
                                record_id,
                                operation,
                                changed_by,
                                new_values
                            ) VALUES (
                                'products', $1, 'UPDATE', $2, $3
                            )
                        """,
                        [
                            item.id,
                            current_user.get("id"),
                            update_data,
                        ],
                    )
                except Exception as audit_exc:  # pragma: no cover - defensive
                    LOGGER.warning(
                        "Batch audit log update failed for product %s: %s",
                        item.id,
                        audit_exc,
                    )
            except Exception as inner_exc:
                LOGGER.warning("Batch update failed for product %s: %s", item.id, inner_exc)
                results.append(
                    ProductBatchResult(
                        id=item.id,
                        status="failed",
                        error=str(inner_exc),
                    )
                )

        summary = ProductBatchResponse(
            success=success_count == len(payload.updates),
            total=len(payload.updates),
            successful=success_count,
            failed=len(payload.updates) - success_count,
            results=results,
        )
        return SuccessResponse(data=summary)
    except HTTPException:
        raise
    except Exception as exc:
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.delete(
    "/batch/delete",
    response_model=SuccessResponse[ProductBatchResponse],
)
@limiter.limit(rate_limit_standard)
async def batch_delete_products(
    request: Request,
    payload: ProductBatchDeleteRequest,
    current_user: dict[str, Any] = Depends(require_permission("products:delete")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[ProductBatchResponse]:
    results: list[ProductBatchResult] = []
    success_count = 0
    try:
        for product_id in payload.product_ids:
            try:
                # First get the existing product for audit log
                existing = await adapter.execute_query(
                    "SELECT * FROM krai_core.products WHERE id = $1 LIMIT 1", [product_id]
                )
                if not existing:
                    raise ValueError("Product not found")

                # Delete the product
                await adapter.execute_query("DELETE FROM krai_core.products WHERE id = $1", [product_id])

                results.append(ProductBatchResult(id=product_id, status="success"))
                success_count += 1

                try:
                    await adapter.execute_query(
                        """
                            INSERT INTO krai_system.audit_log (
                                table_name,
                                record_id,
                                operation,
                                changed_by,
                                old_values
                            ) VALUES (
                                'products', $1, 'DELETE', $2, $3
                            )
                        """,
                        [
                            product_id,
                            current_user.get("id"),
                            existing[0],
                        ],
                    )
                except Exception as audit_exc:  # pragma: no cover - defensive
                    LOGGER.warning(
                        "Batch audit log delete failed for product %s: %s",
                        product_id,
                        audit_exc,
                    )
            except Exception as inner_exc:
                LOGGER.warning("Batch delete failed for product %s: %s", product_id, inner_exc)
                results.append(
                    ProductBatchResult(
                        id=product_id,
                        status="failed",
                        error=str(inner_exc),
                    )
                )

        summary = ProductBatchResponse(
            success=success_count == len(payload.product_ids),
            total=len(payload.product_ids),
            successful=success_count,
            failed=len(payload.product_ids) - success_count,
            results=results,
        )
        return SuccessResponse(data=summary)
    except HTTPException:
        raise
    except Exception as exc:
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@router.get(
    "/series/by-manufacturer/{manufacturer_id}",
    response_model=SuccessResponse[list[ProductSeriesResponse]],
)
@limiter.limit(rate_limit_search)
async def get_manufacturer_series(
    request: Request,
    manufacturer_id: str,
    current_user: dict[str, Any] = Depends(require_permission("products:read")),
    adapter: DatabaseAdapter = Depends(get_database_adapter),
) -> SuccessResponse[list[ProductSeriesResponse]]:
    """Get all product series for a manufacturer."""
    try:
        result = await adapter.execute_query(
            "SELECT * FROM krai_core.product_series WHERE manufacturer_id = $1", [manufacturer_id]
        )
        series_list = [ProductSeriesResponse(**item) for item in result or []]
        return SuccessResponse(data=series_list)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        _log_and_raise(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))
