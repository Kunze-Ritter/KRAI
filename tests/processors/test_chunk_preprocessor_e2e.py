from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.chunk_preprocessor import ChunkPreprocessor

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio, pytest.mark.chunk_prep]


def _make_context(document_id: str) -> ProcessingContext:
    return ProcessingContext(
        document_id=document_id,
        file_path="/tmp/placeholder.pdf",
        document_type="service_manual",
        metadata={},
    )


class TestChunkPreprocessorE2E:
    async def test_process_chunks_success(
        self,
        mock_database_adapter,
        monkeypatch: pytest.MonkeyPatch,
        sample_chunks_for_preprocessing,
    ) -> None:
        document_id = sample_chunks_for_preprocessing[0]["document_id"]

        # Build a minimal supabase-like client that returns our chunks and records updates
        updated_chunks: dict[str, dict[str, Any]] = {}

        class DummyResult:
            def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
                self.data = data or []

        class ChunksTable:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage
                self._filter_doc: str | None = None
                self._update_id: str | None = None
                self._payload: dict[str, Any] | None = None

            def select(self, *_args: Any) -> "ChunksTable":
                return self

            def eq(self, column: str, value: Any) -> "ChunksTable":
                if column == "document_id":
                    self._filter_doc = value
                if column == "id":
                    self._update_id = value
                return self

            def order(self, _col: str) -> "ChunksTable":
                return self

            def update(self, payload: dict[str, Any]) -> "ChunksTable":
                self._payload = payload
                return self

            def execute(self) -> DummyResult:
                if self._payload is not None and self._update_id is not None:
                    if self._update_id in self._storage:
                        self._storage[self._update_id].update(self._payload)
                        updated_chunks[self._update_id] = dict(self._storage[self._update_id])
                    return DummyResult([])

                if self._filter_doc is None:
                    return DummyResult([])
                rows = [c for c in self._storage.values() if c.get("document_id") == self._filter_doc]
                rows = sorted(rows, key=lambda r: r.get("chunk_index", 0))
                return DummyResult(rows)

        class DummyClient:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage

            def table(self, name: str) -> ChunksTable:
                assert name == "chunks"
                return ChunksTable(self._storage)

        # Seed mock storage with sample chunks
        for chunk in sample_chunks_for_preprocessing:
            cid = chunk["id"]
            mock_database_adapter.chunks[cid] = dict(chunk)

        mock_database_adapter.client = DummyClient(mock_database_adapter.chunks)

        processor = ChunkPreprocessor(database_service=mock_database_adapter)
        ctx = _make_context(document_id)

        result = await processor.process(ctx)

        assert result.success is True
        assert result.data["chunks_preprocessed"] > 0
        assert result.data["total_chunks"] == len(sample_chunks_for_preprocessing)

        # Verify that metadata and char_count were updated via client.update
        assert updated_chunks, "Expected some chunks to be updated"
        for chunk_id, stored in updated_chunks.items():
            meta = stored.get("metadata", {})
            assert meta.get("preprocessed") is True
            assert meta.get("chunk_type") in {
                "error_code",
                "parts_list",
                "procedure",
                "specification",
                "table",
                "text",
                "empty",
            }
            assert stored.get("char_count") == len(stored.get("content", ""))

    async def test_process_no_chunks_found_returns_failure(
        self,
        mock_database_adapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Client without any chunks for the given document
        class DummyResult:
            def __init__(self) -> None:
                self.data: list[dict[str, Any]] = []

        class EmptyChunksTable:
            def select(self, *_args: Any) -> "EmptyChunksTable":
                return self

            def eq(self, *_args: Any, **_kwargs: Any) -> "EmptyChunksTable":
                return self

            def order(self, *_args: Any) -> "EmptyChunksTable":
                return self

            def execute(self) -> DummyResult:
                return DummyResult()

        class DummyClient:
            def table(self, _name: str) -> EmptyChunksTable:
                return EmptyChunksTable()

        mock_database_adapter.client = DummyClient()

        processor = ChunkPreprocessor(database_service=mock_database_adapter)
        ctx = _make_context(str(uuid4()))

        result = await processor.process(ctx)
        assert result.success is False
        assert result.data["chunks_preprocessed"] == 0

    async def test_process_handles_update_errors_gracefully(
        self,
        mock_database_adapter,
        monkeypatch: pytest.MonkeyPatch,
        sample_chunks_for_preprocessing,
    ) -> None:
        document_id = sample_chunks_for_preprocessing[0]["document_id"]

        class DummyResult:
            def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
                self.data = data or []

        class FailingTable:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage
                self._doc: str | None = None

            def select(self, *_args: Any) -> "FailingTable":
                return self

            def eq(self, column: str, value: Any) -> "FailingTable":
                if column == "document_id":
                    self._doc = value
                return self

            def order(self, _col: str) -> "FailingTable":
                return self

            def update(self, _payload: dict[str, Any]) -> "FailingTable":
                raise RuntimeError("Simulated DB error")

            def execute(self) -> DummyResult:
                if self._doc is None:
                    return DummyResult([])
                rows = [c for c in self._storage.values() if c.get("document_id") == self._doc]
                return DummyResult(rows)

        class DummyClient:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage

            def table(self, name: str) -> FailingTable:
                assert name == "chunks"
                return FailingTable(self._storage)

        for chunk in sample_chunks_for_preprocessing:
            mock_database_adapter.chunks[chunk["id"]] = dict(chunk)

        mock_database_adapter.client = DummyClient(mock_database_adapter.chunks)

        processor = ChunkPreprocessor(database_service=mock_database_adapter)
        ctx = _make_context(document_id)

        result = await processor.process(ctx)

        # Even with update failures the processor should complete and report
        assert result.success is True
        assert result.data["total_chunks"] == len(sample_chunks_for_preprocessing)
