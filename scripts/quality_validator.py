"""Quality validation module for production pipeline test runs.

This validator checks completeness, correctness, relationship integrity,
embedding coverage, and stage tracking status for a document batch. It uses
schema-aligned joins for product relationships and a resilient parts counting
strategy with safe fallback behavior.
"""

import logging
import os
from typing import Any

from backend.core.types import Stage

logger = logging.getLogger(__name__)


class QualityValidator:
    def __init__(self, database_adapter, thresholds: dict[str, Any]):
        self.database_adapter = database_adapter
        self.thresholds = thresholds

    async def validate(self, document_ids: list[str]) -> dict[str, Any]:
        """Run all quality checks and return a combined PASS/FAIL result."""
        completeness = await self._check_completeness(document_ids)
        correctness = await self._check_correctness(document_ids)
        embeddings = await self._check_embeddings(document_ids)
        relationships = await self._check_relationships(document_ids)
        stage_status = await self._check_stage_status(document_ids)

        metrics = {
            "completeness": completeness,
            "correctness": correctness,
            "embeddings": embeddings,
            "relationships": relationships,
            "stage_status": stage_status,
        }

        overall_pass = all(metric.get("status") == "PASS" for metric in metrics.values())
        return {
            "status": "PASS" if overall_pass else "FAIL",
            "metrics": metrics,
        }

    async def _check_completeness(self, document_ids: list[str]) -> dict[str, Any]:
        """Validate extraction completeness across chunks, images, codes, and parts.

        Uses document-scoped counts for chunks/images/error codes. For parts, this
        applies schema-driven fallback logic and marks parts as SKIPPED when no
        valid relationship path exists.
        """
        try:
            chunks_row = await self.database_adapter.fetch_one(
                "SELECT COUNT(*) as count FROM krai_intelligence.chunks WHERE document_id = ANY($1)",
                [document_ids],
            )
            logger.debug("Completeness chunks query result for %s: %s", document_ids, chunks_row)
        except Exception:
            logger.exception("Completeness chunks query failed for document_ids=%s", document_ids)
            raise

        try:
            images_row = await self.database_adapter.fetch_one(
                "SELECT COUNT(*) as count FROM krai_content.images WHERE document_id = ANY($1)",
                [document_ids],
            )
            logger.debug("Completeness images query result for %s: %s", document_ids, images_row)
        except Exception:
            logger.exception("Completeness images query failed for document_ids=%s", document_ids)
            raise

        try:
            error_codes_row = await self.database_adapter.fetch_one(
                "SELECT COUNT(*) as count FROM krai_intelligence.error_codes WHERE document_id = ANY($1)",
                [document_ids],
            )
            logger.debug("Completeness error_codes query result for %s: %s", document_ids, error_codes_row)
        except Exception:
            logger.exception("Completeness error_codes query failed for document_ids=%s", document_ids)
            raise

        chunks_count = self._row_value(chunks_row, "count")
        images_count = self._row_value(images_row, "count")
        error_codes_count = self._row_value(error_codes_row, "count")
        # Detect parts_catalog schema capabilities
        parts_schema = await self._detect_parts_catalog_schema()

        parts_count = 0
        parts_status = "PASS"

        if parts_schema["has_document_id"]:
            # Direct relationship via document_id
            parts_row = await self.database_adapter.fetch_one(
                "SELECT COUNT(*) as count FROM krai_parts.parts_catalog WHERE document_id = ANY($1)",
                [document_ids],
            )
            parts_count = self._row_value(parts_row, "count")
        elif parts_schema["has_product_id"]:
            # Indirect relationship via product_id through document_products
            parts_row = await self.database_adapter.fetch_one(
                """
                SELECT COUNT(DISTINCT pc.id) as count
                FROM krai_parts.parts_catalog pc
                JOIN krai_core.document_products dp ON pc.product_id = dp.product_id
                WHERE dp.document_id = ANY($1)
                """,
                [document_ids],
            )
            parts_count = self._row_value(parts_row, "count")
        elif parts_schema["has_manufacturer_id"]:
            # Indirect relationship via manufacturer_id through products
            parts_row = await self.database_adapter.fetch_one(
                """
                SELECT COUNT(DISTINCT pc.id) as count
                FROM krai_parts.parts_catalog pc
                JOIN krai_core.products p ON p.manufacturer_id = pc.manufacturer_id
                JOIN krai_core.document_products dp ON dp.product_id = p.id
                WHERE dp.document_id = ANY($1)
                """,
                [document_ids],
            )
            parts_count = self._row_value(parts_row, "count")
        else:
            # No valid relationship path - mark as SKIPPED
            parts_status = "SKIPPED"
            parts_count = 0

        chunk_pass = chunks_count >= self.thresholds.get("min_chunks", 100)
        image_pass = images_count >= self.thresholds.get("min_images", 10)
        error_code_pass = error_codes_count >= self.thresholds.get("min_error_codes", 5)
        parts_pass = parts_count >= self.thresholds.get("min_parts", 0)
        warnings = await self._get_stage_warnings(document_ids)

        return {
            "chunks": {
                "count": chunks_count,
                "threshold": self.thresholds.get("min_chunks", 100),
                "status": "PASS" if chunk_pass else "FAIL",
            },
            "images": {
                "count": images_count,
                "threshold": self.thresholds.get("min_images", 10),
                "status": "PASS" if image_pass else "FAIL",
            },
            "error_codes": {
                "count": error_codes_count,
                "threshold": self.thresholds.get("min_error_codes", 5),
                "status": "PASS" if error_code_pass else "FAIL",
                "warnings": warnings if error_codes_count == 0 else None,
            },
            "parts": {
                "count": parts_count,
                "threshold": self.thresholds.get("min_parts", 0),
                "status": parts_status if parts_status == "SKIPPED" else ("PASS" if parts_pass else "FAIL"),
                "warnings": warnings if parts_count == 0 else None,
            },
            "stage_warnings": warnings,
            "status": (
                "PASS"
                if all([chunk_pass, image_pass, error_code_pass, parts_pass or parts_status == "SKIPPED"])
                else "FAIL"
            ),
        }

    async def _detect_parts_catalog_schema(self) -> dict[str, bool]:
        """Detect which relationship columns exist in parts_catalog table."""
        schema_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'krai_parts'
        AND table_name = 'parts_catalog'
        AND column_name IN ('document_id', 'product_id', 'manufacturer_id')
        """
        rows = await self.database_adapter.fetch_all(schema_query, [])
        available_columns = {row["column_name"] for row in (rows or [])}

        return {
            "has_document_id": "document_id" in available_columns,
            "has_product_id": "product_id" in available_columns,
            "has_manufacturer_id": "manufacturer_id" in available_columns,
        }

    async def _check_correctness(self, document_ids: list[str]) -> dict[str, Any]:
        """Validate extraction correctness in a manufacturer-agnostic way.

        For mixed document batches we treat correctness as:
        - at least `min_products` linked products found
        - at least one non-empty model number present
        - at least one non-empty manufacturer name present
        """
        try:
            rows = await self.database_adapter.fetch_all(
                """
                SELECT p.model_number, m.name as manufacturer
                FROM krai_core.document_products dp
                JOIN krai_core.products p ON dp.product_id = p.id
                JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
                WHERE dp.document_id = ANY($1)
                """,
                [document_ids],
            )
            logger.debug("Correctness query returned %s rows for %s", len(rows or []), document_ids)
        except Exception:
            logger.exception("Correctness query failed for document_ids=%s", document_ids)
            raise

        model_detected = False
        manufacturer_detected = False
        products_count = 0

        for row in rows or []:
            row_dict = dict(row)
            products_count += 1
            model_number = (row_dict.get("model_number") or "").lower()
            manufacturer = (row_dict.get("manufacturer") or "").lower()

            if model_number:
                model_detected = True
            if manufacturer:
                manufacturer_detected = True

        min_products = self.thresholds.get("min_products", 1)
        product_count_pass = products_count >= min_products
        correctness_pass = model_detected and manufacturer_detected and product_count_pass
        warnings = await self._get_stage_warnings(document_ids)

        return {
            "products_count": products_count,
            "products_threshold": min_products,
            "model_detected": model_detected,
            "manufacturer_detected": manufacturer_detected,
            "warnings": warnings if products_count == 0 else None,
            "status": "PASS" if correctness_pass else "FAIL",
        }

    async def _check_embeddings(self, document_ids: list[str]) -> dict[str, Any]:
        """Validate embedding coverage against configured threshold."""
        try:
            total_chunks_row = await self.database_adapter.fetch_one(
                "SELECT COUNT(*) as count FROM krai_intelligence.chunks WHERE document_id = ANY($1)",
                [document_ids],
            )
            logger.debug("Embeddings total_chunks query result for %s: %s", document_ids, total_chunks_row)
        except Exception:
            logger.exception("Embeddings total_chunks query failed for document_ids=%s", document_ids)
            raise

        try:
            embedded_chunks_row = await self.database_adapter.fetch_one(
                """
                SELECT COUNT(*) as count
                FROM krai_intelligence.chunks
                WHERE document_id = ANY($1) AND embedding IS NOT NULL
                """,
                [document_ids],
            )
            logger.debug(
                "Embeddings embedded_chunks query result for %s: %s",
                document_ids,
                embedded_chunks_row,
            )
        except Exception:
            logger.exception("Embeddings embedded_chunks query failed for document_ids=%s", document_ids)
            raise

        total_chunks = self._row_value(total_chunks_row, "count")
        chunks_with_embeddings = self._row_value(embedded_chunks_row, "count")
        coverage = (chunks_with_embeddings / total_chunks) if total_chunks > 0 else 0.0

        threshold = float(self.thresholds.get("min_embedding_coverage", 0.95))
        coverage_pass = coverage >= threshold

        return {
            "total_chunks": total_chunks,
            "chunks_with_embeddings": chunks_with_embeddings,
            "coverage": coverage,
            "threshold": threshold,
            "status": "PASS" if coverage_pass else "FAIL",
        }

    async def _check_relationships(self, document_ids: list[str]) -> dict[str, Any]:
        """Validate document-to-product relationships from junction table links."""
        try:
            row = await self.database_adapter.fetch_one(
                """
                SELECT
                    COUNT(DISTINCT dp.document_id) as doc_count,
                    COUNT(DISTINCT dp.product_id) as product_count
                FROM krai_core.document_products dp
                WHERE dp.document_id = ANY($1)
                """,
                [document_ids],
            )
            logger.debug("Relationships query result for %s: %s", document_ids, row)
        except Exception:
            logger.exception("Relationships query failed for document_ids=%s", document_ids)
            raise

        doc_count = self._row_value(row, "doc_count")
        product_count = self._row_value(row, "product_count")
        relation_pass = product_count >= 1 and doc_count >= 1

        return {
            "linked_documents": doc_count,
            "linked_products": product_count,
            "status": "PASS" if relation_pass else "FAIL",
        }

    async def _check_stage_status(self, document_ids: list[str]) -> dict[str, Any]:
        """Validate that all expected stage records exist and are completed."""
        try:
            rows = await self.database_adapter.fetch_all(
                """
                SELECT document_id, stage_number, stage_name, status, metadata
                FROM krai_system.stage_tracking
                WHERE document_id = ANY($1)
                """,
                [document_ids],
            )
            logger.debug("Stage status query returned %s rows for %s", len(rows or []), document_ids)
        except Exception:
            logger.exception("Stage status query failed for document_ids=%s", document_ids)
            raise

        records = rows or []
        total_records = len(records)
        enabled_stage_count = len(self._enabled_stage_names())

        rows_by_document: dict[str, list[dict[str, Any]]] = {}
        for row in records:
            row_dict = dict(row) if not isinstance(row, dict) else row
            doc_id = str(row_dict.get("document_id"))
            rows_by_document.setdefault(doc_id, []).append(row_dict)

        expected_stage_records = enabled_stage_count * len(document_ids)
        completed_stages = 0
        for document_id in document_ids:
            doc_id = str(document_id)
            doc_rows = rows_by_document.get(doc_id, [])

            for row_dict in doc_rows:
                status = (row_dict.get("status") or "").lower()
                metadata = row_dict.get("metadata") or {}
                if status in {"completed", "skipped"}:
                    completed_stages += 1
                    continue
                if isinstance(metadata, dict) and metadata.get("skipped") is True:
                    completed_stages += 1

        extra_stage_records = max(total_records - expected_stage_records, 0)
        stage_pass = total_records >= expected_stage_records and completed_stages >= expected_stage_records

        return {
            "total_stage_records": total_records,
            "expected_stage_records": expected_stage_records,
            "completed_stages": completed_stages,
            "extra_stage_records": extra_stage_records,
            "expected_completed_stages": expected_stage_records,
            "status": "PASS" if stage_pass else "FAIL",
        }

    def _enabled_stage_names(self) -> list[str]:
        """Return expected stage names for current feature flags."""
        stages = [stage.value for stage in Stage]
        if not self._env_flag_enabled("ENABLE_BRIGHTCOVE_ENRICHMENT", default=False):
            stages = [stage for stage in stages if stage != Stage.VIDEO_ENRICHMENT.value]
        if not self._env_flag_enabled("ENABLE_SVG_EXTRACTION", default=False):
            stages = [stage for stage in stages if stage != Stage.SVG_PROCESSING.value]
        return stages

    @staticmethod
    def _env_flag_enabled(name: str, default: bool = False) -> bool:
        value = os.getenv(name, str(default)).strip().lower()
        return value in {"1", "true", "yes", "on"}

    @staticmethod
    def _row_value(row: Any, key: str) -> int:
        """Safely extract an integer value from a DB row mapping."""
        if row is None:
            return 0
        row_dict = dict(row) if not isinstance(row, dict) else row
        return int(row_dict.get(key, 0))

    async def _get_stage_warnings(self, document_ids: list[str]) -> dict[str, list[str]]:
        """Fetch warnings from stage_tracking metadata for documents."""
        try:
            rows = await self.database_adapter.fetch_all(
                """
                SELECT document_id, stage_name, metadata
                FROM krai_system.stage_tracking
                WHERE document_id = ANY($1)
                  AND metadata ? 'warning'
                """,
                [document_ids],
            )

            warnings: dict[str, list[str]] = {}
            for row in rows or []:
                row_dict = dict(row) if not isinstance(row, dict) else row
                doc_id = str(row_dict.get("document_id"))
                stage = row_dict.get("stage_name")
                metadata = row_dict.get("metadata", {}) or {}
                warning = metadata.get("warning", "")

                if doc_id not in warnings:
                    warnings[doc_id] = []
                warnings[doc_id].append(f"{stage}: {warning}")

            return warnings
        except Exception as e:
            logger.warning("Could not fetch stage warnings: %s", e)
            return {}
