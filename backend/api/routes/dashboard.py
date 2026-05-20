"""Dashboard overview routes for aggregated production metrics."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.api.dependencies.database import get_database_pool
from backend.api.middleware.auth_middleware import require_permission

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _fetch_count(pool: asyncpg.Pool, query: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query)
    if not row:
        return 0
    return int(row["count"] or 0)


async def _fetch_group_counts(pool: asyncpg.Pool, query: str, key_field: str) -> dict[str, int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    results: dict[str, int] = {}
    for row in rows or []:
        key = row.get(key_field) or "unknown"
        results[str(key)] = int(row.get("count", 0) or 0)
    return results


async def _fetch_recent_documents(pool: asyncpg.Pool, limit: int = 5) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, filename, processing_status, manufacturer, updated_at
            FROM krai_core.documents
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
        recent: list[dict[str, Any]] = []
        for row in rows or []:
            updated_at = row.get("updated_at")
            if isinstance(updated_at, datetime):
                updated_at = updated_at.astimezone(UTC).isoformat()
            recent.append(
                {
                    "id": str(row.get("id")),
                    "filename": row.get("filename"),
                    "manufacturer": row.get("manufacturer"),
                    "status": row.get("processing_status"),
                    "updated_at": updated_at,
                }
            )
        return recent


@router.get("/overview")
async def get_dashboard_overview(
    current_user: dict = Depends(require_permission("monitoring:read")),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Return aggregated dashboard stats for production data.

    This endpoint requires 'monitoring:read' permission to access.
    Any failure to query optional tables (or other runtime issues) is logged
    and a safe fallback overview with zero/empty stats is returned instead of a 500 error.
    """

    try:
        total_documents = await _fetch_count(pool, "SELECT COUNT(*) AS count FROM krai_core.documents")
        documents_by_status = await _fetch_group_counts(
            pool,
            "SELECT processing_status, COUNT(*) AS count " "FROM krai_core.documents GROUP BY processing_status",
            "processing_status",
        )
        documents_by_type = await _fetch_group_counts(
            pool,
            "SELECT document_type, COUNT(*) AS count " "FROM krai_core.documents GROUP BY document_type",
            "document_type",
        )
        processed_last_24h = await _fetch_count(
            pool,
            "SELECT COUNT(*) AS count FROM krai_core.documents "
            "WHERE processing_status = 'completed' "
            "AND updated_at >= NOW() - INTERVAL '24 hours'",
        )

        total_products = await _fetch_count(pool, "SELECT COUNT(*) AS count FROM krai_core.products")
        manufacturers_total = await _fetch_count(pool, "SELECT COUNT(*) AS count FROM krai_core.manufacturers")
        active_products = await _fetch_count(
            pool,
            "SELECT COUNT(*) AS count FROM krai_core.products "
            "WHERE end_of_life_date IS NULL OR end_of_life_date > NOW()",
        )
        discontinued_products = await _fetch_count(
            pool,
            "SELECT COUNT(*) AS count FROM krai_core.products "
            "WHERE end_of_life_date IS NOT NULL AND end_of_life_date <= NOW()",
        )

        queue_by_status = await _fetch_group_counts(
            pool,
            "SELECT status, COUNT(*) AS count FROM krai_system.processing_queue GROUP BY status",
            "status",
        )
        queue_total = sum(queue_by_status.values())

        try:
            images_total = await _fetch_count(pool, "SELECT COUNT(*) AS count FROM krai_content.images")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Dashboard images_total query failed: %s", exc)
            images_total = 0

        try:
            videos_total = await _fetch_count(pool, "SELECT COUNT(*) AS count FROM krai_content.videos")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Dashboard videos_total query failed: %s", exc)
            videos_total = 0

        overview = {
            "documents": {
                "total": total_documents,
                "by_status": documents_by_status,
                "by_type": documents_by_type,
                "processed_last_24h": processed_last_24h,
                "recent": await _fetch_recent_documents(pool),
            },
            "products": {
                "total": total_products,
                "manufacturers": manufacturers_total,
                "active": active_products,
                "discontinued": discontinued_products,
            },
            "queue": {
                "total": queue_total,
                "by_status": queue_by_status,
            },
            "media": {
                "images": images_total,
                "videos": videos_total,
            },
        }

        return {"success": True, "data": overview}
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load dashboard data, returning safe fallback: %s", exc)
        fallback_overview = {
            "documents": {
                "total": 0,
                "by_status": {},
                "by_type": {},
                "processed_last_24h": 0,
                "recent": [],
            },
            "products": {
                "total": 0,
                "manufacturers": 0,
                "active": 0,
                "discontinued": 0,
            },
            "queue": {
                "total": 0,
                "by_status": {},
            },
            "media": {
                "images": 0,
                "videos": 0,
            },
        }
        return {"success": True, "data": fallback_overview}
