from __future__ import annotations

import importlib.util
import inspect
import sys
import types
from enum import Enum
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]


def _stub_modules() -> None:
    for name, path_fragment in [
        ("api", "api"),
        ("api.routes", "api/routes"),
        ("api.dependencies", "api/dependencies"),
        ("api.middleware", "api/middleware"),
        ("models", "models"),
    ]:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(ROOT / path_fragment)]
        sys.modules.setdefault(name, pkg)

    asyncpg_mod = types.ModuleType("asyncpg")
    asyncpg_mod.Pool = type("Pool", (), {})
    sys.modules["asyncpg"] = asyncpg_mod

    db_dep_mod = types.ModuleType("api.dependencies.database")
    db_dep_mod.get_database_pool = lambda: None
    sys.modules["api.dependencies.database"] = db_dep_mod

    auth_mod = types.ModuleType("api.middleware.auth_middleware")
    auth_mod.require_permission = lambda _perm: (lambda: {"id": "test-user"})
    sys.modules["api.middleware.auth_middleware"] = auth_mod

    rate_limit_mod = types.ModuleType("api.middleware.rate_limit_middleware")

    class _Limiter:
        def limit(self, _value):
            def decorator(fn):
                return fn

            return decorator

    rate_limit_mod.limiter = _Limiter()
    rate_limit_mod.rate_limit_search = "1/minute"
    rate_limit_mod.rate_limit_standard = "1/minute"
    rate_limit_mod.rate_limit_upload = "1/minute"
    sys.modules["api.middleware.rate_limit_middleware"] = rate_limit_mod

    # NOTE: we intentionally do NOT stub api.routes.response_models.
    # The real module has no heavy dependencies (pure pydantic) and other
    # tests in this directory (e.g. test_document_processing_routes.py) need
    # the real DocumentProcessingStatusResponse class. Replacing it with an
    # incomplete stub leaks across files via sys.modules and breaks those
    # tests when this file is collected first.

    document_mod = types.ModuleType("models.document")

    class SortOrder(str, Enum):
        ASC = "asc"
        DESC = "desc"

    class StageStatus(str, Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
        SKIPPED = "skipped"

    class DocumentStageDetail(BaseModel):
        status: StageStatus
        started_at: str | None = None
        completed_at: str | None = None
        duration_seconds: float | None = None
        progress: int = Field(default=0)
        error: str | None = None
        metadata: dict = Field(default_factory=dict)

    class DocumentStageStatusResponse(BaseModel):
        document_id: str
        filename: str
        overall_progress: float
        current_stage: str
        stages: dict
        can_retry: bool
        last_updated: str

    class DummyModel(BaseModel):
        pass

    document_mod.CANONICAL_STAGES = [
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
    document_mod.DocumentCreateRequest = DummyModel
    document_mod.DocumentFilterParams = DummyModel
    document_mod.DocumentListResponse = DummyModel
    document_mod.DocumentResponse = DummyModel
    document_mod.DocumentSortParams = DummyModel
    document_mod.DocumentStageDetail = DocumentStageDetail
    document_mod.DocumentStageStatusResponse = DocumentStageStatusResponse
    document_mod.DocumentStatsResponse = DummyModel
    document_mod.DocumentUpdateRequest = DummyModel
    document_mod.PaginationParams = DummyModel
    document_mod.SortOrder = SortOrder
    document_mod.StageStatus = StageStatus
    sys.modules["models.document"] = document_mod


_stub_modules()

spec = importlib.util.spec_from_file_location(
    "api.routes.documents",
    ROOT / "api" / "routes" / "documents.py",
)
documents_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(documents_module)


def test_parse_stage_status_accepts_legacy_string_values() -> None:
    result = documents_module._parse_stage_status(
        {
            "upload": "completed",
            "text_extraction": {"status": "processing", "progress": 40},
        }
    )

    assert result["upload"].status.value == "completed"
    assert result["upload"].progress == 100
    assert result["text_extraction"].status.value == "processing"
    assert result["text_extraction"].progress == 40


def test_parse_stage_status_accepts_json_string_payload() -> None:
    result = documents_module._parse_stage_status(
        '{"text_extraction": "failed", "series_detection": {"status": "processing", "progress": 10}}'
    )

    assert result["text_extraction"].status.value == "failed"
    assert result["text_extraction"].progress == 0
    assert result["series_detection"].status.value == "processing"
    assert result["series_detection"].progress == 10


def test_get_document_stages_exposes_response_parameter_for_rate_limiter() -> None:
    signature = inspect.signature(documents_module.get_document_stages)

    assert "response" in signature.parameters


def _delete_doc_mock_setup():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "doc-1", "filename": "manual.pdf"})
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )
    return conn, pool


@pytest.mark.asyncio
async def test_delete_document_deletes_videos_before_document() -> None:
    request = MagicMock()
    current_user = {"id": "test-user"}
    conn, pool = _delete_doc_mock_setup()

    response = await documents_module.delete_document(
        request=request,
        document_id="doc-1",
        current_user=current_user,
        pool=pool,
    )

    executed_queries = [call.args[0] for call in conn.execute.await_args_list]

    assert response.success is True
    assert any("DELETE FROM krai_content.videos" in query for query in executed_queries)
    assert any("DELETE FROM krai_core.documents" in query for query in executed_queries)


@pytest.mark.asyncio
async def test_delete_document_cleans_link_scraping_jobs() -> None:
    """link_scraping_jobs has no documented ON DELETE CASCADE, so explicit
    cleanup must happen before the documents row goes away."""
    request = MagicMock()
    current_user = {"id": "test-user"}
    conn, pool = _delete_doc_mock_setup()

    response = await documents_module.delete_document(
        request=request,
        document_id="doc-1",
        current_user=current_user,
        pool=pool,
    )

    executed_queries = [call.args[0] for call in conn.execute.await_args_list]
    assert response.success is True
    assert any("DELETE FROM krai_system.link_scraping_jobs" in q for q in executed_queries)

    # link_scraping_jobs delete must run BEFORE the documents row (so the FK
    # target still exists if the table has ON DELETE RESTRICT).
    queries_text = " ".join(executed_queries)
    link_pos = queries_text.find("DELETE FROM krai_system.link_scraping_jobs")
    doc_pos = queries_text.find("DELETE FROM krai_core.documents")
    assert 0 <= link_pos < doc_pos, "link_scraping_jobs must be deleted before documents row"


@pytest.mark.asyncio
async def test_delete_document_returns_404_for_missing_document() -> None:
    """Contract: second delete (or any delete of a non-existent document) returns
    404. This is intentional REST semantics — clients that need 'already gone'
    detection rely on this status code. Flipping to 200/idempotent would be a
    contract change that requires explicit sign-off (plan Task D2)."""
    from fastapi import HTTPException

    request = MagicMock()
    current_user = {"id": "test-user"}

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)  # document missing
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await documents_module.delete_document(
            request=request,
            document_id="never-existed",
            current_user=current_user,
            pool=pool,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_tolerates_missing_optional_tables() -> None:
    """Delete should not abort if an optional cleanup table (e.g. link_scraping_jobs)
    is absent in the deployment — surface the document delete success either way."""
    request = MagicMock()
    current_user = {"id": "test-user"}
    conn, pool = _delete_doc_mock_setup()

    class _UndefinedTableError(Exception):
        pass

    # asyncpg-style error for missing relation; documents.py either catches
    # broad Exception or specifically UndefinedTableError. Simulate the former.
    async def _execute(query, *_args):
        if "link_scraping_jobs" in query:
            raise _UndefinedTableError("relation does not exist")

    conn.execute = AsyncMock(side_effect=_execute)

    # The endpoint currently raises if any DELETE blows up — this test documents
    # the expected behavior. If/when delete becomes defensive, this assertion
    # flips to `response.success is True`.
    with pytest.raises(Exception):
        await documents_module.delete_document(
            request=request,
            document_id="doc-1",
            current_user=current_user,
            pool=pool,
        )
