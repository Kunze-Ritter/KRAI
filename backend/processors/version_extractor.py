"""
Version Extractor - Extract document versions using pattern matching

Supports multiple version formats:
- Edition: "Edition 3, 5/2024"
- Date: "2024/12/25", "5/2024", "November 2024"
- Firmware: "FW 4.2", "Firmware 4.2"
- Standard: "Version 1.0", "Ver 1.0", "v1.0"
- Revision: "Rev 1.0", "Revision 1.0"
"""

import json
import re
from pathlib import Path

from .logger import get_logger
from .models import ExtractedVersion


class VersionExtractor:
    """Extract version information from text"""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize version extractor

        Args:
            config_path: Path to version_patterns.json (optional)
        """
        self.logger = get_logger()

        # Load patterns
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "version_patterns.json"

        self.patterns = self._load_patterns(config_path)
        self.compiled_patterns = self._compile_patterns()

    def _load_patterns(self, config_path: Path) -> dict:
        """Load version patterns from JSON"""
        try:
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("version_patterns", {})
            else:
                self.logger.warning(f"Pattern file not found: {config_path}")
                return self._get_default_patterns()
        except Exception as e:
            self.logger.error(f"Error loading patterns: {e}")
            return self._get_default_patterns()

    def _get_default_patterns(self) -> dict:
        """Default patterns if config file not available"""
        return {
            "patterns": {
                "edition_patterns": {
                    "patterns": [
                        {"pattern": r"edition\s+([0-9]+(?:\.[0-9]+)?)\s*,?\s*([0-9]+/[0-9]{4})", "priority": 1},
                        {"pattern": r"edition\s+([0-9]+(?:\.[0-9]+)?)", "priority": 2},
                    ]
                },
                "date_patterns": {
                    "patterns": [
                        {"pattern": r"([0-9]{4}/[0-9]{2}/[0-9]{2})", "priority": 1},
                        {"pattern": r"([0-9]{2}/[0-9]{4})", "priority": 2},
                        {"pattern": r"([a-z]+\s+[0-9]{4})", "priority": 3},
                    ]
                },
                "firmware_patterns": {
                    "patterns": [
                        {"pattern": r"fw\s+([0-9\.]+)", "priority": 1},
                        {"pattern": r"firmware\s+([0-9\.]+)", "priority": 2},
                    ]
                },
                "standard_patterns": {
                    "patterns": [
                        {"pattern": r"version\s+([0-9\.]+)", "priority": 1},
                        {"pattern": r"ver\s+([0-9\.]+)", "priority": 2},
                        {"pattern": r"v\s*([0-9\.]+)", "priority": 3},
                        {"pattern": r"rev\s+([0-9\.]+)", "priority": 4},
                    ]
                },
            }
        }

    def _compile_patterns(self) -> dict:
        """Compile regex patterns for faster matching"""
        compiled = {}

        patterns_data = self.patterns.get("patterns", {})

        for category, category_data in patterns_data.items():
            compiled[category] = []

            for pattern_def in category_data.get("patterns", []):
                try:
                    regex = re.compile(pattern_def["pattern"], re.IGNORECASE | re.MULTILINE)
                    compiled[category].append(
                        {"regex": regex, "priority": pattern_def.get("priority", 999), "category": category}
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to compile pattern: {pattern_def['pattern']}: {e}")

        return compiled

    def extract_from_text(
        self, text: str, manufacturer: str | None = None, page_number: int | None = None
    ) -> list[ExtractedVersion]:
        """
        Extract DOCUMENT VERSION from text using MANUFACTURER-SPECIFIC patterns

        Args:
            text: Text to extract from (first few pages)
            manufacturer: Manufacturer name (REQUIRED for specific patterns)
            page_number: Page number in document

        Returns:
            List with 1 version (first match for manufacturer)
        """
        if not text or len(text.strip()) < 10:
            return []

        # MANUFACTURER-SPECIFIC DOCUMENT VERSION PATTERNS
        # Note: version_type must be one of: edition, date, firmware, version, revision
        manufacturer_patterns = {
            "hp": [
                (r"edition\s+(\d+(?:\.\d+)?)\s*,?\s*(\d+/\d{4})", "edition", 0.95),  # Edition 3, 5/2024
                (r"edition\s+(\d+(?:\.\d+)?)", "edition", 0.90),  # Edition 4.0
            ],
            "konica_minolta": [
                (r"(\d{4}/\d{2}/\d{2})", "date", 0.95),  # 2024/12/25
                (r"(\d{4}\.\d{2}\.\d{2})", "date", 0.90),  # 2024.01.15
            ],
            "lexmark": [
                (r"([A-Z][a-z]+\s+\d{4})", "date", 0.95),  # November 2024
                (r"(\d{2}/\d{2}/\d{4})", "date", 0.90),  # 11/15/2024
            ],
            "utax": [
                (r"version\s+(\d+\.\d+(?:\.\d+)?)", "version", 0.95),  # Version 1.0
                (r"v\s*(\d+\.\d+)", "version", 0.90),  # v1.0
                (r"(\d{2}/\d{4})", "date", 0.85),  # 5/2024
            ],
            "triumph_adler": [
                (r"version\s+(\d+\.\d+(?:\.\d+)?)", "version", 0.95),  # Version 1.0
                (r"v\s*(\d+\.\d+)", "version", 0.90),  # v1.0
                (r"(\d{2}/\d{4})", "date", 0.85),  # 5/2024
            ],
            "kyocera": [
                (r"version\s+(\d+\.\d+(?:\.\d+)?)", "version", 0.95),  # Version 1.0
                (r"v\s*(\d+\.\d+)", "version", 0.90),  # v1.0
                (r"(\d{2}/\d{4})", "date", 0.85),  # 5/2024
                (r"rev\.\s*([A-Z])", "revision", 0.80),  # Rev. A
            ],
        }

        # Get manufacturer-specific patterns
        if manufacturer:
            manufacturer_key = manufacturer.lower().replace(" ", "_").replace("-", "_")
            patterns = manufacturer_patterns.get(manufacturer_key)
        else:
            patterns = None

        # Fallback to generic patterns if manufacturer not found
        if not patterns:
            patterns = [
                (r"edition\s+(\d+(?:\.\d+)?)\s*,?\s*(\d+/\d{4})", "edition", 0.90),
                (r"(\d{4}/\d{2}/\d{2})", "date", 0.85),
                (r"version\s+(\d+\.\d+)", "version", 0.80),
            ]

        versions = []
        found_matches = set()

        # Try patterns in order - STOP AFTER FIRST MATCH
        for pattern, version_type, confidence in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                version_string = match.group(0).strip()

                # Avoid duplicates
                if version_string.lower() in found_matches:
                    continue

                # Skip forbidden patterns
                if self._is_forbidden(version_string):
                    continue

                found_matches.add(version_string.lower())

                # Create ExtractedVersion
                version = ExtractedVersion(
                    version_string=version_string,
                    version_type=version_type,
                    confidence=confidence,
                    extraction_method=f"manufacturer_{manufacturer_key if manufacturer else 'generic'}",
                    page_number=page_number,
                    context=self._get_context(text, match.start(), match.end()),
                )

                versions.append(version)

                # STOP AFTER FIRST MATCH
                return versions[:1]  # Return only first match

        return versions

    def _is_forbidden(self, version_string: str) -> bool:
        """Check if version string matches forbidden patterns"""
        forbidden = [
            "copyright",
            "all rights reserved",
            "development",
        ]
        version_lower = version_string.lower()
        return any(forbidden_term in version_lower for forbidden_term in forbidden)

    def _determine_version_type(self, category: str) -> str:
        """Determine version type from category"""
        type_mapping = {
            "edition_patterns": "edition",
            "date_patterns": "date",
            "firmware_patterns": "firmware",
            "standard_patterns": "version",
            "numeric_patterns": "version",
        }
        return type_mapping.get(category, "version")

    def _calculate_confidence(self, version_string: str, category: str, priority: int) -> float:
        """Calculate confidence score for extracted version"""
        # Base confidence on priority (lower priority = higher confidence)
        confidence = 1.0 - (priority * 0.1)

        # Adjust based on category
        if category == "edition_patterns":
            confidence += 0.1
        elif category == "firmware_patterns":
            confidence += 0.05

        # Adjust based on length and format
        if len(version_string) > 3 and len(version_string) < 30:
            confidence += 0.05

        # Ensure in valid range
        return max(0.0, min(1.0, confidence))

    def _validate_version(self, version_string: str) -> bool:
        """Validate extracted version"""
        validation = self.patterns.get("validation", {})

        # Check length
        min_length = validation.get("min_version_length", 1)
        max_length = validation.get("max_version_length", 50)

        if not (min_length <= len(version_string) <= max_length):
            return False

        # Check forbidden patterns
        forbidden = validation.get("forbidden_patterns", [])
        return all(not re.search(forbidden_pattern, version_string, re.IGNORECASE) for forbidden_pattern in forbidden)

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get surrounding context of match"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()

    def extract_best_version(self, text: str, manufacturer: str | None = None) -> ExtractedVersion | None:
        """
        Extract single best version from text

        Args:
            text: Text to extract from
            manufacturer: Manufacturer name

        Returns:
            Best version or None
        """
        versions = self.extract_from_text(text, manufacturer)

        if not versions:
            return None

        # Return version with highest confidence
        return max(versions, key=lambda v: v.confidence)

    def validate_extraction(self, version: ExtractedVersion) -> list[str]:
        """
        Validate extracted version

        Args:
            version: Extracted version to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not version.version_string:
            errors.append("Version string is empty")

        if version.confidence < 0.3:
            errors.append(f"Low confidence: {version.confidence:.2f}")

        if len(version.version_string) > 50:
            errors.append("Version string too long")

        return errors


# Example usage
if __name__ == "__main__":
    extractor = VersionExtractor()

    # Test texts
    test_texts = [
        "AccurioPress C4080 Service Manual Edition 3, 5/2024",
        "Lexmark CX833 Service Manual November 2024",
        "This document is for FW 4.2 and later versions",
        "Version 1.0.5 - Updated 2024/12/25",
        "Service Manual Rev 2.3",
    ]

    print("Version Extraction Tests")
    print("=" * 60)

    for i, text in enumerate(test_texts, 1):
        print(f"\nTest {i}: {text[:50]}...")
        versions = extractor.extract_from_text(text)

        if versions:
            for v in versions:
                print(f"  ✓ Found: {v.version_string}")
                print(f"    Type: {v.version_type}")
                print(f"    Confidence: {v.confidence:.2f}")
        else:
            print("  ✗ No version found")
