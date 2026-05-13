from pathlib import Path

import pytest

from backend.processors.text_extractor import TextExtractor

pytestmark = pytest.mark.processor


def _make_extractor_stub(max_structured_lines: int = 5, max_structured_line_len: int = 80) -> TextExtractor:
    """Create a lightweight TextExtractor instance without running __init__.

    We bypass heavy PDF library checks in __init__ by constructing the
    instance via object.__new__ and setting only the attributes required by
    the helper methods under test.
    """
    extractor = object.__new__(TextExtractor)  # type: ignore[call-arg]
    extractor.prefer_engine = "pymupdf"
    extractor.max_structured_lines = max_structured_lines
    extractor.max_structured_line_len = max_structured_line_len
    return extractor


class TestDocumentTypeClassificationUnit:
    """Unit tests for TextExtractor._classify_document_type."""

    def test_service_manual_detection_from_title(self) -> None:
        extractor = _make_extractor_stub()

        doc_type = extractor._classify_document_type(  # type: ignore[attr-defined]
            title="Konica Minolta C750i Service Manual",
            filename="konica_c750i_manual.pdf",
        )

        assert doc_type == "service_manual"

    def test_parts_catalog_detection_from_filename(self) -> None:
        extractor = _make_extractor_stub()

        doc_type = extractor._classify_document_type(  # type: ignore[attr-defined]
            title="",
            filename="canon_ir_advance_parts_catalog.pdf",
        )

        assert doc_type == "parts_catalog"

    def test_user_guide_detection_from_title_and_filename(self) -> None:
        extractor = _make_extractor_stub()

        doc_type = extractor._classify_document_type(  # type: ignore[attr-defined]
            title="User Guide",
            filename="hp_laserjet_user_guide.pdf",
        )

        assert doc_type == "user_guide"

    def test_troubleshooting_detection_from_keywords(self) -> None:
        extractor = _make_extractor_stub()

        doc_type = extractor._classify_document_type(  # type: ignore[attr-defined]
            title="Error Code Troubleshooting Reference",
            filename="error_reference.pdf",
        )

        assert doc_type == "troubleshooting"

    def test_default_document_type_when_no_keywords_match(self) -> None:
        extractor = _make_extractor_stub()

        doc_type = extractor._classify_document_type(  # type: ignore[attr-defined]
            title="Marketing Brochure",
            filename="printer_brochure.pdf",
        )

        # Fallback default is service_manual
        assert doc_type == "service_manual"


class TestTextCleaningUnit:
    """Unit tests for TextExtractor._clean_text."""

    def test_clean_text_normalizes_whitespace_and_newlines(self) -> None:
        extractor = _make_extractor_stub()

        raw = (
            "Line 1 with   extra   spaces\tand tabs\n"  # tabs and multiple spaces
            "\n\n\n"  # many blank lines
            "  Line 2 with leading and trailing spaces   \n"
            "\x00Null byte and  multiple\t\tspaces on line 3   "
        )

        cleaned = extractor._clean_text(raw)  # type: ignore[attr-defined]

        # Should not contain null bytes
        assert "\x00" not in cleaned

        # Multiple spaces/tabs collapsed
        assert "  " not in cleaned
        assert "\t" not in cleaned

        # Excessive blank lines reduced (no triple-newline sequences)
        assert "\n\n\n" not in cleaned

        # Lines should be stripped at start/end
        for line in cleaned.split("\n"):
            assert line == line.strip()


class TestStructuredTextExtractionUnit:
    """Unit tests for TextExtractor._extract_structured_text_from_raw."""

    def test_extract_structured_text_returns_none_for_empty_raw(self) -> None:
        extractor = _make_extractor_stub()

        result = extractor._extract_structured_text_from_raw({})  # type: ignore[attr-defined]

        assert result is None

    def test_extract_structured_text_detects_error_code_like_lines(self) -> None:
        extractor = _make_extractor_stub(max_structured_lines=10, max_structured_line_len=200)

        raw = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {"text": "01.23A.45 Fuser Unit Error ................"},
                            ]
                        },
                        {
                            "spans": [
                                {"text": "Some unrelated text that should be ignored"},
                            ]
                        },
                    ],
                },
                {
                    "type": 1,  # non-text block, should be ignored
                    "lines": [
                        {"spans": [{"text": "99.99Z.99 Should not be read from here"}]},
                    ],
                },
            ]
        }

        structured = extractor._extract_structured_text_from_raw(raw)  # type: ignore[attr-defined]

        assert structured is not None
        # Should include normalized version of the structured line
        assert "01.23A.45" in structured
        assert "Fuser Unit Error" in structured

    def test_extract_structured_text_respects_line_cap(self) -> None:
        # Configure a very small cap to ensure truncation happens
        extractor = _make_extractor_stub(max_structured_lines=1, max_structured_line_len=200)

        raw = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {"spans": [{"text": "01.23A.45 First error"}]},
                        {"spans": [{"text": "02.34B.56 Second error"}]},
                    ],
                }
            ]
        }

        structured = extractor._extract_structured_text_from_raw(raw)  # type: ignore[attr-defined]

        assert structured is not None
        # Only one line should be present due to the cap
        lines = structured.split("\n")
        assert len(lines) == 1
        assert "01.23A.45" in lines[0]

    def test_extract_structured_text_trims_long_lines(self) -> None:
        max_len = 40
        extractor = _make_extractor_stub(max_structured_lines=5, max_structured_line_len=max_len)

        long_text = "01.23A.45 " + "A" * 200
        raw = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {"spans": [{"text": long_text}]},
                    ],
                }
            ]
        }

        structured = extractor._extract_structured_text_from_raw(raw)  # type: ignore[attr-defined]

        assert structured is not None
        # Line should be trimmed to max_len plus ellipsis
        assert structured.endswith("…")
        assert len(structured) == max_len + 1


class TestExtractTextAPI:
    """API-level tests for TextExtractor.extract_text using mocked engines."""

    @pytest.mark.asyncio
    async def test_extract_text_uses_pymupdf_engine_by_default(self, tmp_path: Path, monkeypatch) -> None:
        """extract_text should use PyMuPDF when prefer_engine='pymupdf'."""
        pdf_path = tmp_path / "test_pymupdf.pdf"
        pdf_path.write_bytes(b"dummy")

        from uuid import uuid4

        # Ensure both engines appear available
        monkeypatch.setattr("backend.processors.text_extractor.PYMUPDF_AVAILABLE", True, raising=False)
        monkeypatch.setattr("backend.processors.text_extractor.PDFPLUMBER_AVAILABLE", True, raising=False)

        # Mock fitz.open to return a simple document with pages
        class DummyPage:
            def get_text(self, mode: str) -> str:
                if mode == "text":
                    return "Dummy page text"
                if mode == "rawdict":
                    return {"blocks": []}
                return ""

        class DummyDoc:
            def __init__(self) -> None:
                self.metadata = {"title": "Konica Minolta Service Manual", "author": "Test"}

            def __len__(self) -> int:  # page_count
                return 2

            def __getitem__(self, index: int) -> DummyPage:
                return DummyPage()

            def close(self) -> None:
                pass

        dummy_doc = DummyDoc()

        def fake_open(path: Path):  # type: ignore[override]
            return dummy_doc

        monkeypatch.setattr(
            "backend.processors.text_extractor.fitz", type("_M", (), {"open": staticmethod(fake_open)}), raising=False
        )

        extractor = TextExtractor(prefer_engine="pymupdf", enable_ocr_fallback=False)
        page_texts, metadata, structured = extractor.extract_text(pdf_path, uuid4())

        # Assert
        assert page_texts
        assert set(page_texts.keys()) == {1, 2}
        assert metadata.engine_used == "pymupdf"
        assert metadata.document_type == "service_manual"
        assert metadata.page_count == 2
        assert metadata.file_size_bytes > 0

    @pytest.mark.asyncio
    async def test_extract_text_uses_pdfplumber_engine_when_requested(self, tmp_path: Path, monkeypatch) -> None:
        """extract_text should use pdfplumber when prefer_engine='pdfplumber'."""
        pdf_path = tmp_path / "test_pdfplumber.pdf"
        pdf_path.write_bytes(b"dummy")

        from uuid import uuid4

        monkeypatch.setattr("backend.processors.text_extractor.PYMUPDF_AVAILABLE", True, raising=False)
        monkeypatch.setattr("backend.processors.text_extractor.PDFPLUMBER_AVAILABLE", True, raising=False)

        class DummyPage:
            def extract_text(self) -> str:
                return "Dummy pdfplumber text"

        class DummyPdf:
            def __init__(self) -> None:
                self.metadata = {"Title": "Parts Catalog", "Author": "Test"}
                self.pages = [DummyPage()]

            def __enter__(self) -> "DummyPdf":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                pass

        def fake_open(path: Path):  # type: ignore[override]
            return DummyPdf()

        monkeypatch.setattr(
            "backend.processors.text_extractor.pdfplumber",
            type("_M", (), {"open": staticmethod(fake_open)}),
            raising=False,
        )

        extractor = TextExtractor(prefer_engine="pdfplumber", enable_ocr_fallback=False)
        page_texts, metadata, structured = extractor.extract_text(pdf_path, uuid4())

        assert page_texts
        assert set(page_texts.keys()) == {1}
        assert metadata.engine_used == "pdfplumber"
        assert metadata.document_type == "parts_catalog"
        assert metadata.page_count == 1

    @pytest.mark.asyncio
    async def test_extract_text_falls_back_to_pdfplumber_when_pymupdf_fails(self, tmp_path: Path, monkeypatch) -> None:
        """When PyMuPDF extraction fails, TextExtractor should fall back to pdfplumber if available."""
        pdf_path = tmp_path / "test_fallback.pdf"
        pdf_path.write_bytes(b"dummy")

        from uuid import uuid4

        monkeypatch.setattr("backend.processors.text_extractor.PYMUPDF_AVAILABLE", True, raising=False)
        monkeypatch.setattr("backend.processors.text_extractor.PDFPLUMBER_AVAILABLE", True, raising=False)

        # PyMuPDF path raises an error
        class DummyFitz:
            def open(self, path: Path):  # type: ignore[override]
                raise RuntimeError("Simulated PyMuPDF failure")

        monkeypatch.setattr("backend.processors.text_extractor.fitz", DummyFitz(), raising=False)

        # pdfplumber fallback
        class DummyPage:
            def extract_text(self) -> str:
                return "Fallback pdfplumber text"

        class DummyPdf:
            def __init__(self) -> None:
                self.metadata = {"Title": "Fallback Manual", "Author": "Test"}
                self.pages = [DummyPage()]

            def __enter__(self) -> "DummyPdf":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                pass

        def fake_open(path: Path):  # type: ignore[override]
            return DummyPdf()

        monkeypatch.setattr(
            "backend.processors.text_extractor.pdfplumber",
            type("_M", (), {"open": staticmethod(fake_open)}),
            raising=False,
        )

        extractor = TextExtractor(prefer_engine="pymupdf", enable_ocr_fallback=False)
        page_texts, metadata, structured = extractor.extract_text(pdf_path, uuid4())

        assert page_texts
        assert metadata.engine_used == "pdfplumber"
        assert metadata.fallback_used == "pdfplumber"

    def test_extract_text_raises_file_not_found_for_missing_path(self) -> None:
        extractor = _make_extractor_stub()

        from uuid import uuid4

        missing = Path("/nonexistent/path/does_not_exist.pdf")

        with pytest.raises(FileNotFoundError):
            # Call the real method on a stubbed instance; it checks path.exists first
            extractor.extract_text(missing, uuid4())  # type: ignore[attr-defined]
