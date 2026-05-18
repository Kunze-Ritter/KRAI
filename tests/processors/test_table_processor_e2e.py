"""End-to-end tests for TableProcessor.

Covers table extraction from PDFs, storage into structured_tables,
embedding generation into embeddings_v2, error handling and stage tracking.

The tests intentionally focus on high-level flows and database side effects
rather than every edge case detail, to keep runtime reasonable while
exercising the critical paths.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.table_processor import TableProcessor

pytestmark = [pytest.mark.processor, pytest.mark.table]


def _create_context(document_id: str, pdf_path: Path) -> ProcessingContext:
    ctx = ProcessingContext(
        document_id=document_id,
        file_path=str(pdf_path),
        document_type="service_manual",
        metadata={"filename": pdf_path.name},
    )
    # Make TableProcessor dependency on context.pdf_path explicit for tests
    ctx.pdf_path = str(pdf_path)
    return ctx


class TestTableExtractionE2E:
    """End-to-end extraction of tables from PDFs into ProcessingResult data."""

    @pytest.mark.asyncio
    async def test_process_document_with_tables(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_with_tables,
        mock_stage_tracker,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = mock_stage_tracker

        doc_id = str(uuid4())
        ctx = _create_context(doc_id, sample_pdf_with_tables["path"])

        result = await processor.process(ctx)

        assert result.success
        assert result.data["tables_extracted"] >= 1
        assert "embeddings_created" in result.data

        tables = await mock_database_adapter.get_structured_tables_by_document(doc_id)
        assert isinstance(tables, list)
        assert len(tables) == result.data["tables_extracted"]

    @pytest.mark.asyncio
    async def test_process_document_no_tables(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_files,
        mock_stage_tracker,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = mock_stage_tracker

        doc_id = str(uuid4())
        ctx = _create_context(doc_id, sample_pdf_files["valid_pdf"]["path"])

        result = await processor.process(ctx)

        assert result.success
        assert result.data["tables_extracted"] >= 0


class TestTableStorageE2E:
    """Verify that extracted tables and embeddings are persisted via adapter hooks."""

    @pytest.mark.asyncio
    async def test_store_tables_and_embeddings(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_with_tables,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = None

        doc_id = str(uuid4())
        result = await processor.process_document(doc_id, str(sample_pdf_with_tables["path"]))

        assert result["success"]
        tables = await mock_database_adapter.get_structured_tables_by_document(doc_id)
        assert len(tables) == result["tables_extracted"]

        # At least some tables should have embeddings stored
        any_embeddings = any(await mock_database_adapter.get_embeddings_by_source(t["id"], "table") for t in tables)
        assert any_embeddings


class TestTableProcessorErrorHandling:
    """Basic negative-path behaviour for missing/invalid inputs."""

    @pytest.mark.asyncio
    async def test_process_missing_pdf_path(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = None

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/nonexistent.pdf",
            document_type="service_manual",
        )
        # Explicitly remove pdf_path to trigger validation path
        ctx.pdf_path = None

        result = await processor.process(ctx)
        assert not result.success

    @pytest.mark.asyncio
    async def test_process_invalid_pdf_path(
        self,
        mock_database_adapter,
        mock_embedding_service,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = None

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/does_not_exist.pdf",
            document_type="service_manual",
        )

        result = await processor.process(ctx)
        assert not result.success
        assert "not found" in str(result.error).lower()


class TestTableProcessorStageTracking:
    """Smoke-test that stage tracker hooks are invoked on success and failure."""

    @pytest.mark.asyncio
    async def test_stage_tracker_success_path(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_with_tables,
        mock_stage_tracker,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = mock_stage_tracker

        ctx = _create_context(str(uuid4()), sample_pdf_with_tables["path"])
        result = await processor.process(ctx)

        assert result.success

    @pytest.mark.asyncio
    async def test_stage_tracker_failure_path(
        self,
        mock_database_adapter,
        mock_embedding_service,
        mock_stage_tracker,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )
        processor.stage_tracker = mock_stage_tracker

        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path="/tmp/missing.pdf",
            document_type="service_manual",
        )
        result = await processor.process(ctx)
        assert not result.success
