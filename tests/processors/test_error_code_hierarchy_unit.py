"""Unit tests for error_code_hierarchy module."""

from backend.processors.error_code_hierarchy import create_category_entries, derive_parent_code


class TestDeriveParentCode:
    """Test parent code derivation."""

    def test_first_n_segments_hp_style(self):
        """Test HP style codes (13.B9.Az -> 13.B9)."""
        rules = {"strategy": "first_n_segments", "separator": ".", "n": 2}
        assert derive_parent_code("13.B9.Az", rules) == "13.B9"

    def test_first_n_segments_xerox(self):
        """Test Xerox style codes (541-011 -> 541)."""
        rules = {"strategy": "first_n_segments", "separator": "-", "n": 1}
        assert derive_parent_code("541-011", rules) == "541"

    def test_prefix_digits_ricoh(self):
        """Test Ricoh style codes (SC542 -> SC5)."""
        rules = {"strategy": "prefix_digits", "prefix_length": 3}
        assert derive_parent_code("SC542", rules) == "SC5"

    def test_no_rules_returns_none(self):
        """Test with no rules returns None."""
        assert derive_parent_code("13.B9.Az", None) is None

    def test_too_short_code(self):
        """Test code shorter than threshold."""
        rules = {"strategy": "first_n_segments", "separator": ".", "n": 2}
        assert derive_parent_code("13", rules) is None

    def test_prefix_too_short(self):
        """Test prefix length longer than code."""
        rules = {"strategy": "prefix_digits", "prefix_length": 10}
        assert derive_parent_code("SC542", rules) is None


class TestCreateCategoryEntries:
    """Test category entry creation."""

    def test_empty_input(self):
        """Test with empty code list."""
        rules = {"strategy": "first_n_segments", "separator": ".", "n": 2}
        result = create_category_entries([], rules)
        assert result == []

    def test_no_rules_returns_empty(self):
        """Test with no rules returns empty list."""
        codes = [{"error_code": "13.B9.Az"}]
        result = create_category_entries(codes, None)
        assert result == []

    def test_single_code_no_children(self):
        """Test single code without children."""
        rules = {"strategy": "first_n_segments", "separator": ".", "n": 2}
        codes = [{"error_code": "13.B9"}]
        result = create_category_entries(codes, rules)
        assert result == []
