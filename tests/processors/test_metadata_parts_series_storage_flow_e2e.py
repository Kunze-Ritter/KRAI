from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

import backend.core.base_processor as backend_base_processor
import backend.processors.parts_processor as parts_mod
import backend.utils.series_detector as backend_series_detector
from backend.core.base_processor import ProcessingContext
from backend.processors.metadata_processor_ai import MetadataProcessorAI
from backend.processors.parts_processor import PartsProcessor
from backend.processors.storage_processor import StorageProcessor

core_pkg = types.ModuleType("core")
core_pkg.base_processor = backend_base_processor
sys.modules.setdefault("core", core_pkg)
sys.modules.setdefault("core.base_processor", backend_base_processor)

utils_pkg = types.ModuleType("utils")
utils_pkg.series_detector = backend_series_detector
sys.modules.setdefault("utils", utils_pkg)
sys.modules.setdefault("utils.series_detector", backend_series_detector)

from backend.processors.series_processor import SeriesProcessor  # noqa: E402


class MockResult:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


class MockTable:
    def __init__(self, storage: list[dict[str, Any]], name: str):
        self._storage = storage
        self._name = name
        self._filters: dict[str, Any] = {}
        self._insert_buffer: list[dict[str, Any]] | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> MockTable:
        return self

    def eq(self, key: str, value: Any) -> MockTable:
        self._filters[key] = value
        return self

    def insert(self, payload: dict[str, Any] | list[dict[str, Any]]) -> MockTable:
        if isinstance(payload, list):
            self._insert_buffer = payload
        else:
            self._insert_buffer = [payload]
        return self

    def execute(self) -> MockResult:
        if self._insert_buffer is not None:
            for row in self._insert_buffer:
                if "id" not in row:
                    row["id"] = f"{self._name}-{len(self._storage) + 1}"
            self._storage.extend(self._insert_buffer)
            data = list(self._insert_buffer)
            self._insert_buffer = None
            return MockResult(data)

        data: list[dict[str, Any]] = []
        for row in self._storage:
            match = True
            for key, value in self._filters.items():
                if row.get(key) != value:
                    match = False
                    break
            if match:
                data.append(row)
        return MockResult(data)


class MockClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "vw_processing_queue": [],
            "vw_links": [],
            "vw_videos": [],
            "vw_chunks": [],
            "vw_embeddings": [],
            "vw_images": [],
            "documents": [],
            "error_codes": [],
            "chunks": [],
            "products": [],
            "manufacturers": [],
            "product_series": [],
            "parts_catalog": [],
        }

    def table(self, name: str) -> MockTable:
        self.tables.setdefault(name, [])
        return MockTable(self.tables[name], name)


class AsyncStorageService:
    """Minimal async storage service compatible with StorageProcessor."""

    def __init__(self, success: bool = True) -> None:
        self.client = object()
        self.success = success
        self.upload_calls: list[dict[str, Any]] = []

    async def upload_image(
        self,
        content: bytes,
        filename: str,
        bucket_type: str = "document_images",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.upload_calls.append(
            {
                "content": content,
                "filename": filename,
                "bucket_type": bucket_type,
                "metadata": metadata or {},
            }
        )
        if not self.success:
            return {"success": False}
        return {
            "success": True,
            "url": f"https://mock-storage/{bucket_type}/{filename}",
            "storage_path": f"{bucket_type}/{filename}",
            "file_hash": "mock-hash",
        }


class UnifiedMockDatabase:
    def __init__(self) -> None:
        self.client = MockClient()
        self.error_code_part_links: list[dict[str, Any]] = []

    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        for row in self.client.tables["documents"]:
            if row.get("id") == document_id:
                return row
        return None

    async def update_document(self, document_id: str, updates: dict[str, Any]) -> bool:
        doc = await self.get_document(document_id)
        if not doc:
            return False
        doc.update(updates)
        return True

    async def get_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return [c for c in self.client.tables["chunks"] if c.get("document_id") == document_id]

    async def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        for c in self.client.tables["chunks"]:
            if c.get("id") == chunk_id:
                return c
        return None

    async def get_error_codes_by_document(self, document_id: str) -> list[dict[str, Any]]:
        return [e for e in self.client.tables["error_codes"] if e.get("document_id") == document_id]

    async def get_part_by_number_and_manufacturer(
        self, part_number: str, manufacturer_id: str
    ) -> dict[str, Any] | None:
        for p in self.client.tables["parts_catalog"]:
            if p.get("part_number") == part_number and p.get("manufacturer_id") == manufacturer_id:
                return p
        return None

    async def get_part_by_number(self, part_number: str) -> dict[str, Any] | None:
        for p in self.client.tables["parts_catalog"]:
            if p.get("part_number") == part_number:
                return p
        return None

    async def create_part(self, part_data: dict[str, Any]) -> None:
        stored = dict(part_data)
        if "id" not in stored:
            stored["id"] = f"part-{len(self.client.tables['parts_catalog']) + 1}"
        self.client.tables["parts_catalog"].append(stored)

    async def update_part(self, part_id: str, updates: dict[str, Any]) -> bool:
        for p in self.client.tables["parts_catalog"]:
            if p.get("id") == part_id:
                p.update(updates)
                return True
        return False

    async def create_error_code_part_link(self, data: dict[str, Any]) -> None:
        self.error_code_part_links.append(dict(data))

    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        for p in self.client.tables["products"]:
            if p.get("id") == product_id:
                return p
        return None

    async def get_manufacturer(self, manufacturer_id: str) -> dict[str, Any] | None:
        for m in self.client.tables["manufacturers"]:
            if m.get("id") == manufacturer_id:
                return m
        return None

    async def update_product(self, product_id: str, updates: dict[str, Any]) -> bool:
        for p in self.client.tables["products"]:
            if p.get("id") == product_id:
                p.update(updates)
                return True
        return False

    async def get_product_series_by_name_and_pattern(
        self, manufacturer_id: str, series_name: str, model_pattern: str | None
    ) -> dict[str, Any] | None:
        for s in self.client.tables["product_series"]:
            if (
                s.get("manufacturer_id") == manufacturer_id
                and s.get("series_name") == series_name
                and s.get("model_pattern") == model_pattern
            ):
                return s
        return None

    async def create_product_series(self, series_data: dict[str, Any]) -> dict[str, Any]:
        stored = dict(series_data)
        if "id" not in stored:
            stored["id"] = f"series-{len(self.client.tables['product_series']) + 1}"
        self.client.tables["product_series"].append(stored)
        return stored

    async def get_product_series_by_manufacturer(self, manufacturer_id: str) -> list[dict[str, Any]]:
        return [s for s in self.client.tables["product_series"] if s.get("manufacturer_id") == manufacturer_id]


@pytest.fixture
def unified_db() -> UnifiedMockDatabase:
    return UnifiedMockDatabase()


@pytest.fixture
def storage_service() -> AsyncStorageService:
    return AsyncStorageService(success=True)


@pytest.mark.e2e
@pytest.mark.metadata
@pytest.mark.parts
@pytest.mark.series
@pytest.mark.storage
@pytest.mark.asyncio
async def test_metadata_parts_series_storage_flow(
    unified_db: UnifiedMockDatabase,
    storage_service: AsyncStorageService,
    tmp_path,
):
    document_id = "doc-1"
    manufacturer_id = "manu-1"
    product_id = "prod-1"

    unified_db.client.tables["documents"].append(
        {
            "id": document_id,
            "manufacturer": "HP",
            "manufacturer_id": manufacturer_id,
            "model_number": "M404n",
        }
    )
    unified_db.client.tables["manufacturers"].append({"id": manufacturer_id, "name": "HP"})
    unified_db.client.tables["products"].append(
        {
            "id": product_id,
            "model_number": "M404n",
            "manufacturer_id": manufacturer_id,
            "series_id": None,
        }
    )

    chunk_id = "chunk-1"
    chunk_text = "Error 900.01: Replace fuser unit (part A0X1-1234) to continue."
    unified_db.client.tables["chunks"].append(
        {
            "id": chunk_id,
            "document_id": document_id,
            "chunk_index": 0,
            "content": chunk_text,
        }
    )

    link_payload = {
        "document_id": document_id,
        "url": "https://example.com/support",
        "description": "Support page",
        "page_number": 1,
        "confidence_score": 0.9,
    }
    unified_db.client.tables["vw_processing_queue"].append(
        {
            "id": "q-link-1",
            "document_id": document_id,
            "stage": "storage",
            "status": "pending",
            "artifact_type": "link",
            "payload": json.dumps(link_payload),
            "created_at": "now",
        }
    )

    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_text("dummy")

    metadata_proc = MetadataProcessorAI(database_service=unified_db)

    def fake_error_extract(pdf_path, manufacturer: str, *args, **kwargs):
        from types import SimpleNamespace as _NS

        return [
            _NS(
                error_code="900.01",
                error_description="Fuser unit error",
                solution_text=chunk_text,
                page_number=1,
                confidence=0.95,
                extraction_method="regex",
                requires_technician=True,
                requires_parts=True,
                severity_level="high",
                context_text="context",
                chunk_id=chunk_id,
                product_id=None,
                video_id=None,
            )
        ]

    metadata_proc.error_code_extractor.extract = fake_error_extract
    metadata_proc.version_extractor.extract = lambda _path: "v1.0"

    meta_ctx = ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        manufacturer="HP",
        model="M404n",
        language="en",
    )

    meta_result = await metadata_proc.process(meta_ctx)
    assert meta_result.success is True
    assert len(unified_db.client.tables["error_codes"]) == 1
    doc_row = await unified_db.get_document(document_id)
    assert doc_row.get("version") == "v1.0"

    original_extract_parts = parts_mod.extract_parts_with_context

    def fake_extract_parts(text: str, manufacturer_key: str = "hp", max_parts: int = 10):
        return [
            {
                "part": "A0X1-1234",
                "context": text,
                "confidence": 0.99,
            }
        ]

    parts_mod.extract_parts_with_context = fake_extract_parts
    try:
        parts_proc = PartsProcessor(database_adapter=unified_db)
        parts_ctx = SimpleNamespace(document_id=document_id)
        parts_result = await parts_proc.process(parts_ctx)
    finally:
        parts_mod.extract_parts_with_context = original_extract_parts

    assert parts_result.success is True
    assert len(unified_db.client.tables["parts_catalog"]) >= 1
    assert len(unified_db.error_code_part_links) >= 1

    series_proc = SeriesProcessor(database_adapter=unified_db)
    series_ctx = SimpleNamespace(product_id=product_id)
    series_result = await series_proc.process(series_ctx)
    assert series_result.success is True
    assert series_result.data["series_detected"] is True

    product_row = await unified_db.get_product(product_id)
    assert product_row.get("series_id") is not None
    assert len(unified_db.client.tables["product_series"]) >= 1

    storage_proc = StorageProcessor(
        database_service=unified_db,
        storage_service=storage_service,
    )
    storage_ctx = SimpleNamespace(document_id=document_id)
    storage_result = await storage_proc.process(storage_ctx)

    assert storage_result.success is True
    assert storage_result.data["saved_items"] == 1
    links = unified_db.client.tables["vw_links"]
    assert len(links) == 1
    assert links[0]["url"] == link_payload["url"]
