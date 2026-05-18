"""
Context Extraction Configuration
Configuration for Phase 5: Context-Aware Media Processing
"""

import os
from dataclasses import dataclass
from enum import Enum


class ContextExtractionMode(Enum):
    """Context extraction modes"""

    DISABLED = "disabled"
    BASIC = "basic"  # Extract captions and basic context
    ENHANCED = "enhanced"  # Extract error codes, products, and related entities
    COMPREHENSIVE = "comprehensive"  # Full context extraction with embeddings


@dataclass
class ContextExtractionConfig:
    """Configuration for context extraction service"""

    # Main configuration
    enable_context_extraction: bool = True
    extraction_mode: ContextExtractionMode = ContextExtractionMode.ENHANCED

    # Image context extraction
    enable_image_context: bool = True
    image_caption_confidence_threshold: float = 0.7
    max_surrounding_paragraphs: int = 3
    max_context_length: int = 2000  # Maximum characters for context text

    # Video context extraction
    enable_video_context: bool = True
    video_description_confidence_threshold: float = 0.6
    max_video_context_length: int = 1500

    # Link context extraction
    enable_link_context: bool = True
    link_context_confidence_threshold: float = 0.5
    max_link_context_length: int = 1000

    # Error code extraction
    enable_error_code_extraction: bool = True
    error_code_patterns_file: str = "config/error_code_patterns.json"
    max_error_codes_per_media: int = 10

    # Product extraction
    enable_product_extraction: bool = True
    product_patterns_file: str = "config/parts_patterns.json"
    max_products_per_media: int = 5

    # Context embedding generation
    enable_context_embeddings: bool = True
    context_embedding_dimension: int = 768
    context_embedding_model: str = "nomic-embed-text:latest"

    # Processing limits
    max_media_items_per_batch: int = 50
    context_extraction_timeout_seconds: int = 30
    embedding_generation_timeout_seconds: int = 60

    # Quality control
    min_context_quality_score: float = 0.3
    enable_context_validation: bool = True
    filter_duplicate_contexts: bool = True

    # Logging and monitoring
    enable_detailed_logging: bool = False
    log_context_extraction_samples: bool = True
    max_log_samples_per_document: int = 5


class ContextExtractionConfigLoader:
    """Load context extraction configuration from environment variables"""

    @staticmethod
    def load_config() -> ContextExtractionConfig:
        """Load configuration from environment variables with defaults"""

        # Main configuration
        enable_context_extraction = os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() == "true"

        extraction_mode_str = os.getenv("CONTEXT_EXTRACTION_MODE", "enhanced")
        try:
            extraction_mode = ContextExtractionMode(extraction_mode_str)
        except ValueError:
            extraction_mode = ContextExtractionMode.ENHANCED

        # Image context extraction
        enable_image_context = os.getenv("ENABLE_IMAGE_CONTEXT", "true").lower() == "true"
        image_caption_confidence_threshold = float(os.getenv("IMAGE_CAPTION_CONFIDENCE_THRESHOLD", "0.7"))
        max_surrounding_paragraphs = int(os.getenv("MAX_SURROUNDING_PARAGRAPHS", "3"))
        max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "2000"))

        # Video context extraction
        enable_video_context = os.getenv("ENABLE_VIDEO_CONTEXT", "true").lower() == "true"
        video_description_confidence_threshold = float(os.getenv("VIDEO_DESCRIPTION_CONFIDENCE_THRESHOLD", "0.6"))
        max_video_context_length = int(os.getenv("MAX_VIDEO_CONTEXT_LENGTH", "1500"))

        # Link context extraction
        enable_link_context = os.getenv("ENABLE_LINK_CONTEXT", "true").lower() == "true"
        link_context_confidence_threshold = float(os.getenv("LINK_CONTEXT_CONFIDENCE_THRESHOLD", "0.5"))
        max_link_context_length = int(os.getenv("MAX_LINK_CONTEXT_LENGTH", "1000"))

        # Error code extraction
        enable_error_code_extraction = os.getenv("ENABLE_ERROR_CODE_EXTRACTION", "true").lower() == "true"
        error_code_patterns_file = os.getenv("ERROR_CODE_PATTERNS_FILE", "config/error_code_patterns.json")
        max_error_codes_per_media = int(os.getenv("MAX_ERROR_CODES_PER_MEDIA", "10"))

        # Product extraction
        enable_product_extraction = os.getenv("ENABLE_PRODUCT_EXTRACTION", "true").lower() == "true"
        product_patterns_file = os.getenv("PRODUCT_PATTERNS_FILE", "config/parts_patterns.json")
        max_products_per_media = int(os.getenv("MAX_PRODUCTS_PER_MEDIA", "5"))

        # Context embedding generation
        enable_context_embeddings = os.getenv("ENABLE_CONTEXT_EMBEDDINGS", "true").lower() == "true"
        context_embedding_dimension = int(os.getenv("CONTEXT_EMBEDDING_DIMENSION", "768"))
        context_embedding_model = os.getenv("CONTEXT_EMBEDDING_MODEL", "nomic-embed-text:latest")

        # Processing limits
        max_media_items_per_batch = int(os.getenv("MAX_MEDIA_ITEMS_PER_BATCH", "50"))
        context_extraction_timeout_seconds = int(os.getenv("CONTEXT_EXTRACTION_TIMEOUT_SECONDS", "30"))
        embedding_generation_timeout_seconds = int(os.getenv("EMBEDDING_GENERATION_TIMEOUT_SECONDS", "60"))

        # Quality control
        min_context_quality_score = float(os.getenv("MIN_CONTEXT_QUALITY_SCORE", "0.3"))
        enable_context_validation = os.getenv("ENABLE_CONTEXT_VALIDATION", "true").lower() == "true"
        filter_duplicate_contexts = os.getenv("FILTER_DUPLICATE_CONTEXTS", "true").lower() == "true"

        # Logging and monitoring
        enable_detailed_logging = os.getenv("ENABLE_DETAILED_CONTEXT_LOGGING", "false").lower() == "true"
        log_context_extraction_samples = os.getenv("LOG_CONTEXT_EXTRACTION_SAMPLES", "true").lower() == "true"
        max_log_samples_per_document = int(os.getenv("MAX_LOG_SAMPLES_PER_DOCUMENT", "5"))

        return ContextExtractionConfig(
            enable_context_extraction=enable_context_extraction,
            extraction_mode=extraction_mode,
            # Image context
            enable_image_context=enable_image_context,
            image_caption_confidence_threshold=image_caption_confidence_threshold,
            max_surrounding_paragraphs=max_surrounding_paragraphs,
            max_context_length=max_context_length,
            # Video context
            enable_video_context=enable_video_context,
            video_description_confidence_threshold=video_description_confidence_threshold,
            max_video_context_length=max_video_context_length,
            # Link context
            enable_link_context=enable_link_context,
            link_context_confidence_threshold=link_context_confidence_threshold,
            max_link_context_length=max_link_context_length,
            # Error code extraction
            enable_error_code_extraction=enable_error_code_extraction,
            error_code_patterns_file=error_code_patterns_file,
            max_error_codes_per_media=max_error_codes_per_media,
            # Product extraction
            enable_product_extraction=enable_product_extraction,
            product_patterns_file=product_patterns_file,
            max_products_per_media=max_products_per_media,
            # Context embeddings
            enable_context_embeddings=enable_context_embeddings,
            context_embedding_dimension=context_embedding_dimension,
            context_embedding_model=context_embedding_model,
            # Processing limits
            max_media_items_per_batch=max_media_items_per_batch,
            context_extraction_timeout_seconds=context_extraction_timeout_seconds,
            embedding_generation_timeout_seconds=embedding_generation_timeout_seconds,
            # Quality control
            min_context_quality_score=min_context_quality_score,
            enable_context_validation=enable_context_validation,
            filter_duplicate_contexts=filter_duplicate_contexts,
            # Logging and monitoring
            enable_detailed_logging=enable_detailed_logging,
            log_context_extraction_samples=log_context_extraction_samples,
            max_log_samples_per_document=max_log_samples_per_document,
        )

    @staticmethod
    def get_environment_variables() -> dict[str, str]:
        """Get all environment variables used by context extraction"""
        return {
            # Main configuration
            "ENABLE_CONTEXT_EXTRACTION": "Enable/disable context extraction (true/false)",
            "CONTEXT_EXTRACTION_MODE": "Extraction mode (disabled/basic/enhanced/comprehensive)",
            # Image context extraction
            "ENABLE_IMAGE_CONTEXT": "Enable image context extraction (true/false)",
            "IMAGE_CAPTION_CONFIDENCE_THRESHOLD": "Minimum confidence for image captions (0.0-1.0)",
            "MAX_SURROUNDING_PARAGRAPHS": "Maximum paragraphs to extract around images",
            "MAX_CONTEXT_LENGTH": "Maximum length of context text in characters",
            # Video context extraction
            "ENABLE_VIDEO_CONTEXT": "Enable video context extraction (true/false)",
            "VIDEO_DESCRIPTION_CONFIDENCE_THRESHOLD": "Minimum confidence for video descriptions (0.0-1.0)",
            "MAX_VIDEO_CONTEXT_LENGTH": "Maximum length of video context text in characters",
            # Link context extraction
            "ENABLE_LINK_CONTEXT": "Enable link context extraction (true/false)",
            "LINK_CONTEXT_CONFIDENCE_THRESHOLD": "Minimum confidence for link context (0.0-1.0)",
            "MAX_LINK_CONTEXT_LENGTH": "Maximum length of link context text in characters",
            # Error code extraction
            "ENABLE_ERROR_CODE_EXTRACTION": "Enable error code extraction (true/false)",
            "ERROR_CODE_PATTERNS_FILE": "Path to error code patterns JSON file",
            "MAX_ERROR_CODES_PER_MEDIA": "Maximum error codes to extract per media item",
            # Product extraction
            "ENABLE_PRODUCT_EXTRACTION": "Enable product extraction (true/false)",
            "PRODUCT_PATTERNS_FILE": "Path to product patterns JSON file",
            "MAX_PRODUCTS_PER_MEDIA": "Maximum products to extract per media item",
            # Context embedding generation
            "ENABLE_CONTEXT_EMBEDDINGS": "Enable context embedding generation (true/false)",
            "CONTEXT_EMBEDDING_DIMENSION": "Dimension of context embedding vectors",
            "CONTEXT_EMBEDDING_MODEL": "Ollama model for context embeddings",
            # Processing limits
            "MAX_MEDIA_ITEMS_PER_BATCH": "Maximum media items to process in one batch",
            "CONTEXT_EXTRACTION_TIMEOUT_SECONDS": "Timeout for context extraction in seconds",
            "EMBEDDING_GENERATION_TIMEOUT_SECONDS": "Timeout for embedding generation in seconds",
            # Quality control
            "MIN_CONTEXT_QUALITY_SCORE": "Minimum quality score for extracted context (0.0-1.0)",
            "ENABLE_CONTEXT_VALIDATION": "Enable context validation (true/false)",
            "FILTER_DUPLICATE_CONTEXTS": "Filter duplicate contexts (true/false)",
            # Logging and monitoring
            "ENABLE_DETAILED_CONTEXT_LOGGING": "Enable detailed logging (true/false)",
            "LOG_CONTEXT_EXTRACTION_SAMPLES": "Log context extraction samples (true/false)",
            "MAX_LOG_SAMPLES_PER_DOCUMENT": "Maximum log samples per document",
        }


# Global configuration instance
_context_config: ContextExtractionConfig | None = None


def get_context_config() -> ContextExtractionConfig:
    """Get the global context extraction configuration"""
    global _context_config
    if _context_config is None:
        _context_config = ContextExtractionConfigLoader.load_config()
    return _context_config


def reload_context_config() -> ContextExtractionConfig:
    """Reload the context extraction configuration from environment"""
    global _context_config
    _context_config = ContextExtractionConfigLoader.load_config()
    return _context_config
