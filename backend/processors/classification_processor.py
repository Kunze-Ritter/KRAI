"""
Classification Processor - Classify documents by manufacturer and type

Stage 4 of the processing pipeline.

Detects manufacturer and document type using AI and pattern matching.
"""

import re
from pathlib import Path
from typing import Any

from backend.core.base_processor import BaseProcessor, Stage
from backend.core.types import ProcessingContext, ProcessingResult
from backend.utils.manufacturer_normalizer import (
    MANUFACTURER_MAP,
    normalize_manufacturer,
    normalize_manufacturer_prefix,
)

from .document_type_detector import DocumentTypeDetector

KNOWN_MANUFACTURER_UUIDS = {
    "HP Inc.": "e7680b1c-d4f8-45fb-934a-3be603c29cac",
}


class ClassificationProcessor(BaseProcessor):
    """
    Stage 4: Classification Processor

    Classifies documents by manufacturer and document type.
    Uses AI for intelligent classification and pattern matching for validation.
    """

    def __init__(
        self, database_service=None, ai_service=None, features_service=None, manufacturer_verification_service=None
    ):
        """
        Initialize classification processor

        Args:
            database_service: Database service instance
            ai_service: AI service instance
            features_service: Features service instance
            manufacturer_verification_service: Web-based manufacturer verification service
        """
        super().__init__(name="classification_processor")
        self.stage = Stage.CLASSIFICATION
        self.database_service = database_service
        self.ai_service = ai_service
        self.features_service = features_service
        self.manufacturer_verification_service = manufacturer_verification_service

        # Initialize document type detector
        self.type_detector = DocumentTypeDetector(debug=False)

        # Known manufacturers for pattern matching
        self.known_manufacturers = [
            "HP",
            "Canon",
            "Epson",
            "Brother",
            "Lexmark",
            "Ricoh",
            "Konica Minolta",
            "Xerox",
            "Samsung",
            "Kyocera",
            "Sharp",
            "Oki",
            "Dell",
            "Toshiba",
            "Panasonic",
            "Develop",
        ]

        self.logger.info("ClassificationProcessor initialized")

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Process classification

        Args:
            context: Processing context with file_path and document_id

        Returns:
            Processing result with manufacturer and document_type
        """
        with self.logger_context(document_id=getattr(context, "document_id", None), stage=self.stage) as adapter:
            try:
                file_path = Path(context.file_path)

                doc_metadata = await self._get_document_metadata(context.document_id)
                await self._hydrate_page_texts_from_chunks(context)

                manufacturer = await self._detect_manufacturer(file_path, doc_metadata, context, adapter)

                if not manufacturer:
                    adapter.warning("Could not detect manufacturer")
                    manufacturer = "Unknown"

                manufacturer_id = await self._resolve_manufacturer_id(manufacturer)
                document_type, version = await self._detect_document_type(
                    file_path, doc_metadata, manufacturer, context, adapter
                )
                model_candidates = self._extract_model_candidates_for_linking(file_path, context)

                if self.database_service:
                    await self._update_document_classification(
                        context.document_id,
                        manufacturer,
                        manufacturer_id,
                        document_type,
                        version,
                        model_candidates=model_candidates,
                    )
                    if manufacturer_id:
                        adapter.info("Manufacturer ID resolved: %s -> %s", manufacturer, manufacturer_id)
                    else:
                        adapter.warning("Manufacturer ID could not be resolved for: %s", manufacturer)
                    linked_products = await self._link_document_products(
                        context.document_id, manufacturer_id, model_candidates, adapter
                    )
                else:
                    linked_products = 0

                self.logger.success(f"✅ Classification: {manufacturer} - {document_type}")

                # Automatic Product Discovery after classification
                models_found = []
                if self.manufacturer_verification_service and manufacturer:
                    try:
                        # Extract models from context if available
                        models = getattr(context, "models", [])
                        if not models and doc_metadata:
                            # Try to extract from filename with multiple patterns
                            filename = doc_metadata.get("filename", "")
                            import re

                            # Multiple regex patterns for different model number formats
                            patterns = [
                                r"[A-Z]{1,3}[-_]?[0-9]{3,5}[A-Z]*",  # E877, M454dn, HL-L8360CDW
                                r"[A-Z]{2,4}[-_][A-Z]?[0-9]{3,5}[A-Z]*",  # HP-E877z, HL-L8360
                                r"(?:Color\s+)?LaserJet\s+(?:Managed\s+)?(?:MFP\s+)?([A-Z]?[0-9]{3,5}[A-Z]*)",  # LaserJet E877z
                            ]

                            for pattern in patterns:
                                matches = re.findall(pattern, filename, re.IGNORECASE)
                                if matches:
                                    # Take first match, clean it up
                                    model = matches[0] if isinstance(matches[0], str) else matches[0][0]
                                    model = model.strip().replace("_", "-")
                                    models = [model]
                                    break

                        if models:
                            self.logger.info(f"🔍 Starting product discovery for {len(models)} model(s)")

                            for model in models[:3]:  # Limit to first 3 models
                                try:
                                    self.logger.info(f"   Discovering: {manufacturer} {model}")

                                    result = await self.manufacturer_verification_service.discover_product_page(
                                        manufacturer=manufacturer,
                                        model_number=model,
                                        save_to_db=True,  # Auto-save to database
                                    )

                                    if result and result.get("url"):
                                        self.logger.success(f"   ✅ Found: {result['url']}")
                                        models_found.append(
                                            {
                                                "model": model,
                                                "url": result["url"],
                                                "confidence": result.get("confidence", 0),
                                                "product_id": result.get("product_id"),
                                            }
                                        )
                                    else:
                                        self.logger.warning(f"   ⚠️  No product page found for {model}")

                                except Exception as e:
                                    self.logger.warning(f"   ⚠️  Product discovery failed for {model}: {e}")

                            if models_found:
                                self.logger.success(
                                    f"✅ Product Discovery: {len(models_found)}/{len(models)} products found"
                                )
                        else:
                            self.logger.debug("No models detected for product discovery")

                    except Exception as e:
                        self.logger.warning(f"Product discovery error: {e}")

                return self._create_result(
                    success=True,
                    message=f"Classification completed: {manufacturer} - {document_type}",
                    data={
                        "manufacturer": manufacturer,
                        "manufacturer_id": manufacturer_id,
                        "document_type": document_type,
                        "version": version,
                        "models_detected_for_linking": model_candidates,
                        "document_products_linked": linked_products,
                        "products_discovered": models_found,
                    },
                )

            except Exception as e:
                adapter.error("Classification failed: %s", e)
                self.logger.error(f"Classification failed: {e}")
                return self._create_result(success=False, message=f"Classification error: {e!s}", data={})

    async def _hydrate_page_texts_from_chunks(self, context: ProcessingContext) -> None:
        """Populate context.page_texts from chunks when upstream context is missing."""
        if getattr(context, "page_texts", None):
            return
        if not self.database_service or not hasattr(self.database_service, "fetch_all"):
            return

        try:
            rows = await self.database_service.fetch_all(
                """
                SELECT page_start, text_chunk
                FROM krai_intelligence.chunks
                WHERE document_id = $1::uuid
                ORDER BY chunk_index
                """,
                [str(context.document_id)],
            )
            pages: dict[int, list[str]] = {}
            for row in rows or []:
                page = row.get("page_start")
                chunk = row.get("text_chunk") or ""
                if page is None or not chunk:
                    continue
                pages.setdefault(int(page), []).append(chunk)

            if pages:
                context.page_texts = {p: "\n".join(parts) for p, parts in pages.items()}
        except Exception as exc:
            self.logger.debug("Could not hydrate page_texts from chunks: %s", exc)

    async def _get_document_metadata(self, document_id: str) -> dict[str, Any]:
        """Get document metadata from database"""
        if not self.database_service:
            return {}

        try:
            if hasattr(self.database_service, "get_document"):
                doc = await self.database_service.get_document(document_id)
                if doc:
                    return {
                        "filename": getattr(doc, "filename", ""),
                        "title": getattr(doc, "title", ""),
                        "file_hash": getattr(doc, "file_hash", ""),
                    }
            elif hasattr(self.database_service, "client"):
                result = self.database_service.client.table("documents").select("*").eq("id", document_id).execute()
                if result.data:
                    return result.data[0]
        except Exception as e:
            self.logger.warning(f"Could not get document metadata: {e}")

        return {}

    async def _detect_manufacturer(self, file_path: Path, doc_metadata: dict[str, Any], context, adapter) -> str | None:
        """
        Detect manufacturer from filename, content, and AI

        Priority:
        1. Filename patterns (HP, Canon, etc.)
        2. Document title
        3. Filename parsing fallback (HP_, KM_, Lexmark machine type, etc.)
        4. First/last pages analysis (introduction & imprint)
        5. AI classification (content chunks)
        """
        filename = file_path.name.lower()

        # 1. Check filename for manufacturer patterns
        for manufacturer in self.known_manufacturers:
            if manufacturer.lower() in filename:
                normalized = normalize_manufacturer(manufacturer)
                adapter.info("Manufacturer detected from filename: %s", normalized)
                return normalized

        # 2. Check document title
        title = doc_metadata.get("title", "").lower()
        for manufacturer in self.known_manufacturers:
            if manufacturer.lower() in title:
                normalized = normalize_manufacturer(manufacturer)
                adapter.info("Manufacturer detected from title: %s", normalized)
                return normalized

        # 3. FALLBACK: Parse filename pattern (e.g., HP_E475_SM.pdf, KM_C759_SM.pdf, 7566-69x_sm.pdf)
        manufacturer = self._parse_manufacturer_from_filename(file_path)
        if manufacturer:
            adapter.info("Manufacturer detected from filename pattern: %s", manufacturer)
            return manufacturer

        # 4. Check first and last pages for manufacturer
        if hasattr(context, "page_texts") and context.page_texts:
            manufacturer = self._detect_manufacturer_from_pages(context.page_texts, adapter)
            if manufacturer:
                return manufacturer

        # 5. Use AI to detect from content (if available)
        if self.ai_service and self.features_service:
            try:
                # Get first few chunks for analysis
                chunks = await self._get_document_chunks(context.document_id, limit=5)
                if chunks:
                    content_sample = "\n".join([chunk.get("content", "") for chunk in chunks[:3]])

                    # Use AI to detect manufacturer
                    manufacturer = await self._ai_detect_manufacturer(content_sample)
                    if manufacturer:
                        adapter.info("Manufacturer detected by AI: %s", manufacturer)
                        return manufacturer
            except Exception as e:
                adapter.warning("AI manufacturer detection failed: %s", e)

        # 6. WEB VERIFICATION FALLBACK: Use web search to verify manufacturer from model numbers
        if self.manufacturer_verification_service:
            potential_models = self._extract_potential_models(file_path, context)
            if potential_models:
                adapter.debug("Attempting web verification with models: %s", potential_models)
                for model in potential_models:
                    try:
                        verification = await self.manufacturer_verification_service.verify_manufacturer(
                            model_number=model, hints=[filename, title]
                        )
                        if verification and verification.get("confidence", 0) > 0.7:
                            manufacturer = verification["manufacturer"]
                            adapter.info(
                                "Manufacturer verified via web search: %s (confidence: %.2f, source: %s)",
                                manufacturer,
                                verification["confidence"],
                                verification.get("source_url", "N/A"),
                            )
                            return manufacturer
                    except Exception as e:
                        adapter.warning("Web verification failed for model %s: %s", model, e)

        return None

    def _detect_manufacturer_from_pages(self, page_texts: dict[int, str], adapter: Any) -> str | None:
        """
        Detect manufacturer from first and last pages

        Analyzes first 3 pages (introduction, branding) and last 2 pages (imprint)
        for manufacturer names using aliases from manufacturer_normalizer.
        More reliable than random chunk analysis.

        Args:
            page_texts: Dictionary mapping page numbers to extracted text
            adapter: Logger adapter for structured logging

        Returns:
            Normalized manufacturer name or None
        """
        if not page_texts or not isinstance(page_texts, dict):
            adapter.debug("No page texts available for manufacturer detection")
            return None

        if not page_texts:
            return None

        # Get total pages
        total_pages = max(page_texts.keys()) if page_texts else 0

        # Handle documents with few pages
        if total_pages < 3:
            # Use all available pages for small documents
            first_pages_text = "\n".join([page_texts.get(i, "") for i in sorted(page_texts.keys())])
            last_pages_text = ""
        elif total_pages < 5:
            # For documents with 3-4 pages, only use first pages (avoid overlap)
            first_pages_text = "\n".join([page_texts.get(i, "") for i in [1, 2, 3]])
            last_pages_text = ""
        else:
            # Extract first 3 pages (focus on first 2000 chars per page for performance)
            first_pages = []
            for i in [1, 2, 3]:
                page_text = page_texts.get(i, "")
                if page_text:
                    first_pages.append(page_text[:2000])
            first_pages_text = "\n".join(first_pages)

            # Extract last 2 pages
            last_page_numbers = [total_pages - 1, total_pages]
            last_pages = []
            for i in last_page_numbers:
                page_text = page_texts.get(i, "")
                if page_text:
                    last_pages.append(page_text)
            last_pages_text = "\n".join(last_pages)

        # Whitelist for short canonical names that should be detected (e.g., HP)
        short_name_whitelist = {"HP"}

        # Search for manufacturer names in first pages (higher priority)
        # Iterate through all canonical manufacturers and their aliases
        for canonical_name, aliases in MANUFACTURER_MAP.items():
            # Check each alias for this manufacturer
            for alias in aliases:
                # Skip very short aliases to avoid false positives, unless whitelisted
                if len(alias) <= 3:
                    if alias.upper() not in short_name_whitelist:
                        adapter.debug("Skipping short alias '%s' (not in whitelist)", alias)
                        continue
                    # For whitelisted short names, ensure strict word boundary matching
                    adapter.debug("Checking whitelisted short alias '%s'", alias)

                # Case-insensitive search with word boundaries
                pattern = r"\b" + re.escape(alias.lower()) + r"\b"
                adapter.debug("Testing alias '%s' with pattern '%s' in first pages", alias, pattern)

                if re.search(pattern, first_pages_text.lower()):
                    # Normalize to canonical name
                    normalized = normalize_manufacturer(alias)
                    adapter.info("Manufacturer detected from first pages (alias '%s'): %s", alias, normalized)
                    return normalized

        # Search for manufacturer names in last pages (lower priority)
        if last_pages_text:
            for canonical_name, aliases in MANUFACTURER_MAP.items():
                # Check each alias for this manufacturer
                for alias in aliases:
                    # Skip very short aliases to avoid false positives, unless whitelisted
                    if len(alias) <= 3:
                        if alias.upper() not in short_name_whitelist:
                            adapter.debug("Skipping short alias '%s' in last pages (not in whitelist)", alias)
                            continue
                        adapter.debug("Checking whitelisted short alias '%s' in last pages", alias)

                    # Case-insensitive search with word boundaries
                    pattern = r"\b" + re.escape(alias.lower()) + r"\b"
                    adapter.debug("Testing alias '%s' with pattern '%s' in last pages", alias, pattern)

                    if re.search(pattern, last_pages_text.lower()):
                        # Normalize to canonical name
                        normalized = normalize_manufacturer(alias)
                        adapter.info("Manufacturer detected from last pages (alias '%s'): %s", alias, normalized)
                        return normalized

        return None

    def _extract_potential_models(self, file_path: Path, context: ProcessingContext) -> list[str]:
        """
        Extract potential model numbers from filename and context for web verification.

        Args:
            file_path: Path to the document
            context: Processing context with page_texts

        Returns:
            List of potential model numbers (max 3 to avoid excessive API calls)
        """
        models = []

        # Extract from filename (e.g., HP_E475_SM.pdf → E475)
        filename_stem = file_path.stem
        # Use regex to find model-like patterns (alphanumeric, 3-10 chars)
        pattern = r"\b([A-Z0-9]{3,10})\b"
        matches = re.findall(pattern, filename_stem.upper())
        models.extend(matches)

        # Extract from first page if available
        if hasattr(context, "page_texts") and context.page_texts:
            first_page = context.page_texts.get(1, "")
            if first_page:
                # Search first 500 chars for model numbers
                matches = re.findall(pattern, first_page[:500])
                models.extend(matches)

        # Remove duplicates and common false positives
        models = list(dict.fromkeys(models))  # Preserve order while removing duplicates
        # Filter out common document-related terms
        false_positives = {"PDF", "SM", "CPMD", "FW", "REV", "DOC", "MANUAL", "SERVICE", "PARTS", "LIST"}
        models = [m for m in models if m not in false_positives]

        return models[:3]  # Limit to 3 models to avoid excessive API calls

    async def _ai_detect_manufacturer(self, content: str) -> str | None:
        """Use AI to detect manufacturer from content"""
        if not self.ai_service or not content:
            return None

        try:
            prompt = f"""Analyze this technical document excerpt and identify the manufacturer.
Look for brand names, model numbers, and company references.

Content:
{content[:1000]}

Respond with ONLY the manufacturer name (e.g., "HP", "Canon", "Konica Minolta").
If uncertain, respond with "Unknown"."""

            response = await self.ai_service.generate(prompt, max_tokens=50)

            if response and response.strip():
                manufacturer = response.strip()
                # Normalize the response
                normalized = normalize_manufacturer(manufacturer)
                if normalized and normalized != "Unknown":
                    return normalized
        except Exception as e:
            self.logger.warning(f"AI manufacturer detection error: {e}")

        return None

    def _parse_manufacturer_from_filename(self, file_path: Path) -> str | None:
        """
        Parse manufacturer from structured filename patterns

        Extracts manufacturer prefix from filenames like:
        - HP_E475_SM.pdf -> HP
        - KM_C759_C659_SM.pdf -> KM (Konica Minolta)
        - CANON_iR_ADV_C5550i.pdf -> CANON

        Args:
            file_path: Path object for the file

        Returns:
            Normalized manufacturer name or None
        """
        # Manufacturer prefix mapping
        prefix_patterns = [
            "HP_",
            "KM_",
            "CANON_",
            "RICOH_",
            "XEROX_",
            "BROTHER_",
            "LEXMARK_",
            "SHARP_",
            "EPSON_",
            "KYOCERA_",
            "FUJIFILM_",
            "FUJI_",
            "RISO_",
            "TOSHIBA_",
            "OKI_",
            "UTAX_",
        ]

        # Get filename stem (without extension)
        filename_stem = file_path.stem.upper()

        # Check if filename starts with known prefix
        for prefix_pattern in prefix_patterns:
            if filename_stem.startswith(prefix_pattern):
                # Extract prefix (remove trailing underscore)
                prefix = prefix_pattern.rstrip("_")
                # Normalize using manufacturer normalizer
                normalized = normalize_manufacturer_prefix(prefix)
                if normalized:
                    return normalized

        # Lexmark machine-type filenames often look like 7566-69x_sm.pdf.
        if re.match(r"^\d{4}-\d{2}[A-Z](?:_|-|$)", filename_stem):
            return normalize_manufacturer("Lexmark")

        return None

    async def _detect_document_type(
        self, file_path: Path, doc_metadata: dict[str, Any], manufacturer: str, context, adapter
    ) -> tuple[str, str]:
        """Detect document type and version"""

        # Get content statistics
        content_stats = await self._get_content_statistics(context.document_id)

        # Use document type detector
        pdf_metadata = {
            "title": doc_metadata.get("title", ""),
            "filename": file_path.name,
            "creation_date": doc_metadata.get("created_at", ""),
        }

        document_type, version = self.type_detector.detect(
            pdf_metadata=pdf_metadata, content_stats=content_stats, manufacturer=manufacturer
        )

        adapter.info("Document type detected: %s", document_type)

        return document_type, version

    async def _get_content_statistics(self, document_id: str) -> dict[str, Any]:
        """Get content statistics for document via DatabaseAdapter."""
        stats = {"total_error_codes": 0, "parts_count": 0}

        if not self.database_service:
            self.logger.warning("Cannot get content statistics: no database_service available")
            return stats

        try:
            intel_schema = getattr(self.database_service, "_intelligence_schema", "krai_intelligence")

            # Use direct fetch_one if available
            if hasattr(self.database_service, "fetch_one"):
                ec_row = await self.database_service.fetch_one(
                    f"SELECT COUNT(*) as c FROM {intel_schema}.error_codes WHERE document_id = $1", [document_id]
                )
                stats["total_error_codes"] = int(ec_row["c"]) if ec_row else 0

                parts_row = await self.database_service.fetch_one(
                    """
                    SELECT COUNT(DISTINCT pc.id) AS c
                    FROM krai_core.document_products dp
                    JOIN krai_parts.parts_catalog pc ON pc.product_id = dp.product_id
                    WHERE dp.document_id = $1
                    """,
                    [document_id],
                )
                stats["parts_count"] = int(parts_row["c"]) if parts_row else 0
            else:
                self.logger.warning("Content statistics fallback: adapter does not support fetch_one")
        except Exception as e:
            self.logger.warning("Could not get content statistics: %s", e)

        return stats

    async def _get_document_chunks(self, document_id: str, limit: int = 5) -> list:
        """Get first N chunks of document"""
        if not self.database_service:
            return []

        try:
            if hasattr(self.database_service, "fetch_all"):
                result = await self.database_service.fetch_all(
                    "SELECT text_chunk as content FROM krai_intelligence.chunks WHERE document_id = $1 ORDER BY chunk_index LIMIT $2",
                    [document_id, limit],
                )
                return result or []

            client = getattr(self.database_service, "client", None)
            if client is not None:
                result = (
                    client.table("chunks")
                    .select("text_chunk")
                    .eq("document_id", document_id)
                    .order("chunk_index")
                    .limit(limit)
                    .execute()
                )
                return [{"content": row.get("text_chunk") or row.get("content", "")} for row in (result.data or [])]

            return []
        except Exception as e:
            self.logger.warning(f"Could not get chunks: {e}")
            return []

    async def _update_document_classification(
        self,
        document_id: str,
        manufacturer: str,
        manufacturer_id: str | None,
        document_type: str,
        version: str,
        model_candidates: list[Any] | None = None,
    ):
        """Update document with classification results"""
        try:
            update_data = {
                "manufacturer": manufacturer,
                "manufacturer_id": manufacturer_id,
                "document_type": document_type,
                "version": version,
            }
            if model_candidates:
                update_data["models"] = model_candidates

            if hasattr(self.database_service, "update_document"):
                await self.database_service.update_document(document_id, update_data)

            self.logger.info("Updated document classification in database")
        except Exception as e:
            self.logger.error(f"Failed to update document classification: {e}")

    async def _resolve_manufacturer_id(self, manufacturer: str) -> str | None:
        """Resolve manufacturer name to manufacturers.id."""
        if not manufacturer or manufacturer == "Unknown" or not self.database_service:
            return None

        try:
            canonical = normalize_manufacturer(manufacturer) or manufacturer
            if canonical in KNOWN_MANUFACTURER_UUIDS:
                return KNOWN_MANUFACTURER_UUIDS[canonical]
            if manufacturer.strip().lower() in {"hp inc", "hp inc.", "hp", "hewlett-packard", "hewlett packard"}:
                return KNOWN_MANUFACTURER_UUIDS["HP Inc."]

            if hasattr(self.database_service, "fetch_one"):
                row = await self.database_service.fetch_one(
                    """
                    SELECT id
                    FROM krai_core.manufacturers
                    WHERE LOWER(name) = LOWER($1)
                       OR LOWER(short_name) = LOWER($1)
                       OR LOWER(name) LIKE LOWER($2)
                    ORDER BY
                        CASE
                            WHEN LOWER(name) = LOWER($1) THEN 0
                            WHEN LOWER(short_name) = LOWER($1) THEN 1
                            ELSE 2
                        END
                    LIMIT 1
                    """,
                    [manufacturer, f"%{manufacturer}%"],
                )
                if row:
                    return str(row["id"])

                # Auto-create missing manufacturer entries (e.g., Lexmark) to unblock downstream stages.
                short_name = re.sub(r"[^A-Z]", "", manufacturer.upper())[:8] or manufacturer[:8].upper()
                created = await self.database_service.fetch_one(
                    """
                    INSERT INTO krai_core.manufacturers (name, short_name)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    [manufacturer, short_name],
                )
                if created:
                    self.logger.info("Created missing manufacturer '%s' (%s)", manufacturer, short_name)
                    return str(created["id"])
        except Exception as e:
            self.logger.warning("Could not resolve manufacturer_id for '%s': %s", manufacturer, e)
        return None

    def _extract_model_candidates_for_linking(self, file_path: Path, context) -> list:
        """Extract strict model tokens suitable for product linking."""
        candidates = []
        model_pattern = re.compile(r"^(?:[A-Z]{1,3}-)?[A-Z]{0,2}\d{3,5}[A-Z]{0,4}$")

        for token in re.split(r"[^A-Z0-9-]+", file_path.stem.upper()):
            token = token.strip()
            if token and model_pattern.match(token):
                candidates.append(token)

        if hasattr(context, "page_texts") and context.page_texts:
            # Include first pages where model families are commonly listed.
            for page_no in (1, 2, 3):
                page_text = context.page_texts.get(page_no, "") or ""
                if not page_text:
                    continue
                for token in re.split(r"[^A-Z0-9-]+", page_text[:2000].upper()):
                    token = token.strip()
                    if token and model_pattern.match(token):
                        candidates.append(token)

        reject = {"PDF", "SM", "CPMD", "FW", "DOC", "MANUAL", "SERVICE", "LIST", "PAGE"}
        normalized = []
        for token in candidates:
            token = token.strip("_- ")
            if token in reject:
                continue
            # Ignore pure numeric tokens (years, counters) for product linking.
            if not re.search(r"[A-Z]", token):
                continue
            if token and token not in normalized:
                normalized.append(token)
        # Keep enough filename models for multi-model manuals (e.g. C658_C558_C458_C368_C308_C258).
        return normalized[:12]

    async def _link_document_products(
        self,
        document_id: str,
        manufacturer_id: str | None,
        model_candidates: list[Any],
        adapter,
    ) -> int:
        """Upsert products and link them to the current document."""
        if not manufacturer_id:
            adapter.warning("Skipping document_products linking: no manufacturer_id")
            return 0
        if not model_candidates:
            adapter.info("No model candidates found for product linking")
            return 0
        if not hasattr(self.database_service, "fetch_one") or not hasattr(self.database_service, "execute_query"):
            adapter.warning("Skipping product linking: adapter does not support SQL operations")
            return 0

        linked = 0
        for model in model_candidates:
            try:
                product = await self.database_service.fetch_one(
                    """
                    SELECT id
                    FROM krai_core.products
                    WHERE manufacturer_id = $1::uuid
                      AND LOWER(model_number) = LOWER($2)
                    LIMIT 1
                    """,
                    [manufacturer_id, model],
                )

                if product:
                    product_id = str(product["id"])
                else:
                    created = await self.database_service.fetch_one(
                        """
                        INSERT INTO krai_core.products (manufacturer_id, model_number, product_type)
                        VALUES ($1::uuid, $2, $3)
                        RETURNING id
                        """,
                        [manufacturer_id, model, "printer"],
                    )
                    product_id = str(created["id"])

                link_exists = await self.database_service.fetch_one(
                    """
                    SELECT id
                    FROM krai_core.document_products
                    WHERE document_id = $1::uuid AND product_id = $2::uuid
                    LIMIT 1
                    """,
                    [document_id, product_id],
                )
                if link_exists:
                    continue

                await self.database_service.execute_query(
                    """
                    INSERT INTO krai_core.document_products (document_id, product_id)
                    VALUES ($1::uuid, $2::uuid)
                    """,
                    [document_id, product_id],
                )
                linked += 1
            except Exception as e:
                adapter.warning("Failed to link model '%s': %s", model, e)

        if linked:
            adapter.info("Linked %s products to document", linked)
        return linked

    def _create_result(self, success: bool, message: str, data: dict[str, Any]) -> ProcessingResult:
        """Create a BaseProcessor-compatible result payload."""
        if success:
            return self.create_success_result(data=data, metadata={"message": message})

        from backend.core.base_processor import ProcessingError

        error = ProcessingError(message, self.name, "CLASSIFICATION_ERROR")
        return self.create_error_result(error=error, metadata={})
