"""Tests for document_processing router."""

from __future__ import annotations

import ast
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]


def _stub_modules():
    """Register minimal stubs so document_processing.py can be imported without full app."""
    # Top-level package stubs with __path__ so sub-modules resolve
    for name, path_fragment in [
        ("api", "api"),
        ("api.routes", "api/routes"),
        ("api.dependencies", "api/dependencies"),
        ("api.middleware", "api/middleware"),
        ("services", "services"),
        ("processors", "processors"),
        ("core", "core"),
    ]:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(ROOT / path_fragment)]
        sys.modules.setdefault(name, pkg)

    # auth_middleware stub
    auth_mod = types.ModuleType("api.middleware.auth_middleware")
    auth_mod.require_permission = lambda _perm: (lambda: {"id": "test"})
    sys.modules["api.middleware.auth_middleware"] = auth_mod

    # api.dependencies.database stub (avoids deep services import chain)
    db_dep_mod = types.ModuleType("api.dependencies.database")
    db_dep_mod.get_database_pool = lambda: None
    sys.modules["api.dependencies.database"] = db_dep_mod

    # asyncpg stub — needs Pool attribute so FastAPI can resolve type annotations
    asyncpg_mod = types.ModuleType("asyncpg")
    asyncpg_mod.Pool = type("Pool", (), {})  # minimal class stub
    sys.modules["asyncpg"] = asyncpg_mod

    # models.document stub with CANONICAL_STAGES
    models_pkg = types.ModuleType("models")
    models_pkg.__path__ = [str(ROOT / "models")]
    sys.modules.setdefault("models", models_pkg)

    doc_mod = types.ModuleType("models.document")
    doc_mod.CANONICAL_STAGES = [
        "upload",
        "text_extraction",
        "table_extraction",
        "svg_processing",
        "image_processing",
        "visual_embedding",
        "link_extraction",
        "chunk_prep",
        "classification",
        "metadata_extraction",
        "parts_extraction",
        "series_detection",
        "storage",
        "embedding",
        "search_indexing",
    ]
    sys.modules["models.document"] = doc_mod

    video_mod = types.ModuleType("services.video_enrichment_service")

    class VideoEnrichmentService:
        async def enrich_video_url(self, url: str, document_id: str | None = None, manufacturer_id: str | None = None):
            return {
                "video_id": "stub-video",
                "title": "Stub",
                "platform": "youtube",
                "thumbnail_url": "https://example.test/thumb.png",
                "duration": 0,
                "channel_title": "Stub Channel",
            }

    video_mod.VideoEnrichmentService = VideoEnrichmentService
    sys.modules["services.video_enrichment_service"] = video_mod

    thumb_mod = types.ModuleType("processors.thumbnail_processor")

    class ThumbnailProcessor:
        def __init__(self, *_args, **_kwargs):
            pass

        async def process(self, _context):
            return types.SimpleNamespace(
                success=True,
                data={"thumbnail_url": "https://example.test/thumb.png", "file_size": 1},
                error=None,
            )

    thumb_mod.ThumbnailProcessor = ThumbnailProcessor
    sys.modules["processors.thumbnail_processor"] = thumb_mod

    core_types_mod = types.ModuleType("core.types")

    @dataclass
    class ProcessingContext:
        document_id: str
        file_path: str
        document_type: str
        manufacturer: str | None = None
        model: str | None = None
        series: str | None = None
        version: str | None = None
        language: str = "en"
        processing_config: dict | None = None
        file_hash: str | None = None

        def __post_init__(self):
            if self.processing_config is None:
                self.processing_config = {}

    core_types_mod.ProcessingContext = ProcessingContext
    sys.modules["core.types"] = core_types_mod


# Run once at module import time so tests don't clobber sys.modules on each call
_stub_modules()


def test_router_imports_cleanly():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "api.routes.document_processing",
        ROOT / "api" / "routes" / "document_processing.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from fastapi import APIRouter

    assert hasattr(mod, "router")
    assert mod.router is not None
    assert isinstance(mod.router, APIRouter)


def _make_test_app():
    """Create a minimal FastAPI app with the document_processing router and a mock pool."""
    from api.routes.document_processing import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    async def override_pool():
        return mock_pool

    from api.dependencies.database import get_database_pool

    app.dependency_overrides[get_database_pool] = override_pool
    app.state.pipeline = MagicMock()
    app.state.storage_service = MagicMock()
    app.state.db_adapter = MagicMock()
    return app, mock_conn


@pytest.mark.asyncio
async def test_get_stages_names_returns_canonical_list():
    app, _ = _make_test_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stages/names",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"]["stages"], list)
    assert len(body["data"]["stages"]) > 0
    assert body["data"]["total"] == len(body["data"]["stages"])


@pytest.mark.asyncio
async def test_get_document_status_returns_success_response():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "id": "doc-123",
            "processing_status": "completed",
            "stage_status": json.dumps({"embedding": "completed", "text_extraction": "completed"}),
        }
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/documents/doc-123/status",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "completed"
    assert body["data"]["document_id"] == "doc-123"
    assert "current_stage" in body["data"]
    assert "progress" in body["data"]


@pytest.mark.asyncio
async def test_get_document_status_returns_stage_summary():
    """Response must include a per-status count of stages from stage_status JSONB.
    Handles both flat strings (legacy) and structured payloads (new)."""
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "id": "doc-123",
            "processing_status": "processing",
            "stage_status": json.dumps(
                {
                    "text_extraction": {"status": "completed"},
                    "embedding": {"status": "processing"},
                    "image_processing": "completed",  # legacy flat string
                    "table_extraction": {"status": "failed", "message": "boom"},
                    "storage": {"status": "skipped"},
                }
            ),
        }
    )
    mock_conn.fetchval = AsyncMock(return_value=0)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/documents/doc-123/status",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    summary = body["data"]["stage_summary"]
    assert summary["completed"] == 2  # text_extraction + image_processing
    assert summary["processing"] == 1  # embedding
    assert summary["failed"] == 1  # table_extraction
    assert summary["skipped"] == 1  # storage
    assert summary["total"] >= 5  # at least the explicitly tracked stages
    assert summary["pending"] >= 0


@pytest.mark.asyncio
async def test_get_document_status_includes_real_queue_position():
    """Queue position must be queried from krai_system.processing_queue,
    not hardcoded to 0."""
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "id": "doc-123",
            "processing_status": "processing",
            "stage_status": json.dumps({"text_extraction": "completed"}),
        }
    )
    # Mock processing_queue queries: queue_position = 2, total_queue_items = 5
    mock_conn.fetchval = AsyncMock(side_effect=[2, 5])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/documents/doc-123/status",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["queue_position"] == 2
    assert body["data"]["total_queue_items"] == 5


@pytest.mark.asyncio
async def test_get_document_status_404_when_not_found():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/documents/missing-id/status",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_document_returns_pending():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    mock_conn.execute = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.run_stages = AsyncMock(return_value={})
    app.state.pipeline = mock_pipeline
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/reprocess",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "pending"
    assert body["data"]["document_id"] == "doc-123"
    # Verify pipeline was actually triggered with all canonical stages
    mock_pipeline.run_stages.assert_called_once()
    call_args = mock_pipeline.run_stages.call_args
    assert call_args[0][0] == "doc-123"
    assert isinstance(call_args[0][1], list)
    assert len(call_args[0][1]) > 0


@pytest.mark.asyncio
async def test_reprocess_document_404_when_not_found():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/missing/reprocess",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_process_single_stage_valid_stage():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    mock_pipeline = AsyncMock()
    mock_pipeline.run_stages = AsyncMock(return_value={})
    app.state.pipeline = mock_pipeline
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stage/embedding",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["stage"] == "embedding"
    assert body["data"]["status"] == "queued"
    # Verify only the requested stage was queued
    mock_pipeline.run_stages.assert_called_once()
    call_args = mock_pipeline.run_stages.call_args
    assert call_args[0][0] == "doc-123"
    assert call_args[0][1] == ["embedding"]


@pytest.mark.asyncio
async def test_process_single_stage_invalid_stage_returns_400():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stage/nonexistent_stage",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_process_multiple_stages_returns_stage_results():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    mock_pipeline = MagicMock()
    mock_pipeline.run_stages = AsyncMock(
        return_value={
            "success": True,
            "total_stages": 2,
            "successful": 2,
            "failed": 0,
            "success_rate": 100.0,
            "stage_results": [
                {"stage": "text_extraction", "success": True, "processing_time": 1.1, "data": {}},
                {"stage": "embedding", "success": True, "processing_time": 2.2, "data": {}},
            ],
        }
    )
    app.state.pipeline = mock_pipeline
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stages",
            json={"stages": ["text_extraction", "embedding"], "stop_on_error": True},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_stages"] == 2
    assert len(body["data"]["stage_results"]) == 2
    assert body["data"]["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_process_multiple_stages_defaults_missing_processing_time_to_zero():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    mock_pipeline = MagicMock()
    mock_pipeline.run_stages = AsyncMock(
        return_value={
            "success": False,
            "total_stages": 1,
            "successful": 0,
            "failed": 1,
            "success_rate": 0.0,
            "stage_results": [
                {"stage": "text_extraction", "success": False, "error": "boom"},
            ],
        }
    )
    app.state.pipeline = mock_pipeline
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stages",
            json={"stages": ["text_extraction"], "stop_on_error": True},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["failed"] == 1
    assert body["data"]["stage_results"][0]["processing_time"] == 0.0


@pytest.mark.asyncio
async def test_process_multiple_stages_defaults_missing_stage_name_from_request_order():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    mock_pipeline = MagicMock()
    mock_pipeline.run_stages = AsyncMock(
        return_value={
            "success": False,
            "total_stages": 1,
            "successful": 0,
            "failed": 1,
            "success_rate": 0.0,
            "stage_results": [
                {"success": False, "error": "No processor for stage: text_extraction"},
            ],
        }
    )
    app.state.pipeline = mock_pipeline
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stages",
            json={"stages": ["text_extraction"], "stop_on_error": True},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["stage_results"][0]["stage"] == "text_extraction"
    assert body["data"]["stage_results"][0]["processing_time"] == 0.0


@pytest.mark.asyncio
async def test_process_multiple_stages_rejects_invalid_stage():
    app, _ = _make_test_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/documents/doc-123/process/stages",
            json={"stages": ["fake_stage"], "stop_on_error": True},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_process_video_returns_video_metadata():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(return_value={"id": "doc-123"})
    with patch("api.routes.document_processing.VideoEnrichmentService") as mock_video_service_class:
        mock_video_service = MagicMock()
        mock_video_service.enrich_video_url = AsyncMock(
            return_value={
                "video_id": "vid-1",
                "title": "Test",
                "platform": "youtube",
                "thumbnail_url": "https://img",
                "duration": 120,
                "channel_title": "Chan",
            }
        )
        mock_video_service_class.return_value = mock_video_service
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/documents/doc-123/process/video",
                json={"video_url": "https://youtube.com/watch?v=abc", "manufacturer_id": None},
                headers={"Authorization": "Bearer test-token"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["platform"] == "youtube"


@pytest.mark.asyncio
async def test_process_thumbnail_returns_url():
    app, mock_conn = _make_test_app()
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "id": "doc-123",
            "storage_path": "/docs/test.pdf",
            "document_type": "service_manual",
        }
    )
    with patch("api.routes.document_processing.ThumbnailProcessor") as mock_thumbnail_processor_class:
        mock_processor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {
            "thumbnail_url": "https://minio/thumbnails/doc-123.png",
            "file_size": 48000,
            "size": [300, 400],
        }
        mock_result.error = None
        mock_processor.process = AsyncMock(return_value=mock_result)
        mock_thumbnail_processor_class.return_value = mock_processor
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/documents/doc-123/process/thumbnail",
                json={"size": [300, 400], "page": 0},
                headers={"Authorization": "Bearer test-token"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["thumbnail_url"] == "https://minio/thumbnails/doc-123.png"
    assert body["data"]["file_size"] == 48000


def test_upload_endpoint_accepts_language_form_param():
    """The /upload endpoint must accept optional multipart context fields."""
    app_path = ROOT / "api" / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    upload_fn = next(
        (node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "upload_document"),
        None,
    )

    assert upload_fn is not None, "upload_document function not found in app.py"

    fn_source = ast.get_source_segment(source, upload_fn) or ""
    assert 'document_type: str = Form("service_manual")' in fn_source
    assert 'language: str = Form("en")' in fn_source
    assert "manufacturer: str | None = Form(None)" in fn_source
    assert "series: str | None = Form(None)" in fn_source
    assert "model: str | None = Form(None)" in fn_source
    assert "force_reprocess: bool = Form(False)" in fn_source
    assert 'language=language or "en"' in fn_source
    assert "manufacturer=manufacturer or None" in fn_source
    assert "series=series or None" in fn_source
    assert "model=model or None" in fn_source


def test_legacy_documents_stage_response_casts_document_id_to_string():
    source = (ROOT / "api" / "routes" / "documents.py").read_text(encoding="utf-8")

    assert 'document_id=str(doc["id"])' in source
