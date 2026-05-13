"""Shared scope and query helpers for the KRAI agent."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, Field

CURRENT_AGENT_SCOPE: ContextVar[dict[str, str] | None] = ContextVar(
    "current_agent_scope",
    default=None,
)


class AgentScope(BaseModel):
    """Optional machine/product scope attached to a chat session."""

    manufacturer: str | None = Field(default=None, description="Manufacturer name")
    product: str | None = Field(default=None, description="Product model or machine name")
    product_id: str | None = Field(default=None, description="Product UUID")
    series: str | None = Field(default=None, description="Product series name")
    document_id: str | None = Field(default=None, description="Document UUID")


def extract_scope_from_openai_payload(
    explicit_scope: AgentScope | Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    *,
    reset_scope: bool = False,
) -> tuple[AgentScope | None, bool]:
    """Extract an agent scope from OpenAI/OpenWebUI-compatible request payloads."""

    payload = dict(metadata or {})
    scope_candidate = explicit_scope or payload.get("scope") or payload.get("krai_scope")
    resolved_reset = reset_scope or bool(payload.get("reset_scope", False))

    if isinstance(scope_candidate, AgentScope):
        return scope_candidate, resolved_reset

    if isinstance(scope_candidate, Mapping):
        return AgentScope(**scope_candidate), resolved_reset

    return None, resolved_reset


def normalize_scope(scope: AgentScope | Mapping[str, Any] | None) -> dict[str, str]:
    """Drop empty values and normalize whitespace."""

    if scope is None:
        return {}

    raw_scope = scope.model_dump(exclude_none=True) if isinstance(scope, AgentScope) else dict(scope)
    normalized: dict[str, str] = {}

    for key, value in raw_scope.items():
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned:
            normalized[key] = cleaned

    return normalized


def merge_scope(
    existing: AgentScope | Mapping[str, Any] | None,
    incoming: AgentScope | Mapping[str, Any] | None,
    *,
    reset: bool = False,
) -> dict[str, str]:
    """Merge session scope updates and clear dependent fields when parents change."""

    current = normalize_scope(existing)
    update = normalize_scope(incoming)

    if reset:
        return update

    merged = dict(current)

    if "manufacturer" in update and update["manufacturer"] != current.get("manufacturer"):
        merged.pop("product", None)
        merged.pop("product_id", None)
        merged.pop("series", None)
        merged.pop("document_id", None)
    elif "product" in update and update["product"] != current.get("product"):
        merged.pop("product_id", None)
        merged.pop("document_id", None)
    elif "series" in update and update["series"] != current.get("series"):
        merged.pop("document_id", None)

    merged.update(update)
    return merged


def build_scope_system_message(scope: Mapping[str, str] | None) -> str | None:
    """Create a short system hint for the active session scope."""

    active_scope = normalize_scope(scope)
    if not active_scope:
        return None

    labels = {
        "manufacturer": "Hersteller",
        "product": "Produkt",
        "product_id": "Produkt-ID",
        "series": "Serie",
        "document_id": "Dokument-ID",
    }
    parts = [f"{labels[key]}: {value}" for key, value in active_scope.items() if key in labels]
    joined = "; ".join(parts)
    return (
        "Aktiver Gerätekontext für diese Session: "
        f"{joined}. Nutze diesen Scope bei allen Suchen automatisch und antworte bevorzugt "
        "mit Treffern für genau dieses Gerät."
    )


def extract_error_search_term(query: str) -> str:
    """Extract the most likely error code from free-form user input."""

    patterns = [
        r"\b[A-Z0-9]{1,4}(?:[.\-][A-Z0-9]{1,4}){1,5}\b",
        r"\b[A-Z]{1,3}[-]?\d{3,6}\b",
        r"\b\d{2,}(?:\.\d+)+\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(0).upper()

    return query.strip()


def build_error_code_variants(search_term: str) -> list[str]:
    """Generate normalized lookup variants for an extracted error code."""

    variants: list[str] = []

    def add_variant(value: str) -> None:
        cleaned = value.strip().upper()
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    add_variant(search_term)
    add_variant(search_term.replace("-", ""))
    add_variant(search_term.replace(".", ""))
    add_variant(search_term.replace("-", "").replace(".", ""))

    return variants


def build_scope_filters(
    params: list[Any],
    scope: Mapping[str, str] | None,
    *,
    manufacturer_templates: Sequence[str] = (),
    product_templates: Sequence[str] = (),
    product_id_template: str | None = None,
    series_templates: Sequence[str] = (),
    document_id_template: str | None = None,
) -> list[str]:
    """Build SQL scope filters with asyncpg-style numbered placeholders."""

    active_scope = normalize_scope(scope)
    clauses: list[str] = []

    if active_scope.get("manufacturer") and manufacturer_templates:
        clauses.append(_append_template_group(params, manufacturer_templates, f"%{active_scope['manufacturer']}%"))

    if active_scope.get("product") and product_templates:
        clauses.append(_append_template_group(params, product_templates, f"%{active_scope['product']}%"))

    if active_scope.get("series") and series_templates:
        clauses.append(_append_template_group(params, series_templates, f"%{active_scope['series']}%"))

    if active_scope.get("product_id") and product_id_template:
        params.append(active_scope["product_id"])
        clauses.append(product_id_template.format(index=len(params)))

    if active_scope.get("document_id") and document_id_template:
        params.append(active_scope["document_id"])
        clauses.append(document_id_template.format(index=len(params)))

    return clauses


def _append_template_group(params: list[Any], templates: Sequence[str], value: str) -> str:
    group: list[str] = []
    for template in templates:
        params.append(value)
        group.append(template.format(index=len(params)))
    return f"({' OR '.join(group)})"
