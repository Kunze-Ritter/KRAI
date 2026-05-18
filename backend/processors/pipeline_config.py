"""
Pipeline Configuration - Centralized settings management

Reads all pipeline settings from .env and provides
consistent skip/enable logging across all processors.
"""

import os
from typing import Any

from .env_loader import load_all_env_files

# Load all .env.* files
load_all_env_files()


class PipelineConfig:
    """Centralized pipeline configuration"""

    def __init__(self):
        """Load all settings from .env"""

        # Processing stages
        self.enable_product_extraction = self._get_bool("ENABLE_PRODUCT_EXTRACTION", True)
        self.enable_parts_extraction = self._get_bool("ENABLE_PARTS_EXTRACTION", True)
        self.enable_error_code_extraction = self._get_bool("ENABLE_ERROR_CODE_EXTRACTION", True)
        self.enable_version_extraction = self._get_bool("ENABLE_VERSION_EXTRACTION", True)
        self.enable_image_extraction = self._get_bool("ENABLE_IMAGE_EXTRACTION", True)
        self.enable_ocr = self._get_bool("ENABLE_OCR", True)
        self.enable_vision_ai = self._get_bool("ENABLE_VISION_AI", True)
        self.enable_link_extraction = self._get_bool("ENABLE_LINK_EXTRACTION", True)
        self.enable_embeddings = self._get_bool("ENABLE_EMBEDDINGS", True)
        self.enable_brightcove_enrichment = self._get_bool("ENABLE_BRIGHTCOVE_ENRICHMENT", False)

        # Storage settings (MinIO/object-storage only)
        self.upload_images_to_storage = self._get_bool("UPLOAD_IMAGES_TO_STORAGE", False)
        self.upload_documents_to_storage = self._get_bool("UPLOAD_DOCUMENTS_TO_STORAGE", False)

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean value from environment"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def get_summary(self) -> dict[str, Any]:
        """Get configuration summary"""
        return {
            "extraction": {
                "products": self.enable_product_extraction,
                "parts": self.enable_parts_extraction,
                "error_codes": self.enable_error_code_extraction,
                "versions": self.enable_version_extraction,
                "images": self.enable_image_extraction,
                "links": self.enable_link_extraction,
                "brightcove_enrichment": self.enable_brightcove_enrichment,
            },
            "ai": {
                "ocr": self.enable_ocr,
                "vision": self.enable_vision_ai,
                "embeddings": self.enable_embeddings,
            },
            "storage": {
                "images_to_storage": self.upload_images_to_storage,
                "documents_to_storage": self.upload_documents_to_storage,
            },
        }


def log_stage_header(logger, stage_number: str, stage_name: str):
    """
    Log consistent stage header

    Args:
        logger: Logger instance
        stage_number: Stage number (e.g., "2", "3c", "6-7")
        stage_name: Stage name (e.g., "Product Extraction")
    """
    logger.info("=" * 80)
    logger.info(f"STAGE {stage_number}: {stage_name}")
    logger.info("=" * 80)


def log_step_header(logger, step_number: str, total_steps: int, step_name: str):
    """
    Log consistent step header

    Args:
        logger: Logger instance
        step_number: Step number (e.g., "2", "3c")
        total_steps: Total number of steps
        step_name: Step name (e.g., "Extracting product models")
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"STEP {step_number}/{total_steps}: {step_name}")
    logger.info("=" * 80)


def log_stage_skip(logger, stage_number: str, stage_name: str, reason: str):
    """
    Log stage skip with consistent formatting

    Args:
        logger: Logger instance
        stage_number: Stage number
        stage_name: Stage name
        reason: Reason for skipping
    """
    logger.info("=" * 80)
    logger.info(f"⏭️  STAGE {stage_number}: {stage_name} - SKIPPED")
    logger.info(f"   Reason: {reason}")
    logger.info("=" * 80)


def log_step_skip(logger, step_number: str, total_steps: int, step_name: str, reason: str):
    """
    Log step skip with consistent formatting

    Args:
        logger: Logger instance
        step_number: Step number
        total_steps: Total steps
        step_name: Step name
        reason: Reason for skipping
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"⏭️  STEP {step_number}/{total_steps}: {step_name} - SKIPPED")
    logger.info(f"   Reason: {reason}")
    logger.info("=" * 80)


# Global config instance
_config = None


def get_pipeline_config() -> PipelineConfig:
    """Get global pipeline configuration instance"""
    global _config
    if _config is None:
        _config = PipelineConfig()
    return _config
