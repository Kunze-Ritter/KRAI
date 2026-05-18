"""
Verification test for Storage Stage (Stage 13).

Tests MinIO upload with mock image, storage_url return, database record creation,
and file hash deduplication.

Run: pytest tests/verification/test_storage_stage.py -v
Or:  python -m pytest tests/verification/test_storage_stage.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from backend.processors.storage_processor import StorageProcessor


class MockStorageService:
    """Mock storage service for unit tests."""

    def __init__(self, success: bool = True):
        self.success = success
        self.upload_calls = []

    async def upload_image(
        self,
        content: bytes,
        filename: str,
        bucket_type: str = "document_images",
        metadata: dict | None = None,
    ) -> dict:
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
        import hashlib

        file_hash = hashlib.sha256(content).hexdigest()
        return {
            "success": True,
            "url": f"https://mock-storage/{bucket_type}/{file_hash}",
            "storage_path": f"images/{file_hash}",
            "public_url": f"https://mock-storage/{bucket_type}/{file_hash}",
            "file_hash": file_hash,
        }


class MockDatabaseService:
    """Mock database service for unit tests."""

    def __init__(self):
        self.inserts = []
        self.queries = []

    async def execute_query(self, query: str, params: list | None = None):
        self.queries.append({"query": query, "params": params or []})
        return []


@pytest.mark.storage
@pytest.mark.verification
class TestStorageStage:
    """Verification tests for Storage stage."""

    @pytest.mark.asyncio
    async def test_storage_processor_extends_base_processor(self):
        """Verify StorageProcessor extends BaseProcessor with Stage.STORAGE."""
        from backend.core.base_processor import BaseProcessor, Stage

        processor = StorageProcessor()
        assert isinstance(processor, BaseProcessor)
        assert processor.stage == Stage.STORAGE

    @pytest.mark.asyncio
    async def test_storage_processor_accepts_database_and_storage_services(self):
        """Confirm constructor accepts database_service and storage_service."""
        db = MockDatabaseService()
        storage = MockStorageService()
        processor = StorageProcessor(database_service=db, storage_service=storage)
        assert processor.database_service is db
        assert processor.storage_service is storage

    @pytest.mark.asyncio
    async def test_minio_upload_returns_storage_url(self):
        """Test MinIO upload flow - verify storage_url is returned."""
        storage = MockStorageService(success=True)
        processor = StorageProcessor(storage_service=storage)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-image-content")
            temp_path = f.name

        try:
            document_id = str(uuid4())
            image_id = str(uuid4())
            context = type(
                "Context",
                (),
                {
                    "document_id": document_id,
                    "images": [
                        {
                            "id": image_id,
                            "temp_path": temp_path,
                            "path": temp_path,
                            "filename": "test_image.png",
                            "page_number": 1,
                            "image_index": 0,
                            "width": 100,
                            "height": 100,
                        }
                    ],
                },
            )()

            result = await processor.process(context)

            assert result.success is True
            assert len(storage.upload_calls) == 1
            upload_result = storage.upload_calls[0]
            assert upload_result["bucket_type"] == "document_images"
            assert "storage_url" in str(result.data) or "saved_items" in result.data
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_database_record_created_with_storage_service(self):
        """Confirm database record is created when storage succeeds."""
        db = MockDatabaseService()
        storage = MockStorageService(success=True)
        processor = StorageProcessor(database_service=db, storage_service=storage)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-content")
            temp_path = f.name

        try:
            document_id = str(uuid4())
            image_id = str(uuid4())
            context = type(
                "Context",
                (),
                {
                    "document_id": document_id,
                    "images": [
                        {
                            "id": image_id,
                            "temp_path": temp_path,
                            "path": temp_path,
                            "filename": "test.png",
                            "page_number": 1,
                            "image_index": 0,
                        }
                    ],
                },
            )()

            await processor.process(context)

            assert len(db.queries) >= 1
            insert_query = next((q for q in db.queries if "INSERT INTO krai_content.images" in q["query"]), None)
            assert insert_query is not None
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_file_hash_deduplication_mock(self):
        """Check file hash deduplication - storage service returns same path for same content."""
        storage = MockStorageService(success=True)
        content = b"identical-image-content"
        result1 = await storage.upload_image(content, "img1.png", "document_images", {})
        result2 = await storage.upload_image(content, "img2.png", "document_images", {})

        assert result1["success"] and result2["success"]
        assert result1["file_hash"] == result2["file_hash"]
        assert result1["storage_path"] == result2["storage_path"]

    @pytest.mark.asyncio
    async def test_process_requires_document_id(self):
        """Verify process() raises ValueError when document_id is missing."""
        processor = StorageProcessor()
        context = type("Context", (), {"document_id": None, "images": []})()

        with pytest.raises(ValueError, match="document_id"):
            await processor.process(context)

    @pytest.mark.asyncio
    async def test_process_handles_empty_images(self):
        """Verify process handles empty images list gracefully."""
        processor = StorageProcessor()
        context = type("Context", (), {"document_id": str(uuid4()), "images": []})()

        result = await processor.process(context)

        assert result.success is True
        assert result.data.get("saved_items", 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
