"""Unit tests for TableProcessor internals.

Covers table detection, data extraction, type detection, context extraction,
and embedding generation using the structured-data fixtures and mock services.
"""

from typing import Any

import pandas as pd
import pytest

try:  # Optional – some tests are skipped if PyMuPDF is unavailable
    import fitz
except ImportError:  # pragma: no cover - environment dependent
    fitz = None

from backend.processors.table_processor import TableProcessor

pytestmark = [pytest.mark.processor, pytest.mark.table]


class DummyBBox:
    """Simple bounding-box helper used for context/caption tests."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.width = x1 - x0
        self.height = y1 - y0


class DummyTab:
    """Minimal table object compatible with TableProcessor._extract_table_data."""

    def __init__(self, data: list[list[Any]], bbox: DummyBBox | None = None) -> None:
        self._data = data
        self.bbox = bbox or DummyBBox(0, 100, 400, 300)

    def extract(self) -> list[list[Any]]:
        return self._data


class DummyPage:
    """Minimal page stub providing text for context and caption extraction."""

    def __init__(self, header: str = "", above: str = "", below: str = "") -> None:
        self._header = header
        self._above = above
        self._below = below
        self.rect = DummyBBox(0, 0, 600, 800)

    def get_text(self, clip=None) -> str:  # type: ignore[override]
        if clip is None:
            return f"{self._header}\n{self._above}\n{self._below}"
        # Heuristic based on y coordinates used in TableProcessor
        y0, y1 = clip.y0, clip.y1  # type: ignore[attr-defined]
        if y1 <= 80:  # header region
            return self._header
        if y1 <= 300:  # above table
            return self._above
        if y0 >= 300:  # below table
            return self._below
        return ""


class TestTableDetection:
    """Detection and basic validation of tables on a page."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(fitz is None, reason="PyMuPDF not installed")
    async def test_extract_page_tables_with_lines_strategy(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_with_tables,
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
            strategy="lines",
            fallback_strategy="text",
        )
        processor.stage_tracker = None

        doc = fitz.open(sample_pdf_with_tables["path"])  # type: ignore[arg-type]
        page = doc[0]

        tables = processor._extract_page_tables(page, page_number=1)

        doc.close()

        assert isinstance(tables, list)
        assert len(tables) >= 1
        for table in tables:
            assert "table_markdown" in table
            assert "row_count" in table
            assert table["row_count"] >= processor.min_rows

    @pytest.mark.asyncio
    @pytest.mark.skipif(fitz is None, reason="PyMuPDF not installed")
    async def test_extract_page_tables_respects_min_rows_and_cols(
        self,
        mock_database_adapter,
        mock_embedding_service,
        sample_pdf_with_tables,
    ) -> None:
        # Use very high thresholds to force rejection
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
            strategy="lines",
            fallback_strategy="text",
            min_rows=100,
            min_cols=10,
        )
        processor.stage_tracker = None

        doc = fitz.open(sample_pdf_with_tables["path"])  # type: ignore[arg-type]
        page = doc[0]

        tables = processor._extract_page_tables(page, page_number=1)
        doc.close()

        assert tables == []

    def test_extract_table_data_validation_min_rows_and_cols(
        self, mock_database_adapter, mock_embedding_service
    ) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
            min_rows=2,
            min_cols=2,
        )

        # Too few rows (only header + 0 data rows)
        data_too_few_rows = [["A", "B"]]
        tab1 = DummyTab(data_too_few_rows)
        page = DummyPage()
        result1 = processor._extract_table_data(tab1, page, page_number=1, table_index=0)
        assert result1 is None

        # Too few columns
        data_too_few_cols = [["A"], ["1"], ["2"]]
        tab2 = DummyTab(data_too_few_cols)
        result2 = processor._extract_table_data(tab2, page, page_number=1, table_index=0)
        assert result2 is None


class TestTableDataExtraction:
    """Extraction of table content, markdown, and basic metadata."""

    def test_extract_table_data_with_headers_and_markdown(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
            min_rows=2,
            min_cols=2,
        )

        raw = [
            ["ColA", "ColB"],
            ["v1", "x1"],
            ["v2", "x2"],
        ]
        tab = DummyTab(raw)
        page = DummyPage(above="Table 1: Specifications", below="End of table")

        table = processor._extract_table_data(tab, page, page_number=2, table_index=1)
        assert table is not None
        assert table["column_headers"] == ["ColA", "ColB"]
        assert table["row_count"] == 2
        assert table["column_count"] == 2
        assert "| ColA" in table["table_markdown"]

    def test_extract_table_data_bbox_and_metadata(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(
            database_service=mock_database_adapter,
            embedding_service=mock_embedding_service,
        )

        raw = [["H1", "H2"], ["a", "b"], ["c", "d"]]
        bbox = DummyBBox(10, 100, 210, 260)
        tab = DummyTab(raw, bbox=bbox)
        page = DummyPage(above="Header text", below="Footer text")

        table = processor._extract_table_data(tab, page, page_number=1, table_index=0)
        assert table is not None
        assert json_loads(table["bbox"])[0] == pytest.approx(10.0)
        metadata = json_loads(table["metadata"])
        assert metadata["total_rows"] == 3
        assert metadata["total_columns"] == 2


class TestTableTypeDetection:
    """Classification of tables into semantic types based on headers."""

    def test_detect_table_type_specification(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        df = pd.DataFrame([["75 ppm"], ["1200x1200"]], columns=["Specification"])
        assert processor._detect_table_type(df) == "specification"

    def test_detect_table_type_parts_list(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        df = pd.DataFrame([["P001", "A001"]], columns=["Part", "Number"])
        assert processor._detect_table_type(df) == "parts_list"

    def test_detect_table_type_error_codes(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        df = pd.DataFrame([["900.01", "Fuser Error"]], columns=["Error", "Code"])
        assert processor._detect_table_type(df) == "error_codes"

    @pytest.mark.parametrize(
        "columns,expected",
        [
            (["Model", "Speed"], "comparison"),
            (["Compatible", "Model"], "compatibility"),
            (["Foo", "Bar"], "other"),
        ],
    )
    def test_detect_table_type_parametrized(
        self,
        columns: list[str],
        expected: str,
        mock_database_adapter,
        mock_embedding_service,
    ) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        df = pd.DataFrame([["x"] * len(columns)], columns=columns)
        assert processor._detect_table_type(df) == expected


class TestTableContextExtraction:
    """Extraction of structured context JSON around tables."""

    def test_extract_table_context_above_below_and_header(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        bbox = (50.0, 200.0, 300.0, 350.0)
        page = DummyPage(
            header="Service Manual - Error Codes",
            above="Error codes: 900.01, 900.02",
            below="Model C4080 on page 5",
        )

        context_json = processor._extract_table_context(page, bbox)
        ctx = json_loads(context_json)
        assert "900.01" in ctx["text"]
        assert any(code.startswith("90") for code in ctx["error_codes"])
        assert ctx["page_header"].startswith("Service Manual")

    def test_extract_caption_patterns(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        bbox = (50.0, 200.0, 300.0, 350.0)
        page = DummyPage(
            header="",
            above="Table 2: Parts List for Model C4080",
            below="",
        )

        caption = processor._extract_caption(page, bbox)
        assert caption is not None
        assert "Parts List" in caption


class TestTableEmbeddingGeneration:
    """Generation of embeddings for table markdown via mock embedding service."""

    def test_generate_table_embedding_success(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        emb = processor._generate_table_embedding(md)
        assert isinstance(emb, list)
        assert len(emb) == 768
        assert any(v != 0.0 for v in emb)

    def test_generate_table_embedding_empty_table(self, mock_database_adapter, mock_embedding_service) -> None:
        processor = TableProcessor(mock_database_adapter, mock_embedding_service)
        emb = processor._generate_table_embedding("")
        # For empty input, mock still returns vector but _generate_table_embedding should handle errors gracefully
        assert isinstance(emb, list)

    def test_generate_table_embedding_service_failure(self, mock_database_adapter) -> None:
        class FailingEmbeddingService:
            def _generate_embedding(self, text: str) -> list[float]:  # pragma: no cover - simple failure path
                raise RuntimeError("embedding failed")

        processor = TableProcessor(mock_database_adapter, FailingEmbeddingService())
        emb = processor._generate_table_embedding("| A | B |")
        assert emb == []


def json_loads(value: str | None) -> Any:
    """Small helper to safely load JSON from strings used in table metadata/bbox."""
    import json

    if not value:
        return {}
    return json.loads(value)
