"""
KRAI Integration Test Configuration
===================================

Pytest configuration and fixtures for integration testing of the complete KRAI pipeline.
This module provides session-scoped fixtures for database, storage, AI services,
and environment isolation to ensure consistent and repeatable integration tests.
"""

import asyncio
import logging
import os
import sys
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

# Add backend root to sys.path using an absolute path so `services.*` imports resolve
backend_root = Path(__file__).resolve().parents[2]
backend_root_str = str(backend_root)
if backend_root_str not in sys.path:
    sys.path.insert(0, backend_root_str)

# Note: ProductResearcher service does not exist yet - tests are prepared for future implementation
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.services.ai_service import AIService
from backend.services.database_adapter import DatabaseAdapter
from backend.services.database_factory import create_database_adapter
from backend.services.link_enrichment_service import LinkEnrichmentService
from backend.services.manufacturer_crawler import ManufacturerCrawler
from backend.services.multimodal_search_service import MultimodalSearchService
from backend.services.object_storage_service import ObjectStorageService
from backend.services.storage_factory import create_storage_service
from backend.services.web_scraping_service import FirecrawlUnavailableError, WebScrapingService

# Test configuration
TEST_CONFIG = {
    "test_db_name": "krai_test",
    "test_buckets": {
        "documents": "test-documents",
        "images": "test-images",
        "videos": "test-videos",
        "tables": "test-tables",
        "temp": "test-temp",
    },
    "cleanup_after_test": True,
    "preserve_test_data": False,
}

# ---------------------------
# Manufacturer crawler fixtures (real-ish scaffold)
# ---------------------------


@pytest.fixture(scope="session")
def firecrawl_available() -> bool:
    """
    Flag indicating whether Firecrawl backend can be used.

    Returns False if SDK missing or env var FIRECRAWL_API_KEY absent.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    api_url = os.getenv("FIRECRAWL_API_URL", "")

    # Check if Firecrawl SDK is available
    try:
        from firecrawl import AsyncFirecrawl
    except ImportError:
        return False

    # Check if API key and URL are configured
    return bool(api_key and api_url)


@pytest.fixture(scope="function")
async def real_manufacturer_crawler(
    test_database: DatabaseAdapter, firecrawl_available: bool
) -> AsyncGenerator[ManufacturerCrawler, None]:
    """
    ManufacturerCrawler with real services where available.

    Uses WebScrapingService (Firecrawl if present, BeautifulSoup fallback) and
    the shared DatabaseService test fixture. BatchTaskService/StructuredExtractionService
    are omitted here to keep the scaffold lightweight; tests can monkeypatch if needed.

    NOTE: ManufacturerCrawler currently expects Supabase client, so we add a compatibility wrapper.
    """

    from backend.services.web_scraping_service import BeautifulSoupBackend, FirecrawlBackend

    # Create backends
    if firecrawl_available:
        try:
            api_url = os.getenv("FIRECRAWL_API_URL", "http://krai-firecrawl-api:3002")
            llm_provider = os.getenv("LLM_PROVIDER", "ollama")
            model_name = os.getenv("MODEL_NAME", "llama3.2:latest")
            embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
            timeout = float(os.getenv("FIRECRAWL_TIMEOUT", "30.0"))
            crawl_timeout = float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "300.0"))

            primary = FirecrawlBackend(
                api_url=api_url,
                llm_provider=llm_provider,
                model_name=model_name,
                embedding_model=embedding_model,
                timeout=timeout,
                crawl_timeout=crawl_timeout,
                mock_mode=False,
            )
        except Exception:
            primary = BeautifulSoupBackend(mock_mode=False)
    else:
        primary = BeautifulSoupBackend(mock_mode=False)

    fallback = BeautifulSoupBackend(mock_mode=False)

    web_scraping = WebScrapingService(
        primary_backend=primary,
        fallback_backend=fallback,
    )

    # ManufacturerCrawler now uses DatabaseService directly (no Supabase wrapper needed!)
    crawler = ManufacturerCrawler(
        web_scraping_service=web_scraping,
        database_service=test_database,
    )
    crawler._enabled = True
    yield crawler


@pytest.fixture
async def test_manufacturer_data(test_database: DatabaseAdapter):
    """
    Provide a unique manufacturer_id for isolation and ensure base records exist if needed.
    """
    manufacturer_id = f"mfr-{uuid.uuid4().hex[:8]}"
    yield {"manufacturer_id": manufacturer_id}


@pytest.fixture(autouse=True)
async def cleanup_crawler_data(test_database: DatabaseAdapter):
    """
    Cleanup manufacturer crawler data after each test to maintain isolation.
    """
    yield
    try:
        await test_database.execute_query("DELETE FROM krai_system.manufacturer_crawl_jobs")
        await test_database.execute_query("DELETE FROM krai_system.manufacturer_crawl_schedules")
        await test_database.execute_query("DELETE FROM krai_system.crawled_pages")
    except Exception as exc:
        logging.warning(f"Failed to cleanup manufacturer crawler tables: {exc}")


@pytest.fixture(scope="session")
def test_crawl_urls() -> dict[str, str]:
    """
    Provide simple publicly reachable URLs for smoke crawls.
    """
    return {
        "example": "https://example.com",
        "httpbin": "https://httpbin.org/html",
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_database() -> AsyncGenerator[DatabaseAdapter, None]:
    """
    Session-scoped database fixture for integration tests.

    Provides a clean database connection with test schema isolation.
    Automatically handles setup and teardown of test database.
    """
    # Load test environment
    from dotenv import load_dotenv

    test_env_path = Path(__file__).parent.parent.parent / ".env.test"
    if test_env_path.exists():
        load_dotenv(test_env_path)
    else:
        load_dotenv()  # Fallback to main .env

    # Initialize database service
    database_service = create_database_adapter()

    try:
        # Connect to test database
        await database_service.connect()

        # Verify test database schema
        schemas = await database_service.execute_query(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'krai_%'"
        )

        if not schemas:
            pytest.skip("No KRAI schemas found in test database")

        logging.info(f"Connected to test database with schemas: {[s['schema_name'] for s in schemas]}")

        yield database_service

    except Exception as e:
        pytest.fail(f"Failed to setup test database: {e}")

    finally:
        # Cleanup test data if enabled
        if TEST_CONFIG["cleanup_after_test"]:
            await _cleanup_test_data(database_service)

        await database_service.disconnect()


@pytest.fixture(scope="function")
async def test_storage() -> AsyncGenerator[ObjectStorageService, None]:
    """
    Session-scoped storage fixture for integration tests.

    Provides isolated storage buckets for test files.
    Automatically creates test buckets and cleans them up after tests.
    """
    # Initialize storage service
    storage_service = create_storage_service()

    try:
        await storage_service.connect()

        # Create test buckets
        for bucket_type, bucket_name in TEST_CONFIG["test_buckets"].items():
            try:
                await storage_service.create_bucket(bucket_name)
                logging.info(f"Created test bucket: {bucket_name}")
            except Exception as e:
                # Bucket might already exist
                logging.warning(f"Test bucket {bucket_name} already exists or failed to create: {e}")

        yield storage_service

    except Exception as e:
        pytest.fail(f"Failed to setup test storage: {e}")

    finally:
        # Cleanup test buckets if enabled
        if TEST_CONFIG["cleanup_after_test"]:
            await _cleanup_test_buckets(storage_service)

        await storage_service.disconnect()


@pytest.fixture(scope="function")
async def test_ai_service() -> AsyncGenerator[AIService, None]:
    """
    Session-scoped AI service fixture for integration tests.

    Provides AI service connection for embedding generation and LLM calls.
    Uses test configuration to avoid affecting production metrics.
    """
    ai_service = AIService()

    try:
        await ai_service.connect()

        # Test basic embedding generation
        test_embedding = await ai_service.generate_embeddings("test query")
        if not test_embedding:
            pytest.fail("AI service failed to generate test embedding")

        logging.info("AI service connected and tested successfully")

        yield ai_service

    except Exception as e:
        pytest.fail(f"Failed to setup test AI service: {e}")

    finally:
        await ai_service.disconnect()


@pytest.fixture(scope="function")
async def test_pipeline(
    test_database: DatabaseAdapter, test_storage: ObjectStorageService, test_ai_service: AIService
) -> AsyncGenerator[KRMasterPipeline, None]:
    """
    Session-scoped pipeline fixture for integration tests.

    Provides fully initialized master pipeline with test services.
    Ready for end-to-end processing tests.
    """
    pipeline = KRMasterPipeline()

    try:
        # Initialize pipeline with test services
        await pipeline.initialize_services()

        logging.info("Master pipeline initialized for integration tests")

        yield pipeline

    except Exception as e:
        pytest.fail(f"Failed to setup test pipeline: {e}")


@pytest.fixture(scope="function")
async def test_search_service(
    test_database: DatabaseAdapter, test_ai_service: AIService
) -> AsyncGenerator[MultimodalSearchService, None]:
    """
    Session-scoped search service fixture for integration tests.

    Provides multimodal search service with test database and AI services.
    """
    search_service = MultimodalSearchService(
        database_service=test_database, ai_service=test_ai_service, default_threshold=0.5, default_limit=10
    )

    yield search_service


@pytest.fixture
def sample_test_document() -> dict[str, Any]:
    """
    Fixture providing sample test document data.

    Returns a dictionary with test document metadata for processing tests.
    """
    return {
        "filename": "test_manual.pdf",
        "file_path": str(Path(__file__).parent.parent.parent / "service_documents" / "test_manual.pdf"),
        "file_size": 1024000,  # 1MB
        "document_type": "service_manual",
        "manufacturer": "TestCorp",
        "model": "C4080",
        "language": "en",
    }


@pytest.fixture
def temporary_test_file() -> Generator[Path, None, None]:
    """
    Fixture providing a temporary file for test operations.

    Creates a temporary file that is automatically cleaned up after the test.
    """
    with TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / f"test_file_{uuid.uuid4().hex}.txt"
        temp_file.write_text("This is a test file for integration testing.")
        yield temp_file


@pytest.fixture
def test_queries() -> dict[str, list]:
    """
    Fixture providing test queries for search functionality.

    Returns categorized test queries for different search scenarios.
    """
    return {
        "error_codes": ["error 900.01", "error 900.02", "error 920.00"],
        "components": ["fuser unit", "paper tray", "toner cartridge"],
        "procedures": ["maintenance procedures", "installation guide", "troubleshooting"],
        "general": ["technical specifications", "user manual", "warranty information"],
    }


async def _cleanup_test_data(database_service: DatabaseAdapter):
    """Clean up test data from database."""
    try:
        # Clean up test documents
        await database_service.execute_query("DELETE FROM krai_core.documents WHERE filename LIKE 'test_%'")

        # Clean up test chunks
        await database_service.execute_query(
            "DELETE FROM krai_intelligence.chunks WHERE document_id IN "
            "(SELECT id FROM krai_core.documents WHERE filename LIKE 'test_%')"
        )

        # Clean up test embeddings
        await database_service.execute_query(
            "DELETE FROM krai_intelligence.embeddings_v2 WHERE document_id IN "
            "(SELECT id FROM krai_core.documents WHERE filename LIKE 'test_%')"
        )

        logging.info("Test data cleanup completed")

    except Exception as e:
        logging.warning(f"Test data cleanup failed: {e}")


async def _cleanup_test_buckets(storage_service: ObjectStorageService):
    """Clean up test storage buckets."""
    try:
        for bucket_name in TEST_CONFIG["test_buckets"].values():
            try:
                # List and delete all objects in bucket
                objects = await storage_service.list_objects(bucket_name)
                for obj in objects:
                    await storage_service.delete_object(bucket_name, obj["name"])

                # Delete bucket
                await storage_service.delete_bucket(bucket_name)
                logging.info(f"Cleaned up test bucket: {bucket_name}")

            except Exception as e:
                logging.warning(f"Failed to cleanup test bucket {bucket_name}: {e}")

    except Exception as e:
        logging.warning(f"Test bucket cleanup failed: {e}")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "database: mark test as requiring database")
    config.addinivalue_line("markers", "storage: mark test as requiring storage")


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all tests."""
    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"

    yield

    # Cleanup environment variables
    os.environ.pop("TESTING", None)
    os.environ.pop("LOG_LEVEL", None)


# ---------------------------
# Real Service Fixtures for Link Enrichment & Product Research
# ---------------------------


@pytest.fixture
async def real_link_enrichment_service(
    test_database: DatabaseAdapter, firecrawl_available: bool
) -> AsyncGenerator[LinkEnrichmentService, None]:
    """
    Real LinkEnrichmentService with live WebScrapingService backend.

    Uses Firecrawl if available, otherwise falls back to BeautifulSoup.
    Provides full integration testing with actual scraping operations.
    """
    from backend.services.web_scraping_service import BeautifulSoupBackend, FirecrawlBackend

    # Create backends
    if firecrawl_available:
        try:
            api_url = os.getenv("FIRECRAWL_API_URL", "http://krai-firecrawl-api:3002")
            llm_provider = os.getenv("LLM_PROVIDER", "ollama")
            model_name = os.getenv("MODEL_NAME", "llama3.2:latest")
            embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
            timeout = float(os.getenv("FIRECRAWL_TIMEOUT", "30.0"))
            crawl_timeout = float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "300.0"))

            primary = FirecrawlBackend(
                api_url=api_url,
                llm_provider=llm_provider,
                model_name=model_name,
                embedding_model=embedding_model,
                timeout=timeout,
                crawl_timeout=crawl_timeout,
                mock_mode=False,
            )
        except Exception:
            primary = BeautifulSoupBackend(mock_mode=False)
    else:
        primary = BeautifulSoupBackend(mock_mode=False)

    fallback = BeautifulSoupBackend(mock_mode=False)

    web_scraping = WebScrapingService(
        primary_backend=primary,
        fallback_backend=fallback,
    )

    service = LinkEnrichmentService(database_service=test_database, web_scraping_service=web_scraping)

    yield service


@pytest.fixture
async def real_product_researcher(
    test_database: DatabaseAdapter, firecrawl_available: bool
) -> AsyncGenerator["ProductResearcher", None]:
    """
    Real ProductResearcher with live scraping and LLM backend.

    Uses real WebScrapingService and Ollama for LLM analysis.
    Provides full integration testing of product research workflows.
    """
    from backend.services.product_researcher import ProductResearcher
    from backend.services.web_scraping_service import BeautifulSoupBackend, FirecrawlBackend

    # Create backends
    if firecrawl_available:
        try:
            api_url = os.getenv("FIRECRAWL_API_URL", "http://krai-firecrawl-api:3002")
            llm_provider = os.getenv("LLM_PROVIDER", "ollama")
            model_name = os.getenv("MODEL_NAME", "llama3.2:latest")
            embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
            timeout = float(os.getenv("FIRECRAWL_TIMEOUT", "30.0"))
            crawl_timeout = float(os.getenv("FIRECRAWL_CRAWL_TIMEOUT", "300.0"))

            primary = FirecrawlBackend(
                api_url=api_url,
                llm_provider=llm_provider,
                model_name=model_name,
                embedding_model=embedding_model,
                timeout=timeout,
                crawl_timeout=crawl_timeout,
                mock_mode=False,
            )
        except Exception:
            primary = BeautifulSoupBackend(mock_mode=False)
    else:
        primary = BeautifulSoupBackend(mock_mode=False)

    fallback = BeautifulSoupBackend(mock_mode=False)

    web_scraping = WebScrapingService(
        primary_backend=primary,
        fallback_backend=fallback,
    )

    ollama_url = os.getenv("OLLAMA_URL", "http://krai-ollama:11434")

    researcher = ProductResearcher(
        database_service=test_database, web_scraping_service=web_scraping, ollama_url=ollama_url
    )

    yield researcher


@pytest.fixture
async def test_link_data(test_database: DatabaseAdapter):
    """
    Factory fixture for creating test links in database.

    Returns a callable that creates a link record with unique ID.
    Automatically tracks created links for cleanup.
    """
    created_links = []

    async def create_link(
        url: str,
        manufacturer_id: str | None = None,
        document_id: str | None = None,
        scrape_status: str = "pending",
    ):
        """Create a test scraping job in database."""
        link_id = str(uuid.uuid4())  # Generate proper UUID

        # Use link_scraping_jobs table (separate from manual links)
        query = """
            INSERT INTO krai_system.link_scraping_jobs (id, url, manufacturer_id, document_id, scrape_status, created_at)
            VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5, NOW())
            RETURNING *
        """

        result = await test_database.execute_query(query, (link_id, url, manufacturer_id, document_id, scrape_status))

        created_links.append(link_id)
        return result[0] if result else None

    yield create_link

    # Cleanup created scraping jobs
    if created_links:
        placeholders = ", ".join([f"${i+1}::uuid" for i in range(len(created_links))])
        await test_database.execute_query(
            f"DELETE FROM krai_system.link_scraping_jobs WHERE id IN ({placeholders})", tuple(created_links)
        )


@pytest.fixture
async def test_crawled_page_data(test_database: DatabaseAdapter):
    """
    Factory fixture for creating test crawled pages in database.

    Returns a callable that creates a crawled page record.
    Automatically tracks created pages for cleanup.
    """
    created_pages = []

    async def create_page(url: str, content: str, manufacturer_id: str | None = None) -> dict[str, Any]:
        page_id = f"test-page-{uuid.uuid4().hex[:12]}"

        query = """
            INSERT INTO krai_system.crawled_pages (id, url, content, manufacturer_id, crawled_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING *
        """

        result = await test_database.execute_query(query, (page_id, url, content, manufacturer_id))

        created_pages.append(page_id)
        return result[0] if result else None

    yield create_page

    # Cleanup created pages
    if created_pages:
        placeholders = ", ".join([f"${i+1}" for i in range(len(created_pages))])
        await test_database.execute_query(
            f"DELETE FROM krai_system.crawled_pages WHERE id IN ({placeholders})", tuple(created_pages)
        )


@pytest.fixture(autouse=True)
async def cleanup_link_enrichment_data(test_database: DatabaseAdapter):
    """
    Autouse fixture to cleanup link enrichment test data after each test.

    Removes test links, enrichment data, and related records to maintain isolation.
    """
    yield

    try:
        # Cleanup is handled by individual fixtures
        pass

        # Cleanup test crawled pages
        await test_database.execute_query("DELETE FROM krai_system.crawled_pages WHERE id LIKE 'test-page-%'")

        logging.info("Link enrichment test data cleanup completed")

    except Exception as exc:
        logging.warning(f"Failed to cleanup link enrichment data: {exc}")


# ---------------------------
# Helper Functions for Integration Tests
# ---------------------------


async def create_test_link(
    database: DatabaseAdapter, url: str, manufacturer_id: str | None = None, document_id: str | None = None
) -> str:
    """
    Helper to create a test link record in database.

    Args:
        database: DatabaseAdapter instance
        url: URL to create link for
        manufacturer_id: Optional manufacturer ID
        document_id: Optional document ID

    Returns:
        Created link ID
    """
    link_id = str(uuid.uuid4())  # Generate proper UUID

    # Use link_scraping_jobs table
    query = """
        INSERT INTO krai_system.link_scraping_jobs (id, url, manufacturer_id, document_id, scrape_status, created_at)
        VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5, NOW())
        RETURNING id
    """

    result = await database.execute_query(query, (link_id, url, manufacturer_id, document_id, "pending"))

    return result[0]["id"] if result else None


async def wait_for_enrichment(
    database: DatabaseAdapter, link_id: str, timeout: int = 30, check_interval: float = 0.5
) -> bool:
    """
    Wait for link enrichment to complete.

    Args:
        database: DatabaseAdapter instance
        link_id: Link ID to wait for
        timeout: Maximum wait time in seconds
        check_interval: Time between status checks in seconds

    Returns:
        True if enrichment completed successfully, False on timeout
    """
    import time

    start_time = time.time()

    while time.time() - start_time < timeout:
        query = "SELECT scrape_status FROM krai_system.link_scraping_jobs WHERE id = $1::uuid"
        result = await database.execute_query(query, (link_id,))

        if result and result[0]["scrape_status"] in ("success", "failed"):
            return True

        await asyncio.sleep(check_interval)

    return False


async def verify_link_enrichment(database: DatabaseAdapter, link_id: str) -> dict[str, Any]:
    """
    Verify link enrichment data quality.

    Args:
        database: DatabaseAdapter instance
        link_id: Link ID to verify

    Returns:
        Dictionary with verification results
    """
    query = """
        SELECT
            scrape_status,
            scraped_content,
            content_hash,
            scraped_metadata,
            scrape_error,
            scraped_at
        FROM krai_system.link_scraping_jobs
        WHERE id = $1::uuid
    """

    result = await database.execute_query(query, (link_id,))

    if not result:
        return {"valid": False, "error": "Link not found"}

    link = result[0]

    verification = {
        "valid": True,
        "status": link["scrape_status"],
        "has_content": bool(link["scraped_content"]),
        "content_length": len(link["scraped_content"]) if link["scraped_content"] else 0,
        "has_hash": bool(link["content_hash"]),
        "has_metadata": bool(link["scraped_metadata"]),
        "has_error": bool(link["scrape_error"]),
        "scraped_at": link["scraped_at"],
    }

    # Quality checks
    if link["scrape_status"] == "success":
        verification["quality_checks"] = {
            "content_not_empty": verification["content_length"] > 100,
            "hash_present": verification["has_hash"],
            "metadata_present": verification["has_metadata"],
            "no_error": not verification["has_error"],
        }

    return verification


from contextlib import asynccontextmanager


@asynccontextmanager
async def simulate_firecrawl_failure(service: LinkEnrichmentService):
    """
    Context manager to simulate Firecrawl service failure.

    Temporarily replaces scrape_url method to raise FirecrawlUnavailableError.
    Automatically restores original method on exit.

    Usage:
        async with simulate_firecrawl_failure(service):
            # Firecrawl will fail, triggering fallback
            await service.enrich_link(link_id)
    """
    original_scrape = service._web_scraping_service.scrape_url

    async def failing_scrape(url: str, options: dict | None = None):
        raise FirecrawlUnavailableError("Simulated Firecrawl failure for testing")

    service._web_scraping_service.scrape_url = failing_scrape

    try:
        yield
    finally:
        service._web_scraping_service.scrape_url = original_scrape
