"""
Configuration Service for KR-AI-Engine
Manages all configuration files and settings
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, cast


class ConfigService:
    """
    Configuration service for KR-AI-Engine

    Manages configuration files:
    - chunk_settings.json: Text chunking strategies
    - error_code_patterns.json: Error code patterns
    - version_patterns.json: Version extraction patterns
    - model_placeholder_patterns.json: Model placeholder patterns
    """

    def __init__(self, config_dir: str = "config"):
        # Get the absolute path to the config directory
        current_dir = Path(__file__).parent.parent  # Go up from services/ to backend/
        self.config_dir = current_dir / config_dir
        self.logger = logging.getLogger("krai.config")
        self._setup_logging()

        # Configuration cache
        self._configs: dict[str, Any] = {}
        self._last_loaded: dict[str, datetime] = {}

    def _setup_logging(self):
        """Setup logging for config service"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - Config - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _load_config_file(self, filename: str) -> dict[str, Any]:
        """Load configuration file"""
        try:
            config_path = self.config_dir / filename

            if not config_path.exists():
                self.logger.warning(f"Configuration file {filename} not found")
                return {}

            with open(config_path, encoding="utf-8") as f:
                config = cast(dict[str, Any], json.load(f))

            self.logger.info(f"Loaded configuration from {filename}")
            return config

        except Exception as e:
            self.logger.error(f"Failed to load configuration {filename}: {e}")
            return {}

    def get_chunk_settings(self) -> dict[str, Any]:
        """Get text chunking settings"""
        if "chunk_settings" not in self._configs:
            self._configs["chunk_settings"] = self._load_config_file("chunk_settings.json")

        return cast(dict[str, Any], self._configs["chunk_settings"])

    def get_error_code_patterns(self) -> dict[str, Any]:
        """Get error code patterns"""
        if "error_code_patterns" not in self._configs:
            self._configs["error_code_patterns"] = self._load_config_file("error_code_patterns.json")

        return cast(dict[str, Any], self._configs["error_code_patterns"])

    def get_version_patterns(self) -> dict[str, Any]:
        """Get version extraction patterns"""
        if "version_patterns" not in self._configs:
            self._configs["version_patterns"] = self._load_config_file("version_patterns.json")

        return cast(dict[str, Any], self._configs["version_patterns"])

    def get_model_placeholder_patterns(self) -> dict[str, Any]:
        """Get model placeholder patterns"""
        if "model_placeholder_patterns" not in self._configs:
            self._configs["model_placeholder_patterns"] = self._load_config_file("model_placeholder_patterns.json")

        return cast(dict[str, Any], self._configs["model_placeholder_patterns"])

    def get_scraping_config(self) -> dict[str, Any]:
        """Return cached scraping configuration derived from environment variables.

        Example:
            >>> config = config_service.get_scraping_config()
            >>> if config["backend"] == "firecrawl":
            ...     # initialise Firecrawl backend
            ...     pass

        Returns:
            Dict[str, Any]: Normalised scraping configuration.
        """

        if "scraping_config" in self._configs:
            return cast(dict[str, Any], self._configs["scraping_config"])

        def _to_bool(value: str | None, default: bool) -> bool:
            if value is None:
                return default
            return value.lower() in {"1", "true", "yes", "on"}

        backend = os.getenv("SCRAPING_BACKEND", "beautifulsoup").lower()
        firecrawl_api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
        llm_provider = os.getenv("FIRECRAWL_LLM_PROVIDER", "ollama")
        config = {
            "backend": backend,
            "firecrawl_api_url": firecrawl_api_url,
            "firecrawl_llm_provider": llm_provider,
            "firecrawl_model_name": os.getenv("FIRECRAWL_MODEL_NAME", "llama3.2:latest"),
            "firecrawl_embedding_model": os.getenv("FIRECRAWL_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "max_concurrency": int(os.getenv("FIRECRAWL_MAX_CONCURRENCY", "4") or 4),
            "block_media": _to_bool(os.getenv("FIRECRAWL_BLOCK_MEDIA"), True),
            "allow_local_webhooks": _to_bool(os.getenv("FIRECRAWL_ALLOW_LOCAL_WEBHOOKS"), True),
            "proxy_server": os.getenv("FIRECRAWL_PROXY_SERVER"),
            "proxy_username": os.getenv("FIRECRAWL_PROXY_USERNAME"),
            "proxy_password": os.getenv("FIRECRAWL_PROXY_PASSWORD"),
            "scrape_timeout": float(os.getenv("FIRECRAWL_SCRAPE_TIMEOUT", "30.0") or 30.0),
            "crawl_timeout": float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "300.0") or 300.0),
            "retries": int(os.getenv("FIRECRAWL_RETRIES", "3") or 3),
            "enable_link_enrichment": _to_bool(os.getenv("ENABLE_LINK_ENRICHMENT"), False),
            "enable_manufacturer_crawling": _to_bool(os.getenv("ENABLE_MANUFACTURER_CRAWLING"), False),
        }

        if backend == "firecrawl" and not firecrawl_api_url:
            self.logger.warning("Firecrawl backend selected but FIRECRAWL_API_URL is missing; using default")

        self._configs["scraping_config"] = config
        self._last_loaded["scraping_config"] = datetime.utcnow()
        self.logger.info(
            "Loaded scraping configuration: backend=%s, llm_provider=%s",
            backend,
            llm_provider,
        )

        return config

    def get_scraping_backend(self) -> str:
        """Return the active scraping backend name."""

        return cast(str, self.get_scraping_config().get("backend", "beautifulsoup"))

    def is_firecrawl_enabled(self) -> bool:
        """Return True when Firecrawl is the active scraping backend."""

        return self.get_scraping_backend() == "firecrawl"

    def get_chunking_strategy(self, document_type: str, manufacturer: str | None = None) -> dict[str, Any]:
        """
        Get chunking strategy for document type and manufacturer

        Args:
            document_type: Type of document
            manufacturer: Optional manufacturer name

        Returns:
            Chunking strategy configuration
        """
        try:
            chunk_settings = self.get_chunk_settings()

            # Get document type specific settings
            doc_type_settings = chunk_settings.get("chunk_settings", {}).get("document_type_specific", {})
            strategy = doc_type_settings.get(document_type, {})

            # Apply manufacturer specific modifications
            if manufacturer:
                manufacturer_settings = chunk_settings.get("chunk_settings", {}).get("manufacturer_specific", {})
                manufacturer_config = manufacturer_settings.get(manufacturer.lower(), {})

                # Apply manufacturer multiplier
                multiplier = manufacturer_config.get("chunk_size_multiplier", 1.0)
                if "chunk_size" in strategy:
                    strategy["chunk_size"] = int(strategy["chunk_size"] * multiplier)

                # Apply manufacturer preferred strategy
                if "preferred_strategy" in manufacturer_config:
                    strategy["preferred_strategy"] = manufacturer_config["preferred_strategy"]

            # Fallback to default strategy
            if not strategy:
                default_strategy = chunk_settings.get("chunk_settings", {}).get(
                    "default_strategy", "contextual_chunking"
                )
                strategy = {"preferred_strategy": default_strategy, "chunk_size": 1000, "chunk_overlap": 150}

            self.logger.info(
                f"Chunking strategy for {document_type} ({manufacturer}): {strategy.get('preferred_strategy', 'default')}"
            )
            return cast(dict[str, Any], strategy)

        except Exception as e:
            self.logger.error(f"Failed to get chunking strategy: {e}")
            return {"preferred_strategy": "contextual_chunking", "chunk_size": 1000, "chunk_overlap": 150}

    def get_error_patterns_for_manufacturer(self, manufacturer: str) -> dict[str, Any]:
        """
        Get error code patterns for specific manufacturer

        Args:
            manufacturer: Manufacturer name

        Returns:
            Error code patterns for manufacturer
        """
        try:
            error_patterns = self.get_error_code_patterns()
            manufacturer_patterns = error_patterns.get("error_code_patterns", {}).get(manufacturer.lower(), {})

            if not manufacturer_patterns:
                self.logger.warning(f"No error patterns found for manufacturer: {manufacturer}")
                return {}

            self.logger.info(f"Loaded error patterns for {manufacturer}")
            return cast(dict[str, Any], manufacturer_patterns)

        except Exception as e:
            self.logger.error(f"Failed to get error patterns for {manufacturer}: {e}")
            return {}

    def get_version_patterns_for_document(self, document_type: str) -> dict[str, Any]:
        """
        Get version extraction patterns for document type

        Args:
            document_type: Type of document

        Returns:
            Version extraction patterns
        """
        try:
            version_patterns = self.get_version_patterns()
            patterns = version_patterns.get("version_patterns", {})

            # Document type specific patterns
            doc_patterns = patterns.get("document_type_specific", {}).get(document_type, {})

            # Fallback to general patterns
            if not doc_patterns:
                doc_patterns = patterns.get("general", {})

            self.logger.info(f"Loaded version patterns for {document_type}")
            return cast(dict[str, Any], doc_patterns)

        except Exception as e:
            self.logger.error(f"Failed to get version patterns for {document_type}: {e}")
            return {}

    def get_model_placeholder_patterns_for_manufacturer(self, manufacturer: str) -> dict[str, Any]:
        """
        Get model placeholder patterns for manufacturer

        Args:
            manufacturer: Manufacturer name

        Returns:
            Model placeholder patterns
        """
        try:
            placeholder_patterns = self.get_model_placeholder_patterns()
            patterns = placeholder_patterns.get("model_placeholder_patterns", {})

            # Manufacturer specific patterns
            manufacturer_patterns = patterns.get("manufacturer_specific", {}).get(manufacturer.lower(), {})

            # Fallback to general patterns
            if not manufacturer_patterns:
                manufacturer_patterns = patterns.get("general", {})

            self.logger.info(f"Loaded model placeholder patterns for {manufacturer}")
            return cast(dict[str, Any], manufacturer_patterns)

        except Exception as e:
            self.logger.error(f"Failed to get model placeholder patterns for {manufacturer}: {e}")
            return {}

    def reload_configs(self):
        """Reload all configuration files"""
        try:
            self._configs.clear()
            self._last_loaded.clear()

            # Reload all configs
            self.get_chunk_settings()
            self.get_error_code_patterns()
            self.get_version_patterns()
            self.get_model_placeholder_patterns()
            self.get_scraping_config()

            self.logger.info("All configurations reloaded")

        except Exception as e:
            self.logger.error(f"Failed to reload configurations: {e}")
            raise

    def get_config_summary(self) -> dict[str, Any]:
        """Get summary of all loaded configurations"""
        try:
            summary = {
                "chunk_settings": {
                    "loaded": "chunk_settings" in self._configs,
                    "strategies": len(self.get_chunk_settings().get("chunk_settings", {}).get("strategies", {})),
                },
                "error_code_patterns": {
                    "loaded": "error_code_patterns" in self._configs,
                    "manufacturers": len(self.get_error_code_patterns().get("error_code_patterns", {})),
                },
                "version_patterns": {
                    "loaded": "version_patterns" in self._configs,
                    "patterns": len(self.get_version_patterns().get("version_patterns", {})),
                },
                "model_placeholder_patterns": {
                    "loaded": "model_placeholder_patterns" in self._configs,
                    "patterns": len(self.get_model_placeholder_patterns().get("model_placeholder_patterns", {})),
                },
                "scraping_config": {
                    "loaded": "scraping_config" in self._configs,
                    "backend": self.get_scraping_backend(),
                },
            }

            return cast(dict[str, Any], summary)

        except Exception as e:
            self.logger.error(f"Failed to get config summary: {e}")
            return {}

    def health_check(self) -> dict[str, Any]:
        """Perform configuration service health check"""
        try:
            summary = self.get_config_summary()

            all_loaded = all(config["loaded"] for config in summary.values())

            return {
                "status": "healthy" if all_loaded else "degraded",
                "configurations": summary,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
