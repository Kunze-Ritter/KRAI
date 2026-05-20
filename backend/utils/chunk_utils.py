"""
Chunking Utilities for KR-AI-Engine
Intelligent text chunking strategies
"""

import logging
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkData:
    """Chunk data structure"""

    content: str
    section_title: str | None = None
    confidence: float = 0.8
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChunkingStrategy:
    """
    Intelligent text chunking strategies for KR-AI-Engine

    Supports multiple chunking strategies:
    - Simple word chunking
    - Sentence-based chunking
    - Paragraph-based chunking
    - Contextual chunking
    - Structure-based chunking
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.chunking")
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for chunking strategy"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - Chunking - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def create_chunks(
        self, text: str, strategy: str = "contextual_chunking", chunk_size: int = 1000, chunk_overlap: int = 150
    ) -> list[ChunkData]:
        """
        Create chunks from text using specified strategy

        Args:
            text: Input text to chunk
            strategy: Chunking strategy to use
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks

        Returns:
            List of ChunkData objects
        """
        try:
            if strategy == "simple_word_chunking":
                return self._simple_word_chunking(text, chunk_size, chunk_overlap)
            if strategy == "sentence_based_chunking":
                return self._sentence_based_chunking(text, chunk_size, chunk_overlap)
            if strategy == "paragraph_based_chunking":
                return self._paragraph_based_chunking(text, chunk_size, chunk_overlap)
            if strategy == "contextual_chunking":
                return self._contextual_chunking(text, chunk_size, chunk_overlap)
            if strategy == "structure_based_chunking":
                return self._structure_based_chunking(text, chunk_size, chunk_overlap)
            self.logger.warning(f"Unknown chunking strategy: {strategy}. Using contextual_chunking.")
            return self._contextual_chunking(text, chunk_size, chunk_overlap)

        except Exception as e:
            self.logger.error(f"Failed to create chunks: {e}")
            return []

    def _simple_word_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        """Simple word-based chunking"""
        try:
            chunks = []
            words = text.split()

            start = 0
            while start < len(words):
                end = min(start + chunk_size, len(words))
                chunk_words = words[start:end]
                chunk_text = " ".join(chunk_words)

                chunk = ChunkData(
                    content=chunk_text,
                    confidence=0.8,
                    metadata={"strategy": "simple_word_chunking", "word_count": len(chunk_words)},
                )
                chunks.append(chunk)

                start = end - chunk_overlap
                if start >= len(words):
                    break

            self.logger.info(f"Created {len(chunks)} chunks using simple word chunking")
            return chunks

        except Exception as e:
            self.logger.error(f"Simple word chunking failed: {e}")
            return []

    def _sentence_based_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        """Sentence-based chunking"""
        try:
            # Split into sentences
            sentences = re.split(r"[.!?]+", text)
            sentences = [s.strip() for s in sentences if s.strip()]

            chunks = []
            current_chunk = ""
            current_sentences = []

            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += sentence + ". "
                    current_sentences.append(sentence)
                else:
                    if current_chunk:
                        chunk = ChunkData(
                            content=current_chunk.strip(),
                            confidence=0.9,
                            metadata={"strategy": "sentence_based_chunking", "sentence_count": len(current_sentences)},
                        )
                        chunks.append(chunk)

                    # Start new chunk with overlap
                    overlap_sentences = current_sentences[-2:] if len(current_sentences) >= 2 else current_sentences
                    current_chunk = " ".join(overlap_sentences) + " " + sentence + ". "
                    current_sentences = [*overlap_sentences, sentence]

            # Add final chunk
            if current_chunk:
                chunk = ChunkData(
                    content=current_chunk.strip(),
                    confidence=0.9,
                    metadata={"strategy": "sentence_based_chunking", "sentence_count": len(current_sentences)},
                )
                chunks.append(chunk)

            self.logger.info(f"Created {len(chunks)} chunks using sentence-based chunking")
            return chunks

        except Exception as e:
            self.logger.error(f"Sentence-based chunking failed: {e}")
            return []

    def _paragraph_based_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        """Paragraph-based chunking"""
        try:
            # Split into paragraphs
            paragraphs = text.split("\n\n")
            paragraphs = [p.strip() for p in paragraphs if p.strip()]

            chunks = []
            current_chunk = ""
            current_paragraphs = []

            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) <= chunk_size:
                    current_chunk += paragraph + "\n\n"
                    current_paragraphs.append(paragraph)
                else:
                    if current_chunk:
                        chunk = ChunkData(
                            content=current_chunk.strip(),
                            confidence=0.95,
                            metadata={
                                "strategy": "paragraph_based_chunking",
                                "paragraph_count": len(current_paragraphs),
                            },
                        )
                        chunks.append(chunk)

                    # Start new chunk with overlap
                    overlap_paragraphs = current_paragraphs[-1:] if current_paragraphs else []
                    current_chunk = "\n\n".join(overlap_paragraphs) + "\n\n" + paragraph + "\n\n"
                    current_paragraphs = [*overlap_paragraphs, paragraph]

            # Add final chunk
            if current_chunk:
                chunk = ChunkData(
                    content=current_chunk.strip(),
                    confidence=0.95,
                    metadata={"strategy": "paragraph_based_chunking", "paragraph_count": len(current_paragraphs)},
                )
                chunks.append(chunk)

            self.logger.info(f"Created {len(chunks)} chunks using paragraph-based chunking")
            return chunks

        except Exception as e:
            self.logger.error(f"Paragraph-based chunking failed: {e}")
            return []

    def _contextual_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        """Contextual chunking with semantic awareness"""
        try:
            # Split into sections based on headers
            sections = self._split_into_sections(text)

            chunks = []
            for section in sections:
                section_title = section.get("title", "")
                section_content = section.get("content", "")

                if len(section_content) <= chunk_size:
                    # Section fits in one chunk
                    chunk = ChunkData(
                        content=section_content,
                        section_title=section_title,
                        confidence=0.9,
                        metadata={"strategy": "contextual_chunking", "section": section_title},
                    )
                    chunks.append(chunk)
                else:
                    # Split section into smaller chunks
                    section_chunks = self._split_section_into_chunks(
                        section_content, section_title, chunk_size, chunk_overlap
                    )
                    chunks.extend(section_chunks)

            self.logger.info(f"Created {len(chunks)} chunks using contextual chunking")
            return chunks

        except Exception as e:
            self.logger.error(f"Contextual chunking failed: {e}")
            return []

    def _structure_based_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        """Structure-based chunking for technical documents"""
        try:
            # Identify document structure
            structure = self._identify_document_structure(text)

            chunks = []
            for element in structure:
                element_type = element.get("type", "text")
                element_content = element.get("content", "")
                element_title = element.get("title", "")

                if element_type in ["header", "section"]:
                    # Headers and sections get their own chunks
                    chunk = ChunkData(
                        content=element_content,
                        section_title=element_title,
                        confidence=0.95,
                        metadata={"strategy": "structure_based_chunking", "element_type": element_type},
                    )
                    chunks.append(chunk)
                elif element_type == "procedure":
                    # Procedures are chunked by steps
                    procedure_chunks = self._chunk_procedure(element_content, chunk_size)
                    chunks.extend(procedure_chunks)
                else:
                    # Regular text chunking
                    if len(element_content) <= chunk_size:
                        chunk = ChunkData(
                            content=element_content,
                            section_title=element_title,
                            confidence=0.8,
                            metadata={"strategy": "structure_based_chunking", "element_type": element_type},
                        )
                        chunks.append(chunk)
                    else:
                        text_chunks = self._split_text_into_chunks(element_content, chunk_size, chunk_overlap)
                        for i, text_chunk in enumerate(text_chunks):
                            chunk = ChunkData(
                                content=text_chunk,
                                section_title=f"{element_title} (Part {i+1})" if element_title else None,
                                confidence=0.8,
                                metadata={"strategy": "structure_based_chunking", "element_type": element_type},
                            )
                            chunks.append(chunk)

            self.logger.info(f"Created {len(chunks)} chunks using structure-based chunking")
            return chunks

        except Exception as e:
            self.logger.error(f"Structure-based chunking failed: {e}")
            return []

    def _split_into_sections(self, text: str) -> list[dict[str, str]]:
        """Split text into sections based on headers"""
        try:
            sections = []
            current_section = {"title": "", "content": ""}

            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if line is a header (various patterns)
                if self._is_header(line):
                    if current_section["content"]:
                        sections.append(current_section)
                    current_section = {"title": line, "content": ""}
                else:
                    current_section["content"] += line + "\n"

            if current_section["content"]:
                sections.append(current_section)

            return sections

        except Exception as e:
            self.logger.error(f"Failed to split into sections: {e}")
            return [{"title": "", "content": text}]

    def _is_header(self, line: str) -> bool:
        """Check if line is a header"""
        # Various header patterns
        header_patterns = [
            r"^\d+\.\s+[A-Z]",  # 1. HEADER
            r"^[A-Z][A-Z\s]+$",  # ALL CAPS
            r"^[A-Z][a-z].*:$",  # Title:
            r"^\d+\.\d+\s+",  # 1.1 Header
        ]

        return any(re.match(pattern, line) for pattern in header_patterns)

    def _split_section_into_chunks(
        self, content: str, title: str, chunk_size: int, chunk_overlap: int
    ) -> list[ChunkData]:
        """Split a section into smaller chunks"""
        try:
            chunks = []
            start = 0

            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunk_content = content[start:end]

                chunk = ChunkData(
                    content=chunk_content,
                    section_title=title,
                    confidence=0.8,
                    metadata={"strategy": "contextual_chunking", "section": title},
                )
                chunks.append(chunk)

                start = end - chunk_overlap
                if start >= len(content):
                    break

            return chunks

        except Exception as e:
            self.logger.error(f"Failed to split section into chunks: {e}")
            return []

    def _identify_document_structure(self, text: str) -> list[dict[str, str]]:
        """Identify document structure elements"""
        try:
            structure = []
            lines = text.split("\n")
            current_element = {"type": "text", "title": "", "content": ""}

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Identify element type
                if self._is_header(line):
                    if current_element["content"]:
                        structure.append(current_element)
                    current_element = {"type": "section", "title": line, "content": ""}
                elif self._is_procedure_line(line):
                    if current_element["type"] != "procedure":
                        if current_element["content"]:
                            structure.append(current_element)
                        current_element = {"type": "procedure", "title": "Procedure", "content": ""}
                    current_element["content"] += line + "\n"
                else:
                    current_element["content"] += line + "\n"

            if current_element["content"]:
                structure.append(current_element)

            return structure

        except Exception as e:
            self.logger.error(f"Failed to identify document structure: {e}")
            return [{"type": "text", "title": "", "content": text}]

    def _is_procedure_line(self, line: str) -> bool:
        """Check if line is part of a procedure"""
        procedure_patterns = [
            r"^\d+\.\s+",  # 1. Step
            r"^Step\s+\d+",  # Step 1
            r"^\d+\)\s+",  # 1) Step
        ]

        return any(re.match(pattern, line) for pattern in procedure_patterns)

    def _chunk_procedure(self, procedure_text: str, chunk_size: int) -> list[ChunkData]:
        """Chunk procedure text by steps"""
        try:
            chunks = []
            steps = re.split(r"\n(?=\d+\.)", procedure_text)

            for step in steps:
                if step.strip():
                    chunk = ChunkData(
                        content=step.strip(),
                        section_title="Procedure Step",
                        confidence=0.9,
                        metadata={"strategy": "structure_based_chunking", "element_type": "procedure"},
                    )
                    chunks.append(chunk)

            return chunks

        except Exception as e:
            self.logger.error(f"Failed to chunk procedure: {e}")
            return []

    def _split_text_into_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        """Split text into chunks with overlap"""
        try:
            chunks = []
            start = 0

            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk = text[start:end]
                chunks.append(chunk)

                start = end - chunk_overlap
                if start >= len(text):
                    break

            return chunks

        except Exception as e:
            self.logger.error(f"Failed to split text into chunks: {e}")
            return [text]
