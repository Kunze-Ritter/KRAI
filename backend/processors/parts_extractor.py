"""
Parts Extractor - Extract spare parts from parts catalogs using manufacturer-specific patterns
Enhanced with Vision AI for complex tables and layouts
"""

import json
import re
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger()

from .models import ExtractedPart


class PartsExtractor:
    """Extract spare parts from documents using pattern matching + Vision AI"""

    def __init__(self, config_path: Path | None = None, vision_processor=None):
        """
        Initialize parts extractor with configuration

        Args:
            config_path: Path to parts_patterns.json config file
            vision_processor: Optional VisionProcessor for AI-based extraction
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "parts_patterns.json"

        self.config_path = config_path
        self.patterns_config = self._load_config()
        self.extraction_rules = self.patterns_config.get("extraction_rules", {})
        self.vision_processor = vision_processor

        logger.info(f"Loaded parts patterns for {len(self.patterns_config) - 1} manufacturers")
        if vision_processor:
            logger.info("Vision AI enabled for parts extraction")

    def _load_config(self) -> dict[str, Any]:
        """Load parts patterns configuration"""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            logger.warning(f"Parts patterns config not found: {self.config_path}")
            return {"extraction_rules": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in parts patterns config: {e}")
            return {"extraction_rules": {}}

    def extract_parts(
        self, text: str, manufacturer_name: str | None = None, page_number: int | None = None
    ) -> list[ExtractedPart]:
        """
        Extract parts from text using manufacturer-specific patterns

        Args:
            text: Text to extract parts from
            manufacturer_name: Manufacturer name to use specific patterns
            page_number: Page number for context

        Returns:
            List of ExtractedPart objects
        """
        if not text or len(text.strip()) < 10:
            return []

        # Determine which patterns to use
        manufacturer_key = self._get_manufacturer_key(manufacturer_name)
        patterns_to_use = []

        if manufacturer_key and manufacturer_key in self.patterns_config:
            # Use manufacturer-specific patterns ONLY
            patterns_to_use.append((manufacturer_key, self.patterns_config[manufacturer_key]))
            pattern_count = len(self.patterns_config[manufacturer_key].get("patterns", []))
            config_version = self.patterns_config[manufacturer_key].get("config_version", "unknown")
            config_date = self.patterns_config[manufacturer_key].get("last_updated", "unknown")
            logger.debug(f"🔍 Using {pattern_count} patterns for {manufacturer_key} (v{config_version}, {config_date})")
        else:
            # No patterns available - return empty list with clear error
            if manufacturer_name:
                logger.error(f"❌ No parts patterns configured for manufacturer: '{manufacturer_name}'")
                logger.error(
                    f"   Available manufacturers: {', '.join([k for k in self.patterns_config.keys() if k != 'generic'])}"
                )
                logger.error("   Please add patterns to: backend/config/parts_patterns.json")
            else:
                logger.warning("⚠️  No manufacturer specified - cannot extract parts")
            return []

        # Extract parts
        extracted_parts = []
        seen_part_numbers = set()

        for mfr_key, mfr_config in patterns_to_use:
            patterns = mfr_config.get("patterns", [])

            for pattern_config in patterns:
                parts = self._extract_with_pattern(
                    text=text,
                    pattern_config=pattern_config,
                    manufacturer_name=manufacturer_name or mfr_config.get("manufacturer_name"),
                    page_number=page_number,
                )

                for part in parts:
                    part.part_name = self._clean_part_text(part.part_name, True)
                    part.part_description = self._clean_part_text(part.part_description, False)
                    # Deduplicate by part number
                    if part.part_number not in seen_part_numbers:
                        seen_part_numbers.add(part.part_number)
                        extracted_parts.append(part)

        # Sort by confidence
        extracted_parts.sort(key=lambda p: p.confidence, reverse=True)

        # Apply max parts limit
        max_parts = self.extraction_rules.get("max_parts_per_page", 50)
        if len(extracted_parts) > max_parts:
            logger.warning(f"Extracted {len(extracted_parts)} parts, limiting to {max_parts}")
            extracted_parts = extracted_parts[:max_parts]

        # Don't log per-page results - progress bar shows running count
        pass

        return extracted_parts

    def _clean_part_text(self, text: str | None, is_name: bool = True) -> str | None:
        if not text:
            return None
        cleaned = text.replace("\u2013", "-").replace("\u2014", "-").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip("\"'`“”‘’|•·-:;()[]{}")
        if is_name:
            sentence_split = cleaned.split(".")
            if sentence_split and len(sentence_split[0]) >= 3:
                cleaned = sentence_split[0]
            if len(cleaned) > 80:
                cleaned = cleaned[:80].rstrip(" ,;:-")
        else:
            if len(cleaned) > 300:
                cleaned = cleaned[:300].rstrip()
        cleaned = cleaned.strip("\"'`“”‘’|•·-:;()[]{}")
        return cleaned or None

    def enrich_parts_with_vision(
        self, parts: list[ExtractedPart], pdf_path: Path, manufacturer_name: str
    ) -> list[ExtractedPart]:
        """
        Enrich parts with missing names/descriptions using Vision AI

        Args:
            parts: List of extracted parts (some may have None for part_name)
            pdf_path: Path to PDF file
            manufacturer_name: Manufacturer name for context

        Returns:
            Enriched parts list with Vision AI data
        """
        if not self.vision_processor:
            logger.warning("Vision processor not available, skipping Vision AI enrichment")
            return parts

        # Find parts that need enrichment (no name or description)
        parts_needing_vision = [p for p in parts if not p.part_name or (not p.part_description and len(p.context) < 50)]

        if not self.vision_processor.vision_available:
            logger.warning("Vision AI reported unavailable, skipping enrichment")
            return parts

        if not parts_needing_vision:
            logger.info("All parts have names, skipping Vision AI enrichment")
            return parts

        logger.info(f"Enriching {len(parts_needing_vision)} parts with Vision AI...")

        # Group by page number for efficient processing
        pages_to_process = list(set(p.page_number for p in parts_needing_vision))

        enriched_parts = []
        for part in parts:
            if part.page_number in pages_to_process and not part.part_name:
                # Use Vision AI to extract part info from page image
                vision_result = self._extract_part_with_vision(
                    pdf_path=pdf_path,
                    page_number=part.page_number,
                    part_number=part.part_number,
                    manufacturer_name=manufacturer_name,
                )

                if vision_result:
                    # Update part with Vision AI data
                    enriched_name = self._clean_part_text(vision_result.get("part_name"), True)
                    enriched_desc = self._clean_part_text(vision_result.get("part_description"), False)
                    part.part_name = enriched_name or part.part_name
                    part.part_description = enriched_desc or part.part_description
                    part.confidence = max(part.confidence, vision_result.get("confidence", 0.5))
                    logger.debug(f"✅ Vision AI enriched {part.part_number}: {part.part_name}")

            enriched_parts.append(part)

        return enriched_parts

    def _get_manufacturer_key(self, manufacturer_name: str | None) -> str | None:
        """Convert manufacturer name to config key"""
        if not manufacturer_name:
            return None

        # Normalize manufacturer name
        normalized = manufacturer_name.lower().replace(" ", "_").replace("-", "_")

        # Direct mapping for common cases
        mapping = {
            "hp": "hp",
            "hewlett_packard": "hp",
            "konica_minolta": "konica_minolta",
            "konica": "konica_minolta",
            "minolta": "konica_minolta",
            "canon": "canon",
            "ricoh": "ricoh",
            "xerox": "xerox",
            "lexmark": "lexmark",
            "brother": "brother",
            "epson": "epson",
            "fujifilm": "fujifilm",
            "riso": "riso",
            "sharp": "sharp",
            "kyocera": "kyocera",
            "toshiba": "toshiba",
            "oki": "oki",
        }

        # Check direct match
        if normalized in mapping:
            return mapping[normalized]

        # Check if any key is in the normalized name
        for key, value in mapping.items():
            if key in normalized:
                return value

        return None

    def _extract_with_pattern(
        self, text: str, pattern_config: dict[str, Any], manufacturer_name: str | None, page_number: int | None
    ) -> list[ExtractedPart]:
        """Extract parts using a specific pattern"""
        pattern = pattern_config.get("pattern")
        pattern_name = pattern_config.get("name")
        base_confidence = pattern_config.get("confidence", 0.75)

        if not pattern:
            return []

        try:
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return []

        parts = []
        context_window = self.extraction_rules.get("context_window_chars", 200)

        for match in regex.finditer(text):
            part_number = match.group(0).strip()

            # Get context around match
            start = max(0, match.start() - context_window // 2)
            end = min(len(text), match.end() + context_window // 2)
            context = text[start:end].strip()

            # Validate context
            if not self._validate_context(context):
                continue

            # Extract additional info from context
            part_name, part_description = self._extract_part_info(context, part_number)

            # Adjust confidence based on context
            confidence = self._calculate_confidence(
                base_confidence=base_confidence,
                context=context,
                has_name=bool(part_name),
                has_description=bool(part_description),
            )

            part = ExtractedPart(
                part_number=part_number,
                part_name=part_name,
                part_description=part_description,
                part_category=self._infer_category(context, pattern_name),
                manufacturer_name=manufacturer_name,
                confidence=confidence,
                pattern_name=pattern_name,
                page_number=page_number,
                context=context[:500],  # Limit context length
            )
            min_confidence = self.extraction_rules.get("min_confidence", 0.70)
            if confidence < min_confidence:
                part.quality_flag = "low_confidence"

            parts.append(part)

        return parts

    def _extract_part_with_vision(
        self, pdf_path: Path, page_number: int, part_number: str, manufacturer_name: str
    ) -> dict[str, Any] | None:
        """
        Extract part info from page image using Vision AI

        Returns:
            Dict with part_name, part_description, confidence
        """
        try:
            # Create prompt for Vision AI
            prompt = f"""This is a parts catalog page from {manufacturer_name}.
Find the part number {part_number} in this image.
Extract:
1. Part name (short description, 1-5 words)
2. Part description (longer description if available)

Format your response as JSON:
{{"part_name": "...", "part_description": "...", "confidence": 0.0-1.0}}

If you cannot find the part number, return {{"found": false}}"""

            # Use vision processor to analyze page
            result = self.vision_processor.analyze_page(pdf_path=pdf_path, page_number=page_number, prompt=prompt)

            if result and result.get("found") != False:
                return result

        except Exception as e:
            logger.error(f"Vision AI error for {part_number} on page {page_number}: {e}")

        return None

    def _validate_context(self, context: str) -> bool:
        """Validate that context looks like a parts catalog entry"""
        context_lower = context.lower()

        # Check for required keywords
        required_keywords = self.extraction_rules.get("require_context_keywords", [])
        has_required = any(kw in context_lower for kw in required_keywords)

        # Check for excluded keywords (like "page", "figure", etc.)
        excluded_keywords = self.extraction_rules.get("exclude_if_near", [])
        has_excluded = any(kw in context_lower for kw in excluded_keywords)

        return has_required and not has_excluded

    def _extract_part_info(self, context: str, part_number: str) -> tuple[str | None, str | None]:
        """Extract part name and description from context"""
        lines = context.split("\n")
        part_name = None
        part_description = None

        for i, line in enumerate(lines):
            if part_number in line:
                # Try to extract name from same line
                remaining = line.split(part_number, 1)[1].strip()

                # Clean up common prefixes/separators
                for prefix in [":", "|", "-", "–"]:
                    if remaining.startswith(prefix):
                        remaining = remaining[1:].strip()

                # If we have text after part number, use it as name
                if remaining and len(remaining) > 3:
                    # Stop at common delimiters
                    for delimiter in ["|", "\t", "  "]:  # pipe, tab, double space
                        if delimiter in remaining:
                            remaining = remaining.split(delimiter)[0].strip()
                    part_name = remaining[:255]

                # If no name yet, check next line
                if not part_name and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Skip common labels
                    for label in ["Description:", "Desc:", "Part Name:", "Name:"]:
                        if next_line.startswith(label):
                            next_line = next_line[len(label) :].strip()

                    if next_line and len(next_line) > 3:
                        part_name = next_line[:255]

                # Description from next lines (skip if it's the name)
                for j in range(i + 1, min(i + 4, len(lines))):
                    desc_line = lines[j].strip()
                    if desc_line and len(desc_line) > 10 and desc_line != part_name:
                        part_description = desc_line[:500]
                        break

                break

        return part_name, part_description

    def _calculate_confidence(
        self, base_confidence: float, context: str, has_name: bool, has_description: bool
    ) -> float:
        """Calculate final confidence score"""
        confidence = base_confidence

        # Boost if has additional info
        if has_name:
            confidence = min(1.0, confidence + 0.05)
        if has_description:
            confidence = min(1.0, confidence + 0.03)

        # Boost if context has part indicators
        context_lower = context.lower()
        part_indicators = self.extraction_rules.get("part_number_indicators", [])
        if any(indicator in context_lower for indicator in part_indicators):
            confidence = min(1.0, confidence + 0.05)

        return round(confidence, 2)

    def _infer_category(self, context: str, pattern_name: str | None) -> str | None:
        """Infer part category from context and pattern"""
        context_lower = context.lower()

        # Check pattern name first
        if pattern_name:
            if "toner" in pattern_name:
                return "toner_cartridge"
            if "developer" in pattern_name:
                return "developer_unit"
            if "drum" in pattern_name or "imaging" in pattern_name:
                return "drum_unit"
            if "fuser" in pattern_name:
                return "fuser_assembly"
            if "maintenance" in pattern_name:
                return "maintenance_kit"
            if "ink" in pattern_name:
                return "ink_cartridge"
            if "waste" in pattern_name and "toner" in pattern_name:
                return "waste_toner_box"

        # Check consumable types in context
        consumable_types = self.extraction_rules.get("consumable_types", [])
        for consumable in consumable_types:
            if consumable in context_lower:
                return consumable.replace(" ", "_")

        return None
