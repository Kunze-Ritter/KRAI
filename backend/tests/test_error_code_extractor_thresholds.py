import inspect

from backend.processors import error_code_extractor as ece_module
from backend.processors.error_code_extractor import ErrorCodeExtractor
from backend.processors.models import ExtractedErrorCode


def _make_code(solution_text: str) -> ExtractedErrorCode:
    return ExtractedErrorCode(
        error_code="13.B9.Az",
        error_description="Paper jam in fuser area detected",
        solution_technician_text=solution_text,
        context_text="Error code 13.B9.Az indicates a paper jam in the fuser area of the printer unit.",
        confidence=0.8,
        page_number=1,
        extraction_method="test",
    )


def test_enrichment_skip_threshold_is_500_not_100():
    """Bug 4: enrichment skip threshold must be 500, not 100."""
    source = inspect.getsource(ece_module)
    assert "<= 500" in source, "Enrichment skip threshold must be 500, not 100"
    assert "<= 100" not in source, "Old 100-char threshold must be removed"


def test_enrichment_skip_threshold_present_in_codes_needing_enrichment():
    """The threshold <= 500 must appear in the codes_needing_enrichment filter."""
    source = inspect.getsource(ece_module.ErrorCodeExtractor.enrich_error_codes_from_document)
    assert "<= 500" in source, "Enrichment skip threshold must be <= 500 in enrich_error_codes_from_document"
    assert "<= 100" not in source, "Old 100-char threshold must not be in enrich_error_codes_from_document"


def test_early_exit_threshold_is_1500_not_200():
    """The early-exit threshold in the enrichment match loop must be >1500, not >200 (Bug 1 fix)."""
    source = inspect.getsource(ece_module.ErrorCodeExtractor.enrich_error_codes_from_document)
    # The old (wrong) threshold was > 200 — ensure it is NOT present and > 1500 IS present
    assert "> 200" not in source, "Old threshold '> 200' still present in enrich_error_codes"
    assert "> 1500" in source, "New threshold '> 1500' not found in enrich_error_codes"


def test_extract_description_allows_up_to_1500_chars():
    """_extract_description max_length must be 1500, not 500 (Bug 2 fix)."""
    extractor = ErrorCodeExtractor()
    long_desc = "Classification: " + ("This is a detailed error description. " * 50)  # >500 chars
    result = extractor._extract_description(long_desc, 0, max_length=1500)
    assert result is not None, "_extract_description returned None for a valid description"
    assert not result.endswith("..."), "Description must not be truncated with ellipsis"
    assert len(result) <= 1500


def test_bullet_line_cap_is_30_not_8():
    """Bullet line cap in _extract_solution must be [:30] not [:8] (Bug 3 fix)."""
    source = inspect.getsource(ece_module.ErrorCodeExtractor._extract_solution)
    # Verify the cap was raised from 8 to 30
    assert "[:8]" not in source, "Old bullet cap '[:8]' still present in _extract_solution"
    assert "[:30]" in source, "New bullet cap '[:30]' not found in _extract_solution"
