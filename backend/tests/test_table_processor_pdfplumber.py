from unittest.mock import MagicMock, patch


def _make_processor():
    from backend.processors.table_processor import TableProcessor

    return TableProcessor(
        database_service=MagicMock(),
        embedding_service=MagicMock(),
    )


def test_pdfplumber_fallback_called_when_pymupdf_finds_nothing():
    """When both PyMuPDF strategies find 0 tables, pdfplumber fallback must be tried."""
    processor = _make_processor()

    mock_page = MagicMock()
    mock_tabs = MagicMock()
    mock_tabs.tables = []
    mock_page.find_tables.return_value = mock_tabs

    mock_plumber_pdf = MagicMock()
    mock_plumber_pdf.pages = [MagicMock()]

    with patch.object(processor, "_extract_page_tables_pdfplumber", return_value=[]) as mock_plumber:
        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_plumber_pdf)
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            processor._extract_page_tables(mock_page, page_number=1, pdf_path="/fake/path.pdf")
        mock_plumber.assert_called_once_with(mock_plumber_pdf, 1)


def test_pdfplumber_not_called_when_pymupdf_finds_tables():
    """When PyMuPDF finds tables, pdfplumber must NOT be called."""
    processor = _make_processor()

    mock_page = MagicMock()
    mock_tabs = MagicMock()
    mock_tabs.tables = [MagicMock()]  # PyMuPDF found 1 table
    mock_page.find_tables.return_value = mock_tabs

    # Mock _extract_table_data to avoid deep processing
    with patch.object(processor, "_extract_table_data", return_value=None):
        with patch.object(processor, "_extract_page_tables_pdfplumber") as mock_plumber:
            processor._extract_page_tables(mock_page, page_number=1, pdf_path="/fake/path.pdf")
            mock_plumber.assert_not_called()


def test_has_headers_returns_false_for_all_numeric_row():
    """_detect_has_headers must return False when first row is all numeric."""
    processor = _make_processor()
    assert processor._detect_has_headers([["1", "2", "3"]]) is False


def test_has_headers_returns_true_for_text_row():
    """_detect_has_headers must return True when first row contains short text strings."""
    processor = _make_processor()
    assert processor._detect_has_headers([["Error Code", "Description", "Solution"]]) is True


def test_has_headers_returns_true_when_uncertain():
    """_detect_has_headers must return True (safe default) for empty/ambiguous input."""
    processor = _make_processor()
    assert processor._detect_has_headers([]) is True
    assert processor._detect_has_headers([[]]) is True
