"""Error Code Hierarchy Module

Handles hierarchical error code relationships (parent codes, categories).
Separated from main extractor for better maintainability.
"""

from typing import Any


def derive_parent_code(code: str, hierarchy_rules: dict[str, Any] | None) -> str | None:
    """
    Derive parent error code from child code based on hierarchy rules.

    Examples:
    - HP: '13.B9.Az' -> '13.B9'
    - Xerox: '541-011' -> '541'
    - Konica Minolta: 'C-2801' -> 'C-28'
    """
    if not hierarchy_rules:
        return None

    strategy = hierarchy_rules.get("strategy", "first_n_segments")
    separator = hierarchy_rules.get("separator", ".")

    if strategy == "first_n_segments":
        segments = code.split(separator)
        n = hierarchy_rules.get("n", 2)
        if len(segments) > n:
            return separator.join(segments[:n])
        return None

    if strategy == "prefix_digits":
        prefix_length = hierarchy_rules.get("prefix_length", 4)
        if len(code) > prefix_length:
            return code[:prefix_length]
        return None

    return None


def create_category_entries(
    codes: list[dict[str, Any]], hierarchy_rules: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """
    Create category entries for hierarchical error codes.

    A category groups multiple specific error codes under a parent code.
    Only creates entries where child codes exist.
    """
    if not hierarchy_rules:
        return []

    category_entries = []
    parent_codes_created = set()

    for code_data in codes:
        code = code_data.get("error_code", "")
        parent_code = derive_parent_code(code, hierarchy_rules)

        if parent_code and parent_code not in parent_codes_created:
            # Check if this parent actually has children
            has_children = any(
                derive_parent_code(c.get("error_code", ""), hierarchy_rules) == parent_code
                for c in codes
                if c.get("error_code", "") != code
            )

            if has_children:
                category_entries.append(
                    {
                        "error_code": parent_code,
                        "error_description": f"Category: {parent_code} series errors",
                        "is_category": True,
                        "parent_code": None,
                        "severity": "unknown",
                        "solutions": [],
                        "confidence": 0.5,
                    }
                )
                parent_codes_created.add(parent_code)

    return category_entries
