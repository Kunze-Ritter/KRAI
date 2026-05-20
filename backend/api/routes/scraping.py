from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.config_service import ConfigService
from backend.services.web_scraping_service import create_web_scraping_service

router = APIRouter(prefix="/scraping", tags=["Scraping"])
config_service = ConfigService()
runtime_firecrawl_config: dict[str, Any] = {}
activity_logs: list[dict[str, Any]] = []


class ScrapeRequest(BaseModel):
    url: str
    options: dict[str, Any] | None = None
    force_backend: str | None = None


class CrawlRequest(BaseModel):
    start_url: str
    options: dict[str, Any] | None = None


class ExtractRequest(BaseModel):
    url: str
    extraction_schema: dict[str, Any]
    options: dict[str, Any] | None = None


class MapRequest(BaseModel):
    url: str
    options: dict[str, Any] | None = None


class FirecrawlConfigRequest(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    embedding_model: str | None = None
    max_concurrency: int | None = None
    block_media: bool | None = None


def _get_effective_config() -> dict[str, Any]:
    base = config_service.get_scraping_config()
    return {**base, **runtime_firecrawl_config}


def _create_service(backend: str | None = None):
    config_service._configs["scraping_config"] = _get_effective_config()
    return create_web_scraping_service(backend=backend, config_service=config_service)


def _add_activity_log(action: str, url: str, backend: str | None) -> None:
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "url": url,
        "backend": backend or "unknown",
    }
    activity_logs.append(entry)
    # keep only latest 200 entries
    if len(activity_logs) > 200:
        del activity_logs[:-200]


@router.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    service = _create_service(backend=request.force_backend)
    result = await service.scrape_url(request.url, request.options, request.force_backend)
    _add_activity_log("scrape", request.url, result.get("backend"))
    return result


@router.post("/crawl")
async def crawl_site(request: CrawlRequest):
    service = _create_service()
    result = await service.crawl_site(request.start_url, request.options)
    _add_activity_log("crawl", request.start_url, result.get("backend"))
    return result


@router.post("/extract")
async def extract_structured(request: ExtractRequest):
    service = _create_service()
    result = await service.extract_structured_data(request.url, request.extraction_schema, request.options)
    _add_activity_log("extract", request.url, result.get("backend"))
    return result


@router.post("/map")
async def map_urls(request: MapRequest):
    service = _create_service()
    result = await service.map_urls(request.url, request.options)
    _add_activity_log("map", request.url, result.get("backend"))
    return result


@router.get("/health")
async def health_check():
    service = _create_service()
    try:
        return await service.health_check()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/info")
async def get_backend_info():
    service = _create_service()
    return service.get_backend_info()


@router.get("/logs")
async def get_activity_logs(limit: int = 50):
    limited = activity_logs[-limit:] if limit > 0 else []
    return {"logs": list(reversed(limited))}


@router.get("/config")
async def get_firecrawl_config():
    return {"config": _get_effective_config()}


@router.put("/config")
async def update_firecrawl_config(config: FirecrawlConfigRequest):
    update_payload = {k: v for k, v in config.dict().items() if v is not None}
    runtime_firecrawl_config.update(update_payload)
    return {"config": _get_effective_config()}
