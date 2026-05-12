"""
OpenAI-Compatible API Wrapper for KRAI
=======================================
Exposes ``/v1/chat/completions`` and ``/v1/models`` so that OpenWebUI
(or any OpenAI client) can talk to the KRAI agent without modification.

Fast-Path (no LLM needed):
  Exact error-code patterns (e.g. 99.00.02, C-2801, SC542) are detected in
  the user message and resolved directly via a SQL query — response in < 50 ms.
  Only open-ended / conversational messages go through the LangGraph agent.

Supported backends (env LLM_BACKEND):
  ollama  — local Ollama (default, model via OLLAMA_MODEL_CHAT)
  openai  — OpenAI API  (model via OPENAI_MODEL, key via OPENAI_API_KEY)
  openrouter — OpenRouter API (model via OPENROUTER_MODEL, key via OPENROUTER_API_KEY)

Vision / Image Analysis
  When the request contains image_url content parts the images are forwarded
  directly to the LLM (llava on Ollama, gpt-4o on OpenAI).  The KRAI agent
  then uses its tools to enrich the response with DB lookups.

Session Management
  OpenWebUI sends the full message history on every request.  We derive a
  stable session_id from the content of the first user message so that
  LangGraph's MemorySaver maintains continuity across turns.
  Callers may also pass a custom session id via the ``user`` field.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.agent_scope import AgentScope, build_scope_filters, extract_scope_from_openai_payload, normalize_scope
from api.middleware.auth_middleware import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible"])

# Public base URL for MinIO image bucket — used to rewrite internal storage URLs.
# Set OBJECT_STORAGE_PUBLIC_URL_IMAGES in .env, e.g.:
#   http://localhost:9000/images          (local)
#   https://minio.example.com/images     (production)
# Falls back to OBJECT_STORAGE_PUBLIC_URL (without bucket path) if not set.
_MINIO_IMAGES_PUBLIC = (
    os.getenv("OBJECT_STORAGE_PUBLIC_URL_IMAGES") or os.getenv("OBJECT_STORAGE_PUBLIC_URL", "")
).rstrip("/")
_MINIO_DOCUMENTS_PUBLIC = (
    os.getenv("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS") or os.getenv("OBJECT_STORAGE_PUBLIC_URL", "")
).rstrip("/")


def _rewrite_storage_url(url: str) -> str:
    """Replace the internal MinIO host:port with the configured public URL.

    This lets the same DB data work locally (127.0.0.1:9000) and in
    production (https://minio.example.com) without re-processing images.
    The path portion (/images/<hash>) is always preserved.
    """
    if not _MINIO_IMAGES_PUBLIC or not url:
        return url
    parsed = urlparse(url)
    internal_origin = f"{parsed.scheme}://{parsed.netloc}"
    public_origin = urlparse(_MINIO_IMAGES_PUBLIC).scheme + "://" + urlparse(_MINIO_IMAGES_PUBLIC).netloc
    return url.replace(internal_origin, public_origin, 1)


def _rewrite_document_url(url: str | None) -> str | None:
    """Rewrite document URLs to the configured public documents origin."""
    if not _MINIO_DOCUMENTS_PUBLIC or not url:
        return url
    parsed = urlparse(url)
    internal_origin = f"{parsed.scheme}://{parsed.netloc}"
    public_origin = urlparse(_MINIO_DOCUMENTS_PUBLIC).scheme + "://" + urlparse(_MINIO_DOCUMENTS_PUBLIC).netloc
    return url.replace(internal_origin, public_origin, 1)


# ---------------------------------------------------------------------------
# Pydantic models (OpenAI request/response format)
# ---------------------------------------------------------------------------


class ImageUrl(BaseModel):
    url: str  # "data:image/jpeg;base64,..." or https URL


class ContentPart(BaseModel):
    type: str  # "text" | "image_url"
    text: str | None = None
    image_url: ImageUrl | None = None


class OAIMessage(BaseModel):
    role: str  # system | user | assistant
    content: str | list[ContentPart]


class ChatCompletionRequest(BaseModel):
    model: str = "krai"
    messages: list[OAIMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None  # treated as session_id hint when set
    metadata: dict[str, Any] | None = None
    scope: AgentScope | None = None
    reset_scope: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_id(messages: list[OAIMessage], user: str | None) -> str:
    """Return a stable session identifier for this conversation thread.

    Priority: explicit ``user`` field → hash of first user message content.
    """
    if user:
        return user[:64]
    for msg in messages:
        if msg.role == "user":
            text = (
                msg.content if isinstance(msg.content, str) else json.dumps([p.model_dump() for p in msg.content])  # type: ignore[union-attr]
            )
            return "oai_" + hashlib.sha256(text.encode()).hexdigest()[:32]
    return "oai_" + uuid.uuid4().hex


def _extract_last_user_content(
    messages: list[OAIMessage],
) -> tuple[str | list, list[str]]:
    """Extract text and image URLs from the last user message.

    Returns ``(content, image_urls)`` where *content* is either a plain
    string or a list of OpenAI-style content dicts when images are present.
    """
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        if isinstance(msg.content, str):
            return msg.content, []
        text_parts: list[str] = []
        image_urls: list[str] = []
        for part in msg.content:
            if part.type == "text" and part.text:
                text_parts.append(part.text)
            elif part.type == "image_url" and part.image_url:
                image_urls.append(part.image_url.url)
        if image_urls:
            # Build multi-modal content list for the LLM
            content: list = [{"type": "text", "text": " ".join(text_parts)}]
            content += [{"type": "image_url", "image_url": {"url": url}} for url in image_urls]
            return content, image_urls
        return " ".join(text_parts), []
    return "", []


def _make_response(content: str, model: str, krai_context: dict[str, Any] | None = None) -> dict:
    """Build a non-streaming OpenAI chat.completion response object."""
    response = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    if krai_context is not None:
        response["krai_context"] = krai_context
    return response


def _product_label(row) -> str | None:
    parts = [row.get("model_name"), row.get("model_number")]
    value = " ".join(part for part in parts if part).strip()
    return value or None


def _scope_label(scope: dict[str, str]) -> str:
    bits = []
    if scope.get("manufacturer"):
        bits.append(scope["manufacturer"])
    if scope.get("product"):
        bits.append(scope["product"])
    elif scope.get("series"):
        bits.append(scope["series"])
    return " / ".join(bits)


def _serialize_krai_row(row) -> dict[str, Any]:
    return {
        "manufacturer": row.get("manufacturer_name"),
        "product": _product_label(row),
        "series": row.get("series_name"),
    }


def _model_match_score(row, raw_model: str | None) -> int:
    if not raw_model:
        return 0
    raw_model_lower = raw_model.lower()
    score = 0
    for value in (
        row.get("model_number"),
        row.get("model_name"),
        row.get("series_name"),
        row.get("document_filename"),
        row.get("filename"),
    ):
        if value and raw_model_lower in str(value).lower():
            score += 50
    return score


def _strip_hp_family_lines(text: str, error_code: str) -> str:
    if not text:
        return text
    upper_code = error_code.upper()
    if not re.match(r"^\d{2}\.[A-Z]\d(?:\.[A-Z0-9]{2})?$", upper_code):
        return text

    parts = upper_code.split(".")
    family_stem = f"{parts[0]}.{parts[1][0]}" if len(parts) >= 2 and parts[1] else None
    filtered_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        upper_line = stripped.upper()
        if not stripped:
            filtered_lines.append(line)
            continue
        if family_stem and upper_line.startswith(f"{family_stem}X."):
            continue
        if family_stem and upper_line.startswith(f"{family_stem}") and upper_code not in upper_line:
            continue
        if upper_line in {
            "RESIDUAL PAPER JAM IN TRAY X. ( X = TRAY 2, 3, OR 4 )",
            "THIS JAM OCCURS WHEN RESIDUAL PAPER IS DETECTED AT THE TRAY X FEED SENSOR.",
        }:
            continue
        filtered_lines.append(line)

    cleaned = "\n".join(filtered_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _contains_video_term(text: str, term: str) -> bool:
    words = re.findall(r"\w+", term.lower())
    normalized = text.lower()
    return bool(words) and all(word in normalized for word in words)


def _detect_query_manufacturer(text: str, scope: dict[str, str] | None = None) -> str | None:
    manufacturer = (scope or {}).get("manufacturer")
    if manufacturer:
        return manufacturer
    manufacturer_patterns = (
        (r"\b(hp|hewlett[\s\-]?packard)\b", "HP"),
        (r"\blexmark\b", "Lexmark"),
        (r"\bkonica\s+minolta\b", "Konica Minolta"),
        (r"\bricoh\b", "Ricoh"),
        (r"\bxerox\b", "Xerox"),
        (r"\bkyocera\b", "Kyocera"),
        (r"\bcanon\b", "Canon"),
        (r"\bbrother\b", "Brother"),
        (r"\bsharp\b", "Sharp"),
        (r"\btoshiba\b", "Toshiba"),
        (r"\bepson\b", "Epson"),
        (r"\boki\b", "OKI"),
        (r"\bfujifilm\b", "Fujifilm"),
        (r"\briso\b", "Riso"),
    )
    for pattern, label in manufacturer_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _video_row_relevance(
    row,
    search_terms: list[str],
    *,
    issue_terms: list[str] | None = None,
    expansion_terms: list[str] | None = None,
) -> int:
    title_text = (row.get("title") or "").lower()
    description_text = " ".join(
        part.lower()
        for part in (
            row.get("description") or "",
            row.get("channel_title") or "",
        )
        if part
    )
    product_text = " ".join(
        part.lower()
        for part in (
            row.get("model_number") or "",
            row.get("model_name") or "",
            row.get("series_name") or "",
        )
        if part
    )
    combined_text = " ".join(part for part in (title_text, description_text, product_text) if part)

    score = 0
    for term in search_terms:
        if _contains_video_term(product_text, term):
            score += 40
        elif _contains_video_term(title_text, term):
            score += 30
        elif _contains_video_term(combined_text, term):
            score += 15

    if search_terms and all(_contains_video_term(combined_text, term) for term in search_terms):
        score += 30
    if search_terms and all(_contains_video_term(title_text, term) for term in search_terms):
        score += 20

    issue_terms = issue_terms or []
    issue_matches = sum(1 for term in issue_terms if _contains_video_term(combined_text, term))
    title_issue_matches = sum(1 for term in issue_terms if _contains_video_term(title_text, term))
    score += issue_matches * 25
    score += title_issue_matches * 15
    if issue_terms and issue_matches == 0:
        score -= 25

    expansion_terms = expansion_terms or []
    score += sum(1 for term in expansion_terms if _contains_video_term(combined_text, term)) * 12
    score += sum(1 for term in expansion_terms if _contains_video_term(title_text, term)) * 8

    return score


def _build_video_search_plan(text: str, scope: dict[str, str] | None = None) -> dict[str, Any]:
    model_match = _MODEL_RE.search(text)
    tray_match = re.search(r"\btray\s*\d+\b", text, re.IGNORECASE)
    jam_match = re.search(r"\b(paper\s+jam|jam|stau)\b", text, re.IGNORECASE)
    manufacturer = _detect_query_manufacturer(text, scope)

    issue_terms: list[str] = []
    if tray_match and jam_match:
        issue_terms.append(f"{tray_match.group(0)} {jam_match.group(0)}")
    if tray_match:
        issue_terms.append(tray_match.group(0))
    if jam_match:
        issue_terms.append(jam_match.group(0))

    expansion_terms: list[str] = []
    tray_number_match = re.search(r"(\d+)", tray_match.group(0)) if tray_match else None
    tray_number = tray_number_match.group(1) if tray_number_match else None
    if manufacturer and manufacturer.lower().startswith("hp") and jam_match:
        expansion_terms.append("paper jam")
        if tray_number == "4":
            expansion_terms.extend(["13.A4", "HCI", "cassette"])

    if model_match and issue_terms:
        search_term_sets = [
            [model_match.group(0), issue_terms[0]],
            [model_match.group(0)] + issue_terms[1:],
            [model_match.group(0)],
            [issue_terms[0]],
        ]
    elif model_match:
        search_term_sets = [[model_match.group(0)]]
    elif issue_terms:
        search_term_sets = [[issue_terms[0]]]
    else:
        tokens = [
            token for token in re.findall(r"\b\w[\w\-\.]{2,}\b", text) if token.lower() not in _VIDEO_QUERY_STOPWORDS
        ]
        manufacturer_tokens = {token.lower() for token in re.findall(r"\w+", manufacturer or "")}
        ranked_tokens = sorted(
            dict.fromkeys(token for token in tokens if token.lower() not in manufacturer_tokens),
            key=lambda token: (
                0 if _PARTS_KEYWORDS.search(token) else 1,
                -len(token),
                token.lower(),
            ),
        )
        if ranked_tokens:
            search_term_sets = []
            if manufacturer:
                search_term_sets.append([manufacturer, ranked_tokens[0]])
            search_term_sets.append([ranked_tokens[0]])
            if len(ranked_tokens) > 1:
                if manufacturer:
                    search_term_sets.append([manufacturer, ranked_tokens[1]])
                search_term_sets.append([ranked_tokens[1]])
            if manufacturer:
                search_term_sets.append([manufacturer])
        else:
            fallback_term = manufacturer or text[:40]
            search_term_sets = [[fallback_term]]

    if model_match:
        for expansion_term in expansion_terms:
            search_term_sets.append([model_match.group(0), expansion_term])
    else:
        for expansion_term in expansion_terms:
            search_term_sets.append([expansion_term])

    deduped_term_sets: list[list[str]] = []
    seen_term_sets: set[tuple[str, ...]] = set()
    for term_set in search_term_sets:
        normalized = tuple(dict.fromkeys(term_set))
        if normalized and normalized not in seen_term_sets:
            seen_term_sets.add(normalized)
            deduped_term_sets.append(list(normalized))

    return {
        "manufacturer": manufacturer,
        "model": model_match.group(0) if model_match else None,
        "issue_terms": issue_terms,
        "expansion_terms": expansion_terms,
        "search_term_sets": deduped_term_sets,
    }


def _serialize_video_match(row, *, score: int | None = None) -> dict[str, Any]:
    payload = {
        "title": row["title"],
        "url": row["video_url"],
        "description": row["description"],
        "duration": row["duration"],
        "channel_title": row["channel_title"],
        **_serialize_krai_row(row),
    }
    if score is not None:
        payload["score"] = score
    return payload


def _serialize_document_match(row) -> dict[str, Any]:
    return {
        "filename": row["filename"],
        "document_type": row["document_type"],
        "storage_url": _rewrite_document_url(row.get("storage_url")),
        **_serialize_krai_row(row),
    }


def _has_explicit_error_intent(text: str) -> bool:
    """Return True when the user is clearly asking about an error/event code."""

    return bool(
        re.search(
            r"\b(fehler|error(?:\s*code)?|event\s*code|warn(?:ung|code)?|störung|fault\s*code)\b",
            text,
            re.IGNORECASE,
        )
    )


def _prefer_keyword_route(text: str) -> str | None:
    """Prefer parts/video routing over error-code routing for ambiguous model-like terms."""

    if _has_explicit_error_intent(text):
        return None
    if _VIDEO_KEYWORDS.search(text):
        return "video"
    if _PARTS_KEYWORDS.search(text):
        return "parts"
    return None


_SEMANTIC_INTENT_PATTERNS = (
    re.compile(r"\b(was bedeutet|erkl[äa]r(?:e|ung)?|bedeutung|ursache|l[öo]sung|hilfe)\b", re.IGNORECASE),
    re.compile(r"\b(suche|finde|zeige|gib mir|welche[srn]?|passende[nrs]?|relevante[nrs]?)\b", re.IGNORECASE),
    re.compile(r"\b(dokument|handbuch|manual|service manual|cpmd|bulletin|quelle|quellen)\b", re.IGNORECASE),
    re.compile(r"\b(fehler|fehlercode|stau|jam|paper jam|problem|st[öo]rung)\b", re.IGNORECASE),
)


def _should_use_semantic_fast_path(text: str) -> bool:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    if _ERROR_CODE_RE.search(normalized):
        return True
    if _prefer_keyword_route(normalized) is not None:
        return True
    return any(pattern.search(normalized) for pattern in _SEMANTIC_INTENT_PATTERNS)


def _is_meaningful_response_image(row) -> bool:
    """Filter decorative or redundant text/table images from responses."""

    width = row.get("width_px") or 0
    height = row.get("height_px") or 0
    file_size = row.get("file_size") or 0
    image_type = (row.get("image_type") or "").lower()
    contains_text = bool(row.get("contains_text"))
    ocr_text = (row.get("ocr_text") or "").strip()

    if width and height and width * height < 20_000:
        return False
    if file_size and file_size < 2_000:
        return False
    if image_type == "table":
        return False
    return not (
        contains_text and len(ocr_text) > 40 and image_type not in {"diagram", "photo", "schematic", "flowchart"}
    )


async def _find_related_videos(
    conn,
    query: str,
    scope: dict[str, str],
    *,
    matched_product_ids: list[str] | None = None,
    matched_document_ids: list[str] | None = None,
    limit: int = 3,
):
    params: list[object] = [f"%{query}%"]
    where_clauses = [
        "("
        "v.title ILIKE $1 OR "
        "COALESCE(v.description, '') ILIKE $1 OR "
        "COALESCE(v.context_description, '') ILIKE $1 OR "
        "COALESCE(p.model_number, '') ILIKE $1 OR "
        "COALESCE(p.model_name, '') ILIKE $1 OR "
        "COALESCE(ps.series_name, '') ILIKE $1"
        ")"
    ]

    if matched_product_ids:
        params.append(matched_product_ids)
        where_clauses.append(f"vp.product_id = ANY(${len(params)}::uuid[])")

    if matched_document_ids:
        params.append(matched_document_ids)
        where_clauses.append(f"v.document_id = ANY(${len(params)}::uuid[])")

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
            product_id_template="vp.product_id = ${index}::uuid",
            series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
            document_id_template="v.document_id = ${index}::uuid",
        )
    )
    params.append(limit)

    return await conn.fetch(
        f"""
        {_VIDEO_BASE_SQL}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY v.id, v.published_at DESC NULLS LAST
        LIMIT ${len(params)}
        """,
        *params,
    )


async def _find_related_documents(
    conn,
    query: str,
    scope: dict[str, str],
    *,
    matched_product_ids: list[str] | None = None,
    exclude_document_ids: list[str] | None = None,
    limit: int = 4,
):
    params: list[object] = [f"%{query}%"]
    where_clauses = [
        "("
        "d.filename ILIKE $1 OR "
        "COALESCE(d.document_type, '') ILIKE $1 OR "
        "COALESCE(ch.text_chunk, '') ILIKE $1 OR "
        "COALESCE(p.model_number, '') ILIKE $1 OR "
        "COALESCE(p.model_name, '') ILIKE $1 OR "
        "COALESCE(ps.series_name, '') ILIKE $1"
        ")"
    ]

    if matched_product_ids:
        params.append(matched_product_ids)
        where_clauses.append(f"dp.product_id = ANY(${len(params)}::uuid[])")

    if exclude_document_ids:
        params.append(exclude_document_ids)
        where_clauses.append(f"NOT (d.id = ANY(${len(params)}::uuid[]))")

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

    return await conn.fetch(
        f"""
        {_RELATED_DOCUMENTS_BASE_SQL}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY d.id, d.updated_at DESC
        LIMIT ${len(params)}
        """,
        *params,
    )


async def _sse_stream(
    token_gen: AsyncGenerator[str, None],
    model: str,
) -> AsyncGenerator[str, None]:
    """Wrap a KRAI token generator as OpenAI-format Server-Sent Events."""
    cmpl_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    async for chunk in token_gen:
        payload = {
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(payload)}\n\n"
    # Final chunk
    payload = {
        "id": cmpl_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(payload)}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Fast-path: direct DB lookup for error codes (no LLM required)
# ---------------------------------------------------------------------------

# Matches: 99.00.02 / 50.FF.02 / C-2801 / C2801 / SC542 / 541-011 / E001
_ERROR_CODE_RE = re.compile(
    r"\b([A-Z0-9]{1,4}(?:[.\-][A-Z0-9]{1,4}){1,5})\b"  # dotted/dashed: 99.00.02, 50.FF.02, C-2801
    r"|\b([A-Z]{1,3}[-]?\d{3,6})\b",  # alpha+digits:  SC542, C9402, E001
    re.IGNORECASE,
)

# HP/Konica/Ricoh model patterns: M507, E50045, MFP 8601, bizhub 308, Aficio MP201
_MODEL_RE = re.compile(
    r"\b(E\d{3,6}|M\d{3,4}|P\d{4,6}|bizhub\s*\d{3,4}|Aficio\s*\w+|"
    r"MFP\s*\d{4,5}|MP\s*\d{3,4}|C\d{3,4}(?:dn|dw|n)?|LaserJet\s*\w+|"
    r"\w+[-]\d{3,5}(?:dn|dw|n|i|f)?)\b",
    re.IGNORECASE,
)

_FAST_PATH_BASE_SQL = """
    SELECT DISTINCT ON (ec.id)
           ec.error_code, ec.error_description,
           ec.solution_customer_text, ec.solution_agent_text, ec.solution_technician_text,
           ec.page_number, ec.severity_level, ec.confidence_score,
           m.name AS manufacturer_name,
           d.filename AS document_filename,
           p.model_number, p.model_name, ps.series_name,
           ec.document_id AS document_id,
           dp.product_id AS product_id
    FROM   krai_intelligence.error_codes ec
    LEFT JOIN krai_core.manufacturers m ON ec.manufacturer_id = m.id
    LEFT JOIN krai_core.documents d ON ec.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON dp.document_id = d.id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
"""

# Fallback: search chunks when all 3 solution columns are still NULL.
# NOTE: Only ASCII-safe ILIKE patterns — asyncpg can misparse non-ASCII string literals.
_CHUNK_SOLUTION_SQL = """
    SELECT c.text_chunk, d.filename, c.page_start
    FROM   krai_intelligence.chunks c
    JOIN   krai_core.documents d ON c.document_id = d.id
    WHERE  c.text_chunk ILIKE $1
      AND  c.text_chunk ILIKE $2
    ORDER  BY c.page_start
    LIMIT  3
"""

# Non-HP variant: skip early TOC/index pages (page_start > 20) so
# we hit the actual content section, not the table-of-contents.
_CHUNK_DESC_FALLBACK_SQL = """
    SELECT c.text_chunk, d.filename, c.page_start
    FROM   krai_intelligence.chunks c
    JOIN   krai_core.documents d ON c.document_id = d.id
    WHERE  c.text_chunk ILIKE $1
      AND  c.page_start > 20
    ORDER  BY c.page_start
    LIMIT  5
"""

# Full solution: fetch the chunk containing the error code PLUS all consecutive
# chunks from the same document on the same and immediately following pages.
# Uses DISTINCT ON to deduplicate chunks from multiple processing runs.
_FULL_SOLUTION_SQL = """
    WITH code_chunk AS (
        SELECT c.id, c.document_id, c.page_start,
               -- Whether this chunk has a real solution header (not just a code-table row)
               -- prio=0: HP-style "Recommended action" header
               -- prio=1: HP alt header or Kyocera procedure table (contains "Measures" column)
               -- prio=2: bare code-table row (only the code + description, no procedure)
               CASE WHEN c.text_chunk ILIKE '%Recommended action%' THEN 0
                    WHEN c.text_chunk ILIKE '%Follow these troubleshooting%' THEN 1
                    WHEN c.text_chunk ILIKE '%Measures%' THEN 1
                    ELSE 2 END AS prio
        FROM   krai_intelligence.chunks c
        JOIN   krai_core.documents d ON c.document_id = d.id
        WHERE  d.filename = $1
          AND  c.text_chunk ILIKE $2
          AND  c.page_start > 20
        ORDER  BY prio,
                  -- Secondary sort: among same-prio "Measures" chunks, prefer the one
                  -- where the target code appears closest to "Measures" in the text.
                  -- This avoids picking self-diagnostic table chunks where many unrelated
                  -- codes appear between the target code and the Measures header.
                  -- Note: PostgreSQL does not resolve SELECT aliases inside CASE expressions
                  -- in ORDER BY, so the prio CASE is repeated here.
                  CASE WHEN c.text_chunk ILIKE '%Measures%'
                            AND c.text_chunk NOT ILIKE '%Recommended action%'
                            AND c.text_chunk NOT ILIKE '%Follow these troubleshooting%' THEN
                       ABS(POSITION(UPPER(TRIM('%' FROM $2)) IN UPPER(c.text_chunk))
                           - POSITION('MEASURES' IN UPPER(c.text_chunk)))
                  ELSE 0 END ASC,
                  c.page_start
        LIMIT  1
    ),
    -- When anchor chunk is a bare table row (prio=2), limit the page window tightly
    -- so we don't drag in unrelated procedures from 20+ pages away.
    deduped AS (
        SELECT DISTINCT ON (c.text_chunk) c.text_chunk, c.page_start
        FROM   krai_intelligence.chunks c
        JOIN   code_chunk cc ON c.document_id = cc.document_id
        WHERE  c.page_start BETWEEN cc.page_start - 2
                             AND    cc.page_start + (CASE WHEN cc.prio < 2 THEN 20 ELSE 8 END)
        ORDER  BY c.text_chunk, c.page_start, c.id
    )
    SELECT text_chunk, page_start FROM deduped
    ORDER BY page_start
    LIMIT  40
"""

# Images for a document + error code, grouped by page for inline insertion.
_IMAGE_BY_DOC_PAGE_SQL = """
    SELECT DISTINCT ON (img.page_number)
        img.storage_url, img.page_number, img.image_type, img.ai_description,
        img.file_size, img.width_px, img.height_px, img.contains_text, img.ocr_text
    FROM krai_content.images img
    JOIN krai_core.documents d ON d.id = img.document_id
    WHERE d.filename = $1
      AND $2 = ANY(img.related_error_codes)
      AND img.storage_url LIKE 'http%'
    ORDER BY img.page_number,
             CASE img.image_type WHEN 'diagram' THEN 0 WHEN 'photo' THEN 1 ELSE 2 END
    LIMIT 6
"""

_TABLE_BY_DOC_PAGE_SQL = """
    SELECT st.page_number, st.table_index, st.table_type, st.table_markdown, st.caption, st.context_text
    FROM   krai_intelligence.structured_tables st
    JOIN   krai_core.documents d ON d.id = st.document_id
    WHERE  d.filename = $1
      AND  ($2 = ANY(st.related_error_codes) OR COALESCE(st.context_text, '') ILIKE $3 OR COALESCE(st.table_markdown, '') ILIKE $3)
    ORDER  BY st.page_number, st.table_index
    LIMIT  4
"""


def _format_solution_text(text: str) -> str:
    """Clean up PDF-extraction artifacts and produce clean Markdown.

    Fixes:
    - Bullet "●" joined as proper "- " list items
    - Numbered steps split across lines: "1.\\nText" → "1. Text"
    - Section headers like "Recommended action" → **bold**
    - Excessive blank lines collapsed
    """
    if not text:
        return text
    # Bullet char: ensure each item starts on its own line
    text = re.sub(r"●\s*\n\s*", "\n- ", text)
    text = re.sub(r"●\s+", "\n- ", text)
    # Numbered step split across lines: "1.\n  Text" → "1. Text"
    text = re.sub(r"(\d+)\.\s*\n\s*([A-Z\(])", r"\1. \2", text)
    # Numbered steps inline without newline: "..sentence.1. Next" → "..sentence.\n1. Next"
    text = re.sub(r"([a-z\.])(\d+)\.\s+([A-Z])", r"\1\n\2. \3", text)
    # Sub-steps "a.\n", "b.\n" → join with next line
    text = re.sub(r"\n([a-z])\.\s*\n\s*([A-Z\(])", r"\n\1. \2", text)
    # Bold "Recommended action" section headers (single-pass regex, avoids double-bolding)
    text = re.sub(
        r"Recommended action(?:\s+for\s+(?:HP\s+service|service\s+or\s+support|customers|(?:call-center\s+)?agents(?:\s+and\s+technicians)?|onsite\s+technicians))?",
        lambda m: f"\n\n**{m.group(0).strip()}**\n\n",
        text,
    )
    # Remove HP catch-all variant lines like "13.B9.Dz" (standalone lines, also at end)
    text = re.sub(r"(?:^|\n)[0-9A-Fa-f]{2}\.[0-9A-Fa-f]{2}\.[A-Za-z][a-z]?\s*(?=\n|$)", "", text)
    # Remove PDF chapter/section headings that slip into solution text
    text = re.sub(r"\n?Chapter\s+\d+[^\n]*\n?", "\n", text)
    text = re.sub(r"\nENWW\n", "\n", text)
    # Remove PDF table header artefacts (pre-boot menu tables etc.)
    text = re.sub(r"\nTable\s+\d+[-–]\d+[^\n]*\n", "\n", text)  # noqa: RUF001  # en-dash present in PDF text
    text = re.sub(r"\n(?:Menu option|First level|Second level|Third level|Description)\n", "\n", text)
    # Remove lonely "Administrator" / "Administrator (continued)" lines from HP pre-boot tables
    text = re.sub(r"\nAdministrator(?:\s*\(continued\))?\n", "\n", text)
    # Collapse 3+ blank lines → one blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_solution_from_chunk(chunk_text: str, error_code: str, allow_desc_fallback: bool = False) -> str | None:
    """Pull the solution/recommended-action block for ``error_code`` out of a raw chunk."""
    # Find the section starting at the error code.
    # Skip TOC-style occurrences (line immediately after code contains dotted leaders "....N")
    # so that e.g. a table-of-contents entry like "C0830.....7-448" is ignored and we
    # land on the actual description/procedure entry instead.
    search_start = 0
    idx = -1
    upper_text = chunk_text.upper()
    upper_code = error_code.upper()
    while True:
        pos = upper_text.find(upper_code, search_start)
        if pos == -1:
            break
        # Peek at the rest of the line and the next line to detect TOC entries
        snippet = chunk_text[pos : pos + 120]
        lines_after = snippet.split("\n", 2)
        # If the current line or the very next line has dotted leaders → TOC entry, skip
        is_toc = any(re.search(r"\.{4,}\s*\d+", ln) for ln in lines_after[:2])
        if not is_toc:
            idx = pos
            break
        search_start = pos + len(error_code)

    if idx == -1:
        return None
    section = chunk_text[idx:]
    # Look for "Recommended action" / "Empfohlene" / solution markers.
    # Non-Measures markers: use first occurrence only.
    # Measures: loop through ALL occurrences, skipping authentication/login procedures
    # that appear before the real hardware fix steps on Kyocera FAX multi-code pages
    # (IC Card login failure procedure comes first, actual FAX PWB / SSD fix comes later).
    _AUTH_PROC_RE = re.compile(  # noqa: N806  # function-scoped regex constant
        r"IC\s*Card|KeyPWB|Department\s+Management.*?Authentication|"
        r"Log\s+in\s+by\s+key\s+board|Set.*?IC\s+Card\s+authentication|"
        r"Changing\s+the\s+setting.*?IC\s+Card",
        re.IGNORECASE | re.DOTALL,
    )
    _HW_ACTION_RE = re.compile(  # noqa: N806  # function-scoped regex constant
        r"\b(replac|reinstall|check\b|firmware|execut|reset\b|install\b|"
        r"turn\s+off|reattach|remov|upgrade|initializ|U\d{3,}\b)",
        re.IGNORECASE,
    )
    for marker in ("Recommended action", "Empfohlene", "Lösung:", "Solution:"):
        m = section.find(marker)
        if m == -1:
            continue
        block = section[m : m + 1200].strip()
        stop = re.search(r"\n\d+\.\d+\.\d+\s", block)
        if stop:
            block = block[: stop.start()].strip()
        if len(block) > 20:
            return block
    # Measures: loop through all occurrences, skipping bad blocks
    search_pos = 0
    while True:
        m = section.find("Measures", search_pos)
        if m == -1:
            break
        block = section[m : m + 1200].strip()
        block = re.sub(r"^Measures\s*\nReference\s*\n", "", block)
        block = re.sub(r"^Measures\s*\n", "", block)
        # Remove pure table-header lines (Step, Check description, Assumed cause)
        block = re.sub(
            r"^(Step|Check description|Assumed cause|Reference)\s*$",
            "",
            block,
            flags=re.MULTILINE,
        )
        # Join hyphenated word-splits from PDF column layout (e.g. "Instal-\nlation")
        block = re.sub(r"(\w)-\n(\w)", r"\1\2", block)
        # Remove Reference column fragments that appear between procedure steps
        block = re.sub(
            r"\n(?:FAX\s+)?Instal(?:lation\s*)?Guide\b[^\n]*",
            "",
            block,
            flags=re.IGNORECASE,
        )
        block = re.sub(r"\nFirmware\s+Update\b[^\n]*", "", block, flags=re.IGNORECASE)
        block = re.sub(r"\nError\s+code\s*\n\s*Contents[^\n]*", "", block, flags=re.IGNORECASE)
        block = re.sub(r"\n{3,}", "\n\n", block).strip()
        # Reject Kyocera configuration tables (Items/Contents headers, not procedures)
        if re.search(r"^Items\s*$", block, re.MULTILINE) and re.search(r"^Contents\s*$", block, re.MULTILINE):
            search_pos = m + len("Measures")
            continue
        # Skip authentication/login-only blocks that precede the real hardware procedure
        if _AUTH_PROC_RE.search(block) and not _HW_ACTION_RE.search(block):
            search_pos = m + len("Measures")
            continue
        # Stop at the next error-code heading (e.g. "99.00.03 ...")
        stop = re.search(r"\n\d+\.\d+\.\d+\s", block)
        if stop:
            block = block[: stop.start()].strip()
        if len(block) > 20:
            return block
        search_pos = m + len("Measures")
    # No explicit marker — return numbered steps if any
    steps = re.findall(r"\n\d+\.\s+[^\n]{10,}", section[:1200])
    if steps:
        # Reject if these "steps" are actually a harness/connector table
        # (contains "Drawer connector" or "Part number" style entries)
        steps_text = "\n".join(steps)
        if not re.search(r"Drawer connector|Part number|Connection\s+Type", steps_text, re.IGNORECASE):
            return steps_text[: 6 * 120].strip() if len(steps) >= 1 else None
    # Description-only fallback for non-HP manufacturers (e.g. Kyocera FAX codes):
    # extract meaningful text immediately after the error code line.
    if allow_desc_fallback:
        lines = section.splitlines()
        desc_lines = []
        for line in lines[1:8]:  # skip first line (the code itself), take up to 7 more
            stripped = line.strip()
            if not stripped:
                if desc_lines:
                    break  # stop at first blank line after content
                continue
            # Skip TOC-style lines: "Something ..... 7-375"
            if re.search(r"\.{4,}\s*\d+", stripped):
                break
            # Stop if we hit the next error code (e.g. "C0040:" or "C0070:")
            # Also matches codes on their own line like "C0060" (no colon/space after)
            if re.match(r"^[A-Z]\d{4}([:\s]|$)", stripped):
                break
            # Also stop at "(1-N)C0070:" style TOC entries
            if re.match(r"^\(\d+-\d+\)[A-Z]\d{4}", stripped):
                break
            desc_lines.append(stripped)
        if desc_lines:
            text = "\n".join(desc_lines).strip()
            return text if len(text) > 20 else None
    return None


_CODE_HEADING_RE = re.compile(
    # Matches both numeric (10.05.60) and x-placeholder (10.0x.60) HP code headings
    r"\n\d{2,3}[.\-][0-9x]{2}[.\-][0-9xa-fA-F]{2,}\s+\S",
    re.MULTILINE,
)


def _extract_levels_from_combined(combined_text: str, error_code: str) -> dict:
    """
    Extract HP solution levels from a concatenation of deduplicated consecutive chunks.

    Finds where error_code starts and extracts all three HP solution levels from
    that point onwards, stopping at the next different error-code heading.

    When the specific code appears inside a dense table listing (e.g. 10.0x.35 variants),
    the individual code line is very short and the shared "Recommended action" comes AFTER
    the whole table.  In that case we back up to the family-code line (e.g. 10.0x.35) and
    extract from there so the shared solution is included.

    In all cases the block is truncated at the first *different* error-code section
    heading so that adjacent sections don't contaminate the extracted levels.
    """
    from backend.utils.hp_solution_filter import extract_all_hp_levels

    idx = combined_text.upper().find(error_code.upper())
    if idx == -1:
        block = combined_text
        anchor_len = 0
    else:
        block = combined_text[idx:]
        anchor_len = len(error_code)
        # Stop at the next DIFFERENT error-code heading on its own line
        stop = re.search(
            r"\n[A-Z0-9]{1,4}[.\-][A-Z0-9]{1,4}[.\-][A-Z0-9]{1,4}\s+[A-Z]",
            block[anchor_len:],
            re.IGNORECASE,
        )
        if stop:
            candidate = block[: anchor_len + stop.start()]
            # Only truncate if the candidate block is substantial (≥200 chars) or already
            # contains a "Recommended action" header.
            if len(candidate) >= 200 or re.search(r"Recommended\s+action", candidate, re.IGNORECASE):
                block = candidate
            # else: candidate is tiny (code appears inside a table listing) —
            # try to back up to the family code line (e.g. "10.0x.35" for "10.00.35")
            else:
                family_pat = re.sub(
                    r"(\d{2,3})\.(\d{2})\.(\d{1,3})",
                    lambda m: f"{m.group(1)}.0x.{m.group(3)}",
                    error_code,
                )
                family_idx = combined_text.upper().rfind(family_pat.upper(), 0, idx)
                if family_idx != -1:
                    block = combined_text[family_idx:]
                    anchor_len = len(family_pat)
                # else: keep full block (no family line found)

    # Truncate at the first adjacent section's code heading, but only AFTER we've
    # passed the first "Recommended action" header.  Without this guard the pattern
    # would fire inside the code-variant table (e.g. "10.00.35 Black toner cartridge")
    # and produce an empty block.
    first_rec = re.search(r"Recommended\s+action", block[anchor_len:], re.IGNORECASE)
    if first_rec:
        search_from = anchor_len + first_rec.end()
        adjacent = _CODE_HEADING_RE.search(block[search_from:])
        if adjacent:
            block = block[: search_from + adjacent.start()]

    return extract_all_hp_levels(block, manufacturer="HP")


async def _fast_path_lookup(
    pool,
    text: str,
    scope: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any] | None] | None:
    """Try an instant DB lookup if ``text`` contains an error code.

    Also detects a model number in the query (e.g. "M507", "E50045", "bizhub 308")
    and filters results to documents that cover that model.

    Returns:
        - Formatted Markdown with results (filtered by model when detected).
        - A "not found" message when a code is detected but absent from DB.
        - ``None`` when no error-code pattern is detected.
    """
    # Collect all matches; prefer dotted/dashed codes (group 1) over plain alpha+digit codes
    # (group 2), and skip matches that look like model numbers (e.g. E877, M507).
    all_matches = list(_ERROR_CODE_RE.finditer(text))
    if not all_matches:
        return None

    # Prefer group-1 matches (dotted/dashed like 13.A8.D4) over group-2 (SC542, E001)
    group1 = [m for m in all_matches if m.group(1) and not _MODEL_RE.fullmatch(m.group(1))]
    group2 = [m for m in all_matches if m.group(2) and not _MODEL_RE.fullmatch(m.group(2))]
    m = (group1 or group2 or all_matches)[0]

    raw_code = (m.group(1) or m.group(2)).upper()
    variants = [raw_code]
    no_dash = raw_code.replace("-", "")
    if no_dash != raw_code:
        variants.append(no_dash)

    # Detect optional model number in user message (ignore the error code itself)
    text_without_code = text[: m.start()] + text[m.end() :]
    model_match = _MODEL_RE.search(text_without_code)
    raw_model = model_match.group(0).strip() if model_match else None
    active_scope = normalize_scope(scope)

    try:
        async with pool.acquire() as conn:
            rows = None
            for v in variants:
                model_filter_enabled = raw_model and not any(
                    active_scope.get(key) for key in ("product", "product_id", "series")
                )
                for apply_model_filter in [True, False] if model_filter_enabled else [False]:
                    params: list[object] = [f"%{v}%"]
                    where_clauses = [
                        "ec.is_category IS NOT TRUE",
                        "ec.error_code ILIKE $1",
                    ]
                    where_clauses.extend(
                        build_scope_filters(
                            params,
                            active_scope,
                            manufacturer_templates=("m.name ILIKE ${index}",),
                            product_templates=(
                                "COALESCE(p.model_number, '') ILIKE ${index}",
                                "COALESCE(p.model_name, '') ILIKE ${index}",
                                "COALESCE(ps.series_name, '') ILIKE ${index}",
                            ),
                            product_id_template="dp.product_id = ${index}::uuid",
                            series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                            document_id_template="ec.document_id = ${index}::uuid",
                        )
                    )
                    if apply_model_filter and raw_model:
                        params.append(f"%{raw_model}%")
                        where_clauses.append(
                            f"(COALESCE(p.model_number, '') ILIKE ${len(params)} "
                            f"OR COALESCE(p.model_name, '') ILIKE ${len(params)} "
                            f"OR COALESCE(ps.series_name, '') ILIKE ${len(params)})"
                        )
                    params.append(50)
                    rows = await conn.fetch(
                        f"""
                        {_FAST_PATH_BASE_SQL}
                        WHERE {' AND '.join(where_clauses)}
                        ORDER BY ec.id, ec.confidence_score DESC NULLS LAST
                        LIMIT ${len(params)}
                        """,
                        *params,
                    )
                    if rows:
                        break
                if rows:
                    break
    except Exception as exc:
        logger.warning("fast_path_lookup DB error: %s", exc)
        return None

    # Code pattern detected but nothing in DB → return immediately, skip LLM
    if not rows:
        return (
            (
                f"**Fehlercode `{raw_code}` nicht in der KRAI-Datenbank gefunden.**\n\n"
                "Mögliche Ursachen:\n"
                "- Dieser Code wurde noch nicht aus den Service-Handbüchern extrahiert\n"
                "- Prüfe die Schreibweise (z.B. `C-2801` statt `C2801`)\n"
                "- Wende dich an den Hersteller-Support oder öffne das zugehörige Service-Manual direkt"
            ),
            {
                "type": "error_code_lookup",
                "found": False,
                "error_code": raw_code,
                "scope": active_scope,
            },
        )

    if raw_model:
        rows = sorted(
            rows,
            key=lambda row: (
                -_model_match_score(row, raw_model),
                -(float(row["confidence_score"]) if row["confidence_score"] else 0.0),
                str(row.get("document_filename") or "").lower(),
            ),
        )

    # ── Group by (code, description) — collect unique sources with model info ──
    groups: dict[str, dict] = {}
    for row in rows:
        key = f"{row['error_code']}|{row['error_description']}"
        row_tech = row["solution_technician_text"] or ""
        row_agent = row["solution_agent_text"] or ""
        row_cust = row["solution_customer_text"] or ""
        if key not in groups:
            groups[key] = {
                "code": row["error_code"],
                "desc": row["error_description"] or "—",
                "sol_customer": row_cust,
                "sol_agent": row_agent,
                "sol_technician": row_tech,
                "mfr": row["manufacturer_name"] or "",
                "sources": [],  # list of (filename, page, models_list)
            }
        else:
            # Keep the longest (best) solution text across all matching rows
            if len(row_tech) > len(groups[key]["sol_technician"]):
                groups[key]["sol_technician"] = row_tech
            if len(row_agent) > len(groups[key]["sol_agent"]):
                groups[key]["sol_agent"] = row_agent
            if len(row_cust) > len(groups[key]["sol_customer"]):
                groups[key]["sol_customer"] = row_cust
        fn = row["document_filename"]
        pg = row["page_number"]
        mdl = [value for value in (_product_label(row), row["series_name"]) if value]
        src_key = f"{fn}:{pg}"
        if fn and src_key not in {f"{s[0]}:{s[1]}" for s in groups[key]["sources"]}:
            groups[key]["sources"].append((fn, pg, mdl))

    # ── Fetch full multi-chunk solution for each unique document source ───────
    # Also collects images linked to the error code for inline display.
    full_solutions: dict[str, dict] = {}  # filename → {customer, agent, technician, images}
    try:
        async with pool.acquire() as conn:
            seen_docs: set[str] = set()
            for group in groups.values():
                for fn, pg, mdl in group["sources"]:
                    if fn in seen_docs:
                        continue
                    seen_docs.add(fn)

                    # Always fetch images — independent of solution text quality
                    img_rows = await conn.fetch(_IMAGE_BY_DOC_PAGE_SQL, fn, raw_code)
                    seen_urls: set[str] = set()
                    image_md_list: list[str] = []
                    for ir in img_rows:
                        if not _is_meaningful_response_image(ir):
                            continue
                        url = _rewrite_storage_url(ir["storage_url"])
                        if url not in seen_urls:
                            seen_urls.add(url)
                            caption = ir["ai_description"] or ir["image_type"] or "Bild"
                            image_md_list.append(f"![{caption}]({url})")

                    # Only fetch chunks when DB solution columns are short/missing
                    # OR when the solution looks like a Table of Contents (dot leaders)
                    # OR when the solution looks contaminated (code-table or harness table)
                    # NOTE: chunk extraction uses HP-specific level parsing; skip for non-HP
                    # manufacturers to avoid dumping entire Kyocera/Lexmark code tables.
                    mfr_name = (group.get("mfr") or "").lower()
                    is_hp_doc = "hewlett" in mfr_name or mfr_name == "hp"
                    db_tech = group["sol_technician"] or ""
                    db_tech_len = len(db_tech)
                    is_toc = bool(re.search(r"\.{10,}", db_tech))
                    is_contaminated = bool(
                        re.search(r"Harness Part number|Connection\s+Type", db_tech, re.IGNORECASE)
                        or re.search(r"\n1[0-9]\.[0-9x]{2}\.[0-9a-fA-F]{2,}\s+\S", db_tech)
                    )
                    if is_hp_doc and (db_tech_len < 200 or is_toc or is_contaminated):
                        chunk_rows = await conn.fetch(_FULL_SOLUTION_SQL, fn, f"%{raw_code}%")
                        if chunk_rows:
                            combined = "\n".join(row["text_chunk"] for row in chunk_rows)
                            # Skip chunks that are pure error-code reference tables with no
                            # actual solution steps (e.g. Lexmark tables that only say
                            # "see service check on page N").  Require at least one of:
                            # - a recognised solution/action header
                            # - at least 2 numbered steps (1. text or 1 Text)
                            _has_solution_header = bool(
                                re.search(
                                    r"Recommended\s+action|Corrective\s+action|"
                                    r"Troubleshooting\s+steps?|Solution\s*:|Procedure\s*:|Action\s*:",
                                    combined,
                                    re.IGNORECASE,
                                )
                            )
                            _numbered_steps = re.findall(
                                r"^\s*\d+[\.\)][ \t]+\S|^\s*\d+[ \t]+[A-Z]",
                                combined,
                                re.MULTILINE,
                            )
                            if not _has_solution_header and len(_numbered_steps) < 2:
                                # No useful solution content — skip chunk fallback
                                pass
                            else:
                                levels = _extract_levels_from_combined(combined, raw_code)
                                new_tech_len = len(levels.get("technician") or "")
                                best_len = max(
                                    new_tech_len,
                                    len(levels.get("agent") or ""),
                                    len(levels.get("customer") or ""),
                                )
                                if any(levels.values()) and best_len >= max(db_tech_len, 100):
                                    full_solutions[fn] = {**levels, "images": image_md_list}
                                    continue

                    # DB solution is good — just store images (no text override)
                    if image_md_list and fn not in full_solutions:
                        full_solutions[fn] = {"images": image_md_list}
    except Exception as exc:
        logger.warning("full_solution_lookup error: %s", exc)

    # ── Chunk fallback only when ALL three DB columns are empty ───────────────
    solution_from_chunk: str | None = None
    related_videos = []
    related_documents = []
    related_tables = []
    first_group = next(iter(groups.values()))
    # Treat harness/connector-table solutions as absent — they are extraction artifacts
    # containing component names (e.g. "• Drawer connector … Image drive PWB") but no
    # actionable procedure steps.
    _tech = first_group["sol_technician"] or ""
    _is_harness_garbage = bool(
        re.search(r"Drawer\s+connector|Harness\s+Part\s+number|Connection\s+Type", _tech, re.IGNORECASE)
        and not re.search(r"(check|replac|remov|install|turn off|firmware)", _tech, re.IGNORECASE)
    )
    if _is_harness_garbage:
        for _g in groups.values():
            _g["sol_technician"] = ""
            _g["sol_agent"] = ""
            _g["sol_customer"] = ""
    has_db_solution = bool(first_group["sol_technician"] or first_group["sol_agent"] or first_group["sol_customer"])

    if not has_db_solution:
        mfr_lower = (first_group.get("mfr") or "").lower()
        is_hp = "hewlett" in mfr_lower or mfr_lower == "hp"
        try:
            async with pool.acquire() as conn:
                if is_hp:
                    chunk_rows = await conn.fetch(
                        _CHUNK_SOLUTION_SQL,
                        f"%{raw_code}%",
                        "%Recommended action%",
                    )
                    for cr in chunk_rows:
                        sol = _extract_solution_from_chunk(cr["text_chunk"], raw_code)
                        if sol:
                            solution_from_chunk = sol
                            break
                else:
                    # Non-HP (Kyocera, Lexmark, etc.): try FULL_SOLUTION_SQL for every
                    # source document (anchor chunk + surrounding pages).  When multiple
                    # documents contain the code we score each candidate result against
                    # the error description so that the most relevant procedure wins.
                    error_desc_lower = (first_group.get("desc") or "").lower()
                    # Significant keywords from the description (≥4 chars, not boilerplate)
                    _stop_words = {
                        "this",
                        "that",
                        "with",
                        "from",
                        "have",
                        "been",
                        "which",
                        "when",
                        "error",
                        "fault",
                        "code",
                        "message",
                        "occur",
                        "cannot",
                        "does",
                        "into",
                    }
                    desc_keywords = [
                        w for w in set(re.findall(r"\b[a-z]{4,}\b", error_desc_lower)) if w not in _stop_words
                    ]
                    best_sol: str | None = None
                    best_score: int = -1
                    seen_filenames: set[str] = set()
                    for grp in groups.values():
                        for src_fn, _pg, _mdl in grp.get("sources", []):
                            if not src_fn or src_fn in seen_filenames:
                                continue
                            seen_filenames.add(src_fn)
                            combined_rows = await conn.fetch(_FULL_SOLUTION_SQL, src_fn, f"%{raw_code}%")
                            if not combined_rows:
                                continue
                            combined = "\n".join(row["text_chunk"] for row in combined_rows)
                            sol = _extract_solution_from_chunk(combined, raw_code, allow_desc_fallback=True)
                            if not sol:
                                continue
                            # Score candidate: count how many description keywords appear
                            sol_lower = sol.lower()
                            score = sum(1 for kw in desc_keywords if kw in sol_lower)
                            if score > best_score:
                                best_score = score
                                best_sol = sol
                    if best_sol:
                        solution_from_chunk = best_sol
                    if not solution_from_chunk:
                        # Fallback: search any chunk across all documents with this code
                        chunk_rows = await conn.fetch(
                            _CHUNK_DESC_FALLBACK_SQL,
                            f"%{raw_code}%",
                        )
                        for cr in chunk_rows:
                            sol = _extract_solution_from_chunk(cr["text_chunk"], raw_code, allow_desc_fallback=True)
                            if sol:
                                solution_from_chunk = sol
                                break
        except Exception as exc:
            logger.warning("chunk_solution_lookup error: %s", exc)

    try:
        matched_product_ids = list({str(row["product_id"]) for row in rows if row["product_id"]})
        matched_document_ids = list({str(row["document_id"]) for row in rows if row["document_id"]})
        related_query = f"{raw_code} {raw_model}" if raw_model else raw_code
        async with pool.acquire() as conn:
            related_videos = await _find_related_videos(
                conn,
                related_query,
                active_scope,
                matched_product_ids=matched_product_ids,
                matched_document_ids=matched_document_ids,
            )
            related_documents = await _find_related_documents(
                conn,
                related_query,
                active_scope,
                matched_product_ids=matched_product_ids,
                exclude_document_ids=matched_document_ids,
            )
            if raw_model and not related_documents:
                related_documents = await _find_related_documents(
                    conn,
                    raw_model,
                    active_scope,
                    matched_product_ids=matched_product_ids,
                    exclude_document_ids=matched_document_ids,
                )
            for doc_filename in {row["document_filename"] for row in rows if row["document_filename"]}:
                related_tables.extend(await conn.fetch(_TABLE_BY_DOC_PAGE_SQL, doc_filename, raw_code, f"%{raw_code}%"))
    except Exception as exc:
        logger.warning("related_context_lookup error: %s", exc)

    if raw_model:
        related_documents = sorted(
            related_documents,
            key=lambda document: (
                -_model_match_score(document, raw_model),
                str(document.get("filename") or "").lower(),
            ),
        )

    # ── Format output ─────────────────────────────────────────────────────────
    parts: list[str] = []
    for group in groups.values():
        code = group["code"]
        desc = group["desc"]
        sol_c = group["sol_customer"]
        sol_a = group["sol_agent"]
        sol_t = group["sol_technician"]
        mfr = group["mfr"]
        sources = group["sources"]

        # Strip leading punctuation/spaces from description (PDF extraction artifact)
        desc = re.sub(r"^[\s,;:\-–—]+", "", desc).strip() or "—"  # noqa: RUF001
        header = f"### Fehler `{code}` – {desc}"  # noqa: RUF001
        if mfr:
            header += f"  *({mfr})*"
        if raw_model:
            header += f"  🖨️ gefiltert für **{raw_model}**"
        elif active_scope and _scope_label(active_scope):
            header += f"  🖨️ Scope: **{_scope_label(active_scope)}**"
        parts.append(header)

        # Use full multi-chunk solution when available, fall back to DB column.
        # Prefer the source document whose solution contains inline images (![...]).
        first_src_fn = sources[0][0] if sources else None
        full = {}
        for fn, _pg, _mdl in sources:
            candidate = full_solutions.get(fn, {})
            if not candidate:
                continue
            # Prefer any candidate that has images
            if candidate.get("images"):
                full = candidate
                break
            if not full:
                full = candidate
        sol_t_full = _format_solution_text(full.get("technician") or (sol_t if not full else "") or "")
        sol_a_full = _format_solution_text(full.get("agent") or (sol_a if not full else "") or "")
        sol_c_full = _format_solution_text(full.get("customer") or (sol_c if not full else "") or "")
        sol_t_full = _strip_hp_family_lines(sol_t_full, code)
        sol_a_full = _strip_hp_family_lines(sol_a_full, code)
        sol_c_full = _strip_hp_family_lines(sol_c_full, code)
        images_md: list[str] = full.get("images") or []

        # Solution: technician preferred → agent → customer → chunk fallback
        if sol_t_full:
            parts.append("\n**🔧 Techniker-Lösung:**\n")
            parts.append(sol_t_full)
            if images_md:
                parts.append("\n\n**🖼️ Bilder aus dem Service-Manual:**\n")
                parts.extend(images_md)
            if sol_c_full:
                parts.append("\n---\n**👤 Anwender-Kurzlösung:**\n")
                parts.append(sol_c_full)
        elif sol_a_full:
            parts.append("\n**📞 2nd-Level-Lösung:**\n")
            parts.append(sol_a_full)
            if images_md:
                parts.append("\n\n**🖼️ Bilder aus dem Service-Manual:**\n")
                parts.extend(images_md)
            if sol_c_full:
                parts.append("\n---\n**👤 Anwender-Kurzlösung:**\n")
                parts.append(sol_c_full)
        elif sol_c_full:
            parts.append("\n**👤 Anwender-Lösung:**\n")
            parts.append(sol_c_full)
        elif solution_from_chunk:
            # Use a description label when the content has no numbered steps (non-HP fallback)
            _has_steps = bool(re.search(r"^\s*\d+[\.\)]\s+\S", solution_from_chunk, re.MULTILINE))
            if _has_steps:
                parts.append("\n**Lösung** *(aus Service-Manual)*:\n")
            else:
                parts.append("\n**ℹ️ Fehlerbeschreibung** *(aus Service-Manual)*:\n")  # noqa: RUF001
            parts.append(_format_solution_text(solution_from_chunk))
        else:
            parts.append("\n⚠️ *Keine Schritt-für-Schritt-Lösung verfügbar. Bitte Service-Manual konsultieren.*")

        # Sources with model coverage
        if sources:
            parts.append("")
            if raw_model:
                parts.append(f"**📄 Quelle für {raw_model}:**")
            else:
                parts.append(f"**📄 Quellen** ({len(sources)} Dokumente):")
            ordered_sources = sorted(
                sources,
                key=lambda source: (
                    -_model_match_score(
                        {
                            "document_filename": source[0],
                            "model_number": " ".join(source[2]),
                            "series_name": " ".join(source[2]),
                        },
                        raw_model,
                    ),
                    str(source[0] or "").lower(),
                ),
            )
            for fn, pg, mdl in ordered_sources:
                src = f"- `{fn}`"
                if pg:
                    src += f", Seite {pg}"
                if mdl and not raw_model:
                    shown = ", ".join(mdl[:6])
                    if len(mdl) > 6:
                        shown += f" +{len(mdl)-6} weitere"
                    src += f"\n  *Modelle: {shown}*"
                parts.append(src)

        if not raw_model and not active_scope.get("product") and len(sources) > 1:
            parts.append(f"\n> 💡 Nenne dein Modell für eine gefilterte Antwort — z.B. `{code} M507`")

    if related_videos:
        parts.append("\n## 🎬 Passende Videos\n")
        for video in related_videos:
            dur = f" ({video['duration']//60}:{video['duration']%60:02d})" if video["duration"] else ""
            lines = [f"- **[{video['title']}]({video['video_url']})**{dur}"]
            product_label = _product_label(video) or video["series_name"]
            if product_label:
                lines.append(f"  Gerät: {product_label}")
            if video["description"]:
                lines.append(f"  _{video['description'][:120]}_")
            parts.append("\n".join(lines))

    if related_documents:
        parts.append("\n## 📚 Weitere relevante Dokumente\n")
        for document in related_documents:
            storage_url = _rewrite_document_url(document.get("storage_url"))
            if storage_url:
                lines = [f"- **[{document['filename']}]({storage_url})**"]
            else:
                lines = [f"- **`{document['filename']}`**"]
            if document["document_type"]:
                lines[0] += f" — {document['document_type']}"
            product_label = _product_label(document) or document["series_name"]
            if product_label:
                lines.append(f"  Gerät: {product_label}")
            if document["manufacturer_name"]:
                lines.append(f"  Hersteller: {document['manufacturer_name']}")
            parts.append("\n".join(lines))

    if related_tables:
        parts.append("\n## 📋 Relevante Tabellen\n")
        seen_table_keys: set[tuple[object, object]] = set()
        for table in related_tables:
            table_key = (table["page_number"], table["table_index"])
            if table_key in seen_table_keys:
                continue
            seen_table_keys.add(table_key)
            header = f"- Tabelle Seite {table['page_number']}"
            if table["caption"]:
                header += f": {table['caption']}"
            parts.append(header)
            if table["table_markdown"]:
                parts.append(f"\n{table['table_markdown']}\n")

    primary_group = next(iter(groups.values()))
    context = {
        "type": "error_code_lookup",
        "found": True,
        "error_code": raw_code,
        "scope": active_scope,
        "summary": {
            "description": primary_group["desc"],
            "manufacturer": primary_group["mfr"],
        },
        "solutions": {
            "technician": sol_t_full if "sol_t_full" in locals() else None,
            "agent": sol_a_full if "sol_a_full" in locals() else None,
            "customer": sol_c_full if "sol_c_full" in locals() else None,
            "chunk_fallback": solution_from_chunk,
        },
        "videos": [
            {
                "title": video["title"],
                "url": video["video_url"],
                "description": video["description"],
                "duration": video["duration"],
                **_serialize_krai_row(video),
            }
            for video in related_videos
        ],
        "related_documents": [
            {
                "filename": document["filename"],
                "document_type": document["document_type"],
                "storage_url": _rewrite_document_url(document.get("storage_url")),
                **_serialize_krai_row(document),
            }
            for document in related_documents
        ],
        "tables": [
            {
                "page_number": table["page_number"],
                "table_index": table["table_index"],
                "table_type": table["table_type"],
                "caption": table["caption"],
                "table_markdown": table["table_markdown"],
            }
            for table in related_tables
        ],
        "source_documents": [
            {
                "filename": filename,
                "page_number": page_number,
                "models": models,
            }
            for filename, page_number, models in primary_group["sources"]
        ],
    }

    return "\n".join(parts), context


# ---------------------------------------------------------------------------
# Guided-path: direct SQL for parts / video queries (no LLM)
# ---------------------------------------------------------------------------

_PARTS_KEYWORDS = re.compile(
    r"\b(ersatzteil|spare.?part|part.?number|teilenummer|bauteil|fuser|drum|toner|"
    r"roller|belt|kit|assembly|unit|motor|sensor|board|pcb)\b",
    re.IGNORECASE,
)

_VIDEO_KEYWORDS = re.compile(
    r"\b(video|youtube|tutorial|anleitung|howto|how.?to|reparatur|repair|"
    r"wartung|maintenance|replace|austausch|einbau|installation)\b",
    re.IGNORECASE,
)

_VIDEO_QUERY_STOPWORDS = {
    "gibt",
    "es",
    "ein",
    "eine",
    "einen",
    "video",
    "youtube",
    "tutorial",
    "anleitung",
    "howto",
    "how-to",
    "how",
    "to",
    "repair",
    "reparatur",
    "replace",
    "tauschen",
    "austauschen",
    "wechseln",
    "wechsel",
    "remove",
    "removal",
    "install",
    "installation",
    "einbau",
    "wie",
    "kann",
    "ich",
    "das",
    "die",
    "der",
    "dem",
    "den",
    "zu",
    "für",
    "for",
}

_PARTS_BASE_SQL = """
    SELECT pc.part_number, pc.part_name, pc.description, pc.category,
           pc.price_usd, m.name AS manufacturer_name,
           p.model_number, p.model_name, ps.series_name
    FROM   krai_parts.parts_catalog pc
    LEFT JOIN krai_core.products p ON pc.product_id = p.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
    LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
"""

_VIDEO_BASE_SQL = """
    SELECT DISTINCT ON (v.id)
           v.title, v.video_url, v.description, v.duration, v.channel_title,
           m.name AS manufacturer_name, p.model_number, p.model_name, ps.series_name
    FROM   krai_content.videos v
    LEFT JOIN krai_core.manufacturers m ON v.manufacturer_id = m.id
    LEFT JOIN krai_content.video_products vp ON vp.video_id = v.id
    LEFT JOIN krai_core.products p ON vp.product_id = p.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
"""

_SEMANTIC_BASE_SQL = """
    SELECT DISTINCT ON (c.id)
           c.text_chunk, c.page_start, d.filename, d.original_filename,
           m.name AS manufacturer_name, p.model_number, p.model_name, ps.series_name
    FROM   krai_intelligence.chunks c
    JOIN   krai_core.documents d ON c.document_id = d.id
    LEFT JOIN krai_core.document_products dp ON dp.document_id = d.id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
    LEFT JOIN krai_core.manufacturers m ON COALESCE(p.manufacturer_id, d.manufacturer_id) = m.id
"""

_RELATED_DOCUMENTS_BASE_SQL = """
    SELECT DISTINCT ON (d.id)
           d.id, d.filename, d.document_type, d.storage_url,
           m.name AS manufacturer_name,
           p.model_number, p.model_name, ps.series_name
    FROM   krai_core.documents d
    LEFT JOIN krai_core.document_products dp ON dp.document_id = d.id
    LEFT JOIN krai_core.products p ON dp.product_id = p.id
    LEFT JOIN krai_core.product_series ps ON p.series_id = ps.id
    LEFT JOIN krai_core.manufacturers m ON COALESCE(p.manufacturer_id, d.manufacturer_id) = m.id
    LEFT JOIN krai_intelligence.chunks ch ON ch.document_id = d.id
"""


async def _parts_lookup(pool, text: str, scope: dict[str, str] | None = None) -> str | None:
    """Return spare-parts results when query mentions part-related keywords."""
    if not _PARTS_KEYWORDS.search(text):
        return None
    active_scope = normalize_scope(scope)
    # Extract longest token as search term
    tokens = [
        t
        for t in re.findall(r"\b\w[\w\-\.]{2,}\b", text)
        if not re.match(
            r"^(was|ist|wie|gibt|es|der|die|das|und|oder|ich|du|wir|sie|ein|für|mit|von|bei|nach|auf|an|im|zur|zum)$",
            t,
            re.I,
        )
    ]
    term = max(tokens, key=len) if tokens else text[:40]
    try:
        async with pool.acquire() as conn:
            params: list[object] = [f"%{term}%"]
            where_clauses = [
                "("
                "pc.part_number ILIKE $1 OR "
                "COALESCE(pc.part_name, '') ILIKE $1 OR "
                "COALESCE(pc.description, '') ILIKE $1"
                ")"
            ]
            where_clauses.extend(
                build_scope_filters(
                    params,
                    active_scope,
                    manufacturer_templates=("m.name ILIKE ${index}",),
                    product_templates=(
                        "COALESCE(p.model_number, '') ILIKE ${index}",
                        "COALESCE(p.model_name, '') ILIKE ${index}",
                        "COALESCE(ps.series_name, '') ILIKE ${index}",
                    ),
                    product_id_template="pc.product_id = ${index}::uuid",
                    series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                )
            )
            params.append(8)
            rows = await conn.fetch(
                f"""
                {_PARTS_BASE_SQL}
                WHERE {' AND '.join(where_clauses)}
                ORDER BY pc.part_number
                LIMIT ${len(params)}
                """,
                *params,
            )
            if not rows and len(term) > 6:
                # Retry with shorter stem
                params[0] = f"%{term[:6]}%"
                rows = await conn.fetch(
                    f"""
                    {_PARTS_BASE_SQL}
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY pc.part_number
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
    except Exception as exc:
        logger.warning("parts_lookup DB error: %s", exc)
        return None
    if not rows:
        return f"**Kein Ersatzteil für `{term}` gefunden.**\n\nTipp: Suche nach Teilenummer oder Gerätebezeichnung."
    lines = ["## 🔧 Ersatzteile\n"]
    if active_scope and _scope_label(active_scope):
        lines.append(f"_Scope: { _scope_label(active_scope) }_\n")
    for r in rows:
        price = f" — ${r['price_usd']:.2f}" if r["price_usd"] else ""
        mfr = f" *({r['manufacturer_name']})*" if r["manufacturer_name"] else ""
        lines.append(f"**{r['part_number']}** – {r['part_name']}{mfr}{price}")  # noqa: RUF001
        if _product_label(r) or r["series_name"]:
            lines.append(f"  Gerät: {_product_label(r) or r['series_name']}")
        if r["description"]:
            lines.append(f"  _{r['description'][:120]}_")
    return "\n".join(lines)


async def _video_lookup(
    pool,
    text: str,
    scope: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return ranked video results with related context for video/tutorial queries."""
    if not _VIDEO_KEYWORDS.search(text):
        return None
    active_scope = normalize_scope(scope)
    search_plan = _build_video_search_plan(text, active_scope)
    if search_plan["manufacturer"] and not active_scope.get("manufacturer"):
        active_scope = {**active_scope, "manufacturer": search_plan["manufacturer"]}
    search_term_sets = search_plan["search_term_sets"]
    primary_terms = search_term_sets[0]
    display_term = " ".join(primary_terms)
    try:
        async with pool.acquire() as conn:
            ranked_rows: dict[str, tuple[dict[str, Any], int]] = {}
            for search_terms in search_term_sets:
                params: list[object] = [f"%{term}%" for term in search_terms]
                where_clauses = []
                for index in range(1, len(search_terms) + 1):
                    where_clauses.append(
                        "("
                        f"v.title ILIKE ${index} OR "
                        f"COALESCE(v.description, '') ILIKE ${index} OR "
                        f"COALESCE(v.context_description, '') ILIKE ${index} OR "
                        f"COALESCE(p.model_number, '') ILIKE ${index} OR "
                        f"COALESCE(p.model_name, '') ILIKE ${index} OR "
                        f"COALESCE(ps.series_name, '') ILIKE ${index}"
                        ")"
                    )
                where_clauses.extend(
                    build_scope_filters(
                        params,
                        active_scope,
                        manufacturer_templates=("m.name ILIKE ${index}",),
                        product_templates=(
                            "COALESCE(p.model_number, '') ILIKE ${index}",
                            "COALESCE(p.model_name, '') ILIKE ${index}",
                            "COALESCE(ps.series_name, '') ILIKE ${index}",
                        ),
                        product_id_template="vp.product_id = ${index}::uuid",
                        series_templates=("COALESCE(ps.series_name, '') ILIKE ${index}",),
                        document_id_template="v.document_id = ${index}::uuid",
                    )
                )
                params.append(20)
                rows = await conn.fetch(
                    f"""
                    {_VIDEO_BASE_SQL}
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY v.id, v.published_at DESC NULLS LAST
                    LIMIT ${len(params)}
                    """,
                    *params,
                )
                for row in rows:
                    score = _video_row_relevance(
                        row,
                        primary_terms,
                        issue_terms=search_plan["issue_terms"],
                        expansion_terms=search_plan["expansion_terms"],
                    )
                    if search_terms == primary_terms:
                        score += 20
                    elif search_terms == [search_plan["model"]]:
                        score += 10

                    row_key = row.get("video_url") or row.get("title") or str(row)
                    previous = ranked_rows.get(row_key)
                    if previous is None or score > previous[1]:
                        ranked_rows[row_key] = (dict(row), score)

            ordered_rows = [
                row
                for row, _score in sorted(
                    ranked_rows.values(),
                    key=lambda item: (-item[1], str(item[0].get("title") or "").lower()),
                )[:5]
            ]

            related_documents = await _find_related_documents(
                conn,
                " ".join(primary_terms),
                active_scope,
                limit=4,
            )
    except Exception as exc:
        logger.warning("video_lookup DB error: %s", exc)
        return None

    if not ordered_rows:
        parts = [
            f"**Kein Video für `{display_term}` gefunden.**\n",
            "Tipp: Suche nach Gerätemodell oder Reparaturtyp.",
        ]
        if related_documents:
            parts.append("\n## 📚 Relevante Dokumente\n")
            for document in related_documents:
                storage_url = _rewrite_document_url(document.get("storage_url"))
                if storage_url:
                    lines = [f"- **[{document['filename']}]({storage_url})**"]
                else:
                    lines = [f"- **`{document['filename']}`**"]
                if document["document_type"]:
                    lines[0] += f" — {document['document_type']}"
                product_label = _product_label(document) or document["series_name"]
                if product_label:
                    lines.append(f"  Gerät: {product_label}")
                parts.append("\n".join(lines))
        return (
            "\n".join(parts),
            {
                "type": "video_lookup",
                "found": False,
                "scope": active_scope,
                "query": text,
                "search_terms": primary_terms,
                "signals": {
                    "model": search_plan["model"],
                    "issue_terms": search_plan["issue_terms"],
                },
                "related_documents": [_serialize_document_match(document) for document in related_documents],
            },
        )

    lines = ["## 🎬 Videos\n"]
    if active_scope and _scope_label(active_scope):
        lines.append(f"_Scope: { _scope_label(active_scope) }_\n")
    if search_plan["model"] or search_plan["issue_terms"]:
        understood_bits = []
        if search_plan["model"]:
            understood_bits.append(f"Modell `{search_plan['model']}`")
        if search_plan["issue_terms"]:
            understood_bits.append(f"Thema `{', '.join(search_plan['issue_terms'])}`")
        if search_plan["expansion_terms"]:
            understood_bits.append(f"HP-Erweiterung `{', '.join(search_plan['expansion_terms'])}`")
        lines.append(f"_Verstanden als: {' · '.join(understood_bits)}_\n")
    for r in ordered_rows:
        dur = f" ({r['duration']//60}:{r['duration']%60:02d})" if r["duration"] else ""
        ch = f" — {r['channel_title']}" if r["channel_title"] else ""
        lines.append(f"**[{r['title']}]({r['video_url']})**{dur}{ch}")
        if _product_label(r) or r["series_name"]:
            lines.append(f"  Gerät: {_product_label(r) or r['series_name']}")
        if r["description"]:
            lines.append(f"  _{r['description'][:120]}_\n")
    if related_documents:
        lines.append("\n## 📚 Relevante Dokumente\n")
        for document in related_documents:
            storage_url = _rewrite_document_url(document.get("storage_url"))
            if storage_url:
                doc_lines = [f"- **[{document['filename']}]({storage_url})**"]
            else:
                doc_lines = [f"- **`{document['filename']}`**"]
            if document["document_type"]:
                doc_lines[0] += f" — {document['document_type']}"
            product_label = _product_label(document) or document["series_name"]
            if product_label:
                doc_lines.append(f"  Gerät: {product_label}")
            if document["manufacturer_name"]:
                doc_lines.append(f"  Hersteller: {document['manufacturer_name']}")
            lines.append("\n".join(doc_lines))

    return (
        "\n".join(lines),
        {
            "type": "video_lookup",
            "found": True,
            "scope": active_scope,
            "query": text,
            "search_terms": primary_terms,
            "signals": {
                "model": search_plan["model"],
                "issue_terms": search_plan["issue_terms"],
            },
            "videos": [
                _serialize_video_match(
                    row,
                    score=_video_row_relevance(
                        row,
                        primary_terms,
                        issue_terms=search_plan["issue_terms"],
                        expansion_terms=search_plan["expansion_terms"],
                    ),
                )
                for row in ordered_rows
            ],
            "related_documents": [_serialize_document_match(document) for document in related_documents],
        },
    )


async def _semantic_fast_lookup(pool, text: str, scope: dict[str, str] | None = None) -> str | None:
    """Embedding-based semantic search — no LLM, uses pgvector directly (~1.5 s)."""
    ollama_url = os.getenv("OLLAMA_URL", "http://krai-ollama-prod:11434")
    embed_model = os.getenv("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text:latest")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/embed",
                json={"model": embed_model, "input": text},
            )
            resp.raise_for_status()
            embedding = resp.json()["embeddings"][0]
    except Exception as exc:
        logger.warning("semantic_fast_lookup embed error: %s", exc)
        return None

    # Format embedding as pgvector literal
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    active_scope = normalize_scope(scope)
    try:
        async with pool.acquire() as conn:
            params: list[object] = [vec_literal]
            where_clauses = [
                "c.embedding IS NOT NULL",
                "c.processing_status = 'completed'",
            ]
            where_clauses.extend(
                build_scope_filters(
                    params,
                    active_scope,
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
            params.append(5)
            rows = await conn.fetch(
                f"""
                {_SEMANTIC_BASE_SQL}
                WHERE {' AND '.join(where_clauses)}
                ORDER BY c.id, c.embedding <=> $1::vector
                LIMIT ${len(params)}
                """,
                *params,
            )
    except Exception as exc:
        logger.warning("semantic_fast_lookup DB error: %s", exc)
        return None

    if not rows:
        return "**Keine relevanten Inhalte in den Service-Handbüchern gefunden.**"

    lines = [f"## 🔍 Suchergebnisse für: _{text[:80]}_\n"]
    if active_scope and _scope_label(active_scope):
        lines.append(f"_Scope: { _scope_label(active_scope) }_\n")
    for i, r in enumerate(rows, 1):
        doc = r["original_filename"] or r["filename"] or "Unbekanntes Dokument"
        page = f", Seite {r['page_start']}" if r["page_start"] else ""
        lines.append(f"### Ergebnis {i} — 📄 {doc}{page}")
        if _product_label(r) or r["series_name"]:
            lines.append(f"_Gerät: {_product_label(r) or r['series_name']}_")
        lines.append(r["text_chunk"][:600].strip())
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/models")
async def list_models(
    current_user: dict = Depends(require_permission("agent:chat")),
) -> dict:
    """List available KRAI models in OpenAI format."""
    llm_backend = os.getenv("LLM_BACKEND", "ollama").lower()
    if llm_backend == "openai":
        backend_model = os.getenv("OPENAI_MODEL", "gpt-4o")
    elif llm_backend == "openrouter":
        backend_model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    else:
        backend_model = os.getenv("OLLAMA_MODEL_CHAT") or os.getenv("OLLAMA_MODEL_TEXT", "llama3.2:latest")
    return {
        "object": "list",
        "data": [
            {
                "id": "krai",
                "object": "model",
                "created": 1700000000,
                "owned_by": "krai",
                "description": (
                    f"KRAI AI Agent — error codes, spare parts, service manuals "
                    f"(powered by {llm_backend}:{backend_model})"
                ),
            }
        ],
    }


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    current_user: dict = Depends(require_permission("agent:chat")),
):
    """OpenAI-compatible chat completions endpoint backed by the KRAI routing layer.

    Routing priority (fastest → slowest, all LLM-free except the last):
      1. Error-code pattern  → direct SQL on error_codes  (~300 ms)
      2. Parts keywords      → direct SQL on parts_catalog (~300 ms)
      3. Video keywords      → direct SQL on videos        (~300 ms)
      4. Everything else     → pgvector semantic search    (~1.5 s)
      5. Fallback            → LangGraph agent (needs LLM, with timeout)
    """
    agent = getattr(request.app.state, "krai_agent", None)

    session_id = _session_id(body.messages, body.user)
    content, images = _extract_last_user_content(body.messages)
    scope, reset_scope = extract_scope_from_openai_payload(
        body.scope,
        body.metadata,
        reset_scope=body.reset_scope,
    )
    if agent is not None and hasattr(agent, "resolve_session_scope"):
        active_scope = agent.resolve_session_scope(session_id, scope, reset_scope=reset_scope)
    else:
        active_scope = normalize_scope(scope)

    if not content:
        raise HTTPException(status_code=400, detail="No user message found in request")

    # ── Routing: SQL/embedding paths (no LLM, always fast) ──────────────────
    # Only applicable for plain-text, non-image messages.
    if not images and isinstance(content, str):
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None:
            preferred_keyword_route = _prefer_keyword_route(content)

            if preferred_keyword_route == "parts":
                result = await _parts_lookup(pool, content, active_scope)
                if result is not None:
                    logger.info("route=parts-preferred for: %.60s", content)
                    return _make_response(result, body.model)

            if preferred_keyword_route == "video":
                result = await _video_lookup(pool, content, active_scope)
                if result is not None:
                    logger.info("route=video-preferred for: %.60s", content)
                    result_text, krai_context = result
                    return _make_response(result_text, body.model, krai_context=krai_context)

            # 1. Error-code pattern → instant SQL (~300 ms)
            result = await _fast_path_lookup(pool, content, active_scope)
            if result is not None:
                logger.info("route=error_code for: %.60s", content)
                result_text, krai_context = result
                return _make_response(result_text, body.model, krai_context=krai_context)

            # 2. Spare-parts keywords → SQL parts_catalog (~300 ms)
            result = await _parts_lookup(pool, content, active_scope)
            if result is not None:
                logger.info("route=parts for: %.60s", content)
                return _make_response(result, body.model)

            # 3. Video/tutorial keywords → SQL videos (~300 ms)
            result = await _video_lookup(pool, content, active_scope)
            if result is not None:
                logger.info("route=video for: %.60s", content)
                result_text, krai_context = result
                return _make_response(result_text, body.model, krai_context=krai_context)

            # 4. Semantic search via pgvector (embed ~1 s + vector search ~0.5 s)
            if _should_use_semantic_fast_path(content):
                result = await _semantic_fast_lookup(pool, content, active_scope)
                if result is not None:
                    logger.info("route=semantic for: %.60s", content)
                    return _make_response(result, body.model)

    # ── Fallback: LangGraph agent (requires LLM — slow without GPU) ──────────
    if agent is None:
        return _make_response(
            "⚠️ KRAI Agent ist nicht verfügbar. Bitte versuche eine spezifischere "
            "Anfrage mit einem Fehlercode (z.B. `99.00.02`) oder Stichworten.",
            body.model,
        )

    _AGENT_TIMEOUT = int(os.getenv("KRAI_AGENT_TIMEOUT", "30"))  # noqa: N806  # function-scoped constant

    if body.stream:

        async def _gen() -> AsyncGenerator[str, None]:
            try:
                async with asyncio.timeout(_AGENT_TIMEOUT):
                    async for token in agent.chat_stream(
                        content,
                        session_id,
                        scope,
                        reset_scope=reset_scope,
                    ):
                        yield token
            except TimeoutError:
                yield "\n\n⚠️ *Antwort-Timeout. Bitte stelle eine spezifischere Frage.*"

        return StreamingResponse(
            _sse_stream(_gen(), body.model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        async with asyncio.timeout(_AGENT_TIMEOUT):
            response_text, _active_scope = await agent.chat(
                content,
                session_id,
                scope,
                reset_scope=reset_scope,
            )
    except TimeoutError:
        response_text = (
            "⚠️ **Timeout** — Die Anfrage hat zu lange gedauert.\n\n"
            "Versuche es mit einem Fehlercode (z.B. `99.00.02`), "
            "einem Ersatzteil-Stichwort oder einem Video-Begriff."
        )
    return _make_response(response_text, body.model)
