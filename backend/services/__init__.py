"""
KR-AI-Engine Services Module
Core services for storage, and AI operations
"""

from .ai_service import AIService, create_ai_service
from .config_service import ConfigService
from .link_enrichment_service import LinkEnrichmentService
from .manufacturer_crawler import ManufacturerCrawler
from .manufacturer_verification_service import ManufacturerVerificationService
from .object_storage_service import ObjectStorageService
from .storage_factory import StorageFactory, create_storage_service
from .structured_extraction_service import StructuredExtractionService
from .web_scraping_service import (
    BeautifulSoupBackend,
    FirecrawlBackend,
    WebScraperBackend,
    WebScrapingService,
    create_web_scraping_service,
)

__all__ = [
    "AIService",
    "BeautifulSoupBackend",
    "ConfigService",
    "FirecrawlBackend",
    "LinkEnrichmentService",
    "ManufacturerCrawler",
    "ManufacturerVerificationService",
    "ObjectStorageService",
    "StorageFactory",
    "StructuredExtractionService",
    "WebScraperBackend",
    "WebScrapingService",
    "create_ai_service",
    "create_storage_service",
    "create_web_scraping_service",
]
