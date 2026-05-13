"""
Smart Chunking Optimization - Best of both worlds
Fast processing + Intelligent analysis
"""

import gc
import logging
import re
from collections.abc import Generator
from typing import Any

try:
    import fitz
except ImportError:
    fitz = None


class SmartChunkingOptimizer:
    """
    Smart chunking that combines speed with intelligence
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger("krai.chunking.smart")

        # Patterns for intelligent detection
        self.section_patterns = [
            (r"^#+\s+(.+)$", 1),  # Markdown headers
            (r"^\d+\.\s+(.+)$", 1),  # Numbered sections
            (r"^([A-Z][A-Z\s]+)$", 1),  # ALL CAPS headers
            (r"^(Chapter\s+\d+.*)$", 1),  # Chapter headers
            (r"^(Section\s+\d+.*)$", 1),  # Section headers
        ]

        self.chunk_type_patterns = {
            "error_code": [r"Error\s+(\d+)", r"Code\s+(\d+)", r"Err\s+(\d+)"],
            "procedure": [r"Step\s+\d+", r"Procedure\s+\d+", r"Instructions:"],
            "table": [r"Table\s+\d+", r"Figure\s+\d+"],
            "list": [r"^\s*[-*]\s+", r"^\s*\d+\.\s+"],
            "code": [r"```", r"<code>", r"function\s+\w+\("],
        }

    def extract_smart_chunks_streaming(self, file_path: str, document_id: str) -> Generator[dict[str, Any], None, None]:
        """
        Extract chunks with intelligent analysis while maintaining memory efficiency

        Args:
            file_path: Path to PDF file
            document_id: Document ID for chunk metadata

        Yields:
            Smart chunk data with page numbers, section titles, and chunk types
        """
        if fitz is None:
            yield self._create_mock_chunk(document_id, 0, "Mock content", 1, "Mock Section", "text")
            return

        try:
            if fitz is None:
                self.logger.error("PyMuPDF not available - using mock chunks")
                yield self._create_mock_chunk(
                    document_id, 0, "Mock content - PyMuPDF not available", 1, "Mock Section", "text"
                )
                return

            doc = fitz.open(file_path)
            chunk_index = 0
            current_page = 0
            current_section = None

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                current_page = page_num + 1

                # Detect section titles on this page
                page_section = self._detect_section_title(page_text)
                if page_section:
                    current_section = page_section

                # Process page text in chunks
                page_chunks = self._process_page_text(
                    page_text, document_id, chunk_index, current_page, current_section
                )

                for chunk in page_chunks:
                    yield chunk
                    chunk_index += 1

                # Force garbage collection after each page
                del page_text
                gc.collect()

            doc.close()

        except Exception as e:
            self.logger.error(f"Smart chunking failed: {e}")
            # Try to get more specific error info
            if "no such group" in str(e):
                self.logger.error("PyMuPDF installation issue - check fitz installation")
            yield self._create_mock_chunk(
                document_id, 0, f"Error extracting chunks: {str(e)[:100]}", 1, "Error", "text"
            )

    def _process_page_text(
        self, page_text: str, document_id: str, start_chunk_index: int, page_number: int, section_title: str | None
    ) -> list[dict[str, Any]]:
        """Process page text into intelligent chunks"""
        chunks = []
        buffer = ""
        chunk_index = start_chunk_index

        # Split text into sentences for better chunking
        sentences = self._split_into_sentences(page_text)

        for sentence in sentences:
            buffer += sentence + " "

            # Check if we need to create a chunk
            if len(buffer) >= self.chunk_size:
                # Find good break point
                break_point = self._find_smart_break_point(buffer, self.chunk_size)

                chunk_text = buffer[:break_point].strip()
                buffer = buffer[break_point - self.overlap :]

                if chunk_text:
                    chunk_data = self._create_smart_chunk(
                        document_id, chunk_index, chunk_text, page_number, section_title
                    )
                    chunks.append(chunk_data)
                    chunk_index += 1

        # Process remaining buffer
        if buffer.strip():
            chunk_data = self._create_smart_chunk(document_id, chunk_index, buffer.strip(), page_number, section_title)
            chunks.append(chunk_data)

        return chunks

    def _create_smart_chunk(
        self, document_id: str, chunk_index: int, content: str, page_number: int, section_title: str | None
    ) -> dict[str, Any]:
        """Create a smart chunk with intelligent analysis"""

        # Detect chunk type
        chunk_type = self._detect_chunk_type(content)

        # Calculate confidence based on content quality
        confidence_score = self._calculate_confidence(content, chunk_type)

        # Extract additional metadata
        metadata = self._extract_chunk_metadata(content)

        return {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "content": content,
            "chunk_type": chunk_type,
            "page_number": page_number,
            "section_title": section_title,
            "confidence_score": confidence_score,
            "language": "en",
            "metadata": metadata,
        }

    def _detect_section_title(self, page_text: str) -> str | None:
        """Detect section titles from page text"""
        lines = page_text.split("\n")

        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if not line:
                continue

            # Check against patterns
            for pattern, group_num in self.section_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(group_num).strip()

        return None

    def _detect_chunk_type(self, content: str) -> str:
        """Detect the type of chunk based on content patterns"""

        # Check each chunk type pattern
        for chunk_type, patterns in self.chunk_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return chunk_type

        # Default to text if no specific pattern matches
        return "text"

    def _calculate_confidence(self, content: str, chunk_type: str) -> float:
        """Calculate confidence score based on content quality"""
        base_confidence = 0.8

        # Increase confidence for specific chunk types
        if chunk_type in ["error_code", "procedure"]:
            base_confidence += 0.1

        # Increase confidence for longer, more structured content
        if len(content) > 200:
            base_confidence += 0.05

        # Decrease confidence for very short content
        if len(content) < 50:
            base_confidence -= 0.2

        return min(max(base_confidence, 0.0), 1.0)

    def _extract_chunk_metadata(self, content: str) -> dict[str, Any]:
        """Extract additional metadata from chunk content"""
        metadata = {
            "word_count": len(content.split()),
            "character_count": len(content),
            "has_numbers": bool(re.search(r"\d", content)),
            "has_special_chars": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', content)),
            "extraction_method": "smart_streaming",
        }

        # Extract error codes if present
        error_codes = re.findall(r"Error\s+(\d+)", content, re.IGNORECASE)
        if error_codes:
            metadata["error_codes"] = error_codes

        # Extract step numbers if present
        steps = re.findall(r"Step\s+(\d+)", content, re.IGNORECASE)
        if steps:
            metadata["steps"] = steps

        return metadata

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences for better chunking"""
        # Simple sentence splitting
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() + "." for s in sentences if s.strip()]

    def _find_smart_break_point(self, text: str, max_length: int) -> int:
        """Find intelligent break point in text"""
        if len(text) <= max_length:
            return len(text)

        # Look for sentence endings first
        for i in range(max_length, max(0, max_length - 100), -1):
            if text[i] in ".!?":
                return i + 1

        # Look for paragraph breaks
        for i in range(max_length, max(0, max_length - 50), -1):
            if text[i] == "\n" and text[i - 1] == "\n":
                return i

        # Look for word boundaries
        for i in range(max_length, max(0, max_length - 30), -1):
            if text[i] == " ":
                return i

        return max_length

    def _create_mock_chunk(
        self, document_id: str, chunk_index: int, content: str, page_number: int, section_title: str, chunk_type: str
    ) -> dict[str, Any]:
        """Create mock chunk for testing"""
        return {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "content": content,
            "chunk_type": chunk_type,
            "page_number": page_number,
            "section_title": section_title,
            "confidence_score": 0.8,
            "language": "en",
            "metadata": {
                "word_count": len(content.split()),
                "character_count": len(content),
                "extraction_method": "mock",
            },
        }
