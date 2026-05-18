from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.classification_processor import ClassificationProcessor

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio, pytest.mark.classification]


def _make_context(document_id: str, pdf_path: Path) -> ProcessingContext:
    return ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={},
    )


class TestManufacturerDetection:
    async def test_detect_manufacturer_from_filename(self, tmp_path: Path, mock_database_adapter) -> None:
        pdf_path = tmp_path / "HP_LaserJet_M4555_Service_Manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = _make_context(str(uuid4()), pdf_path)

        # We call the internal helper directly to avoid DB coupling
        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)  # type: ignore[attr-defined]

        assert manufacturer is not None
        assert "hp" in manufacturer.lower()

    async def test_detect_manufacturer_from_title(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "generic_manual.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(database_service=None, ai_service=None, features_service=None)
        ctx = _make_context(str(uuid4()), pdf_path)

        meta: dict[str, Any] = {"title": "Canon imageRUNNER ADVANCE C5560 User Guide", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)  # type: ignore[attr-defined]

        assert manufacturer is not None
        assert "canon" in manufacturer.lower()

    async def test_detect_manufacturer_from_ai(self, tmp_path: Path, mock_ai_service) -> None:
        pdf_path = tmp_path / "unknown_manual.pdf"
        pdf_path.write_text("bizhub C4080 Konica Minolta service information")

        class DummyClient:
            def __init__(self, text: str) -> None:
                self._text = text

            class _Result:
                def __init__(self, data: list[dict[str, Any]]) -> None:
                    self.data = data

            class _Table:
                def __init__(self, text: str) -> None:
                    self._text = text

                def select(self, *_a: Any) -> "TestManufacturerDetection.DummyClient._Table":  # type: ignore[name-defined]
                    return self

                def eq(self, *_a: Any, **_kw: Any) -> "TestManufacturerDetection.DummyClient._Table":  # type: ignore[name-defined]
                    return self

                def order(self, *_a: Any) -> "TestManufacturerDetection.DummyClient._Table":  # type: ignore[name-defined]
                    return self

                def limit(self, _n: int) -> "TestManufacturerDetection.DummyClient._Table":  # type: ignore[name-defined]
                    return self

                def execute(self) -> "DummyClient._Result":
                    return DummyClient._Result([{"content": "Konica Minolta bizhub C4080"}])

            def table(self, _name: str) -> "DummyClient._Table":
                return DummyClient._Table(self._text)

        class DummyDB:
            def __init__(self, text: str) -> None:
                self.client = DummyClient(text)

        document_id = str(uuid4())
        processor = ClassificationProcessor(
            database_service=DummyDB("Konica Minolta"), ai_service=mock_ai_service, features_service=object()
        )
        ctx = _make_context(document_id, pdf_path)

        meta: dict[str, Any] = {"title": "", "filename": pdf_path.name}
        manufacturer = await processor._detect_manufacturer(pdf_path, meta, ctx, processor.logger)  # type: ignore[attr-defined]

        assert manufacturer is not None
        assert "konica" in manufacturer.lower()


class TestDocumentTypeAndVersion:
    async def test_detect_document_type_and_version_from_metadata(
        self,
        tmp_path: Path,
        mock_database_adapter,
    ) -> None:
        pdf_path = tmp_path / "Canon_iR_ADV_C5560_Parts_Guide.pdf"
        pdf_path.write_text("Dummy content")

        # Stub DB client for content statistics
        class DummyResult:
            def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
                self.data = data or []

        class DummyTable:
            def __init__(self, count: int) -> None:
                self._count = count

            def select(self, *_args: Any) -> "DummyTable":
                return self

            def eq(self, *_args: Any, **_kwargs: Any) -> "DummyTable":
                return self

            def execute(self) -> DummyResult:
                return DummyResult([{"id": i} for i in range(self._count)])

        class DummyClient:
            def table(self, name: str) -> DummyTable:
                if name == "error_codes":
                    return DummyTable(0)
                if name == "parts_catalog":
                    return DummyTable(10)
                return DummyTable(0)

        mock_database_adapter.client = DummyClient()

        processor = ClassificationProcessor(
            database_service=mock_database_adapter, ai_service=None, features_service=None
        )
        ctx = _make_context(str(uuid4()), pdf_path)

        doc_meta = {
            "title": "Canon imageRUNNER ADVANCE C5560 Parts Catalog",
            "filename": pdf_path.name,
            "created_at": "D:20240808064126Z",
        }

        doc_type, version = await processor._detect_document_type(  # type: ignore[attr-defined]
            pdf_path,
            doc_meta,
            manufacturer="Canon",
            context=ctx,
            adapter=processor.logger,
        )

        assert doc_type in {"parts_catalog", "service_manual"}
        assert version is None or isinstance(version, str)

    async def test_detect_cpmd_document_type_from_hp_metadata(
        self,
        tmp_path: Path,
        mock_database_adapter,
    ) -> None:
        pdf_path = tmp_path / "HP_E877_CPMD.pdf"
        pdf_path.write_text("Dummy content")

        processor = ClassificationProcessor(
            database_service=mock_database_adapter, ai_service=None, features_service=None
        )
        ctx = _make_context(str(uuid4()), pdf_path)

        doc_meta = {
            "title": "Control Panel Messages Document (CPMD)",
            "filename": pdf_path.name,
            "created_at": "D:20240808064126Z",
        }

        doc_type, version = await processor._detect_document_type(  # type: ignore[attr-defined]
            pdf_path,
            doc_meta,
            manufacturer="HP",
            context=ctx,
            adapter=processor.logger,
        )

        assert doc_type == "cpmd_database"
        assert version is None or isinstance(version, str)


class TestClassificationProcessorEndToEnd:
    async def test_process_updates_document_when_db_available(
        self,
        tmp_path: Path,
        mock_database_adapter,
    ) -> None:
        pdf_path = tmp_path / "HP_LaserJet_M404n_User_Guide.pdf"
        pdf_path.write_text("HP LaserJet Pro M404n User Guide content")

        # Provide a simple DB client that supports reading metadata and updating classification
        doc_id = str(uuid4())
        mock_database_adapter.documents[doc_id] = {
            "id": doc_id,
            "filename": pdf_path.name,
            "title": "HP LaserJet Pro M404n User Guide",
            "file_hash": "hash",
            "created_at": "D:20240101000000Z",
        }

        class DummyClient:
            def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                self._storage = storage

            class _Result:
                def __init__(self, data: list[dict[str, Any]]) -> None:
                    self.data = data

            class _Table:
                def __init__(self, storage: dict[str, dict[str, Any]]) -> None:
                    self._storage = storage
                    self._id: str | None = None
                    self._payload: dict[str, Any] | None = None

                def select(self, *_args: Any) -> "ClassificationProcessorEndToEnd.DummyClient._Table":  # type: ignore[name-defined]
                    return self

                def eq(self, _col: str, value: Any) -> "ClassificationProcessorEndToEnd.DummyClient._Table":  # type: ignore[name-defined]
                    self._id = value
                    return self

                def execute(self) -> "ClassificationProcessorEndToEnd.DummyClient._Result":  # type: ignore[name-defined]
                    if self._payload is not None and self._id is not None:
                        if self._id in self._storage:
                            self._storage[self._id].update(self._payload)
                        return ClassificationProcessorEndToEnd.DummyClient._Result([])  # type: ignore[name-defined]
                    if self._id is None or self._id not in self._storage:
                        return ClassificationProcessorEndToEnd.DummyClient._Result([])  # type: ignore[name-defined]
                    return ClassificationProcessorEndToEnd.DummyClient._Result([self._storage[self._id]])  # type: ignore[name-defined]

                def update(self, payload: dict[str, Any]) -> "ClassificationProcessorEndToEnd.DummyClient._Table":  # type: ignore[name-defined]
                    self._payload = payload
                    return self

            def table(self, name: str) -> "ClassificationProcessorEndToEnd.DummyClient._Table":  # type: ignore[name-defined]
                assert name == "documents"
                return ClassificationProcessorEndToEnd.DummyClient._Table(self._storage)  # type: ignore[name-defined]

        mock_database_adapter.client = DummyClient(mock_database_adapter.documents)

        processor = ClassificationProcessor(
            database_service=mock_database_adapter, ai_service=None, features_service=None
        )
        ctx = _make_context(doc_id, pdf_path)

        result = await processor.process(ctx)

        assert result.success is True
        data = result.data
        assert "manufacturer" in data
        assert "document_type" in data

        updated = mock_database_adapter.documents[doc_id]
        assert updated.get("manufacturer") is not None
        assert updated.get("document_type") is not None
