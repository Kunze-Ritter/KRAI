"""Compatibility shim for legacy MasterPipeline imports.

This module preserves the previous import path while the canonical
implementation lives in ``backend.pipeline.master_pipeline``.
"""

from backend.pipeline.master_pipeline import KRMasterPipeline

__all__ = ["KRMasterPipeline", "MasterPipeline"]

# Backwards compatibility alias
MasterPipeline = KRMasterPipeline
