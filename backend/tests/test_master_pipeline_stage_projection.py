"""Tests for structured stage_status projection helpers.

Verifies the contract used by KRMasterPipeline.track_stage_status to project
stage transitions into krai_core.documents.stage_status (structured JSONB per
plan docs/superpowers/plans/2026-03-25-document-status-and-lifecycle-refactor.md).

The helpers live in backend.pipeline.stage_projection so the tests don't drag
in master_pipeline's full import tree.
"""

# ruff: noqa: E402  # imports follow sys.path.insert below

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))


from backend.pipeline.stage_projection import (
    STAGE_PROJECTION_SQL,
    build_stage_detail,
    derive_document_processing_status,
)

# ---------- STAGE_PROJECTION_SQL contract ----------


def test_stage_projection_sql_updates_documents_stage_and_processing_status():
    assert "UPDATE krai_core.documents" in STAGE_PROJECTION_SQL
    assert "stage_status" in STAGE_PROJECTION_SQL
    assert "processing_status" in STAGE_PROJECTION_SQL
    # Uses bind params, not string interpolation
    assert "$1" in STAGE_PROJECTION_SQL
    assert "$2" in STAGE_PROJECTION_SQL
    assert "$3" in STAGE_PROJECTION_SQL


# ---------- build_stage_detail ----------


def test_build_stage_detail_running_sets_started_at_and_no_completed_at():
    detail = build_stage_detail(new_status="running", existing_entry=None, error_message=None)
    assert detail["status"] == "processing"  # 'running' normalizes to 'processing'
    assert detail["started_at"] is not None
    assert detail["completed_at"] is None
    assert detail["processing_time"] is None
    assert detail["message"] is None


def test_build_stage_detail_completed_preserves_started_at_and_computes_processing_time():
    existing = {
        "status": "processing",
        "started_at": "2026-03-25T12:00:00",
        "completed_at": None,
        "processing_time": None,
        "message": None,
    }
    detail = build_stage_detail(new_status="completed", existing_entry=existing, error_message=None)
    assert detail["status"] == "completed"
    assert detail["started_at"] == "2026-03-25T12:00:00"
    assert detail["completed_at"] is not None
    assert isinstance(detail["processing_time"], float)
    assert detail["processing_time"] >= 0


def test_build_stage_detail_failed_records_message():
    detail = build_stage_detail(
        new_status="failed",
        existing_entry={"status": "processing", "started_at": "2026-03-25T12:00:00"},
        error_message="boom",
    )
    assert detail["status"] == "failed"
    assert detail["message"] == "boom"
    assert detail["completed_at"] is not None


def test_build_stage_detail_skipped_marks_completed_at():
    detail = build_stage_detail(new_status="skipped", existing_entry=None, error_message=None)
    assert detail["status"] == "skipped"
    assert detail["completed_at"] is not None


def test_build_stage_detail_tolerates_legacy_string_existing_entry():
    """If existing_entry is a flat string (legacy), still produce a structured payload."""
    detail = build_stage_detail(
        new_status="completed",
        existing_entry="processing",
        error_message=None,
    )
    assert detail["status"] == "completed"
    # No started_at available from legacy string → processing_time stays None
    assert detail["processing_time"] is None


# ---------- derive_document_processing_status ----------


def test_derive_document_processing_status_failed_wins():
    result = derive_document_processing_status(
        {
            "text_extraction": {"status": "completed"},
            "embedding": {"status": "failed"},
            "storage": {"status": "completed"},
        }
    )
    assert result == "failed"


def test_derive_document_processing_status_all_completed_or_skipped():
    result = derive_document_processing_status(
        {
            "text_extraction": {"status": "completed"},
            "video_enrichment": {"status": "skipped"},
            "storage": {"status": "completed"},
        }
    )
    assert result == "completed"


def test_derive_document_processing_status_any_active_means_processing():
    result = derive_document_processing_status(
        {
            "text_extraction": {"status": "completed"},
            "embedding": {"status": "processing"},
            "storage": {"status": "pending"},
        }
    )
    assert result == "processing"


def test_derive_document_processing_status_running_alias_treated_as_processing():
    result = derive_document_processing_status(
        {
            "text_extraction": {"status": "running"},
        }
    )
    assert result == "processing"


def test_derive_document_processing_status_empty_is_pending():
    assert derive_document_processing_status({}) == "pending"
    assert derive_document_processing_status(None) == "pending"


def test_derive_document_processing_status_tolerates_legacy_flat_strings():
    """Backward compat: callers may pass {stage: 'completed'} flat-string entries."""
    result = derive_document_processing_status(
        {
            "text_extraction": "completed",
            "embedding": "failed",
        }
    )
    assert result == "failed"


def test_derive_document_processing_status_partial_progress_is_processing():
    """At least one completed/skipped + others pending → processing."""
    result = derive_document_processing_status(
        {
            "text_extraction": {"status": "completed"},
            "embedding": {"status": "pending"},
        }
    )
    assert result == "processing"
