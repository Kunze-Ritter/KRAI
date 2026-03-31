"""
Metadata Processor (AI) - Extract metadata using AI

Stage 7 of the processing pipeline.

Extracts error codes, version numbers, and other metadata from documents.
Uses pattern matching and AI for intelligent extraction.
"""

import re as _re

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage
from backend.core.data_models import ErrorCodeModel

from .error_code_extractor import ErrorCodeExtractor
from .version_extractor import VersionExtractor


class MetadataProcessorAI(BaseProcessor):
    """
    Stage 7: Metadata Processor (AI)

    Extracts metadata like error codes and version numbers.
    Uses pattern matching for error codes and AI for complex metadata.
    """

    def __init__(self, database_service=None, ai_service=None, config_service=None):
        """
        Initialize metadata processor

        Args:
            database_service: Database service instance
            ai_service: AI service instance
            config_service: Config service instance
        """
        super().__init__(name="metadata_processor_ai")
        self.stage = Stage.METADATA_EXTRACTION
        self.database_service = database_service
        self.ai_service = ai_service
        self.config_service = config_service

        # Initialize extractors
        self.error_code_extractor = ErrorCodeExtractor()
        self.version_extractor = VersionExtractor()

        self.logger.info("MetadataProcessorAI initialized")

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Process metadata extraction

        Args:
            context: Processing context with file_path and document_id

        Returns:
            Processing result with error_codes_extracted count
        """
        with self.logger_context(document_id=getattr(context, "document_id", None), stage=self.stage) as adapter:
            try:
                manufacturer = await self._get_document_manufacturer(context.document_id)
                manufacturer, manufacturer_id = manufacturer

                if not manufacturer or manufacturer == "Unknown":
                    adapter.warning("No manufacturer found - using AUTO detection")
                    manufacturer = "AUTO"

                adapter.info("Extracting error codes (manufacturer: %s)...", manufacturer)
                error_codes = await self._extract_error_codes_from_chunks(
                    document_id=context.document_id,
                    manufacturer=manufacturer,
                    adapter=adapter,
                )

                if error_codes:
                    self.logger.success(f"✅ Extracted {len(error_codes)} error codes")

                    if self.database_service:
                        saved_count = await self._save_error_codes(
                            error_codes,
                            context.document_id,
                            manufacturer,
                            adapter,
                            manufacturer_id=manufacturer_id,
                        )
                        self.logger.success(f"✅ Saved {saved_count} error codes to database")
                else:
                    adapter.info("No error codes found")

                adapter.info("Extracting version information...")

                version_info = None
                version_text = None
                page_texts = getattr(context, "page_texts", None)
                if isinstance(page_texts, dict) and page_texts:
                    first_pages = sorted(page_texts.keys())[:5]
                    version_text = "\n\n".join(
                        [page_texts.get(p, "") for p in first_pages if page_texts.get(p)]
                    ).strip()

                if version_text:
                    best_version = self.version_extractor.extract_best_version(
                        version_text,
                        manufacturer=None if manufacturer == "AUTO" else manufacturer,
                    )
                    version_info = best_version.version_string if best_version else None
                else:
                    adapter.warning("No page text available - skipping version extraction")

                if version_info:
                    self.logger.success(f"✅ Extracted version: {version_info}")

                    if self.database_service:
                        await self._update_document_version(context.document_id, version_info, adapter)

                return self._create_result(
                    success=True,
                    message=f"Metadata extraction completed: {len(error_codes)} error codes",
                    data={"error_codes_extracted": len(error_codes), "version_info": version_info},
                )

            except Exception as e:
                adapter.error("Metadata extraction failed: %s", e)
                self.logger.error(f"Metadata extraction failed: {e}")
                return self._create_result(success=False, message=f"Metadata extraction error: {e!s}", data={})

    async def _get_document_manufacturer(self, document_id: str) -> tuple[str, str | None]:
        """Get manufacturer name and id from document. Returns (name, manufacturer_id)."""
        if not self.database_service:
            return "AUTO", None

        try:
            if hasattr(self.database_service, "get_document"):
                doc = await self.database_service.get_document(document_id)
                if doc:
                    name = getattr(doc, "manufacturer", "AUTO") or "AUTO"
                    mid = getattr(doc, "manufacturer_id", None)
                    return name, str(mid) if mid else None
            elif hasattr(self.database_service, "client"):
                result = (
                    self.database_service.client.table("documents")
                    .select("manufacturer,manufacturer_id")
                    .eq("id", document_id)
                    .execute()
                )
                if result.data:
                    row = result.data[0]
                    return row.get("manufacturer", "AUTO") or "AUTO", row.get("manufacturer_id")
        except Exception as e:
            self.logger.warning(f"Could not get manufacturer: {e}")

        return "AUTO", None

    async def _extract_error_codes_from_chunks(self, document_id: str, manufacturer: str, adapter) -> list:
        """Extract error codes by scanning document chunks."""
        if not self.database_service or not hasattr(self.database_service, "get_chunks_by_document"):
            adapter.warning("Chunk access unavailable - cannot extract error codes")
            return []

        chunks = await self.database_service.get_chunks_by_document(document_id)
        if not chunks:
            adapter.warning("No chunks found for error code extraction")
            return []

        extracted = []
        seen_codes: dict[str, int] = {}  # code → index in extracted

        # Deduplicate chunks by fingerprint to avoid processing the same text multiple times
        # (can happen when text_processor runs multiple times without deleting old chunks)
        seen_fingerprints: set[str] = set()

        for chunk in chunks:
            chunk_dict = dict(chunk) if not isinstance(chunk, dict) else chunk

            # Skip duplicate chunks (same fingerprint = same text content)
            fingerprint = chunk_dict.get("fingerprint")
            if fingerprint:
                if fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(fingerprint)

            text = chunk_dict.get("text_chunk") or chunk_dict.get("content") or chunk_dict.get("text") or ""
            if not text:
                continue

            page_number = chunk_dict.get("page_start") or chunk_dict.get("page_number") or 1
            chunk_codes = self.error_code_extractor.extract_from_text(
                text=text,
                page_number=int(page_number),
                manufacturer_name=manufacturer if manufacturer != "AUTO" else None,
            )
            for code in chunk_codes:
                key = getattr(code, "error_code", None)
                if not key:
                    continue
                # Preserve chunk linkage where possible.
                raw_id = chunk_dict.get("id")
                setattr(code, "chunk_id", str(raw_id) if raw_id is not None else None)

                if key not in seen_codes:
                    seen_codes[key] = len(extracted)
                    extracted.append(code)
                    continue

                # A duplicate code was found in a later chunk — keep the BETTER extraction.
                # "Better" means: has numbered procedure steps (vs. revision-history garbage).
                idx = seen_codes[key]
                existing = extracted[idx]
                existing_sol = getattr(existing, "solution_technician_text", "") or ""
                new_sol = getattr(code, "solution_technician_text", "") or ""
                existing_desc = getattr(existing, "error_description", "") or ""
                new_desc = getattr(code, "error_description", "") or ""

                _step_pat = _re.compile(r"^\s*\d+[\.\)]\s+\w", _re.MULTILINE)
                existing_has_steps = bool(_step_pat.search(existing_sol))
                new_has_steps = bool(_step_pat.search(new_sol))

                replace = False
                if (
                    (new_has_steps and not existing_has_steps)
                    or (not existing_has_steps and len(new_sol) > len(existing_sol))
                    or (len(new_desc) > len(existing_desc) * 1.5 and len(new_desc) > 50)
                ):
                    replace = True

                if replace:
                    extracted[idx] = code

        # For codes without solutions that reference a service check page, try to
        # find the service check chunk and use its text as the solution.
        return self._enrich_solutions_from_service_check_refs(extracted, chunks, adapter)

    # ------------------------------------------------------------------
    # Service-check reference lookup for Lexmark-style PDFs
    # ------------------------------------------------------------------
    _SEE_PAGE_PATTERN = _re.compile(
        r"[Ff]or more information[,\s]*see\s+(.+?)\s+on\s+page\s+\d+",
        _re.DOTALL,
    )
    # Matches bare step markers: "1.", "2.", "a.", "b.", "10.", "c."
    _BARE_STEP_RE = _re.compile(r"^(?:\d+|[a-zA-Z])[.)]\s*$")
    # Short non-ASCII only lines = garbled bullet symbols from PDF rendering
    _GARBLED_BULLET_RE = _re.compile(r"^[\u0080-\uffff]{1,6}\s*$")
    # Detects TOC-style reference lines: "See <name> on page N"
    _TOC_LINE_RE = _re.compile(r"[Ss]ee .+ on page \d+")
    # Extract page number from a "see ... on page N" reference
    _SEE_PAGE_NUM_RE = _re.compile(r"on page (\d+)")

    def _enrich_solutions_from_service_check_refs(self, extracted: list, chunks, adapter) -> list:
        """
        For error codes that have no solution but whose context contains a
        'For more information, see <name> on page N' reference, find the
        matching service-check chunk and use its cleaned text as the solution.

        This handles Lexmark-style PDFs where error code listing pages only
        reference a separate service-check page for the actual repair steps.
        """
        codes_without_solution = [
            c
            for c in extracted
            if not getattr(c, "is_category", False) and not (getattr(c, "solution_technician_text", None) or "").strip()
        ]
        if not codes_without_solution:
            return extracted

        # Build a list of (chunk_id, page_start, text) for searching.
        chunk_data: list[tuple] = []
        for ch in chunks:
            ch_dict = dict(ch) if not isinstance(ch, dict) else ch
            cid = ch_dict.get("id")
            txt = ch_dict.get("text_chunk") or ch_dict.get("content") or ch_dict.get("text") or ""
            page_start = ch_dict.get("page_start") or ch_dict.get("page_number") or 0
            if cid and txt:
                chunk_data.append((cid, int(page_start or 0), txt))

        enriched_count = 0
        for code in codes_without_solution:
            context = getattr(code, "context_text", "") or ""
            m = self._SEE_PAGE_PATTERN.search(context)
            if not m:
                continue

            service_check_name = _re.sub(r"\s+", " ", m.group(1)).strip()
            if len(service_check_name) < 10:
                continue

            # Extract the referenced page number if available.
            page_m = self._SEE_PAGE_NUM_RE.search(m.group(0))
            ref_page = int(page_m.group(1)) if page_m else None

            search_key = service_check_name[:60].lower()
            best_text: str | None = None
            best_score = -1

            for _cid, page_start, chunk_text in chunk_data:
                chunk_lower = chunk_text.lower()
                if search_key not in chunk_lower:
                    continue

                # Skip TOC/revision-history chunks:
                # they contain many "See ... on page N" cross-references
                toc_refs = len(self._TOC_LINE_RE.findall(chunk_text))
                if toc_refs > 3:
                    continue

                # Find ALL occurrences of the service-check name; require at least
                # one that is a STANDALONE title (not inside a "see ... on page N" ref).
                standalone_idx: int | None = None
                start = 0
                while True:
                    idx = chunk_lower.find(search_key, start)
                    if idx < 0:
                        break
                    prefix = chunk_lower[max(0, idx - 25) : idx]
                    suffix = chunk_lower[idx + len(search_key) : idx + len(search_key) + 60]
                    preceded_by_see = bool(_re.search(r"\bsee\s+$", prefix.rstrip()))
                    followed_by_see = bool(_re.search(r"^[^.\n]*\.\s*[Ss]ee\s", suffix))
                    if not preceded_by_see and not followed_by_see:
                        standalone_idx = idx
                        break
                    start = idx + 1

                if standalone_idx is None:
                    continue  # Only references found, no standalone title

                # The cleaned content after the title must have ≥80 chars of
                # substantive text (not just references or step markers).
                candidate = self._clean_service_check_chunk(chunk_text, service_check_name)
                lines_candidate = candidate.splitlines()
                ref_lines = sum(1 for ln in lines_candidate if "on page" in ln.lower())
                total_lines = len(lines_candidate)
                if total_lines > 0 and ref_lines / total_lines > 0.5:
                    continue  # Mostly cross-references, skip
                if len(candidate) < 80:
                    continue

                # Prefer chunks whose page_start matches the referenced page.
                page_bonus = 500 if (ref_page and page_start == ref_page) else 0
                # Prefer chunks where the standalone title is near the top.
                position_score = max(0, 1000 - standalone_idx)
                score = position_score + page_bonus + len(candidate) // 10

                if score > best_score:
                    best_score = score
                    best_text = candidate  # already cleaned

            if not best_text:
                continue

            code.solution_technician_text = best_text
            enriched_count += 1

        if enriched_count:
            adapter.info(
                "Enriched %d error code(s) with service-check solutions via page reference",
                enriched_count,
            )
        return extracted

    def _clean_service_check_chunk(self, text: str, service_check_name: str | None = None) -> str:
        """
        Remove noise from a service-check chunk:
          - Bare step markers ("1.", "a.", "b.")
          - Garbled bullet symbols from PDF rendering (e.g. 'Ôùª', 'ÔÇó')
          - Blank lines
        Returns the substantive diagnostic text.
        """
        # If the chunk contains the service check name, trim to the relevant section.
        if service_check_name:
            name_key = service_check_name[:50].lower()
            idx = text.lower().find(name_key)
            if idx >= 0:
                text = text[idx:]

        lines = text.split("\n")
        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if self._BARE_STEP_RE.match(stripped):
                continue
            if self._GARBLED_BULLET_RE.match(stripped):
                continue
            cleaned.append(stripped)

        return "\n".join(cleaned).strip()

    async def _save_error_codes(
        self,
        error_codes: list,
        document_id: str,
        manufacturer: str,
        adapter,
        manufacturer_id: str | None = None,
    ) -> int:
        """Save error codes to database via DatabaseAdapter or Supabase client. Fails or logs when neither is available."""
        if not self.database_service:
            adapter.error("Cannot save error codes: no database_service available")
            return 0

        has_adapter = hasattr(self.database_service, "create_error_code")
        has_client = hasattr(self.database_service, "client") and self.database_service.client is not None

        if not has_adapter and not has_client:
            adapter.error(
                "Cannot save error codes: neither DatabaseAdapter (create_error_code) nor Supabase client available"
            )
            return 0

        saved_count = 0
        for error_code in error_codes:
            try:
                code_value = getattr(error_code, "error_code", None) or ""
                page_num = getattr(error_code, "page_number", None)
                page_num = page_num if page_num is not None else 1

                if has_adapter:
                    model = ErrorCodeModel(
                        document_id=str(document_id),
                        manufacturer_id=manufacturer_id,
                        error_code=str(code_value),
                        error_description=getattr(error_code, "error_description", None) or "No description available",
                        solution_customer_text=getattr(error_code, "solution_customer_text", None),
                        solution_agent_text=getattr(error_code, "solution_agent_text", None),
                        solution_technician_text=getattr(error_code, "solution_technician_text", None),
                        page_number=int(page_num),
                        confidence_score=float(getattr(error_code, "confidence", 0) or 0),
                        extraction_method=getattr(error_code, "extraction_method", None) or "pattern",
                        requires_parts=bool(getattr(error_code, "requires_parts", False)),
                        severity_level=str(getattr(error_code, "severity_level", None) or "low"),
                        parent_code=getattr(error_code, "parent_code", None),
                        is_category=bool(getattr(error_code, "is_category", False)),
                        chunk_id=getattr(error_code, "chunk_id", None),
                    )
                    await self.database_service.create_error_code(model)
                    saved_count += 1
                elif has_client:
                    error_data = {
                        "document_id": str(document_id),
                        "error_code": code_value,
                        "error_description": getattr(error_code, "error_description", None),
                        "solution_customer_text": getattr(error_code, "solution_customer_text", None),
                        "solution_agent_text": getattr(error_code, "solution_agent_text", None),
                        "solution_technician_text": getattr(error_code, "solution_technician_text", None),
                        "page_number": page_num,
                        "confidence_score": getattr(error_code, "confidence", None),
                        "extraction_method": getattr(error_code, "extraction_method", None),
                        "requires_parts": getattr(error_code, "requires_parts", False),
                        "severity_level": getattr(error_code, "severity_level", None),
                        "chunk_id": getattr(error_code, "chunk_id", None),
                        "product_id": getattr(error_code, "product_id", None),
                        "video_id": getattr(error_code, "video_id", None),
                        "parent_code": getattr(error_code, "parent_code", None),
                        "is_category": getattr(error_code, "is_category", False),
                    }
                    result = self.database_service.client.table("error_codes").insert(error_data).execute()
                    if result.data:
                        saved_count += 1
            except Exception as e:
                adapter.warning("Failed to save error code %s: %s", getattr(error_code, "error_code", None), e)

        return saved_count

    async def _update_document_version(self, document_id: str, version_info: str, adapter):
        """Update document with version information via DatabaseAdapter or Supabase client. Fails or logs when neither is available."""
        if not self.database_service:
            adapter.error("Cannot update document version: no database_service available")
            return

        has_adapter = hasattr(self.database_service, "update_document")
        has_client = hasattr(self.database_service, "client") and self.database_service.client is not None

        if not has_adapter and not has_client:
            adapter.error(
                "Cannot update document version: neither DatabaseAdapter (update_document) nor Supabase client available"
            )
            return

        try:
            if has_adapter:
                await self.database_service.update_document(document_id, {"version": version_info})
            else:
                self.database_service.client.table("documents").update({"version": version_info}).eq(
                    "id", document_id
                ).execute()
            adapter.info("Updated document version: %s", version_info)
        except Exception as e:
            adapter.warning("Failed to update document version: %s", e)

    def _create_result(self, success: bool, message: str, data: dict) -> ProcessingResult:
        """Create a processing result object using BaseProcessor helpers."""

        if success:
            # Attach human-readable message to metadata for downstream logging.
            return self.create_success_result(data=data, metadata={"message": message})

        error = ProcessingError(message, self.name, "METADATA_PROCESSING_ERROR")
        return self.create_error_result(error=error, metadata={})
