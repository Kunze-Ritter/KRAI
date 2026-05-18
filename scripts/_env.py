"""Shared helpers for loading project environment variables in scripts."""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files  # noqa: E402


def load_env(extra_files: Iterable[str] | None = None) -> list[str]:
    """Load environment variables using the centralized loader.

    Args:
        extra_files: Optional iterable of additional `.env` filenames to load
            after the defaults. This mirrors `load_all_env_files` semantics.

    Returns:
        A list of `.env` filenames that were successfully loaded.
    """

    files: Sequence[str] | None = None

    if extra_files:
        if isinstance(extra_files, str):
            files = [extra_files]
        else:
            files = list(extra_files)

    return load_all_env_files(PROJECT_ROOT, extra_files=files if files else None)
