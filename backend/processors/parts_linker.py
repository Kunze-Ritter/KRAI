"""
Parts Linker Module
Verknüpft Parts mit Products, Error Codes und Chunks

Strategien:
1. Parts im Service Manual → Verknüpfe mit Error Code wenn im gleichen Kontext
2. Parts im Parts Catalog → Verknüpfe mit Product basierend auf Kompatibilität
3. Parts in Lösung erwähnt → Verknüpfe mit Error Code
"""

import logging
import re

logger = logging.getLogger(__name__)


def find_parts_in_error_solution(error_code, parts: list, verbose: bool = False) -> list[str]:
    """
    Findet Parts die in der Error Code Lösung erwähnt werden

    Args:
        error_code: ExtractedErrorCode Objekt
        parts: Liste von ExtractedPart Objekten
        verbose: Logging aktivieren

    Returns:
        Liste von part_numbers die in der Lösung erwähnt werden

    Example:
        >>> error_code.solution_text = "Replace formatter (part 12345-A)"
        >>> parts = [ExtractedPart(part_number="12345-A", ...)]
        >>> linked = find_parts_in_error_solution(error_code, parts)
        >>> # Returns: ["12345-A"]
    """
    if not hasattr(error_code, "solution_text") or not error_code.solution_text:
        return []

    solution_text = error_code.solution_text.upper()
    linked_parts = []

    for part in parts:
        part_number = part.part_number.upper()

        # Direkte Erwähnung der Part Number
        if part_number in solution_text:
            linked_parts.append(part.part_number)
            if verbose:
                logger.info(f"✅ Found part {part_number} in error {error_code.error_code} solution")
            continue

        # Part Name erwähnt (z.B. "formatter", "fuser")
        if hasattr(part, "part_name") and part.part_name:
            part_name_lower = part.part_name.lower()
            # Extrahiere Hauptwort (z.B. "formatter" aus "HP Formatter Board")
            main_words = [w for w in part_name_lower.split() if len(w) > 4]

            for word in main_words:
                if word in solution_text.lower():
                    linked_parts.append(part.part_number)
                    if verbose:
                        logger.info(f"✅ Found part {part_number} via name '{word}' in error {error_code.error_code}")
                    break

    return linked_parts


def find_parts_near_error_code(error_code, parts: list, max_page_distance: int = 2, verbose: bool = False) -> list[str]:
    """
    Findet Parts die nahe beim Error Code im Dokument sind

    Args:
        error_code: ExtractedErrorCode Objekt
        parts: Liste von ExtractedPart Objekten
        max_page_distance: Maximale Seiten-Distanz
        verbose: Logging aktivieren

    Returns:
        Liste von part_numbers die nahe beim Error Code sind

    Example:
        >>> error_code.page_number = 45
        >>> parts = [ExtractedPart(part_number="12345", page_number=46)]
        >>> linked = find_parts_near_error_code(error_code, parts, max_page_distance=2)
        >>> # Returns: ["12345"]
    """
    if not hasattr(error_code, "page_number") or not error_code.page_number:
        return []

    error_page = error_code.page_number
    linked_parts = []

    for part in parts:
        if not hasattr(part, "page_number") or not part.page_number:
            continue

        part_page = part.page_number
        distance = abs(part_page - error_page)

        if distance <= max_page_distance:
            linked_parts.append(part.part_number)
            if verbose:
                logger.info(
                    f"✅ Found part {part.part_number} near error {error_code.error_code} (distance: {distance} pages)"
                )

    return linked_parts


def link_parts_to_error_codes(
    error_codes: list, parts: list, strategy: str = "solution_first", verbose: bool = False
) -> dict[str, list[str]]:
    """
    Verknüpft Parts mit Error Codes

    Strategien:
    - "solution_first": Bevorzuge Parts die in Lösung erwähnt werden
    - "proximity": Bevorzuge Parts die nahe beim Error Code sind
    - "both": Kombiniere beide Strategien

    Args:
        error_codes: Liste von ExtractedErrorCode Objekten
        parts: Liste von ExtractedPart Objekten
        strategy: Verknüpfungs-Strategie
        verbose: Logging aktivieren

    Returns:
        Dict: {error_code: [part_numbers]}

    Example:
        >>> links = link_parts_to_error_codes(error_codes, parts, strategy="both")
        >>> print(f"Error 66.60.32 needs parts: {links['66.60.32']}")
    """
    links = {}

    for error_code in error_codes:
        linked_parts = []

        # Strategie 1: Parts in Lösung
        if strategy in ["solution_first", "both"]:
            solution_parts = find_parts_in_error_solution(error_code, parts, verbose)
            linked_parts.extend(solution_parts)

        # Strategie 2: Parts in Nähe
        if strategy in ["proximity", "both"]:
            proximity_parts = find_parts_near_error_code(error_code, parts, verbose=verbose)
            # Nur hinzufügen wenn nicht schon in solution_parts
            for part in proximity_parts:
                if part not in linked_parts:
                    linked_parts.append(part)

        if linked_parts:
            links[error_code.error_code] = linked_parts
            if verbose:
                logger.info(f"📎 Linked {len(linked_parts)} parts to error {error_code.error_code}")

    return links


def find_parts_for_product(
    product, parts: list, parts_catalog_data: list[dict] | None = None, verbose: bool = False
) -> list[str]:
    """
    Findet Parts die zu einem Product gehören

    Args:
        product: ExtractedProduct Objekt
        parts: Liste von ExtractedPart Objekten (aus Service Manual)
        parts_catalog_data: Optional - Parts aus DB (krai_parts.parts_catalog)
        verbose: Logging aktivieren

    Returns:
        Liste von part_numbers die zum Product gehören

    Example:
        >>> product.model_number = "E877"
        >>> parts = db.table('vw_parts').select('*').ilike('compatible_models', '*E877*').execute()
        >>> linked = find_parts_for_product(product, [], parts.data)
    """
    linked_parts = []
    model = product.model_number.upper()

    # Strategie 1: Parts aus Service Manual (gleiche Seite oder nahe)
    if hasattr(product, "source_page") and product.source_page:
        product_page = product.source_page

        for part in parts:
            if not hasattr(part, "page_number") or not part.page_number:
                continue

            # Parts auf gleicher Seite oder ±5 Seiten
            if abs(part.page_number - product_page) <= 5:
                linked_parts.append(part.part_number)
                if verbose:
                    logger.info(f"✅ Found part {part.part_number} for product {model} (same document)")

    # Strategie 2: Parts aus Parts Catalog (kompatible Modelle)
    if parts_catalog_data:
        for part_data in parts_catalog_data:
            compatible_models = part_data.get("compatible_models", "")
            if not compatible_models:
                continue

            # Prüfe ob Model in compatible_models
            if model in compatible_models.upper():
                part_number = part_data.get("part_number")
                if part_number and part_number not in linked_parts:
                    linked_parts.append(part_number)
                    if verbose:
                        logger.info(f"✅ Found part {part_number} for product {model} (catalog)")

    return linked_parts


def extract_parts_from_context(context_text: str, known_parts: list | None = None) -> list[str]:
    """
    Extrahiert Part Numbers aus Text-Kontext

    Nützlich um Parts aus Error Code Kontext zu extrahieren.

    Args:
        context_text: Text der durchsucht werden soll
        known_parts: Optional - Liste bekannter Parts zum Abgleich

    Returns:
        Liste von gefundenen part_numbers

    Example:
        >>> context = "Replace formatter (RM1-12345-000) or fuser (RM2-67890-000)"
        >>> parts = extract_parts_from_context(context)
        >>> # Returns: ["RM1-12345-000", "RM2-67890-000"]
    """
    # Patterns für Part Numbers
    patterns = [
        r"\b[A-Z]{2,3}\d{1,2}-\d{5}-\d{3}\b",  # HP: RM1-12345-000
        r"\b[A-Z]\d{6}[A-Z]?\b",  # Generic: A123456B
        r"\b\d{5,8}-\d{2,3}\b",  # Generic: 12345-001
        r"\b[A-Z]{1,3}-\d{4,6}\b",  # Generic: ABC-12345
    ]

    found_parts = []

    for pattern in patterns:
        matches = re.findall(pattern, context_text.upper())
        found_parts.extend(matches)

    # Dedupliziere
    found_parts = list(set(found_parts))

    # Validiere gegen bekannte Parts wenn vorhanden
    if known_parts:
        known_part_numbers = [p.part_number.upper() for p in known_parts]
        found_parts = [p for p in found_parts if p in known_part_numbers]

    return found_parts


def validate_parts_linking(error_codes: list, parts: list, links: dict[str, list[str]]) -> dict[str, any]:
    """
    Validiert Parts-Verknüpfung und gibt Statistiken zurück

    Args:
        error_codes: Liste von ExtractedErrorCode Objekten
        parts: Liste von ExtractedPart Objekten
        links: Dict von {error_code: [part_numbers]}

    Returns:
        Dict mit Statistiken
    """
    total_errors = len(error_codes)
    errors_with_parts = len(links)
    total_parts_linked = sum(len(parts) for parts in links.values())

    return {
        "total_errors": total_errors,
        "errors_with_parts": errors_with_parts,
        "errors_without_parts": total_errors - errors_with_parts,
        "total_parts_linked": total_parts_linked,
        "avg_parts_per_error": total_parts_linked / errors_with_parts if errors_with_parts > 0 else 0,
        "linking_rate": (errors_with_parts / total_errors * 100) if total_errors > 0 else 0,
    }


__all__ = [
    "extract_parts_from_context",
    "find_parts_for_product",
    "find_parts_in_error_solution",
    "find_parts_near_error_code",
    "link_parts_to_error_codes",
    "validate_parts_linking",
]
