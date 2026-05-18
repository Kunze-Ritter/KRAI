import pytest

from backend.processors.chunk_preprocessor import ChunkPreprocessor

pytestmark = [pytest.mark.unit, pytest.mark.chunk_prep]


def _make_preprocessor() -> ChunkPreprocessor:
    return ChunkPreprocessor(database_service=None)


class TestChunkCleaning:
    def test_clean_chunk_remove_headers_and_footers(self) -> None:
        pre = _make_preprocessor()
        content = (
            "Page 1 of 10\n"
            "Konica Minolta C4080 Service Manual\n"
            "Chapter 1\n"
            "Safety information\n"
            "Copyright 2025 Konica Minolta"
        )

        cleaned = pre._clean_chunk(content)  # type: ignore[attr-defined]
        lines: list[str] = cleaned.split("\n")

        assert all("Page 1 of 10" not in line for line in lines)
        assert all("Copyright" not in line for line in lines)
        assert any("Safety information" in line for line in lines)

    def test_clean_chunk_normalize_whitespace_and_remove_empty(self) -> None:
        pre = _make_preprocessor()
        content = """   Line 1   with   extra    spaces\n\n\nLine 2\twith\ttabs    too   \n   \n"""

        cleaned = pre._clean_chunk(content)  # type: ignore[attr-defined]
        lines = cleaned.split("\n")

        # No empty lines
        assert all(line.strip() for line in lines)
        # No multiple spaces or tabs
        for line in lines:
            assert "\t" not in line
            assert "  " not in line

    def test_clean_chunk_empty_input(self) -> None:
        pre = _make_preprocessor()
        assert pre._clean_chunk("") == ""  # type: ignore[attr-defined]
        assert pre._clean_chunk(None) is None  # type: ignore[arg-type,attr-defined]


class TestChunkTypeDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "C-4080 Error: Paper jam",
            "E123-45 Fuser failure",
            "A12 3456 Error description",
        ],
    )
    def test_detect_chunk_type_error_code(self, text: str) -> None:
        pre = _make_preprocessor()
        chunk_type = pre._detect_chunk_type(text)  # type: ignore[attr-defined]
        assert chunk_type == "error_code"

    @pytest.mark.parametrize(
        "text",
        [
            "Part ABC-1234: Fuser Unit",
            "ITEM DEF 5678 component",
        ],
    )
    def test_detect_chunk_type_parts_list(self, text: str) -> None:
        pre = _make_preprocessor()
        chunk_type = pre._detect_chunk_type(text)  # type: ignore[attr-defined]
        assert chunk_type in {"parts_list", "text"}

    def test_detect_chunk_type_procedure(self) -> None:
        pre = _make_preprocessor()
        text = "1. Remove cover\n2. Replace cartridge\n3. Close cover"
        assert pre._detect_chunk_type(text) == "procedure"  # type: ignore[attr-defined]

    def test_detect_chunk_type_specification(self) -> None:
        pre = _make_preprocessor()
        text = "Resolution: 1200 dpi, Speed: 80 ppm, Weight: 50 kg"
        assert pre._detect_chunk_type(text) == "specification"  # type: ignore[attr-defined]

    def test_detect_chunk_type_table(self) -> None:
        pre = _make_preprocessor()
        text = "Code    Description    Value\n900.01  Fuser Error    Critical\n900.02  Lamp Error     Warning"
        assert pre._detect_chunk_type(text) == "table"  # type: ignore[attr-defined]

    def test_detect_chunk_type_text_default(self) -> None:
        pre = _make_preprocessor()
        text = "This is a general descriptive chunk of text."
        assert pre._detect_chunk_type(text) == "text"  # type: ignore[attr-defined]

    def test_detect_chunk_type_empty(self) -> None:
        pre = _make_preprocessor()
        assert pre._detect_chunk_type("") == "empty"  # type: ignore[attr-defined]
