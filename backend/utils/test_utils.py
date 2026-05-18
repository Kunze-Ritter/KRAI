#!/usr/bin/env python3
"""
KRAI Test Utilities - Public Test Hooks

This module provides public utility functions and test hooks to replace
private method usage in test scripts. All functions are designed to be
test-friendly and provide controlled access to internal functionality.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.base_processor import ProcessingContext
from pipeline.master_pipeline import KRMasterPipeline
from services.ai_service import AIService
from services.config_service import ConfigService
from services.context_extraction_service import ContextExtractionService
from services.database_service_production import DatabaseService
from services.features_service import FeaturesService
from services.multimodal_search_service import MultimodalSearchService
from services.quality_check_service import QualityCheckService
from services.storage_factory import create_storage_service

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TestDocument:
    """Test document data structure"""

    filename: str
    file_path: str
    file_size: int
    document_type: str = "pdf"
    manufacturer: str | None = None
    product_code: str | None = None


@dataclass
class TestEnvironment:
    """Test environment configuration"""

    database_url: str
    storage_endpoint: str
    storage_access_key: str
    storage_secret_key: str
    ai_service_url: str
    test_mode: bool = True


class TestServiceManager:
    """Manage test services with proper isolation and cleanup"""

    def __init__(self, environment: TestEnvironment):
        self.environment = environment
        self.database_service = None
        self.storage_service = None
        self.ai_service = None
        self.pipeline = None
        self.context_service = None
        self.search_service = None
        self.config_service = None
        self.features_service = None
        self.quality_service = None

    async def initialize_all_services(self) -> bool:
        """Initialize all KRAI services for testing"""
        try:
            logger.info("🔧 Initializing test services...")

            # Initialize database service
            self.database_service = DatabaseService()
            await self.database_service.initialize()

            # Initialize storage service
            self.storage_service = create_storage_service(
                endpoint=self.environment.storage_endpoint,
                access_key=self.environment.storage_access_key,
                secret_key=self.environment.storage_secret_key,
                secure=False,
            )
            await self.storage_service.initialize()

            # Initialize AI service
            self.ai_service = AIService()
            await self.ai_service.initialize()

            # Initialize config service
            self.config_service = ConfigService()
            await self.config_service.initialize()

            # Initialize features service
            self.features_service = FeaturesService()
            await self.features_service.initialize()

            # Initialize quality check service
            self.quality_service = QualityCheckService()
            await self.quality_service.initialize()

            # Initialize context extraction service
            self.context_service = ContextExtractionService(self.ai_service, self.database_service)
            await self.context_service.initialize()

            # Initialize multimodal search service
            self.search_service = MultimodalSearchService(self.database_service, self.ai_service)
            await self.search_service.initialize()

            # Initialize master pipeline
            self.pipeline = KRMasterPipeline()
            await self.pipeline.initialize()

            logger.info("✅ All test services initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize test services: {e}")
            return False

    async def cleanup_all_services(self) -> bool:
        """Cleanup all test services"""
        try:
            logger.info("🧹 Cleaning up test services...")

            if self.pipeline:
                await self.pipeline.cleanup()

            if self.search_service:
                await self.search_service.cleanup()

            if self.context_service:
                await self.context_service.cleanup()

            if self.quality_service:
                await self.quality_service.cleanup()

            if self.features_service:
                await self.features_service.cleanup()

            if self.config_service:
                await self.config_service.cleanup()

            if self.ai_service:
                await self.ai_service.cleanup()

            if self.storage_service:
                await self.storage_service.cleanup()

            if self.database_service:
                await self.database_service.cleanup()

            logger.info("✅ All test services cleaned up successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to cleanup test services: {e}")
            return False

    def get_service(self, service_name: str):
        """Get a specific service instance"""
        service_map = {
            "database": self.database_service,
            "storage": self.storage_service,
            "ai": self.ai_service,
            "pipeline": self.pipeline,
            "context": self.context_service,
            "search": self.search_service,
            "config": self.config_service,
            "features": self.features_service,
            "quality": self.quality_service,
        }
        return service_map.get(service_name)


class TestDocumentManager:
    """Manage test documents for testing"""

    def __init__(self, service_manager: TestServiceManager):
        self.service_manager = service_manager
        self.test_documents: list[TestDocument] = []

    async def prepare_test_documents(
        self, documents_dir: str = "service_documents", file_pattern: str = "*.pdf"
    ) -> list[TestDocument]:
        """
        Prepare test documents from directory

        Args:
            documents_dir: Directory containing test documents
            file_pattern: File pattern to match (default: *.pdf)

        Returns:
            List of prepared test documents
        """
        try:
            docs_path = Path(documents_dir)

            if not docs_path.exists():
                logger.warning(f"Documents directory does not exist: {documents_dir}")
                logger.info(f"Creating directory: {documents_dir}")
                docs_path.mkdir(parents=True, exist_ok=True)
                return []

            # Find matching files
            files = list(docs_path.glob(file_pattern))

            if not files:
                logger.warning(f"No files found matching pattern '{file_pattern}' in {documents_dir}")
                return []

            # Prepare test documents
            self.test_documents = []
            for file_path in files:
                test_doc = TestDocument(
                    filename=file_path.name,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size,
                    document_type=file_path.suffix.lower().lstrip("."),
                )
                self.test_documents.append(test_doc)

            logger.info(f"📄 Prepared {len(self.test_documents)} test documents")
            return self.test_documents

        except Exception as e:
            logger.error(f"❌ Failed to prepare test documents: {e}")
            return []

    async def upload_test_document(self, test_doc: TestDocument, bucket: str = "documents") -> str | None:
        """
        Upload a test document to storage

        Args:
            test_doc: Test document to upload
            bucket: Storage bucket name

        Returns:
            Storage path if successful, None otherwise
        """
        try:
            storage_service = self.service_manager.get_service("storage")
            if not storage_service:
                raise ValueError("Storage service not available")

            # Read file content
            with open(test_doc.file_path, "rb") as f:
                file_content = f.read()

            # Generate unique storage path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            storage_path = f"test/{timestamp}_{test_doc.filename}"

            # Upload to storage
            await storage_service.upload_file(
                bucket=bucket,
                file_path=storage_path,
                content=file_content,
                content_type=f"application/{test_doc.document_type}",
            )

            logger.info(f"📤 Uploaded test document: {storage_path}")
            return storage_path

        except Exception as e:
            logger.error(f"❌ Failed to upload test document: {e}")
            return None

    async def create_document_record(self, test_doc: TestDocument, storage_path: str) -> int | None:
        """
        Create document record in database

        Args:
            test_doc: Test document
            storage_path: Storage path from upload

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            database_service = self.service_manager.get_service("database")
            if not database_service:
                raise ValueError("Database service not available")

            # Insert document record
            query = """
                INSERT INTO krai_core.documents (
                    filename, original_filename, storage_path,
                    file_size, document_type, manufacturer,
                    product_code, status, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                RETURNING id
            """

            params = [
                test_doc.filename,
                test_doc.filename,
                storage_path,
                test_doc.file_size,
                test_doc.document_type,
                test_doc.manufacturer,
                test_doc.product_code,
                "uploaded",
            ]

            result = await database_service.fetch_query(query, params)

            if result and len(result) > 0:
                document_id = result[0]["id"]
                logger.info(f"📋 Created document record: {document_id}")
                return document_id
            logger.error("❌ Failed to create document record")
            return None

        except Exception as e:
            logger.error(f"❌ Failed to create document record: {e}")
            return None


class TestPipelineRunner:
    """Run pipeline tests with proper isolation"""

    def __init__(self, service_manager: TestServiceManager):
        self.service_manager = service_manager
        self.document_manager = TestDocumentManager(service_manager)

    async def run_document_processing(
        self, document_id: int, processing_options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run document processing pipeline

        Args:
            document_id: Document ID to process
            processing_options: Optional processing parameters

        Returns:
            Processing results
        """
        try:
            pipeline = self.service_manager.get_service("pipeline")
            if not pipeline:
                raise ValueError("Pipeline service not available")

            # Create processing context
            context = ProcessingContext(document_id=document_id, options=processing_options or {})

            # Run pipeline
            logger.info(f"🔄 Starting document processing for document {document_id}")
            result = await pipeline.process_document(context)

            logger.info(f"✅ Document processing completed for document {document_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Document processing failed: {e}")
            return {"success": False, "error": str(e)}

    async def run_multimodal_search(
        self, query: str, search_options: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Run multimodal search

        Args:
            query: Search query
            search_options: Optional search parameters

        Returns:
            Search results
        """
        try:
            search_service = self.service_manager.get_service("search")
            if not search_service:
                raise ValueError("Search service not available")

            # Default search options
            options = {"limit": 10, "threshold": 0.5, "include_content": True}
            options.update(search_options or {})

            # Run search
            logger.info(f"🔍 Running multimodal search: '{query}'")
            results = await search_service.search(query, options)

            logger.info(f"✅ Search completed: {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"❌ Multimodal search failed: {e}")
            return []


class TestDataValidator:
    """Validate test data and results"""

    @staticmethod
    def validate_test_document(test_doc: TestDocument) -> tuple[bool, list[str]]:
        """
        Validate test document

        Args:
            test_doc: Test document to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check file exists
        if not Path(test_doc.file_path).exists():
            errors.append(f"File does not exist: {test_doc.file_path}")

        # Check file size
        if test_doc.file_size <= 0:
            errors.append(f"Invalid file size: {test_doc.file_size}")

        # Check filename
        if not test_doc.filename:
            errors.append("Filename is empty")

        # Check document type
        valid_types = ["pdf", "docx", "txt", "html"]
        if test_doc.document_type not in valid_types:
            errors.append(f"Unsupported document type: {test_doc.document_type}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_processing_result(result: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate processing result

        Args:
            result: Processing result to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check result structure
        if not isinstance(result, dict):
            errors.append("Result is not a dictionary")
            return False, errors

        # Check success flag
        if "success" not in result:
            errors.append("Missing 'success' field in result")

        # Check for errors
        if result.get("success") and "error" in result:
            errors.append("Successful result should not contain error")

        if not result.get("success") and "error" not in result:
            errors.append("Failed result should contain error message")

        return len(errors) == 0, errors


class TestReporter:
    """Generate test reports"""

    def __init__(self, output_dir: str = "test_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_test_report(self, test_results: list[dict[str, Any]], report_name: str = "test_report") -> str:
        """
        Generate comprehensive test report

        Args:
            test_results: List of test results
            report_name: Name of the report

        Returns:
            Path to generated report file
        """
        try:
            # Calculate summary statistics
            total_tests = len(test_results)
            successful_tests = sum(1 for r in test_results if r.get("success", False))
            failed_tests = total_tests - successful_tests
            success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0

            # Create report structure
            report = {
                "report_metadata": {
                    "name": report_name,
                    "generated_at": datetime.now().isoformat(),
                    "total_tests": total_tests,
                    "successful_tests": successful_tests,
                    "failed_tests": failed_tests,
                    "success_rate": round(success_rate, 2),
                },
                "test_results": test_results,
                "summary": {
                    "passed_tests": [r for r in test_results if r.get("success", False)],
                    "failed_tests": [r for r in test_results if not r.get("success", False)],
                },
            }

            # Save report
            report_file = self.output_dir / f"{report_name}.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"📊 Test report generated: {report_file}")
            return str(report_file)

        except Exception as e:
            logger.error(f"❌ Failed to generate test report: {e}")
            return ""


# Public factory functions for easy access
def create_test_environment() -> TestEnvironment:
    """Create test environment from configuration"""
    return TestEnvironment(
        database_url=os.getenv("DATABASE_URL", "postgresql://localhost:5432/krai_test"),
        storage_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        storage_access_key=os.getenv("MINIO_ACCESS_KEY", "test_access_key"),
        storage_secret_key=os.getenv("MINIO_SECRET_KEY", "test_secret_key"),
        ai_service_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        test_mode=os.getenv("TESTING", "true").lower() == "true",
    )


def create_test_service_manager(environment: TestEnvironment | None = None) -> TestServiceManager:
    """Create test service manager"""
    if environment is None:
        environment = create_test_environment()
    return TestServiceManager(environment)


async def setup_test_environment() -> TestServiceManager:
    """Setup complete test environment"""
    environment = create_test_environment()
    service_manager = create_test_service_manager(environment)

    success = await service_manager.initialize_all_services()
    if not success:
        raise RuntimeError("Failed to setup test environment")

    return service_manager


# Utility functions for common test operations
async def upload_and_process_document(test_doc: TestDocument, service_manager: TestServiceManager) -> dict[str, Any]:
    """
    Upload and process a test document

    Args:
        test_doc: Test document to process
        service_manager: Test service manager

    Returns:
        Processing results
    """
    document_manager = TestDocumentManager(service_manager)
    pipeline_runner = TestPipelineRunner(service_manager)

    # Upload document
    storage_path = await document_manager.upload_test_document(test_doc)
    if not storage_path:
        return {"success": False, "error": "Failed to upload document"}

    # Create document record
    document_id = await document_manager.create_document_record(test_doc, storage_path)
    if not document_id:
        return {"success": False, "error": "Failed to create document record"}

    # Process document
    result = await pipeline_runner.run_document_processing(document_id)
    result["document_id"] = document_id
    result["storage_path"] = storage_path

    return result


async def run_search_test(
    query: str, service_manager: TestServiceManager, search_options: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Run search test

    Args:
        query: Search query
        service_manager: Test service manager
        search_options: Optional search parameters

    Returns:
        Search results
    """
    pipeline_runner = TestPipelineRunner(service_manager)
    results = await pipeline_runner.run_multimodal_search(query, search_options)

    return {"success": True, "query": query, "results_count": len(results), "results": results}
