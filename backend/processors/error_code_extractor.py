"""Error Code Extraction Module

Extracts error codes using manufacturer-specific patterns from JSON config.

ARCHITECTURE (Refactored 2026-03-05):
- error_code_patterns.py: Regex patterns, constants, config loading
- error_code_hierarchy.py: Parent code derivation, category creation
- error_code_extractor.py: Main facade (this file)

OEM/REBRAND SUPPORT:
- Automatically detects OEM engine manufacturer
- Uses correct patterns for rebranded products
- Example: Konica Minolta 5000i uses Brother error codes
"""

import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from backend.config.oem_mappings import get_effective_manufacturer
from backend.utils.hp_solution_filter import extract_all_hp_levels
from backend.utils.manufacturer_normalizer import normalize_manufacturer

# Import from refactored modules
from .error_code_patterns import (
    BULLET_PATTERN,
    CLASSIFICATION_PATTERN,
    MAX_BATCH_CODE_LENGTH,
    NUMBERED_STEPS_PATTERN,
    RECOMMENDED_ACTION_PATTERN,
    REJECT_CODES,
    SECTION_END_NOTE,
    SECTION_END_NUMBERED,
    SECTION_END_TITLE,
    SENTENCE_END_PATTERN,
    SOLUTION_KEYWORDS_PATTERN,
    STEP_LINE_PATTERN,
    STEP_MATCH_PATTERN,
    TECHNICAL_TERMS,
)
from .error_code_patterns import slugify_error_code as _slugify
from .logger import get_logger
from .models import ExtractedErrorCode
from .models import ValidationError as ValError

try:
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

    RICH_PROGRESS_AVAILABLE = True
except ImportError:
    Progress = SpinnerColumn = TextColumn = BarColumn = TaskProgressColumn = TimeRemainingColumn = None  # type: ignore
    RICH_PROGRESS_AVAILABLE = False

logger = get_logger()


class ErrorCodeExtractor:
    """Extract error codes using manufacturer-specific patterns"""

    def __init__(self, config_path: Path | None = None):
        """Initialize error code extractor with configuration"""

        self.logger = get_logger()
        self._chunk_cache: dict[str, Any] = {}  # Cache chunks to avoid repeated queries
        self._missing_manufacturer_events: list[dict[str, Any]] = []

        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "error_code_patterns.json"

        self.config_path = config_path
        self.patterns_config = self._load_config()
        self.extraction_rules = self.patterns_config.get("extraction_rules", {})

        logger.info(
            f"Loaded error code patterns for {len([k for k in self.patterns_config if k != 'extraction_rules'])} manufacturers"
        )

    def _load_config(self) -> dict[str, Any]:
        """Load error code patterns configuration"""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except FileNotFoundError:
            logger.warning(f"Error code patterns config not found: {self.config_path}")
            return {"extraction_rules": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in error code patterns config: {e}")
            return {"extraction_rules": {}}

    @staticmethod
    def _slugify(name: str) -> str:
        return _slugify(name)

    def _reset_missing_manufacturer_events(self):
        self._missing_manufacturer_events.clear()

    def _get_missing_manufacturer_events(self) -> list[dict[str, Any]]:
        return list(self._missing_manufacturer_events)

    def reset_missing_manufacturer_events(self) -> None:
        """Public helper to clear missing-manufacturer telemetry buffer."""
        self._reset_missing_manufacturer_events()

    def get_missing_manufacturer_events(self) -> list[dict[str, Any]]:
        """Return missing-manufacturer telemetry collected during extraction."""
        return self._get_missing_manufacturer_events()

    def _get_manufacturer_key(self, manufacturer_name: str | None) -> str | None:
        """Convert manufacturer name to config key using unified normalization"""
        if not manufacturer_name:
            return None

        canonical = normalize_manufacturer(manufacturer_name) or manufacturer_name
        slug_candidates = {self._slugify(manufacturer_name), self._slugify(canonical)}

        for candidate in list(slug_candidates):
            if candidate.endswith("inc"):
                slug_candidates.add(candidate[:-3])
            if candidate.endswith("corp"):
                slug_candidates.add(candidate[:-4])

        for config_key in self.patterns_config:
            if config_key == "extraction_rules":
                continue
            key_slug = self._slugify(config_key)
            for candidate in slug_candidates:
                if not candidate:
                    continue
                if candidate == key_slug or candidate.endswith(key_slug) or key_slug.endswith(candidate):
                    return config_key

        return None

    def enrich_error_codes_from_document(
        self,
        error_codes: list[ExtractedErrorCode],
        full_document_text: str,
        manufacturer_name: str | None = None,
        product_series: str | None = None,
    ) -> list[ExtractedErrorCode]:
        """
        Enrich error codes with full details from entire document

        OPTIMIZED: Batch processing with compiled regex patterns
        OEM-AWARE: Uses OEM manufacturer patterns for rebranded products

        For codes found in lists (e.g., "List of JAM code"), search the entire
        document for detailed sections with Classification, Cause, Measures.

        Args:
            error_codes: List of error codes to enrich
            full_document_text: Full text of entire document
            manufacturer_name: Brand manufacturer name (e.g., "Konica Minolta")
            product_series: Product series for OEM detection (e.g., "5000i")

        Returns:
            Enriched error codes with full details
        """
        # OEM/REBRAND DETECTION
        # Check if this is a rebranded product and use OEM patterns
        effective_manufacturer = manufacturer_name
        if manufacturer_name and product_series:
            oem_manufacturer = get_effective_manufacturer(manufacturer_name, product_series, for_purpose="error_codes")
            if oem_manufacturer != manufacturer_name:
                self.logger.info(
                    f"🔄 OEM Detected: {manufacturer_name} {product_series} uses {oem_manufacturer} error codes"
                )
                effective_manufacturer = oem_manufacturer

        # Use effective manufacturer for pattern lookup
        manufacturer_name = effective_manufacturer
        # OPTIMIZATION 1: Skip enrichment if all codes already have good solutions
        codes_needing_enrichment = [
            ec for ec in error_codes if not ec.solution_technician_text or len(ec.solution_technician_text) <= 500
        ]

        if not codes_needing_enrichment:
            self.logger.debug("All error codes already have good solutions, skipping enrichment")
            return error_codes

        self.logger.info(f"Enriching {len(codes_needing_enrichment)}/{len(error_codes)} error codes...")

        # Performance note: This is CPU-bound (regex). For 3919 codes:
        # - Single-threaded: ~1 minute (after optimization)
        # - Multi-threaded: Not beneficial (Python GIL + regex overhead)
        # - GPU/NPU: Not applicable (regex is CPU-only)

        # OPTIMIZATION 2: Build a single regex pattern for all codes (batch search)
        # Group codes by pattern to reduce regex complexity
        code_to_original: dict[str, ExtractedErrorCode] = {}
        pattern_entries: list[tuple[str, str]] = []  # (original_code, escaped_code)
        long_code_values: list[str] = []

        for error_code in codes_needing_enrichment:
            code_value = (error_code.error_code or "").strip()
            if not code_value:
                self.logger.debug("Skipping empty error code during enrichment batch setup")
                continue

            code_to_original[code_value] = error_code

            if len(code_value) > MAX_BATCH_CODE_LENGTH:
                self.logger.debug(
                    "Skipping batch regex for long code '%s' (len=%s) - streaming fallback", code_value, len(code_value)
                )
                long_code_values.append(code_value)
                continue

            escaped_code = re.escape(code_value)
            if len(escaped_code) > MAX_BATCH_CODE_LENGTH:
                self.logger.debug(
                    "Escaped pattern for code '%s' exceeds limit (len=%s) - streaming fallback",
                    code_value,
                    len(escaped_code),
                )
                long_code_values.append(code_value)
                continue

            pattern_entries.append((code_value, escaped_code))

        # OPTIMIZATION 3: Compile single regex for all codes
        # Use alternation (|) to match any of the codes in one pass
        batchable_count = len(pattern_entries)
        if long_code_values:
            self.logger.info(
                "   Streaming fallback for %s long codes (excluded from batch regex)", len(long_code_values)
            )

        self.logger.info("   Building batch regex for %s codes...", batchable_count)

        all_matches: dict[str, list[tuple[int, int]]] = {}

        if batchable_count:
            all_matches = self._collect_with_batches(
                full_document_text, pattern_entries, batch_size=100, existing_matches=all_matches
            )

        if long_code_values:
            self._streaming_fallback(
                full_document_text, long_code_values, matches=all_matches, batch_label="long-codes"
            )

        # OPTIMIZATION 4: Process each code with its pre-found matches
        enriched_codes = []

        self.logger.info(f"   Starting enrichment loop for {len(error_codes)} codes...")

        # Progress tracking
        progress_console = getattr(self.logger, "console", None)
        if RICH_PROGRESS_AVAILABLE and progress_console is not None:
            disable_progress = not getattr(progress_console, "is_terminal", False)
            progress_context = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=progress_console,
                transient=False,
                disable=disable_progress,
            )
        else:
            progress_context = self.logger.progress_bar([], "Enriching error codes")

        with progress_context as progress:
            task = progress.add_task(f"[cyan]Enriching {len(error_codes)} error codes...", total=len(error_codes))

            # Performance tracking
            import time

            loop_start = time.time()
            processed_count = 0

            for error_code in error_codes:
                # Skip if already has good solution
                if error_code.solution_technician_text and len(error_code.solution_technician_text) > 100:
                    enriched_codes.append(error_code)
                    progress.update(task, advance=1)
                    continue

                # DEBUG: Log first code to see where it hangs
                if processed_count == 0:
                    self.logger.info(f"   Processing first code: {error_code.error_code}")

                # Get pre-found matches for this code
                matches = all_matches.get(error_code.error_code, [])

                # OPTIMIZATION: Filter matches to only those in error code context
                # Avoid false positives (e.g., product names like "C4080" that appear everywhere)
                filtered_matches = []
                for start_pos, end_pos in matches:
                    # Check context before the match (100 chars)
                    context_before = full_document_text[max(0, start_pos - 100) : start_pos].lower()
                    # Look for error code indicators
                    if any(
                        keyword in context_before for keyword in ["error", "code", "trouble", "fault", "alarm", "jam"]
                    ):
                        filtered_matches.append((start_pos, end_pos))
                        if len(filtered_matches) >= 10:  # Limit to 10 good matches
                            break

                # Fallback: If no filtered matches, use first 3 raw matches
                matches = filtered_matches if filtered_matches else matches[:3]

                if processed_count == 0:
                    self.logger.info(f"   Found {len(matches)} matches for first code (limited to 10)")

                # Try each occurrence to find the detailed section
                best_description = error_code.error_description
                best_solution_raw = error_code.solution_technician_text  # raw full text for enrichment
                best_confidence = error_code.confidence

                for match_idx, (start_pos, end_pos) in enumerate(matches):
                    if processed_count == 0 and match_idx == 0:
                        self.logger.info("   Extracting context for first match...")

                    # Extract larger context (up to 3000 chars for detailed sections)
                    context = self._extract_context(full_document_text, start_pos, end_pos, context_size=3000)

                    if processed_count == 0 and match_idx == 0:
                        self.logger.info(f"   Context extracted ({len(context)} chars), extracting description...")

                    # Try to extract structured description
                    description = self._extract_description(
                        full_document_text,
                        end_pos,
                        max_length=1500,
                        code_start_pos=start_pos,
                    )

                    if processed_count == 0 and match_idx == 0:
                        self.logger.info("   Description extracted, extracting solution...")
                    if description and len(description) > len(best_description):
                        best_description = description
                        best_confidence = min(0.95, best_confidence + 0.1)

                    # Try to extract solution
                    solution = self._extract_solution(context, full_document_text, end_pos)

                    if processed_count == 0 and match_idx == 0:
                        self.logger.info("   Solution extracted, creating enriched code...")

                    if solution and len(solution) > len(best_solution_raw or ""):
                        best_solution_raw = solution
                        best_confidence = min(0.95, best_confidence + 0.1)

                        # OPTIMIZATION 5: Early exit if we found a good solution
                        if len(best_solution_raw) > 1500:
                            break

                # Split raw solution text into the 3 levels
                enriched_manufacturer = getattr(error_code, "manufacturer_name", manufacturer_name)
                enriched_effective = getattr(error_code, "effective_manufacturer", effective_manufacturer)
                sol_levels = extract_all_hp_levels(best_solution_raw or "", manufacturer=enriched_effective)
                enriched_code = ExtractedErrorCode(
                    error_code=error_code.error_code,
                    error_description=best_description,
                    solution_customer_text=sol_levels["customer"],
                    solution_agent_text=sol_levels["agent"],
                    solution_technician_text=sol_levels["technician"],
                    context_text=error_code.context_text,
                    confidence=best_confidence,
                    page_number=error_code.page_number,
                    extraction_method=f"{error_code.extraction_method}_enriched",
                    severity_level=error_code.severity_level,
                    manufacturer_name=enriched_manufacturer,
                    effective_manufacturer=enriched_effective,
                )
                enriched_codes.append(enriched_code)
                progress.update(task, advance=1)

                # Log progress every 100 codes
                processed_count += 1
                if processed_count % 100 == 0:
                    elapsed = time.time() - loop_start
                    rate = processed_count / elapsed
                    self.logger.info(f"   Processed {processed_count}/{len(error_codes)} codes ({rate:.1f} codes/sec)")

        return enriched_codes

    def _collect_with_batches(
        self,
        document_text: str,
        pattern_entries: list[tuple[str, str]],
        batch_size: int,
        existing_matches: dict[str, list[tuple[int, int]]] | None = None,
    ) -> dict[str, list[tuple[int, int]]]:
        """Collect regex matches while handling large batches defensively."""
        matches: dict[str, list[tuple[int, int]]] = existing_matches or {}
        total_patterns = len(pattern_entries)
        if total_patterns == 0:
            return matches

        # Sort longest-first to reduce catastrophic backtracking risk
        sorted_entries = sorted(pattern_entries, key=lambda entry: len(entry[1]), reverse=True)

        for batch_start in range(0, total_patterns, batch_size):
            batch = sorted_entries[batch_start : batch_start + batch_size]
            if not batch:
                continue

            alternation = "|".join(entry[1] for entry in batch)
            # Guard alternation length to avoid regex DoS
            if len(alternation) > 100_000:
                self.logger.warning(
                    "Batch alternation length %s exceeds cap, splitting batch (size=%s)", len(alternation), len(batch)
                )
                self._collect_with_batches(document_text, batch, max(1, batch_size // 2), matches)
                continue

            pattern = rf"\b({alternation})\b"
            try:
                compiled_regex = re.compile(pattern)
            except re.error as regex_error:
                self.logger.error(
                    "Regex compilation failed for batch starting at %s (size=%s): %s",
                    batch_start,
                    len(batch),
                    regex_error,
                )
                # Retry with smaller batches
                if batch_size > 1:
                    half = max(1, batch_size // 2)
                    self.logger.info("Retrying batch starting at %s with smaller size %s", batch_start, half)
                    self._collect_with_batches(document_text, batch, half, matches)
                    continue
                # Fallback to streaming search for smallest unit
                codes = [entry[0] for entry in batch]
                self._streaming_fallback(document_text, codes, matches, batch_label="regex-error")
                continue

            for match in compiled_regex.finditer(document_text):
                code = match.group(0)
                matches.setdefault(code, []).append((match.start(), match.end()))

        return matches

    def _streaming_fallback(
        self, document_text: str, codes: list[str], matches: dict[str, list[tuple[int, int]]], batch_label: str
    ) -> None:
        """Perform serial search for codes when batch regex fails or is unsuitable."""
        self.logger.info("   Streaming fallback (%s) for %s codes", batch_label, len(codes))

        for code in codes:
            start = 0
            while True:
                idx = document_text.find(code, start)
                if idx == -1:
                    break
                end_idx = idx + len(code)
                matches.setdefault(code, []).append((idx, end_idx))
                start = end_idx

    def extract_from_text(
        self, text: str, page_number: int, manufacturer_name: str | None = None, product_series: str | None = None
    ) -> list[ExtractedErrorCode]:
        """
        Extract error codes from text using manufacturer-specific patterns

        Args:
            text: Text to extract from
            page_number: Page number
            manufacturer_name: Manufacturer name for specific patterns

        Returns:
            List of validated error codes
        """
        if not text or len(text) < 20:
            return []

        effective_manufacturer = manufacturer_name
        if manufacturer_name and product_series:
            oem_manufacturer = get_effective_manufacturer(manufacturer_name, product_series, for_purpose="error_codes")
            if oem_manufacturer and oem_manufacturer != manufacturer_name:
                self.logger.info(
                    f"🔄 OEM Detected: {manufacturer_name} {product_series} uses {oem_manufacturer} error codes"
                )
                effective_manufacturer = oem_manufacturer

        manufacturer_key = self._get_manufacturer_key(effective_manufacturer)

        if manufacturer_name and effective_manufacturer and manufacturer_name != effective_manufacturer:
            self.logger.debug(
                "Using OEM manufacturer '%s' for validation (original: '%s')",
                effective_manufacturer,
                manufacturer_name,
            )

        # Determine which patterns to use
        patterns_to_use: list[tuple[str, dict[str, Any]]] = []

        if manufacturer_key and manufacturer_key in self.patterns_config:
            # Use manufacturer-specific patterns ONLY (no generic fallback to avoid false positives like part numbers)
            patterns_to_use.append((manufacturer_key, self.patterns_config[manufacturer_key]))
            logger.debug(f"Using error code patterns for manufacturer: {manufacturer_key}")
        else:
            if manufacturer_name:
                logger.warning(
                    "⚠️  No error code patterns configured for '%s' (effective: '%s')",
                    manufacturer_name,
                    effective_manufacturer or "unknown",
                )
                self._missing_manufacturer_events.append(
                    {
                        "manufacturer": manufacturer_name,
                        "effective_manufacturer": effective_manufacturer,
                        "page": page_number,
                    }
                )
                return []
            logger.warning("No manufacturer specified for error code extraction - skipping")
            return []

        found_codes: list[ExtractedErrorCode] = []
        seen_codes = set()

        for mfr_key, mfr_config in patterns_to_use:
            patterns = mfr_config.get("patterns", [])
            validation_regex = mfr_config.get("validation_regex")

            for pattern_str in patterns:
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern_str}': {e}")
                    continue

                matches = pattern.finditer(text)

                for match in matches:
                    code = match.group(1) if match.groups() else match.group(0)
                    code = code.strip()

                    if validation_regex and not re.match(validation_regex, code):
                        continue
                    if code in seen_codes:
                        continue
                    if code.lower() in REJECT_CODES:
                        continue

                    context = self._extract_context(text, match.start(), match.end())

                    if re.match(r"^\d{2}-\d{2}$", code):
                        context_lower = context.lower()
                        jam_keywords = [
                            "jam",
                            "misfeed",
                            "paper",
                            "feed",
                            "transport",
                            "duplex",
                            "tray",
                            "bypass",
                            "section",
                        ]
                        if not any(kw in context_lower for kw in jam_keywords):
                            logger.debug(
                                f"Skipping JAM code '{code}' - no jam-related context (use J-{code} format for explicit JAM codes)"
                            )
                            continue
                    elif re.match(r"^J-\d{2}-\d{2}$", code):
                        logger.debug(f"Accepted JAM code '{code}' - explicit J- prefix")

                    if not self._validate_context(context):
                        continue

                    description = self._extract_description(
                        text,
                        match.end(),
                        max_length=2000,
                        code_start_pos=match.start(),
                    )
                    if not description or self._is_generic_description(description):
                        continue

                    solution = self._extract_solution(context, text, match.end())
                    confidence = self._calculate_confidence(code, description, solution, context)

                    severity = self._determine_severity(description, solution)

                    hierarchy_rules = mfr_config.get("hierarchy_rules")
                    parent_code = self._derive_parent_code(code, hierarchy_rules)

                    sol_levels = extract_all_hp_levels(solution or "", manufacturer=effective_manufacturer)
                    try:
                        error_code = ExtractedErrorCode(
                            error_code=code,
                            error_description=description,
                            solution_customer_text=sol_levels["customer"],
                            solution_agent_text=sol_levels["agent"],
                            solution_technician_text=sol_levels["technician"],
                            context_text=context,
                            confidence=confidence,
                            page_number=page_number,
                            extraction_method=f"{mfr_key}_pattern",
                            severity_level=severity,
                            manufacturer_name=manufacturer_name,
                            effective_manufacturer=effective_manufacturer,
                            parent_code=parent_code,
                        )
                        found_codes.append(error_code)
                        seen_codes.add(code)
                        min_confidence = self.extraction_rules.get("min_confidence", 0.70)
                        if confidence < min_confidence:
                            error_code.quality_flag = "low_confidence"
                    except Exception as e:
                        logger.debug(f"Validation failed for code '{code}': {e}")

        unique_codes = self._deduplicate(found_codes)

        # Create category entries for parent codes
        for _mfr_key, mfr_config in patterns_to_use:
            hierarchy_rules = mfr_config.get("hierarchy_rules")
            if hierarchy_rules:
                categories = self._create_category_entries(unique_codes, hierarchy_rules, _mfr_key, manufacturer_name)
                unique_codes.extend(categories)

        unique_codes.sort(key=lambda x: x.confidence, reverse=True)

        max_codes = self.extraction_rules.get("max_codes_per_page", 20)
        if len(unique_codes) > max_codes:
            logger.warning(f"Extracted {len(unique_codes)} error codes, limiting to {max_codes}")
            unique_codes = unique_codes[:max_codes]

        return unique_codes

    @staticmethod
    def _derive_parent_code(code: str, hierarchy_rules: dict[str, Any] | None) -> str | None:
        """Derive parent category code from a specific error code.

        Supports two strategies configured via hierarchy_rules:
        - "first_n_segments": split by separator and take first N segments
          (e.g., "13.B9.Az" with separator="." and parent_segments=2 → "13.B9")
        - "prefix_digits": take the first N characters as parent
          (e.g., "SC542" with prefix_length=3 → "SC5")
        """
        if not hierarchy_rules:
            return None
        method = hierarchy_rules.get("derive_parent")
        if method == "first_n_segments":
            sep = cast(str, hierarchy_rules.get("separator", "."))
            parts = code.split(sep)
            n = cast(int, hierarchy_rules.get("parent_segments", 2))
            if len(parts) > n:
                return sep.join(parts[:n])
        elif method == "prefix_digits":
            length = cast(int, hierarchy_rules.get("prefix_length", 3))
            if len(code) > length:
                return code[:length]
        return None

    def _create_category_entries(
        self,
        codes: list[ExtractedErrorCode],
        hierarchy_rules: dict[str, Any],
        mfr_key: str,
        manufacturer_name: str | None,
    ) -> list[ExtractedErrorCode]:
        """Create category entries for parent codes that don't already exist."""
        parent_codes = {c.parent_code for c in codes if c.parent_code}
        existing_codes = {c.error_code for c in codes}
        categories: list[ExtractedErrorCode] = []
        for parent in sorted(parent_codes):
            if parent in existing_codes:
                continue
            children = [c for c in codes if c.parent_code == parent]
            if not children:
                continue
            best_child = max(children, key=lambda c: c.confidence)
            child_descs = [f"{c.error_code} {c.error_description[:60]}" for c in children[:5]]
            description = f"{parent} error family ({len(children)} codes: {', '.join(child_descs)})"
            if len(description) < 10:
                description = f"{parent} error code category"
            try:
                category = ExtractedErrorCode(
                    error_code=parent,
                    error_description=description,
                    solution_customer_text=None,
                    solution_agent_text=None,
                    solution_technician_text=None,
                    context_text=best_child.context_text,
                    confidence=0.95,
                    page_number=best_child.page_number,
                    extraction_method=f"{mfr_key}_category",
                    severity_level="medium",
                    manufacturer_name=manufacturer_name,
                    effective_manufacturer=best_child.effective_manufacturer,
                    is_category=True,
                )
                categories.append(category)
            except Exception as exc:
                logger.debug("Failed to create category entry for '%s': %s", parent, exc)
        return categories

    def _validate_context(self, context: str) -> bool:
        """Validate that context looks like an error code section"""
        context_lower = context.lower()

        # Check for required keywords
        required_keywords = self.extraction_rules.get("require_context_keywords", [])
        has_required = any(kw in context_lower for kw in required_keywords)

        # Check for excluded keywords
        excluded_keywords = self.extraction_rules.get("exclude_if_near", [])
        has_excluded = any(kw in context_lower for kw in excluded_keywords)

        return has_required and not has_excluded

    def _extract_context(self, text: str, start_pos: int, end_pos: int, context_size: int = 500) -> str:
        """
        Extract context around error code

        Args:
            text: Full text
            start_pos: Error code start position
            end_pos: Error code end position
            context_size: Characters to include before/after

        Returns:
            Context text
        """
        context_start = max(0, start_pos - context_size)
        context_end = min(len(text), end_pos + context_size)

        context = text[context_start:context_end]
        return context.strip()

    def _extract_description(
        self,
        text: str,
        code_end_pos: int,
        max_length: int = 500,
        code_start_pos: int | None = None,
    ) -> str | None:
        """
        Extract error description (text after error code)

        For Konica Minolta: Looks for 'Classification' section
        For others: Extracts text after error code

        Args:
            text: Full text
            code_end_pos: Position where error code ends
            max_length: Maximum description length

        Returns:
            Description or None
        """
        # Extract text after code
        remaining_text = text[code_end_pos : code_end_pos + max_length * 2]

        # Try to find structured sections (Konica Minolta format)
        # PERFORMANCE: Use pre-compiled pattern
        classification_match = CLASSIFICATION_PATTERN.search(remaining_text)
        if classification_match:
            description = classification_match.group(1).strip()
            # Limit to max_length
            if len(description) > max_length:
                description = description[:max_length].rsplit(" ", 1)[0]
            return description

        # Fallback: Extract text after code (original logic)
        remaining_text = remaining_text[:max_length]

        # Skip leading whitespace/newlines so codes in table rows (where the
        # description appears on the NEXT line) don't cause an immediate
        # sentence-end hit at position 0 and fall through to the backward search.
        remaining_text_trimmed = remaining_text.lstrip()

        # Pre-normalize soft-wrapped lines: PDF tables/columns often break sentences
        # at narrow widths (e.g. Lexmark: "Paper fed from the MPF was\ndetected...").
        # Join lines where the continuation starts with a lowercase letter or comma
        # so SENTENCE_END_PATTERN can find the real sentence boundary (period).
        remaining_text_trimmed = re.sub(r"\n(?=[a-z,])", " ", remaining_text_trimmed)

        # Find end of sentence or paragraph
        # PERFORMANCE: Use pre-compiled pattern
        sentence_end = SENTENCE_END_PATTERN.search(remaining_text_trimmed)

        if sentence_end:
            description = remaining_text_trimmed[: sentence_end.start()].strip()
        else:
            description = remaining_text_trimmed.strip()

        # Keep searching with fallback heuristics when forward description is near-empty.
        # Only clear truly insufficient results: ≤ 5 chars or a single non-letter token.
        if len(description) < 5 or (len(description) < 15 and " " not in description):
            description = ""

        # Remove common prefixes (including = which appears in HP CPMD table cells)
        for prefix in ["=", ":", "-", "-", "—", "error", "code"]:  # second "-" placeholder
            description = description.lstrip(prefix).strip()

        # Strip leading standalone numbers/symbols (e.g. "70 Black toner" → "Black toner", "06 Over heat" → "Over heat")
        description = re.sub(r"^[\d●•\s]+(?=[A-Za-z])", "", description).strip()

        # Strip trailing bullet/list symbols (e.g. "Over heat error ●" → "Over heat error")
        description = re.sub(r"[\s●•]+$", "", description).strip()

        # Strip outer parentheses if the whole description is wrapped (e.g. "(Dual-cassette feeder)")
        if description.startswith("(") and description.endswith(")"):
            description = description[1:-1].strip()

        # Return a complete inline phrase immediately (≥ 2 words starting with a letter)
        # so table-format codes like "10.05.35 Black drum unit" don't fall through to
        # backward search which would pick up the previous line's text.
        _words = description.split()
        if description and (len(description) >= 100 or (len(_words) >= 2 and description[0].isalpha())):
            return description

        # Fallback for table/list layouts where the useful description appears
        # before the error code (e.g. "Error when disconnected ... 63.00.02").
        if code_start_pos is not None:
            window_start = max(0, code_start_pos - 350)
            before_text = text[window_start:code_start_pos]
            before_compact = re.sub(r"\s+", " ", before_text).strip()
            if before_compact:
                marker_patterns = [
                    r"(error\s+when\s+disconnected[^.;\n]{10,260})$",
                    r"((?:error|fault|alarm|warning|message)[^.;\n]{12,260})$",
                    r"([^.;\n]{20,260})$",
                ]
                for marker in marker_patterns:
                    match = re.search(marker, before_compact, re.IGNORECASE)
                    if not match:
                        continue
                    candidate = match.group(1).strip(" -:;,.")
                    candidate = re.sub(r"\s+", " ", candidate)
                    if len(candidate) >= 20:
                        return candidate[:max_length]

        # Return shorter forward result as last resort (e.g. "Dual-cassette feeder")
        if description and len(description) >= 10:
            return description

        return None

    def _extract_solution(self, context: str, full_text: str, code_end_pos: int) -> str | None:
        """
        Extract solution steps from context or following text

        Handles multiple formats:
        - "Recommended action for customers" (HP style)
        - "Solution:" sections
        - Numbered troubleshooting steps
        - Bullet point lists

        Returns:
            Solution text or None
        """
        # Extended text window for better extraction (increased for multi-page procedures)
        text_after = full_text[code_end_pos : code_end_pos + 5000]
        combined_text = context + "\n" + text_after

        # Pattern 1: HP/Manufacturer style "Recommended action" OR Konica Minolta "Measures/Correction"
        # PERFORMANCE: Use pre-compiled pattern (avoids recompilation 3919+ times!)
        # Search text_after only (not combined_text) to avoid context-tail contamination:
        # combined_text includes 500 chars AFTER the code match, which can bleed into procedure
        # steps mid-sentence, causing description text from the next code match to be
        # appended as a step continuation (e.g. ": Paper feed communication error" on step 2).
        match = RECOMMENDED_ACTION_PATTERN.search(text_after)
        if match:
            # Use full post-header text (not just group(1)) so multi-line steps are captured via continuation logic
            post_header = text_after[match.start(1) : match.start(1) + 3000]
            # Clip at earliest section-end marker to avoid capturing unrelated content
            earliest_end = len(post_header)
            for end_pat in [SECTION_END_NUMBERED, SECTION_END_NOTE, SECTION_END_TITLE]:
                end_m = end_pat.search(post_header)
                if end_m and end_m.start() < earliest_end:
                    earliest_end = end_m.start()
            post_header = post_header[:earliest_end]
            lines = post_header.split("\n")
            filtered_lines = []
            for line in lines[:80]:
                # Match main steps (1., 1)) AND sub-steps (  1), 2), a), etc.)
                # PERFORMANCE: Use pre-compiled pattern
                if STEP_LINE_PATTERN.match(line):
                    filtered_lines.append(line.strip())
                elif (
                    filtered_lines and len(line.strip()) > 3
                ):  # Continuation line (lowered from 10 to catch short words)
                    filtered_lines[-1] += " " + line.strip()
                elif filtered_lines and not line.strip():  # Empty line between steps - keep going
                    continue
                elif (
                    filtered_lines and line.strip() and len(line.strip()) <= 3 and line.strip()[0].isupper()
                ):  # Very short section marker
                    break
            if filtered_lines:
                return "\n".join(filtered_lines)

        # Pattern 2: Standard "Solution:" or "Fix:" sections
        # PERFORMANCE: Use pre-compiled pattern
        match = SOLUTION_KEYWORDS_PATTERN.search(combined_text)
        if match:
            solution = match.group(1).strip()
            # Extract until next section header or end
            # PERFORMANCE: Use pre-compiled patterns
            for pattern in [SECTION_END_NOTE, SECTION_END_TITLE, SECTION_END_NUMBERED]:
                section_end = pattern.search(solution)
                if section_end:
                    solution = solution[: section_end.start()]
                    break
            return solution[:3000].strip()  # Limit length (increased from 1000 to 3000)

        # Pattern 3: Numbered steps without header (1., 1), 2), Step 1, ...)
        # PERFORMANCE: Use pre-compiled pattern
        match = NUMBERED_STEPS_PATTERN.search(text_after)
        if match:
            # Use text from match.start() rather than match.group(1) to avoid lazy-quantifier
            # truncation: the outer {2,} greedy group is satisfied with the minimum 2 reps, so
            # the 2nd line's lazy .{15,500}? stops at only 15 chars instead of the full line.
            remaining = text_after[match.start() :]
            lines = [ln.strip() for ln in remaining.split("\n") if ln.strip()]
            step_lines = []
            for line in lines[:30]:
                # PERFORMANCE: Use pre-compiled pattern
                if STEP_MATCH_PATTERN.match(line):
                    step_lines.append(line)
                elif step_lines and len(line) > 20:  # Continuation of previous step
                    step_lines[-1] += " " + line
            if len(step_lines) >= 2:
                return "\n".join(step_lines)

        # Pattern 4: Bullet point lists
        # PERFORMANCE: Use pre-compiled pattern
        match = BULLET_PATTERN.search(text_after)
        if match:
            # Skip if bullets are from a "Relevant electrical parts" section (not a procedure).
            # Check both before AND inside the match — the "-" trouble-isolation marker can
            # be the first "bullet", with the parts header appearing inside the match group.
            search_window = text_after[: match.start() + len(match.group(1))]
            if not re.search(
                r"(?:Relevant electrical parts|Relevant parts|Electrical parts)", search_window, re.IGNORECASE
            ):
                bullets = match.group(1).strip()
                lines = [ln.strip() for ln in bullets.split("\n") if ln.strip()][:30]
                return "\n".join(lines)

                # Return raw full-text — levels are split later at ExtractedErrorCode creation

        # No solution found — return full combined text (levels split at creation)
        # Guard: if result looks like a Table of Contents (dot leaders ......), discard it
        if combined_text and re.search(r"\.{10,}", combined_text):
            return None
        # Guard: if result looks like a trouble code listing table, discard it
        if combined_text and re.search(r"Trouble Code\s*\nContents\s*\nRank", combined_text):
            return None
        # Guard: only return fallback if text_after contains numbered steps.
        # Requiring steps in text_after (not just combined_text) prevents context from
        # neighboring sections from being returned as this code's solution.
        # Supports both "1. Step" and "1 Check" (Lexmark) formats.
        # Use [ \t]+ (not \s+) to avoid false positives where "245.\n200.05" looks like a step.
        if not re.search(r"^\s*\d+[\.\)][ \t]+\w|^\s*\d+[ \t]+[A-Z]", text_after, re.MULTILINE):
            return None
        return combined_text if combined_text else None

    def _is_generic_description(self, description: str) -> bool:
        """
        Check if description is too generic to be useful

        Returns:
            True if generic
        """
        # Fragment check: description starting with lowercase is likely a
        # continuation from a preceding code's text in an index/list table.
        if description and description[0].islower():
            return True

        generic_phrases = [
            "refer to manual",
            "see documentation",
            "contact support",
            "error code",
            "see page",
            "refer to page",
            "table",
            "figure",
        ]

        desc_lower = description.lower()

        # If short and contains generic phrase
        if len(description) < 50:
            for phrase in generic_phrases:
                if phrase in desc_lower:
                    return True

        return False

    def _calculate_confidence(self, code: str, description: str, solution: str | None, context: str) -> float:
        """
        Calculate extraction confidence based on quality indicators

        Returns:
            Confidence score (0.0 - 1.0)
        """
        confidence = 0.0

        # Base confidence for valid format
        confidence += 0.3

        # Has proper description (not generic)
        if description and len(description) > 30:
            confidence += 0.2
        if description and len(description) > 100:
            confidence += 0.1

        # Has solution steps
        if solution:
            confidence += 0.2
            # Bonus for numbered or bulleted steps
            if re.search(r"\d+\.|\•|\*", solution):
                confidence += 0.1

        # Context contains technical terms
        context_lower = context.lower()
        tech_term_count = sum(1 for term in TECHNICAL_TERMS if term in context_lower)
        if tech_term_count > 0:
            confidence += 0.1
        if tech_term_count > 3:
            confidence += 0.1

        # Code appears multiple times (important!)
        if context.count(code) > 1:
            confidence += 0.1

        # Context has reasonable length
        if 200 < len(context) < 2000:
            confidence += 0.05

        return min(confidence, 1.0)

    def _determine_severity(self, description: str, solution: str | None) -> str:
        """
        Determine error severity from description

        Returns:
            One of: low, medium, high, critical
        """
        text = f"{description} {solution or ''}".lower()

        # Critical keywords
        if any(kw in text for kw in ["critical", "fatal", "shutdown", "stop"]):
            return "critical"

        # High severity
        if any(kw in text for kw in ["major", "serious", "damage", "failure"]):
            return "high"

        # Low severity
        if any(kw in text for kw in ["minor", "warning", "informational", "notice"]):
            return "low"

        # Default to medium
        return "medium"

    def _deduplicate(self, error_codes: list[ExtractedErrorCode]) -> list[ExtractedErrorCode]:
        """
        Remove duplicate error codes, keep highest confidence

        Args:
            error_codes: List of error codes

        Returns:
            Deduplicated list
        """
        if not error_codes:
            return []

        # Group by error_code
        seen: dict[str, ExtractedErrorCode] = {}
        for ec in error_codes:
            key = ec.error_code
            if key not in seen or ec.confidence > seen[key].confidence:
                seen[key] = ec

        return list(seen.values())

    def extract_from_structured_data(
        self,
        structured_data: dict[str, Any],
        manufacturer: str | None,
        document_id: UUID | None = None,
        source_url: str | None = None,
    ) -> list[dict[str, Any]]:
        """Extract error codes from Firecrawl structured extraction payloads."""

        error_codes = structured_data.get("error_codes") or []
        if not error_codes:
            return []

        dedup: dict[str, dict[str, Any]] = {}
        for code_data in error_codes:
            code = (code_data or {}).get("code")
            if not code:
                continue

            if not self._validate_code_format(code, manufacturer):
                self.logger.debug("Skipping invalid code format: %s", code)
                continue

            confidence = float(code_data.get("confidence") or structured_data.get("confidence") or 0.8)

            entry = {
                "code": code,
                "manufacturer": manufacturer,
                "description": code_data.get("description", ""),
                "solution": code_data.get("solution", ""),
                "severity": code_data.get("severity", "warning"),
                "requires_parts": bool(code_data.get("requires_parts", False)),
                "related_parts": code_data.get("related_parts") or [],
                "confidence": confidence,
                "extraction_method": "firecrawl_structured",
                "source_url": source_url,
                "document_id": str(document_id) if document_id else None,
                "related_error_codes": code_data.get("related_error_codes") or [],
                "affected_models": code_data.get("affected_models") or [],
            }

            existing = dedup.get(code)
            if not existing or confidence > existing.get("confidence", 0.0):
                dedup[code] = entry

        return list(dedup.values())

    def _validate_code_format(self, code: str, manufacturer: str | None) -> bool:
        """Validate error code format against manufacturer validation regex."""

        if not manufacturer:
            # Without manufacturer context accept the code
            return True

        validation_regex = self._get_validation_regex(manufacturer, manufacturer)
        if not validation_regex:
            return True

        try:
            return bool(re.match(validation_regex, code))
        except re.error as exc:
            self.logger.debug("Invalid validation regex '%s': %s", validation_regex, exc)
            return True

    def enrich_from_link_content(
        self,
        link_id: UUID,
        database_service: Any,
    ) -> list[dict[str, Any]]:
        """Extract error codes from enriched link content or structured data."""

        client = getattr(database_service, "service_client", None) or getattr(database_service, "client", None)
        if client is None:
            self.logger.warning("Database service client unavailable for link enrichment")
            return []

        response = (
            client.table("vw_links")
            .select("id, url, scraped_content, manufacturer_id, document_id")
            .eq("id", str(link_id))
            .limit(1)
            .execute()
        )

        if not response.data:
            self.logger.warning("Link %s not found", link_id)
            return []

        link = response.data[0]
        content = link.get("scraped_content")

        manufacturer_id = link.get("manufacturer_id")
        manufacturer_name = self._get_manufacturer_name(manufacturer_id, client)

        structured_result = (
            client.table("structured_extractions", schema="krai_intelligence")
            .select("extracted_data, confidence")
            .eq("source_type", "link")
            .eq("source_id", str(link_id))
            .eq("extraction_type", "error_code")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if structured_result.data:
            payload = structured_result.data[0]
            return self.extract_from_structured_data(
                structured_data=payload.get("extracted_data", {}),
                manufacturer=manufacturer_name,
                document_id=link.get("document_id"),
                source_url=link.get("url"),
            )

        if not content:
            self.logger.debug("Link %s has no scraped content to extract from", link_id)
            return []

        extracted = self.extract_from_text(
            text=content,
            page_number=0,
            manufacturer_name=manufacturer_name,
        )

        return [
            {
                "code": ec.error_code,
                "manufacturer": manufacturer_name,
                "description": ec.error_description,
                "solution": ec.solution_technician_text or ec.solution_agent_text or ec.solution_customer_text,
                "severity": ec.severity_level,
                "requires_parts": ec.requires_parts,
                "related_parts": [],
                "confidence": ec.confidence,
                "extraction_method": ec.extraction_method,
                "source_url": link.get("url"),
                "document_id": str(link.get("document_id")) if link.get("document_id") else None,
                "related_error_codes": [],
                "affected_models": [],
            }
            for ec in extracted
        ]

    def _get_manufacturer_name(self, manufacturer_id: str | None, client: Any) -> str | None:
        if not manufacturer_id:
            return None

        try:
            result = client.table("vw_manufacturers").select("name").eq("id", str(manufacturer_id)).limit(1).execute()
            if result.data:
                name = result.data[0].get("name")
                return cast(str | None, name)
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.debug("Failed to load manufacturer name for %s: %s", manufacturer_id, exc)

        return None

    def _get_validation_regex(self, manufacturer_name: str | None, effective_manufacturer: str | None) -> str | None:
        """Resolve the appropriate validation regex for a manufacturer."""
        # Prefer effective manufacturer, but fall back to declared name for logging clarity
        for name in (effective_manufacturer, manufacturer_name):
            key = self._get_manufacturer_key(name)
            if key and key in self.patterns_config:
                regex = self.patterns_config[key].get("validation_regex")
                return cast(str | None, regex)
        return None

    def validate_extraction(self, error_code: ExtractedErrorCode) -> list[ValError]:
        """
        Validate extracted error code

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        validation_regex = self._get_validation_regex(error_code.manufacturer_name, error_code.effective_manufacturer)

        if validation_regex and not re.match(validation_regex, error_code.error_code):
            errors.append(
                ValError(
                    field="error_code",
                    value=error_code.error_code,
                    error_message=("Error code doesn't match manufacturer validation regex " f"'{validation_regex}'"),
                    severity="error",
                )
            )
        elif not validation_regex:
            self.logger.debug(
                "No validation regex available for manufacturer '%s' (effective: '%s')",
                error_code.manufacturer_name,
                error_code.effective_manufacturer,
            )

        # Check description length
        if len(error_code.error_description) < 20:
            errors.append(
                ValError(
                    field="error_description",
                    value=error_code.error_description,
                    error_message="Description too short (< 20 chars)",
                    severity="warning",
                )
            )

        # Check confidence
        if error_code.confidence < 0.6:
            errors.append(
                ValError(
                    field="confidence",
                    value=error_code.confidence,
                    error_message="Confidence below threshold (0.6)",
                    severity="error",
                )
            )

        return errors


# Convenience function
def extract_error_codes_from_text(text: str, page_number: int) -> list[ExtractedErrorCode]:
    """
    Convenience function to extract error codes from text

    Args:
        text: Text to extract from
        page_number: Page number

    Returns:
        List of validated error codes
    """
    extractor = ErrorCodeExtractor()
    return extractor.extract_from_text(text, page_number)


def find_chunk_for_error_code(error_code: str, page_number: int, chunks: list[dict], logger=None) -> str | None:
    """
    Find the intelligence chunk that contains this error code

    Strategy:
    1. Prefer chunks on same page that contain the error code
    2. Fallback to any chunk containing the error code
    3. Return None if not found

    Args:
        error_code: The error code to find (e.g., "66.60.32")
        page_number: Page where error code was found
        chunks: List of chunk dicts from database
        logger: Optional logger

    Returns:
        chunk_id (UUID as string) or None
    """
    if not chunks:
        return None

    # Strategy 1: Same page + contains error code
    for chunk in chunks:
        chunk_page = chunk.get("page_start") or chunk.get("page_number")
        chunk_text = chunk.get("text_chunk", "")
        chunk_id = chunk.get("id")

        if chunk_page == page_number and error_code in chunk_text and chunk_id:
            if logger:
                logger.debug(f"Found chunk for {error_code} on page {page_number}")
            return str(chunk_id)

    # Strategy 2: Any chunk containing error code
    for chunk in chunks:
        chunk_text = chunk.get("text_chunk", "")
        chunk_id = chunk.get("id")

        if error_code in chunk_text and chunk_id:
            if logger:
                logger.debug(f"Found chunk for {error_code} (different page)")
            return str(chunk_id)

    if logger:
        logger.debug(f"No chunk found for {error_code}")
    return None
