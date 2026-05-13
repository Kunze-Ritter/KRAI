"""Manufacturer Normalizer

Normalizes manufacturer names to handle variations and aliases.
"""

import re

# Manufacturer normalization map
# Key: canonical name (what we store in DB)
# Value: list of aliases/variations
MANUFACTURER_MAP = {
    "HP Inc.": [
        "hp",
        "HP",
        "HP Inc",
        "HP Inc.",
        "hp inc",
        "hp inc.",
        "Hewlett Packard",
        "Hewlett-Packard",
        "hewlett packard",
        "hewlett-packard",
        "HEWLETT PACKARD",
        "HEWLETT-PACKARD",
        "H-P",
        "H P",
        "Hp",
        # Product series
        "laserjet",
        "LaserJet",
        "LASERJET",
        "officejet",
        "OfficeJet",
        "OFFICEJET",
        "deskjet",
        "DeskJet",
        "DESKJET",
        "pagewide",
        "PageWide",
        "PAGEWIDE",
        "designjet",
        "DesignJet",
        "DESIGNJET",
        "indigo",
        "Indigo",
        "INDIGO",
    ],
    "Konica Minolta": [
        "konica minolta",
        "Konica Minolta",
        "KONICA MINOLTA",
        "Konica-Minolta",
        "konica-minolta",
        "KONICA-MINOLTA",
        # Product series (strong indicators)
        "bizhub",
        "Bizhub",
        "BIZHUB",
        "accuriopress",
        "AccurioPress",
        "ACCURIOPRESS",
        "accurioprint",
        "AccurioPrint",
        "ACCURIOPRINT",
        "accuriolabel",
        "AccurioLabel",
        "ACCURIOLABEL",
        "accuriojet",
        "AccurioJet",
        "ACCURIOJET",
        # Removed: 'konica', 'minolta', 'km' (too generic - causes false positives)
        # 'KM' matches "5 KM" (kilometer), 'konica' alone is ambiguous
    ],
    "Canon": ["canon", "Canon", "CANON", "Canon Inc", "Canon Inc.", "canon inc", "canon inc."],
    "Ricoh": ["ricoh", "Ricoh", "RICOH", "Ricoh Company", "ricoh company"],
    "Xerox": ["xerox", "Xerox", "XEROX", "Xerox Corporation", "xerox corporation"],
    "Brother": ["brother", "Brother", "BROTHER", "Brother Industries", "brother industries"],
    "Lexmark": ["lexmark", "Lexmark", "LEXMARK", "Lexmark International", "lexmark international"],
    "Sharp": ["sharp", "Sharp", "SHARP", "Sharp Corporation", "sharp corporation"],
    "Epson": ["epson", "Epson", "EPSON", "Seiko Epson", "seiko epson", "SEIKO EPSON"],
    "Fujifilm": ["fujifilm", "Fujifilm", "FUJIFILM", "fuji", "Fuji", "FUJI", "Fuji Xerox", "fuji xerox", "FUJI XEROX"],
    "Riso": ["riso", "Riso", "RISO", "Riso Kagaku", "riso kagaku"],
    "Toshiba": ["toshiba", "Toshiba", "TOSHIBA", "Toshiba TEC", "toshiba tec", "TOSHIBA TEC"],
    "OKI": ["oki", "Oki", "OKI", "Oki Data", "oki data", "OKI DATA", "Okidata", "okidata", "OKIDATA"],
    "UTAX": [
        "utax",
        "Utax",
        "UTAX",
        "TA Triumph-Adler",
        "ta triumph-adler",
        "TA TRIUMPH-ADLER",
        "Triumph Adler",
        "triumph adler",
        "TRIUMPH ADLER",
        "Triumph-Adler",
        "triumph-adler",
        "TRIUMPH-ADLER",
    ],
    "Kyocera": [
        "kyocera",
        "Kyocera",
        "KYOCERA",
        "Kyocera Document Solutions",
        "kyocera document solutions",
        "Kyocera Mita",
        "kyocera mita",
        "KYOCERA MITA",
        # Product series
        "ecosys",
        "ECOSYS",
        "Ecosys",
        "taskalfa",
        "TASKalfa",
        "TASKALFA",
    ],
}


def normalize_manufacturer(name: str, strict: bool = False) -> str | None:
    """
    Normalize manufacturer name to canonical form

    Args:
        name: Manufacturer name (any variation)
        strict: If True, only use exact matches (no fuzzy matching)

    Returns:
        Canonical manufacturer name or None if not found

    Examples:
        normalize_manufacturer("hp inc") -> "Hewlett Packard"
        normalize_manufacturer("KM") -> "Konica Minolta"
        normalize_manufacturer("hewlett packard") -> "Hewlett Packard"
    """
    if not name:
        return None

    # Clean input
    name_clean = name.strip()
    name_lower = name_clean.lower()

    # Try exact match first (case-insensitive)
    for canonical, aliases in MANUFACTURER_MAP.items():
        if name_clean.lower() in [alias.lower() for alias in aliases]:
            return canonical

    # If strict mode, stop here
    if strict:
        return None

    # Try fuzzy match (contains) - but be more careful
    # Only match if the keyword is substantial (>3 chars) and appears as whole word

    # Special cases for common patterns - require word boundaries
    if re.search(r"\bhewlett\b|\bpackard\b", name_lower):
        return "Hewlett Packard"

    if re.search(r"\blexmark\b", name_lower):
        return "Lexmark"

    # For Konica Minolta, require both words or full match to avoid false positives
    if re.search(r"\bkonica\s+minolta\b", name_lower):
        return "Konica Minolta"

    # Try partial match with word boundaries
    for canonical, aliases in MANUFACTURER_MAP.items():
        for alias in aliases:
            # Only match if alias is substantial (>3 chars)
            if len(alias) > 3:
                # Use word boundary for better matching
                pattern = r"\b" + re.escape(alias.lower()) + r"\b"
                if re.search(pattern, name_lower):
                    return canonical

    # No match found
    return None


def normalize_manufacturer_prefix(prefix: str) -> str | None:
    """
    Normalize manufacturer prefix from filename to canonical form

    Args:
        prefix: Manufacturer prefix from filename (e.g., "HP_", "KM", "CANON_")

    Returns:
        Canonical manufacturer name or None if not found

    Examples:
        normalize_manufacturer_prefix("HP_") -> "HP Inc."
        normalize_manufacturer_prefix("KM") -> "Konica Minolta"
        normalize_manufacturer_prefix("CANON") -> "Canon"
    """
    if not prefix:
        return None

    # Clean input: strip underscores and whitespace, convert to uppercase
    prefix_clean = prefix.strip().strip("_").upper()

    # Prefix-to-canonical mapping
    PREFIX_MAP = {
        "HP": "HP Inc.",
        "KM": "Konica Minolta",
        "CANON": "Canon",
        "RICOH": "Ricoh",
        "XEROX": "Xerox",
        "BROTHER": "Brother",
        "LEXMARK": "Lexmark",
        "SHARP": "Sharp",
        "EPSON": "Epson",
        "KYOCERA": "Kyocera",
        "FUJIFILM": "Fujifilm",
        "FUJI": "Fujifilm",
        "RISO": "Riso",
        "TOSHIBA": "Toshiba",
        "OKI": "OKI",
        "UTAX": "UTAX",
    }

    return PREFIX_MAP.get(prefix_clean)


def get_manufacturer_aliases(canonical_name: str) -> list:
    """
    Get all aliases for a canonical manufacturer name

    Args:
        canonical_name: Canonical manufacturer name

    Returns:
        List of aliases
    """
    return MANUFACTURER_MAP.get(canonical_name, [])


def is_manufacturer_alias(name: str, canonical_name: str) -> bool:
    """
    Check if name is an alias of canonical manufacturer

    Args:
        name: Name to check
        canonical_name: Canonical manufacturer name

    Returns:
        True if name is an alias
    """
    if not name or not canonical_name:
        return False

    aliases = MANUFACTURER_MAP.get(canonical_name, [])
    return name.lower() in [alias.lower() for alias in aliases]


def add_manufacturer_alias(canonical_name: str, alias: str):
    """
    Add a new alias to a manufacturer

    Args:
        canonical_name: Canonical manufacturer name
        alias: New alias to add
    """
    if canonical_name in MANUFACTURER_MAP:
        if alias not in MANUFACTURER_MAP[canonical_name]:
            MANUFACTURER_MAP[canonical_name].append(alias)


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "HP Inc",
        "hp",
        "Hewlett Packard",
        "KM",
        "Konica",
        "Minolta",
        "konica minolta",
        "Canon Inc.",
        "Ricoh",
        "Brother Industries",
    ]

    print("Manufacturer Normalization Tests:")
    print("=" * 60)
    for test in test_cases:
        normalized = normalize_manufacturer(test)
        print(f"{test:30} -> {normalized}")
