"""
Tests for structured text cap and line length limits.

Tests memory protection features:
- Maximum lines per page cap
- Maximum line length trimming
"""

from typing import Any

import pytest

from backend.processors.text_extractor import DEFAULT_MAX_STRUCTURED_LINES, STRUCTURED_LINE_MAX_LENGTH, TextExtractor


def _generate_rawdict(entries: list[str]) -> dict[str, Any]:
    """Create a minimal PyMuPDF-like rawdict structure for testing."""
    return {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {
                                "text": entry,
                            }
                        ]
                    }
                    for entry in entries
                ],
            }
        ]
    }


class TestStructuredTextCap:
    """Test structured text extraction caps"""

    def test_default_caps(self):
        """Test default cap values"""
        extractor = TextExtractor()
        assert extractor.max_structured_lines == DEFAULT_MAX_STRUCTURED_LINES
        assert extractor.max_structured_line_len == STRUCTURED_LINE_MAX_LENGTH

    def test_custom_caps(self):
        """Test custom cap values"""
        extractor = TextExtractor(max_structured_lines=100, max_structured_line_len=200)
        assert extractor.max_structured_lines == 100
        assert extractor.max_structured_line_len == 200

    def test_line_count_cap(self):
        """Structured lines should be capped at configured maximum."""
        cap = 10
        extractor = TextExtractor(max_structured_lines=cap, max_structured_line_len=60)

        entries = [f"{i:02d}.AB1.CD Item {i}" for i in range(30)]
        rawdict = _generate_rawdict(entries)

        result = extractor._extract_structured_text_from_raw(rawdict)
        assert result is not None

        lines = result.split("\n")
        assert len(lines) == cap
        # Ensure the first 'cap' entries are present and unique
        assert lines[0] == "00.AB1.CD Item 0"
        assert lines[-1] == f"{cap - 1:02d}.AB1.CD Item {cap - 1}"
        assert len(set(lines)) == cap

    def test_line_length_trim(self):
        """Long structured lines should be trimmed with ellipsis."""
        max_len = 25
        extractor = TextExtractor(max_structured_lines=5, max_structured_line_len=max_len)

        long_text = "42.ABC.12 " + "X" * 100
        rawdict = _generate_rawdict([long_text])

        result = extractor._extract_structured_text_from_raw(rawdict)
        assert result is not None

        lines = result.split("\n")
        assert len(lines) == 1
        trimmed_line = lines[0]
        assert trimmed_line.endswith("…")
        assert len(trimmed_line) == max_len + 1  # include ellipsis

    def test_memory_protection(self):
        """Large structured tables should respect caps and deduplicate entries."""
        extractor = TextExtractor(
            max_structured_lines=DEFAULT_MAX_STRUCTURED_LINES,
            max_structured_line_len=STRUCTURED_LINE_MAX_LENGTH,
        )

        # Create many lines with alternating duplicates to ensure deduping works
        entries = [
            f"{i % 50:02d}.AA1.BB Detail {i}" if i % 2 == 0 else f"{i % 50:02d}.AA1.BB Detail {i % 50}"
            for i in range(600)
        ]
        rawdict = _generate_rawdict(entries)

        result = extractor._extract_structured_text_from_raw(rawdict)
        assert result is not None

        lines = result.split("\n")
        # Should not exceed configured cap
        assert len(lines) <= DEFAULT_MAX_STRUCTURED_LINES
        # Ensure duplicates are filtered out (since seen set prevents repeats)
        assert len(lines) == len(set(lines))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
