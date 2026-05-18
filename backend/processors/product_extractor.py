"""
Product Model Extraction Module

Extracts product model numbers from PDFs with strict validation.
NO filenames, ONLY real product models!

Now uses manufacturer-specific YAML configs for patterns.
"""

import re
from pathlib import Path

from backend.constants.product_types import ALLOWED_PRODUCT_TYPES
from backend.utils.manufacturer_config import get_manufacturer_config
from backend.utils.manufacturer_normalizer import normalize_manufacturer

from .logger import get_logger
from .models import ExtractedProduct
from .models import ValidationError as ValError

logger = get_logger()

DEFAULT_PRODUCT_TYPE = (
    "laser_multifunction" if "laser_multifunction" in ALLOWED_PRODUCT_TYPES else sorted(ALLOWED_PRODUCT_TYPES)[0]
)


# HP Product Model Patterns
HP_PATTERNS = {
    "laserjet": re.compile(
        r"\b(?:Color\s+)?LaserJet\s+(?:Pro\s+|Enterprise\s+|Managed\s+|Flow\s+)?"
        r"(?:MFP\s+)?[A-Z]?\d{3,5}[a-z]{0,3}(?:\s*[a-z]{1,3})?\b",
        re.IGNORECASE,
    ),
    "officejet": re.compile(r"\bOfficeJet\s+(?:Pro\s+)?[A-Z]?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "designjet": re.compile(r"\bDesignJet\s+[A-Z]?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "pagewide": re.compile(r"\bPageWide\s+(?:Pro\s+|Enterprise\s+)?[A-Z]?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "simple_model": re.compile(r"\b[EM]\d{3,5}[a-z]{0,2}\b"),  # E877, E87740, M455, etc.
}

# Canon Patterns
CANON_PATTERNS = {
    "imagerunner": re.compile(r"\bimageRUNNER\s+(?:ADVANCE\s+)?(?:DX\s+)?[A-Z]?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "pixma": re.compile(r"\bPIXMA\s+[A-Z]{2}\d{3,4}\b", re.IGNORECASE),
    "imageclass": re.compile(r"\bimageCLASS\s+(?:MF|LBP|D)\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
}

# Konica Minolta Patterns
KONICA_MINOLTA_PATTERNS = {
    "accuriopress": re.compile(r"\bAccurioPress\s+C\d{4}(?:P|hc)?\b", re.IGNORECASE),
    "accurioprint": re.compile(r"\bAccurioPrint\s+C\d{4}(?:P)?\b", re.IGNORECASE),
    "bizhub": re.compile(r"\bbizhub\s+(?:C|PRESS\s+)?C?\d{3,4}[a-z]{0,2}\b", re.IGNORECASE),
    "c_series": re.compile(
        r"\bC\d{3,4}[a-z]{0,2}\b"  # C750i, C751i, C4080, C4070, C84hc (3-4 digits + optional letters)
    ),
}

# Ricoh Patterns
RICOH_PATTERNS = {
    "aficio": re.compile(r"\bAficio\s+(?:MP|SP)\s?\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
    "pro_c": re.compile(r"\bPro\s+C\d{3,4}[a-z]{0,2}\b", re.IGNORECASE),
    "im_c": re.compile(r"\bIM\s+C\d{3,4}[A-Z]{0,2}\b", re.IGNORECASE),
}

# Xerox Patterns
XEROX_PATTERNS = {
    "workcentre": re.compile(r"\bWorkCentre\s+\d{3,4}[a-z]{0,2}\b", re.IGNORECASE),
    "versalink": re.compile(r"\bVersaLink\s+[CB]\d{3,4}\b", re.IGNORECASE),
    "altalink": re.compile(r"\bAltaLink\s+[CB]\d{3,4}\b", re.IGNORECASE),
    "phaser": re.compile(r"\bPhaser\s+\d{3,4}[A-Z]{0,2}\b", re.IGNORECASE),
}

# Kyocera Patterns
KYOCERA_PATTERNS = {
    "ecosys": re.compile(r"\bECOSYS\s+[PM]\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "taskalfa": re.compile(r"\bTASKalfa\s+\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "fs_series": re.compile(r"\bFS-\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
    "km_series": re.compile(r"\bKM-\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
}

# UTAX Patterns (Kyocera rebrand)
UTAX_PATTERNS = {
    "p_series": re.compile(r"\bP-\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "cd_series": re.compile(r"\bCD\s?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "cdc_series": re.compile(r"\bCDC\s?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
    "lp_series": re.compile(r"\bLP\s?\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),
}

# Brother Patterns
BROTHER_PATTERNS = {
    "mfc": re.compile(r"\bMFC-[LJ]?\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
    "hl": re.compile(r"\bHL-[LJ]?\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
    "dcp": re.compile(r"\bDCP-[LJ]?\d{3,4}[A-Z]{0,3}\b", re.IGNORECASE),
}

# Epson Patterns
EPSON_PATTERNS = {
    "workforce": re.compile(r"\bWorkForce\s+(?:Pro\s+)?[A-Z]{2,3}-\d{3,4}\b", re.IGNORECASE),
    "ecotank": re.compile(r"\bEcoTank\s+[A-Z]{1,2}\d{3,4}\b", re.IGNORECASE),
}

# Sharp Patterns
SHARP_PATTERNS = {
    "mx": re.compile(r"\bMX-[A-Z]?\d{3,4}[A-Z]{0,2}\b", re.IGNORECASE),
}

# Lexmark Patterns
LEXMARK_PATTERNS = {
    "cx": re.compile(r"\bCX\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),  # CX833, CX961, CX962, CX963
    "xc": re.compile(r"\bXC\d{4}[a-z]{0,3}\b", re.IGNORECASE),  # XC8355, XC9635, XC9645
    "mx": re.compile(r"\bMX\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),  # MX321, MX421, MX521, MX622
    "ms": re.compile(r"\bMS\d{3,4}[a-z]{0,3}\b", re.IGNORECASE),  # MS321, MS421, MS521, MS622
    "mb": re.compile(r"\bMB\d{4}[a-z]{0,3}\b", re.IGNORECASE),  # MB2236, MB2338, MB2442, MB2546
    "b": re.compile(r"\bB\d{4}[a-z]{0,3}\b", re.IGNORECASE),  # B2236, B2338, B2442, B2546
    "c": re.compile(r"\bC\d{4}[a-z]{0,3}\b", re.IGNORECASE),  # C2132, C2240, C2325, C2425
}

# All patterns by manufacturer
ALL_MANUFACTURER_PATTERNS = {
    "HP": HP_PATTERNS,
    "CANON": CANON_PATTERNS,
    "KONICA MINOLTA": KONICA_MINOLTA_PATTERNS,
    "RICOH": RICOH_PATTERNS,
    "XEROX": XEROX_PATTERNS,
    "KYOCERA": KYOCERA_PATTERNS,
    "UTAX": UTAX_PATTERNS,
    "BROTHER": BROTHER_PATTERNS,
    "EPSON": EPSON_PATTERNS,
    "SHARP": SHARP_PATTERNS,
    "LEXMARK": LEXMARK_PATTERNS,
}

# Words to REJECT (not product models)
REJECT_WORDS = {
    "page",
    "chapter",
    "section",
    "figure",
    "table",
    "error",
    "code",
    "step",
    "note",
    "warning",
    "caution",
    "procedure",
    "manual",
    "document",
    "revision",
    "version",
    "edition",
    "copyright",
    "trademark",
    "contents",
    "index",
    "appendix",
    "glossary",
    "troubleshooting",
    "specifications",
    "features",
    "overview",
}


class ProductExtractor:
    """Extract product models with validation"""

    def __init__(self, manufacturer_name: str = "HP", debug: bool = False, document_title: str | None = None):
        """
        Initialize product extractor

        Args:
            manufacturer_name: Manufacturer name (HP, Canon, etc.)
            debug: Enable debug logging
            document_title: PDF title for context-based series extraction
        """
        self.raw_manufacturer_name = manufacturer_name
        self.canonical_manufacturer = None
        if manufacturer_name and manufacturer_name != "AUTO":
            self.canonical_manufacturer = normalize_manufacturer(manufacturer_name) or manufacturer_name

        self.manufacturer_name = self.canonical_manufacturer or manufacturer_name
        self.debug = debug
        self.document_title = document_title
        self.context_series = self._extract_series_from_title(document_title) if document_title else []
        self.logger = get_logger()

        # Load manufacturer-specific config
        self.config = None
        self.compiled_patterns = []
        self.reject_patterns = []

        if self.canonical_manufacturer and self.canonical_manufacturer != "AUTO":
            self.config = get_manufacturer_config(self.canonical_manufacturer)
            if not self.config:
                # Fallback: try raw manufacturer string for legacy configs
                self.config = get_manufacturer_config(manufacturer_name)
            if self.config:
                self.compiled_patterns = self.config.get_compiled_patterns()
                self.reject_patterns = self.config.get_reject_patterns()
                if self.debug:
                    self.logger.info(
                        f"✓ Loaded config for {self.config.canonical_name}: {len(self.compiled_patterns)} patterns"
                    )
            else:
                if self.debug:
                    self.logger.warning(f"⚠️  No config found for {manufacturer_name}, using legacy patterns")

        if self.context_series and self.debug:
            self.logger.debug(f"Detected series from title: {self.context_series}")

    def extract_from_text(self, text: str, page_number: int = 1, filename: str | None = None) -> list[ExtractedProduct]:
        """
        Extract product models from text

        Args:
            text: Text to extract from
            page_number: Page number (for metadata)
            filename: Optional filename for fallback extraction when content yields no results

        Returns:
            List of validated ExtractedProduct
        """
        if not text or len(text) < 10:
            return []

        found_models = []

        # Use config patterns if available
        if self.config and self.compiled_patterns:
            # Log pattern usage sparingly to avoid noisy output
            if self.debug:
                self.logger.debug(
                    f"🔍 Using {len(self.compiled_patterns)} patterns from {self.config.canonical_name} config"
                )
            elif page_number == 1:
                self.logger.info(
                    f"🔍 Using {len(self.compiled_patterns)} patterns from {self.config.canonical_name} config"
                )
            # Use manufacturer-specific config patterns
            for series_name, pattern, product_type in self.compiled_patterns:
                matches = pattern.finditer(text)

                for match in matches:
                    model = match.group(0).strip()

                    # Check reject patterns first
                    rejected = False
                    for reject_pattern in self.reject_patterns:
                        if reject_pattern.match(model):
                            if self.debug:
                                self.logger.info(f"✗ Rejected by pattern: '{model}'")
                            rejected = True
                            break

                    if rejected:
                        continue

                    if self.debug:
                        self.logger.info(f"✓ Pattern '{series_name}' matched: '{model}'")

                    # Validate
                    if self._validate_model(model):
                        # Calculate confidence
                        confidence = self._calculate_confidence(model, text, match.start(), series_name)

                        if self.debug:
                            self.logger.info(f"  ✓ Validated! Confidence: {confidence:.2f}")

                        # Use product_type from config (normalize against shared allow list)
                        normalized_product_type = self._ensure_allowed_product_type(
                            product_type, source=f"pattern '{series_name}'"
                        )
                        try:
                            product = ExtractedProduct(
                                model_number=model,
                                product_series=series_name,
                                product_type=normalized_product_type,
                                manufacturer_name=self.config.canonical_name,
                                confidence=confidence,
                                source_page=page_number,
                                extraction_method=f"regex_config_{series_name}",
                            )
                            found_models.append(product)
                            if self.debug:
                                self.logger.success(f"  ✅ Added: {model}")
                        except Exception as e:
                            if self.debug:
                                self.logger.error(f"  ✗ Pydantic validation failed: {e}")
                    else:
                        if self.debug:
                            self.logger.warning(f"  ✗ Rejected by validation: {model}")
        else:
            # Fallback to legacy patterns if no config
            if self.debug:
                self.logger.warning("⚠️  Using legacy pattern extraction (no config loaded)")
            # Keep old code as fallback
            pass

        # Deduplicate
        unique_models = self._deduplicate(found_models)

        # FALLBACK: If no products found from content and filename provided, try filename extraction
        if not unique_models and filename:
            if self.debug:
                self.logger.debug(f"No products from content, attempting filename fallback: {filename}")
            filename_products = self.extract_from_filename(filename)
            if filename_products:
                self.logger.info(f"Extracted {len(filename_products)} products from filename fallback")
                unique_models = filename_products

        if unique_models:
            if page_number in {0, -1}:
                # Keep prominent logs for filename/title extraction
                self.logger.info(f"Extracted {len(unique_models)} unique products from page {page_number}")
            else:
                # Downgrade regular page spam to debug
                self.logger.debug(f"Extracted {len(unique_models)} unique products from page {page_number}")

        return unique_models

    def extract_from_first_page(self, first_page_text: str) -> ExtractedProduct | None:
        """
        Extract primary product model from first page

        Args:
            first_page_text: Text from first page

        Returns:
            Primary product model or None
        """
        products = self.extract_from_text(first_page_text, page_number=1)

        if not products:
            return None

        # Return highest confidence product
        products.sort(key=lambda p: p.confidence, reverse=True)
        return products[0]

    def _parse_filename_segments(self, filename: str) -> dict[str, any]:
        """
        Parse filename into segments for model extraction

        Parses structured filenames like:
        - HP_E475_SM.pdf -> {manufacturer_prefix: 'HP', model_candidates: ['E475'], doc_type: 'SM'}
        - KM_C759_C659_FW4.1_SM.pdf -> {manufacturer_prefix: 'KM', model_candidates: ['C759', 'C659'], doc_type: 'SM'}
        - CANON_iR_ADV_C5550i_Manual.pdf -> {manufacturer_prefix: 'CANON', model_candidates: ['iR', 'ADV', 'C5550i'], doc_type: 'Manual'}

        Args:
            filename: Filename to parse

        Returns:
            Dictionary with manufacturer_prefix, model_candidates, doc_type
        """
        # Remove file extension
        stem = Path(filename).stem

        # Split by underscore and hyphen
        segments = re.split(r"[_-]", stem)

        # Clean segments: remove empty, normalize case
        segments = [seg.strip() for seg in segments if seg.strip()]

        # Known manufacturer prefixes
        manufacturer_prefixes = [
            "HP",
            "KM",
            "CANON",
            "RICOH",
            "XEROX",
            "BROTHER",
            "LEXMARK",
            "SHARP",
            "EPSON",
            "KYOCERA",
            "FUJIFILM",
            "FUJI",
            "RISO",
            "TOSHIBA",
            "OKI",
            "UTAX",
        ]

        # Known document type suffixes
        doc_type_suffixes = [
            "SM",
            "CPMD",
            "MANUAL",
            "GUIDE",
            "FW",
            "FIRMWARE",
            "DRIVER",
            "PARTS",
            "SERVICE",
            "USER",
            "INSTALL",
            "SETUP",
        ]

        manufacturer_prefix = None
        doc_type = None
        model_candidates = []

        # Identify manufacturer prefix (first segment if matches)
        if segments and segments[0].upper() in manufacturer_prefixes:
            manufacturer_prefix = segments[0].upper()
            segments = segments[1:]  # Remove manufacturer from candidates

        # Identify document type suffix (last segment if matches)
        if segments and segments[-1].upper() in doc_type_suffixes:
            doc_type = segments[-1].upper()
            segments = segments[:-1]  # Remove doc type from candidates

        # Remaining segments are model candidates
        # Filter out version patterns like FW4.1, V1.0, etc.
        for seg in segments:
            seg_upper = seg.upper()
            # Skip if looks like version (starts with FW, V, VER followed by number)
            if re.match(r"^(FW|V|VER|VERSION)\d", seg_upper):
                continue
            # Skip if pure version number like 4.1, 1.0
            if re.match(r"^\d+\.\d+$", seg):
                continue
            # Skip if too short (likely not a model)
            if len(seg) < 2:
                continue
            model_candidates.append(seg)

        return {"manufacturer_prefix": manufacturer_prefix, "model_candidates": model_candidates, "doc_type": doc_type}

    def extract_from_filename(self, filename: str) -> list[ExtractedProduct]:
        """
        Extract product models from structured filename patterns

        This is a FALLBACK mechanism with lower confidence than content-based extraction.
        Only use when content extraction fails.

        Examples:
        - HP_E475_SM.pdf -> Extract: E475
        - KM_C759_C659_FW4.1_SM.pdf -> Extract: C759, C659
        - CANON_iR_ADV_C5550i_Manual.pdf -> Extract: C5550i

        Args:
            filename: Filename to parse

        Returns:
            List of ExtractedProduct objects with confidence 0.3-0.5
        """
        self.logger.debug("Attempting filename parsing for models")

        # Parse filename into segments
        parsed = self._parse_filename_segments(filename)

        if not parsed["model_candidates"]:
            self.logger.debug("Filename parsing yielded no valid models")
            return []

        extracted_products = []

        for model_candidate in parsed["model_candidates"]:
            # Validate model using existing validation
            if not self._validate_model(model_candidate):
                self.logger.warning(f"Rejected invalid model from filename: {model_candidate}")
                continue

            # Determine product type and series
            product_type = self._determine_product_type(model_candidate, "filename_parsing")
            product_series = self._determine_product_series(model_candidate, "filename_parsing")

            # Create ExtractedProduct with lower confidence
            try:
                product = ExtractedProduct(
                    model_number=model_candidate,
                    manufacturer_name=self.manufacturer_name,
                    confidence=0.4,  # Lower than content-based extraction
                    source_page=-1,  # Indicates filename source
                    extraction_method="filename_parsing",
                    product_type=product_type,
                    product_series=product_series,
                )
                extracted_products.append(product)
            except Exception as e:
                self.logger.warning(f"Failed to create product from filename model {model_candidate}: {e}")
                continue

        if extracted_products:
            self.logger.info(
                f"Extracted {len(extracted_products)} models from filename: {[p.model_number for p in extracted_products]}"
            )
        else:
            self.logger.debug("Filename parsing yielded no valid models")

        return extracted_products

    def _validate_model(self, model: str) -> bool:
        """
        Validate that model is a real product, not garbage

        Returns:
            True if valid
        """
        # Length check
        if len(model) < 3 or len(model) > 50:
            return False

        # Not a reject word
        if model.lower() in REJECT_WORDS:
            return False

        # Must have both letters and numbers
        has_letter = any(c.isalpha() for c in model)
        has_digit = any(c.isdigit() for c in model)

        if not (has_letter and has_digit):
            return False

        # Must NOT look like a filename
        if any(char in model for char in [".", "_", "/", "\\", ":", "*", "?"]):
            return False

        # Not all caps filename pattern (e.g., "COLORLJM480M")
        if len(model) > 12 and model.isupper() and " " not in model:
            return False

        return True

    def _calculate_confidence(self, model: str, full_text: str, position: int, pattern_name: str) -> float:
        """
        Calculate extraction confidence

        Returns:
            Confidence score (0.0 - 1.0)
        """
        confidence = 0.6  # Base confidence

        # Bonus for specific patterns
        if pattern_name in ["laserjet", "officejet", "designjet", "pagewide"]:
            confidence += 0.2  # High confidence for full product names

        # Bonus if appears multiple times
        appearances = full_text.count(model)
        if appearances > 1:
            confidence += 0.1
        if appearances > 3:
            confidence += 0.1

        # Bonus if near certain keywords
        context_start = max(0, position - 100)
        context_end = min(len(full_text), position + 100)
        context = full_text[context_start:context_end].lower()

        if any(kw in context for kw in ["model", "product", "printer", "scanner"]):
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)

    def _determine_product_series(self, model: str, pattern_name: str) -> str | None:
        """
        Determine product series from pattern name, model, and document context

        Priority:
        1. Series in model name (e.g., "AccurioPress C4080")
        2. Pattern name mapping
        3. Context from document title

        Returns:
            Product series name or None
        """
        # Map pattern names to series names
        series_mapping = {
            "laserjet": "LaserJet",
            "officejet": "OfficeJet",
            "designjet": "DesignJet",
            "pagewide": "PageWide",
            "accuriopress": "AccurioPress",
            "accurioprint": "AccurioPrint",
            "bizhub": "bizhub",
            "imagerunner": "imageRUNNER",
            "imageclass": "imageCLASS",
            "pixma": "PIXMA",
            "aficio": "Aficio",
            "pro_c": "Pro C",
            "im_c": "IM C",
            "workcentre": "WorkCentre",
            "versalink": "VersaLink",
            "altalink": "AltaLink",
            "phaser": "Phaser",
            "ecosys": "ECOSYS",
            "taskalfa": "TASKalfa",
            "c_series": None,  # Bare model number - use context
        }

        # 1. First check if series is already in the model name
        model_lower = model.lower()
        for pattern, series in series_mapping.items():
            if series and pattern.replace("_", "").lower() in model_lower.replace(" ", "").lower():
                return series

        # 2. Use pattern name mapping
        series_from_pattern = series_mapping.get(pattern_name)
        if series_from_pattern:
            return series_from_pattern

        # 3. Fall back to context from document title (for bare models like "C4080")
        if self.context_series:
            # If only one series in title, use it
            if len(self.context_series) == 1:
                if self.debug:
                    self.logger.debug(f"  Using context series: {self.context_series[0]}")
                return self.context_series[0]

            # If multiple series, match by model number pattern
            matched_series = self._match_series_by_model_pattern(model, self.context_series)
            if matched_series:
                if self.debug:
                    self.logger.debug(f"  Matched series by pattern: {matched_series}")
                return matched_series

        return None

    def _determine_product_type(self, model: str, pattern_name: str) -> str:
        """
        Determine product type from model name

        Returns:
            Specific product type matching DB constraint (e.g., laser_printer, inkjet_printer, laser_multifunction)
        """
        model_lower = model.lower()

        # Check for plotters first
        if "designjet" in model_lower:
            if "latex" in model_lower:
                return self._ensure_allowed_product_type("latex_plotter", source="model heuristic")
            if "inkjet" in model_lower:
                return self._ensure_allowed_product_type("inkjet_plotter", source="model heuristic")
            return self._ensure_allowed_product_type("inkjet_plotter", source="model heuristic")

        # Check for multifunction devices
        if any(kw in model_lower for kw in ["mfp", "multifunction", "all-in-one"]):
            # Determine if laser or inkjet
            if any(kw in model_lower for kw in ["laserjet", "laser", "accurio", "bizhub", "imagerunner"]):
                return self._ensure_allowed_product_type("laser_multifunction", source="model heuristic")
            if any(kw in model_lower for kw in ["officejet", "inkjet", "pagewide"]):
                return self._ensure_allowed_product_type("inkjet_multifunction", source="model heuristic")
            return self._ensure_allowed_product_type("laser_multifunction", source="model heuristic")

        # Check for scanners
        if "scanner" in model_lower or "scanjet" in model_lower:
            if "document" in model_lower:
                return self._ensure_allowed_product_type("document_scanner", source="model heuristic")
            if "photo" in model_lower:
                return self._ensure_allowed_product_type("photo_scanner", source="model heuristic")
            return self._ensure_allowed_product_type("scanner", source="model heuristic")

        # Check for copiers
        if "copier" in model_lower:
            return self._ensure_allowed_product_type("copier", source="model heuristic")

        # Default: Determine printer type
        # Check if it's a laser printer
        if any(kw in model_lower for kw in ["laserjet", "laser", "accurio", "bizhub", "imagerunner", "phaser"]):
            return self._ensure_allowed_product_type("laser_printer", source="model heuristic")
        # Check if it's an inkjet printer
        if any(kw in model_lower for kw in ["officejet", "inkjet", "pagewide", "pixma", "workforce"]):
            return self._ensure_allowed_product_type("inkjet_printer", source="model heuristic")
        # Default to laser printer (most common in enterprise)
        return self._ensure_allowed_product_type("laser_printer", source="model heuristic")

    def _ensure_allowed_product_type(self, product_type: str | None, source: str) -> str:
        """Normalize product_type values against shared allow-list."""
        normalized = (product_type or "").strip().lower()
        if normalized in ALLOWED_PRODUCT_TYPES:
            return normalized

        if product_type and product_type in ALLOWED_PRODUCT_TYPES:
            return product_type

        if self.debug:
            self.logger.debug(
                f"[{source}] product_type '{product_type}' not in ALLOWED_PRODUCT_TYPES. "
                f"Falling back to '{DEFAULT_PRODUCT_TYPE}'."
            )
        return DEFAULT_PRODUCT_TYPE

    def _extract_series_from_title(self, title: str | None) -> list[str]:
        """
        Extract product series names from document title

        Args:
            title: Document title (e.g., "AccurioPress_C4080_C4070_AccurioPrint_C4065")

        Returns:
            List of detected series names
        """
        if not title:
            return []

        detected_series = []
        title_lower = title.lower()

        # Known series patterns (case-insensitive)
        series_patterns = {
            "accuriopress": "AccurioPress",
            "accurioprint": "AccurioPrint",
            "bizhub": "bizhub",
            "laserjet": "LaserJet",
            "officejet": "OfficeJet",
            "designjet": "DesignJet",
            "pagewide": "PageWide",
            "imagerunner": "imageRUNNER",
            "imageclass": "imageCLASS",
            "pixma": "PIXMA",
            "aficio": "Aficio",
            "workcentre": "WorkCentre",
            "versalink": "VersaLink",
            "altalink": "AltaLink",
            "phaser": "Phaser",
            "ecosys": "ECOSYS",
            "taskalfa": "TASKalfa",
        }

        for pattern, series_name in series_patterns.items():
            if pattern in title_lower:
                detected_series.append(series_name)

        return detected_series

    def _match_series_by_model_pattern(self, model: str, available_series: list[str]) -> str | None:
        """
        Match model number to series based on known patterns

        Args:
            model: Model number (e.g., "C4080", "C4065")
            available_series: List of possible series from context

        Returns:
            Matched series name or None
        """
        # Model number to series mapping rules
        # Format: series_name -> [list of regex patterns]
        series_patterns = {
            "AccurioPress": [
                r"^C40[78]0",  # C4070, C4080
                r"^C\d{2}hc",  # C74hc, C84hc (any 2-digit + hc)
            ],
            "AccurioPrint": [
                r"^C4065P?",  # C4065, C4065P
            ],
            "bizhub": [
                r"^C\d{3,4}",  # General bizhub C-series
            ],
            "LaserJet": [
                r"^(M|E)\d{3,4}",  # M455, E877, etc.
            ],
            "OfficeJet": [
                r"^Pro\s*\d{4}",  # Pro 9025, etc.
            ],
        }

        # Try to match model against patterns for each available series
        for series_name in available_series:
            if series_name in series_patterns:
                patterns = series_patterns[series_name]
                for pattern in patterns:
                    if re.match(pattern, model, re.IGNORECASE):
                        return series_name

        # If no specific pattern matched, use first series as fallback
        return available_series[0] if available_series else None

    def _deduplicate(self, products: list[ExtractedProduct]) -> list[ExtractedProduct]:
        """
        Remove duplicate products, keep best version

        Strategy:
        - "AccurioPress C4080" and "C4080" are the SAME product
        - Extract bare model number for comparison
        - Prefer bare model (since we have series separately)

        Args:
            products: List of products

        Returns:
            Deduplicated list
        """
        if not products:
            return []

        seen = {}

        for product in products:
            # Extract bare model number (remove series prefix)
            bare_model = self._extract_bare_model(product.model_number)
            key = bare_model.lower()

            if key not in seen:
                seen[key] = product
            else:
                # Keep the one with better quality
                existing = seen[key]

                # Prefer bare model if both have same series
                is_bare = product.model_number == bare_model
                existing_is_bare = existing.model_number == self._extract_bare_model(existing.model_number)

                # Decision priority:
                # 1. Same series? Prefer bare model
                # 2. Higher confidence? Keep that one
                # 3. Has series field? Prefer that one
                if product.product_series == existing.product_series:
                    if is_bare and not existing_is_bare:
                        seen[key] = product  # Replace with bare
                    elif product.confidence > existing.confidence:
                        seen[key] = product
                elif (
                    product.product_series and not existing.product_series
                ) or product.confidence > existing.confidence:
                    seen[key] = product

        return list(seen.values())

    def _extract_bare_model(self, model_number: str) -> str:
        """
        Extract bare model number without series prefix

        Examples:
            "AccurioPress C4080" -> "C4080"
            "LaserJet Pro M455" -> "M455"
            "C4080" -> "C4080"

        Returns:
            Bare model number
        """
        # Remove common series prefixes
        prefixes = [
            "accuriopress",
            "accurioprint",
            "bizhub",
            "laserjet pro",
            "laserjet",
            "officejet pro",
            "officejet",
            "designjet",
            "pagewide",
            "imagerunner",
            "imageclass",
            "pixma",
            "aficio",
            "workcentre",
            "versalink",
            "altalink",
            "phaser",
            "ecosys",
            "taskalfa",
        ]

        model_lower = model_number.lower().strip()

        for prefix in prefixes:
            if model_lower.startswith(prefix):
                # Remove prefix and any following spaces
                bare = model_number[len(prefix) :].strip()
                return bare

        return model_number

    def validate_extraction(self, product: ExtractedProduct) -> list[ValError]:
        """
        Validate extracted product

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check model number format
        if "." in product.model_number or "_" in product.model_number:
            errors.append(
                ValError(
                    field="model_number",
                    value=product.model_number,
                    error_message="Model number contains filename characters",
                    severity="error",
                )
            )

        # Check product type
        if product.product_type not in ALLOWED_PRODUCT_TYPES:
            errors.append(
                ValError(
                    field="product_type",
                    value=product.product_type,
                    error_message=("Invalid product_type, must be one of " f"{sorted(ALLOWED_PRODUCT_TYPES)}"),
                    severity="error",
                )
            )

        return errors


# Convenience function
def extract_products_from_text(text: str, manufacturer: str = "HP", page_number: int = 1) -> list[ExtractedProduct]:
    """
    Convenience function to extract products from text

    Args:
        text: Text to extract from
        manufacturer: Manufacturer name
        page_number: Page number

    Returns:
        List of validated products
    """
    extractor = ProductExtractor(manufacturer_name=manufacturer)
    return extractor.extract_from_text(text, page_number)
