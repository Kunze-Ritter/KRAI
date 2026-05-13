"""
KR-AI-Engine Core Module
Base interfaces and data models for the processing pipeline
"""

from .base_processor import BaseProcessor, ProcessingError, ProcessingResult
from .data_models import ChunkModel, DocumentModel, ErrorCodeModel, ImageModel

__all__ = [
    "BaseProcessor",
    "ChunkModel",
    "DocumentModel",
    "ErrorCodeModel",
    "ImageModel",
    "ProcessingError",
    "ProcessingResult",
]
