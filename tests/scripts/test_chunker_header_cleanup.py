import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from processors.chunker import SmartChunker


def test_header_cleanup_enabled():
    chunker = SmartChunker(chunk_size=200, overlap_size=0, enable_header_cleanup=True)
    text = "Manual Header\nLaserJet Pro 400\nPage 1\n\nThis is the actual content for testing."
    page_texts = {1: text}
    chunks = chunker.chunk_document(page_texts, uuid4())

    assert len(chunks) == 1
    chunk = chunks[0]
    assert "Manual Header" not in chunk.text
    assert chunk.metadata.get("header_removed") is True
    assert "Manual Header" in chunk.metadata.get("page_header", "")
    assert chunk.metadata.get("header_detection_rules")


def test_header_cleanup_disabled():
    chunker = SmartChunker(chunk_size=200, overlap_size=0, enable_header_cleanup=False)
    text = "Manual Header\nLaserJet Pro 400\nPage 1\n\nContent remains with header."
    page_texts = {1: text}
    chunks = chunker.chunk_document(page_texts, uuid4())

    assert len(chunks) == 1
    chunk = chunks[0]
    assert "Manual Header" in chunk.text
    assert chunk.metadata.get("header_removed") is False
    assert "Manual Header" in chunk.metadata.get("page_header", "")
