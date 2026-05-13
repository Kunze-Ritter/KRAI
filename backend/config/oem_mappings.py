"""
OEM/Rebrand Manufacturer Mappings
==================================

Many printer manufacturers rebrand other manufacturers' products.
This causes issues with error code and parts detection because:
- The BRAND says "Konica Minolta"
- But the ERROR CODES are from "Brother"
- And the PARTS are from "Brother"

This module maps product series to their OEM engine manufacturer.

Usage:
    from config.oem_mappings import get_oem_manufacturer

    # Product is branded as "Konica Minolta 5000i"
    oem = get_oem_manufacturer("Konica Minolta", "5000i")
    # Returns: "Brother" (for error codes and parts)
"""

import re
from typing import Any, cast

# OEM Mappings
# Format: (Brand Manufacturer, Series Pattern) -> OEM Engine Manufacturer
OEM_MAPPINGS: dict[tuple[str, str], dict[str, Any]] = {
    # ===== KONICA MINOLTA REBRANDS =====
    # Konica Minolta 5000i/4000i series → Brother Engine
    ("Konica Minolta", r"[45]000i"): {
        "oem_manufacturer": "Brother",
        "series_name": "5000i/4000i Series",
        "notes": "Brother engine with Konica Minolta branding",
        "applies_to": ["error_codes", "parts"],
    },
    # Konica Minolta bizhub 4750/4050/4020 → Lexmark Engine
    ("Konica Minolta", r"(?:bizhub\s+)?40[257]0i?"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "bizhub 4000 Series",
        "notes": "Lexmark engine with Konica Minolta branding",
        "applies_to": ["error_codes", "parts"],
    },
    # Konica Minolta bizhub 3300P/3320 → Lexmark Engine
    ("Konica Minolta", r"(?:bizhub\s+)?33[02]0P?"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "bizhub 3300 Series",
        "notes": "Lexmark engine with Konica Minolta branding",
        "applies_to": ["error_codes", "parts"],
    },
    # ===== LEXMARK REBRANDS =====
    # Lexmark CS/CX 900 series → Konica Minolta Engine
    ("Lexmark", r"C[SX]9[0-9]{2}[a-z]*"): {
        "oem_manufacturer": "Konica Minolta",
        "series_name": "CS/CX 900 Series",
        "notes": "Konica Minolta bizhub engine (XC9225, XC9235, XC9245, XC9255, XC9265)",
        "applies_to": ["error_codes", "parts"],
    },
    # Lexmark CS/CX 800 series → Konica Minolta Engine
    ("Lexmark", r"C[SX]8[0-9]{2}[a-z]*"): {
        "oem_manufacturer": "Konica Minolta",
        "series_name": "CS/CX 800 Series",
        "notes": "Konica Minolta bizhub engine",
        "applies_to": ["error_codes", "parts"],
    },
    # Lexmark MX622 → Konica Minolta Engine
    ("Lexmark", r"MX6[0-9]{2}[a-z]*"): {
        "oem_manufacturer": "Konica Minolta",
        "series_name": "MX600 Series",
        "notes": "Konica Minolta engine (same as bizhub 4750)",
        "applies_to": ["error_codes", "parts"],
    },
    # ===== UTAX REBRANDS =====
    # UTAX → Kyocera (ALL products!)
    ("UTAX", r".*"): {
        "oem_manufacturer": "Kyocera",
        "series_name": "All UTAX Products",
        "notes": "UTAX is Kyocera rebrand for European market (100% identical hardware)",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # Triumph-Adler (TA) → Kyocera (ALL products!)
    ("Triumph-Adler", r".*"): {
        "oem_manufacturer": "Kyocera",
        "series_name": "All Triumph-Adler Products",
        "notes": "Triumph-Adler is Kyocera rebrand (owned by Kyocera since 2003)",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # TA Triumph-Adler (alternative name)
    ("TA Triumph-Adler", r".*"): {
        "oem_manufacturer": "Kyocera",
        "series_name": "All TA Triumph-Adler Products",
        "notes": "TA Triumph-Adler is Kyocera rebrand",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # ===== XEROX REBRANDS =====
    # Xerox A4 devices → Lexmark Engine (majority of A4 portfolio)
    ("Xerox", r"VersaLink [BC]\d{3}"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "VersaLink Series",
        "notes": "Lexmark engine (Xerox ships 1M+ Lexmark-based A4 devices)",
        "applies_to": ["error_codes", "parts"],
    },
    # Xerox WorkCentre 6515 → Lexmark Engine
    ("Xerox", r"WorkCentre 651[05]"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "WorkCentre 6515 Series",
        "notes": "Lexmark CS/CX engine",
        "applies_to": ["error_codes", "parts"],
    },
    # Xerox B-series → Lexmark Engine
    ("Xerox", r"B[0-9]{3}[a-z]*"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "B-Series",
        "notes": "Lexmark engine for A4 monochrome",
        "applies_to": ["error_codes", "parts"],
    },
    # Xerox C-series → Lexmark Engine
    ("Xerox", r"C[0-9]{3}[a-z]*"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "C-Series",
        "notes": "Lexmark engine for A4 color",
        "applies_to": ["error_codes", "parts"],
    },
    # Xerox A3 MFPs → Fujifilm Engine
    ("Xerox", r"AltaLink [BC]\d{4}"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "AltaLink Series",
        "notes": "Fujifilm Business Innovation engine (A3 MFPs, ex-Fuji Xerox partnership)",
        "applies_to": ["error_codes", "parts"],
    },
    # Xerox Versant → Fujifilm Engine
    ("Xerox", r"Versant.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "Versant Series",
        "notes": "Fujifilm engine (production color press, renewed multi-year contract)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
    # Xerox Iridesse → Fujifilm Engine
    ("Xerox", r"Iridesse.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "Iridesse Production Press",
        "notes": "Fujifilm engine (specialty color production press with 6-color capability)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
    # Xerox PrimeLink → Fujifilm Engine
    ("Xerox", r"PrimeLink.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "PrimeLink Series",
        "notes": "Fujifilm engine (production print, entry to mid-range)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
    # Xerox Nuvera → Fujifilm Engine
    ("Xerox", r"Nuvera.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "Nuvera Series",
        "notes": "Fujifilm engine (high-volume monochrome production)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
    # Xerox Production Inkjet → Kyocera Engine (NEW 2025!)
    ("Xerox", r"(?:TASKalfa Pro|Inkjet).*15000"): {
        "oem_manufacturer": "Kyocera",
        "series_name": "Production Inkjet Series",
        "notes": "Kyocera TASKalfa Pro 15000c engine (partnership announced July 2025)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
    # ===== RICOH FAMILY (Same Company, Different Brands) =====
    # Savin → Ricoh (100% identical, just different badge)
    ("Savin", r".*"): {
        "oem_manufacturer": "Ricoh",
        "series_name": "All Savin Products",
        "notes": "Savin is Ricoh subsidiary - identical hardware, different badge",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # Lanier → Ricoh (100% identical, just different badge)
    ("Lanier", r".*"): {
        "oem_manufacturer": "Ricoh",
        "series_name": "All Lanier Products",
        "notes": "Lanier is Ricoh subsidiary - identical hardware, different badge",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # Gestetner → Ricoh (now merged into Lanier)
    ("Gestetner", r".*"): {
        "oem_manufacturer": "Ricoh",
        "series_name": "All Gestetner Products",
        "notes": "Gestetner is now Lanier (Ricoh subsidiary)",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # ===== TOSHIBA REBRANDS =====
    # Toshiba e-STUDIO 389CS/509CS → Lexmark Engine
    ("Toshiba", r"e-STUDIO [3-5]89CS"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "e-STUDIO CS Series",
        "notes": "Lexmark CX725 engine (same as Lexmark CX725dhe)",
        "applies_to": ["error_codes", "parts"],
    },
    # Toshiba e-STUDIO 478s → Lexmark Engine
    ("Toshiba", r"e-STUDIO 478s"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "e-STUDIO 478s",
        "notes": "Lexmark MX622 engine",
        "applies_to": ["error_codes", "parts"],
    },
    # ===== DELL REBRANDS =====
    # Dell Laser Printers → Lexmark Engine (historical partnership)
    ("Dell", r"[BC]\d{4}[a-z]*"): {
        "oem_manufacturer": "Lexmark",
        "series_name": "Dell Laser Printers",
        "notes": "Lexmark engine (Dell-Lexmark partnership 2002-2017)",
        "applies_to": ["error_codes", "parts"],
    },
    # ===== HP REBRANDS =====
    # HP Samsung A3 devices → Samsung Engine (acquired 2017)
    ("HP", r"(?:Samsung\s+)?(?:SL-|SCX-)[A-Z]\d{4}"): {
        "oem_manufacturer": "Samsung",
        "series_name": "HP Samsung A3 Series",
        "notes": "Samsung engine (HP acquired Samsung printer business in 2017)",
        "applies_to": ["error_codes", "parts"],
    },
    # HP A3 MFPs with Samsung heritage
    ("HP", r"LaserJet MFP E[78]\d{4}"): {
        "oem_manufacturer": "Samsung",
        "series_name": "LaserJet Enterprise A3 MFP",
        "notes": "Samsung-based A3 platform (post-2017 acquisition)",
        "applies_to": ["error_codes", "parts"],
    },
    # ===== FUJIFILM / FUJI XEROX =====
    # Fuji Xerox → Fujifilm Business Innovation (rebranded 2021)
    ("Fuji Xerox", r".*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "All Fuji Xerox Products",
        "notes": "Fuji Xerox rebranded to Fujifilm Business Innovation in April 2021",
        "applies_to": ["error_codes", "parts", "accessories"],
    },
    # Fujifilm Business Innovation ApeosPort → Same as Xerox AltaLink
    ("Fujifilm", r"ApeosPort.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "ApeosPort Series",
        "notes": "Fujifilm engine (same platform as Xerox AltaLink, ex-Fuji Xerox)",
        "applies_to": ["error_codes", "parts"],
    },
    # Fujifilm Business Innovation DocuCentre → Same as Xerox WorkCentre
    ("Fujifilm", r"DocuCentre.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "DocuCentre Series",
        "notes": "Fujifilm engine (same platform as Xerox WorkCentre, ex-Fuji Xerox)",
        "applies_to": ["error_codes", "parts"],
    },
    # Fujifilm DocuPrint
    ("Fujifilm", r"DocuPrint.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "DocuPrint Series",
        "notes": "Fujifilm engine (ex-Fuji Xerox)",
        "applies_to": ["error_codes", "parts"],
    },
    # Fujifilm Revoria Press → Same platform as Xerox Versant/Iridesse
    ("Fujifilm", r"Revoria.*"): {
        "oem_manufacturer": "Fujifilm",
        "series_name": "Revoria Press Series",
        "notes": "Fujifilm production press (same platform as Xerox Versant/Iridesse, launched after Fuji Xerox split)",
        "applies_to": ["error_codes", "parts", "supplies"],
    },
}


def get_oem_manufacturer(brand_manufacturer: str, model_or_series: str, for_purpose: str = "error_codes") -> str | None:
    """
    Get the OEM engine manufacturer for a product

    Args:
        brand_manufacturer: The brand name (e.g., "Konica Minolta", "Lexmark")
        model_or_series: The model or series name (e.g., "5000i", "CS943")
        for_purpose: What you need the OEM for ('error_codes', 'parts', 'accessories')

    Returns:
        OEM manufacturer name if rebrand, None if original manufacturer

    Examples:
        >>> get_oem_manufacturer("Konica Minolta", "5000i", "error_codes")
        "Brother"

        >>> get_oem_manufacturer("Lexmark", "CS943", "error_codes")
        "Konica Minolta"

        >>> get_oem_manufacturer("HP", "M455", "error_codes")
        None  # HP is original manufacturer
    """
    if not brand_manufacturer or not model_or_series:
        return None

    # Check each OEM mapping
    for (brand, pattern), mapping in OEM_MAPPINGS.items():
        # Check if brand matches
        if brand.lower() != brand_manufacturer.lower():
            continue

        # Check if model/series matches pattern and purpose applies
        if re.search(pattern, model_or_series, re.IGNORECASE) and for_purpose in mapping["applies_to"]:
            return cast(str, mapping["oem_manufacturer"])

    # No OEM mapping found - use original manufacturer
    return None


def get_effective_manufacturer(brand_manufacturer: str, model_or_series: str, for_purpose: str = "error_codes") -> str:
    """
    Get the effective manufacturer to use for detection

    This returns either the OEM manufacturer (if rebrand) or the original manufacturer.

    Args:
        brand_manufacturer: The brand name
        model_or_series: The model or series name
        for_purpose: What you need the manufacturer for

    Returns:
        The manufacturer to use for detection (OEM or original)

    Examples:
        >>> get_effective_manufacturer("Konica Minolta", "5000i", "error_codes")
        "Brother"  # Use Brother patterns

        >>> get_effective_manufacturer("HP", "M455", "error_codes")
        "HP"  # Use HP patterns
    """
    oem = get_oem_manufacturer(brand_manufacturer, model_or_series, for_purpose)
    return oem if oem else brand_manufacturer


def get_oem_info(brand_manufacturer: str, model_or_series: str) -> dict | None:
    """
    Get full OEM information for a product

    Args:
        brand_manufacturer: The brand name
        model_or_series: The model or series name

    Returns:
        Dictionary with OEM info, or None if not a rebrand

    Example:
        >>> get_oem_info("Konica Minolta", "5000i")
        {
            'oem_manufacturer': 'Brother',
            'series_name': '5000i/4000i Series',
            'notes': 'Brother engine with Konica Minolta branding',
            'applies_to': ['error_codes', 'parts']
        }
    """
    if not brand_manufacturer or not model_or_series:
        return None

    for (brand, pattern), mapping in OEM_MAPPINGS.items():
        if brand.lower() == brand_manufacturer.lower() and re.search(pattern, model_or_series, re.IGNORECASE):
            return mapping

    return None


def list_all_oem_mappings() -> list[dict]:
    """
    List all OEM mappings for documentation/debugging

    Returns:
        List of all OEM mappings with brand and pattern info
    """
    mappings = []
    for (brand, pattern), mapping in OEM_MAPPINGS.items():
        mappings.append({"brand": brand, "pattern": pattern, **mapping})
    return mappings


def is_rebrand(brand_manufacturer: str, model_or_series: str) -> bool:
    """
    Check if a product is a rebrand

    Args:
        brand_manufacturer: The brand name
        model_or_series: The model or series name

    Returns:
        True if rebrand, False if original
    """
    return get_oem_manufacturer(brand_manufacturer, model_or_series) is not None


# Example usage and testing
if __name__ == "__main__":
    print("=" * 80)
    print("OEM Manufacturer Mappings")
    print("=" * 80)

    test_cases = [
        ("Konica Minolta", "5000i", "error_codes"),
        ("Konica Minolta", "4000i", "error_codes"),
        ("Lexmark", "CS943", "error_codes"),
        ("Lexmark", "CX943", "parts"),
        ("UTAX", "P-4020", "error_codes"),
        ("HP", "M455", "error_codes"),
        ("Xerox", "VersaLink C405", "error_codes"),
    ]

    print("\nTest Cases:")
    print("-" * 80)
    for brand, model, purpose in test_cases:
        oem = get_oem_manufacturer(brand, model, purpose)
        effective = get_effective_manufacturer(brand, model, purpose)
        is_rb = is_rebrand(brand, model)

        print(f"\n{brand} {model} (for {purpose}):")
        print(f"  OEM: {oem if oem else 'None (original)'}")
        print(f"  Effective Manufacturer: {effective}")
        print(f"  Is Rebrand: {is_rb}")

        if is_rb:
            info = get_oem_info(brand, model)
            if info:
                print(f"  Series: {info['series_name']}")
                print(f"  Notes: {info['notes']}")

    print("\n" + "=" * 80)
    print("All OEM Mappings:")
    print("=" * 80)
    for mapping in list_all_oem_mappings():
        print(f"\n{mapping['brand']} (pattern: {mapping['pattern']})")
        print(f"  → {mapping['oem_manufacturer']}")
        print(f"  Series: {mapping['series_name']}")
        print(f"  Applies to: {', '.join(mapping['applies_to'])}")
