from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from typing import Any

import pytest

from backend.processors.storage_processor import StorageProcessor


class MockResult:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data


class MockTable:
    def __init__(self, storage: list[dict[str, Any]]):
        self._storage = storage
        self._filters: dict[str, Any] = {}
        self._insert_buffer: list[dict[str, Any]] | None = None

    def select(self, *_args, **_kwargs) -> MockTable:
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
    def __init__(self):
        self.tables: dict[str, list[dict[str, Any]]] = {
            "vw_processing_queue": [],
            "vw_links": [],
            "vw_videos": [],
            "vw_chunks": [],
            "vw_embeddings": [],
            "vw_images": [],
        }

    def table(self, name: str) -> MockTable:
        self.tables.setdefault(name, [])
        return MockTable(self.tables[name])


class MockDatabaseService:
    def __init__(self) -> None:
        self.client = MockClient()


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


@pytest.fixture
def db_service() -> MockDatabaseService:
    return MockDatabaseService()


@pytest.fixture
def storage_service() -> AsyncStorageService:
    return AsyncStorageService(success=True)


@pytest.mark.storage
@pytest.mark.e2e
class TestStorageProcessorE2E:
    @pytest.mark.asyncio
    async def test_process_persists_all_artifact_types(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        queue = db_service.client.tables["vw_processing_queue"]
        document_id = "doc-all"

        link_payload = {
            "document_id": document_id,
            "url": "https://example.com/manual",
            "description": "Service manual",
            "page_number": 1,
            "confidence_score": 0.95,
        }
        video_payload = {
            "document_id": document_id,
            "link_id": "link-1",
            "youtube_id": "YTB123",
            "title": "Repair Video",
            "description": "How to repair",
            "page_number": 2,
        }
        chunk_payload = {
            "document_id": document_id,
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 1,
            "content": "Chunk content",
            "content_hash": "hash-1",
            "char_count": 13,
            "metadata": {"type": "text"},
        }
        embedding_payload = {
            "document_id": document_id,
            "chunk_id": "chunk-1",
            "embedding": [0.1, 0.2, 0.3],
            "model": "test-model",
            "embedding_type": "document",
        }
        raw_image = b"image-bytes"
        image_payload = {
            "document_id": document_id,
            "page_number": 3,
            "image_type": "diagram",
            "filename": "image.png",
            "content": base64.b64encode(raw_image).decode("utf-8"),
            "content_encoding": "base64",
            "metadata": {"w": 100, "h": 200},
        }

        queue.extend(
            [
                {
                    "id": "q-link",
                    "document_id": document_id,
                    "stage": "storage",
                    "status": "pending",
                    "artifact_type": "link",
                    "payload": json.dumps(link_payload),
                    "created_at": "now",
                },
                {
                    "id": "q-video",
                    "document_id": document_id,
                    "stage": "storage",
                    "status": "pending",
                    "artifact_type": "video",
                    "payload": json.dumps(video_payload),
                    "created_at": "now",
                },
                {
                    "id": "q-chunk",
                    "document_id": document_id,
                    "stage": "storage",
                    "status": "pending",
                    "artifact_type": "chunk",
                    "payload": json.dumps(chunk_payload),
                    "created_at": "now",
                },
                {
                    "id": "q-embedding",
                    "document_id": document_id,
                    "stage": "storage",
                    "status": "pending",
                    "artifact_type": "embedding",
                    "payload": json.dumps(embedding_payload),
                    "created_at": "now",
                },
                {
                    "id": "q-image",
                    "document_id": document_id,
                    "stage": "storage",
                    "status": "pending",
                    "artifact_type": "image",
                    "payload": json.dumps(image_payload),
                    "created_at": "now",
                },
            ]
        )

        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)
        context = SimpleNamespace(document_id=document_id)

        result = await processor.process(context)

        assert result.success is True
        assert result.data["saved_items"] == 5

        links = db_service.client.tables["vw_links"]
        videos = db_service.client.tables["vw_videos"]
        chunks = db_service.client.tables["vw_chunks"]
        embeddings = db_service.client.tables["vw_embeddings"]
        images = db_service.client.tables["vw_images"]

        assert len(links) == 1
        assert links[0]["url"] == link_payload["url"]

        assert len(videos) == 1
        assert videos[0]["youtube_id"] == video_payload["youtube_id"]

        assert len(chunks) == 1
        assert chunks[0]["content"] == chunk_payload["content"]

        assert len(embeddings) == 1
        assert embeddings[0]["model"] == embedding_payload["model"]

        assert len(images) == 1
        assert images[0]["storage_path"].endswith(image_payload["filename"])
        assert images[0]["document_id"] == document_id

    @pytest.mark.asyncio
    async def test_process_no_pending_artifacts_returns_zero(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)
        context = SimpleNamespace(document_id="doc-empty")

        result = await processor.process(context)

        assert result.success is True
        assert result.data["saved_items"] == 0
        assert "No pending artifacts" in result.message

    @pytest.mark.asyncio
    async def test_process_skips_unsupported_artifact_type(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        queue = db_service.client.tables["vw_processing_queue"]
        document_id = "doc-unsupported"

        queue.append(
            {
                "id": "q-ignored",
                "document_id": document_id,
                "stage": "storage",
                "status": "pending",
                "artifact_type": "unsupported",
                "payload": json.dumps({"foo": "bar"}),
                "created_at": "now",
            }
        )
        queue.append(
            {
                "id": "q-link",
                "document_id": document_id,
                "stage": "storage",
                "status": "pending",
                "artifact_type": "link",
                "payload": json.dumps({"document_id": document_id, "url": "https://example.com"}),
                "created_at": "now",
            }
        )

        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)
        context = SimpleNamespace(document_id=document_id)

        result = await processor.process(context)

        assert result.success is True
        assert result.data["saved_items"] == 1

        links = db_service.client.tables["vw_links"]
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_process_with_upload_failure_records_no_image(self, db_service: MockDatabaseService):
        storage = AsyncStorageService(success=False)
        queue = db_service.client.tables["vw_processing_queue"]
        document_id = "doc-upload-fail"

        image_payload = {
            "document_id": document_id,
            "filename": "image.png",
            "content": base64.b64encode(b"data").decode("utf-8"),
            "content_encoding": "base64",
        }

        queue.append(
            {
                "id": "q-image",
                "document_id": document_id,
                "stage": "storage",
                "status": "pending",
                "artifact_type": "image",
                "payload": json.dumps(image_payload),
                "created_at": "now",
            }
        )

        processor = StorageProcessor(database_service=db_service, storage_service=storage)
        context = SimpleNamespace(document_id=document_id)

        result = await processor.process(context)

        assert result.success is False
        assert result.data["saved_items"] == 0
        assert "errors" in result.data
        assert len(result.data["errors"]) >= 1

        images = db_service.client.tables["vw_images"]
        assert images == []

    @pytest.mark.asyncio
    async def test_process_with_invalid_json_payload(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        queue = db_service.client.tables["vw_processing_queue"]
        document_id = "doc-invalid-json"

        queue.append(
            {
                "id": "q-link-invalid",
                "document_id": document_id,
                "stage": "storage",
                "status": "pending",
                "artifact_type": "link",
                "payload": "{invalid-json}",
                "created_at": "now",
            }
        )

        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)
        context = SimpleNamespace(document_id=document_id)

        result = await processor.process(context)

        assert result.success is True
        assert result.data["saved_items"] == 1

        links = db_service.client.tables["vw_links"]
        assert len(links) == 1
        assert links[0]["url"] is None

    @pytest.mark.asyncio
    async def test_process_with_missing_document_id_raises(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)
        context = SimpleNamespace()

        with pytest.raises(ValueError):
            await processor.process(context)
