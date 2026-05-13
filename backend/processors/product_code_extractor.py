"""
Product Code Extractor for Konica Minolta
Extracts product codes (first 4 chars) from parts catalogs
"""

import re
from collections import Counter
from typing import Any


class ProductCodeExtractor:
    """
    Extract Konica Minolta product codes from parts catalogs

    Product Code = First 4 characters of serial number (e.g., A93E, AAJN)
    Found in part numbers like: A93E160105, AAJNR70322
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

    def extract_from_parts_catalog(self, parts: list, pdf_metadata: dict[str, Any]) -> dict[str, Any] | None:
        """
        Extract product code and series from parts catalog

        Args:
            parts: List of extracted parts (with part_number)
            pdf_metadata: PDF metadata (title, filename, etc.)

        Returns:
            {
                'product_code': 'A93E',
                'series_name': 'bizhub C3550i',
                'model_number': 'bizhub C3550i',
                'confidence': 0.95
            }
        """
        if not parts:
            return None

        # Extract product codes from part numbers
        product_codes = self._extract_codes_from_parts(parts)

        # If no codes found in parts, try filename/title only
        # This happens with consumables/options catalogs (MK-719, WT-506, etc.)
        if not product_codes:
            filename_code = self._extract_code_from_filename(pdf_metadata.get("filename", ""))
            if filename_code:
                # Validate against title
                title = pdf_metadata.get("title", "").upper()
                if filename_code in title:
                    # Use filename code even without parts validation
                    series_name = self._extract_series_from_metadata(pdf_metadata)
                    return {
                        "product_code": filename_code,
                        "series_name": series_name,
                        "model_number": series_name or filename_code,
                        "confidence": 0.90,  # Good confidence - filename + title match
                        "extraction_method": "filename_title_only",
                    }
            return None  # Really no way to extract code

        # Try to get code from filename first (most reliable!)
        filename_code = self._extract_code_from_filename(pdf_metadata.get("filename", ""))

        # Validate filename code against title
        if filename_code:
            # Check if code appears in title (most reliable!)
            title = pdf_metadata.get("title", "").upper()
            title_match = filename_code in title

            # For Parts Catalogs: Filename/Title match is enough!
            # Parts often contain codes from multiple devices
            if title_match:
                most_common_code = filename_code
                confidence = 0.95  # High confidence - filename AND title match
                if self.debug:
                    print(f"✓ Filename code '{filename_code}' validated by title match")
            else:
                # Filename doesn't match title - check if it's in parts
                parts_match = filename_code in product_codes
                if parts_match:
                    most_common_code = filename_code
                    confidence = 0.85  # Medium confidence - only parts match
                    if self.debug:
                        print(f"✓ Filename code '{filename_code}' validated by parts match")
                else:
                    # Filename code not validated - use most common from parts
                    if self.debug:
                        print(f"⚠ Filename code '{filename_code}' NOT validated - using most common from parts")
                    most_common_code = product_codes.most_common(1)[0][0]
                    confidence = product_codes[most_common_code] / len(parts)
        else:
            # No filename code - use most common from parts
            most_common_code = product_codes.most_common(1)[0][0]
            confidence = product_codes[most_common_code] / len(parts)

        # Extract series name from parts descriptions or labels
        series_name = self._extract_series_from_parts(parts)

        if not series_name:
            # Try from PDF metadata
            series_name = self._extract_series_from_metadata(pdf_metadata)

        return {
            "product_code": most_common_code,
            "series_name": series_name,
            "model_number": series_name or most_common_code,
            "confidence": min(confidence, 0.95),
            "extraction_method": "parts_catalog_analysis",
        }

    def _extract_code_from_filename(self, filename: str) -> str | None:
        """
        Extract product code from filename

        Examples:
        - A93E.pdf → A93E
        - ADXM.pdf → ADXM
        - ACET011.pdf → ACET (first 4 chars)
        """
        if not filename:
            return None

        # Remove extension
        name = filename.replace(".pdf", "").replace(".PDF", "")

        # Try exact 4 character match
        # Pattern: Mix of letters and digits (A93E, ADXM, etc.)
        # Must have at least 1 letter AND 1 digit OR be all letters (ADXM)
        if len(name) == 4 and re.match(r"^[A-Z0-9]{4}$", name):
            has_letter = any(c.isalpha() for c in name)
            if has_letter:  # Valid if has at least one letter
                return name

        # Try first 4 characters
        if len(name) >= 4:
            code = name[:4].upper()
            if re.match(r"^[A-Z0-9]{4}$", code):
                has_letter = any(c.isalpha() for c in code)
                if has_letter:  # Valid if has at least one letter
                    return code

        return None

    def _extract_codes_from_parts(self, parts: list) -> Counter:
        r"""
        Extract product codes from part numbers

        Pattern: First 4 characters if they match [A-Z]{2,4}\d{0,2}
        Examples:
        - A93E160105 → A93E
        - AAJNR70322 → AAJN
        - A797162000 → A797
        """
        codes = Counter()

        for part in parts:
            part_number = part.get("part_number", "") if isinstance(part, dict) else getattr(part, "part_number", "")

            if not part_number or len(part_number) < 4:
                continue

            # Extract first 4 characters
            code = part_number[:4].upper()

            # Validate: Should be letters + optional digits
            # Valid: A93E, AAJN, A797
            # Invalid: 1234, ABCD (too many letters without digits)
            if re.match(r"^[A-Z]{1,3}\d{1,3}$", code):
                codes[code] += 1

        return codes

    def _extract_series_from_parts(self, parts: list) -> str | None:
        """
        Extract series name from part descriptions

        Look for patterns like:
        - "Label bizhub C3550i"
        - "Cover for bizhub C4080"
        """
        series_patterns = [
            r"bizhub\s+(?:PRESS\s+)?C?\d{3,4}[a-z]{0,2}",  # bizhub C3550i, bizhub PRESS C4080
            r"AccurioPress\s+C\d{4}(?:P|hc)?",  # AccurioPress C4080
            r"AccurioPrint\s+C\d{4}(?:P)?",  # AccurioPrint C4070
        ]

        series_found = Counter()

        for part in parts:
            # Support both 'description' and 'part_description' keys
            description = (
                part.get("part_description", "") or part.get("description", "")
                if isinstance(part, dict)
                else getattr(part, "part_description", "") or getattr(part, "description", "")
            )

            if not description:
                continue

            for pattern in series_patterns:
                matches = re.finditer(pattern, description, re.IGNORECASE)
                for match in matches:
                    series = match.group(0)
                    # Normalize: "bizhub C3550i" format
                    series_found[series] += 1

        if series_found:
            # Return most common series
            return series_found.most_common(1)[0][0]

        return None

    def _extract_series_from_metadata(self, pdf_metadata: dict[str, Any]) -> str | None:
        """
        Extract series from PDF metadata (title, filename)
        """
        title = pdf_metadata.get("title", "")
        filename = pdf_metadata.get("filename", "")

        combined = f"{title} {filename}"

        series_patterns = [
            r"bizhub\s+(?:PRESS\s+)?C?\d{3,4}[a-z]{0,2}",
            r"AccurioPress\s+C\d{4}(?:P|hc)?",
            r"AccurioPrint\s+C\d{4}(?:P)?",
        ]

        for pattern in series_patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def should_skip_product_extraction(self, document_type: str, manufacturer: str) -> bool:
        """
        Determine if we should skip normal product extraction

        For Konica Minolta parts catalogs, we should use product code extraction
        instead of normal product extraction (which would match all part numbers)
        """
        return document_type == "parts_catalog" and manufacturer and "konica" in manufacturer.lower()
