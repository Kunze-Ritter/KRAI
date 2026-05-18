# 🚀 KR-AI-Engine - Processing Modules
"""
Specialized document processing modules

Each processor handles a specific aspect of document analysis:
- TextProcessor: PDF text extraction and chunking
- ImageProcessor: Image extraction, OCR, and vision AI
- EmbeddingProcessor: Vector generation and management
- ClassificationProcessor: Document type and metadata classification
- StorageProcessor: Database and storage operations
"""

from .classification_processor import ClassificationProcessor
from .embedding_processor import EmbeddingProcessor
from .image_processor import ImageProcessor
from .storage_processor import StorageProcessor
from .text_processor import TextProcessor

__all__ = ["ClassificationProcessor", "EmbeddingProcessor", "ImageProcessor", "StorageProcessor", "TextProcessor"]
