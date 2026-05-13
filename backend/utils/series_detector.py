"""Product Series Detection Module

Detects product series from model numbers and names.
"""

import re


def _calculate_confidence(series_data: dict, context: str) -> float:
    """
    Calculate confidence score based on context

    Args:
        series_data: Detected series information
        context: Text context (e.g., document chunk)

    Returns:
        Confidence score 0.0-1.0
    """
    if not context:
        return 0.5  # Default confidence without context

    context_lower = context.lower()
    series_name = series_data.get("series_name", "").lower()

    confidence = 0.5  # Base confidence

    # Check if series name appears in context
    if series_name in context_lower:
        confidence += 0.3

    # Check for partial matches (e.g., "accurio" for "AccurioPress")
    series_keywords = series_name.split()
    for keyword in series_keywords:
        if len(keyword) > 3 and keyword in context_lower:
            confidence += 0.1

    # Boost confidence for specific series markers
    series_markers = {
        "laserjet": ["laserjet", "laser jet"],
        "officejet": ["officejet", "office jet"],
        "pagewide": ["pagewide", "page wide"],
        "accuriopress": ["accuriopress", "accurio press"],
        "accurioprint": ["accurioprint", "accurio print"],
        "bizhub": ["bizhub", "biz hub"],
        "imagerunner": ["imagerunner", "image runner"],
        "versalink": ["versalink", "versa link"],
        "workcentre": ["workcentre", "work centre", "workcentre"],
    }

    for series_key, markers in series_markers.items():
        if series_key in series_name.replace(" ", ""):
            for marker in markers:
                if marker in context_lower:
                    confidence += 0.2
                    break

    # Cap at 1.0
    return min(confidence, 1.0)


def detect_series(model_number: str, manufacturer_name: str, context: str = None) -> dict | None:
    """
    Detect product series from model number with optional context validation

    Args:
        model_number: Product model number (e.g., "M479fdw", "X580", "C454e")
        manufacturer_name: Manufacturer name
        context: Optional text context to validate series name (e.g., document chunk)

    Returns:
        Dict with series_name, series_code, confidence, or None
    """
    if not model_number:
        return None

    # Skip very short model numbers without context validation
    if len(model_number) < 3 and not context:
        return None

    manufacturer_lower = manufacturer_name.lower()

    # HP Series Detection
    if "hp" in manufacturer_lower or "hewlett" in manufacturer_lower or "packard" in manufacturer_lower:
        result = _detect_hp_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Canon Series Detection
    if "canon" in manufacturer_lower:
        result = _detect_canon_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Konica Minolta Series Detection
    if "konica" in manufacturer_lower or "minolta" in manufacturer_lower:
        result = _detect_konica_series(model_number)
        if result:
            if context:
                result["confidence"] = _calculate_confidence(result, context)
                # Reject low confidence matches for short model numbers or context-required patterns
                if (len(model_number) <= 3 or result.get("requires_context", False)) and result.get(
                    "confidence", 0
                ) < 0.7:
                    return None
            elif result.get("requires_context", False):
                # Pattern requires context but none provided - reject
                return None
        return result

    # Ricoh Series Detection
    if "ricoh" in manufacturer_lower:
        result = _detect_ricoh_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Xerox Series Detection
    if "xerox" in manufacturer_lower:
        result = _detect_xerox_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Brother Series Detection
    if "brother" in manufacturer_lower:
        result = _detect_brother_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Lexmark Series Detection
    if "lexmark" in manufacturer_lower:
        result = _detect_lexmark_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Kyocera Series Detection
    if "kyocera" in manufacturer_lower:
        result = _detect_kyocera_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # UTAX Series Detection (Kyocera rebrand)
    if "utax" in manufacturer_lower or "triumph" in manufacturer_lower or "ta " in manufacturer_lower:
        result = _detect_utax_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Fujifilm Series Detection (Xerox successor in Asia/Japan)
    if "fujifilm" in manufacturer_lower or "fuji" in manufacturer_lower:
        result = _detect_fujifilm_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # OKI Series Detection
    if "oki" in manufacturer_lower:
        result = _detect_oki_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Xerox Series Detection
    if "xerox" in manufacturer_lower:
        result = _detect_xerox_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Epson Series Detection
    if "epson" in manufacturer_lower:
        result = _detect_epson_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Sharp Series Detection
    if "sharp" in manufacturer_lower:
        result = _detect_sharp_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Toshiba Series Detection
    if "toshiba" in manufacturer_lower:
        result = _detect_toshiba_series(model_number)
        if result and context:
            result["confidence"] = _calculate_confidence(result, context)
        return result

    # Generic fallback
    result = _detect_generic_series(model_number)
    if result and context:
        result["confidence"] = _calculate_confidence(result, context)
    return result


def _detect_hp_series(model_number: str) -> dict | None:
    """Detect HP series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:HP\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production & Large Format =====

    # HP Indigo Digital Press (12000 HD, 7900, 7K, 6K, 100K)
    if re.match(r"^INDIGO\s+(\d+K?|HD|\d+\s+HD)", model_clean):
        return {
            "series_name": "Indigo Digital Press",
            "model_pattern": "Indigo",
            "series_description": "HP Indigo digital production press",
        }

    # HP Latex Production (115, 315, 335, 365, 570, 800, 630, 730, 830, R530, FS50, FS60)
    match = re.match(r"^LATEX\s+([RF]?S?\d{2,3})$", model_clean)
    if match:
        return {"series_name": "Latex", "model_pattern": "Latex", "series_description": "HP Latex production printer"}

    # DesignJet Large Format (T650, T730, Z6, Z9+)
    match = re.match(r"^DESIGNJET\s+([TZ]\d+\+?)$", model_clean)
    if match:
        series = match.group(1)[0]  # T or Z
        return {
            "series_name": "DesignJet",
            "model_pattern": f"DesignJet {series}",
            "series_description": f"HP DesignJet {series} series large format printer",
        }

    # ===== PRIORITY 2: Inkjet Series =====

    # Smart Tank / Smart Tank Plus (5105, 570, 615)
    if re.match(r"^SMART\s+TANK(\s+PLUS)?\s+\d{3,4}$", model_clean):
        if "PLUS" in model_clean:
            return {
                "series_name": "Smart Tank Plus",
                "model_pattern": "Smart Tank Plus",
                "series_description": "HP Smart Tank Plus refillable ink tank printer",
            }
        return {
            "series_name": "Smart Tank",
            "model_pattern": "Smart Tank",
            "series_description": "HP Smart Tank refillable ink tank printer",
        }

    # ENVY Inspire (7920e)
    if re.match(r"^ENVY\s+INSPIRE\s+\d{4}E?$", model_clean):
        return {
            "series_name": "ENVY Inspire",
            "model_pattern": "ENVY Inspire",
            "series_description": "HP ENVY Inspire all-in-one inkjet printer",
        }

    # ENVY Photo (6230)
    if re.match(r"^ENVY\s+PHOTO\s+\d{4}$", model_clean):
        return {
            "series_name": "ENVY Photo",
            "model_pattern": "ENVY Photo",
            "series_description": "HP ENVY Photo all-in-one inkjet printer",
        }

    # ENVY (6020)
    if re.match(r"^ENVY\s+\d{4}$", model_clean):
        return {
            "series_name": "ENVY",
            "model_pattern": "ENVY",
            "series_description": "HP ENVY all-in-one inkjet printer",
        }

    # DeskJet Plus (4120)
    if re.match(r"^DESKJET\s+PLUS\s+\d{4}$", model_clean):
        return {
            "series_name": "DeskJet Plus",
            "model_pattern": "DeskJet Plus",
            "series_description": "HP DeskJet Plus all-in-one inkjet printer",
        }

    # DeskJet (3760)
    if re.match(r"^DESKJET\s+\d{4}$", model_clean):
        return {"series_name": "DeskJet", "model_pattern": "DeskJet", "series_description": "HP DeskJet inkjet printer"}

    # OfficeJet Pro (9020, 7740, 7740 Wide Format)
    match = re.match(r"^(?:OFFICEJET\s+)?PRO\s+(\d{4})(?:\s+WIDE\s+FORMAT)?$", model_clean)
    if match:
        return {
            "series_name": "OfficeJet Pro",
            "model_pattern": "OfficeJet Pro",
            "series_description": "HP OfficeJet Pro inkjet all-in-one",
        }

    # OfficeJet (6950)
    if re.match(r"^OFFICEJET\s+\d{4}$", model_clean):
        return {
            "series_name": "OfficeJet",
            "model_pattern": "OfficeJet",
            "series_description": "HP OfficeJet inkjet all-in-one",
        }

    # PageWide Pro (352dw, 477dw, 577dw, 7740)
    match = re.match(r"^PAGEWIDE\s+PRO\s+(\d{3,4})[A-Z]{0,3}$", model_clean)
    if match:
        return {
            "series_name": "PageWide Pro",
            "model_pattern": "PageWide Pro",
            "series_description": "HP PageWide Pro business inkjet printer",
        }

    # PageWide (352dw)
    match = re.match(r"^PAGEWIDE\s+(\d{3})[A-Z]{0,3}$", model_clean)
    if match:
        return {
            "series_name": "PageWide",
            "model_pattern": "PageWide",
            "series_description": "HP PageWide inkjet printer",
        }

    # ===== PRIORITY 3: LaserJet Enterprise =====

    # LaserJet Enterprise MFP (M634h, M725)
    match = re.match(r"^(?:LASERJET\s+)?ENTERPRISE\s+MFP\s+M(\d{3,4})[A-Z]?$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "LaserJet Enterprise MFP",
            "model_pattern": f"M{series_num[0]}xx",
            "series_description": f"HP LaserJet Enterprise MFP M{series_num[0]}xx series",
        }

    # LaserJet Enterprise (M506, M607, M611, M632, M635)
    match = re.match(r"^(?:LASERJET\s+)?ENTERPRISE\s+M(\d{3})$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "LaserJet Enterprise",
            "model_pattern": f"M{series_num[0]}xx",
            "series_description": f"HP LaserJet Enterprise M{series_num[0]}xx series",
        }

    # ===== PRIORITY 4: Color LaserJet Pro MFP =====

    # Color LaserJet Pro MFP (M255dw, M283fdw, M452nw, M454dn, M479fdn, M479fdw, M281fdw)
    match = re.match(r"^(?:COLOR\s+LASERJET\s+PRO\s+)?MFP\s+M(\d{3,4})[A-Z]{0,5}$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "Color LaserJet Pro MFP",
            "model_pattern": f"M{series_num[0]}xx",
            "series_description": f"HP Color LaserJet Pro MFP M{series_num[0]}xx series",
        }

    # ===== PRIORITY 5: LaserJet Pro MFP =====

    # LaserJet Pro MFP (M28w, M130fn, M148fdw, M2727nf, M428fdn, M428fdw, M429fdn)
    match = re.match(r"^(?:LASERJET\s+PRO\s+)?MFP\s+M(\d{2,4})[A-Z]{0,5}$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "LaserJet Pro MFP",
            "model_pattern": f"M{series_num[0]}xx" if len(series_num) >= 3 else f"M{series_num}",
            "series_description": f"HP LaserJet Pro MFP M{series_num[0]}xx series",
        }

    # ===== PRIORITY 6: Laser MFP (Compact) =====

    # Laser MFP (131, 133, 135, 137, 135a, 137fnw)
    match = re.match(r"^LASER\s+MFP\s+1(\d{2})[A-Z]{0,5}$", model_clean)
    if match:
        return {
            "series_name": "Laser MFP",
            "model_pattern": "1xx",
            "series_description": "HP Laser MFP 1xx series compact multifunction printer",
        }

    # ===== PRIORITY 7: LaserJet Pro (Single Function) =====

    # LaserJet Pro M series (M15w, M28w, M102w, M130fn, M404dn, M428fdw, M521dn)
    match = re.match(r"^(?:LASERJET\s+PRO\s+)?M(\d{2,3})[A-Z]{0,5}$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "LaserJet Pro",
            "model_pattern": f"M{series_num[0]}xx" if len(series_num) >= 3 else f"M{series_num}",
            "series_description": f"HP LaserJet Pro M{series_num[0]}xx series",
        }

    # ===== PRIORITY 8: Legacy Patterns =====

    # LaserJet E series (E50045, E50145, E52545, etc.)
    match = re.match(r"^E(\d)(\d{2})", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "LaserJet Enterprise",
            "model_pattern": f"E{series_digit}xxxx",
            "series_description": f"HP LaserJet Enterprise E{series_digit}0000 series",
        }

    # OfficeJet Pro X series (X580, X585, etc.)
    match = re.match(r"^X(\d)(\d{2})", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "OfficeJet Pro",
            "model_pattern": f"X{series_digit}xx",
            "series_description": f"HP OfficeJet Pro X{series_digit}00 series",
        }

    # PageWide series (P77960, P55250, etc.)
    match = re.match(r"^P(\d)(\d{4})", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "PageWide",
            "model_pattern": f"P{series_digit}xxxx",
            "series_description": f"HP PageWide P{series_digit} series",
        }

    # Color LaserJet series (CP5225, CP4525, etc.)
    match = re.match(r"^CP(\d{2})", model_clean)
    if match:
        return {
            "series_name": "Color LaserJet",
            "model_pattern": f"CP{match.group(1)}xx",
            "series_description": f"HP Color LaserJet CP{match.group(1)} series",
        }

    return None


def _detect_canon_series(model_number: str) -> dict | None:
    """Detect Canon series - Returns marketing name + technical pattern"""
    model = model_number.upper()

    # imageRUNNER ADVANCE C series (C5560i, C5550i, etc.)
    match = re.match(r"C(\d{2})\d{2}", model)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "imageRUNNER ADVANCE",  # Marketing name
            "model_pattern": f"C{series_digit}xx",  # Technical pattern
            "series_description": f"Canon imageRUNNER ADVANCE C{series_digit} series",
        }

    # imageRUNNER series (iR2530, iR2545, etc.)
    match = re.match(r"(?:IR)?(\d{2})\d{2}", model)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "imageRUNNER",  # Marketing name
            "model_pattern": f"{series_digit}xx",  # Technical pattern
            "series_description": f"Canon imageRUNNER {series_digit} series",
        }

    return None


def _detect_konica_series(model_number: str) -> dict | None:
    """Detect Konica Minolta series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common suffixes for pattern matching
    model_clean = re.sub(r"(?:SERIES|MFP)$", "", model).strip()

    # ===== PRIORITY 1: BIG Kiss (Special naming) =====
    if "BIG" in model and "KISS" in model:
        return {
            "series_name": "BIG Kiss",
            "model_pattern": "BIG Kiss",
            "series_description": "Konica Minolta BIG Kiss special series",
        }

    # ===== PRIORITY 2: AccurioPrint (Production) =====
    # MUST CHECK BEFORE AccurioPress to avoid false matches!

    # C659, C759 (3 digits)
    if re.match(r"^C[67]59$", model_clean):
        return {
            "series_name": "AccurioPrint",
            "model_pattern": "Cx59",
            "series_description": "Konica Minolta AccurioPrint production color printers",
        }

    # C2060, C2070, C4065 (specific 4-digit models)
    if re.match(r"^C(2060|2070|4065)[LP]?$", model_clean):
        return {
            "series_name": "AccurioPrint",
            "model_pattern": "Cxxxx",
            "series_description": "Konica Minolta AccurioPrint production color printers",
        }

    # C10500, C12010, C14010 (5-digit models with optional suffix)
    # AccurioPrint C10500, C12010, C14010 series
    if re.match(r"^C(10500|12010|14010)[SWOX]{0,2}$", model_clean):
        return {
            "series_name": "AccurioPrint",
            "model_pattern": "Cxxxxx",
            "series_description": "Konica Minolta AccurioPrint production color printers",
        }

    # ===== PRIORITY 3: AccurioPress (High-end production) =====
    # C + 4-5 digits (C1060, C3070, C3080, C4070, C4080, C6085, C6100, C7090, C7100, C12000, C14000, C16000)
    # Also includes C74hc, C84hc (high capacity models)
    # Excludes C2060, C2070, C4065 which are AccurioPrint
    if re.match(
        r"^C(1[0246][0-9]{2,3}|3[0-9]{3}|4[0-9]{3}|6[01][0-9]{2}|70[79]0|71[0]0|[78]4hc)[LNPX]?$",
        model_clean,
        re.IGNORECASE,
    ):
        # Double-check it's not an AccurioPrint model
        if not re.match(r"^C(2060|2070|4065)[LP]?$", model_clean):
            return {
                "series_name": "AccurioPress",
                "model_pattern": "Cxxxx",
                "series_description": "Konica Minolta AccurioPress high-end production color printers",
            }

    # 4 digits without C (6100, 6120, 6136, 6136P)
    if re.match(r"^6[01][0-9]{2}P?$", model_clean):
        return {
            "series_name": "AccurioPress",
            "model_pattern": "6xxx",
            "series_description": "Konica Minolta AccurioPress high-end production printers",
        }

    # ===== PRIORITY 4: bizhub Press (Production) =====
    # C + 4 digits (C1000, C1060, C1070, C1085, C1100, C2060, C2070, C3070, C3080, C6000)
    # Note: Overlaps with AccurioPress/AccurioPrint, so comes after
    if re.match(r"^C(1[0-9]{3}|[236][0-9]{3})[DLPX]{0,2}$", model_clean):
        return {
            "series_name": "bizhub Press",
            "model_pattern": "Cxxxx",
            "series_description": "Konica Minolta bizhub Press production color printers",
        }

    # 4 digits (1052, 1200, 1250, 2250)
    if re.match(r"^(1[02][0-9]{2}|2250)[EP]?$", model_clean):
        return {
            "series_name": "bizhub Press",
            "model_pattern": "xxxx",
            "series_description": "Konica Minolta bizhub Press production printers",
        }

    # ===== PRIORITY 5: bizhub i-Series (Office/MFP) =====
    # C + 4 digits + i (C3350i, C3351i, C4050i, C4051i) - Compact Multifunction i-Series
    match = re.match(r"^C([2-9])(\d{3})i$", model_clean)
    if match:
        series_digit = match.group(1)
        speed = match.group(1) + match.group(2)[:1]  # e.g., "40" from "4050"
        return {
            "series_name": "bizhub i-Series",
            "model_pattern": f"C{series_digit}x{match.group(2)[1:]}i",
            "series_description": f"Konica Minolta bizhub i-Series compact color MFP (~{speed} ppm)",
        }

    # C + 3 digits + i (C750i, C751i, C650i, C550i, C450i) - Color Multifunction i-Series
    match = re.match(r"^C([2-9])(\d{2})i$", model_clean)
    if match:
        series_digit = match.group(1)
        speed = match.group(1) + match.group(2)[:1]  # e.g., "75" from "750"
        return {
            "series_name": "bizhub i-Series",
            "model_pattern": f"C{series_digit}x{match.group(2)[1]}i",
            "series_description": f"Konica Minolta bizhub i-Series color MFP (~{speed} ppm)",
        }

    # C + 3-4 digits + e/E/PS (C224e, C284e, C364e, C454e, C554e, C654e, C754e) - Enhanced Series (older)
    match = re.match(r"^C([2-9])(\d{2,3})([EI]|PS)$", model_clean)
    if match:
        series_digit = match.group(1)
        suffix = match.group(3).lower()
        series_type = "Enhanced" if suffix in ["e", "i"] else "Professional"
        return {
            "series_name": f"bizhub {suffix.upper()}-Series",
            "model_pattern": f"C{series_digit}xx{suffix}",
            "series_description": f"Konica Minolta bizhub {series_type} color MFPs",
        }

    # C + 3 digits (no suffix) - Generic bizhub
    match = re.match(r"^C([2-9])(\d{2})$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "bizhub",
            "model_pattern": f"C{series_digit}xx",
            "series_description": f"Konica Minolta bizhub C{series_digit}xx series color MFPs",
        }

    # 3-4 digits without C (160, 185, 195, 200, 223, 227, 250, 266, 282, 287, 306, 308, 350, 360, 420, 454e, 554e, 654e, 754e, 920, 950i, 958)
    match = re.match(r"^([1-9])(\d{2,3})([EFIPX]|RM|MFP)?$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "bizhub",
            "model_pattern": f"{series_digit}xxx",
            "series_description": f"Konica Minolta bizhub {series_digit}xxx series MFPs",
        }

    # 2 digits (20, 25, 36, 40, 42, 43)
    # NOTE: These are very short and prone to false positives!
    # Only match if there's a suffix (P, E, PX) to increase specificity
    match = re.match(r"^([2-4][0-9])([EP]|PX)$", model_clean)
    if match:
        return {
            "series_name": "bizhub",
            "model_pattern": match.group(1),
            "series_description": f"Konica Minolta bizhub {match.group(1)} series compact MFPs",
            "requires_context": True,  # Flag that this needs context validation
        }

    # Special patterns: 3100P, 3300P, 3301P, 3320, 3602P, 3622MFP, 4000i, 4020, 4050, 4400, 4402P, 4422MFP, 4700i, 4750, 5000i, 5020i
    match = re.match(r"^([3-5])[0-9]{3}([IP]|MFP)?$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "bizhub",
            "model_pattern": f"{series_digit}xxx",
            "series_description": f"Konica Minolta bizhub {series_digit}xxx series",
        }

    return None


def _detect_ricoh_series(model_number: str) -> dict | None:
    """Detect Ricoh series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:RICOH\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing =====

    # Pro C series (Pro C5300s, Pro C5310s, Pro C7500, Pro C9500, Pro C901, Pro C7200sx)
    match = re.match(r"^PRO\s+C(\d{3,4})([A-Z]{0,2})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Pro C",
            "model_pattern": f"Pro C{series_digit}xxx",
            "series_description": f"Ricoh Pro C{series_digit}xxx series production color systems",
        }

    # Pro VC series - Inkjet High-speed (Pro VC80000, Pro VC70000)
    match = re.match(r"^PRO\s+VC(\d{5})$", model_clean)
    if match:
        return {
            "series_name": "Pro VC",
            "model_pattern": "Pro VC",
            "series_description": "Ricoh Pro VC series high-speed inkjet production printers",
        }

    # Pro 8400 series - High-volume B&W (Pro 8420)
    match = re.match(r"^PRO\s+(8\d{3})$", model_clean)
    if match:
        return {
            "series_name": "Pro 8",
            "model_pattern": "Pro 8xxx",
            "series_description": "Ricoh Pro 8xxx series high-volume monochrome production printers",
        }

    # ===== PRIORITY 2: Large Format/CAD =====

    # MP W series - Wide Format (MP W6700, MP W3601)
    match = re.match(r"^(?:AFICIO\s+)?MP\s+W(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MP W",
            "model_pattern": f"MP W{series_digit}xxx",
            "series_description": f"Ricoh MP W{series_digit}xxx series wide format MFPs",
        }

    # IM CW series - Wide Format (IM CW2200)
    match = re.match(r"^IM\s+CW(\d{4})$", model_clean)
    if match:
        return {
            "series_name": "IM CW",
            "model_pattern": "IM CW",
            "series_description": "Ricoh IM CW series wide format MFPs",
        }

    # ===== PRIORITY 3: IM Series (Smart MFP) =====

    # IM C series with suffix (IM C400F, IM C401F, IM C4510(A))
    match = re.match(r"^IM\s+C(\d{3,4})([A-Z]?)\(?[A-Z]?\)?$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "IM C",
            "model_pattern": f"IM C{series_digit}xxx",
            "series_description": f"Ricoh IM C{series_digit}xxx series smart color MFPs",
        }

    # IM series monochrome (IM 2500A, IM 3000A, IM 3500A, IM 2702)
    match = re.match(r"^IM\s+(\d{4})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "IM",
            "model_pattern": f"IM {series_digit}xxx",
            "series_description": f"Ricoh IM {series_digit}xxx series smart monochrome MFPs",
        }

    # ===== PRIORITY 4: MP Series (Office MFP) =====

    # MP C series with suffix (MP C2503SP, MP C501SP)
    match = re.match(r"^MP\s+C(\d{3,4})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MP C",
            "model_pattern": f"MP C{series_digit}xxx",
            "series_description": f"Ricoh MP C{series_digit}xxx series color office MFPs",
        }

    # MP series monochrome (MP 2014AD, MP 2555SP, MP 3055SP, MP 6055SP)
    match = re.match(r"^MP\s+(\d{4})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MP",
            "model_pattern": f"MP {series_digit}xxx",
            "series_description": f"Ricoh MP {series_digit}xxx series monochrome office MFPs",
        }

    # ===== PRIORITY 5: Aficio MP Series (Legacy) =====

    # Aficio MP C series (Aficio MP C2030, MP C2800, MP C3500)
    match = re.match(r"^AFICIO\s+MP\s+C(\d{3,4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Aficio MP C",
            "model_pattern": f"Aficio MP C{series_digit}xxx",
            "series_description": f"Ricoh Aficio MP C{series_digit}xxx series color MFPs (legacy)",
        }

    # Aficio MP series monochrome (Aficio MP 171, MP 161)
    match = re.match(r"^AFICIO\s+MP\s+(\d{3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Aficio MP",
            "model_pattern": f"Aficio MP {series_digit}xx",
            "series_description": f"Ricoh Aficio MP {series_digit}xx series monochrome MFPs (legacy)",
        }

    # ===== PRIORITY 6: SP Series (Printer) =====

    # SP C series - Color (SP C261DNw)
    match = re.match(r"^SP\s+C(\d{3})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "SP C",
            "model_pattern": f"SP C{series_digit}xx",
            "series_description": f"Ricoh SP C{series_digit}xx series color printers",
        }

    # SP series - Monochrome (SP 230DNw, SP 230SFNw, SP 311)
    match = re.match(r"^SP\s+(\d{3})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "SP",
            "model_pattern": f"SP {series_digit}xx",
            "series_description": f"Ricoh SP {series_digit}xx series monochrome printers",
        }

    # ===== PRIORITY 7: P Series (Modern Printer) =====

    # P C series - Color (P C200W)
    match = re.match(r"^P\s+C(\d{3})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "P C",
            "model_pattern": f"P C{series_digit}xx",
            "series_description": f"Ricoh P C{series_digit}xx series modern color printers",
        }

    # P series - Monochrome (P 502)
    match = re.match(r"^P\s+(\d{3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "P",
            "model_pattern": f"P {series_digit}xx",
            "series_description": f"Ricoh P {series_digit}xx series modern monochrome printers",
        }

    # ===== PRIORITY 8: Aficio SG Series (GelJet) =====

    # Aficio SG series (SG 2100N, SG 3110DN, SG 3100SNw)
    match = re.match(r"^(?:AFICIO\s+)?SG\s+(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Aficio SG",
            "model_pattern": f"Aficio SG {series_digit}xxx",
            "series_description": f"Ricoh Aficio SG {series_digit}xxx series GelJet printers",
        }

    return None


def _detect_xerox_series(model_number: str) -> dict | None:
    """Detect Xerox series"""
    model = model_number.upper()

    # VersaLink C series (C7020, C7025, C7030, etc.)
    match = re.match(r"C(\d{2})\d{2}", model)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": f"VersaLink C{series_digit}xx Series",
            "series_code": f"C{series_digit}XX",
            "series_description": f"Xerox VersaLink C{series_digit} series color MFPs",
        }

    # WorkCentre series (WC7835, WC7845, etc.)
    match = re.match(r"(?:WC)?(\d{2})\d{2}", model)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": f"WorkCentre {series_digit}xx Series",
            "series_code": f"WC{series_digit}XX",
            "series_description": f"Xerox WorkCentre {series_digit} series",
        }

    return None


def _detect_brother_series(model_number: str) -> dict | None:
    """Detect Brother series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:BROTHER\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing (DTG/Textile) =====

    # GTXpro series (GTXpro, GTXpro B, GTX600, GTX R2R)
    if re.match(r"^GTXPRO\s*B?$", model_clean):
        return {
            "series_name": "GTXpro",
            "model_pattern": "GTXpro",
            "series_description": "Brother GTXpro series direct-to-garment (DTG) printers",
        }

    # GTX series (GTX600, GTX R2R)
    if re.match(r"^GTX", model_clean):
        return {
            "series_name": "GTX",
            "model_pattern": "GTX",
            "series_description": "Brother GTX series direct-to-garment/DTF printers",
        }

    # ===== PRIORITY 2: Specialty (Plotter/Cutting) =====

    # PL series (Plotter) - PL5250
    match = re.match(r"^PL(\d{4})$", model_clean)
    if match:
        return {"series_name": "PL Series", "model_pattern": "PL", "series_description": "Brother PL series plotters"}

    # ScanNCut series
    if re.match(r"^SCANNCUT", model_clean):
        return {
            "series_name": "ScanNCut",
            "model_pattern": "ScanNCut",
            "series_description": "Brother ScanNCut series cutting machines",
        }

    # ===== PRIORITY 3: MFC Series (4-in-1 MFP) =====

    # MFC-J series (Inkjet MFP) - MFC-J6540DW, MFC-J5740DW
    match = re.match(r"^MFC-J(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MFC-J",
            "model_pattern": f"MFC-J{series_digit}xxx",
            "series_description": f"Brother MFC-J{series_digit}xxx series inkjet MFPs (4-in-1)",
        }

    # MFC-L series (Laser MFP) - MFC-L9570CDW, MFC-L5935DW, MFC-L2750DW
    match = re.match(r"^MFC-L(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MFC-L",
            "model_pattern": f"MFC-L{series_digit}xxx",
            "series_description": f"Brother MFC-L{series_digit}xxx series laser MFPs (4-in-1)",
        }

    # ===== PRIORITY 4: DCP Series (3-in-1 MFP) =====

    # DCP-J series (Inkjet MFP) - DCP-J1200W, DCP-J1310DW
    match = re.match(r"^DCP-J(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "DCP-J",
            "model_pattern": f"DCP-J{series_digit}xxx",
            "series_description": f"Brother DCP-J{series_digit}xxx series inkjet MFPs (3-in-1)",
        }

    # DCP-L series (Laser MFP) - DCP-L3550CDW, DCP-L1640W
    match = re.match(r"^DCP-L(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "DCP-L",
            "model_pattern": f"DCP-L{series_digit}xxx",
            "series_description": f"Brother DCP-L{series_digit}xxx series laser MFPs (3-in-1)",
        }

    # ===== PRIORITY 5: HL Series (Printer) =====

    # HL-L series (Laser Printer) - HL-L2350DW, HL-L5100DN, HL-L9470CDN
    match = re.match(r"^HL-L(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "HL-L",
            "model_pattern": f"HL-L{series_digit}xxx",
            "series_description": f"Brother HL-L{series_digit}xxx series laser printers",
        }

    # ===== PRIORITY 6: IntelliFax Series (Fax Printers) =====

    # IntelliFax series - IntelliFax 2840, 4750e
    match = re.match(r"^INTELLIFAX\s+(\d{4})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "IntelliFax",
            "model_pattern": f"IntelliFax {series_digit}xxx",
            "series_description": f"Brother IntelliFax {series_digit}xxx series fax machines",
        }

    # ===== PRIORITY 7: PJ Series (Mobile/Portable) =====

    # PJ series (Mobile Printer) - PJ-763MFi, PJ-863PK
    match = re.match(r"^PJ-(\d{3})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "PJ Series",
            "model_pattern": f"PJ-{series_num[0]}xx",
            "series_description": f"Brother PJ-{series_num[0]}xx series mobile/portable printers",
        }

    return None


def _detect_lexmark_series(model_number: str) -> dict | None:
    """Detect Lexmark series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common suffixes for pattern matching
    model_clean = re.sub(r"(?:SERIES)$", "", model).strip()

    # ===== PRIORITY 1: Enterprise & Production (9xxx, 8xxx) =====
    # 9xxx = A3 Enterprise Production (e.g., 9300)
    if re.match(r"^9\d{3}$", model_clean):
        return {
            "series_name": "Enterprise Production",
            "model_pattern": "9xxx",
            "series_description": "Lexmark 9xxx series A3 Enterprise Production printers/MFPs",
        }

    # 8xxx = A4 Enterprise Color MFP (e.g., 8300)
    if re.match(r"^8\d{3}$", model_clean):
        return {
            "series_name": "Enterprise Color",
            "model_pattern": "8xxx",
            "series_description": "Lexmark 8xxx series A4 Enterprise Color MFPs",
        }

    # ===== PRIORITY 2: Color Series (C, MC, CX) =====

    # CX series - Color MFP (CX725, CX735, CX860, CX921, CX931, CX942adse, CX94X)
    # Pattern: CX + 2-4 digits/X + optional suffix
    match = re.match(r"^CX(\d{1,3}[X\d])([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "CX Series",
            "model_pattern": f"CX{series_digit}xx",
            "series_description": f"Lexmark CX{series_digit}xx series color MFPs",
        }

    # MC series - Color MFP (MC3224i, MC3224dwe, MC3326i, MC3426i)
    # Pattern: MC + 4 digits + optional suffix
    match = re.match(r"^MC(\d{4})([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit (3)
        return {
            "series_name": "MC Series",
            "model_pattern": f"MC{series_digit}xxx",
            "series_description": f"Lexmark MC{series_digit}xxx series color multifunction printers",
        }

    # C series - Color Single Function (C2326, C3224dw, C3326dw, C3426dw)
    # Pattern: C + 4 digits + optional suffix
    match = re.match(r"^C(\d{4})([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "C Series",
            "model_pattern": f"C{series_digit}xxx",
            "series_description": f"Lexmark C{series_digit}xxx series color laser printers",
        }

    # ===== PRIORITY 3: Monochrome Series (B, MB, MS, MX, XM) =====

    # XM series - Enterprise Monochrome MFP (XM3350, XM9145, XM9155)
    # Pattern: XM + 4 digits
    match = re.match(r"^XM(\d{4})$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "XM Series",
            "model_pattern": f"XM{series_digit}xxx",
            "series_description": f"Lexmark XM{series_digit}xxx series enterprise monochrome MFPs",
        }

    # MX series - Monochrome MFP (MX317dn, MX421ade, MX522adhe, MX532adwe, MX622adhe, MX822ade, MX931dse, MX94X)
    # Pattern: MX + 2-4 digits/X + suffix
    match = re.match(r"^MX(\d{1,3}[X\d])([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "MX Series",
            "model_pattern": f"MX{series_digit}xx",
            "series_description": f"Lexmark MX{series_digit}xx series monochrome MFPs",
        }

    # MS series - Monochrome Single Function (MS310dn, MS312dn, MS317dn, MS321dn, MS331dn, MS421dn)
    # Pattern: MS + 3 digits + suffix
    match = re.match(r"^MS(\d{3})([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "MS Series",
            "model_pattern": f"MS{series_digit}xx",
            "series_description": f"Lexmark MS{series_digit}xx series monochrome laser printers",
        }

    # MB series - Monochrome Compact MFP (MB2236adw, MB2236i, MB3442i)
    # Pattern: MB + 4 digits + suffix
    match = re.match(r"^MB(\d{4})([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "MB Series",
            "model_pattern": f"MB{series_digit}xxx",
            "series_description": f"Lexmark MB{series_digit}xxx series monochrome compact MFPs",
        }

    # B series - Monochrome Compact Single Function (B2236dw, B3340dw, B3442dw)
    # Pattern: B + 4 digits + suffix
    match = re.match(r"^B(\d{4})([A-Z]{0,5})?$", model_clean)
    if match:
        model_num = match.group(1)
        series_digit = model_num[0]  # First digit
        return {
            "series_name": "B Series",
            "model_pattern": f"B{series_digit}xxx",
            "series_description": f"Lexmark B{series_digit}xxx series monochrome compact laser printers",
        }

    # ===== PRIORITY 4: Historical Models =====

    # Interpret S400 Series - Inkjet (S400, S402, S405, S408, S415)
    if re.match(r"^S4\d{2}$", model_clean):
        return {
            "series_name": "Interpret S400 Series",
            "model_pattern": "S4xx",
            "series_description": "Lexmark Interpret S400 series inkjet printers",
        }

    # Plus Matrix Printers (2380-3, 2381-3, 2390-3, 2391-3)
    match = re.match(r"^(23[89][01])-(\d)$", model_clean)
    if match:
        return {
            "series_name": "Plus Matrix Series",
            "model_pattern": "23xx",
            "series_description": "Lexmark Plus series dot matrix printers",
        }

    return None


def _detect_kyocera_series(model_number: str) -> dict | None:
    """Detect Kyocera series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:KYOCERA\s+)?", "", model).strip()

    # ===== PRIORITY 1: TASKalfa Pro (Production) =====

    # TASKalfa Pro (Pro 15000c, Pro 55000c)
    match = re.match(r"^(?:TASKALFA\s+)?PRO\s+(\d{5})C?$", model_clean)
    if match:
        return {
            "series_name": "TASKalfa Pro",
            "model_pattern": "TASKalfa Pro",
            "series_description": "Kyocera TASKalfa Pro production color systems",
        }

    # ===== PRIORITY 2: TASKalfa (A3/A4 MFP) =====

    # TASKalfa with ci suffix (2553ci, 5053ci, etc.)
    match = re.match(r"^(?:TASKALFA\s+)?(\d{4})CI$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "TASKalfa",
            "model_pattern": f"TASKalfa {series_digit}xxxci",
            "series_description": f"Kyocera TASKalfa {series_digit}xxxci series color MFPs",
        }

    # TASKalfa general (2552, 3252, etc.)
    match = re.match(r"^(?:TASKALFA\s+)?(\d{4})([A-Z]{0,3})?$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "TASKalfa",
            "model_pattern": f"TASKalfa {series_digit}xxx",
            "series_description": f"Kyocera TASKalfa {series_digit}xxx series MFPs",
        }

    # ===== PRIORITY 3: ECOSYS PA/MA/M Serie =====

    # ECOSYS PA (PA3500cx, PA4500x)
    match = re.match(r"^(?:ECOSYS\s+)?PA(\d{4})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ECOSYS PA",
            "model_pattern": f"ECOSYS PA{series_digit}xxx",
            "series_description": f"Kyocera ECOSYS PA{series_digit}xxx series color printers",
        }

    # ECOSYS MA (MA2100cfx, MA3500cifx)
    match = re.match(r"^(?:ECOSYS\s+)?MA(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ECOSYS MA",
            "model_pattern": f"ECOSYS MA{series_digit}xxx",
            "series_description": f"Kyocera ECOSYS MA{series_digit}xxx series color MFPs",
        }

    # ECOSYS M (M3860idnf, M4132idn, M8130cidn)
    match = re.match(r"^(?:ECOSYS\s+)?M(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ECOSYS M",
            "model_pattern": f"ECOSYS M{series_digit}xxx",
            "series_description": f"Kyocera ECOSYS M{series_digit}xxx series MFPs",
        }

    # ===== PRIORITY 4: FS-Serie (Drucker & MFP) =====

    # FS-Serie MFP (FS-1030MFP, FS-6530MFP)
    match = re.match(r"^FS-(\d{4})MFP$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "FS-Series MFP",
            "model_pattern": f"FS-{series_digit}xxxMFP",
            "series_description": f"Kyocera FS-{series_digit}xxx series multifunction printers",
        }

    # FS-Serie Drucker (FS-1000, FS-1120DN, FS-1320D, FS-4020DN, FS-6020DTN)
    match = re.match(r"^FS-(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "FS-Series",
            "model_pattern": f"FS-{series_digit}xxx",
            "series_description": f"Kyocera FS-{series_digit}xxx series printers",
        }

    # ===== PRIORITY 5: KM-Serie (Ältere MFPs) =====

    # KM-Serie (KM-2050, KM-5050)
    match = re.match(r"^KM-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "KM-Series",
            "model_pattern": f"KM-{series_digit}xxx",
            "series_description": f"Kyocera KM-{series_digit}xxx series legacy MFPs",
        }

    # ===== PRIORITY 6: Weitere Serien (DC, DP, TC, F) =====

    # TC-Serie (TC-4026i)
    match = re.match(r"^TC-(\d{4})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "TC-Series",
            "model_pattern": f"TC-{series_digit}xxx",
            "series_description": f"Kyocera TC-{series_digit}xxx series",
        }

    # F-Serie (F 2010)
    match = re.match(r"^F\s*(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "F-Series",
            "model_pattern": f"F {series_digit}xxx",
            "series_description": f"Kyocera F {series_digit}xxx series",
        }

    # DC-Serie
    match = re.match(r"^DC-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "DC-Series",
            "model_pattern": f"DC-{series_digit}xxx",
            "series_description": f"Kyocera DC-{series_digit}xxx series",
        }

    # DP-Serie
    match = re.match(r"^DP-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "DP-Series",
            "model_pattern": f"DP-{series_digit}xxx",
            "series_description": f"Kyocera DP-{series_digit}xxx series",
        }

    return None


def _detect_utax_series(model_number: str) -> dict | None:
    """Detect UTAX series - Returns marketing name + technical pattern

    UTAX is a Kyocera rebrand (TA Triumph-Adler)
    """
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:UTAX\s+)?", "", model).strip()

    # ===== PRIORITY 1: P-Serie (Monochrom & Farb MFP/Drucker) =====

    # P-Serie MFP with i suffix (P-4532i MFP, P-4539i MFP, P-5539i MFP, P-6039i MFP)
    match = re.match(r"^P-(\d)(\d{3})I\s*MFP$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "P-Series MFP",
            "model_pattern": f"P-{series_digit}xxxI MFP",
            "series_description": f"UTAX P-{series_digit}xxx series multifunction printers (i-model)",
        }

    # P-Serie MFP without i (P-4532 MFP, P-4539 MFP)
    match = re.match(r"^P-(\d)(\d{3})\s*MFP$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "P-Series MFP",
            "model_pattern": f"P-{series_digit}xxx MFP",
            "series_description": f"UTAX P-{series_digit}xxx series multifunction printers",
        }

    # P-Serie Drucker (P-4534DN, P-5034DN, P-5534DN, P-6034DN)
    match = re.match(r"^P-(\d)(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "P-Series",
            "model_pattern": f"P-{series_digit}xxx",
            "series_description": f"UTAX P-{series_digit}xxx series printers",
        }

    # ===== PRIORITY 2: LP-Serie (A3-Monochrom) =====

    # LP-Serie (LP 3130DN, LP 4155DN, LP 3245, LP 4345)
    match = re.match(r"^LP\s*(\d)(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": "LP-Series",
            "model_pattern": f"LP {series_digit}xxx",
            "series_description": f"UTAX LP {series_digit}xxx series A3 monochrome printers",
        }

    # ===== PRIORITY 3: CDC/CDP/CD-Serie (Farb-MFP/Drucker) =====

    # CDC Serie (CDC 1720, CDC 2240)
    match = re.match(r"^CDC\s*(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "CDC Series",
            "model_pattern": f"CDC {series_digit}xxx",
            "series_description": f"UTAX CDC {series_digit}xxx series color MFPs",
        }

    # CDP Serie
    match = re.match(r"^CDP\s*(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "CDP Series",
            "model_pattern": f"CDP {series_digit}xxx",
            "series_description": f"UTAX CDP {series_digit}xxx series color printers",
        }

    # CD Serie (CD 1630)
    match = re.match(r"^CD\s*(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "CD Series",
            "model_pattern": f"CD {series_digit}xxx",
            "series_description": f"UTAX CD {series_digit}xxx series color devices",
        }

    # ===== PRIORITY 4: Numeric Models (Kyocera-based) =====

    # 4-digit models with "ci" suffix (5006ci, 4006ci, 3206ci, etc.)
    # These are Kyocera TASKalfa rebrands
    match = re.match(r"^(\d)(\d{3})CI$", model_clean)
    if match:
        series_digit = match.group(1)
        return {
            "series_name": f"{series_digit}xxxci Series",
            "model_pattern": f"{series_digit}xxxci",
            "series_description": f"UTAX {series_digit}xxxci series color MFPs (Kyocera-based)",
        }

    return None


def _detect_fujifilm_series(model_number: str) -> dict | None:
    """Detect Fujifilm series - Returns marketing name + technical pattern

    Fujifilm is the Xerox successor in Asia/Japan (formerly Fuji Xerox)
    """
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:FUJIFILM\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Systems =====

    # Revoria Press (SC285(S), EC2100(S), PC1120(S))
    match = re.match(r"^REVORIA\s+PRESS\s+([SEMP]C)(\d{3,4})\(?S?\)?$", model_clean)
    if match:
        series_prefix = match.group(1)  # SC, EC, MC, PC
        return {
            "series_name": "Revoria Press",
            "model_pattern": f"Revoria Press {series_prefix}",
            "series_description": f"Fujifilm Revoria Press {series_prefix} series high-end production systems",
        }

    # JetPress (750S)
    match = re.match(r"^JETPRESS\s+(\d{3,4})S?$", model_clean)
    if match:
        return {
            "series_name": "JetPress",
            "model_pattern": "JetPress",
            "series_description": "Fujifilm JetPress inkjet SRA3 production printer",
        }

    # ===== PRIORITY 2: ApeosPro (Light Production) =====

    # ApeosPro C Series (C810, C750, C650)
    match = re.match(r"^APEOSPRO\s+C(\d{3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ApeosPro",
            "model_pattern": f"ApeosPro C{series_digit}xx",
            "series_description": f"Fujifilm ApeosPro C{series_digit}xx series light production color systems",
        }

    # ===== PRIORITY 3: Apeos/ApeosPort (MFP) =====

    # ApeosPort-VII (ApeosPort-VII C4473)
    match = re.match(r"^APEOSPORT-VII\s+C(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ApeosPort-VII",
            "model_pattern": f"ApeosPort-VII C{series_digit}xxx",
            "series_description": f"Fujifilm ApeosPort-VII C{series_digit}xxx series color MFPs",
        }

    # ApeosPort (general)
    match = re.match(r"^APEOSPORT\s+C(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ApeosPort",
            "model_pattern": f"ApeosPort C{series_digit}xxx",
            "series_description": f"Fujifilm ApeosPort C{series_digit}xxx series color MFPs",
        }

    # Apeos MFP (C3060, C3070)
    match = re.match(r"^APEOS\s+C(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Apeos",
            "model_pattern": f"Apeos C{series_digit}xxx",
            "series_description": f"Fujifilm Apeos C{series_digit}xxx series color MFPs",
        }

    # ===== PRIORITY 4: ApeosPrint (Printer) =====

    # ApeosPrint (C325, C4030)
    match = re.match(r"^APEOSPRINT\s+C(\d{3,4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ApeosPrint",
            "model_pattern": f"ApeosPrint C{series_digit}xx",
            "series_description": f"Fujifilm ApeosPrint C{series_digit}xx series color printers",
        }

    # ===== PRIORITY 5: INSTAX (Photo Printers) =====

    # INSTAX mini Link
    if re.match(r"^INSTAX\s+MINI\s+LINK", model_clean):
        return {
            "series_name": "INSTAX mini Link",
            "model_pattern": "INSTAX mini Link",
            "series_description": "Fujifilm INSTAX mini Link compact photo printer",
        }

    # INSTAX SQUARE Link
    if re.match(r"^INSTAX\s+SQUARE\s+LINK", model_clean):
        return {
            "series_name": "INSTAX SQUARE Link",
            "model_pattern": "INSTAX SQUARE Link",
            "series_description": "Fujifilm INSTAX SQUARE Link compact photo printer",
        }

    # INSTAX Link Wide
    if re.match(r"^INSTAX\s+LINK\s+WIDE", model_clean):
        return {
            "series_name": "INSTAX Link Wide",
            "model_pattern": "INSTAX Link Wide",
            "series_description": "Fujifilm INSTAX Link Wide compact photo printer",
        }

    # INSTAX (generic)
    if re.match(r"^INSTAX", model_clean):
        return {
            "series_name": "INSTAX",
            "model_pattern": "INSTAX",
            "series_description": "Fujifilm INSTAX compact photo printer",
        }

    # ===== PRIORITY 6: Legacy DocuPrint/DocuCentre (Xerox-based) =====

    # DocuPrint (CP505)
    match = re.match(r"^DOCUPRINT\s+([A-Z]{2})(\d{3})$", model_clean)
    if match:
        series_prefix = match.group(1)
        return {
            "series_name": "DocuPrint",
            "model_pattern": f"DocuPrint {series_prefix}",
            "series_description": f"Fujifilm DocuPrint {series_prefix} series (Xerox-based legacy)",
        }

    # DocuCentre
    match = re.match(r"^DOCUCENTRE\s+([A-Z]{1,2})(\d{3,4})$", model_clean)
    if match:
        series_prefix = match.group(1)
        return {
            "series_name": "DocuCentre",
            "model_pattern": f"DocuCentre {series_prefix}",
            "series_description": f"Fujifilm DocuCentre {series_prefix} series MFPs (Xerox-based legacy)",
        }

    return None


def _detect_oki_series(model_number: str) -> dict | None:
    """Detect OKI series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:OKI\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing =====

    # Pro9 series (Pro9431dn, Pro9541dn, Pro9542dn)
    match = re.match(r"^PRO9(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "Pro9",
            "model_pattern": f"Pro9{series_num[0]}xx",
            "series_description": f"OKI Pro9{series_num[0]}xx series industrial production printers",
        }

    # Pro1040/Pro1050 (Label printers)
    if re.match(r"^PRO10[45]0$", model_clean):
        return {
            "series_name": "Pro10",
            "model_pattern": "Pro10xx",
            "series_description": "OKI Pro10xx series roll-to-roll label printers",
        }

    # ===== PRIORITY 2: MC Series (Color MFP) =====

    # MC series high-end (MC883dn, MC883dnct, MC883dnv, MC770dn, MC780dn)
    match = re.match(r"^MC(\d{3})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MC Series",
            "model_pattern": f"MC{series_digit}xx",
            "series_description": f"OKI MC{series_digit}xx series color MFPs",
        }

    # ===== PRIORITY 3: MB Series (Monochrome MFP) =====

    # MB series (MB472dnw, MB492dn, MB562dnw)
    match = re.match(r"^MB(\d{3})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MB Series",
            "model_pattern": f"MB{series_digit}xx",
            "series_description": f"OKI MB{series_digit}xx series monochrome MFPs",
        }

    # ===== PRIORITY 4: C Series (Color Printer) =====

    # C series (C332dn, C542dn, C612dn, C824dn, C833dn, C843dn)
    match = re.match(r"^C(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "C Series",
            "model_pattern": f"C{series_digit}xx",
            "series_description": f"OKI C{series_digit}xx series color printers",
        }

    # ===== PRIORITY 5: B Series (Monochrome Printer/MFP) =====

    # B series MFP (B2520 MFP, B2540 MFP)
    match = re.match(r"^B(\d{4})\s+MFP$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "B Series MFP",
            "model_pattern": f"B{series_digit}xxx MFP",
            "series_description": f"OKI B{series_digit}xxx series monochrome MFPs",
        }

    # B series printer (B401d, B431dn, B512dn, B721dn, B731dn)
    match = re.match(r"^B(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "B Series",
            "model_pattern": f"B{series_digit}xx",
            "series_description": f"OKI B{series_digit}xx series monochrome printers",
        }

    # ===== PRIORITY 6: ES Series (Executive) =====

    # ES series MFP (ES4191 MFP, ES4192 MFP)
    match = re.match(r"^ES(\d{4})\s+MFP$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ES Series MFP",
            "model_pattern": f"ES{series_digit}xxx MFP",
            "series_description": f"OKI ES{series_digit}xxx series executive MFPs",
        }

    # ES series printer (ES4191dn, ES5112dn)
    match = re.match(r"^ES(\d{4})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "ES Series",
            "model_pattern": f"ES{series_digit}xxx",
            "series_description": f"OKI ES{series_digit}xxx series executive printers",
        }

    # ===== PRIORITY 7: CX Series (Office Color) =====

    # CX series MFP (CX 3500 Series)
    if re.match(r"^CX\s+\d{4}(?:\s+SERIES)?", model_clean):
        return {
            "series_name": "CX Series",
            "model_pattern": "CX",
            "series_description": "OKI CX series office color MFPs",
        }

    # CX series printer (CX 3535)
    match = re.match(r"^CX\s+(\d{4})$", model_clean)
    if match:
        return {
            "series_name": "CX Series",
            "model_pattern": "CX",
            "series_description": "OKI CX series office color devices",
        }

    return None


def _detect_xerox_series(model_number: str) -> dict | None:
    """Detect Xerox series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:XEROX\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing =====

    # Iridesse Production Press
    if re.match(r"^IRIDESSE\s+PRODUCTION\s+PRESS", model_clean):
        return {
            "series_name": "Iridesse Production Press",
            "model_pattern": "Iridesse",
            "series_description": "Xerox Iridesse Production Press (CMYK + Gold/Silver/White)",
        }

    # Color Press series (Color Press 800/1000, 280, 570, 800/1000i)
    match = re.match(r"^COLOR\s+PRESS\s+(\d{3,4})I?(?:/(\d{3,4})I?)?$", model_clean)
    if match:
        return {
            "series_name": "Color Press",
            "model_pattern": "Color Press",
            "series_description": "Xerox Color Press series production color systems",
        }

    # PrimeLink series (C9065, C9070)
    match = re.match(r"^PRIMELINK\s+C(\d{4})$", model_clean)
    if match:
        return {
            "series_name": "PrimeLink",
            "model_pattern": "PrimeLink C",
            "series_description": "Xerox PrimeLink C series production/office systems",
        }

    # Versant series
    match = re.match(r"^VERSANT\s+(\d{3})$", model_clean)
    if match:
        return {
            "series_name": "Versant",
            "model_pattern": "Versant",
            "series_description": "Xerox Versant series production color press",
        }

    # iGen series
    if re.match(r"^IGEN", model_clean):
        return {
            "series_name": "iGen",
            "model_pattern": "iGen",
            "series_description": "Xerox iGen series digital production press",
        }

    # ===== PRIORITY 2: AltaLink (High-End MFP) =====

    # AltaLink (B8045, B8055, C8030, C8045, C8255, C8270)
    match = re.match(r"^ALTALINK\s+([BC])(\d{4})$", model_clean)
    if match:
        color_type = match.group(1)  # B or C
        series_num = match.group(2)
        series_digit = series_num[0]
        color_desc = "color" if color_type == "C" else "monochrome"
        return {
            "series_name": "AltaLink",
            "model_pattern": f"AltaLink {color_type}{series_digit}xxx",
            "series_description": f"Xerox AltaLink {color_type}{series_digit}xxx series {color_desc} high-end MFPs",
        }

    # ===== PRIORITY 3: VersaLink (Office MFP/Printer) =====

    # VersaLink MFP (C405, C505, C605, B405, B605, B615, B625)
    match = re.match(r"^VERSALINK\s+([BC])(\d{3})$", model_clean)
    if match:
        color_type = match.group(1)  # B or C
        series_num = match.group(2)
        series_digit = series_num[0]
        color_desc = "color" if color_type == "C" else "monochrome"

        # Determine if MFP or Printer based on model number
        # B400, C400, C500, C600, B600 = Printer
        # C405, C505, C605, B405, B605, B615, B625 = MFP
        if series_num in ["400", "500", "600"]:
            device_type = "printer"
            return {
                "series_name": "VersaLink",
                "model_pattern": f"VersaLink {color_type}{series_digit}xx",
                "series_description": f"Xerox VersaLink {color_type}{series_digit}xx series {color_desc} printers",
            }
        device_type = "MFP"
        return {
            "series_name": "VersaLink",
            "model_pattern": f"VersaLink {color_type}{series_digit}xx",
            "series_description": f"Xerox VersaLink {color_type}{series_digit}xx series {color_desc} MFPs",
        }

    # ===== PRIORITY 4: WorkCentre (Office MFP) =====

    # WorkCentre (6515, 7855, 7858, 7970, 7970i, 7835i)
    match = re.match(r"^WORKCENTRE\s+(\d{4})I?$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "WorkCentre",
            "model_pattern": f"WorkCentre {series_digit}xxx",
            "series_description": f"Xerox WorkCentre {series_digit}xxx series MFPs",
        }

    # ===== PRIORITY 5: Phaser (Printer) =====

    # Phaser (6022, 6510, 6600, 7100, 7800)
    match = re.match(r"^PHASER\s+(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Phaser",
            "model_pattern": f"Phaser {series_digit}xxx",
            "series_description": f"Xerox Phaser {series_digit}xxx series color printers",
        }

    # ===== PRIORITY 6: ColorQube (Solid Ink) =====

    # ColorQube MFP (9303 MFP, 9301 MFP, 9302 MFP)
    match = re.match(r"^COLORQUBE\s+(\d{4})\s+MFP$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "ColorQube",
            "model_pattern": f"ColorQube {series_num[0]}xxx MFP",
            "series_description": f"Xerox ColorQube {series_num[0]}xxx series solid ink MFPs",
        }

    # ColorQube printer (8580, 9301, 9302, 9303)
    match = re.match(r"^COLORQUBE\s+(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "ColorQube",
            "model_pattern": f"ColorQube {series_num[0]}xxx",
            "series_description": f"Xerox ColorQube {series_num[0]}xxx series solid ink printers",
        }

    # ===== PRIORITY 7: Wide Format =====

    # Wide Format series (7142, 8000)
    match = re.match(r"^WIDE\s+FORMAT\s+(\d{4})$", model_clean)
    if match:
        return {
            "series_name": "Wide Format",
            "model_pattern": "Wide Format",
            "series_description": "Xerox Wide Format series large format printers",
        }

    # ===== PRIORITY 8: Legacy DocuPrint/DocuCentre =====

    # DocuPrint (CP225)
    match = re.match(r"^DOCUPRINT\s+([A-Z]{2})(\d{3})$", model_clean)
    if match:
        series_prefix = match.group(1)
        return {
            "series_name": "DocuPrint",
            "model_pattern": f"DocuPrint {series_prefix}",
            "series_description": f"Xerox DocuPrint {series_prefix} series (legacy)",
        }

    # DocuCentre (SC2020)
    match = re.match(r"^DOCUCENTRE\s+([A-Z]{2})(\d{4})$", model_clean)
    if match:
        series_prefix = match.group(1)
        return {
            "series_name": "DocuCentre",
            "model_pattern": f"DocuCentre {series_prefix}",
            "series_description": f"Xerox DocuCentre {series_prefix} series MFPs (legacy)",
        }

    return None


def _detect_epson_series(model_number: str) -> dict | None:
    """Detect Epson series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:EPSON\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing =====

    # SureColor F series - Textile (SC-F Series - all F models)
    if re.match(r"^(?:SURECOLOR\s+)?SC-F", model_clean):
        return {
            "series_name": "SureColor F",
            "model_pattern": "SureColor SC-F",
            "series_description": "Epson SureColor SC-F series textile/sublimation printers",
        }

    # SureColor P series - Production (SC-P9500 and higher)
    match = re.match(r"^(?:SURECOLOR\s+)?SC-P(\d{4})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        if int(series_num) >= 9000:
            return {
                "series_name": "SureColor Production",
                "model_pattern": "SureColor SC-P",
                "series_description": "Epson SureColor SC-P series production large format printers",
            }

    # Monna Lisa series (Industrial textile)
    if re.match(r"^MONNA\s+LISA", model_clean):
        return {
            "series_name": "Monna Lisa",
            "model_pattern": "Monna Lisa",
            "series_description": "Epson Monna Lisa series industrial textile printers",
        }

    # SureLab series (MiniLab photo production)
    if re.match(r"^SURELAB", model_clean):
        return {
            "series_name": "SureLab",
            "model_pattern": "SureLab",
            "series_description": "Epson SureLab series professional photo production systems",
        }

    # ===== PRIORITY 2: SureColor (Professional/Photo/Large Format) =====

    # SureColor SC-P series (SC-P600, SC-P800, SC-P7300)
    match = re.match(r"^(?:SURECOLOR\s+)?SC-P(\d{3,4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "SureColor P",
            "model_pattern": f"SureColor SC-P{series_digit}xxx",
            "series_description": f"Epson SureColor SC-P{series_digit}xxx series professional large format printers",
        }

    # ===== PRIORITY 3: WorkForce Enterprise/Pro (MFP & Printer) =====

    # WorkForce Enterprise (WF-C17590)
    match = re.match(r"^WORKFORCE\s+ENTERPRISE\s+WF-C(\d{5})$", model_clean)
    if match:
        return {
            "series_name": "WorkForce Enterprise",
            "model_pattern": "WorkForce Enterprise",
            "series_description": "Epson WorkForce Enterprise series high-volume inkjet MFPs",
        }

    # WorkForce Pro MFP (Pro WF-4745, Pro WF-5620, WF-4745DWF, WF-8510DWF)
    match = re.match(r"^(?:WORKFORCE\s+)?PRO\s+WF-(\d{4})([A-Z]{0,5})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "WorkForce Pro",
            "model_pattern": f"WorkForce Pro WF-{series_digit}xxx",
            "series_description": f"Epson WorkForce Pro WF-{series_digit}xxx series professional inkjet MFPs",
        }

    # WorkForce standard (WF-2830, WF-2850, WF-7840)
    match = re.match(r"^(?:WORKFORCE\s+)?WF-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "WorkForce",
            "model_pattern": f"WorkForce WF-{series_digit}xxx",
            "series_description": f"Epson WorkForce WF-{series_digit}xxx series inkjet MFPs",
        }

    # ===== PRIORITY 4: EcoTank (Refillable Ink) =====

    # EcoTank (ET-2750, ET-7700, ET-2850, ET-3850, ET-5880)
    match = re.match(r"^(?:ECOTANK\s+)?ET-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "EcoTank",
            "model_pattern": f"EcoTank ET-{series_digit}xxx",
            "series_description": f"Epson EcoTank ET-{series_digit}xxx series refillable ink printers/MFPs",
        }

    # ===== PRIORITY 5: Expression Home/Photo =====

    # Expression Photo (XP-8700)
    match = re.match(r"^(?:EXPRESSION\s+)?PHOTO\s+XP-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Expression Photo",
            "model_pattern": f"Expression Photo XP-{series_digit}xxx",
            "series_description": f"Epson Expression Photo XP-{series_digit}xxx series photo printers",
        }

    # Expression Home (XP-2200, XP-332, XP-5200)
    match = re.match(r"^(?:EXPRESSION\s+)?HOME\s+XP-(\d{3,4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "Expression Home",
            "model_pattern": f"Expression Home XP-{series_digit}xxx",
            "series_description": f"Epson Expression Home XP-{series_digit}xxx series home inkjet printers/MFPs",
        }

    # ===== PRIORITY 6: Stylus Series (Legacy) =====

    # Stylus Photo (PX700W, PX710W)
    match = re.match(r"^(?:STYLUS\s+)?PHOTO\s+PX(\d{3})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        return {
            "series_name": "Stylus Photo",
            "model_pattern": f"Stylus Photo PX{series_num[0]}xx",
            "series_description": f"Epson Stylus Photo PX{series_num[0]}xx series photo printers (legacy)",
        }

    # Stylus Pro (legacy large format)
    if re.match(r"^(?:STYLUS\s+)?PRO", model_clean):
        return {
            "series_name": "Stylus Pro",
            "model_pattern": "Stylus Pro",
            "series_description": "Epson Stylus Pro series large format printers (legacy, replaced by SureColor)",
        }

    # Stylus (general)
    if re.match(r"^STYLUS", model_clean):
        return {
            "series_name": "Stylus",
            "model_pattern": "Stylus",
            "series_description": "Epson Stylus series printers (legacy)",
        }

    # ===== PRIORITY 7: Legacy Matrix/Office (MJ, MX, MP, P) =====

    # MJ series (Matrix)
    if re.match(r"^MJ-", model_clean):
        return {
            "series_name": "MJ Series",
            "model_pattern": "MJ",
            "series_description": "Epson MJ series dot matrix printers (legacy)",
        }

    # MX series (Office)
    match = re.match(r"^MX-(\d{3,4})$", model_clean)
    if match:
        return {
            "series_name": "MX Series",
            "model_pattern": "MX",
            "series_description": "Epson MX series office printers (legacy)",
        }

    # MP series (Office)
    match = re.match(r"^MP-(\d{3,4})$", model_clean)
    if match:
        return {
            "series_name": "MP Series",
            "model_pattern": "MP",
            "series_description": "Epson MP series office printers (legacy)",
        }

    # P series (Office)
    match = re.match(r"^P-(\d{3,4})$", model_clean)
    if match:
        return {
            "series_name": "P Series",
            "model_pattern": "P",
            "series_description": "Epson P series office printers (legacy)",
        }

    return None


def _detect_sharp_series(model_number: str) -> dict | None:
    """Detect Sharp series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:SHARP\s+)?", "", model).strip()

    # ===== PRIORITY 1: Production Printing =====

    # BP Pro series - Production (BP-90C70, BP-90C80, BP-1360M)
    match = re.match(r"^BP-(\d{2,4})([CM])(\d{2,3})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        color_type = match.group(2)  # C or M
        if int(series_num) >= 90 or int(series_num) >= 1300:
            return {
                "series_name": "BP Pro",
                "model_pattern": "BP Pro",
                "series_description": "Sharp BP Pro series production/light production systems",
            }

    # MX High-end Production (MX-6500, MX-7500, MX-8090)
    match = re.match(r"^MX-([6-8]\d{3})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "MX Production",
            "model_pattern": f"MX-{series_digit}xxx",
            "series_description": f"Sharp MX-{series_digit}xxx series high-performance production MFPs",
        }

    # ===== PRIORITY 2: BP Series (Office & Production MFP) =====

    # BP-C/E/Q series MFP (BP-50C31, BP-50C55, BP-60C45, BP-55C26, BP-22C25)
    match = re.match(r"^BP-(\d{2})([CEQ])(\d{2,3})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_type = match.group(2)  # C, E, or Q
        return {
            "series_name": "BP Series",
            "model_pattern": f"BP-{series_num}{series_type}",
            "series_description": f"Sharp BP-{series_num}{series_type} series office MFPs",
        }

    # BP-C/E/Q series Printer (BP-C131PW, BP-10C20)
    match = re.match(r"^BP-([CEQ])(\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_type = match.group(1)
        return {
            "series_name": "BP Printer",
            "model_pattern": f"BP-{series_type}",
            "series_description": f"Sharp BP-{series_type} series office printers",
        }

    # ===== PRIORITY 3: MX Series (A3/A4 MFP) =====

    # MX-B/C series MFP (MX-3071, MX-4071, MX-3571, MX-2651, MX-3551, MX-4051, MX-B350, MX-C300)
    match = re.match(r"^MX-([BC]?)(\d{3,4})$", model_clean)
    if match:
        color_prefix = match.group(1)  # B or C (optional)
        series_num = match.group(2)
        series_digit = series_num[0]

        if color_prefix:
            color_desc = "monochrome" if color_prefix == "B" else "color"
            return {
                "series_name": f"MX-{color_prefix}",
                "model_pattern": f"MX-{color_prefix}{series_digit}xx",
                "series_description": f"Sharp MX-{color_prefix}{series_digit}xx series {color_desc} MFPs",
            }
        return {
            "series_name": "MX Series",
            "model_pattern": f"MX-{series_digit}xxx",
            "series_description": f"Sharp MX-{series_digit}xxx series MFPs",
        }

    # MX-B/C series Printer (MX-B350P, MX-C300P)
    match = re.match(r"^MX-([BC])(\d{3})P$", model_clean)
    if match:
        color_prefix = match.group(1)
        series_num = match.group(2)
        series_digit = series_num[0]
        color_desc = "monochrome" if color_prefix == "B" else "color"
        return {
            "series_name": f"MX-{color_prefix} Printer",
            "model_pattern": f"MX-{color_prefix}{series_digit}xxP",
            "series_description": f"Sharp MX-{color_prefix}{series_digit}xx series {color_desc} printers",
        }

    # ===== PRIORITY 4: AR/AL Series (Legacy) =====

    # AR series (Legacy MFP) - AR-6020N
    match = re.match(r"^AR-(\d{4})([A-Z]?)$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "AR Series",
            "model_pattern": f"AR-{series_digit}xxx",
            "series_description": f"Sharp AR-{series_digit}xxx series legacy MFPs",
        }

    # AL series (Legacy Printer) - AL-2040
    match = re.match(r"^AL-(\d{4})$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "AL Series",
            "model_pattern": f"AL-{series_digit}xxx",
            "series_description": f"Sharp AL-{series_digit}xxx series legacy printers",
        }

    return None


def _detect_toshiba_series(model_number: str) -> dict | None:
    """Detect Toshiba series - Returns marketing name + technical pattern"""
    model = model_number.upper().strip()

    # Remove common prefixes for pattern matching
    model_clean = re.sub(r"^(?:TOSHIBA\s+)?", "", model).strip()

    # ===== PRIORITY 1: e-STUDIO Series =====

    # e-STUDIO Production (High-end: 65+ ppm models like 7527AC, 6525AC)
    match = re.match(r"^E-STUDIO\s+([6-9]\d{3})([A-Z]{0,3})$", model_clean)
    if match:
        series_num = match.group(1)
        suffix = match.group(2)
        if int(series_num) >= 6500:
            return {
                "series_name": "e-STUDIO Production",
                "model_pattern": "e-STUDIO Production",
                "series_description": "Toshiba e-STUDIO high-end production systems (65+ ppm)",
            }

    # e-STUDIO AC/AM/AS/CP (Office MFP with suffixes)
    match = re.match(r"^E-STUDIO\s+(\d{4})(AC|AM|AS|CP)$", model_clean)
    if match:
        series_num = match.group(1)
        suffix = match.group(2)
        series_digit = series_num[0]

        suffix_desc = {"AC": "color", "AM": "monochrome", "AS": "standard", "CP": "compact"}.get(suffix, "")

        return {
            "series_name": "e-STUDIO",
            "model_pattern": f"e-STUDIO {series_digit}xxx{suffix}",
            "series_description": f"Toshiba e-STUDIO {series_digit}xxx{suffix} series {suffix_desc} MFPs",
        }

    # e-STUDIO with A suffix (e-STUDIO 306, 2303A, 5008A)
    match = re.match(r"^E-STUDIO\s+(\d{3,4})A?$", model_clean)
    if match:
        series_num = match.group(1)
        series_digit = series_num[0]
        return {
            "series_name": "e-STUDIO",
            "model_pattern": f"e-STUDIO {series_digit}xxx",
            "series_description": f"Toshiba e-STUDIO {series_digit}xxx series MFPs/printers",
        }

    # e-STUDIO Hybrid (Paper recycling)
    if re.match(r"^E-STUDIO\s+HYBRID", model_clean):
        return {
            "series_name": "e-STUDIO Hybrid",
            "model_pattern": "e-STUDIO Hybrid",
            "series_description": "Toshiba e-STUDIO Hybrid series with paper recycling technology",
        }

    # ===== PRIORITY 2: Legacy Series =====

    # Pagelaser series
    match = re.match(r"^PAGELASER\s+([A-Z]{0,2}\s?\d{3})$", model_clean)
    if match:
        return {
            "series_name": "Pagelaser",
            "model_pattern": "Pagelaser",
            "series_description": "Toshiba Pagelaser series printers (legacy)",
        }

    # PAL series
    match = re.match(r"^PAL\s+(\d{3})$", model_clean)
    if match:
        return {
            "series_name": "PAL Series",
            "model_pattern": "PAL",
            "series_description": "Toshiba PAL series printers (legacy)",
        }

    # Spot series
    match = re.match(r"^SPOT\s+(\d{1})$", model_clean)
    if match:
        return {
            "series_name": "Spot Series",
            "model_pattern": "Spot",
            "series_description": "Toshiba Spot series printers (legacy)",
        }

    # T series
    match = re.match(r"^T-(\d{3})$", model_clean)
    if match:
        return {
            "series_name": "T Series",
            "model_pattern": "T",
            "series_description": "Toshiba T series printers (legacy)",
        }

    # TF/TF-P series
    match = re.match(r"^TF(-P)?\s?(\d{3})$", model_clean)
    if match:
        series_type = match.group(1)
        if series_type:
            return {
                "series_name": "TF-P Series",
                "model_pattern": "TF-P",
                "series_description": "Toshiba TF-P series printers (legacy)",
            }
        return {
            "series_name": "TF Series",
            "model_pattern": "TF",
            "series_description": "Toshiba TF series printers (legacy)",
        }

    return None


def _detect_generic_series(model_number: str) -> dict | None:
    """Generic series detection fallback"""
    model = model_number.upper()

    # Try to extract first 2-3 digits/letters
    match = re.match(r"([A-Z]{0,2}\d{1,2})", model)
    if match:
        series_code = match.group(1)
        return {
            "series_name": f"{series_code}xx Series",
            "series_code": f"{series_code}XX",
            "series_description": f"{series_code} series products",
        }

    return None


if __name__ == "__main__":
    # Test
    test_cases = [
        ("M479fdw", "HP"),
        ("X580", "HP"),
        ("C454e", "Konica Minolta"),
        ("MP C2004", "Ricoh"),
        ("MFC-L2750DW", "Brother"),
    ]

    for model, mfr in test_cases:
        result = detect_series(model, mfr)
        print(f"{mfr} {model}: {result}")
