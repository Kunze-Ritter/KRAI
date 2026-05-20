"""Focused integration tests for the OpenAI-compatible OpenWebUI endpoint."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI


def _load_openai_compat_module():
    """Load openai_compat with a lightweight synthetic api package."""

    root = Path(__file__).resolve().parents[1]
    agent_scope_path = root / "api" / "agent_scope.py"
    openai_compat_path = root / "api" / "routes" / "openai_compat.py"

    api_pkg = types.ModuleType("api")
    api_pkg.__path__ = [str(root / "api")]
    middleware_pkg = types.ModuleType("api.middleware")
    middleware_pkg.__path__ = [str(root / "api" / "middleware")]

    auth_module = types.ModuleType("api.middleware.auth_middleware")

    def require_permission(_permission: str):
        async def dependency():
            return {"id": "test-user"}

        return dependency

    auth_module.require_permission = require_permission

    agent_scope_spec = importlib.util.spec_from_file_location("api.agent_scope", agent_scope_path)
    assert agent_scope_spec and agent_scope_spec.loader
    agent_scope_module = importlib.util.module_from_spec(agent_scope_spec)

    previous_modules = {
        name: sys.modules.get(name)
        for name in (
            "api",
            "api.middleware",
            "api.middleware.auth_middleware",
            "api.agent_scope",
        )
    }

    sys.modules["api"] = api_pkg
    sys.modules["api.middleware"] = middleware_pkg
    sys.modules["api.middleware.auth_middleware"] = auth_module
    sys.modules["api.agent_scope"] = agent_scope_module
    agent_scope_spec.loader.exec_module(agent_scope_module)

    compat_spec = importlib.util.spec_from_file_location("test_openai_compat_module", openai_compat_path)
    assert compat_spec and compat_spec.loader
    compat_module = importlib.util.module_from_spec(compat_spec)
    compat_spec.loader.exec_module(compat_module)

    for name, module in previous_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module

    return compat_module


class FakeConnection:
    def __init__(self) -> None:
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *params):
        self.fetch_calls.append((query, params))

        if "FROM   krai_intelligence.error_codes ec" in query:
            param_text = " ".join(str(param) for param in params[:-1])
            if "13.A2" in param_text:
                if "E877" in param_text:
                    return []
                return [
                    {
                        "error_code": "13.A2.FF",
                        "error_description": "Residual Paper Jam in Tray 2",
                        "solution_customer_text": "",
                        "solution_agent_text": "",
                        "solution_technician_text": "Clear the residual paper from the tray path.",
                        "page_number": 64,
                        "severity_level": "warning",
                        "confidence_score": 0.95,
                        "manufacturer_name": "HP",
                        "document_filename": None,
                        "model_number": None,
                        "model_name": None,
                        "series_name": None,
                        "document_id": None,
                        "product_id": None,
                    }
                ]
            return [
                {
                    "error_code": "10.00.33",
                    "error_description": "Paper jam in tray 4",
                    "solution_customer_text": "Papierstau beseitigen.",
                    "solution_agent_text": "Call-Center Schritte",
                    "solution_technician_text": "A" * 240,
                    "page_number": 88,
                    "severity_level": "warning",
                    "confidence_score": 0.98,
                    "manufacturer_name": "HP",
                    "document_filename": "hp_e877_service_manual.pdf",
                    "model_number": "E877",
                    "model_name": "Color LaserJet Managed Flow MFP",
                    "series_name": "E877",
                    "document_id": "doc-123",
                    "product_id": "prod-123",
                }
            ]

        if "FROM krai_content.images img" in query:
            return [
                {
                    "storage_url": "https://example.com/tiny-bullet.png",
                    "page_number": 37,
                    "image_type": "unknown",
                    "ai_description": "tiny bullet",
                    "file_size": 584,
                    "width_px": 24,
                    "height_px": 24,
                    "contains_text": False,
                    "ocr_text": "",
                }
            ]

        if "FROM   krai_content.videos v" in query:
            param_text = " ".join(str(param) for param in params[:-1])
            if "Lexmark" in param_text and "fuser" in param_text.lower():
                return [
                    {
                        "title": "202.xx fuser paper jams",
                        "video_url": "https://lexmark.scene7.com/is/content/lexmark/CS-3-4-51x-202xx-fuser-paper-jams",
                        "description": "Lexmark video for fuser paper jam handling.",
                        "duration": 95,
                        "channel_title": "Lexmark Support",
                        "manufacturer_name": "Lexmark",
                        "model_number": "XC9525",
                        "model_name": "XC9525",
                        "series_name": "XC9525",
                    }
                ]
            if len(params) <= 4 and "E877" not in param_text and "Tray 4 jam" not in param_text:
                return []
            if len(params) <= 4:
                return [
                    {
                        "title": "Remove the duplex jam 2 sensor",
                        "video_url": "https://example.com/video-generic",
                        "description": "Generic E877 jam-sensor repair video.",
                        "duration": 194,
                        "channel_title": "KRAI",
                        "manufacturer_name": "HP",
                        "model_number": "E877",
                        "model_name": "Color LaserJet Managed Flow MFP",
                        "series_name": "E877",
                    },
                    {
                        "title": "HP E877 Tray 4 jam removal",
                        "video_url": "https://example.com/video",
                        "description": "Shows how to clear tray 4 jams on E877 devices.",
                        "duration": 125,
                        "channel_title": "KRAI",
                        "manufacturer_name": "HP",
                        "model_number": "E877",
                        "model_name": "Color LaserJet Managed Flow MFP",
                        "series_name": "E877",
                    },
                    {
                        "title": "Remove the right door switch assembly",
                        "video_url": "https://example.com/video-door",
                        "description": "Generic E877 door repair video.",
                        "duration": 102,
                        "channel_title": "KRAI",
                        "manufacturer_name": "HP",
                        "model_number": "E877",
                        "model_name": "Color LaserJet Managed Flow MFP",
                        "series_name": "E877",
                    },
                ]
            return [
                {
                    "title": "HP E877 Tray 4 jam removal",
                    "video_url": "https://example.com/video",
                    "description": "Shows how to clear tray 4 jams on E877 devices.",
                    "duration": 125,
                    "channel_title": "KRAI",
                    "manufacturer_name": "HP",
                    "model_number": "E877",
                    "model_name": "Color LaserJet Managed Flow MFP",
                    "series_name": "E877",
                }
            ]

        if "FROM   krai_core.documents d" in query:
            param_text = " ".join(str(param) for param in params[:-1])
            if "Lexmark" in param_text and "fuser" in param_text.lower():
                return [
                    {
                        "id": "doc-789",
                        "filename": "lexmark_XC9525_support_videos.virtual",
                        "document_type": "support_video_collection",
                        "storage_url": "",
                        "manufacturer_name": "Lexmark",
                        "model_number": "XC9525",
                        "model_name": "XC9525",
                        "series_name": "XC9525",
                    }
                ]
            return [
                {
                    "id": "doc-456",
                    "filename": "hp_e877_cpmd.pdf",
                    "document_type": "cpmd_database",
                    "storage_url": "https://example.com/hp_e877_cpmd.pdf",
                    "manufacturer_name": "HP",
                    "model_number": "E877",
                    "model_name": "Color LaserJet Managed Flow MFP",
                    "series_name": "E877",
                }
            ]

        if "FROM   krai_intelligence.structured_tables st" in query:
            return [
                {
                    "page_number": 37,
                    "table_index": 0,
                    "table_type": "parts",
                    "caption": "Table 6-6",
                    "context_text": "Toner cartridge part number",
                    "table_markdown": "| Part description | Toner cartridge part number |\n| --- | --- |\n| HP 89A Black Original LaserJet Toner Cartridge | CF289A |",
                }
            ]

        return []


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


class FakeAgent:
    def __init__(self) -> None:
        self.scope_calls: list[tuple[str, object, bool]] = []
        self.chat_called = False

    def resolve_session_scope(self, session_id: str, scope=None, *, reset_scope: bool = False):
        self.scope_calls.append((session_id, scope, reset_scope))
        if scope is None:
            return {}
        return dict(scope.model_dump(exclude_none=True).items())

    async def chat(self, *args, **kwargs):
        self.chat_called = True
        return "fallback", {}

    async def chat_stream(self, *args, **kwargs):
        self.chat_called = True
        if False:
            yield ""


def test_build_video_search_plan_adds_hp_tray_expansion():
    compat_module = _load_openai_compat_module()

    plan = compat_module._build_video_search_plan(
        "Gibt es ein Video zu HP E877 Tray 4 Jam?",
        {"manufacturer": "HP"},
    )

    assert plan["manufacturer"] == "HP"
    assert plan["model"] == "E877"
    assert "Tray 4 Jam" in plan["issue_terms"]
    assert "13.A4" in plan["expansion_terms"]
    assert "HCI" in plan["expansion_terms"]
    assert "cassette" in plan["expansion_terms"]
    assert ["E877", "13.A4"] in plan["search_term_sets"]


def test_strip_hp_family_lines_removes_family_block():
    compat_module = _load_openai_compat_module()

    text = """If all tests pass, replace the tray assembly.
13.AX.FF
Residual paper jam in Tray X. ( X = tray 2, 3, or 4 )
This jam occurs when residual paper is detected at the Tray X feed sensor.
13.A2.FF Residual Paper Jam in Tray 2.
13.A3.FF Residual Paper Jam in Tray 3.
Recommended action for customers
Clear the jam.
"""

    cleaned = compat_module._strip_hp_family_lines(text, "13.A2.FF")

    assert "13.AX.FF" not in cleaned
    assert "Tray X" not in cleaned
    assert "13.A3.FF" not in cleaned
    assert "Recommended action for customers" in cleaned


def test_model_match_score_prefers_exact_model():
    compat_module = _load_openai_compat_module()

    e877_score = compat_module._model_match_score(
        {"filename": "HP_E877_CPMD.pdf", "model_number": "E877", "series_name": "E877"},
        "E877",
    )
    x580_score = compat_module._model_match_score(
        {"filename": "HP_X580_CPMD.pdf", "model_number": "X580", "series_name": "X580"},
        "E877",
    )

    assert e877_score > x580_score


def test_semantic_fast_path_only_for_retrieval_like_queries():
    compat_module = _load_openai_compat_module()

    assert compat_module._should_use_semantic_fast_path("Was bedeutet HP Fehler 13.A2 auf E877?")
    assert compat_module._should_use_semantic_fast_path("Zeige mir relevante Dokumente zum Tray 4 jam auf E877")
    assert not compat_module._should_use_semantic_fast_path("Antworte nur mit dem Wort BEREIT.")
    assert not compat_module._should_use_semantic_fast_path("Sag einfach hallo.")


def test_build_video_search_plan_prefers_domain_term_over_generic_action():
    compat_module = _load_openai_compat_module()

    plan = compat_module._build_video_search_plan("Lexmark fuser tauschen video")

    assert plan["manufacturer"] == "Lexmark"
    assert plan["model"] is None
    assert plan["search_term_sets"][0] == ["Lexmark", "fuser"]
    assert ["tauschen"] not in plan["search_term_sets"]


@pytest.mark.asyncio
async def test_list_models_reports_openrouter_backend(monkeypatch: pytest.MonkeyPatch):
    compat_module = _load_openai_compat_module()

    monkeypatch.setenv("LLM_BACKEND", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-8b-instruct:free")

    app = FastAPI()
    app.include_router(compat_module.router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/models")

    assert response.status_code == 200
    model = response.json()["data"][0]
    assert model["id"] == "krai"
    assert "openrouter:meta-llama/llama-3.3-8b-instruct:free" in model["description"]


@pytest.mark.asyncio
async def test_chat_completions_routes_freeform_prompt_to_agent():
    compat_module = _load_openai_compat_module()
    connection = FakeConnection()
    agent = FakeAgent()

    app = FastAPI()
    app.state.db_pool = FakePool(connection)
    app.state.krai_agent = agent
    app.include_router(compat_module.router)

    payload = {
        "model": "krai",
        "user": "tech-session-agent",
        "messages": [{"role": "user", "content": "Antworte nur mit dem Wort BEREIT."}],
    }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]

    assert content == "fallback"
    assert "krai_context" not in body
    assert agent.chat_called is True

    semantic_queries = [
        query for query, _params in connection.fetch_calls if "FROM   krai_intelligence.chunks c" in query
    ]
    assert not semantic_queries


@pytest.mark.asyncio
async def test_chat_completions_prefers_real_lexmark_fuser_video():
    compat_module = _load_openai_compat_module()
    connection = FakeConnection()
    agent = FakeAgent()

    app = FastAPI()
    app.state.db_pool = FakePool(connection)
    app.state.krai_agent = agent
    app.include_router(compat_module.router)

    payload = {
        "model": "krai",
        "user": "tech-session-lexmark-video",
        "messages": [{"role": "user", "content": "Lexmark fuser tauschen video"}],
    }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    krai_context = body["krai_context"]

    assert "202.xx fuser paper jams" in content
    assert "https://lexmark.scene7.com/is/content/lexmark/CS-3-4-51x-202xx-fuser-paper-jams" in content
    assert krai_context["type"] == "video_lookup"
    assert krai_context["found"] is True
    assert krai_context["videos"][0]["url"].startswith("https://lexmark.scene7.com/")
    assert agent.chat_called is False


@pytest.mark.asyncio
async def test_chat_completions_uses_scoped_fast_path_and_returns_related_video():
    compat_module = _load_openai_compat_module()
    connection = FakeConnection()
    agent = FakeAgent()

    app = FastAPI()
    app.state.db_pool = FakePool(connection)
    app.state.krai_agent = agent
    app.include_router(compat_module.router)

    payload = {
        "model": "krai",
        "user": "tech-session-123",
        "messages": [{"role": "user", "content": "Was bedeutet HP Fehler 10.00.33?"}],
        "metadata": {
            "scope": {
                "manufacturer": "HP",
                "product": "Color LaserJet Managed Flow MFP E877",
                "series": "E877",
            }
        },
    }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    krai_context = body["krai_context"]

    assert "Fehler `10.00.33`" in content
    assert "Scope: **HP / Color LaserJet Managed Flow MFP E877**" in content
    assert "## 🎬 Passende Videos" in content
    assert "HP E877 Tray 4 jam removal" in content
    assert "## 📚 Weitere relevante Dokumente" in content
    assert "hp_e877_cpmd.pdf" in content
    assert "[hp_e877_cpmd.pdf](https://example.com/hp_e877_cpmd.pdf)" in content
    assert "## 📋 Relevante Tabellen" in content
    assert "Table 6-6" in content
    assert "tiny-bullet.png" not in content
    assert "🖼️ Bilder aus dem Service-Manual" not in content
    assert krai_context["type"] == "error_code_lookup"
    assert krai_context["found"] is True
    assert krai_context["error_code"] == "10.00.33"
    assert krai_context["scope"]["manufacturer"] == "HP"
    assert krai_context["videos"][0]["title"] == "HP E877 Tray 4 jam removal"
    assert krai_context["related_documents"][0]["filename"] == "hp_e877_cpmd.pdf"
    assert krai_context["related_documents"][0]["storage_url"] == "https://example.com/hp_e877_cpmd.pdf"
    assert krai_context["tables"][0]["caption"] == "Table 6-6"
    assert agent.chat_called is False
    assert agent.scope_calls and agent.scope_calls[0][0] == "tech-session-123"

    error_queries = [query for query, _params in connection.fetch_calls if "error_codes ec" in query]
    video_queries = [query for query, _params in connection.fetch_calls if "videos v" in query]
    document_queries = [query for query, _params in connection.fetch_calls if "FROM   krai_core.documents d" in query]

    assert error_queries
    assert "m.name ILIKE" in error_queries[0]
    assert "COALESCE(p.model_number, '') ILIKE" in error_queries[0]
    assert video_queries
    assert document_queries


@pytest.mark.asyncio
async def test_chat_completions_error_code_query_retries_without_model_linkage():
    compat_module = _load_openai_compat_module()
    connection = FakeConnection()
    agent = FakeAgent()

    app = FastAPI()
    app.state.db_pool = FakePool(connection)
    app.state.krai_agent = agent
    app.include_router(compat_module.router)

    payload = {
        "model": "krai",
        "user": "tech-session-error-video",
        "messages": [
            {
                "role": "user",
                "content": "Was bedeutet HP Fehler 13.A2 auf E877? Bitte mit passenden Videos und relevanten Dokumenten.",
            }
        ],
    }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    krai_context = body["krai_context"]

    assert "Fehler `13.A2.FF`" in content
    assert "## 🎬 Passende Videos" in content
    assert "## 📚 Weitere relevante Dokumente" in content
    assert "hp_e877_cpmd.pdf" in content
    assert "[hp_e877_cpmd.pdf](https://example.com/hp_e877_cpmd.pdf)" in content
    assert krai_context["type"] == "error_code_lookup"
    assert krai_context["found"] is True
    assert agent.chat_called is False

    error_queries = [(query, params) for query, params in connection.fetch_calls if "error_codes ec" in query]
    semantic_queries = [
        query for query, _params in connection.fetch_calls if "FROM   krai_intelligence.chunks c" in query
    ]

    assert len(error_queries) >= 2
    assert any("E877" in " ".join(str(param) for param in params[:-1]) for _query, params in error_queries)
    assert any("E877" not in " ".join(str(param) for param in params[:-1]) for _query, params in error_queries)
    assert not semantic_queries


@pytest.mark.asyncio
async def test_chat_completions_prefers_video_route_for_model_like_terms():
    compat_module = _load_openai_compat_module()
    connection = FakeConnection()
    agent = FakeAgent()

    app = FastAPI()
    app.state.db_pool = FakePool(connection)
    app.state.krai_agent = agent
    app.include_router(compat_module.router)

    payload = {
        "model": "krai",
        "user": "tech-session-video",
        "messages": [{"role": "user", "content": "Gibt es ein Video zu HP E877 Tray 4 Jam?"}],
    }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    krai_context = body["krai_context"]

    assert "## 🎬 Videos" in content
    assert "HP E877 Tray 4 jam removal" in content
    assert "## 📚 Relevante Dokumente" in content
    assert "hp_e877_cpmd.pdf" in content
    assert "[hp_e877_cpmd.pdf](https://example.com/hp_e877_cpmd.pdf)" in content
    assert "Verstanden als:" in content
    assert "Fehlercode `E877`" not in content
    assert agent.chat_called is False
    assert content.index("HP E877 Tray 4 jam removal") < content.index("Remove the duplex jam 2 sensor")
    assert krai_context["type"] == "video_lookup"
    assert krai_context["found"] is True
    assert krai_context["signals"]["model"] == "E877"
    assert "tray 4 jam" in [term.lower() for term in krai_context["signals"]["issue_terms"]]
    assert krai_context["videos"][0]["title"] == "HP E877 Tray 4 jam removal"
    assert krai_context["related_documents"][0]["filename"] == "hp_e877_cpmd.pdf"
    assert krai_context["related_documents"][0]["storage_url"] == "https://example.com/hp_e877_cpmd.pdf"

    error_queries = [query for query, _params in connection.fetch_calls if "error_codes ec" in query]
    video_queries = [(query, params) for query, params in connection.fetch_calls if "videos v" in query]
    document_queries = [query for query, _params in connection.fetch_calls if "FROM   krai_core.documents d" in query]

    assert not error_queries
    assert video_queries
    assert document_queries
    assert any("E877" in " ".join(str(param) for param in params[:-1]) for _query, params in video_queries)
