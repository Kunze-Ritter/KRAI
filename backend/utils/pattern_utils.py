"""
Pattern Utilities for KR-AI-Engine
Pattern matching for error codes, versions, and model placeholders
"""

import logging
import re
from typing import Any


class PatternMatcher:
    """
    Pattern matcher for KR-AI-Engine

    Handles:
    - Error code pattern matching
    - Version pattern extraction
    - Model placeholder resolution
    - Manufacturer-specific patterns
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.patterns")
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for pattern matcher"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - PatternMatcher - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def match_error_codes(self, text: str, manufacturer: str) -> list[dict[str, Any]]:
        """
        Match error codes in text for specific manufacturer

        Args:
            text: Text to search
            manufacturer: Manufacturer name

        Returns:
            List of matched error codes
        """
        try:
            # Manufacturer-specific patterns
            patterns = {
                "hp": [r"\b(\d{2}\.\d{2}\.\d{2})\b", r"\b(\d{2}\.\d{2})\b"],  # 13.20.01  # 13.20
                "konica_minolta": [r"\b(C\d{4,5})\b", r"\b(J\d{4,5})\b"],  # C2557  # J1101
                "lexmark": [r"\b(\d{3}\.\d{2})\b", r"\b(\d{2,3})\b"],  # 123.45  # 123
                "utax": [r"\b(\d{5})\b"],  # 12345
            }

            manufacturer_patterns = patterns.get(manufacturer.lower(), [])
            matches = []

            for pattern in manufacturer_patterns:
                for match in re.finditer(pattern, text):
                    matches.append(
                        {
                            "error_code": match.group(1),
                            "position": match.start(),
                            "manufacturer": manufacturer,
                            "pattern": pattern,
                        }
                    )

            self.logger.info(f"Found {len(matches)} error codes for {manufacturer}")
            return matches

        except Exception as e:
            self.logger.error(f"Failed to match error codes: {e}")
            return []

    def extract_versions(self, text: str, document_type: str) -> list[dict[str, Any]]:
        """
        Extract version information from text

        Args:
            text: Text to search
            document_type: Type of document

        Returns:
            List of version information
        """
        try:
            # Version patterns
            patterns = [
                r"version\s+(\d+\.\d+(?:\.\d+)?)",
                r"v(\d+\.\d+(?:\.\d+)?)",
                r"edition\s+(\d+)",
                r"rev(?:ision)?\s+(\d+\.\d+)",
                r"(\d{4}-\d{2}-\d{2})",  # Date format
                r"(\d{2}/\d{2}/\d{4})",  # Date format
            ]

            versions = []
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    versions.append(
                        {
                            "version": match.group(1),
                            "type": self._determine_version_type(match.group(1)),
                            "position": match.start(),
                            "pattern": pattern,
                        }
                    )

            self.logger.info(f"Found {len(versions)} versions")
            return versions

        except Exception as e:
            self.logger.error(f"Failed to extract versions: {e}")
            return []

    def resolve_model_placeholders(self, text: str, manufacturer: str) -> list[dict[str, Any]]:
        """
        Resolve model placeholders in text

        Args:
            text: Text to search
            manufacturer: Manufacturer name

        Returns:
            List of resolved placeholders
        """
        try:
            # Placeholder patterns
            patterns = {
                "hp": [
                    r"\b([A-Z]{2,4}\d{2,4}[A-Z]?)\b",  # LaserJet Pro
                    r"\b([A-Z]{2,4}\d{3,4}[A-Z]?)\b",  # OfficeJet Pro
                ],
                "konica_minolta": [r"\b(bizhub\s+\w+)\b", r"\b(i-series\s+\w+)\b"],  # bizhub C258  # i-series
                "lexmark": [r"\b([A-Z]{2,4}\d{3,4}[A-Z]?)\b", r"\b([A-Z]{2,4}\d{2,3}[A-Z]?)\b"],  # MS421  # CS421
            }

            manufacturer_patterns = patterns.get(manufacturer.lower(), [])
            resolved = []

            for pattern in manufacturer_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    resolved.append(
                        {
                            "model": match.group(1),
                            "manufacturer": manufacturer,
                            "position": match.start(),
                            "pattern": pattern,
                        }
                    )

            self.logger.info(f"Resolved {len(resolved)} model placeholders for {manufacturer}")
            return resolved

        except Exception as e:
            self.logger.error(f"Failed to resolve model placeholders: {e}")
            return []

    def _determine_version_type(self, version: str) -> str:
        """Determine the type of version"""
        if re.match(r"\d+\.\d+\.\d+", version):
            return "semantic"
        if re.match(r"\d+\.\d+", version):
            return "major_minor"
        if re.match(r"\d{4}-\d{2}-\d{2}", version) or re.match(r"\d{2}/\d{2}/\d{4}", version):
            return "date"
        return "unknown"

    def validate_error_code(self, error_code: str, manufacturer: str) -> bool:
        """
        Validate error code format for manufacturer

        Args:
            error_code: Error code to validate
            manufacturer: Manufacturer name

        Returns:
            True if valid format
        """
        try:
            validation_patterns = {
                "hp": r"^\d{2}\.\d{2}(?:\.\d{2})?$",
                "konica_minolta": r"^[CJ]\d{4,5}$",
                "lexmark": r"^\d{2,3}(?:\.\d{2})?$",
                "utax": r"^\d{5}$",
            }

            pattern = validation_patterns.get(manufacturer.lower())
            if pattern:
                return bool(re.match(pattern, error_code))

            return False

        except Exception as e:
            self.logger.error(f"Failed to validate error code: {e}")
            return False
