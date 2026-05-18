"""Central Configuration Module

All environment variables should be accessed through this module.
Provides type-safe access with defaults.
"""

import os
from typing import Optional


class Config:
    """Central configuration with type-safe access."""

    # Database
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "postgresql")
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "")
    DATABASE_CONNECTION_URL: str = os.getenv("DATABASE_CONNECTION_URL", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SCHEMA_PREFIX: str = os.getenv("SCHEMA_PREFIX", "krai")

    # Object Storage (MinIO)
    OBJECT_STORAGE_ENDPOINT: str = os.getenv("OBJECT_STORAGE_ENDPOINT", "localhost:9000")
    OBJECT_STORAGE_ACCESS_KEY: str = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "")
    OBJECT_STORAGE_SECRET_KEY: str = os.getenv("OBJECT_STORAGE_SECRET_KEY", "")
    OBJECT_STORAGE_BUCKET_DOCUMENTS: str = os.getenv("OBJECT_STORAGE_BUCKET_DOCUMENTS", "documents")
    OBJECT_STORAGE_BUCKET_IMAGES: str = os.getenv("OBJECT_STORAGE_BUCKET_IMAGES", "images")
    OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS: str = os.getenv("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS", "")
    OBJECT_STORAGE_PUBLIC_URL_IMAGES: str = os.getenv("OBJECT_STORAGE_PUBLIC_URL_IMAGES", "")

    # AI/Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL_CHAT: str = os.getenv("OLLAMA_MODEL_CHAT", "llama3.2:latest")
    OLLAMA_MODEL_TEXT: str = os.getenv("OLLAMA_MODEL_TEXT", "llama3.2:latest")
    OLLAMA_MODEL_EMBEDDING: str = os.getenv("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text:latest")

    # Feature Flags
    ENABLE_BRIGHTCOVE_ENRICHMENT: bool = os.getenv("ENABLE_BRIGHTCOVE_ENRICHMENT", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ENABLE_SVG_EXTRACTION: bool = os.getenv("ENABLE_SVG_EXTRACTION", "false").lower() in {"1", "true", "yes", "on"}
    ENABLE_TABLE_EXTRACTION: bool = os.getenv("ENABLE_TABLE_EXTRACTION", "true").lower() in {"1", "true", "yes", "on"}
    ENABLE_CONTEXT_EXTRACTION: bool = os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ENABLE_HIERARCHICAL_CHUNKING: bool = os.getenv("ENABLE_HIERARCHICAL_CHUNKING", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Embedding
    EMBEDDING_REQUEST_TIMEOUT: float = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT", "30"))
    EMBEDDING_REQUEST_MAX_RETRIES: int = int(os.getenv("EMBEDDING_REQUEST_MAX_RETRIES", "4"))
    EMBEDDING_TARGET_LATENCY_LOWER: float = float(os.getenv("EMBEDDING_TARGET_LATENCY_LOWER", "1.0"))
    EMBEDDING_TARGET_LATENCY_UPPER: float = float(os.getenv("EMBEDDING_TARGET_LATENCY_UPPER", "2.0"))

    # Vision AI
    VISION_REQUEST_TIMEOUT: float = float(os.getenv("VISION_REQUEST_TIMEOUT", "60"))
    VISION_REQUEST_MAX_RETRIES: int = int(os.getenv("VISION_REQUEST_MAX_RETRIES", "4"))
    VISION_MAX_IMAGE_MB: float = float(os.getenv("VISION_MAX_IMAGE_MB", "12.0"))
    VISION_MAX_IMAGES_PER_DOCUMENT: int = int(os.getenv("VISION_MAX_IMAGES_PER_DOCUMENT", "80"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TESTING: bool = os.getenv("TESTING", "false").lower() in {"1", "true", "yes", "on"}

    # Firecrawl
    FIRECRAWL_API_URL: str = os.getenv("FIRECRAWL_API_URL", "http://localhost:9004")
    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
    FIRECRAWL_LLM_PROVIDER: str = os.getenv("FIRECRAWL_LLM_PROVIDER", "ollama")
    FIRECRAWL_MODEL_NAME: str = os.getenv("FIRECRAWL_MODEL_NAME", "llama3.2:latest")
    FIRECRAWL_EMBEDDING_MODEL: str = os.getenv("FIRECRAWL_EMBEDDING_MODEL", "nomic-embed-text:latest")
    FIRECRAWL_TIMEOUT: float = float(os.getenv("FIRECRAWL_TIMEOUT", "30.0"))
    FIRECRAWL_CRAWL_TIMEOUT: float = float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "300.0"))

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    @classmethod
    def get_postgres_url(cls) -> str:
        """Get PostgreSQL URL with fallback."""
        return cls.DATABASE_CONNECTION_URL or cls.POSTGRES_URL or cls.DATABASE_URL

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return os.getenv("ENVIRONMENT", "development") == "production"


# Singleton instance
config = Config()
