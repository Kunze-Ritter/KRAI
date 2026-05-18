"""
Accessory/Option Detection System
Detects accessories, options, and consumables and links them to compatible products
"""

import re
from dataclasses import dataclass


@dataclass
class AccessoryMatch:
    """Detected accessory information"""

    model_number: str
    accessory_type: str
    product_type: str
    series_name: str
    description: str
    compatible_series: list[str] = None

    def to_dict(self) -> dict:
        return {
            "model_number": self.model_number,
            "accessory_type": self.accessory_type,
            "product_type": self.product_type,
            "series_name": self.series_name,
            "description": self.description,
            "compatible_series": self.compatible_series or [],
        }


def detect_konica_minolta_accessory(model_number: str) -> AccessoryMatch | None:
    """
    Detect Konica Minolta accessories/options

    Args:
        model_number: Model number to check (e.g., "DF-628", "FS-534", "TN-512")

    Returns:
        AccessoryMatch if detected, None otherwise
    """
    model = model_number.upper().strip()

    # Remove common prefixes
    model_clean = re.sub(r"^(?:KONICA\s+MINOLTA\s+)?", "", model).strip()

    # ===== FINISHING & DOCUMENT FEEDER =====

    # DF-* : Duplex Document Feeder
    match = re.match(r"^DF-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="document_feeder",
            product_type="document_feeder",
            series_name="DF Series",
            description=f"Konica Minolta {model_clean} Duplex Automatic Document Feeder",
            compatible_series=["bizhub"],  # Compatible with bizhub series
        )

    # LU-* : Large Capacity Unit
    match = re.match(r"^LU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="large_capacity_feeder",
            product_type="large_capacity_feeder",
            series_name="LU Series",
            description=f"Konica Minolta {model_clean} Large Capacity Paper Feeder",
            compatible_series=["bizhub"],
        )

    # FS-* : Finisher (Stapling, Booklet, etc.)
    match = re.match(r"^FS-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="finisher",
            product_type="finisher",
            series_name="FS Series",
            description=f"Konica Minolta {model_clean} Finisher (Stapling/Booklet)",
            compatible_series=["bizhub"],
        )

    # SD-* : Saddle Stitcher Module (Upgrade Module for Finishers)
    # SD-511 → FS-534, FS-536
    # SD-512 → FS-537
    # SD-513 → AccurioPress (standalone)
    match = re.match(r"^SD-(\d{3})$", model_clean)
    if match:
        # Determine compatible finishers based on model
        sd_number = match.group(1)
        if sd_number == "511":
            compat_note = "Compatible with FS-534, FS-536"
        elif sd_number == "512":
            compat_note = "Compatible with FS-537"
        elif sd_number == "513":
            compat_note = "For AccurioPress (standalone system)"
        else:
            compat_note = "Saddle Stitcher upgrade module"

        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="saddle_stitcher",
            product_type="finisher_accessory",
            series_name="SD Series",
            description=f"Konica Minolta {model_clean} Saddle Stitcher Module - {compat_note}",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # PK-* : Punch Kit (Finisher Accessory)
    match = re.match(r"^PK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="punch_kit",
            product_type="finisher_accessory",
            series_name="PK Series",
            description=f"Konica Minolta {model_clean} Hole Punch Kit (Finisher Accessory)",
            compatible_series=["bizhub"],
        )

    # PH-* : Punch Hole Unit
    match = re.match(r"^PH-(\d{3,4}[A-Z]?)$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="punch_finisher",
            product_type="punch_finisher",
            series_name="PH Series",
            description=f"Konica Minolta {model_clean} Punch Hole Unit",
            compatible_series=["bizhub"],
        )

    # ZU-* : Z-Fold Unit (ZU-609)
    match = re.match(r"^ZU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="z_fold_unit",
            product_type="z_fold_unit",
            series_name="ZU Series",
            description=f"Konica Minolta {model_clean} Z-Fold Unit",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # ZF-* : Z-Fold Unit (legacy)
    match = re.match(r"^ZF-(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="z_fold_unit",
            product_type="z_fold_unit",
            series_name="ZF Series",
            description=f"Konica Minolta {model_clean} Z-Fold Unit",
            compatible_series=["bizhub"],
        )

    # TU-* : Trimmer Unit (TU-503)
    match = re.match(r"^TU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="trimmer",
            product_type="trimmer",
            series_name="TU Series",
            description=f"Konica Minolta {model_clean} Trimmer Unit",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # PI-* : Post Inserter (PI-507)
    match = re.match(r"^PI-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="post_inserter",
            product_type="post_inserter",
            series_name="PI Series",
            description=f"Konica Minolta {model_clean} Post Inserter",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # JS-* : Job Separator (JS-602)
    match = re.match(r"^JS-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="job_separator",
            product_type="job_separator",
            series_name="JS Series",
            description=f"Konica Minolta {model_clean} Job Separator",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # CR-* : Creaser (CR-101)
    match = re.match(r"^CR-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="creaser",
            product_type="creaser",
            series_name="CR Series",
            description=f"Konica Minolta {model_clean} Creaser",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # FD-* : Folding Unit (FD-503, FD-504)
    match = re.match(r"^FD-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="folding_unit",
            product_type="folding_unit",
            series_name="FD Series",
            description=f"Konica Minolta {model_clean} Folding Unit",
            compatible_series=["bizhub", "AccurioPress"],
        )

    # BF-* : Banner Feeder
    match = re.match(r"^BF-(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="banner_feeder",
            product_type="banner_feeder",
            series_name="BF Series",
            description=f"Konica Minolta {model_clean} Banner Feeder",
            compatible_series=["bizhub"],
        )

    # AK-* : Auto Keycard Reader / Authentication Kit
    match = re.match(r"^AK-?(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="authentication_kit",
            product_type="authentication_kit",
            series_name="AK Series",
            description=f"Konica Minolta {model_clean} Auto Keycard Reader/Authentication Kit",
            compatible_series=["bizhub"],
        )

    # JS-* : Job Separator
    match = re.match(r"^JS-?(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="job_separator",
            product_type="job_separator",
            series_name="JS Series",
            description=f"Konica Minolta {model_clean} Job Separator",
            compatible_series=["bizhub"],
        )

    # IS-* : Inner Shift Tray / Inner Finisher
    match = re.match(r"^IS-(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="inner_finisher",
            product_type="inner_finisher",
            series_name="IS Series",
            description=f"Konica Minolta {model_clean} Inner Shift Tray/Finisher",
            compatible_series=["bizhub"],
        )

    # DP-* : Document Processor (NOT Document Feeder!)
    match = re.match(r"^DP-(\d{3,4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="document_processor",
            product_type="document_processor",
            series_name="DP Series",
            description=f"Konica Minolta {model_clean} Document Processor",
            compatible_series=["bizhub"],
        )

    # ===== PAPER FEEDERS/CASSETTES =====

    # PC-* : Paper Feed Unit/Cassette
    match = re.match(r"^PC-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="paper_feeder",
            product_type="paper_feeder",
            series_name="PC Series",
            description=f"Konica Minolta {model_clean} Paper Feed Unit/Cassette",
            compatible_series=["bizhub"],
        )

    # PF-* : Paper Tray/Cassette
    match = re.match(r"^PF-P(\d{2})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="paper_feeder",
            product_type="paper_feeder",
            series_name="PF Series",
            description=f"Konica Minolta {model_clean} Paper Tray/Cassette",
            compatible_series=["bizhub"],
        )

    # MT-* : Mailbox/Sorter
    match = re.match(r"^MT-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="mailbox",
            product_type="mailbox",
            series_name="MT Series",
            description=f"Konica Minolta {model_clean} Mailbox/Sorter",
            compatible_series=["bizhub"],
        )

    # ===== FAX & CONNECTIVITY =====

    # FK-* : Fax Kit
    match = re.match(r"^FK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="fax_kit",
            product_type="fax_kit",
            series_name="FK Series",
            description=f"Konica Minolta {model_clean} Fax Expansion Kit",
            compatible_series=["bizhub"],
        )

    # MK-* : Mounting Kit/Installation Kit
    match = re.match(r"^MK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="accessory",
            product_type="accessory",
            series_name="MK Series",
            description=f"Konica Minolta {model_clean} Mounting/Installation Kit",
            compatible_series=["bizhub"],
        )

    # RU-* : Relay Unit (Finisher Accessory - Required Bridge)
    match = re.match(r"^RU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="relay_unit",
            product_type="finisher_accessory",
            series_name="RU Series",
            description=f"Konica Minolta {model_clean} Relay Unit (Required Bridge for Finisher)",
            compatible_series=["bizhub"],
        )

    # CU-* : Cleaning Unit
    match = re.match(r"^CU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="maintenance_kit",
            product_type="maintenance_kit",
            series_name="CU Series",
            description=f"Konica Minolta {model_clean} Cleaning Unit",
            compatible_series=["bizhub"],
        )

    # ===== MEMORY, HDD, WIRELESS =====

    # HD-* : Hard Disk Drive
    match = re.match(r"^HD-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="hard_drive",
            product_type="hard_drive",
            series_name="HD Series",
            description=f"Konica Minolta {model_clean} Hard Disk Drive",
            compatible_series=["bizhub"],
        )

    # EK-* : Card Reader/Authentication Kit
    match = re.match(r"^EK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="card_reader",
            product_type="card_reader",
            series_name="EK Series",
            description=f"Konica Minolta {model_clean} Card Reader/Authentication Kit",
            compatible_series=["bizhub"],
        )

    # ===== IMAGE CONTROLLERS & VIDEO INTERFACE =====

    # IC-* : Image Controller / Digital Front End (DFE)
    match = re.match(r"^IC-(\d{3}[A-Z]?)$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="image_controller",
            product_type="image_controller",
            series_name="IC Series",
            description=f"Konica Minolta {model_clean} Image Controller / Digital Front End (DFE)",
            compatible_series=["AccurioPress", "bizhub PRESS", "bizhub"],
        )

    # MIC-* : Image Controller (Fiery for B/W systems)
    match = re.match(r"^MIC-(\d{4})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="image_controller",
            product_type="image_controller",
            series_name="MIC Series",
            description=f"Konica Minolta {model_clean} Image Controller (Fiery for B/W Production)",
            compatible_series=["AccurioPress"],
        )

    # VI-* : Video Interface Kit (Controller Accessory)
    match = re.match(r"^VI-(\d{3}[A-Z]?)$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="video_interface",
            product_type="controller_accessory",
            series_name="VI Series",
            description=f"Konica Minolta {model_clean} Video Interface Kit (Required Bridge for Image Controller)",
            compatible_series=["AccurioPress", "bizhub PRESS"],
        )

    # ===== CONSUMABLES =====

    # WT-* : Waste Toner Box
    match = re.match(r"^WT-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="waste_toner_box",
            product_type="waste_toner_box",
            series_name="WT Series",
            description=f"Konica Minolta {model_clean} Waste Toner Container",
            compatible_series=["bizhub"],
        )

    # AU-* : Authentication Module
    match = re.match(r"^AU-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="card_reader",
            product_type="card_reader",
            series_name="AU Series",
            description=f"Konica Minolta {model_clean} Authentication Module (e.g., Fingerprint)",
            compatible_series=["bizhub"],
        )

    # UK-* : USB Kit
    match = re.match(r"^UK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="interface_kit",
            product_type="interface_kit",
            series_name="UK Series",
            description=f"Konica Minolta {model_clean} USB Interface Kit",
            compatible_series=["bizhub"],
        )

    # ===== TONER/INK & CONSUMABLES =====

    # TN-* : Toner Cartridge
    match = re.match(r"^TN-(\d{3})([A-Z]?)$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="toner_cartridge",
            product_type="toner_cartridge",
            series_name="TN Series",
            description=f"Konica Minolta {model_clean} Toner Cartridge",
            compatible_series=["bizhub"],
        )

    # DR-* : Drum Unit
    match = re.match(r"^DR-(\d{3})([A-Z]?)$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="drum_unit",
            product_type="drum_unit",
            series_name="DR Series",
            description=f"Konica Minolta {model_clean} Drum/Imaging Unit",
            compatible_series=["bizhub"],
        )

    # SK-* : Staples (Finisher Accessory - Consumable)
    match = re.match(r"^SK-(\d{3})$", model_clean)
    if match:
        return AccessoryMatch(
            model_number=model_clean,
            accessory_type="staple_cartridge",
            product_type="finisher_accessory",
            series_name="SK Series",
            description=f"Konica Minolta {model_clean} Staple Cartridge (Finisher Accessory)",
            compatible_series=["bizhub"],
        )

    return None


def detect_accessory(model_number: str, manufacturer: str = None) -> AccessoryMatch | None:
    """
    Main accessory detection function

    Args:
        model_number: Model number to check
        manufacturer: Manufacturer name (optional, helps with detection)

    Returns:
        AccessoryMatch if detected, None otherwise
    """
    if not model_number:
        return None

    # Normalize manufacturer
    if manufacturer:
        manufacturer_lower = manufacturer.lower().strip()
    else:
        manufacturer_lower = ""

    # Konica Minolta accessories
    if "konica" in manufacturer_lower or "minolta" in manufacturer_lower or not manufacturer:
        result = detect_konica_minolta_accessory(model_number)
        if result:
            return result

    # TODO: Add other manufacturers' accessories here
    # - HP accessories
    # - Xerox accessories
    # - Ricoh accessories
    # etc.

    return None
