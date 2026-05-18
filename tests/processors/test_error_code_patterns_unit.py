"""Unit tests for error_code_patterns module."""

from backend.processors.error_code_patterns import (
    REJECT_CODES,
    TECHNICAL_TERMS,
    load_error_code_config,
    slugify_error_code,
)


class TestRejectCodes:
    """Test reject codes set."""

    def test_contains_common_words(self):
        """Verify reject codes contain common non-error words."""
        assert "descriptions" in REJECT_CODES
        assert "troubleshooting" in REJECT_CODES
        assert "error" in REJECT_CODES

    def test_is_frozenset(self):
        """Verify reject codes is a set for fast lookup."""
        assert isinstance(REJECT_CODES, (set, frozenset))


class TestTechnicalTerms:
    """Test technical terms set."""

    def test_contains_fuser(self):
        """Verify technical terms contain fuser (common in error codes)."""
        assert "fuser" in TECHNICAL_TERMS

    def test_contains_jam(self):
        """Verify technical terms contain jam."""
        assert "jam" in TECHNICAL_TERMS


class TestSlugify:
    """Test slugify function."""

    def test_lowercase(self):
        """Verify slugify converts to lowercase."""
        assert slugify_error_code("HP") == "hp"

    def test_removes_special_chars(self):
        """Verify slugify removes special characters."""
        assert slugify_error_code("13.B9.Az") == "13b9az"

    def test_handles_empty(self):
        """Verify slugify handles empty string."""
        assert slugify_error_code("") == ""


class TestLoadConfig:
    """Test config loading."""

    def test_returns_dict(self):
        """Verify load_error_code_config returns a dict."""
        config = load_error_code_config()
        assert isinstance(config, dict)
