"""Centralized Import Module

Handles all imports for processors to avoid path issues.
Use this instead of direct imports in processor files.

Uses lazy imports - functions are imported only when called.
"""

import sys
from pathlib import Path

# Setup paths once
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


# Lazy import functions - import only when called
def get_database_adapter():
    """Create and return database adapter (PostgreSQL)"""
    from backend.services.database_factory import create_database_adapter

    from .env_loader import load_all_env_files

    # Load all .env.* files
    load_all_env_files()

    return create_database_adapter()


def get_logger():
    """Lazy import of get_logger"""
    from processors.logger import get_logger as _get_logger

    return _get_logger()


def extract_parts(text):
    """Lazy import of extract_parts"""
    from utils.parts_extractor import extract_parts as _extract

    return _extract(text)


def extract_parts_with_context(text, manufacturer_key=None, max_parts=20):
    """Lazy import of extract_parts_with_context"""
    from utils.parts_extractor import extract_parts_with_context as _extract

    return _extract(text, manufacturer_key, max_parts)


def detect_series(model_number, manufacturer_name):
    """Lazy import of detect_series"""
    from utils.series_detector import detect_series as _detect

    return _detect(model_number, manufacturer_name)


__all__ = ["detect_series", "extract_parts", "extract_parts_with_context", "get_database_adapter", "get_logger"]
