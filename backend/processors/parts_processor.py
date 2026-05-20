"""Parts Processor

Extracts part numbers and descriptions from document chunks.
Stage 6 in the processing pipeline.
"""

import re
import sys

from backend.core.base_processor import BaseProcessor, Stage
from backend.core.types import ProcessingError

from .imports import extract_parts_with_context, get_database_adapter
from .stage_tracker import StageTracker


class PartsProcessor(BaseProcessor):
    """Extract and store parts from document chunks"""

    def __init__(self, database_adapter=None, stage_tracker: StageTracker | None = None):
        """Initialize parts processor"""
        super().__init__(name="parts_processor")
        self.stage = Stage.PARTS_EXTRACTION
        self.adapter = database_adapter or get_database_adapter()
        # Expose adapter under BaseProcessor-expected attribute names.
        self.db_adapter = self.adapter
        self.database_service = self.adapter
        self.stage_tracker = None  # Temporarily disabled due to Supabase dependency
        self.logger.info("PartsProcessor initialized")

    @staticmethod
    def _read_field(obj, key: str, default=None):
        """Read field from dict-like or attribute-based model objects."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    async def process_document(self, document_id: str) -> dict:
        """
        Process all chunks of a document to extract parts

        Args:
            document_id: UUID of document to process

        Returns:
            Dict with statistics
        """
        stats = {
            "chunks_processed": 0,
            "parts_found": 0,
            "parts_created": 0,
            "parts_updated": 0,
            "parts_linked_to_error_codes": 0,
            "errors": 0,
            "skipped_reason": None,
        }

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            if self.stage_tracker:
                await self.stage_tracker.start_stage(document_id, self.stage)

            try:
                document = await self.adapter.get_document(document_id)
                if not document:
                    adapter.error("Document %s not found", document_id)
                    stats["errors"] += 1
                    if self.stage_tracker:
                        await self.stage_tracker.fail_stage(document_id, self.stage, error="Document not found")
                    return stats

                manufacturer_id = self._read_field(document, "manufacturer_id")
                manufacturer_name = (self._read_field(document, "manufacturer", "") or "").lower().replace(" ", "_")

                if not manufacturer_id:
                    manufacturer_id, manufacturer_name = await self._resolve_document_manufacturer(
                        document_id, manufacturer_name
                    )

                if not manufacturer_id:
                    adapter.warning("No manufacturer_id available, skipping parts extraction")
                    stats["skipped_reason"] = "Missing manufacturer_id"
                    if self.stage_tracker:
                        await self.stage_tracker.skip_stage(document_id, self.stage, reason="Missing manufacturer_id")
                    return stats

                linked_product_ids = await self._get_document_product_ids(document_id)
                if not linked_product_ids:
                    adapter.warning(
                        "No document_products links available; parts extraction will continue with manufacturer context only. "
                        "This may result in lower quality part-product associations."
                    )
                    stats["skipped_reason"] = "No linked products (continuing with manufacturer-only context)"
                primary_product_id = linked_product_ids[0] if linked_product_ids else None

                adapter.info("Extracting parts for manufacturer: %s", manufacturer_name)

                chunks = await self.adapter.get_chunks_by_document(document_id)
                adapter.info("Processing %s chunks for parts extraction", len(chunks))

                for chunk in chunks:
                    stats["chunks_processed"] += 1

                    try:
                        parts_found = self._extract_parts_from_chunk(
                            chunk=chunk,
                            manufacturer_id=manufacturer_id,
                            manufacturer_key=manufacturer_name,
                            document_id=document_id,
                            product_id=primary_product_id,
                        )

                        stats["parts_found"] += len(parts_found)

                        for part_data in parts_found:
                            result = await self._store_part(part_data, adapter)
                            if result == "created":
                                stats["parts_created"] += 1
                            elif result == "updated":
                                stats["parts_updated"] += 1

                    except Exception:
                        chunk_id = chunk.get("id") if isinstance(chunk, dict) else None
                        adapter.exception("Error processing chunk %s", chunk_id)
                        stats["errors"] += 1

                adapter.info("Linking parts to error codes...")
                linked_count = await self._link_parts_to_error_codes(document_id, adapter)
                stats["parts_linked_to_error_codes"] = linked_count

                adapter.info("Parts extraction complete: %s", stats)

                if self.stage_tracker:
                    metadata = {
                        "parts_found": stats["parts_found"],
                        "parts_created": stats["parts_created"],
                        "parts_updated": stats["parts_updated"],
                        "chunks_processed": stats["chunks_processed"],
                        "linked_products": len(linked_product_ids),
                    }
                    if not linked_product_ids:
                        metadata["warning"] = "No products linked - parts extracted with manufacturer context only"
                    await self.stage_tracker.complete_stage(document_id, self.stage, metadata=metadata)

                return stats

            except Exception as e:
                adapter.error("Error in parts processing: %s", e)
                stats["errors"] += 1
                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(document_id, self.stage, error=str(e))
                return stats

    async def process(self, context) -> dict:
        """Async wrapper to support BaseProcessor interface."""
        document_id = getattr(context, "document_id", None)
        if not document_id:
            raise ValueError("Processing context must include 'document_id'")

        stats = await self.process_document(str(document_id))
        skipped_reason = stats.get("skipped_reason")
        if skipped_reason == "Missing manufacturer_id":
            return self.create_error_result(
                error=ProcessingError(
                    message=f"Parts extraction skipped: {skipped_reason}",
                    processor=self.name,
                    error_code="PARTS_PRECONDITION_FAILED",
                ),
                data=stats,
                metadata={
                    "document_id": str(document_id),
                    "stage": self.stage.value,
                    "skipped_reason": skipped_reason,
                },
            )
        metadata = {
            "document_id": str(document_id),
            "stage": self.stage.value,
            "parts_found": stats.get("parts_found", 0),
        }
        return self.create_success_result(stats, metadata=metadata)

    def _extract_parts_from_chunk(
        self,
        chunk: dict,
        manufacturer_id: str,
        manufacturer_key: str,
        document_id: str,
        product_id: str | None = None,
    ) -> list[dict]:
        """
        Extract parts with context from a chunk

        Args:
            chunk: Chunk data
            manufacturer_id: Manufacturer UUID
            manufacturer_key: Manufacturer key for patterns (e.g., 'hp', 'konica_minolta')
            document_id: Document UUID

        Returns:
            List of part data dicts
        """
        # Normalize chunk text across different sources:
        # - content chunks use 'content'
        # - intelligence chunks use 'text_chunk'
        # - some in-memory flows may still provide 'text'
        text = chunk.get("text") or chunk.get("content") or chunk.get("text_chunk") or ""
        if not text:
            return []

        # Extract parts with context using manufacturer-specific patterns
        parts_with_ctx = extract_parts_with_context(text, manufacturer_key=manufacturer_key, max_parts=100)

        parts_data = []
        for item in parts_with_ctx:
            part_number = item["part"]
            context = item["context"]

            if not self._is_plausible_part_number(part_number):
                continue

            # Extract description and category from context
            description, category = self._extract_description_and_category(context, part_number)
            part_name = self._extract_part_name(context, part_number)

            if not self._is_high_quality_part_context(part_name, description):
                continue

            parts_data.append(
                {
                    "part_number": part_number,
                    "manufacturer_id": manufacturer_id,
                    "product_id": product_id,
                    "part_name": part_name,
                    "part_description": description,
                    "part_category": category,
                    "document_id": document_id,
                    "chunk_id": chunk["id"],
                    "context": context,
                }
            )

        return parts_data

    def _is_plausible_part_number(self, part_number: str) -> bool:
        """Reject obvious non-part artifacts like headings or repeated digits."""
        token = (part_number or "").strip()
        if not token:
            return False
        if token.isalpha():
            return False
        return not (token.isdigit() and len(set(token)) == 1)

    def _is_high_quality_part_context(self, part_name: str | None, description: str | None) -> bool:
        """Reject weak/noisy matches that are unlikely to be real spare parts."""
        name = (part_name or "").strip()
        desc = (description or "").strip()
        if name:
            return True
        if len(desc) < 25:
            return False

        lower_desc = desc.lower()
        noise_markers = [
            "bundle zip",
            "settings bundle",
            "import configuration",
            "downloads.lexmark.com",
            "/downloads/firmware/",
            "firmware version",
            "embedded web server",
        ]
        return not any(marker in lower_desc for marker in noise_markers)

    @staticmethod
    def _text_quality_score(value: str | None) -> int:
        """Heuristic quality score for extracted name/description."""
        text = (value or "").strip()
        if not text:
            return 0
        score = 1
        lower = text.lower()
        if text and text[0].isupper():
            score += 2
        if len(text) <= 80:
            score += 1
        if any(k in lower for k in ["drum", "toner", "unit", "cartridge", "kit"]):
            score += 2
        if any(k in lower for k in ["parts name", "number of field standard", "target model"]):
            score -= 2
        if any(k in lower for k in ["bundle zip", "import configuration", "downloads."]):
            score -= 3
        if text and text[0].islower():
            score -= 2
        return score

    async def _get_document_product_ids(self, document_id: str) -> list[str]:
        """Return all linked product IDs for the document."""
        try:
            if hasattr(self.adapter, "fetch_all"):
                rows = await self.adapter.fetch_all(
                    """
                    SELECT product_id
                    FROM krai_core.document_products
                    WHERE document_id = $1::uuid
                    """,
                    [document_id],
                )
                product_ids: list[str] = []
                for row in rows or []:
                    row_dict = dict(row) if not isinstance(row, dict) else row
                    product_id = row_dict.get("product_id")
                    if product_id:
                        product_ids.append(str(product_id))
                return product_ids
        except Exception as e:
            self.logger.warning("Could not load document_products for %s: %s", document_id, e)
        return []

    async def _resolve_document_manufacturer(self, document_id: str, fallback_name: str) -> tuple[str | None, str]:
        """Load manufacturer_id/name directly from documents table when model object omits fields."""
        try:
            if hasattr(self.adapter, "fetch_one"):
                row = await self.adapter.fetch_one(
                    """
                    SELECT manufacturer_id, manufacturer
                    FROM krai_core.documents
                    WHERE id = $1::uuid
                    LIMIT 1
                    """,
                    [document_id],
                )
                if row:
                    row_dict = dict(row) if not isinstance(row, dict) else row
                    manufacturer_id = row_dict.get("manufacturer_id")
                    manufacturer_name = (row_dict.get("manufacturer") or fallback_name or "").lower().replace(" ", "_")
                    return (str(manufacturer_id) if manufacturer_id else None), manufacturer_name
        except Exception as e:
            self.logger.warning("Could not resolve manufacturer for %s: %s", document_id, e)
        return None, fallback_name

    def _extract_part_name(self, context: str, part_number: str) -> str | None:
        """
        Extract short part name from context.

        Prefers table-like row descriptions first because service manuals
        often list part number + quantities + description in one row.
        """
        row_description = self._extract_table_row_description(context, part_number)
        if row_description:
            return row_description[:100]

        patterns = [
            r"(?:replace|install|use|order)\s+(?:the\s+)?([a-z\s]{5,40}?)\s*[-:]\s*" + re.escape(part_number),
            r"([A-Z][a-z\s]{5,40}?)\s*[-:]\s*" + re.escape(part_number),
            r"(?:part|component|assembly)\s*[:]\s*([a-z\s]{5,40}?)\s*[-:]?\s*" + re.escape(part_number),
        ]

        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if not match:
                continue
            name = re.sub(r"\s+", " ", match.group(1).strip())
            return name[:100]

        return None

    def _extract_table_row_description(self, context: str, part_number: str) -> str | None:
        """Extract compact description from table-like row around the part number."""
        if not context:
            return None

        def _clean_desc(text: str) -> str | None:
            desc = re.sub(r"\s+", " ", text).strip(" -:;,")
            desc = re.sub(r"^.*?part\s+number\s+", "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"^.*\b[A-Z0-9]{2,}-[A-Z0-9]{2,}\b\s+", "", desc, flags=re.IGNORECASE)
            if not desc:
                return None
            if desc.lower() in {"description", "removal procedure"}:
                return None
            return desc

        def _is_noise_line(line: str) -> bool:
            l = line.lower().strip()  # noqa: E741
            if not l:
                return True
            if "bizhub" in l:
                return True
            if re.fullmatch(r"[\d,.\- ]+(sheets|counts|m)?", l):
                return True
            return bool(re.fullmatch("[A-Z0-9]{2,}[-]?[A-Z0-9]{2,}", l))

        # Line-aware extraction is more stable for OCR table text.
        lines = [ln.strip() for ln in context.splitlines() if ln and ln.strip()]
        for idx, line in enumerate(lines):
            if part_number not in line:
                continue

            pos = line.find(part_number)
            if pos > 0:
                inline = _clean_desc(line[:pos])
                if inline and not _is_noise_line(inline):
                    return inline

            for back in range(idx - 1, max(-1, idx - 8), -1):
                candidate = _clean_desc(lines[back])
                if not candidate or _is_noise_line(candidate):
                    continue
                return candidate

        compact = re.sub(r"\s+", " ", context).strip()
        patterns = [
            rf"{re.escape(part_number)}\s+\d+\s+\d+\s+([A-Za-z][A-Za-z0-9()\/,\- ]{{3,120}}?)(?:\s+(?:N/A|See\b|$))",
            rf"{re.escape(part_number)}\s+\d+\s+([A-Za-z][A-Za-z0-9()\/,\- ]{{3,120}}?)(?:\s+(?:N/A|See\b|$))",
            rf"([A-Za-z][A-Za-z0-9()\/,\- ]{{8,120}}?)\s+(?:See\s+NOTE\s+above\.\s+)?{re.escape(part_number)}(?:\s|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if not match:
                continue
            desc = _clean_desc(match.group(1))
            if desc:
                return desc
        return None

    def _extract_description_and_category(self, context: str, part_number: str) -> tuple[str | None, str | None]:
        """
        Extract description and category from context

        Args:
            context: Text around part number
            part_number: The part number

        Returns:
            Tuple of (description, category)
        """
        row_description = self._extract_table_row_description(context, part_number)
        description_source = row_description or context
        context_lower = description_source.lower()

        category = None
        if any(word in context_lower for word in ["toner", "cartridge", "ink", "drum"]):
            category = "consumable"
        elif any(word in context_lower for word in ["assembly", "unit", "module"]):
            category = "assembly"
        elif any(word in context_lower for word in ["sensor", "motor", "switch", "board", "pcb"]):
            category = "component"
        elif any(word in context_lower for word in ["roller", "gear", "belt", "spring"]):
            category = "mechanical"
        elif any(word in context_lower for word in ["cable", "harness", "connector"]):
            category = "electrical"

        description = description_source.strip()
        description = re.sub(r"\s+", " ", description)

        return description[:500], category

    async def _store_part(self, part_data: dict, adapter) -> str:
        """
        Store or update part in database

        Args:
            part_data: Part information

        Returns:
            'created', 'updated', or 'error'
        """
        try:
            existing = await self.adapter.get_part_by_number_and_manufacturer(
                part_data["part_number"], part_data["manufacturer_id"]
            )

            store_data = {
                "part_number": part_data["part_number"],
                "manufacturer_id": part_data["manufacturer_id"],
                "product_id": part_data.get("product_id"),
                "part_name": part_data.get("part_name"),
                "part_description": part_data.get("part_description"),
                "part_category": part_data.get("part_category"),
            }

            if existing:
                part_id = existing["id"]
                old_desc = existing.get("part_description") or ""
                new_desc = store_data.get("part_description") or ""
                old_name = existing.get("part_name") or ""
                new_name = store_data.get("part_name") or ""
                old_product_id = existing.get("product_id")
                new_product_id = store_data.get("product_id")
                old_name_l = old_name.lower()
                old_desc_l = old_desc.lower()
                noisy_old_name = "part number" in old_name_l or old_name_l.startswith("iption")
                noisy_old_desc = "part number" in old_desc_l and "description" in old_desc_l

                should_update = False
                if len(new_desc) > len(old_desc):
                    should_update = True
                if new_name and len(new_name) > len(old_name):
                    should_update = True
                if new_name and noisy_old_name:
                    should_update = True
                if new_desc and noisy_old_desc:
                    should_update = True
                if new_name and (self._text_quality_score(new_name) > self._text_quality_score(old_name)):
                    should_update = True
                if new_desc and (self._text_quality_score(new_desc) > self._text_quality_score(old_desc)):
                    should_update = True
                if new_product_id and not old_product_id:
                    should_update = True

                if should_update:
                    await self.adapter.update_part(part_id, store_data)
                    adapter.debug("Updated part %s", part_data["part_number"])
                    return "updated"
                return "exists"

            await self.adapter.create_part(store_data)
            adapter.debug("Created part %s", part_data["part_number"])
            return "created"

        except Exception as e:
            adapter.error("Error storing part %s: %s", part_data["part_number"], e)
            return "error"

    async def _link_parts_to_error_codes(self, document_id: str, adapter) -> int:
        """
        Link parts to error codes based on chunk proximity and solution text

        Args:
            document_id: Document UUID

        Returns:
            Number of links created
        """
        linked_count = 0

        try:
            if not hasattr(self.adapter, "get_error_codes_by_document"):
                adapter.debug("Skipping error-code linking: adapter method get_error_codes_by_document not available")
                return 0

            # Get all error codes for this document
            error_codes = await self.adapter.get_error_codes_by_document(document_id)

            for error_code in error_codes:
                ec_id = error_code["id"]
                solution_text = error_code.get("solution_text", "")
                chunk_id = error_code.get("chunk_id")

                # Extract parts from solution text
                if solution_text:
                    parts_in_solution = await self._extract_and_link_parts_from_text(
                        text=solution_text,
                        error_code_id=ec_id,
                        source="solution_text",
                        adapter=adapter,
                    )
                    linked_count += parts_in_solution

                # Also check the chunk where error code was found
                if chunk_id:
                    if not hasattr(self.adapter, "get_chunk"):
                        continue
                    chunk = await self.adapter.get_chunk(chunk_id)
                    if chunk:
                        chunk_text = chunk.get("text") or chunk.get("content") or chunk.get("text_chunk") or ""
                        parts_in_chunk = await self._extract_and_link_parts_from_text(
                            text=chunk_text,
                            error_code_id=ec_id,
                            source="chunk",
                            adapter=adapter,
                        )
                        linked_count += parts_in_chunk

            adapter.info("Linked %s parts to error codes", linked_count)
            return linked_count

        except Exception as e:
            adapter.error("Error linking parts to error codes: %s", e)
            return linked_count

    async def _extract_and_link_parts_from_text(self, text: str, error_code_id: str, source: str, adapter) -> int:
        """
        Extract parts from text and link to error code

        Args:
            text: Text to extract from
            error_code_id: Error code UUID
            source: Where the text came from

        Returns:
            Number of parts linked
        """
        linked_count = 0

        try:
            # Extract parts
            parts_found = extract_parts_with_context(text, max_parts=10)

            for part_item in parts_found:
                part_number = part_item["part"]
                confidence = part_item.get("confidence", 0.8)

                # Find part in database
                part = await self.adapter.get_part_by_number(part_number)

                if not part:
                    continue

                part_id = part["id"]

                # Create link (ignore if already exists)
                try:
                    await self.adapter.create_error_code_part_link(
                        {
                            "error_code_id": error_code_id,
                            "part_id": part_id,
                            "relevance_score": confidence,
                            "extraction_source": source,
                        }
                    )

                    linked_count += 1
                    adapter.debug("Linked part %s to error code %s", part_number, error_code_id)

                except Exception:
                    # Link probably already exists, ignore
                    pass

            return linked_count

        except Exception as e:
            adapter.error("Error extracting and linking parts: %s", e)
            return linked_count


import asyncio


def main():
    """Test parts processor"""

    if len(sys.argv) < 2:
        print("Usage: python parts_processor.py <document_id>")
        sys.exit(1)

    document_id = sys.argv[1]

    async def run():
        processor = PartsProcessor()
        stats = await processor.process_document(document_id)

        print("\nParts Processing Complete!")
        print(f"Chunks processed: {stats['chunks_processed']}")
        print(f"Parts found: {stats['parts_found']}")
        print(f"Parts created: {stats['parts_created']}")
        print(f"Parts updated: {stats['parts_updated']}")
        print(f"Errors: {stats['errors']}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
