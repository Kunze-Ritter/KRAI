"""Product Type Mapper

Maps series names to product types.
"""

import re

# Series to Product Type mapping
# Valid values: See migration 48_expand_product_type_values.sql
SERIES_PRODUCT_TYPE_MAP = {
    # Konica Minolta
    "AccurioPress": "laser_production_printer",
    "AccurioPrint": "laser_production_printer",
    "AccurioLabel": "laser_production_printer",
    "AccurioJet": "inkjet_production_printer",
    "Revoria": "laser_production_printer",
    "bizhub": "laser_multifunction",
    "bizhub PRESS": "laser_production_printer",
    # HP - Laser (Toner)
    "LaserJet": "laser_printer",
    "LaserJet Pro": "laser_printer",
    "LaserJet Pro MFP": "laser_multifunction",
    "LaserJet Enterprise": "laser_printer",
    "LaserJet Enterprise MFP": "laser_multifunction",
    "LaserJet Managed": "laser_printer",
    "Color LaserJet": "laser_printer",
    "Color LaserJet Pro": "laser_printer",
    "Color LaserJet Pro MFP": "laser_multifunction",
    "Color LaserJet Enterprise": "laser_printer",
    "Laser MFP": "laser_multifunction",
    # HP - Inkjet (Tinte)
    "DeskJet": "inkjet_printer",
    "DeskJet Plus": "inkjet_multifunction",
    "ENVY": "inkjet_multifunction",
    "ENVY Inspire": "inkjet_multifunction",
    "ENVY Photo": "inkjet_multifunction",
    "Smart Tank": "inkjet_printer",
    "Smart Tank Plus": "inkjet_multifunction",
    "OfficeJet": "inkjet_multifunction",
    "OfficeJet Pro": "inkjet_multifunction",
    "PageWide": "inkjet_multifunction",
    "PageWide Pro": "inkjet_multifunction",
    "PageWide Enterprise": "inkjet_multifunction",
    # HP - Production & Plotter
    "DesignJet": "inkjet_plotter",
    "Latex": "latex_plotter",
    "Indigo Digital Press": "laser_production_printer",
    "Scitex": "inkjet_production_printer",
    "PageWide XL": "inkjet_production_printer",
    # Canon - MFP/Printer
    "imageRUNNER": "laser_multifunction",
    "imageRUNNER ADVANCE": "laser_multifunction",
    "imageRUNNER ADVANCE DX": "laser_multifunction",
    "i-SENSYS": "laser_printer",
    "i-SENSYS MF": "laser_multifunction",
    # Canon - Production
    "imagePRESS": "laser_production_printer",
    "imagePRESS C": "laser_production_printer",
    "varioPRINT": "laser_production_printer",
    # Canon - Plotter
    "imagePROGRAF": "inkjet_plotter",
    "imagePROGRAF PRO": "inkjet_plotter",
    "imagePROGRAF TX": "inkjet_plotter",
    "imagePROGRAF TM": "inkjet_plotter",
    "imagePROGRAF TA": "inkjet_plotter",
    "imagePROGRAF iPF": "inkjet_plotter",
    # Xerox - Production
    "Iridesse Production Press": "laser_production_printer",
    "Color Press": "laser_production_printer",
    "Versant": "laser_production_printer",
    "iGen": "laser_production_printer",
    "PrimeLink": "laser_production_printer",
    # Xerox - MFP
    "AltaLink": "laser_multifunction",
    "VersaLink": "laser_multifunction",
    "WorkCentre": "laser_multifunction",
    "ColorQube": "solid_ink_multifunction",
    "DocuCentre": "laser_multifunction",
    # Xerox - Printer
    "Phaser": "laser_printer",
    "DocuPrint": "laser_printer",
    # Xerox - Wide Format
    "Wide Format": "inkjet_plotter",
    # Ricoh - Production
    "Pro C": "laser_production_printer",
    "Pro VC": "inkjet_production_printer",
    "Pro 8": "laser_production_printer",
    # Ricoh - MFP
    "IM C": "laser_multifunction",
    "IM": "laser_multifunction",
    "IM CW": "inkjet_plotter",
    "MP C": "laser_multifunction",
    "MP": "laser_multifunction",
    "MP W": "inkjet_plotter",
    "Aficio MP C": "laser_multifunction",
    "Aficio MP": "laser_multifunction",
    # Ricoh - Printer
    "SP C": "laser_printer",
    "SP": "laser_printer",
    "P C": "laser_printer",
    "P": "laser_printer",
    "Aficio SG": "inkjet_printer",
    # Brother - Production (DTG - Direct to Garment)
    "GTXpro": "inkjet_production_printer",
    "GTX": "inkjet_production_printer",
    # Brother - Specialty
    "PL Series": "inkjet_plotter",
    "ScanNCut": "accessory",
    # Brother - Inkjet MFP
    "MFC-J": "inkjet_multifunction",
    "DCP-J": "inkjet_multifunction",
    # Brother - Laser MFP
    "MFC-L": "laser_multifunction",
    "DCP-L": "laser_multifunction",
    # Brother - Printer
    "HL-L": "laser_printer",
    # Brother - Fax/Mobile
    "IntelliFax": "laser_multifunction",
    "PJ Series": "inkjet_printer",
    # Lexmark - MFP (multifunction)
    "MX Series": "laser_multifunction",
    "CX Series": "laser_multifunction",
    "XC Series": "laser_multifunction",
    "XM Series": "laser_multifunction",
    "MB Series": "laser_multifunction",
    "MC Series": "laser_multifunction",
    # Lexmark - Printer
    "MS Series": "laser_printer",
    "CS Series": "laser_printer",
    "B Series": "laser_printer",
    "C Series": "laser_printer",
    # Lexmark - Production
    "Enterprise Production": "laser_production_printer",
    "Enterprise Color": "laser_multifunction",
    # Lexmark - Legacy
    "Interpret S400 Series": "inkjet_printer",
    "Plus Matrix Series": "dot_matrix_printer",
    # Kyocera - Production
    "TASKalfa Pro": "laser_production_printer",
    # Kyocera - MFP
    "TASKalfa": "laser_multifunction",
    "ECOSYS M": "laser_multifunction",
    "ECOSYS MA": "laser_multifunction",
    "FS-Series MFP": "laser_multifunction",
    "KM-Series": "laser_multifunction",
    # Kyocera - Printer
    "ECOSYS": "laser_printer",
    "ECOSYS P": "laser_printer",
    "ECOSYS PA": "laser_printer",
    "FS-Series": "laser_printer",
    "TC-Series": "laser_printer",
    "F-Series": "laser_printer",
    "DC-Series": "laser_printer",
    "DP-Series": "laser_printer",
    # UTAX (TA Triumph-Adler) - MFP
    "P-Series MFP": "laser_multifunction",
    "CDC Series": "laser_multifunction",
    "2506ci": "laser_multifunction",
    "3206ci": "laser_multifunction",
    "4006ci": "laser_multifunction",
    "5006ci": "laser_multifunction",
    "6006ci": "laser_multifunction",
    "7006ci": "laser_multifunction",
    "8006ci": "laser_multifunction",
    # UTAX - Printer
    "P-Series": "laser_printer",
    "LP-Series": "laser_printer",
    "CDP Series": "laser_printer",
    "CD Series": "laser_printer",
    # Epson - Production
    "SureColor Production": "inkjet_production_printer",
    "SureColor F": "inkjet_production_printer",
    "Monna Lisa": "inkjet_production_printer",
    "SureLab": "dye_sublimation_printer",
    "Stylus Pro": "inkjet_plotter",
    # Epson - Professional
    "SureColor P": "inkjet_plotter",
    # Epson - MFP
    "WorkForce Enterprise": "inkjet_multifunction",
    "WorkForce Pro": "inkjet_multifunction",
    "WorkForce": "inkjet_multifunction",
    "EcoTank": "inkjet_multifunction",
    "Expression Home": "inkjet_multifunction",
    # Epson - Printer
    "Expression Photo": "inkjet_printer",
    "Stylus Photo": "inkjet_printer",
    "Stylus": "inkjet_printer",
    # Epson - Legacy
    "MJ Series": "dot_matrix_printer",
    "MX Series": "inkjet_printer",  # noqa: F601
    "MP Series": "inkjet_printer",
    "P Series": "inkjet_printer",
    # OKI - Production
    "Pro9": "laser_production_printer",
    "Pro10": "laser_production_printer",
    "B Series MFP": "laser_multifunction",
    "ES Series MFP": "laser_multifunction",
    "ES Series": "laser_printer",
    # Fujifilm - Production
    "Revoria Press": "laser_production_printer",
    "JetPress": "inkjet_production_printer",
    "ApeosPro": "laser_production_printer",
    # Fujifilm - MFP
    "ApeosPort-VII": "laser_multifunction",
    "ApeosPort": "laser_multifunction",
    "Apeos": "laser_multifunction",
    # Fujifilm - Printer
    "ApeosPrint": "laser_printer",
    # Fujifilm - Photo
    "INSTAX mini Link": "dye_sublimation_printer",
    "INSTAX SQUARE Link": "dye_sublimation_printer",
    "INSTAX Link Wide": "dye_sublimation_printer",
    "INSTAX": "dye_sublimation_printer",
    # Sharp - Production
    "BP Pro": "laser_production_printer",
    "MX Production": "laser_production_printer",
    # Sharp - MFP
    "BP Series": "laser_multifunction",
    "MX-B": "laser_multifunction",
    "MX-C": "laser_multifunction",
    "AR Series": "laser_multifunction",
    # Sharp - Printer
    "BP Printer": "laser_printer",
    "MX-B Printer": "laser_printer",
    "MX-C Printer": "laser_printer",
    "AL Series": "laser_printer",
    # Toshiba - Production
    "e-STUDIO Production": "laser_production_printer",
    # Toshiba - MFP
    "e-STUDIO": "laser_multifunction",
    "e-STUDIO Hybrid": "laser_multifunction",
    # Toshiba - Legacy
    "Pagelaser": "laser_printer",
    "PAL Series": "laser_printer",
    "Spot Series": "laser_printer",
    "T Series": "laser_printer",
    "TF Series": "laser_printer",
    "TF-P Series": "laser_printer",
}


def get_product_type(series_name: str, model_pattern: str | None = None, model_number: str | None = None) -> str | None:
    """
    Get product type based on series name and model pattern

    Args:
        series_name: Series name (e.g., "LaserJet", "bizhub")
        model_pattern: Technical pattern (e.g., "C5xx", "M4xx")
        model_number: Full model number (e.g., "C558", "M479fdw")

    Returns:
        Product type or None
    """
    # Check model_number for accessory prefixes (Konica Minolta)
    if model_number:
        model_upper = model_number.upper()

        # Accessory detection by prefix
        # Updated to match Migration 107 & 110 product_type_check constraints
        accessory_prefixes = {
            # Finishers & Finisher Accessories (Migration 107)
            "FS-": "finisher",  # Finisher (FS-533, FS-534, FS-539, FS-541)
            "SD-": "saddle_finisher",  # Saddle Finisher (SD-511, SD-512, SD-513) - Migration 107
            "JS-": "stapler",  # Stapler (JS-506, JS-602) - Migration 110
            "PK-": "finisher_accessory",  # Punch Kit (PK-519, PK-520, PK-523, PK-524, PK-526)
            "SK-": "finisher_accessory",  # Staple Cartridge (staples for finisher)
            "TR-": "finisher_accessory",  # Trimmer (cutting unit for finisher)
            "TU-": "trimmer",  # Trimmer Unit (TU-503)
            "PI-": "post_inserter",  # Post Inserter (PI-507) - Migration 107
            "ZU-": "z_fold_unit",  # Z-Fold Unit (ZU-606, ZU-609) - Migration 107
            "CR-": "creaser",  # Creaser (CR-101, CR-102, CR-103) - Migration 107
            "FD-": "folding_unit",  # Folding Unit (FD-503, FD-504) - Migration 107
            "RU-": "relay_unit",  # Relay Unit (RU-513, RU-514, RU-519) - Migration 110
            "HT-": "punch_unit",  # Hole Punch Unit (HT-506, HT-509) - Migration 110
            # Paper Handling
            "PF-": "paper_feeder",  # Paper Feeder (PF-709, PF-710)
            "PC-": "cabinet",  # Paper Cabinet (PC-118, PC-218, PC-418)
            "DK-": "cabinet",  # Desk/Cabinet (DK-518)
            "MB-": "paper_feeder",  # Multi Bypass Tray (250 sheets, banner formats)
            "LU-": "large_capacity_unit",  # Large Capacity Unit (LU-204, LU-208, LU-301) - Migration 110
            "LK-": "large_capacity_unit",  # Large Capacity Unit (LK-102, LK-105, LK-110) - Migration 110
            "DF-": "document_feeder",  # Document Feeder (DF-633) - for scanning
            "EF-": "envelope_feeder",  # Envelope Feeder (EF-106, EF-107, EF-108, EF-109)
            "OT-": "output_tray",  # Output Tray (OT-506, OT-512)
            # Output & Sorting
            "MT-": "mailbox",  # Mailbox/Sorter
            # Image Controllers & Accessories (Migration 107)
            "IC-": "image_controller",  # Image Controller / Digital Front End (IC-320, IC-414)
            "MIC-": "image_controller",  # Image Controller (MIC-4160, MIC-4170 - Fiery)
            "VI-": "controller_accessory",  # Video Interface Kit (VI-506 - required bridge)
            # Controller Units (Migration 110)
            "CU-": "controller_unit",  # Controller Unit (CU-101, CU-104) - Migration 110
            "EK-": "controller_unit",  # Interface Kit (EK-608, EK-609, EK-612) - Migration 110
            "IQ-": "controller_unit",  # IQ Controller (IQ-501) - Migration 110
            # Authentication Units (Migration 110)
            "AU-": "authentication_unit",  # Authentication Unit (AU-102) - Migration 110
            "UK-": "authentication_unit",  # Card Reader (UK-209, UK-221, UK-301) - Migration 110
            # Connectivity & Interface
            "FK-": "fax_kit",  # Fax Kit
            # Storage
            "HD-": "hard_drive",  # Hard Disk Drive
            # Furniture & Support
            "MK-": "mount_kit",  # Mount Kit (MK-602, MK-603, MK-734, MK-735, MK-748)
            # Consumables & Maintenance
            "WT-": "waste_toner_box",  # Waste Toner Box (WT-515) - Migration 107
            "TN": "toner_cartridge",  # Toner Cartridge (TN328K, TN626C, TN715Y)
            "DR": "drum_unit",  # Drum Unit (DR012, DR316K, DR618C)
            "DV": "developer_unit",  # Developer Unit (DV012, DV315C, DV621K)
            # Sensors
            "IM-": "media_sensor",  # Intelligent Media Sensor (IM-101 - paper weight/thickness)
        }

        # Special case: Cxxxxx pattern for Konica Minolta AccurioPrint (C10500, C12010, C14010)
        # These are production printers (AccurioPrint series)
        if re.match(r"^C\d{5}[A-Z]{0,2}$", model_upper):
            return "laser_production_printer"

        for prefix, accessory_type in accessory_prefixes.items():
            if model_upper.startswith(prefix):
                return accessory_type

    # If no series_name, try to infer from model_number
    if not series_name and model_number:
        model_upper = model_number.upper()
        # Common patterns in model numbers
        if "PRESS" in model_upper or "ACCURIO" in model_upper:
            return "laser_production_printer"
        if "LASERJET" in model_upper:
            if "MFP" in model_upper or "M" in model_upper[:3]:
                return "laser_multifunction"
            return "laser_printer"
        # Default if we can't determine
        return "laser_multifunction"

    if not series_name:
        return None

    series_lower = series_name.lower()

    # Special handling for bizhub (depends on model)
    if "bizhub" in series_lower:
        # Check model number or pattern for specific types
        check_str = (model_number or model_pattern or "").upper()

        # bizhub PRESS/PRO = production_printer
        if "PRESS" in series_name or "PRO" in series_name:
            return "production_printer"

        # Printer-only models (4020, 4050, 4750, C3300i, C4000i)
        if any(x in check_str for x in ["4020", "4050", "4750", "C3300", "C4000"]):
            return "laser_printer"

        # Everything else is MFP
        return "laser_multifunction"

    # Direct match
    if series_name in SERIES_PRODUCT_TYPE_MAP:
        return SERIES_PRODUCT_TYPE_MAP[series_name]

    # Partial match (for variations)
    for key, value in SERIES_PRODUCT_TYPE_MAP.items():
        if key.lower() in series_lower or series_lower in key.lower():
            return value

    # Default fallback (assume laser MFP for unknown models)
    return "laser_multifunction"


if __name__ == "__main__":
    # Test
    test_cases = ["LaserJet", "bizhub", "AccurioPress", "DesignJet", "imageRUNNER ADVANCE", "Phaser"]

    print("Product Type Mapping Tests:")
    print("=" * 60)
    for series in test_cases:
        product_type = get_product_type(series)
        print(f"{series:30} → {product_type}")
