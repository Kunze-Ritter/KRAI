"""Structured extraction service leveraging Firecrawl schema-based outputs.

This service coordinates schema-driven structured extraction tasks using the
:class:`~backend.services.web_scraping_service.WebScrapingService` Firecrawl
backend. Extracted payloads are normalised and persisted into the
``krai_intelligence.structured_extractions`` table for downstream consumers
(error code extractor, product catalogue enrichment, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config_service import ConfigService
from .web_scraping_service import WebScrapingService


class StructuredExtractionService:
    """Service coordinating schema-based structured extractions via Firecrawl."""

    def __init__(
        self,
        web_scraping_service: WebScrapingService,
        database_service: Any,
        config_service: ConfigService | None = None,
        schema_path: str | None = None,
    ) -> None:
        self._scraper = web_scraping_service
        self._database_service = database_service
        self._config_service = config_service
        self._logger = logging.getLogger("krai.services.structured_extraction")
        self._schemas: dict[str, dict[str, Any]] = {}

        self._schema_path = (
            Path(schema_path) if schema_path else Path(__file__).parent.parent / "schemas" / "extraction_schemas.json"
        )
        self._load_schemas()
        self._config = self._load_config()

    # ------------------------------------------------------------------
    # Public extraction helpers
    # ------------------------------------------------------------------
    async def extract_product_specs(
        self,
        url: str,
        *,
        manufacturer_id: str | None = None,
        product_id: str | None = None,
        document_id: str | None = None,
        source_type: str = "link",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        schema_info = self._get_schema("product_specs")
        return await self._perform_extraction(
            url=url,
            extraction_type="product_specs",
            schema_info=schema_info,
            manufacturer_id=manufacturer_id,
            product_id=product_id,
            document_id=document_id,
            source_type=source_type,
            source_id=source_id,
        )

    async def extract_error_codes(
        self,
        url: str,
        *,
        manufacturer_id: str | None = None,
        document_id: str | None = None,
        source_type: str = "link",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        schema_info = self._get_schema("error_codes")
        return await self._perform_extraction(
            url=url,
            extraction_type="error_code",
            schema_info=schema_info,
            manufacturer_id=manufacturer_id,
            document_id=document_id,
            source_type=source_type,
            source_id=source_id,
        )

    async def extract_service_manual_metadata(
        self,
        url: str,
        *,
        manufacturer_id: str | None = None,
        document_id: str | None = None,
        source_type: str = "link",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        schema_info = self._get_schema("service_manual")
        return await self._perform_extraction(
            url=url,
            extraction_type="service_manual",
            schema_info=schema_info,
            manufacturer_id=manufacturer_id,
            document_id=document_id,
            source_type=source_type,
            source_id=source_id,
        )

    async def extract_parts_list(
        self,
        url: str,
        *,
        manufacturer_id: str | None = None,
        document_id: str | None = None,
        source_type: str = "link",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        schema_info = self._get_schema("parts_list")
        return await self._perform_extraction(
            url=url,
            extraction_type="parts_list",
            schema_info=schema_info,
            manufacturer_id=manufacturer_id,
            document_id=document_id,
            source_type=source_type,
            source_id=source_id,
        )

    async def extract_troubleshooting(
        self,
        url: str,
        *,
        manufacturer_id: str | None = None,
        document_id: str | None = None,
        source_type: str = "link",
        source_id: str | None = None,
    ) -> dict[str, Any]:
        schema_info = self._get_schema("troubleshooting")
        return await self._perform_extraction(
            url=url,
            extraction_type="troubleshooting",
            schema_info=schema_info,
            manufacturer_id=manufacturer_id,
            document_id=document_id,
            source_type=source_type,
            source_id=source_id,
        )

    async def extract_from_link(self, link_id: str) -> dict[str, Any]:
        """Run structured extraction against a stored link record."""

        client = self._get_db_client()
        if client is None:
            return {"success": False, "error": "database client unavailable"}

        link_response = (
            client.table("vw_links")
            .select(
                "id, url, link_type, link_category, scraped_metadata, scraped_content, manufacturer_id, document_id"
            )
            .eq("id", str(link_id))
            .limit(1)
            .execute()
        )
        if not link_response.data:
            return {"success": False, "error": "link not found"}

        link = link_response.data[0]
        url = link.get("url")
        if not url:
            return {"success": False, "error": "link url missing"}

        extraction_type = self._determine_extraction_type(
            url=url,
            link_type=link.get("link_type"),
            link_category=link.get("link_category"),
        )

        if extraction_type is None:
            return {"success": False, "error": "no matching extraction schema"}

        method_map = {
            "product_specs": self.extract_product_specs,
            "error_code": self.extract_error_codes,
            "service_manual": self.extract_service_manual_metadata,
            "parts_list": self.extract_parts_list,
            "troubleshooting": self.extract_troubleshooting,
        }
        method = method_map.get(extraction_type)
        if method is None:
            return {"success": False, "error": "unsupported extraction type"}

        result = await method(
            url=url,
            manufacturer_id=link.get("manufacturer_id"),
            document_id=link.get("document_id"),
            source_type="link",
            source_id=str(link_id),
        )

        if result.get("success"):
            await self._update_link_metadata(link, result)
        return result

    async def extract_from_crawled_page(self, page_id: str) -> dict[str, Any]:
        client = self._get_db_client()
        if client is None:
            return {"success": False, "error": "database client unavailable"}

        response = (
            client.table("crawled_pages", schema="krai_system")
            .select("id, url, page_type, manufacturer_id, crawl_job_id")
            .eq("id", str(page_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return {"success": False, "error": "crawled page not found"}

        page = response.data[0]
        url = page.get("url")
        if not url:
            return {"success": False, "error": "page url missing"}

        extraction_type = self._determine_extraction_type(
            url=url,
            link_type=page.get("page_type"),
            link_category=None,
        )
        if extraction_type is None:
            return {"success": False, "error": "no matching extraction schema"}

        method_map = {
            "product_specs": self.extract_product_specs,
            "error_code": self.extract_error_codes,
            "service_manual": self.extract_service_manual_metadata,
            "parts_list": self.extract_parts_list,
            "troubleshooting": self.extract_troubleshooting,
        }
        method = method_map.get(extraction_type)
        if method is None:
            return {"success": False, "error": "unsupported extraction type"}

        result = await method(
            url=url,
            manufacturer_id=page.get("manufacturer_id"),
            document_id=None,
            source_type="crawled_page",
            source_id=str(page_id),
        )

        if result.get("success"):
            await self._update_crawled_page(page_id, result)
        return result

    async def batch_extract(
        self,
        source_ids: Sequence[str],
        *,
        source_type: str = "link",
        max_concurrent: int = 2,
    ) -> dict[str, Any]:
        if not source_ids:
            return {"total": 0, "completed": 0, "failed": 0, "results": []}

        semaphore = asyncio.Semaphore(max(1, max_concurrent))
        results: list[dict[str, Any]] = []

        async def _run(source_id: str) -> None:
            async with semaphore:
                if source_type == "link":
                    result = await self.extract_from_link(source_id)
                else:
                    result = await self.extract_from_crawled_page(source_id)
                results.append({"source_id": source_id, **result})

        await asyncio.gather(*[_run(str(source_id)) for source_id in source_ids])

        completed = sum(1 for item in results if item.get("success"))
        failed = sum(1 for item in results if not item.get("success"))
        return {
            "total": len(source_ids),
            "completed": completed,
            "failed": failed,
            "results": results,
        }

    def get_extraction_schemas(self) -> dict[str, dict[str, Any]]:
        return self._schemas

    async def validate_extraction(
        self,
        extraction_id: str,
        *,
        status: str,
        notes: str | None = None,
    ) -> bool:
        if status not in {"pending", "validated", "rejected"}:
            raise ValueError("Invalid validation status")

        client = self._get_db_client()
        if client is None:
            return False

        try:
            client.table("structured_extractions", schema="krai_intelligence").update(
                {
                    "validation_status": status,
                    "validation_notes": notes,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", str(extraction_id)).execute()
            return True
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Failed to update validation status: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_schemas(self) -> None:
        if not self._schema_path.exists():
            raise FileNotFoundError(f"Extraction schema file missing: {self._schema_path}")
        try:
            with open(self._schema_path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in extraction schema file: {exc}") from exc

        schemas = payload.get("schemas") or {}
        for key, value in schemas.items():
            if "schema" not in value:
                raise ValueError(f"Schema entry '{key}' missing 'schema' definition")
            self._schemas[key] = value
        self._logger.info("Loaded %s structured extraction schemas", len(self._schemas))

    def _load_config(self) -> dict[str, Any]:
        if self._config_service:
            try:
                config = self._config_service.get_scraping_config()
                return {
                    "firecrawl_llm_provider": config.get("firecrawl_llm_provider", "ollama"),
                    "firecrawl_model_name": config.get("firecrawl_model_name", "llama3.2:latest"),
                    "extraction_timeout": int(config.get("scrape_timeout", 60)),
                    "confidence_threshold": float(config.get("extraction_confidence_threshold", 0.5)),
                }
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.debug("Failed loading scraping config: %s", exc)
        return {
            "firecrawl_llm_provider": "ollama",
            "firecrawl_model_name": "llama3.2:latest",
            "extraction_timeout": 60,
            "confidence_threshold": 0.5,
        }

    def _get_schema(self, key: str) -> dict[str, Any]:
        schema_info = self._schemas.get(key)
        if schema_info is None:
            raise ValueError(f"Schema '{key}' not available")
        return schema_info

    async def _perform_extraction(
        self,
        *,
        url: str,
        extraction_type: str,
        schema_info: dict[str, Any],
        manufacturer_id: str | None,
        product_id: str | None = None,
        document_id: str | None = None,
        source_type: str,
        source_id: str | None,
    ) -> dict[str, Any]:
        if self._scraper.primary_backend.backend_name != "firecrawl":
            return {"success": False, "error": "structured extraction requires firecrawl backend"}

        schema = schema_info.get("schema")
        schema_version = schema_info.get("version", "1.0")
        description = schema_info.get("description")

        try:
            response = await self._scraper.extract_structured_data(url, schema)
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Structured extraction failed for %s: %s", url, exc)
            return {"success": False, "error": str(exc)}

        if not response.get("success"):
            return {
                "success": False,
                "error": response.get("error", "extraction failed"),
            }

        extracted_data = response.get("data") or {}
        confidence = float(response.get("confidence") or 0.0)
        backend = response.get("backend")

        if confidence < self._config.get("confidence_threshold", 0.5):
            self._logger.debug("Skipping low-confidence extraction for %s (%.2f)", url, confidence)
            return {
                "success": False,
                "skipped": True,
                "reason": "confidence_below_threshold",
                "confidence": confidence,
            }

        persist_result = self._persist_extraction(
            source_type=source_type,
            source_id=source_id,
            extraction_type=extraction_type,
            schema_version=schema_version,
            extracted_data=extracted_data,
            confidence=confidence,
            manufacturer_id=manufacturer_id,
            product_id=product_id,
            document_id=document_id,
            metadata={
                "backend": backend,
                "schema_description": description,
                "url": url,
            },
        )

        return {
            "success": True,
            "extracted_data": extracted_data,
            "confidence": confidence,
            "schema_version": schema_version,
            "record_id": persist_result.get("id"),
            "extraction_type": extraction_type,
        }

    def _persist_extraction(
        self,
        *,
        source_type: str,
        source_id: str | None,
        extraction_type: str,
        schema_version: str,
        extracted_data: dict[str, Any],
        confidence: float,
        manufacturer_id: str | None,
        product_id: str | None,
        document_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._get_db_client()
        if client is None:
            return {"success": False}

        payload = {
            "source_type": source_type,
            "source_id": source_id,
            "extraction_type": extraction_type,
            "schema_version": schema_version,
            "extracted_data": extracted_data,
            "confidence": confidence,
            "llm_provider": self._config.get("firecrawl_llm_provider"),
            "llm_model": self._config.get("firecrawl_model_name"),
            "manufacturer_id": manufacturer_id,
            "product_id": product_id,
            "document_id": document_id,
            "metadata": metadata or {},
        }

        try:
            existing = (
                client.table("structured_extractions", schema="krai_intelligence")
                .select("id")
                .eq("source_type", source_type)
                .eq("source_id", source_id)
                .eq("extraction_type", extraction_type)
                .eq("schema_version", schema_version)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Failed to query structured_extractions: %s", exc)
            existing = None

        now_iso = datetime.now(UTC).isoformat()
        payload["updated_at"] = now_iso

        try:
            if existing and existing.data:
                record_id = existing.data[0]["id"]
                client.table("structured_extractions", schema="krai_intelligence").update(payload).eq(
                    "id", record_id
                ).execute()
                return {"success": True, "id": record_id}

            payload["created_at"] = now_iso
            result = client.table("structured_extractions", schema="krai_intelligence").insert(payload).execute()
            record_id = result.data[0]["id"] if result.data else None
            return {"success": True, "id": record_id}
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Failed to persist structured extraction: %s", exc)
            return {"success": False}

    async def _update_link_metadata(self, link: dict[str, Any], result: dict[str, Any]) -> None:
        client = self._get_db_client()
        if client is None:
            return

        metadata = link.get("scraped_metadata") or {}
        structured_entries = metadata.get("structured_extractions") or []
        entry = {
            "record_id": result.get("record_id"),
            "extraction_type": result.get("extraction_type", "unknown"),
            "confidence": result.get("confidence"),
            "extracted_at": datetime.now(UTC).isoformat(),
        }

        if entry["record_id"]:
            structured_entries = [
                existing_entry
                for existing_entry in structured_entries
                if existing_entry.get("record_id") != entry["record_id"]
            ]
        structured_entries.append(entry)
        metadata["structured_extractions"] = structured_entries

        try:
            client.table("links", schema="krai_content").update(
                {
                    "scraped_metadata": metadata,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", str(link.get("id"))).execute()
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.debug("Failed to update link metadata: %s", exc)

    async def _update_crawled_page(self, page_id: str, result: dict[str, Any]) -> None:
        client = self._get_db_client()
        if client is None:
            return

        try:
            client.table("crawled_pages", schema="krai_system").update(
                {
                    "status": "processed",
                    "processed_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", str(page_id)).execute()
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.debug("Failed to update crawled page status: %s", exc)

    def _get_db_client(self):
        client = getattr(self._database_service, "service_client", None)
        if client is None:
            client = getattr(self._database_service, "client", None)
        if client is None:
            self._logger.error("Database client unavailable for structured extraction")
        return client

    def _determine_extraction_type(
        self,
        *,
        url: str,
        link_type: str | None,
        link_category: str | None,
    ) -> str | None:
        url_lower = url.lower()
        candidates: list[tuple[str, bool]] = [
            ("product_specs", any(keyword in url_lower for keyword in ["spec", "datasheet", "product"])),
            ("error_code", any(keyword in url_lower for keyword in ["error", "code", "troubleshoot"])),
            ("service_manual", any(keyword in url_lower for keyword in ["manual", "download", "pdf"])),
        ]
        for extraction_type, matches in candidates:
            if matches:
                return extraction_type

        if link_type:
            link_type_lower = str(link_type).lower()
            if "product" in link_type_lower:
                return "product_specs"
            if "error" in link_type_lower or "support" in link_type_lower:
                return "error_code"
            if "manual" in link_type_lower:
                return "service_manual"
            if "parts" in link_type_lower:
                return "parts_list"

        if link_category:
            category_lower = str(link_category).lower()
            if "product" in category_lower:
                return "product_specs"
            if "manual" in category_lower:
                return "service_manual"
            if "support" in category_lower or "error" in category_lower:
                return "error_code"

        return None
