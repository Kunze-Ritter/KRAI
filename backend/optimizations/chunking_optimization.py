"""
Memory-Optimized Chunking for KR-AI-Engine
Optimizations for large PDF processing with minimal RAM usage
"""

import gc
import logging
from collections.abc import Generator
from typing import Any

try:
    import fitz
except ImportError:
    fitz = None


class MemoryOptimizedChunking:
    """
    Memory-optimized chunking strategies to reduce RAM usage
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger("krai.chunking.optimized")

    def extract_text_streaming(self, file_path: str) -> Generator[str, None, None]:
        """
        Stream PDF text page by page instead of loading all at once

        Args:
            file_path: Path to PDF file

        Yields:
            Page text content
        """
        if fitz is None:
            yield "Mock text content for testing."
            return

        try:
            doc = fitz.open(file_path)

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()

                # Yield page text and immediately free memory
                yield page_text

                # Force garbage collection for each page
                del page_text
                gc.collect()

            doc.close()

        except Exception as e:
            self.logger.error(f"Streaming text extraction failed: {e}")
            yield "Error extracting text from PDF"

    def create_chunks_streaming(
        self, text_stream: Generator[str, None, None], document_id: str
    ) -> Generator[dict[str, Any], None, None]:
        """
        Create chunks from streaming text to minimize memory usage

        Args:
            text_stream: Generator of text content
            document_id: Document ID for chunk metadata

        Yields:
            Chunk data dictionaries
        """
        buffer = ""
        chunk_index = 0

        for page_text in text_stream:
            buffer += page_text + "\n"

            # Process buffer in chunks
            while len(buffer) >= self.chunk_size:
                # Find good break point (end of sentence or word)
                break_point = self._find_break_point(buffer, self.chunk_size)

                chunk_text = buffer[:break_point]
                buffer = buffer[break_point - self.overlap :]

                chunk_data = {
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "content": chunk_text,
                    "chunk_type": "text",
                    "page_number": None,
                    "section_title": None,
                    "confidence_score": 0.8,
                    "language": "en",
                }

                yield chunk_data
                chunk_index += 1

                # Force garbage collection
                del chunk_text
                gc.collect()

        # Process remaining buffer
        if buffer.strip():
            chunk_data = {
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": buffer.strip(),
                "chunk_type": "text",
                "page_number": None,
                "section_title": None,
                "confidence_score": 0.8,
                "language": "en",
            }
            yield chunk_data

    def _find_break_point(self, text: str, max_length: int) -> int:
        """Find good break point in text (end of sentence or word)"""
        if len(text) <= max_length:
            return len(text)

        # Look for sentence endings
        for i in range(max_length, max(0, max_length - 100), -1):
            if text[i] in ".!?":
                return i + 1

        # Look for word boundaries
        for i in range(max_length, max(0, max_length - 50), -1):
            if text[i] == " ":
                return i

        return max_length


class ParallelChunkingProcessor:
    """
    Process chunks in parallel to utilize CPU cores
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.logger = logging.getLogger("krai.chunking.parallel")

    async def process_chunks_parallel(
        self, chunk_stream: Generator[dict[str, Any], None, None], database_service
    ) -> list[str]:
        """
        Process chunks in parallel batches

        Args:
            chunk_stream: Generator of chunk data
            database_service: Database service for storing chunks

        Returns:
            List of chunk IDs
        """

        chunk_ids = []
        batch_size = self.max_workers * 2  # Process in batches

        batch = []

        for chunk_data in chunk_stream:
            batch.append(chunk_data)

            if len(batch) >= batch_size:
                # Process batch in parallel
                batch_ids = await self._process_batch_parallel(batch, database_service)
                chunk_ids.extend(batch_ids)

                # Clear batch and force garbage collection
                batch.clear()
                gc.collect()

        # Process remaining chunks
        if batch:
            batch_ids = await self._process_batch_parallel(batch, database_service)
            chunk_ids.extend(batch_ids)

        return chunk_ids

    async def _process_batch_parallel(self, batch: list[dict[str, Any]], database_service) -> list[str]:
        """Process a batch of chunks in parallel"""
        import asyncio

        # Create tasks for parallel processing
        tasks = []
        for chunk_data in batch:
            task = database_service.create_chunk_async(chunk_data)
            tasks.append(task)

        # Wait for all tasks to complete
        chunk_ids = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_ids = [chunk_id for chunk_id in chunk_ids if isinstance(chunk_id, str)]

        return valid_ids


class MemoryMonitoring:
    """
    Monitor memory usage during chunking
    """

    @staticmethod
    def get_memory_usage():
        """Get current memory usage in MB"""
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # Convert to MB

    @staticmethod
    def log_memory_usage(logger, stage: str):
        """Log memory usage for a specific stage"""
        memory_mb = MemoryMonitoring.get_memory_usage()
        logger.info(f"Memory usage at {stage}: {memory_mb:.1f} MB")

    @staticmethod
    def force_cleanup():
        """Force garbage collection and memory cleanup"""
        gc.collect()

        # Additional cleanup for large objects
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except:
            pass  # Not available on Windows
