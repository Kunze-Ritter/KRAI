"""Stage status projection helpers (extracted from master_pipeline for testability).

The pipeline persists per-stage status in two places:
  - krai_system.stage_tracking  : append-only execution log (one row per stage)
  - krai_core.documents.stage_status (JSONB) : current state projection
    consumed directly by the Filament UI.

This module owns the projection contract:
  * STAGE_PROJECTION_SQL      — the atomic UPDATE statement
  * build_stage_detail(...)   — structured per-stage JSON entry
  * derive_document_processing_status(...) — document-level rollup

See docs/superpowers/plans/2026-03-25-document-status-and-lifecycle-refactor.md
for the schema rationale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

STAGE_PROJECTION_SQL = """
UPDATE krai_core.documents
SET
    stage_status = $2::jsonb,
    processing_status = $3::text,
    updated_at = NOW()
WHERE id = $1::uuid
"""


_ACTIVE_STATES = {"processing", "running"}
_TERMINAL_OK_STATES = {"completed", "skipped"}


def _entry_status(entry: Any) -> str:
    if isinstance(entry, dict):
        status = entry.get("status", "")
    else:
        status = str(entry or "")
    return "processing" if status == "running" else status


def derive_document_processing_status(stage_status: dict[str, Any] | None) -> str:
    """Derive document-level processing_status from a merged stage_status map.

    Priority: failed > processing > completed > pending.
    """
    if not stage_status:
        return "pending"

    statuses = [_entry_status(value) for value in stage_status.values()]

    if any(s == "failed" for s in statuses):
        return "failed"

    if any(s in _ACTIVE_STATES for s in statuses):
        return "processing"

    terminal_ok = sum(1 for s in statuses if s in _TERMINAL_OK_STATES)
    if terminal_ok == len(statuses):
        return "completed"

    if terminal_ok > 0:
        return "processing"

    return "pending"


def build_stage_detail(
    new_status: str,
    existing_entry: Any,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build the structured per-stage payload that goes into stage_status JSONB.

    Schema:
        {"status": str, "started_at": iso|None, "completed_at": iso|None,
         "processing_time": float|None, "message": str|None}

    Normalizes legacy 'running' → 'processing'. Preserves existing started_at on
    transitions to a terminal state; computes processing_time as elapsed seconds.
    """
    normalized_status = "processing" if new_status == "running" else new_status

    existing_started_at: str | None = None
    if isinstance(existing_entry, dict):
        existing_started_at = existing_entry.get("started_at")

    now_iso = datetime.utcnow().replace(microsecond=0).isoformat()

    if normalized_status == "processing":
        started_at: str | None = existing_started_at or now_iso
    else:
        started_at = existing_started_at

    completed_at: str | None = now_iso if normalized_status in ("completed", "failed", "skipped") else None

    processing_time: float | None = None
    if completed_at and started_at:
        try:
            start_dt = datetime.fromisoformat(started_at.rstrip("Z"))
            processing_time = max(0.0, (datetime.utcnow() - start_dt).total_seconds())
        except (ValueError, AttributeError):
            processing_time = None

    return {
        "status": normalized_status,
        "started_at": started_at,
        "completed_at": completed_at,
        "processing_time": processing_time,
        "message": error_message,
    }
