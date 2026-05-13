import pytest

from config.oem_mappings import get_effective_manufacturer, get_oem_info, get_oem_manufacturer


@pytest.mark.parametrize(
    "brand, series, purpose, expected",
    [
        ("Konica Minolta", "5000i", "error_codes", "Brother"),
        ("Konica Minolta", "4000i", "parts", "Brother"),
        ("Lexmark", "CS943", "error_codes", "Konica Minolta"),
        ("Xerox", "VersaLink C405", "error_codes", "Lexmark"),
        ("UTAX", "P-4020", "parts", "Kyocera"),
        ("HP", "LaserJet MFP E87750", "error_codes", "Samsung"),
    ],
)
def test_get_oem_manufacturer_returns_expected_brand(brand, series, purpose, expected):
    assert get_oem_manufacturer(brand, series, purpose) == expected


@pytest.mark.parametrize(
    "brand, series, purpose",
    [
        ("Konica Minolta", "5000i", "error_codes"),
        ("Lexmark", "CS943", "parts"),
        ("Xerox", "VersaLink C405", "error_codes"),
        ("UTAX", "P-4020", "accessories"),
        ("HP", "LaserJet MFP E87750", "parts"),
    ],
)
def test_get_effective_manufacturer_matches_oem_mapping(brand, series, purpose):
    effective = get_effective_manufacturer(brand, series, purpose)
    oem = get_oem_manufacturer(brand, series, purpose)
    if oem:
        assert effective == oem
    else:
        assert effective == brand


@pytest.mark.parametrize(
    "brand, series, expected_oem",
    [
        ("Konica Minolta", "5000i", "Brother"),
        ("Lexmark", "MX622", "Konica Minolta"),
        ("Xerox", "VersaLink C405", "Lexmark"),
        ("UTAX", "P-4020", "Kyocera"),
        ("HP", "LaserJet MFP E87750", "Samsung"),
    ],
)
def test_get_oem_info_contains_expected_details(brand, series, expected_oem):
    info = get_oem_info(brand, series)
    assert info is not None
    assert info["oem_manufacturer"] == expected_oem
    assert "series_name" in info
    assert "applies_to" in info
