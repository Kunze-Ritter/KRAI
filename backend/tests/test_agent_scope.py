"""Unit tests for agent scope and query helper logic."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "api" / "agent_scope.py"
SPEC = importlib.util.spec_from_file_location("agent_scope", MODULE_PATH)
assert SPEC and SPEC.loader
agent_scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_scope)

AgentScope = agent_scope.AgentScope
build_error_code_variants = agent_scope.build_error_code_variants
build_scope_filters = agent_scope.build_scope_filters
build_scope_system_message = agent_scope.build_scope_system_message
extract_error_search_term = agent_scope.extract_error_search_term
extract_scope_from_openai_payload = agent_scope.extract_scope_from_openai_payload
merge_scope = agent_scope.merge_scope
normalize_scope = agent_scope.normalize_scope


def test_normalize_scope_removes_empty_values():
    scope = AgentScope(manufacturer=" HP ", product=" ", series=None, product_id="abc")

    assert normalize_scope(scope) == {
        "manufacturer": "HP",
        "product_id": "abc",
    }


def test_merge_scope_clears_dependent_fields_when_manufacturer_changes():
    merged = merge_scope(
        {
            "manufacturer": "HP",
            "product": "Color LaserJet E877",
            "product_id": "old-product-id",
            "document_id": "doc-1",
        },
        AgentScope(manufacturer="Konica Minolta"),
    )

    assert merged == {"manufacturer": "Konica Minolta"}


def test_merge_scope_keeps_existing_scope_until_reset():
    merged = merge_scope(
        {"manufacturer": "HP", "product": "E877"},
        AgentScope(series="Flow"),
    )

    assert merged == {
        "manufacturer": "HP",
        "product": "E877",
        "series": "Flow",
    }

    reset = merge_scope(merged, AgentScope(product="bizhub C3320i"), reset=True)
    assert reset == {"product": "bizhub C3320i"}


def test_build_scope_system_message_includes_scope_details():
    message = build_scope_system_message({"manufacturer": "HP", "product": "Color LaserJet E877", "series": "Flow"})

    assert message is not None
    assert "Hersteller: HP" in message
    assert "Produkt: Color LaserJet E877" in message
    assert "Serie: Flow" in message


def test_extract_error_search_term_prefers_code_from_free_text():
    assert extract_error_search_term("HP Fehler 10.00.33 an E877") == "10.00.33"
    assert extract_error_search_term("Konica Minolta C9402 erklärt") == "C9402"
    assert extract_error_search_term("Ricoh SC542 Hilfe") == "SC542"


def test_build_error_code_variants_adds_compact_forms():
    assert build_error_code_variants("50.FF.02") == ["50.FF.02", "50FF02"]
    assert build_error_code_variants("C-2801") == ["C-2801", "C2801"]


def test_build_scope_filters_creates_expected_sql_and_params():
    params: list[object] = []
    clauses = build_scope_filters(
        params,
        {
            "manufacturer": "HP",
            "product": "E877",
            "product_id": "product-uuid",
            "document_id": "document-uuid",
        },
        manufacturer_templates=("m.name ILIKE ${index}",),
        product_templates=(
            "p.model_number ILIKE ${index}",
            "p.model_name ILIKE ${index}",
        ),
        product_id_template="vp.product_id = ${index}::uuid",
        document_id_template="d.id = ${index}::uuid",
    )

    assert clauses == [
        "(m.name ILIKE $1)",
        "(p.model_number ILIKE $2 OR p.model_name ILIKE $3)",
        "vp.product_id = $4::uuid",
        "d.id = $5::uuid",
    ]
    assert params == [
        "%HP%",
        "%E877%",
        "%E877%",
        "product-uuid",
        "document-uuid",
    ]


def test_extract_scope_from_openai_payload_supports_metadata_scope():
    scope, reset_scope = extract_scope_from_openai_payload(
        metadata={
            "scope": {
                "manufacturer": "HP",
                "product": "Color LaserJet E877",
            },
            "reset_scope": True,
        }
    )

    assert scope is not None
    assert scope.manufacturer == "HP"
    assert scope.product == "Color LaserJet E877"
    assert reset_scope is True
