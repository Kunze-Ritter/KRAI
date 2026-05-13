"""
Smart Text Chunking Module

Splits text into chunks with overlap, preserving context.
Respects paragraph boundaries and error code sections.
"""

import hashlib
import os
import re
from typing import Any
from uuid import UUID

from .logger import get_logger
from .models import TextChunk

logger = get_logger()


class SmartChunker:
    """Intelligent text chunking with context preservation"""

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap_size: int = 100,
        min_chunk_size: int = 30,
        enable_header_cleanup: bool = True,
        enable_hierarchical_chunking: bool = True,
        detect_error_code_sections: bool = True,
        link_chunks: bool = True,
    ):
        """
        Initialize chunker

        Args:
            chunk_size: Target chunk size in characters (default: 1000)
            overlap_size: Overlap between chunks (default: 100)
            min_chunk_size: Minimum chunk size after header cleaning (default: 30)
                           Reduced from 50 to preserve short but valuable content
                           like error codes, part numbers, or brief instructions
            enable_header_cleanup: Enable header detection and cleanup (default: True)
            enable_hierarchical_chunking: Enable hierarchy detection (default: True)
            detect_error_code_sections: Detect error code boundaries (default: True)
            link_chunks: Link chunks with previous/next IDs (default: True)
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
        self.enable_header_cleanup = enable_header_cleanup
        self.enable_hierarchical_chunking = enable_hierarchical_chunking
        self.detect_error_code_sections = detect_error_code_sections
        self.link_chunks = link_chunks
        self.logger = get_logger()

    def chunk_document(self, page_texts: dict[int, str], document_id: UUID) -> list[TextChunk]:
        """
        Chunk entire document with page-aware splitting

        Args:
            page_texts: Dictionary {page_number: text}
            document_id: Document UUID

        Returns:
            List of TextChunk objects
        """
        all_chunks = []
        chunk_index = 0

        # Detect document structure if hierarchical chunking is enabled
        structure = None
        if self.enable_hierarchical_chunking:
            structure = self._detect_document_structure(page_texts)
            self.logger.info(
                f"Hierarchical structure: {len(structure.get('sections', []))} sections, {len(structure.get('error_code_sections', []))} error code sections"
            )

        # Process pages in order
        sorted_pages = sorted(page_texts.keys())

        for page_num in sorted_pages:
            text = page_texts[page_num]

            if not text or len(text.strip()) < self.min_chunk_size:
                continue

            # Chunk this page with structure information
            page_chunks = self._chunk_text(
                text=text,
                page_start=page_num,
                page_end=page_num,
                document_id=document_id,
                start_index=chunk_index,
                structure=structure,
            )

            all_chunks.extend(page_chunks)
            chunk_index += len(page_chunks)

        # Link chunks if enabled
        if self.link_chunks and all_chunks:
            all_chunks = self._link_chunks(all_chunks)
            self.logger.info(f"Linked {len(all_chunks)} chunks with previous/next references")

        # Summary statistics
        chunk_types = {}
        chunks_with_headers = 0
        for chunk in all_chunks:
            chunk_type = chunk.metadata.get("chunk_type", "unknown")
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            if chunk.metadata.get("page_header"):
                chunks_with_headers += 1

        self.logger.success(f"✅ Created {len(all_chunks)} chunks from {len(sorted_pages)} pages")
        if chunk_types:
            types_str = ", ".join([f"{k}: {v}" for k, v in sorted(chunk_types.items())])
            self.logger.info(f"   Types: {types_str}")
        if chunks_with_headers > 0:
            self.logger.info(f"   Headers preserved: {chunks_with_headers}/{len(all_chunks)} chunks")

        return all_chunks

    def _chunk_text(
        self,
        text: str,
        page_start: int,
        page_end: int,
        document_id: UUID,
        start_index: int = 0,
        structure: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """
        Chunk single text with overlap

        Args:
            text: Text to chunk
            page_start: Starting page number
            page_end: Ending page number
            document_id: Document UUID
            start_index: Starting chunk index
            structure: Document structure from _detect_document_structure()

        Returns:
            List of TextChunk objects
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []

        chunks = []

        # Split into paragraphs first
        paragraphs = self._split_into_paragraphs(text)

        current_chunk = ""
        chunk_index = start_index

        for para in paragraphs:
            # Check if adding paragraph exceeds chunk size
            potential_size = len(current_chunk) + len(para)

            if potential_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_obj = self._create_chunk(
                    text=current_chunk,
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    document_id=document_id,
                    structure=structure,
                )
                if chunk_obj:
                    chunks.append(chunk_obj)
                    chunk_index += 1

                # Start new chunk with overlap
                current_chunk = self._get_overlap(current_chunk) + "\n\n" + para
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Add final chunk
        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunk_obj = self._create_chunk(
                text=current_chunk,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                document_id=document_id,
                structure=structure,
            )
            if chunk_obj:
                chunks.append(chunk_obj)

        return chunks

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """
        Split text into paragraphs

        Args:
            text: Text to split

        Returns:
            List of paragraphs
        """
        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r"\n\s*\n", text)

        # Clean and filter
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Force-split paragraphs that are too large (e.g. table of contents)
        max_paragraph_size = self.chunk_size * 2  # 2x chunk_size max
        split_paragraphs = []

        for para in paragraphs:
            if len(para) > max_paragraph_size:
                # Split by single newlines instead
                lines = para.split("\n")
                current = ""
                for line in lines:
                    if len(current) + len(line) > max_paragraph_size:
                        if current:
                            split_paragraphs.append(current)
                        current = line
                    else:
                        current = current + "\n" + line if current else line
                if current:
                    split_paragraphs.append(current)
            else:
                split_paragraphs.append(para)

        # Merge very short paragraphs with next one
        merged = []
        buffer = ""

        for para in split_paragraphs:
            if len(buffer) > 0 and len(buffer) < 100:
                # Merge with buffer
                buffer = buffer + "\n\n" + para
            else:
                if buffer:
                    merged.append(buffer)
                buffer = para

        if buffer:
            merged.append(buffer)

        return merged

    def _get_overlap(self, text: str) -> str:
        """
        Get overlap text from end of chunk

        Args:
            text: Full chunk text

        Returns:
            Overlap text
        """
        if len(text) <= self.overlap_size:
            return text

        # Take last N characters
        overlap = text[-self.overlap_size :]

        # Try to start at sentence boundary
        sentence_start = overlap.find(". ")
        if sentence_start > 0:
            overlap = overlap[sentence_start + 2 :]

        return overlap.strip()

    def _create_chunk(
        self,
        text: str,
        chunk_index: int,
        page_start: int,
        page_end: int,
        document_id: UUID,
        structure: dict[str, Any] | None = None,
    ) -> TextChunk:
        """
        Create TextChunk object with metadata

        Args:
            text: Chunk text
            chunk_index: Chunk index
            page_start: Starting page
            page_end: Ending page
            document_id: Document UUID
            structure: Document structure from _detect_document_structure()

        Returns:
            TextChunk object or None if invalid
        """
        original_text = text
        text = text.strip()

        allow_short_chunks = os.getenv("DEBUG_ALLOW_SHORT_CHUNKS", "false").lower() == "true"
        effective_min_size = 0 if allow_short_chunks else self.min_chunk_size

        # Validate minimum size
        if len(text) < effective_min_size:
            return None

        # Clean headers and extract metadata
        cleaned_text, header_metadata = self._clean_headers(
            text,
            perform_cleanup=self.enable_header_cleanup,
        )

        # Validate minimum size AFTER cleaning (headers might have been removed)
        if len(cleaned_text.strip()) < effective_min_size:
            self.logger.debug(
                f"⏭️  Skipped chunk (too short after header cleaning): {len(cleaned_text)} chars (min: {self.min_chunk_size})"
            )
            return None

        # Generate fingerprint
        fingerprint = self._generate_fingerprint(cleaned_text)

        # Detect chunk type
        chunk_type = self._detect_chunk_type(cleaned_text)

        # Create metadata
        metadata = {
            "char_count": len(cleaned_text),
            "word_count": len(cleaned_text.split()),
            "orig_char_count": len(original_text),
            "orig_word_count": len(original_text.split()),
            "has_error_codes": self._contains_error_codes(cleaned_text),
            "chunk_type": chunk_type,
        }

        # Add header metadata if found
        if header_metadata:
            metadata.update(header_metadata)
            self.logger.debug(f"📋 Added header metadata to chunk: {list(header_metadata.keys())}")

        # Add hierarchy metadata if structure is available
        if structure:
            hierarchy_info = self._extract_hierarchy(cleaned_text, structure, page_start)
            if hierarchy_info:
                metadata.update(hierarchy_info)
                self.logger.debug(f"🏗️ Added hierarchy metadata to chunk: {list(hierarchy_info.keys())}")

        try:
            return TextChunk(
                document_id=document_id,
                text=cleaned_text,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                chunk_type=chunk_type,
                metadata=metadata,
                fingerprint=fingerprint,
            )
        except Exception as e:
            self.logger.error(f"Failed to create chunk: {e}")
            return None

    def _clean_headers(
        self,
        text: str,
        perform_cleanup: bool = True,
    ) -> tuple[str, dict[str, object]]:
        """
        Remove repetitive PDF headers and extract as metadata

        Args:
            text: Original chunk text

        Returns:
            Tuple of (cleaned_text, header_metadata)
        """
        header_metadata: dict[str, object] = {}
        cleaned_text = text

        # Common header patterns (first 1-3 lines)
        lines = text.split("\n")
        if len(lines) < 2:
            return text, {}

        header_lines: list[str] = []
        detection_rules: list[str] = []
        content_start_idx = 0

        # Check first few lines for header patterns
        for i, line in enumerate(lines[:5]):  # Check first 5 lines max
            line_clean = line.strip()

            # Stop if we hit actual content (longer lines, paragraphs)
            if i > 0 and len(line_clean) > 80:
                break

            # Detect product model patterns from all major manufacturers
            # Konica Minolta: AccurioPress C4080, bizhub C450i, bizhub PRESS
            # HP: LaserJet M607, OfficeJet Pro 9025, DesignJet T730 (Plotter)
            # Lexmark: CX920, MX910, CS820, MS812, XC9235
            # UTAX: 5006ci, 4006ci, TA5006ci
            # Kyocera: TASKalfa 5053ci, ECOSYS M8130cidn, FS-C5150DN, CS-2552ci
            # Canon: imageRUNNER C5550i, imagePROGRAF PRO-4100 (Plotter)
            # Xerox: VersaLink C7020, AltaLink C8035, WorkCentre 7835
            # Brother: MFC-L8900CDW, HL-L8360CDW, DCP-L8410CDN
            # Fujifilm: ApeosPort-VII C4473, DocuPrint CP505, Apeos C6580, Revoria Press
            # Riso: ComColor GD7330, ORPHIS X9050
            manufacturer_patterns = (
                # Konica Minolta
                r"AccurioPress|AccurioPrint|bizhub PRESS|bizhub|Magicolor"
                # HP - Office & Plotter
                r"|LaserJet|OfficeJet|Color LaserJet|PageWide|DeskJet|ScanJet"
                r"|DesignJet|PageWide XL"  # HP Plotter
                r"|colorlj[A-Z][0-9]+|Color LaserJet [A-Z][0-9]+"  # HP model codes (colorljM455, etc.)
                # Lexmark
                r"|Lexmark\s+[A-Z]{1,2}\d{3,4}|CX\d{3,4}|MX\d{3,4}|CS\d{3,4}|MS\d{3,4}|XC\d{3,4}|MC\d{3,4}"
                # UTAX / Triumph-Adler
                r"|UTAX|Triumph-Adler|TA\s*\d{4}ci"
                # Kyocera - Extended
                r"|TASKalfa|ECOSYS|Kyocera|FS-C\d{4}|FS-\d{4}|CS-\d{4}ci|MA\d{4}|PA\d{4}"
                # Canon - Office & Plotter
                r"|imageRUNNER|imageCLASS|imagePRESS|imageWARE"
                r"|imagePROGRAF|iPF\d{3,4}"  # Canon Plotter
                # Xerox
                r"|VersaLink|AltaLink|WorkCentre|ColorQube|Phaser|PrimeLink"
                # Brother
                r"|MFC-[A-Z]\d{4,5}|HL-[A-Z]\d{4,5}|DCP-[A-Z]\d{4,5}"
                # Fujifilm (Xerox successor in Asia/Japan)
                r"|ApeosPort|Apeos|DocuPrint|DocuCentre|ApeosPort-VII|Apeos C\d{4}|Revoria"
                # Riso (Digital Duplicators & Production Printers)
                r"|ComColor|ORPHIS|Riso|RZ\d{3,4}|SF\d{3,4}"
            )
            rule_trigger: str | None = None

            if re.search(manufacturer_patterns, line_clean, re.IGNORECASE):
                header_lines.append(line_clean)
                content_start_idx = i + 1
                rule_trigger = "manufacturer_pattern"
            elif re.match(r"^[ivxlcdm]+$", line_clean, re.IGNORECASE):
                header_lines.append(line_clean)
                content_start_idx = i + 1
                rule_trigger = "roman_numeral"
            elif i < 3 and re.search(
                r"\b(Document|Manual|Guide|Instruction|Service|Technical|CPMD)\b", line_clean, re.IGNORECASE
            ):
                header_lines.append(line_clean)
                content_start_idx = i + 1
                rule_trigger = "document_keyword"
            elif i < 5 and re.match(r"^(https?://|www\.)", line_clean):
                header_lines.append(line_clean)
                content_start_idx = i + 1
                rule_trigger = "url"
            elif i < 2 and len(line_clean) < 60 and line_clean and not line_clean[0].islower():
                header_lines.append(line_clean)
                content_start_idx = i + 1
                rule_trigger = "short_title"
            else:
                break

            if rule_trigger:
                detection_rules.append(rule_trigger)

        if not header_lines:
            header_metadata["header_removed"] = False
            return cleaned_text, header_metadata

        full_header = "\n".join(header_lines)
        header_metadata["page_header"] = full_header
        header_metadata["header_lines_raw"] = header_lines
        if detection_rules:
            header_metadata["header_detection_rules"] = detection_rules

        products = []
        for line in header_lines:
            products.extend(re.findall(r"[A-Z]\d{4}[a-z]*(?:/[A-Z]\d{4}[a-z]*)*", line))
            products.extend(re.findall(r"colorlj([A-Z]\d+[A-Z]*)", line, re.IGNORECASE))

        if products:
            header_metadata["header_products"] = sorted(set(products))

        if perform_cleanup:
            cleaned_text = "\n".join(lines[content_start_idx:]).strip()
            header_metadata["header_removed"] = True
        else:
            header_metadata["header_removed"] = False

        self.logger.debug(
            f"🎯 Found header: '{full_header[:50]}...' | Products: {products} | Rule triggers: {detection_rules or ['n/a']}"
        )

        return cleaned_text, header_metadata

    def _generate_fingerprint(self, text: str) -> str:
        """
        Generate content fingerprint for deduplication

        Args:
            text: Text to fingerprint

        Returns:
            SHA256 hash (first 32 chars)
        """
        # Normalize text (remove whitespace variations)
        normalized = re.sub(r"\s+", " ", text.lower().strip())

        # Hash
        hash_obj = hashlib.sha256(normalized.encode("utf-8"))
        return hash_obj.hexdigest()[:32]

    def _detect_chunk_type(self, text: str) -> str:
        """
        Detect what type of content this chunk contains

        Returns:
            One of: error_code_section, troubleshooting, procedure, specification, general
        """
        text_lower = text.lower()

        # Error code section
        if re.search(r"\d{2}\.\d{2}\.\d{2}", text) and any(kw in text_lower for kw in ["error", "code", "message"]):
            return "error_code_section"

        # Troubleshooting
        if any(kw in text_lower for kw in ["troubleshoot", "problem", "symptom", "cause", "solution"]):
            return "troubleshooting"

        # Procedure/steps
        if re.search(r"\b\d+\.\s+", text):  # Numbered list
            return "procedure"

        # Specifications
        if any(kw in text_lower for kw in ["specification", "dimension", "weight", "capacity"]):
            return "specification"

        return "general"

    def _contains_error_codes(self, text: str) -> bool:
        """
        Check if text contains error codes

        Args:
            text: Text to check

        Returns:
            True if error codes found
        """
        return bool(re.search(r"\d{2}\.\d{2}(\.\d{2})?", text))

    def deduplicate_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """
        Remove duplicate chunks based on fingerprint

        Args:
            chunks: List of chunks

        Returns:
            Deduplicated list
        """
        seen_fingerprints = set()
        unique_chunks = []
        duplicates = 0

        for chunk in chunks:
            if chunk.fingerprint not in seen_fingerprints:
                seen_fingerprints.add(chunk.fingerprint)
                unique_chunks.append(chunk)
            else:
                duplicates += 1

        if duplicates > 0:
            self.logger.info(f"Removed {duplicates} duplicate chunks")

        return unique_chunks

    def detect_document_structure(self, page_texts: dict[int, str]) -> dict[str, Any]:
        """
        Public API to detect document structure from page texts.

        This method provides a stable public interface that delegates to the internal
        document structure detection logic, maintaining backwards compatibility while
        exposing the functionality for external use.

        Args:
            page_texts: Dictionary mapping page numbers to their text content
                        Format: {page_number: "text content"}

        Returns:
            Dictionary containing:
            - 'sections': List of detected chapters and sections with hierarchy
            - 'error_code_sections': List of error code sections with page ranges

        Example:
            >>> chunker = SmartChunker()
            >>> page_texts = {1: "Chapter 1: Introduction", 2: "1.1 Overview", ...}
            >>> structure = chunker.detect_document_structure(page_texts)
            >>> print(f"Found {len(structure['sections'])} sections")
            >>> print(f"Found {len(structure['error_code_sections'])} error code sections")
        """
        try:
            # Delegate to internal structure detection
            return self._detect_document_structure(page_texts)

        except Exception as e:
            self.logger.error(f"Public document structure detection failed: {e}")
            # Return empty structure on error to maintain API contract
            return {"sections": [], "error_code_sections": []}

    def _detect_document_structure(self, page_texts: dict[int, str]) -> dict[str, Any]:
        """
        Detect document structure (chapters, sections, error code sections)

        Args:
            page_texts: Dictionary {page_number: text}

        Returns:
            Dictionary with sections and error_code_sections
        """
        structure = {"sections": [], "error_code_sections": []}

        # Combine all text for structure detection
        all_text = "\n".join([f"--- PAGE {page_num} ---\n{text}" for page_num, text in sorted(page_texts.items())])

        # Detect chapters
        chapter_pattern = r"Chapter\s+(\d+)[:\s]+(.+)"
        for match in re.finditer(chapter_pattern, all_text, re.IGNORECASE | re.MULTILINE):
            chapter_num = match.group(1)
            chapter_title = match.group(2).strip()
            # Find page number for this chapter
            page_pos = all_text[: match.start()].count("--- PAGE")
            structure["sections"].append(
                {
                    "type": "chapter",
                    "number": chapter_num,
                    "title": chapter_title,
                    "hierarchy": [f"Chapter {chapter_num}: {chapter_title}"],
                    "level": 1,
                    "page_start": page_pos + 1,
                }
            )

        # Detect sections
        section_pattern = r"(\d+\.\d+)[:\s]+(.+)"
        for match in re.finditer(section_pattern, all_text, re.MULTILINE):
            section_num = match.group(1)
            section_title = match.group(2).strip()
            page_pos = all_text[: match.start()].count("--- PAGE")

            # Find parent chapter
            parent_chapter = None
            for section in reversed(structure["sections"]):
                if section["type"] == "chapter" and section["page_start"] <= page_pos + 1:
                    parent_chapter = section
                    break

            hierarchy = []
            if parent_chapter:
                hierarchy.extend(parent_chapter["hierarchy"])
            hierarchy.append(f"{section_num} {section_title}")

            structure["sections"].append(
                {
                    "type": "section",
                    "number": section_num,
                    "title": section_title,
                    "hierarchy": hierarchy,
                    "level": len(hierarchy),
                    "page_start": page_pos + 1,
                }
            )

        # Detect error code sections
        if self.detect_error_code_sections:
            error_code_pattern = r"Error\s+Code\s+(\d{2}\.\d{2}\.\d{2})"
            for match in re.finditer(error_code_pattern, all_text, re.IGNORECASE | re.MULTILINE):
                error_code = match.group(1)
                page_pos = all_text[: match.start()].count("--- PAGE")

                # Find end page for this error code section
                end_page = self._find_error_code_section_end(page_texts, page_pos + 1, error_code)

                # Find parent section
                parent_section = None
                for section in reversed(structure["sections"]):
                    if section["page_start"] <= page_pos + 1:
                        parent_section = section
                        break

                hierarchy = []
                if parent_section:
                    hierarchy.extend(parent_section["hierarchy"])
                hierarchy.append(f"Error Code {error_code}")

                structure["error_code_sections"].append(
                    {"error_code": error_code, "page_start": page_pos + 1, "page_end": end_page, "hierarchy": hierarchy}
                )

        return structure

    def _find_error_code_section_end(self, page_texts: dict[int, str], start_page: int, error_code: str) -> int:
        """
        Find the end page of an error code section

        Args:
            page_texts: Dictionary {page_number: text}
            start_page: Starting page number
            error_code: Current error code

        Returns:
            End page number
        """
        sorted_pages = sorted(page_texts.keys())
        start_idx = sorted_pages.index(start_page) if start_page in sorted_pages else 0

        for i in range(start_idx, len(sorted_pages)):
            page_num = sorted_pages[i]
            text = page_texts[page_num]

            # Check for next error code (different from current)
            next_error_pattern = r"Error\s+Code\s+(\d{2}\.\d{2}\.\d{2})"
            matches = re.findall(next_error_pattern, text, re.IGNORECASE)
            for match in matches:
                if match != error_code:
                    return page_num - 1  # End before this page

            # Check for next major section
            if (
                re.search(r"Chapter\s+\d+|^\d+\.\d+", text, re.MULTILINE | re.IGNORECASE) and i > start_idx
            ):  # Not the first page
                return page_num - 1

        return sorted_pages[-1]  # End of document

    def _extract_hierarchy(self, text: str, structure: dict[str, Any], page_num: int) -> dict[str, Any]:
        """
        Extract hierarchy information for a chunk

        Args:
            text: Chunk text
            structure: Document structure
            page_num: Page number

        Returns:
            Dictionary with hierarchy metadata
        """
        hierarchy_info = {}

        # Find current section
        current_section = None
        for section in reversed(structure["sections"]):
            if section["page_start"] <= page_num:
                current_section = section
                break

        # Check if in error code section
        error_code_section = None
        for error_section in structure["error_code_sections"]:
            if error_section["page_start"] <= page_num <= error_section["page_end"]:
                error_code_section = error_section
                break

        # Add hierarchy information
        if current_section:
            hierarchy_info["section_hierarchy"] = current_section["hierarchy"]
            hierarchy_info["section_title"] = current_section["title"]
            hierarchy_info["section_level"] = current_section["level"]

        if error_code_section:
            hierarchy_info["error_code"] = error_code_section["error_code"]
            hierarchy_info["error_code_section"] = True
            hierarchy_info["section_hierarchy"] = error_code_section["hierarchy"]

        return hierarchy_info

    def _link_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """
        Link chunks with previous/next references

        Args:
            chunks: List of chunks

        Returns:
            List of linked chunks
        """
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.metadata["previous_chunk_id"] = str(chunks[i - 1].chunk_id)
            if i < len(chunks) - 1:
                chunk.metadata["next_chunk_id"] = str(chunks[i + 1].chunk_id)

        return chunks


# Convenience function
def chunk_document_text(
    page_texts: dict[int, str], document_id: UUID, chunk_size: int = 1000, overlap: int = 100
) -> list[TextChunk]:
    """
    Convenience function to chunk document

    Args:
        page_texts: Dictionary {page_number: text}
        document_id: Document UUID
        chunk_size: Target chunk size
        overlap: Overlap size

    Returns:
        List of TextChunk objects
    """
    chunker = SmartChunker(chunk_size=chunk_size, overlap_size=overlap)
    return chunker.chunk_document(page_texts, document_id)
