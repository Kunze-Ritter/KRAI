from __future__ import annotations

import base64
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

    # Query API
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
@pytest.mark.unit
class TestStorageProcessorUnit:
    async def test_load_pending_artifacts_from_queue(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        queue = db_service.client.tables["vw_processing_queue"]
        queue.append(
            {
                "id": "q1",
                "document_id": "doc-1",
                "stage": "storage",
                "status": "pending",
                "artifact_type": "link",
                "payload": '{"url": "http://example.com"}',
                "created_at": "now",
            }
        )

        artifacts = await processor._load_pending_artifacts("doc-1", processor._logger_adapter)
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "link"
        assert artifacts[0]["payload"]["url"] == "http://example.com"

    async def test_load_pending_artifacts_with_empty_queue(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifacts = await processor._load_pending_artifacts("doc-1", processor._logger_adapter)
        assert artifacts == []

    async def test_load_pending_artifacts_with_invalid_json(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        queue = db_service.client.tables["vw_processing_queue"]
        queue.append(
            {
                "id": "q1",
                "document_id": "doc-1",
                "stage": "storage",
                "status": "pending",
                "artifact_type": "link",
                "payload": "{invalid-json}",
                "created_at": "now",
            }
        )

        artifacts = await processor._load_pending_artifacts("doc-1", processor._logger_adapter)
        assert len(artifacts) == 1
        assert artifacts[0]["payload"] == {}

    async def test_load_pending_artifacts_without_db_service(self):
        processor = StorageProcessor(database_service=None)
        artifacts = await processor._load_pending_artifacts("doc-1", processor._logger_adapter)
        assert artifacts == []

    async def test_store_link_artifact(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "a1",
            "artifact_type": "link",
            "payload": {
                "document_id": "doc-1",
                "url": "http://example.com",
                "description": "Example",
                "page_number": 1,
                "confidence_score": 0.9,
            },
        }

        await processor._store_link_artifact(artifact, processor._logger_adapter)
        links = db_service.client.tables["vw_links"]
        assert len(links) == 1
        assert links[0]["url"] == "http://example.com"
        assert links[0]["link_type"] == "external"

    async def test_store_link_artifact_rich_metadata(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "a2",
            "artifact_type": "link",
            "payload": {
                "document_id": "doc-ctx",
                "url": "https://example.com/ctx",
                "description": "Context link",
                "page_number": 2,
                "confidence_score": 0.8,
                "link_type": "internal",
                "link_category": "doc_reference",
                "position_data": {"x": 10, "y": 20},
                "manufacturer_id": "m1",
                "series_id": "s1",
                "related_error_codes": ["ec-1", "ec-2"],
                "context_description": "Link found in troubleshooting section",
                "page_header": "Troubleshooting",
                "related_products": ["prod-1", "prod-2"],
                "related_chunks": ["chunk-1", "chunk-2"],
            },
        }

        await processor._store_link_artifact(artifact, processor._logger_adapter)
        links = db_service.client.tables["vw_links"]
        assert len(links) == 1
        link = links[0]
        assert link["document_id"] == "doc-ctx"
        assert link["link_type"] == "internal"
        assert link["link_category"] == "doc_reference"
        assert link["context_description"] == "Link found in troubleshooting section"
        assert link["page_header"] == "Troubleshooting"
        assert link["related_error_codes"] == ["ec-1", "ec-2"]
        assert link["related_products"] == ["prod-1", "prod-2"]
        assert link["related_chunks"] == ["chunk-1", "chunk-2"]

    async def test_store_video_artifact(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "v1",
            "artifact_type": "video",
            "payload": {
                "document_id": "doc-1",
                "link_id": "l1",
                "youtube_id": "ABC123",
                "title": "Test Video",
                "description": "Desc",
                "page_number": 2,
            },
        }

        await processor._store_video_artifact(artifact, processor._logger_adapter)
        videos = db_service.client.tables["vw_videos"]
        assert len(videos) == 1
        assert videos[0]["youtube_id"] == "ABC123"
        assert videos[0]["platform"] == "youtube"

    async def test_store_video_artifact_rich_metadata(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "v2",
            "artifact_type": "video",
            "payload": {
                "document_id": "doc-ctx",
                "link_id": "link-ctx",
                "youtube_id": "YTB999",
                "title": "Rich Context Video",
                "description": "How-to guide",
                "thumbnail_url": "https://img.yt/ytb999.jpg",
                "duration": 120,
                "platform": "youtube",
                "metadata": {"quality": "1080p"},
                "manufacturer_id": "m1",
                "series_id": "s1",
                "context_description": "Embedded in service manual",
                "page_number": 5,
                "page_header": "Service Videos",
                "related_error_codes": ["ec-10"],
                "related_products": ["prod-10"],
                "related_chunks": ["chunk-10"],
            },
        }

        await processor._store_video_artifact(artifact, processor._logger_adapter)
        videos = db_service.client.tables["vw_videos"]
        assert len(videos) == 1
        video = videos[0]
        assert video["document_id"] == "doc-ctx"
        assert video["link_id"] == "link-ctx"
        assert video["youtube_id"] == "YTB999"
        assert video["title"] == "Rich Context Video"
        assert video["page_number"] == 5
        assert video["page_header"] == "Service Videos"
        assert video["context_description"] == "Embedded in service manual"
        assert video["related_error_codes"] == ["ec-10"]
        assert video["related_products"] == ["prod-10"]
        assert video["related_chunks"] == ["chunk-10"]

    async def test_store_chunk_artifact(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "c1",
            "artifact_type": "chunk",
            "payload": {
                "document_id": "doc-1",
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Chunk content",
                "content_hash": "hash",
                "char_count": 13,
                "metadata": {"type": "text"},
            },
        }

        await processor._store_chunk_artifact(artifact, processor._logger_adapter)
        chunks = db_service.client.tables["vw_chunks"]
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Chunk content"

    async def test_store_embedding_artifact(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        artifact = {
            "id": "e1",
            "artifact_type": "embedding",
            "payload": {
                "document_id": "doc-1",
                "chunk_id": "ch1",
                "embedding": [0.1, 0.2, 0.3],
                "model": "test-model",
                "embedding_type": "document",
            },
        }

        await processor._store_embedding_artifact(artifact, processor._logger_adapter)
        embeddings = db_service.client.tables["vw_embeddings"]
        assert len(embeddings) == 1
        assert embeddings[0]["model"] == "test-model"

    async def test_store_image_artifact_with_upload_and_insert(
        self, db_service: MockDatabaseService, storage_service: AsyncStorageService
    ):
        processor = StorageProcessor(database_service=db_service, storage_service=storage_service)

        raw_content = b"image-bytes"
        encoded = base64.b64encode(raw_content).decode("utf-8")
        artifact = {
            "id": "img1",
            "artifact_type": "image",
            "payload": {
                "document_id": "doc-1",
                "page_number": 1,
                "image_type": "diagram",
                "filename": "image.png",
                "content": encoded,
                "content_encoding": "base64",
                "ai_description": "desc",
                "ocr_text": "ocr",
                "context_caption": "Fuser assembly diagram",
                "page_header": "Exploded Views",
                "figure_reference": "Figure 3-2",
                "related_error_codes": ["13.A1.B2"],
                "related_products": ["M404n"],
                "surrounding_paragraphs": ["See figure 3-2 for fuser details."],
                "related_chunks": ["chunk-42"],
                "metadata": {"w": 100, "h": 200},
            },
        }

        await processor._store_image_artifact(artifact, processor._logger_adapter)

        assert storage_service.upload_calls
        images = db_service.client.tables["vw_images"]
        assert len(images) == 1
        image = images[0]
        assert image["storage_path"].endswith("image.png")
        assert image["document_id"] == "doc-1"
        assert image["context_caption"] == "Fuser assembly diagram"
        assert image["page_header"] == "Exploded Views"
        assert image["figure_reference"] == "Figure 3-2"
        assert image["related_error_codes"] == ["13.A1.B2"]
        assert image["related_products"] == ["M404n"]
        assert image["surrounding_paragraphs"] == ["See figure 3-2 for fuser details."]
        assert image["related_chunks"] == ["chunk-42"]

    async def test_store_image_artifact_without_storage_service(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service, storage_service=None)
        artifact = {
            "id": "img1",
            "artifact_type": "image",
            "payload": {"content": b"x", "filename": "img.png"},
        }

        await processor._store_image_artifact(artifact, processor._logger_adapter)

        images = db_service.client.tables["vw_images"]
        assert images == []

    async def test_store_image_artifact_with_upload_failure(self, db_service: MockDatabaseService):
        storage = AsyncStorageService(success=False)
        processor = StorageProcessor(database_service=db_service, storage_service=storage)

        encoded = base64.b64encode(b"data").decode("utf-8")
        artifact = {
            "id": "img1",
            "artifact_type": "image",
            "payload": {
                "document_id": "doc-1",
                "filename": "image.png",
                "content": encoded,
                "content_encoding": "base64",
            },
        }

        with pytest.raises(ValueError):
            await processor._store_image_artifact(artifact, processor._logger_adapter)

        images = db_service.client.tables["vw_images"]
        assert images == []

    def test_create_result_helper(self, db_service: MockDatabaseService):
        processor = StorageProcessor(database_service=db_service)
        result = processor._create_result(True, "ok", {"saved_items": 1})
        assert result.success is True
        assert result.message == "ok"
        assert result.data["saved_items"] == 1
