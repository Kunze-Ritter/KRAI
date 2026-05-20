"""
Test Pipeline Imports and Initialization

Validates that all pipeline stages can be imported and initialized correctly.
Ensures no ImportError occurs at runtime.
"""

import pytest

pytestmark = pytest.mark.filterwarnings(
    "ignore:PydanticDeprecatedSince20:DeprecationWarning",
    "ignore:.*SwigPy.*:DeprecationWarning",
)
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestPipelineImports:
    """Test that pipeline can import all required processors"""

    def test_import_master_pipeline(self):
        """Test that master_pipeline.py can be imported without errors"""
        try:
            from backend.pipeline import master_pipeline

            assert master_pipeline is not None
        except ImportError as e:
            pytest.fail(f"Failed to import master_pipeline: {e}")

    def test_import_smart_processor(self):
        """Test that smart_processor.py can be imported without errors"""
        try:
            from backend.pipeline import smart_processor

            assert smart_processor is not None
        except ImportError as e:
            pytest.fail(f"Failed to import smart_processor: {e}")

    def test_import_all_processors(self):
        """Test that all processor modules can be imported"""
        processors_to_test = [
            "upload_processor",
            "text_processor_optimized",
            "image_processor",
            "classification_processor",
            "chunk_preprocessor",
            "metadata_processor_ai",
            "link_extraction_processor_ai",
            "storage_processor",
            "embedding_processor",
            "search_processor",
        ]

        for processor_name in processors_to_test:
            try:
                module = __import__(f"backend.processors.{processor_name}", fromlist=[processor_name])
                assert module is not None, f"Module {processor_name} is None"
            except ImportError as e:
                pytest.fail(f"Failed to import {processor_name}: {e}")


class TestPipelineInitialization:
    """Test that pipeline can be initialized with mocked services"""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing"""
        mock_db = Mock()
        mock_db.connect = AsyncMock()
        mock_db.client = Mock()
        mock_db.client.table = Mock(return_value=Mock())

        mock_storage = Mock()
        mock_storage.connect = AsyncMock()

        mock_ai = Mock()
        mock_ai.connect = AsyncMock()

        mock_config = Mock()
        mock_features = Mock()

        return {
            "database": mock_db,
            "storage": mock_storage,
            "ai": mock_ai,
            "config": mock_config,
            "features": mock_features,
        }

    @pytest.mark.asyncio
    async def test_master_pipeline_initialization(self, mock_services):
        """Test that KRMasterPipeline can be initialized with mocked services"""
        from backend.pipeline.master_pipeline import KRMasterPipeline

        # Mock environment variables
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "http://localhost:54321",
                "SUPABASE_ANON_KEY": "test_key",
                "SUPABASE_SERVICE_ROLE_KEY": "test_service_key",
                "POSTGRES_URL": "postgresql://test",
                "OBJECT_STORAGE_ACCESS_KEY": "test",
                "OBJECT_STORAGE_SECRET_KEY": "test",
                "OBJECT_STORAGE_ENDPOINT": "http://test",
                "OBJECT_STORAGE_TYPE": "s3",
                "UPLOAD_IMAGES_TO_STORAGE": "true",
                "UPLOAD_DOCUMENTS_TO_STORAGE": "true",
                "OLLAMA_URL": "http://localhost:11434",
            },
        ):
            # Mock service classes
            with (
                patch("backend.pipeline.master_pipeline.DatabaseService") as MockDB,
                patch("backend.pipeline.master_pipeline.ObjectStorageService") as MockStorage,
                patch("backend.pipeline.master_pipeline.AIService") as MockAI,
                patch("backend.pipeline.master_pipeline.ConfigService") as MockConfig,
                patch("backend.pipeline.master_pipeline.FeaturesService") as MockFeatures,
                patch("backend.pipeline.master_pipeline.QualityCheckService") as MockQuality,
                patch("backend.pipeline.master_pipeline.FileLocatorService") as MockLocator,
                patch("backend.pipeline.master_pipeline.load_dotenv"),
            ):
                # Configure mocks
                MockDB.return_value = mock_services["database"]
                MockStorage.return_value = mock_services["storage"]
                MockAI.return_value = mock_services["ai"]
                MockConfig.return_value = mock_services["config"]
                MockFeatures.return_value = mock_services["features"]
                MockQuality.return_value = Mock()
                MockLocator.return_value = Mock()

                # Create pipeline instance
                pipeline = KRMasterPipeline()

                # Initialize services
                await pipeline.initialize_services()

                # Verify processors are initialized
                assert pipeline.processors is not None
                assert isinstance(pipeline.processors, dict)

                # Verify expected processor keys
                expected_keys = [
                    "upload",
                    "text",
                    "image",
                    "classification",
                    "chunk_prep",
                    "links",
                    "metadata",
                    "storage",
                    "embedding",
                    "search",
                ]

                for key in expected_keys:
                    assert key in pipeline.processors, f"Missing processor: {key}"
                    assert pipeline.processors[key] is not None, f"Processor {key} is None"

    def test_processor_integrity_check(self):
        """Test that processor integrity check works correctly"""
        from backend.pipeline.master_pipeline import KRMasterPipeline

        pipeline = KRMasterPipeline()

        # Test with valid processors
        pipeline.processors = {"test1": Mock(process=Mock()), "test2": Mock(process=Mock())}

        # Should not raise
        pipeline._verify_processor_integrity()

        # Test with missing processor
        pipeline.processors = {"test1": None}

        with pytest.raises(RuntimeError, match="Missing processors"):
            pipeline._verify_processor_integrity()

        # Test with invalid processor (no process method)
        pipeline.processors = {"test1": Mock(spec=[])}  # No process method

        with pytest.raises(RuntimeError, match="Invalid processors"):
            pipeline._verify_processor_integrity()

    def test_all_processors_have_process_method(self):
        """Test that all processor classes have a process() method"""
        from backend.processors.chunk_preprocessor import ChunkPreprocessor
        from backend.processors.classification_processor import ClassificationProcessor
        from backend.processors.embedding_processor import EmbeddingProcessor
        from backend.processors.image_processor import ImageProcessor
        from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI
        from backend.processors.metadata_processor_ai import MetadataProcessorAI
        from backend.processors.search_processor import SearchProcessor
        from backend.processors.storage_processor import StorageProcessor
        from backend.processors.text_processor_optimized import OptimizedTextProcessor
        from backend.processors.upload_processor import UploadProcessor

        processors = [
            UploadProcessor,
            OptimizedTextProcessor,
            ImageProcessor,
            ClassificationProcessor,
            ChunkPreprocessor,
            MetadataProcessorAI,
            LinkExtractionProcessorAI,
            StorageProcessor,
            EmbeddingProcessor,
            SearchProcessor,
        ]

        for processor_class in processors:
            # Create instance with mocked dependencies
            try:
                if processor_class == UploadProcessor:
                    instance = processor_class(Mock())
                elif processor_class in [OptimizedTextProcessor, ChunkPreprocessor]:
                    instance = processor_class(Mock(), Mock())
                elif (
                    processor_class in [ImageProcessor, StorageProcessor]
                    or processor_class in [ClassificationProcessor]
                    or processor_class in [MetadataProcessorAI]
                ):
                    instance = processor_class(Mock(), Mock(), Mock())
                elif (
                    processor_class in [LinkExtractionProcessorAI, SearchProcessor]
                    or processor_class == EmbeddingProcessor
                ):
                    instance = processor_class(Mock(), Mock())
                else:
                    instance = processor_class()

                # Verify process method exists
                assert hasattr(instance, "process"), f"{processor_class.__name__} does not have a process() method"

                # Verify it's callable
                assert callable(instance.process), f"{processor_class.__name__}.process is not callable"

            except Exception as e:
                pytest.fail(f"Failed to instantiate {processor_class.__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
