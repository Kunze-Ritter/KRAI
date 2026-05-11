"""Tests for the /api/v1/monitoring/pipeline-activity endpoint contract.

Verifies the SQL constants query only tables we know exist (no dependency on
removed views/materialized views) and the response-shape helper produces a
contract that matches the Laravel side.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ensure_stubs() -> None:
    """Stub heavy services so monitoring_api can import."""
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    for name, path_fragment in [
        ("api", "api"),
        ("api.routes", "api/routes"),
        ("api.middleware", "api/middleware"),
        ("services", "services"),
        ("models", "models"),
    ]:
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(ROOT / path_fragment)]
            sys.modules[name] = pkg

    if "api.middleware.auth_middleware" not in sys.modules:
        auth_mod = types.ModuleType("api.middleware.auth_middleware")
        auth_mod.require_permission = lambda _perm: (lambda: {"id": "test"})
        sys.modules["api.middleware.auth_middleware"] = auth_mod

    if "services.alert_service" not in sys.modules:
        alert_mod = types.ModuleType("services.alert_service")

        class AlertService:
            pass

        alert_mod.AlertService = AlertService
        sys.modules["services.alert_service"] = alert_mod

    if "services.metrics_service" not in sys.modules:
        metrics_mod = types.ModuleType("services.metrics_service")

        class MetricsService:
            pass

        metrics_mod.MetricsService = MetricsService
        sys.modules["services.metrics_service"] = metrics_mod

    if "services.performance_service" not in sys.modules:
        perf_mod = types.ModuleType("services.performance_service")

        class PerformanceCollector:
            pass

        perf_mod.PerformanceCollector = PerformanceCollector
        sys.modules["services.performance_service"] = perf_mod


def _load_monitoring_module():
    _ensure_stubs()
    import importlib

    return importlib.import_module("api.monitoring_api")


def test_sql_constants_target_only_existing_tables():
    """Plan Task 6 explicitly requires we not depend on krai_core.stage_status or
    materialized views that may not exist."""
    mon = _load_monitoring_module()

    for sql in (mon.ACTIVE_DOCUMENTS_SQL, mon.RECENT_ACTIVITY_SQL, mon.RECENT_FAILURES_SQL):
        assert "krai_core.stage_status" not in sql
        assert "vw_" not in sql.lower()
        assert "MATERIALIZED VIEW" not in sql.upper()


def test_active_documents_sql_targets_documents_table():
    mon = _load_monitoring_module()
    sql = mon.ACTIVE_DOCUMENTS_SQL
    assert "FROM krai_core.documents" in sql
    assert "processing_status" in sql
    assert "stage_status" in sql
    assert "$1" in sql  # parameterized limit


def test_recent_activity_sql_targets_stage_tracking():
    mon = _load_monitoring_module()
    sql = mon.RECENT_ACTIVITY_SQL
    assert "FROM krai_system.stage_tracking" in sql
    assert "$1" in sql


def test_recent_failures_sql_targets_pipeline_errors():
    mon = _load_monitoring_module()
    sql = mon.RECENT_FAILURES_SQL
    assert "FROM krai_system.pipeline_errors" in sql
    assert "$1" in sql


def test_derive_current_stage_from_structured_payload():
    mon = _load_monitoring_module()
    current_stage, progress = mon._derive_current_stage_and_progress(
        {
            "text_extraction": {"status": "completed"},
            "embedding": {"status": "processing"},
            "storage": {"status": "pending"},
        }
    )
    assert current_stage == "embedding"
    assert progress == 0.3333  # round(1/3, 4)


def test_derive_current_stage_from_legacy_flat_strings():
    mon = _load_monitoring_module()
    current_stage, progress = mon._derive_current_stage_and_progress(
        {
            "text_extraction": "completed",
            "embedding": "failed",
        }
    )
    # 'failed' counts as not-complete, so it becomes current_stage
    assert current_stage == "embedding"
    assert progress == 0.5


def test_derive_current_stage_handles_json_string_input():
    """documents.stage_status may arrive as a JSON-encoded string."""
    mon = _load_monitoring_module()
    current_stage, progress = mon._derive_current_stage_and_progress(
        '{"text_extraction": {"status": "completed"}, "embedding": {"status": "processing"}}'
    )
    assert current_stage == "embedding"
    assert progress == 0.5


def test_derive_current_stage_handles_empty_or_invalid():
    mon = _load_monitoring_module()
    assert mon._derive_current_stage_and_progress(None) == (None, 0.0)
    assert mon._derive_current_stage_and_progress({}) == (None, 0.0)
    assert mon._derive_current_stage_and_progress("not-json") == (None, 0.0)


def test_pipeline_activity_response_model_has_required_fields():
    """Laravel side reads pipeline_metrics, active_documents, recent_activity, recent_failures."""
    _ensure_stubs()
    import importlib

    monitoring_models = importlib.import_module("models.monitoring")
    fields = set(monitoring_models.PipelineActivityResponse.model_fields.keys())

    assert {
        "pipeline_metrics",
        "active_documents",
        "recent_activity",
        "recent_failures",
        "timestamp",
    } <= fields
