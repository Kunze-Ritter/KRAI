"""Service Locator for KRAI Pipeline

Lazy loading of services and processors to reduce import time.
Import this module instead of importing services directly.
"""

from typing import Any, ClassVar


class ServiceLocator:
    """Lazy service and processor locator."""

    _services: ClassVar[dict[str, Any]] = {}

    # Service mappings (module path -> class/function name)
    SERVICE_MAP: ClassVar = {
        # Services
        "ObjectStorageService": "backend.services.object_storage_service.ObjectStorageService",
        "create_storage_service": "backend.services.storage_factory.create_storage_service",
        "create_database_adapter": "backend.services.database_factory.create_database_adapter",
        "AIService": "backend.services.ai_service.AIService",
        "ConfigService": "backend.services.config_service.ConfigService",
        "FeaturesService": "backend.services.features_service.FeaturesService",
        "QualityCheckService": "backend.services.quality_check_service.QualityCheckService",
        "FileLocatorService": "backend.services.file_locator_service.FileLocatorService",
        "ManufacturerVerificationService": "backend.services.manufacturer_verification_service.ManufacturerVerificationService",
        "create_web_scraping_service": "backend.services.web_scraping_service.create_web_scraping_service",
        "PerformanceCollector": "backend.services.performance_service.PerformanceCollector",
        "AlertService": "backend.services.alert_service.AlertService",
        "StageAlertManager": "backend.services.stage_alert_manager.StageAlertManager",
        "apply_colored_logging_globally": "backend.utils.colored_logging.apply_colored_logging_globally",
        # Processors
        "UploadProcessor": "backend.processors.upload_processor.UploadProcessor",
        "OptimizedTextProcessor": "backend.processors.text_processor_optimized.OptimizedTextProcessor",
        "SVGProcessor": "backend.processors.svg_processor.SVGProcessor",
        "ImageProcessor": "backend.processors.image_processor.ImageProcessor",
        "ClassificationProcessor": "backend.processors.classification_processor.ClassificationProcessor",
        "ChunkPreprocessor": "backend.processors.chunk_preprocessor.ChunkPreprocessor",
        "MetadataProcessorAI": "backend.processors.metadata_processor_ai.MetadataProcessorAI",
        "LinkExtractionProcessorAI": "backend.processors.link_extraction_processor_ai.LinkExtractionProcessorAI",
        "StorageProcessor": "backend.processors.storage_processor.StorageProcessor",
        "EmbeddingProcessor": "backend.processors.embedding_processor.EmbeddingProcessor",
        "SearchProcessor": "backend.processors.search_processor.SearchProcessor",
        "VisualEmbeddingProcessor": "backend.processors.visual_embedding_processor.VisualEmbeddingProcessor",
        "TableProcessor": "backend.processors.table_processor.TableProcessor",
        "ThumbnailProcessor": "backend.processors.thumbnail_processor.ThumbnailProcessor",
        "PartsProcessor": "backend.processors.parts_processor.PartsProcessor",
        "SeriesProcessor": "backend.processors.series_processor.SeriesProcessor",
        "VideoEnrichmentProcessor": "backend.processors.video_enrichment_processor.VideoEnrichmentProcessor",
        "get_pipeline_config": "backend.processors.pipeline_config.get_pipeline_config",
    }

    @classmethod
    def get(cls, name: str) -> Any:
        """Get a service or processor by name (lazy loaded)."""
        if name not in cls._services:
            if name not in cls.SERVICE_MAP:
                raise ImportError(f"Unknown service: {name}")

            import importlib

            full_path = cls.SERVICE_MAP[name]
            module_path, attr_name = full_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls._services[name] = getattr(module, attr_name)

        return cls._services[name]

    @classmethod
    def preload(cls, *names: str) -> None:
        """Preload specific services."""
        for name in names:
            cls.get(name)

    @classmethod
    def preload_all(cls) -> None:
        """Preload all services (useful for testing)."""
        for name in cls.SERVICE_MAP:
            cls.get(name)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cache (useful for testing)."""
        cls._services.clear()


# Convenience function
def get_service(name: str) -> Any:
    """Get a service by name."""
    return ServiceLocator.get(name)
