"""
KRAI AI Agent API
=================
LangGraph-based conversational agent for technical support.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import AsyncGenerator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from api.agent_scope import (
    CURRENT_AGENT_SCOPE,
    AgentScope,
    build_error_code_variants,
    build_scope_filters,
    build_scope_system_message,
    extract_error_search_term,
    merge_scope,
    normalize_scope,
)
from api.middleware.auth_middleware import require_permission
from processors.env_loader import load_all_env_files
from services.db_pool import get_pool

project_root = Path(__file__).parent.parent.parent
load_all_env_files(project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Chat message from user."""

    message: str | list[dict] = Field(..., description="User message (text or vision parts)")
    session_id: str = Field(..., description="Unique session ID for conversation memory")
    stream: bool = Field(default=False, description="Enable streaming response")
    scope: AgentScope | None = Field(default=None, description="Optional machine/product scope")
    reset_scope: bool = Field(default=False, description="Clear stored scope before applying scope update")


class ChatResponse(BaseModel):
    """Chat response from agent."""

    response: str
    session_id: str
    timestamp: str
    active_scope: AgentScope | None = None


def _coalesce_product_label(row: asyncpg.Record) -> str | None:
    product_bits = [
        row["model_name"] if "model_name" in row else None,
        row["model_number"] if "model_number" in row else None,
    ]
    product_label = " ".join(bit for bit in product_bits if bit).strip()
    return product_label or None


def _serialize_scope() -> dict[str, str]:
    return normalize_scope(CURRENT_AGENT_SCOPE.get())


def _serialize_error_code_row(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "error_code": row["error_code"],
        "error_description": row["error_description"],
        "solution_technician_text": row["solution_technician_text"],
        "solution_agent_text": row["solution_agent_text"],
        "solution_customer_text": row["solution_customer_text"],
        "preferred_solution": row["preferred_solution"],
        "manufacturer": row["manufacturer_name"],
        "product": _coalesce_product_label(row),
        "series": row["series_name"],
        "document": row["document_filename"],
        "document_id": str(row["document_id"]) if row["document_id"] else None,
        "product_id": str(row["product_id"]) if row["product_id"] else None,
        "video_id": str(row["video_id"]) if row["video_id"] else None,
        "chunk_id": str(row["chunk_id"]) if row["chunk_id"] else None,
        "page_number": row["page_number"],
        "severity_level": row["severity_level"],
        "confidence_score": float(row["confidence_score"]) if row["confidence_score"] else 0.0,
    }


def _serialize_video_row(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "video_id": str(row["id"]),
        "title": row["title"],
        "url": row["video_url"],
        "description": row["description"],
        "duration": row["duration"],
        "manufacturer": row["manufacturer_name"],
        "product": _coalesce_product_label(row),
        "series": row["series_name"],
        "document_id": str(row["document_id"]) if row["document_id"] else None,
    }


def _serialize_document_row(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "document_id": str(row["id"]),
        "filename": row["filename"],
        "document_type": row["document_type"],
        "manufacturer": row["manufacturer_name"],
        "product": _coalesce_product_label(row),
        "series": row["series_name"],
    }


def _serialize_part_row(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "part_number": row["part_number"],
        "part_name": row["part_name"],
        "description": row["description"],
        "category": row["category"],
        "price_usd": float(row["price_usd"]) if row["price_usd"] else None,
        "manufacturer": row["manufacturer_name"],
        "product": _coalesce_product_label(row),
        "series": row["series_name"],
    }


async def _fetch_related_videos(
    conn: asyncpg.Connection,
    query: str,
    scope: dict[str, str],
    *,
    matched_product_ids: Sequence[str] = (),
    matched_document_ids: Sequence[str] = (),
    limit: int = 5,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    signals: list[str] = []

    for template in (
        "v.title ILIKE ${index}",
        "COALESCE(v.description, '') ILIKE ${index}",
        "COALESCE(v.context_description, '') ILIKE ${index}",
        (
            "EXISTS (SELECT 1 FROM unnest(COALESCE(v.related_products, ARRAY[]::text[])) AS related_product "
            "WHERE related_product ILIKE ${index})"
        ),
        "COALESCE(p.model_number, '') ILIKE ${index}",
        "COALESCE(p.model_name, '') ILIKE ${index}",
        "COALESCE(ps.series_name, '') ILIKE ${index}",
    ):
        params.append(f"%{query}%")
        signals.append(template.format(index=len(params)))

    if matched_product_ids:
        params.append(list(matched_product_ids))
        signals.append(f"vp.product_id = ANY(${len(params)}::uuid[])")

    if matched_document_ids:
        params.append(list(matched_document_ids))
        signals.append(f"v.document_id = ANY(${len(params)}::uuid[])")

    where_clauses = [f"({' OR '.join(signals)})"]
    where_clauses.extend(
        build_scope_filters(
            params,
            scope,
            manufacturer_templates=("m.name ILIKE ${index}",),
            product_templates=(
                "COALESCE(p.model_number, '') ILIKE ${index}",
                "COALESCE(p.model_name, '') ILIKE ${index}",
                "COALESCE(ps.series_name, '') ILIKE ${index}",
                (
                    "EXISTS (SELECT 1 FROM unnest(COALESCE(v.related_products, ARRAY[]::text[])) AS scoped_product "
                    "WHERE scoped_product ILIKE ${index})"
                ),
            ),
            product_id_template="vp.product_id = ${index}::uuid",
            series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
            document_id_template="v.document_id = ${index}::uuid",
        )
    )

    params.append(limit)
    sql = f"""
        SELECT DISTINCT ON (v.id)
               v.id, v.video_url, v.title, v.description, v.duration,
               v.document_id, m.name AS manufacturer_name,
               p.model_number, p.model_name, ps.series_name
        FROM   krai_content.videos v
        LEFT JOIN krai_core.manufacturers m ON v.manufacturer_id = m.id
        LEFT JOIN krai_content.video_products vp ON vp.video_id = v.id
        LEFT JOIN krai_core.products p ON vp.product_id = p.id
        LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
        WHERE  {' AND '.join(where_clauses)}
        ORDER  BY v.id, v.updated_at DESC
        LIMIT  ${len(params)}
    """
    rows = await conn.fetch(sql, *params)
    return [_serialize_video_row(row) for row in rows]


async def _fetch_related_documents(
    conn: asyncpg.Connection,
    query: str,
    scope: dict[str, str],
    *,
    matched_document_ids: Sequence[str] = (),
    matched_product_ids: Sequence[str] = (),
    limit: int = 8,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    signals: list[str] = []

    for template in (
        "d.filename ILIKE ${index}",
        "d.document_type ILIKE ${index}",
        "COALESCE(ch.text_chunk, '') ILIKE ${index}",
    ):
        params.append(f"%{query}%")
        signals.append(template.format(index=len(params)))

    if matched_document_ids:
        params.append(list(matched_document_ids))
        signals.append(f"d.id = ANY(${len(params)}::uuid[])")

    if matched_product_ids:
        params.append(list(matched_product_ids))
        signals.append(f"dp.product_id = ANY(${len(params)}::uuid[])")

    where_clauses = [f"({' OR '.join(signals)})"]
    where_clauses.extend(
        build_scope_filters(
            params,
            scope,
            manufacturer_templates=("m.name ILIKE ${index}",),
            product_templates=(
                "COALESCE(p.model_number, '') ILIKE ${index}",
                "COALESCE(p.model_name, '') ILIKE ${index}",
                "COALESCE(ps.series_name, '') ILIKE ${index}",
            ),
            product_id_template="dp.product_id = ${index}::uuid",
            series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
            document_id_template="d.id = ${index}::uuid",
        )
    )

    params.append(limit)
    sql = f"""
        SELECT DISTINCT ON (d.id)
               d.id, d.filename, d.document_type, m.name AS manufacturer_name,
               p.model_number, p.model_name, ps.series_name
        FROM   krai_core.documents d
        LEFT JOIN krai_core.manufacturers m ON d.manufacturer_id = m.id
        LEFT JOIN krai_core.document_products dp ON dp.document_id = d.id
        LEFT JOIN krai_core.products p ON dp.product_id = p.id
        LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
        LEFT JOIN krai_intelligence.chunks ch ON ch.document_id = d.id
        WHERE  {' AND '.join(where_clauses)}
        ORDER  BY d.id, d.updated_at DESC
        LIMIT  ${len(params)}
    """
    rows = await conn.fetch(sql, *params)
    return [_serialize_document_row(row) for row in rows]


def create_tools(
    pool: asyncpg.Pool,
    ollama_base_url: str,
    ai_service=None,  # AIService | None
    reranking_service=None,  # RerankingService | None
) -> list:
    """Create agent tools bound to the shared asyncpg pool."""

    async def _vector_seed(query: str) -> dict:
        """
        Embed query and find the 20 most similar chunks via pgvector.
        Returns chunk_ids, document_ids, product_ids (empty lists if ai_service is None or fails).

        Uses plain ORDER BY + LIMIT (NOT DISTINCT ON) so pgvector evaluates similarity
        globally and returns the true top-20.
        """
        if ai_service is None:
            return {"chunk_ids": [], "document_ids": [], "product_ids": []}
        try:
            embedding = await ai_service.generate_embeddings(query)
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT ch.id AS chunk_id,
                           ch.document_id,
                           dp.product_id
                    FROM   krai_intelligence.chunks ch
                    LEFT JOIN krai_core.document_products dp ON dp.document_id = ch.document_id
                    WHERE  ch.embedding IS NOT NULL
                    ORDER  BY ch.embedding <=> $1::vector
                    LIMIT  20
                    """,
                    embedding,
                )
            return {
                "chunk_ids": [str(r["chunk_id"]) for r in rows],
                "document_ids": list({str(r["document_id"]) for r in rows if r["document_id"]}),
                "product_ids": list({str(r["product_id"]) for r in rows if r["product_id"]}),
            }
        except Exception as e:
            logger.warning("_vector_seed failed, falling back to ILIKE: %s", e)
            return {"chunk_ids": [], "document_ids": [], "product_ids": []}

    @tool
    async def search_error_codes(query: str) -> str:
        """Search error codes and aggregate direct hits with related videos/documents."""

        seed = await _vector_seed(query)
        matched_chunk_ids = seed["chunk_ids"]

        search_term = extract_error_search_term(query)
        variants = build_error_code_variants(search_term)
        scope = _serialize_scope()

        exact_params: list[Any] = []
        exact_code_filters: list[str] = []
        for variant in variants:
            exact_params.append(f"%{variant}%")
            exact_code_filters.append(f"ec.error_code ILIKE ${len(exact_params)}")

        exact_where = ["ec.is_category IS NOT TRUE", f"({' OR '.join(exact_code_filters)})"]
        if matched_chunk_ids:
            exact_params.append(matched_chunk_ids)
            exact_where.append(f"ec.chunk_id = ANY(${len(exact_params)}::uuid[])")
        exact_where.extend(
            build_scope_filters(
                exact_params,
                scope,
                manufacturer_templates=("m.name ILIKE ${index}",),
                product_templates=(
                    "COALESCE(p.model_number, '') ILIKE ${index}",
                    "COALESCE(p.model_name, '') ILIKE ${index}",
                    "COALESCE(ps.series_name, '') ILIKE ${index}",
                ),
                product_id_template="ec.product_id = ${index}::uuid",
                series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                document_id_template="ec.document_id = ${index}::uuid",
            )
        )
        exact_params.append(5)

        base_sql = """
            SELECT DISTINCT ON (ec.id)
                   ec.id, ec.error_code, ec.error_description,
                   ec.solution_customer_text, ec.solution_agent_text, ec.solution_technician_text,
                   COALESCE(ec.solution_technician_text, ec.solution_agent_text, ec.solution_customer_text) AS preferred_solution,
                   ec.page_number, ec.severity_level, ec.confidence_score,
                   ec.document_id, ec.product_id, ec.video_id, ec.chunk_id,
                   m.name AS manufacturer_name,
                   d.filename AS document_filename,
                   p.model_number, p.model_name, ps.series_name
            FROM   krai_intelligence.error_codes ec
            LEFT JOIN krai_core.manufacturers m ON ec.manufacturer_id = m.id
            LEFT JOIN krai_core.documents d ON ec.document_id = d.id
            LEFT JOIN krai_core.products p ON ec.product_id = p.id
            LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
        """

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    {base_sql}
                    WHERE {' AND '.join(exact_where)}
                    ORDER BY ec.id, ec.confidence_score DESC NULLS LAST
                    LIMIT ${len(exact_params)}
                    """,
                    *exact_params,
                )

                if not rows:
                    broad_params: list[Any] = [f"%{search_term}%"]
                    broad_where = [
                        "ec.is_category IS NOT TRUE",
                        "("
                        "ec.error_description ILIKE $1 OR "
                        "COALESCE(ec.solution_customer_text, '') ILIKE $1 OR "
                        "COALESCE(ec.solution_agent_text, '') ILIKE $1 OR "
                        "COALESCE(ec.solution_technician_text, '') ILIKE $1 OR "
                        "COALESCE(ec.context_text, '') ILIKE $1"
                        ")",
                    ]
                    if matched_chunk_ids:
                        broad_params.append(matched_chunk_ids)
                        broad_where.append(f"ec.chunk_id = ANY(${len(broad_params)}::uuid[])")
                    broad_where.extend(
                        build_scope_filters(
                            broad_params,
                            scope,
                            manufacturer_templates=("m.name ILIKE ${index}",),
                            product_templates=(
                                "COALESCE(p.model_number, '') ILIKE ${index}",
                                "COALESCE(p.model_name, '') ILIKE ${index}",
                                "COALESCE(ps.series_name, '') ILIKE ${index}",
                            ),
                            product_id_template="ec.product_id = ${index}::uuid",
                            series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                            document_id_template="ec.document_id = ${index}::uuid",
                        )
                    )
                    broad_params.append(5)

                    rows = await conn.fetch(
                        f"""
                        {base_sql}
                        WHERE {' AND '.join(broad_where)}
                        ORDER BY ec.id, ec.confidence_score DESC NULLS LAST
                        LIMIT ${len(broad_params)}
                        """,
                        *broad_params,
                    )

                if not rows:
                    return json.dumps(
                        {
                            "found": False,
                            "searched_term": search_term,
                            "scope": scope,
                            "message": (
                                f"Fehlercode '{search_term}' wurde im aktuellen Gerätekontext nicht gefunden. "
                                "Bitte Schreibweise prüfen oder den Scope anpassen."
                            ),
                        },
                        ensure_ascii=False,
                    )

                matched_product_ids = [str(row["product_id"]) for row in rows if row["product_id"]]
                matched_document_ids = [str(row["document_id"]) for row in rows if row["document_id"]]
                related_videos = await _fetch_related_videos(
                    conn,
                    search_term,
                    scope,
                    matched_product_ids=matched_product_ids,
                    matched_document_ids=matched_document_ids,
                )
                related_documents = await _fetch_related_documents(
                    conn,
                    search_term,
                    scope,
                    matched_document_ids=matched_document_ids,
                    matched_product_ids=matched_product_ids,
                )

            results = [_serialize_error_code_row(row) for row in rows]
            return json.dumps(
                {
                    "found": True,
                    "searched_term": search_term,
                    "scope": scope,
                    "count": len(results),
                    "error_codes": results,
                    "related_videos": related_videos,
                    "related_documents": related_documents,
                },
                ensure_ascii=False,
            )

        except Exception as exc:
            logger.error("search_error_codes error: %s", exc, exc_info=True)
            return json.dumps({"found": False, "error": str(exc), "scope": scope}, ensure_ascii=False)

    @tool
    async def search_parts(query: str, manufacturer: str | None = None) -> str:
        """Search spare parts for the active machine scope."""

        scope = _serialize_scope()
        params: list[Any] = [f"%{query}%", f"%{query}%", f"%{query}%"]
        where_clauses = [
            "("
            "p.part_number ILIKE $1 OR "
            "COALESCE(p.part_name, '') ILIKE $2 OR "
            "COALESCE(p.description, '') ILIKE $3"
            ")"
        ]

        if manufacturer:
            params.append(f"%{manufacturer}%")
            where_clauses.append(f"m.name ILIKE ${len(params)}")

        where_clauses.extend(
            build_scope_filters(
                params,
                scope,
                manufacturer_templates=("m.name ILIKE ${index}",),
                product_templates=(
                    "COALESCE(pr.model_number, '') ILIKE ${index}",
                    "COALESCE(pr.model_name, '') ILIKE ${index}",
                    "COALESCE(ps.series_name, '') ILIKE ${index}",
                ),
                product_id_template="p.product_id = ${index}::uuid",
                series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
            )
        )
        params.append(10)

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT p.part_number, p.part_name, p.description, p.category, p.price_usd,
                           m.name AS manufacturer_name, pr.model_number, pr.model_name, ps.series_name
                    FROM   krai_parts.parts_catalog p
                    LEFT JOIN krai_core.products pr ON p.product_id = pr.id
                    LEFT JOIN krai_core.product_series ps ON pr.series_id = ps.id
                    LEFT JOIN krai_core.manufacturers m ON pr.manufacturer_id = m.id
                    WHERE  {' AND '.join(where_clauses)}
                    LIMIT  ${len(params)}
                    """,
                    *params,
                )

            if not rows:
                return json.dumps(
                    {"found": False, "scope": scope, "message": f"Keine Ersatzteile für '{query}' gefunden."},
                    ensure_ascii=False,
                )

            results = [_serialize_part_row(row) for row in rows]
            return json.dumps(
                {"found": True, "scope": scope, "count": len(results), "parts": results},
                ensure_ascii=False,
            )

        except Exception as exc:
            logger.error("search_parts error: %s", exc, exc_info=True)
            return json.dumps({"found": False, "error": str(exc), "scope": scope}, ensure_ascii=False)

    @tool
    async def search_videos(query: str) -> str:
        """Search repair videos with machine/product-aware filters."""

        scope = _serialize_scope()
        seed = await _vector_seed(query)
        try:
            async with pool.acquire() as conn:
                videos = await _fetch_related_videos(
                    conn,
                    query,
                    scope,
                    matched_document_ids=seed["document_ids"],
                    matched_product_ids=seed["product_ids"],
                    limit=10,
                )

            if not videos:
                return json.dumps(
                    {"found": False, "scope": scope, "message": f"Keine Videos für '{query}' gefunden."},
                    ensure_ascii=False,
                )

            return json.dumps(
                {"found": True, "scope": scope, "count": len(videos), "videos": videos},
                ensure_ascii=False,
            )

        except Exception as exc:
            logger.error("search_videos error: %s", exc, exc_info=True)
            return json.dumps({"found": False, "error": str(exc), "scope": scope}, ensure_ascii=False)

    @tool
    async def semantic_search(query: str, limit: int = 5) -> str:
        """Semantic search over chunks, scoped to the active machine context when available."""

        scope = _serialize_scope()
        try:
            embed_model = os.getenv("OLLAMA_MODEL_EMBED", "nomic-embed-text")
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{ollama_base_url}/api/embeddings",
                    json={"model": embed_model, "prompt": query},
                )

            if resp.status_code != 200:
                return json.dumps({"found": False, "error": f"Embedding failed: {resp.text}"}, ensure_ascii=False)

            query_embedding = resp.json()["embedding"]
            params: list[Any] = [query_embedding]
            scope_clauses = build_scope_filters(
                params,
                scope,
                manufacturer_templates=("m.name ILIKE ${index}",),
                product_templates=(
                    "COALESCE(p.model_number, '') ILIKE ${index}",
                    "COALESCE(p.model_name, '') ILIKE ${index}",
                    "COALESCE(ps.series_name, '') ILIKE ${index}",
                ),
                product_id_template="dp.product_id = ${index}::uuid",
                series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                document_id_template="d.id = ${index}::uuid",
            )

            where_clauses = ["ch.embedding IS NOT NULL", *scope_clauses]
            params.append(limit)

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT * FROM (
                        SELECT DISTINCT ON (ch.id)
                               ch.text_chunk AS content,
                               ch.metadata,
                               ch.document_id,
                               ch.id AS chunk_id,
                               d.filename AS document_filename,
                               m.name AS manufacturer_name,
                               p.model_number,
                               p.model_name,
                               ps.series_name,
                               1 - (ch.embedding <=> $1::vector) AS similarity
                        FROM   krai_intelligence.chunks ch
                        LEFT JOIN krai_core.documents d ON ch.document_id = d.id
                        LEFT JOIN krai_core.document_products dp ON dp.document_id = d.id
                        LEFT JOIN krai_core.products p ON dp.product_id = p.id
                        LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
                        LEFT JOIN krai_core.manufacturers m ON COALESCE(p.manufacturer_id, d.manufacturer_id) = m.id
                        WHERE  {' AND '.join(where_clauses)}
                        ORDER  BY ch.id, ch.embedding <=> $1::vector
                    ) ranked
                    ORDER BY similarity DESC
                    LIMIT ${len(params)}
                    """,
                    *params,
                )

            # Rerank results using index-based reconstruction (handles duplicate content correctly)
            if rows and reranking_service and reranking_service.enabled:
                texts = [row["content"] for row in rows]
                top_texts = reranking_service.rerank(query, texts)
                used_indices: set = set()
                reranked_rows = []
                for text in top_texts:
                    for i, candidate in enumerate(texts):
                        if i not in used_indices and candidate == text:
                            reranked_rows.append(rows[i])
                            used_indices.add(i)
                            break
                rows = reranked_rows

            if not rows:
                return json.dumps(
                    {"found": False, "scope": scope, "message": f"Keine relevanten Inhalte für '{query}' gefunden."},
                    ensure_ascii=False,
                )

            results = [
                {
                    "content": row["content"],
                    "similarity": round(float(row["similarity"]), 4),
                    "metadata": dict(row["metadata"]) if row["metadata"] else {},
                    "document_id": str(row["document_id"]),
                    "chunk_id": str(row["chunk_id"]),
                    "document": row["document_filename"],
                    "manufacturer": row["manufacturer_name"],
                    "product": _coalesce_product_label(row),
                    "series": row["series_name"],
                }
                for row in rows
            ]
            return json.dumps(
                {"found": True, "scope": scope, "count": len(results), "results": results},
                ensure_ascii=False,
            )

        except Exception as exc:
            logger.error("semantic_search error: %s", exc, exc_info=True)
            return json.dumps({"found": False, "error": str(exc), "scope": scope}, ensure_ascii=False)

    return [search_error_codes, search_parts, search_videos, semantic_search]


_SYSTEM_PROMPT = SystemMessage(
    content="""Du bist **KRAI** – der KI-Assistent für Drucker- und Kopierer-Servicetechniker.
Du hast Zugriff auf eine Datenbank mit Fehlercodes, Ersatzteilen, Videos und Servicehandbüchern.

## Deine Tools
- **search_error_codes**: Fehlercode suchen und direkte DB-Treffer mit relevanten Videos/Dokumenten bündeln
- **search_parts**: Ersatzteil nach Nummer oder Name suchen
- **search_videos**: Tutorial-Video nach Gerät, Fehler oder Arbeitsschritt suchen
- **semantic_search**: Freitextsuche in Servicehandbüchern für komplexe oder beschreibende Fragen

## Regeln
1. **Immer zuerst das passende Tool nutzen** – nie aus dem Gedächtnis über Fehlercodes oder Teile antworten.
2. **Nur zurückgeben was Tools liefern** – keine Lösungen, Teilenummern oder URLs erfinden.
3. Wenn ein Scope aktiv ist, **nutze ihn automatisch** und erwähne kurz, dass die Antwort auf dieses Gerät eingegrenzt wurde.
4. Bei Fehlercodes zuerst **search_error_codes** verwenden. Wenn dort nichts gefunden wird, direkt **semantic_search** mit dem gleichen Begriff ausführen.
5. Wenn der Nutzer nach Videos, Bulletins oder weiteren Quellen fragt, nutze die gelieferten **related_videos** und **related_documents** aus der Fehlercode-Suche oder rufe zusätzlich **search_videos** auf.
6. Wenn der Nutzer noch kein Gerät eingegrenzt hat und die Frage mehrdeutig ist, weise kurz darauf hin, dass Hersteller/Modell die Trefferqualität verbessert.
7. Antworte immer auf **Deutsch** und nutze **Markdown**.
"""
)


class KRAIAgent:
    """KRAI conversational agent using LangGraph create_react_agent."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        ollama_base_url: str | None = None,
        ai_service=None,  # AIService | None
        reranking_service=None,  # RerankingService | None
    ) -> None:
        if ollama_base_url is None:
            ollama_base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        self.ai_service = ai_service
        self.reranking_service = reranking_service
        self.logger = logging.getLogger(__name__)
        self._session_scopes: dict[str, dict[str, str]] = {}

        llm_backend = os.getenv("LLM_BACKEND", "ollama").lower()
        if llm_backend in {"openai", "openrouter"}:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "LLM_BACKEND=openai/openrouter requires langchain-openai. Install it with `pip install langchain-openai`."
                ) from exc

            if llm_backend == "openrouter":
                openrouter_model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
                openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
                openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                extra_headers = {}
                if os.getenv("OPENROUTER_SITE_URL"):
                    extra_headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL")
                if os.getenv("OPENROUTER_APP_NAME"):
                    extra_headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME")

                self.logger.info("Using OpenRouter backend, model: %s", openrouter_model)
                llm = ChatOpenAI(
                    model=openrouter_model,
                    api_key=openrouter_api_key,
                    base_url=openrouter_base_url,
                    temperature=0.0,
                    default_headers=extra_headers or None,
                )
            else:
                openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
                openai_base_url = os.getenv("OPENAI_BASE_URL")
                self.logger.info("Using OpenAI backend, model: %s", openai_model)
                llm = ChatOpenAI(
                    model=openai_model,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=openai_base_url,
                    temperature=0.0,
                )
        else:
            ollama_model = os.getenv("OLLAMA_MODEL_CHAT") or os.getenv("OLLAMA_MODEL_TEXT", "llama3.2:latest")
            self.logger.info("Connecting to Ollama at %s, model: %s", ollama_base_url, ollama_model)
            llm = ChatOllama(
                model=ollama_model,
                base_url=ollama_base_url,
                temperature=0.0,
                num_ctx=16384,
            )

        self.agent = create_react_agent(
            model=llm,
            tools=create_tools(
                pool,
                ollama_base_url,
                ai_service=self.ai_service,
                reranking_service=self.reranking_service,
            ),
            checkpointer=MemorySaver(),
            prompt=_SYSTEM_PROMPT,
        )
        self.logger.info("KRAI Agent initialized successfully")

    def _resolve_scope(
        self,
        session_id: str,
        scope: AgentScope | None = None,
        *,
        reset_scope: bool = False,
    ) -> dict[str, str]:
        effective_scope = merge_scope(self._session_scopes.get(session_id), scope, reset=reset_scope)
        if effective_scope:
            self._session_scopes[session_id] = effective_scope
        else:
            self._session_scopes.pop(session_id, None)
        return effective_scope

    def resolve_session_scope(
        self,
        session_id: str,
        scope: AgentScope | None = None,
        *,
        reset_scope: bool = False,
    ) -> dict[str, str]:
        """Public helper to get or update the stored scope for a session."""

        return self._resolve_scope(session_id, scope, reset_scope=reset_scope)

    async def chat(
        self,
        message: str | list,
        session_id: str,
        scope: AgentScope | None = None,
        *,
        reset_scope: bool = False,
    ) -> tuple[str, dict[str, str]]:
        """Process a message and return the response plus the active scope."""

        active_scope = self._resolve_scope(session_id, scope, reset_scope=reset_scope)
        config = {"configurable": {"thread_id": session_id}}
        token = CURRENT_AGENT_SCOPE.set(active_scope or None)

        messages: list[Any] = [HumanMessage(content=message)]
        scope_message = build_scope_system_message(active_scope)
        if scope_message:
            messages.insert(0, SystemMessage(content=scope_message))

        try:
            result = await self.agent.ainvoke({"messages": messages}, config=config)
            response: str = result["messages"][-1].content
            self.logger.info("Agent response (session=%s): %.120s", session_id, response)
            return response, active_scope
        except Exception as exc:
            self.logger.error("chat error: %s", exc, exc_info=True)
            return f"Es ist ein Fehler aufgetreten: {exc}", active_scope
        finally:
            CURRENT_AGENT_SCOPE.reset(token)

    async def chat_stream(
        self,
        message: str | list,
        session_id: str,
        scope: AgentScope | None = None,
        *,
        reset_scope: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Process a message and stream the response token by token."""

        active_scope = self._resolve_scope(session_id, scope, reset_scope=reset_scope)
        config = {"configurable": {"thread_id": session_id}}
        token = CURRENT_AGENT_SCOPE.set(active_scope or None)

        messages: list[Any] = [HumanMessage(content=message)]
        scope_message = build_scope_system_message(active_scope)
        if scope_message:
            messages.insert(0, SystemMessage(content=scope_message))

        try:
            async for chunk, metadata in self.agent.astream(
                {"messages": messages},
                config=config,
                stream_mode="messages",
            ):
                if hasattr(chunk, "content") and chunk.content and metadata.get("langgraph_node") == "agent":
                    yield chunk.content
        except Exception as exc:
            self.logger.error("chat_stream error: %s", exc, exc_info=True)
            yield f"Es ist ein Fehler aufgetreten: {exc}"
        finally:
            CURRENT_AGENT_SCOPE.reset(token)


def create_agent_api(pool: asyncpg.Pool, agent: KRAIAgent | None = None) -> APIRouter:
    """Create and return the FastAPI router for the KRAI agent."""

    router = APIRouter(prefix="/agent", tags=["AI Agent"])
    if agent is None:
        agent = KRAIAgent(pool)

    @router.post("/chat", response_model=ChatResponse)
    async def chat(
        message: ChatMessage,
        current_user: dict = Depends(require_permission("agent:chat")),
    ) -> ChatResponse:
        try:
            response, active_scope = await agent.chat(
                message.message,
                message.session_id,
                message.scope,
                reset_scope=message.reset_scope,
            )
            return ChatResponse(
                response=response,
                session_id=message.session_id,
                timestamp=datetime.utcnow().isoformat(),
                active_scope=AgentScope(**active_scope) if active_scope else None,
            )
        except Exception as exc:
            logger.error("chat endpoint error: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post("/chat/stream")
    async def chat_stream(
        message: ChatMessage,
        current_user: dict = Depends(require_permission("agent:chat")),
    ) -> StreamingResponse:
        async def generate() -> AsyncGenerator[str, None]:
            async for chunk in agent.chat_stream(
                message.message,
                message.session_id,
                message.scope,
                reset_scope=message.reset_scope,
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "agent": "KRAI AI Agent", "version": "2.1.0"}

    return router


async def get_agent_api() -> APIRouter:
    """Compatibility helper for direct startup wiring."""

    pool = await get_pool()
    return create_agent_api(pool)
