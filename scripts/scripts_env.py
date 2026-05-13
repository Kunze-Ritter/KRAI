"""Entry point for loading project environment variables in scripts.

This module provides a standardized entry point for scripts to load environment
variables, wrapping the internal _env module implementation.
"""

from scripts._env import load_env

__all__ = ["load_env"]
