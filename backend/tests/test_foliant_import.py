"""
Unit tests for Foliant PDF import script.

Tests PDF data extraction and database import functionality.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_database_adapter() -> Mock:
    """Provide mock database adapter."""
    adapter = Mock()
    adapter.execute = Mock(return_value=None)
    adapter.query_one = Mock(return_value=None)
    return adapter


def test_extract_foliant_data_structure() -> None:
    """Test that extract_foliant_data returns correct structure."""
    from scripts.import_foliant_to_db import extract_foliant_data

    # Mock pdfplumber
    with patch("scripts.import_foliant_to_db.pdfplumber.open") as mock_open:
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Sample PDF text with product info"
        mock_pdf.pages = [mock_page]
        mock_open.return_value.__enter__.return_value = mock_pdf

        # Test with mock PDF
        result = extract_foliant_data("test.pdf")

        # Verify structure
        assert isinstance(result, dict)
        assert "articles" in result
        assert "compatibility_matrix" in result
        assert "filename" in result
        assert result["filename"] == "test.pdf"
        assert isinstance(result["articles"], list)
        assert isinstance(result["compatibility_matrix"], list)


def test_extract_foliant_data_multipage() -> None:
    """Test extraction from multi-page PDF."""
    from scripts.import_foliant_to_db import extract_foliant_data

    with patch("scripts.import_foliant_to_db.pdfplumber.open") as mock_open:
        mock_pdf = Mock()
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Page 2 content"
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_open.return_value.__enter__.return_value = mock_pdf

        result = extract_foliant_data("multipage.pdf")

        assert result["filename"] == "multipage.pdf"
        # Verify that all pages were processed
        assert mock_page1.extract_text.called
        assert mock_page2.extract_text.called


def test_extract_handles_pdf_error() -> None:
    """Test that extraction handles PDF errors gracefully."""
    from scripts.import_foliant_to_db import extract_foliant_data

    with patch("scripts.import_foliant_to_db.pdfplumber.open") as mock_open:
        mock_open.side_effect = Exception("PDF corruption error")

        with pytest.raises(Exception):
            extract_foliant_data("corrupted.pdf")


def test_import_to_database_with_articles(mock_database_adapter: Mock) -> None:
    """Test importing articles to database."""
    from scripts.import_foliant_to_db import import_to_database

    data = {
        "articles": [
            {
                "model_number": "C257i",
                "product_type": "multifunction",
                "specification": "Test product",
            },
            {
                "model_number": "FS-539",
                "product_type": "accessory",
                "specification": "Test accessory",
            },
        ],
        "compatibility_matrix": [],
        "filename": "test.pdf",
    }

    with patch("backend.services.database_factory.create_database_adapter", return_value=mock_database_adapter):
        result = import_to_database(data)

        # Verify that database adapter was called
        assert mock_database_adapter.execute.called or result is True


def test_import_empty_data() -> None:
    """Test importing empty data."""
    from scripts.import_foliant_to_db import import_to_database

    data = {
        "articles": [],
        "compatibility_matrix": [],
        "filename": "empty.pdf",
    }

    with patch("backend.services.database_factory.create_database_adapter") as mock_factory:
        mock_factory.return_value = Mock()
        result = import_to_database(data)

        # Should handle empty data gracefully
        assert isinstance(result, bool)


def test_process_foliant_directory_creates_processed_folder(tmp_path: Path) -> None:
    """Test that process_foliant_directory creates processed folder."""
    from scripts.import_foliant_to_db import process_foliant_directory

    # Create test directory structure
    input_dir = tmp_path / "input_foliant"
    input_dir.mkdir()
    processed_dir = input_dir / "processed"

    with (
        patch("scripts.import_foliant_to_db.extract_foliant_data") as mock_extract,
        patch("scripts.import_foliant_to_db.import_to_database") as mock_import,
    ):
        mock_extract.return_value = {
            "articles": [],
            "compatibility_matrix": [],
            "filename": "test.pdf",
        }
        mock_import.return_value = False

        # Process empty directory
        stats = process_foliant_directory(str(input_dir))

        # Verify processed folder was created
        assert processed_dir.exists()
        assert stats["processed"] == 0


def test_process_foliant_directory_stats(tmp_path: Path) -> None:
    """Test that process_foliant_directory tracks statistics correctly."""
    from scripts.import_foliant_to_db import process_foliant_directory

    # Create test directory with a mock PDF
    input_dir = tmp_path / "input_foliant"
    input_dir.mkdir()
    test_pdf = input_dir / "test.pdf"
    test_pdf.write_text("mock pdf content")

    with (
        patch("scripts.import_foliant_to_db.extract_foliant_data") as mock_extract,
        patch("scripts.import_foliant_to_db.import_to_database") as mock_import,
        patch("scripts.import_foliant_to_db.shutil.move"),
    ):
        mock_extract.return_value = {
            "articles": [{"model_number": "C257i"}],
            "compatibility_matrix": [],
            "filename": "test.pdf",
        }
        mock_import.return_value = True

        stats = process_foliant_directory(str(input_dir))

        assert stats["processed"] == 1
        assert stats["successful"] == 1
        assert stats["failed"] == 0


def test_process_foliant_directory_on_failure(tmp_path: Path) -> None:
    """Test that process_foliant_directory tracks failed imports."""
    from scripts.import_foliant_to_db import process_foliant_directory

    # Create test directory with a mock PDF
    input_dir = tmp_path / "input_foliant"
    input_dir.mkdir()
    test_pdf = input_dir / "test.pdf"
    test_pdf.write_text("mock pdf content")

    with (
        patch("scripts.import_foliant_to_db.extract_foliant_data") as mock_extract,
        patch("scripts.import_foliant_to_db.import_to_database") as mock_import,
    ):
        mock_extract.return_value = {"articles": [], "compatibility_matrix": [], "filename": "test.pdf"}
        mock_import.return_value = False

        stats = process_foliant_directory(str(input_dir))

        assert stats["processed"] == 1
        assert stats["successful"] == 0
        assert stats["failed"] == 1


def test_extract_articles_from_text_returns_list() -> None:
    """Test that _extract_articles_from_text returns a list."""
    from scripts.import_foliant_to_db import _extract_articles_from_text

    result = _extract_articles_from_text("Sample text with C257i and FS-539 models")

    assert isinstance(result, list)
    # Currently returns empty list as placeholder


def test_extract_compatibility_from_text_returns_list() -> None:
    """Test that _extract_compatibility_from_text returns a list."""
    from scripts.import_foliant_to_db import _extract_compatibility_from_text

    articles = [
        {"model_number": "C257i"},
        {"model_number": "FS-539"},
    ]

    result = _extract_compatibility_from_text("Sample compatibility text", articles)

    assert isinstance(result, list)
    # Currently returns empty list as placeholder
