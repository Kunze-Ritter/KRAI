# 🚀 KR-AI-Engine - Modular Processing System
"""
Modular Document Processing System for KR-AI-Engine

This package contains all the specialized processors and utilities for
AI-powered document processing in technical service environments.

Main Components:
- ModularDocumentProcessor: Master orchestrator for all processing tasks
- Specialized Processors: Text, Image, Embedding, Classification, Storage
- Base Infrastructure: Common interfaces, error handling, metrics
- Utilities: Chunking algorithms, Ollama client, helper functions
"""

from .interfaces.base_processor import (
    BaseProcessor,
    ProcessingContext,
    ProcessingException,
    ProcessingResult,
    ProcessingStatus,
    ProcessorChain,
    ResourceException,
    ValidationException,
)
from .modular_document_processor import (
    DocumentProcessingPipeline,
    ModularDocumentProcessor,
    ProcessingSession,
    batch_process_documents,
    process_document,
)
from .processors.classification_processor import ClassificationProcessor
from .processors.embedding_processor import EmbeddingProcessor
from .processors.image_processor import ImageProcessor
from .processors.storage_processor import StorageProcessor
from .processors.text_processor import TextProcessor
from .utils.chunk_utils import ChunkingUtils
from .utils.ollama_client import OllamaClient

# Version info
__version__ = "1.0.0"
__author__ = "KR-AI-Engine Team"
__description__ = "Modular AI-powered document processing system"

# Module metadata
__all__ = [
    # Main orchestrator
    "ModularDocumentProcessor",
    "DocumentProcessingPipeline",
    "ProcessingSession",
    "process_document",
    "batch_process_documents",
    # Base interfaces
    "BaseProcessor",
    "ProcessingContext",
    "ProcessingResult",
    "ProcessorChain",
    "ProcessingStatus",
    "ProcessingException",
    "ValidationException",
    "ResourceException",
    # Specialized processors
    "TextProcessor",
    "ImageProcessor",
    "EmbeddingProcessor",
    "ClassificationProcessor",
    "StorageProcessor",
    # Utilities
    "ChunkingUtils",
    "OllamaClient",
]
