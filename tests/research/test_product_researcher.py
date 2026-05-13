"""Unit tests for ProductResearcher and ResearchIntegration Firecrawl bridge."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

# Ensure project modules are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Provide lightweight stubs for top-level "services" package expected by product_researcher
services_pkg = ModuleType("services")

config_service_pkg = ModuleType("services.config_service")


class DummyConfigService:  # pragma: no cover - simple stub
    pass


config_service_pkg.ConfigService = DummyConfigService
services_pkg.config_service = config_service_pkg

web_scraping_pkg = ModuleType("services.web_scraping_service")


class DummyWebScrapingService:  # pragma: no cover - simple stub
    pass


def _stub_create_web_scraping_service(*args, **kwargs):  # pragma: no cover - replaced in tests
    raise NotImplementedError


web_scraping_pkg.WebScrapingService = DummyWebScrapingService
web_scraping_pkg.create_web_scraping_service = _stub_create_web_scraping_service
services_pkg.web_scraping_service = web_scraping_pkg

sys.modules.setdefault("services", services_pkg)
sys.modules.setdefault("services.config_service", config_service_pkg)
sys.modules.setdefault("services.web_scraping_service", web_scraping_pkg)

research_pkg_path = PROJECT_ROOT / "backend" / "research"
research_alias_pkg = sys.modules.setdefault("research", ModuleType("research"))
research_alias_pkg.__path__ = [str(research_pkg_path)]  # mark as package for imports
research_alias_pkg.__package__ = "research"

from backend.research import product_researcher as backend_product_researcher

sys.modules.setdefault("research.product_researcher", backend_product_researcher)

research_alias_pkg.ProductResearcher = backend_product_researcher.ProductResearcher
ProductResearcher = backend_product_researcher.ProductResearcher

from backend.research import research_integration as backend_research_integration

sys.modules.setdefault("research.research_integration", backend_research_integration)

research_alias_pkg.ResearchIntegration = backend_research_integration.ResearchIntegration
ResearchIntegration = backend_research_integration.ResearchIntegration


class StubScrapingService:
    """Async stub that simulates WebScrapingService responses."""

    def __init__(
        self,
        scrape_responses: dict[str, dict[str, Any]] | None = None,
        map_response: dict[str, Any] | None = None,
    ) -> None:
        self._scrape_responses = scrape_responses or {}
        self._map_response = map_response or {"success": True, "urls": []}
        self.called_urls: list[str] = []

    async def scrape_url(self, url: str) -> dict[str, Any]:
        self.called_urls.append(url)
        result = self._scrape_responses.get(url)
        if isinstance(result, Exception):
            raise result
        return result or {"success": False, "backend": "firecrawl", "error": "missing"}

    async def map_urls(self, manufacturer_url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._map_response

    def get_backend_info(self) -> dict[str, Any]:
        return {"backend": "firecrawl", "capabilities": ["markdown"], "mock": True}


@pytest.fixture
def stub_scraping_service() -> StubScrapingService:
    return StubScrapingService()


def make_researcher(
    monkeypatch: pytest.MonkeyPatch,
    scraping_service: StubScrapingService,
) -> ProductResearcher:
    """Create ProductResearcher instance using the supplied stub service."""

    monkeypatch.setenv("SCRAPING_BACKEND", "firecrawl")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    monkeypatch.setattr(
        "backend.research.product_researcher.create_web_scraping_service",
        lambda backend, config_service=None: scraping_service,
    )

    return ProductResearcher(config_service=MagicMock())


def test_scrape_urls_prefers_async_service(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "https://example.com/specs": {"success": True, "backend": "firecrawl", "content": "## Specs"},
        "https://example.com/manual": {"success": True, "backend": "firecrawl", "content": "### Manual"},
    }
    service = StubScrapingService(scrape_responses=responses)
    researcher = make_researcher(monkeypatch, service)

    legacy_called: list[str] = []

    def legacy_stub(urls: list[str]) -> str:
        legacy_called.extend(urls)
        return "legacy"

    monkeypatch.setattr(researcher, "_scrape_urls_legacy", legacy_stub)

    combined = researcher._scrape_urls(list(responses.keys()))

    assert "## Specs" in combined
    assert "### Manual" in combined
    assert service.called_urls == list(responses.keys())
    assert not legacy_called, "Legacy scraper should not run when async scraping succeeds"


def test_scrape_urls_falls_back_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {"https://example.com/specs": {"success": False, "backend": "firecrawl", "error": "failed"}}
    service = StubScrapingService(scrape_responses=responses)
    researcher = make_researcher(monkeypatch, service)

    monkeypatch.setattr(researcher, "_scrape_urls_legacy", lambda urls: "legacy-content")

    combined = researcher._scrape_urls(["https://example.com/specs"])

    assert combined == "legacy-content"


def test_discover_urls_filters_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    discovered = {
        "success": True,
        "urls": [
            "https://vendor.com/products/C750i",
            "https://vendor.com/products/c850i",
            "https://vendor.com/support/C750i-manual",
        ],
    }
    service = StubScrapingService(map_response=discovered)
    researcher = make_researcher(monkeypatch, service)

    monkeypatch.setattr(researcher, "_run_async", lambda coro: asyncio.run(coro))

    urls = researcher._discover_urls("https://vendor.com", "C750i")

    assert urls == [
        "https://vendor.com/products/C750i",
        "https://vendor.com/support/C750i-manual",
    ]


def test_get_scraping_info_includes_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StubScrapingService()
    researcher = make_researcher(monkeypatch, service)

    info = researcher.get_scraping_info()

    assert info["backend"] == "firecrawl"
    assert info["service_available"] is True
    assert "capabilities" in info


def test_research_integration_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StubScrapingService()
    monkeypatch.setattr(
        "backend.research.product_researcher.create_web_scraping_service",
        lambda backend, config_service=None: service,
    )
    monkeypatch.setattr(
        "research.product_researcher.create_web_scraping_service",
        lambda backend, config_service=None: service,
    )
    monkeypatch.setattr(
        "backend.research.product_researcher.WebScrapingService",
        StubScrapingService,
    )
    monkeypatch.setattr(
        "research.product_researcher.WebScrapingService",
        StubScrapingService,
    )
    monkeypatch.setenv("SCRAPING_BACKEND", "firecrawl")

    integration = ResearchIntegration(enabled=True, config_service=MagicMock())

    stats = integration.get_scraping_stats()

    assert stats["enabled"] is True
    assert stats["backend"] == "firecrawl"
    assert stats["scraping_info"]["mock"] is True


def test_research_integration_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    integration = ResearchIntegration(enabled=False, config_service=MagicMock())

    stats = integration.get_scraping_stats()

    assert stats["enabled"] is False
    assert stats["backend"] is None
    assert stats["scraping_info"] == {}
