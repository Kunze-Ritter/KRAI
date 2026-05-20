"""Regression tests for storage and search processors."""

import json
from types import SimpleNamespace

import pytest

from backend.processors.search_processor import SearchProcessor
from backend.processors.storage_processor import StorageProcessor


class SupabaseResponse:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class SupabaseTableStub:
    def __init__(self, name: str, client: "SupabaseClientStub"):
        self.name = name
        self.client = client
        self.mode = None
        self.payload = None
        self.filters = []
        self.count_kwargs = {}

    def select(self, *args, **kwargs):
        self.mode = "select"
        self.count_kwargs = kwargs
        return self

    def update(self, payload):
        self.mode = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.mode = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        if self.mode == "select":
            if self.name == "vw_processing_queue":
                return SupabaseResponse(data=self.client.queue_data)

            count = None
            if self.count_kwargs.get("count") == "exact":
                count = self.client.counts.get(self.name, 0)
            return SupabaseResponse(data=[], count=count)

        if self.mode == "update":
            self.client.updates.append((self.name, self.payload, list(self.filters)))
            return SupabaseResponse(data=[{"id": "updated"}])

        if self.mode == "insert":
            self.client.inserts.append((self.name, self.payload))
            return SupabaseResponse(data=[{"id": "inserted"}])

        return SupabaseResponse()


class SupabaseRpcStub:
    def __init__(self, client: "SupabaseClientStub", name: str, params: dict):
        self.client = client
        self.client.rpc_calls.append((name, params))

    def execute(self):
        return SupabaseResponse()


class SupabaseClientStub:
    def __init__(self, *, counts=None, queue_data=None):
        self.counts = counts or {}
        self.queue_data = queue_data or []
        self.updates = []
        self.inserts = []
        self.rpc_calls = []

    def table(self, name: str) -> SupabaseTableStub:
        return SupabaseTableStub(name, self)

    def rpc(self, name: str, params: dict) -> SupabaseRpcStub:
        return SupabaseRpcStub(self, name, params)


class DatabaseServiceStub:
    def __init__(self, client: SupabaseClientStub):
        self.client = client


class StorageServiceStub:
    def __init__(self):
        self.calls = []
        self.client = object()

    async def upload_image(self, content, filename, bucket_type="document_images", metadata=None):
        self.calls.append(
            {
                "content": content,
                "filename": filename,
                "bucket_type": bucket_type,
                "metadata": metadata or {},
            }
        )
        return {
            "success": True,
            "url": f"https://storage.example/{filename}",
            "storage_path": filename,
            "file_hash": "mockhash",
        }


@pytest.mark.asyncio
async def test_storage_processor_handles_empty_queue():
    client = SupabaseClientStub(queue_data=[])
    database_service = DatabaseServiceStub(client)
    storage_service = SimpleNamespace(
        upload_image=lambda *args, **kwargs: {"success": True, "url": "https://example.com/mock"}
    )

    processor = StorageProcessor(database_service, storage_service)
    context = SimpleNamespace(document_id="doc-001")

    result = await processor.process(context)

    assert result.success is True
    assert result.data["saved_items"] == 0
    assert client.inserts == []


@pytest.mark.asyncio
async def test_search_processor_marks_document_search_ready():
    counts = {
        "vw_chunks": 5,
        "vw_embeddings": 5,
        "vw_links": 2,
        "vw_videos": 1,
    }
    client = SupabaseClientStub(counts=counts)
    database_service = DatabaseServiceStub(client)

    processor = SearchProcessor(database_service, ai_service=None)
    context = SimpleNamespace(document_id="doc-xyz")

    called = False

    def mock_log_document_indexed(**kwargs):
        nonlocal called
        called = True
        return True

    processor.analytics.log_document_indexed = mock_log_document_indexed

    result = await processor.process(context)

    assert result.success is True
    assert result.data == {
        "chunks_indexed": 5,
        "embeddings_indexed": 5,
        "links_indexed": 2,
        "videos_indexed": 1,
        "processing_time_seconds": pytest.approx(result.data["processing_time_seconds"], rel=0),
    }

    # Ensure document flags were updated
    assert client.updates, "Expected document update call"
    update_table, payload, filters = client.updates[0]
    assert update_table == "vw_documents"
    assert payload["search_ready"] is True
    assert filters == [("id", "doc-xyz")]

    # Stage tracker should record start and completion
    rpc_names = [name for name, _ in client.rpc_calls]
    assert "start_stage" in rpc_names
    assert "complete_stage" in rpc_names

    assert called is True


@pytest.mark.asyncio
async def test_storage_processor_uploads_image_artifact():
    payload = {
        "document_id": "doc-img",
        "content": b"binary-image-data",
        "filename": "page-1-image.png",
        "bucket_type": "document_images",
        "metadata": {"page_number": 1},
        "page_number": 1,
        "image_type": "diagram",
    }
    queue_entry = {
        "id": "queue-image",
        "artifact_type": "image",
        "payload": payload,
    }

    client = SupabaseClientStub(queue_data=[queue_entry])
    database_service = DatabaseServiceStub(client)
    storage_service = StorageServiceStub()

    processor = StorageProcessor(database_service, storage_service)
    context = SimpleNamespace(document_id="doc-img")

    result = await processor.process(context)

    assert result.success is True
    assert result.data["saved_items"] == 1

    # Verify upload image called
    assert storage_service.calls
    call = storage_service.calls[0]
    assert call["filename"] == payload["filename"]

    # Ensure database insert occurred for image metadata
    inserted_tables = [table for table, _ in client.inserts]
    assert "vw_images" in inserted_tables


@pytest.mark.asyncio
async def test_storage_processor_persists_link_artifact():
    payload = {
        "document_id": "doc-123",
        "url": "https://example.com/link",
        "description": "Support portal",
        "link_type": "support",
        "link_category": "support_portal",
        "page_number": 2,
        "position_data": {"type": "text_extraction"},
        "confidence_score": 0.95,
        "manufacturer_id": "m-1",
        "series_id": "s-1",
        "related_error_codes": ["E01"],
    }
    queue_entry = {
        "id": "queue-1",
        "artifact_type": "link",
        "payload": json.dumps(payload),
    }

    client = SupabaseClientStub(queue_data=[queue_entry])
    database_service = DatabaseServiceStub(client)
    storage_service = SimpleNamespace(
        upload_image=lambda *args, **kwargs: {
            "success": True,
            "url": "https://example.com/mock",
            "storage_path": "mock/path",
            "file_hash": "hash",
        }
    )

    processor = StorageProcessor(database_service, storage_service)
    context = SimpleNamespace(document_id="doc-123")

    result = await processor.process(context)

    assert result.success is True
    assert result.data["saved_items"] == 1
    assert client.inserts, "Expected link insert"

    table, inserted_payload = client.inserts[0]
    assert table == "vw_links"
    assert inserted_payload["url"] == payload["url"]
    assert inserted_payload["related_error_codes"] == payload["related_error_codes"]


@pytest.mark.asyncio
async def test_search_processor_handles_missing_embeddings():
    counts = {
        "vw_chunks": 4,
        "vw_embeddings": 0,
        "vw_links": 1,
        "vw_videos": 0,
    }
    client = SupabaseClientStub(counts=counts)
    database_service = DatabaseServiceStub(client)

    processor = SearchProcessor(database_service, ai_service=None)
    context = SimpleNamespace(document_id="doc-missing")

    result = await processor.process(context)

    # Even without embeddings we should still succeed (with warning)
    assert result.success is True
    assert result.data["embeddings_indexed"] == 0
    assert client.updates, "Expected document update"

    table, payload, filters = client.updates[0]
    assert table == "vw_documents"
    assert payload["search_ready"] is False
    assert filters == [("id", "doc-missing")]

    rpc_names = [name for name, _ in client.rpc_calls]
    assert "start_stage" in rpc_names
    assert "complete_stage" in rpc_names
