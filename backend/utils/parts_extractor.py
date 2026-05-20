"""Parts Extraction Module

Extracts part numbers from error code solutions and descriptions.
Uses manufacturer-specific patterns from config/parts_patterns.json
"""

import json
import re
from pathlib import Path

# Load parts patterns config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "parts_patterns.json"
PARTS_CONFIG = None

MANUFACTURER_ALIASES = {
    "hp_inc": "hp",
    "hewlett_packard": "hp",
    "konica": "konica_minolta",
    "minolta": "konica_minolta",
}


def _load_config():
    """Load parts patterns configuration"""
    global PARTS_CONFIG
    if PARTS_CONFIG is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            PARTS_CONFIG = json.load(f)
    return PARTS_CONFIG


def _valid_manufacturer_keys(config: dict) -> list[str]:
    """Return manufacturer keys with a usable patterns list."""
    keys: list[str] = []
    for key, value in config.items():
        if not isinstance(value, dict):
            continue
        patterns = value.get("patterns")
        if isinstance(patterns, list) and patterns:
            keys.append(key)
    return keys


def _resolve_manufacturer_key(manufacturer_key: str | None, config: dict) -> str | None:
    """Normalize manufacturer aliases to config keys."""
    if not manufacturer_key:
        return None
    normalized = str(manufacturer_key).strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in config:
        return normalized
    return MANUFACTURER_ALIASES.get(normalized)


def extract_parts_by_manufacturer(text: str, manufacturer_key: str) -> str | None:
    """
    Extract parts using manufacturer-specific patterns from config

    Args:
        text: Text to extract from
        manufacturer_key: Manufacturer key (e.g., 'hp', 'canon', 'konica_minolta')

    Returns:
        Comma-separated list of part numbers or None
    """
    if not text:
        return None

    config = _load_config()

    # Get manufacturer patterns
    resolved_key = _resolve_manufacturer_key(manufacturer_key, config)
    if not resolved_key or resolved_key not in config:
        manufacturer_key = "generic"
    else:
        manufacturer_key = resolved_key

    manufacturer_config = config.get(manufacturer_key, {})
    patterns = manufacturer_config.get("patterns", [])

    if not patterns:
        return None

    parts = []
    min_confidence = config.get("extraction_rules", {}).get("min_confidence", 0.70)

    # Extract using all patterns for this manufacturer
    for pattern_config in patterns:
        if isinstance(pattern_config, str):
            pattern = pattern_config
            confidence = 0.8
        else:
            pattern = pattern_config.get("pattern")
            confidence = pattern_config.get("confidence", 0.5)

        if confidence < min_confidence:
            continue

        try:
            matches = re.findall(pattern, text)
            parts.extend(matches)
        except re.error:
            continue

    # Deduplicate
    parts = list(set(parts))

    # Filter out false positives
    parts = _filter_false_positives(parts, config)

    if not parts:
        return None

    parts.sort()
    return ", ".join(parts)


def _filter_false_positives(parts: list[str], config: dict) -> list[str]:
    """Filter out common false positives"""

    # Filter by length
    parts = [p for p in parts if 5 <= len(p) <= 25]

    # Filter common false positives
    false_positives = {"ERROR", "CODE", "PAGE", "STEP", "NOTE", "FIG", "TABLE", "SECTION"}
    return [p for p in parts if p.upper() not in false_positives]


def _has_any_keyword(text: str, keywords: list[str]) -> bool:
    """Case-insensitive keyword lookup."""
    if not text:
        return False
    text_l = text.lower()
    return any(k.lower() in text_l for k in keywords if k)


def _is_plausible_part_token(part: str) -> bool:
    """Basic token sanity checks to reject obvious non-part artifacts."""
    if not part:
        return False
    token = part.strip()
    if not (5 <= len(token) <= 25):
        return False
    # Pure words from headings/TOC should not be treated as part numbers.
    if token.isalpha():
        return False
    # Reject repeated digit artifacts like 1111111111.
    return not (token.isdigit() and len(set(token)) == 1)


def _looks_like_table_row_context(context: str, part: str) -> bool:
    """Heuristic for structured table rows around a part code."""
    if not context or not part:
        return False
    compact = re.sub(r"\s+", " ", context)
    return bool(
        re.search(
            rf"{re.escape(part)}\s+\d+\s+\d+\s+[A-Za-z][A-Za-z0-9()\/,\- ]{{3,120}}",
            compact,
            re.IGNORECASE,
        )
        or re.search(
            rf"{re.escape(part)}\s+\d+\s+[A-Za-z][A-Za-z0-9()\/,\- ]{{3,120}}",
            compact,
            re.IGNORECASE,
        )
    )


def _is_context_noise_for_part(context: str, part: str, rules: dict, manufacturer_key: str, pattern_name: str) -> bool:
    """
    Determine whether a match is likely not a spare part reference.

    This blocks false positives like firmware bundle IDs (e.g. 82M8579).
    """
    if not context:
        return True

    context_l = context.lower()
    indicators = rules.get("part_number_indicators", []) or []
    exclusion_terms = rules.get("exclude_if_near", []) or []

    # Strong noise markers observed in manuals/download instructions.
    hard_noise_terms = [
        "bundle zip",
        "settings bundle",
        "import configuration",
        "downloads.lexmark.com",
        "/downloads/firmware/",
        "firmware version",
        "embedded web server",
        "chart no",
        "ctc-",
        "signal format",
        "preamble",
        "modifications not authorized",
        "safety warnings",
        "authorized by",
    ]

    # Lexmark's broad numeric pattern is useful, but catches firmware IDs.
    if manufacturer_key == "lexmark" and pattern_name == "standard_parts_numeric":
        if _has_any_keyword(context_l, hard_noise_terms):
            return True

    # Prefer stricter indicators over broad service-manual keywords.
    strong_part_terms = [
        "part number",
        "part no",
        "part #",
        "p/n",
        "item no",
        "description",
        "qty",
        "quantity",
        "order",
        "replacement part",
    ]
    has_part_signal = _has_any_keyword(context_l, indicators) or _has_any_keyword(context_l, strong_part_terms)
    has_table_signal = _looks_like_table_row_context(context, part)
    has_soft_exclusion = _has_any_keyword(context_l, exclusion_terms)

    # Konica broad numeric dash pattern often catches option kits and references.
    if manufacturer_key == "konica_minolta" and pattern_name == "parts_4digit_numeric":
        if _has_any_keyword(context_l, ["key counter kit", "kit-", "optional", "chart no", "ctc-"]):
            return True

    # Keep when either table structure or part-related semantics is present.
    if has_table_signal or has_part_signal:
        return False

    # No part signal + contextual noise => likely false positive.
    return has_soft_exclusion or _has_any_keyword(context_l, hard_noise_terms)


def extract_parts(text: str) -> str | None:
    """
    Extract part numbers from text

    Supports multiple formats:
    - 6QN29-67005
    - RM1-1234-000
    - CE285A
    - Q7553X
    - Part: ABC123
    - Part Number: XYZ-456

    Args:
        text: Text to extract parts from

    Returns:
        Comma-separated list of part numbers or None
    """
    if not text:
        return None

    parts = []

    # Pattern 1: HP style (6QN29-67005, RM1-1234-000)
    hp_pattern = r"\b([A-Z0-9]{3,6}-[A-Z0-9]{3,6}(?:-[A-Z0-9]{3})?)\b"
    parts.extend(re.findall(hp_pattern, text))

    # Pattern 2: Toner/Consumable codes (CE285A, Q7553X, CF283A)
    consumable_pattern = r"\b([A-Z]{2}\d{3,4}[A-Z]{0,2})\b"
    parts.extend(re.findall(consumable_pattern, text))

    # Pattern 3: "Part:" or "Part Number:" followed by code
    part_label_pattern = r"(?:part(?:\s+number)?|p/n|part\s*#)\s*[:=]?\s*([A-Z0-9][-A-Z0-9]{4,20})"
    parts.extend(re.findall(part_label_pattern, text, re.IGNORECASE))

    # Pattern 4: Konica Minolta style (A1DU-R750-00, 4062-R750-01)
    km_pattern = r"\b([A-Z0-9]{4}-[A-Z0-9]{4}-\d{2})\b"
    parts.extend(re.findall(km_pattern, text))

    # Pattern 5: Canon style (FM3-5945-000, QY6-0073-000)
    canon_pattern = r"\b([A-Z]{2}\d-\d{4}-\d{3})\b"
    parts.extend(re.findall(canon_pattern, text))

    # Pattern 6: Lexmark style (40X5852, 40X7743)
    lexmark_pattern = r"\b(\d{2}X\d{4})\b"
    parts.extend(re.findall(lexmark_pattern, text))

    # Deduplicate and clean
    parts = list(set(parts))

    # Filter out common false positives
    false_positives = {"ERROR", "CODE", "PAGE", "STEP", "NOTE", "FIG", "TABLE"}
    parts = [p for p in parts if p.upper() not in false_positives]

    # Filter out too short or too long
    parts = [p for p in parts if 5 <= len(p) <= 25]

    if not parts:
        return None

    # Sort and return
    parts.sort()
    return ", ".join(parts)


def extract_parts_with_context(text: str, manufacturer_key: str | None = None, max_parts: int = 20) -> list[dict]:
    """
    Extract parts with surrounding context using config patterns

    Args:
        text: Text to extract from
        manufacturer_key: Manufacturer key for specific patterns
        max_parts: Maximum number of parts to return

    Returns:
        List of dicts with 'part', 'context', 'pattern_name', and 'confidence' keys
    """
    if not text:
        return []

    config = _load_config()
    context_window = config.get("extraction_rules", {}).get("context_window_chars", 200)
    min_confidence = config.get("extraction_rules", {}).get("min_confidence", 0.70)
    extraction_rules = config.get("extraction_rules", {}) or {}

    parts_with_context = []

    # Determine which manufacturers to use
    manufacturers_to_check: list[str] = []
    resolved_key = _resolve_manufacturer_key(manufacturer_key, config)
    if resolved_key and resolved_key in config:
        manufacturers_to_check.append(resolved_key)
    else:
        # Try all configured manufacturers if no specific one given
        manufacturers_to_check = _valid_manufacturer_keys(config)

    # Extract from each manufacturer's patterns
    for mfr_key in manufacturers_to_check:
        mfr_config = config.get(mfr_key, {})
        if not isinstance(mfr_config, dict):
            continue
        patterns = mfr_config.get("patterns", [])

        for pattern_config in patterns:
            # Backward-compatible handling: patterns can be dicts or plain regex strings.
            if isinstance(pattern_config, str):
                pattern = pattern_config
                confidence = 0.8
                pattern_name = "legacy_pattern"
            else:
                pattern = pattern_config.get("pattern")
                confidence = pattern_config.get("confidence", 0.5)
                pattern_name = pattern_config.get("name", "unknown")

            if confidence < min_confidence:
                continue
            if not pattern:
                continue

            try:
                for match in re.finditer(pattern, text):
                    part = match.group(0)
                    if not _is_plausible_part_token(part):
                        continue
                    raw_start = max(0, match.start() - context_window)
                    raw_end = min(len(text), match.end() + context_window)

                    # Expand to nearby line boundaries first, then to word boundaries,
                    # so we avoid clipped tokens like "oner" instead of "Toner".
                    start = raw_start
                    prev_nl = text.rfind("\n", max(0, raw_start - 120), raw_start + 1)
                    if prev_nl != -1:
                        start = prev_nl + 1
                    else:
                        while start > 0 and text[start - 1].isalnum():
                            start -= 1

                    end = raw_end
                    next_nl = text.find("\n", raw_end, min(len(text), raw_end + 120))
                    if next_nl != -1:
                        end = next_nl
                    else:
                        while end < len(text) and text[end].isalnum():
                            end += 1

                    context = text[start:end].strip()

                    if _is_context_noise_for_part(
                        context=context,
                        part=part,
                        rules=extraction_rules,
                        manufacturer_key=mfr_key,
                        pattern_name=pattern_name,
                    ):
                        continue

                    parts_with_context.append(
                        {
                            "part": part,
                            "context": context,
                            "pattern_name": pattern_name,
                            "confidence": confidence,
                            "manufacturer": mfr_key,
                        }
                    )
            except re.error:
                continue

    # Deduplicate by part number (keep highest confidence)
    seen = {}
    for item in parts_with_context:
        part = item["part"]
        if part not in seen or item["confidence"] > seen[part]["confidence"]:
            seen[part] = item

    unique_parts = list(seen.values())

    # Sort by confidence
    unique_parts.sort(key=lambda x: x["confidence"], reverse=True)

    return unique_parts[:max_parts]


if __name__ == "__main__":
    # Test
    test_text = """
    Replace the flatbed scanner assembly.
    Flatbed scanner - 6QN29-67005

    If error persists, replace toner cartridge CE285A.
    Part Number: RM1-1234-000
    """

    parts = extract_parts(test_text)
    print(f"Parts found: {parts}")

    parts_ctx = extract_parts_with_context(test_text)
    for item in parts_ctx:
        print(f"Part: {item['part']}")
        print(f"Context: {item['context']}")
        print()
