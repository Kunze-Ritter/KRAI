#!/usr/bin/env python3
"""
Manufacturer Normalization Service
Prevents duplicate manufacturers due to variations in naming
"""

import logging
import re


class ManufacturerNormalizationService:
    """
    Service to normalize manufacturer names and prevent duplicates

    Handles:
    - Name variations (HP vs HP Inc. vs Hewlett Packard)
    - Common abbreviations and full names
    - Case-insensitive matching
    - Brand name aliases
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.manufacturer_normalization")

        # Manufacturer normalization mappings
        self.normalization_map = {
            # HP variations
            "hp": "HP Inc.",
            "h.p.": "HP Inc.",
            "hewlett packard": "HP Inc.",
            "hewlett-packard": "HP Inc.",
            "hewlett_packard": "HP Inc.",
            "hp inc.": "HP Inc.",
            "hp inc": "HP Inc.",
            "hp incorporated": "HP Inc.",
            # Konica Minolta variations
            "konica minolta": "Konica Minolta",
            "konica-minolta": "Konica Minolta",
            "konica_minolta": "Konica Minolta",
            "km": "Konica Minolta",
            "k-m": "Konica Minolta",
            "konica": "Konica Minolta",
            "minolta": "Konica Minolta",
            # Canon variations
            "canon": "Canon Inc.",
            "canon inc.": "Canon Inc.",
            "canon inc": "Canon Inc.",
            "canon incorporated": "Canon Inc.",
            # Lexmark variations
            "lexmark": "Lexmark International",
            "lexmark international": "Lexmark International",
            "lexmark intl.": "Lexmark International",
            "lexmark intl": "Lexmark International",
            # Xerox variations
            "xerox": "Xerox Corporation",
            "xerox corp.": "Xerox Corporation",
            "xerox corp": "Xerox Corporation",
            "xerox corporation": "Xerox Corporation",
            # UTAX variations
            "utax": "UTAX",
            "utax technologies": "UTAX",
            "utax tech": "UTAX",
            # Brother variations
            "brother": "Brother Industries",
            "brother industries": "Brother Industries",
            "brother intl.": "Brother Industries",
            # Samsung variations
            "samsung": "Samsung Electronics",
            "samsung electronics": "Samsung Electronics",
            "samsung techwin": "Samsung Electronics",
            # Epson variations
            "epson": "Seiko Epson Corporation",
            "seiko epson": "Seiko Epson Corporation",
            "seiko-epson": "Seiko Epson Corporation",
        }

        # Brand aliases (common misspellings and variations)
        self.brand_aliases = {
            "hewlett": "HP Inc.",
            "packard": "HP Inc.",
            "km": "Konica Minolta",
            "konicaminolta": "Konica Minolta",
            "konikaminolta": "Konica Minolta",
        }

    def normalize_manufacturer_name(self, manufacturer_name: str) -> str:
        """
        Normalize manufacturer name to prevent duplicates

        Args:
            manufacturer_name: Raw manufacturer name from document

        Returns:
            Normalized manufacturer name
        """
        if not manufacturer_name:
            return "Unknown"

        # Clean and normalize input
        cleaned_name = self._clean_manufacturer_name(manufacturer_name)

        # Check direct mapping
        if cleaned_name in self.normalization_map:
            normalized = self.normalization_map[cleaned_name]
            self.logger.info(f"Normalized '{manufacturer_name}' -> '{normalized}'")
            return normalized

        # Check brand aliases
        if cleaned_name in self.brand_aliases:
            normalized = self.brand_aliases[cleaned_name]
            self.logger.info(f"Normalized '{manufacturer_name}' -> '{normalized}' (alias)")
            return normalized

        # Fuzzy matching for partial matches
        fuzzy_match = self._fuzzy_match_manufacturer(cleaned_name)
        if fuzzy_match:
            self.logger.info(f"Normalized '{manufacturer_name}' -> '{fuzzy_match}' (fuzzy)")
            return fuzzy_match

        # If no match found, return title-cased version
        normalized = manufacturer_name.title()
        self.logger.info(f"No normalization found for '{manufacturer_name}', using '{normalized}'")
        return normalized

    def _clean_manufacturer_name(self, name: str) -> str:
        """Clean manufacturer name for comparison"""
        if not name:
            return ""

        # Convert to lowercase
        cleaned = name.lower().strip()

        # Remove common suffixes and prefixes
        suffixes_to_remove = [
            "inc.",
            "inc",
            "incorporated",
            "corp.",
            "corp",
            "corporation",
            "ltd.",
            "ltd",
            "limited",
            "llc",
            "gmbh",
            "ag",
            "s.a.",
            "s.a",
            "co.",
            "co",
            "company",
            "technologies",
            "tech",
            "international",
            "intl.",
            "intl",
            "electronics",
            "systems",
            "solutions",
        ]

        for suffix in suffixes_to_remove:
            if cleaned.endswith(" " + suffix) or cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()

        # Remove extra whitespace and special characters
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"[^\w\s-]", "", cleaned)

        return cleaned

    def _fuzzy_match_manufacturer(self, name: str) -> str | None:
        """Fuzzy match manufacturer name"""
        if not name:
            return None

        # Check if any normalized name contains the input name
        for normalized_name, canonical_name in self.normalization_map.items():
            if name in normalized_name or normalized_name in name:
                return canonical_name

        # Check for partial word matches
        name_words = name.split()
        for word in name_words:
            if len(word) >= 3:  # Only check words with 3+ characters
                for normalized_name, canonical_name in self.normalization_map.items():
                    if word in normalized_name:
                        return canonical_name

        return None

    def get_all_normalized_manufacturers(self) -> list[str]:
        """Get list of all normalized manufacturer names"""
        return list(set(self.normalization_map.values()))


# Model and Series Detection Service
class ModelDetectionService:
    """
    Service to detect and extract all product models from documents

    Handles:
    - Multiple model detection (not just filename)
    - Option detection
    - Series detection
    - Model variations and aliases
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.model_detection")

        # Common model patterns for different manufacturers
        self.model_patterns = {
            "hp": [
                r"HP\s+([A-Z]+\d+[A-Z]*)",  # HP M404dn
                r"LaserJet\s+Pro\s+([A-Z]+\d+[A-Z]*)",  # LaserJet Pro M404dn
                r"Deskjet\s+([A-Z]+\d+[A-Z]*)",  # Deskjet 2755e
                r"Officejet\s+Pro\s+([A-Z]+\d+[A-Z]*)",  # Officejet Pro 9015e
                r"([A-Z]\d{3}[A-Z]?\w*)",  # M404dn pattern
                r"([A-Z]{2,}\d{2,}[A-Z]?\d*)",  # General HP pattern
            ],
            "konica minolta": [
                r"Bizhub\s+([A-Z]+\d+[A-Z]*)",  # Bizhub C258
                r"Accurio\s+([A-Z]+\d+[A-Z]*)",  # Accurio C3080
                r"([A-Z]{2,}\d{3,}[A-Z]?\d*)",  # General KM pattern
            ],
            "canon": [
                r"imageCLASS\s+([A-Z]+\d+[A-Z]*)",  # imageCLASS LBP6030
                r"PIXMA\s+([A-Z]+\d+[A-Z]*)",  # PIXMA G7020
                r"MAXIFY\s+([A-Z]+\d+[A-Z]*)",  # MAXIFY MB2720
                r"([A-Z]{2,}\d{3,}[A-Z]?\d*)",  # General Canon pattern
            ],
            "lexmark": [
                r"([A-Z]{2,}\d{2,}[A-Z]?\d*)",  # General Lexmark pattern
            ],
            "xerox": [
                r"WorkCentre\s+([A-Z]+\d+[A-Z]*)",  # WorkCentre 6515
                r"Phaser\s+([A-Z]+\d+[A-Z]*)",  # Phaser 6510
                r"([A-Z]{2,}\d{3,}[A-Z]?\d*)",  # General Xerox pattern
            ],
        }

        # Series patterns
        self.series_patterns = [
            r"(LaserJet\s+[A-Z]+)",  # LaserJet Pro
            r"(Deskjet\s+[A-Z]+)",  # Deskjet Plus
            r"(Officejet\s+[A-Z]+)",  # Officejet Pro
            r"(Bizhub\s+[A-Z]+)",  # Bizhub C
            r"(imageCLASS\s+[A-Z]+)",  # imageCLASS LBP
            r"(WorkCentre\s+[A-Z]+)",  # WorkCentre 6
            r"(Phaser\s+[A-Z]+)",  # Phaser 6
        ]

    def extract_all_models(self, text: str, manufacturer: str) -> list[str]:
        """
        Extract all models from document text

        Args:
            text: Document text content
            manufacturer: Normalized manufacturer name

        Returns:
            List of detected model numbers
        """
        if not text or not manufacturer:
            return []

        models = set()
        manufacturer_lower = manufacturer.lower()

        # Get patterns for manufacturer
        patterns = []
        for mfg_key, mfg_patterns in self.model_patterns.items():
            if mfg_key in manufacturer_lower:
                patterns.extend(mfg_patterns)

        # If no specific patterns, use general patterns
        if not patterns:
            patterns = [r"([A-Z]{2,}\d{2,}[A-Z]?\d*)"]

        # Extract models using patterns
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]

                # Clean and validate model
                cleaned_model = self._clean_model_name(match)
                if self._is_valid_model(cleaned_model):
                    models.add(cleaned_model)

        # Extract from common model mentions
        models.update(self._extract_model_mentions(text))

        result = list(models)
        self.logger.info(f"Extracted {len(result)} models for {manufacturer}: {result}")
        return result

    def extract_series(self, text: str, manufacturer: str) -> str:
        """
        Extract product series from document text

        Args:
            text: Document text content
            manufacturer: Normalized manufacturer name

        Returns:
            Detected series name or "Unknown"
        """
        if not text or not manufacturer:
            return "Unknown"

        # Try series patterns
        for pattern in self.series_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                series = matches[0].strip()
                self.logger.info(f"Detected series '{series}' for {manufacturer}")
                return series

        # Try to extract from common series mentions
        series_mentions = [
            "LaserJet Pro",
            "LaserJet Enterprise",
            "LaserJet Enterprise",
            "Deskjet Plus",
            "Deskjet Ink Advantage",
            "Officejet Pro",
            "Officejet Enterprise",
            "Bizhub C",
            "Bizhub PRO",
            "imageCLASS LBP",
            "imageCLASS D",
            "WorkCentre",
            "Phaser",
        ]

        for mention in series_mentions:
            if mention.lower() in text.lower():
                self.logger.info(f"Detected series '{mention}' for {manufacturer}")
                return mention

        return "Unknown"

    def _clean_model_name(self, model: str) -> str:
        """Clean model name"""
        if not model:
            return ""

        # Remove common prefixes and suffixes
        cleaned = model.strip()
        cleaned = re.sub(r"^[A-Z]{2,}\s+", "", cleaned)  # Remove HP, KM prefixes
        cleaned = re.sub(r"\s+[A-Z]{2,}$", "", cleaned)  # Remove suffixes
        cleaned = re.sub(r"[^\w\d-]", "", cleaned)  # Keep only alphanumeric and dashes

        return cleaned.upper()

    def _is_valid_model(self, model: str) -> bool:
        """Check if model name is valid"""
        if not model or len(model) < 3:
            return False

        # Must contain at least one letter and one digit
        has_letter = bool(re.search(r"[A-Z]", model))
        has_digit = bool(re.search(r"\d", model))

        return has_letter and has_digit

    def _extract_model_mentions(self, text: str) -> set:
        """Extract models from common mentions"""
        models = set()

        # Look for model numbers in various formats
        patterns = [
            r"\(([A-Z]\d{3}[A-Z]?\w*)\)",  # (M404dn)
            r":\s*([A-Z]\d{3}[A-Z]?\w*)",  # : M404dn
            r"model[s]?\s+([A-Z]\d{3}[A-Z]?\w*)",  # model M404dn
            r"- ([A-Z]\d{3}[A-Z]?\w*)",  # - M404dn
            r"([A-Z]\d{3}[A-Z]?\w*)\s*\(",  # M404dn (
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = self._clean_model_name(match)
                if self._is_valid_model(cleaned):
                    models.add(cleaned)

        return models
