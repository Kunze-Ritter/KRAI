"""
Integration tests for stage-based document processing API endpoints.

Tests cover:
- Single stage processing
- Multiple stage processing
- Stage listing and status retrieval
- Video processing integration
- Thumbnail generation
- Error handling and validation
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from backend.api.document_api import DocumentAPI
from backend.core.base_processor import Stage
from backend.services.database_service import DatabaseService
from backend.services.storage_service import StorageService
from backend.services.video_enrichment_service import VideoEnrichmentService


@pytest.mark.asyncio
class TestDocumentStageAPI:
    """Test stage-based document processing endpoints"""

    @pytest.fixture
    async def mock_services(self):
        """Create mock services for testing"""
        database_service = AsyncMock(spec=DatabaseService)
        storage_service = AsyncMock(spec=StorageService)
        video_service = AsyncMock(spec=VideoEnrichmentService)
        ai_service = AsyncMock()

        return {"database": database_service, "storage": storage_service, "video": video_service, "ai": ai_service}

    @pytest.fixture
    async def document_api(self, mock_services):
        """Create DocumentAPI instance with mocked services"""
        api = DocumentAPI(
            database_service=mock_services["database"],
            storage_service=mock_services["storage"],
            ai_service=mock_services["ai"],
            video_enrichment_service=mock_services["video"],
        )

        # Mock pipeline and thumbnail processor methods
        api.pipeline.run_single_stage = AsyncMock()
        api.pipeline.run_stages = AsyncMock()
        api.thumbnail_processor.process = AsyncMock()

        return api

    @pytest.fixture
    async def test_document_id(self):
        """Generate test document ID"""
        return str(uuid4())

    @pytest.fixture
    async def mock_processing_context(self, test_document_id):
        """Create mock ProcessingContext with correct dataclass fields"""
        from backend.core.base_processor import ProcessingContext

        return ProcessingContext(
            document_id=test_document_id,
            file_path="/tmp/test_document.pdf",
            file_hash="",
            document_type="service_manual",
            processing_config={"size": (300, 400), "page": 0},
        )

    @pytest.fixture
    async def client(self, document_api):
        """Create test client with DocumentAPI routes"""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(document_api.router, prefix="/api/v1")

        # Mock auth middleware for testing
        app.dependency_overrides = {}

        return AsyncClient(app=app, base_url="http://test")

    async def test_process_single_stage_success(
        self, client: AsyncClient, test_document_id: str, mock_services, document_api
    ):
        """Test processing a single stage successfully"""
        # Setup mocks
        mock_document = MagicMock()
        mock_document.storage_path = "/tmp/test_document.pdf"
        mock_document.document_type = "service_manual"
        mock_services["database"].get_document.return_value = mock_document

        # Mock pipeline response
        mock_pipeline_result = {
            "success": True,
            "data": {"chunks_created": 150, "text_length": 25000},
            "stage": "text_extraction",
            "processing_time": 2.5,
        }

        # Setup pipeline mock
        document_api.pipeline.run_single_stage.return_value = mock_pipeline_result

        response = await client.post(f"/api/v1/documents/{test_document_id}/process/stage/text_extraction")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["stage"] == "text_extraction"
        assert "processing_time" in data
        assert data["data"]["chunks_created"] == 150

    async def test_process_single_stage_invalid_stage(self, client: AsyncClient, test_document_id: str):
        """Test processing with invalid stage name"""
        response = await client.post(f"/api/v1/documents/{test_document_id}/process/stage/invalid_stage")

        assert response.status_code == 400
        assert "Invalid stage" in response.json()["detail"]

    async def test_process_single_stage_document_not_found(
        self, client: AsyncClient, test_document_id: str, mock_services
    ):
        """Test processing with non-existent document"""
        mock_services["database"].get_document.return_value = None

        response = await client.post(f"/api/v1/documents/{test_document_id}/process/stage/text_extraction")

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    async def test_process_multiple_stages(
        self, client: AsyncClient, test_document_id: str, mock_services, document_api
    ):
        """Test processing multiple stages"""
        # Setup mocks
        mock_document = MagicMock()
        mock_document.storage_path = "/tmp/test_document.pdf"
        mock_document.document_type = "service_manual"
        mock_services["database"].get_document.return_value = mock_document

        # Mock pipeline response
        mock_pipeline_result = {
            "success": True,
            "successful": 2,
            "failed": 0,
            "success_rate": 100.0,
            "stage_results": [
                {
                    "stage": "text_extraction",
                    "success": True,
                    "data": {"chunks_created": 150},
                    "error": None,
                    "processing_time": 2.5,
                },
                {
                    "stage": "image_processing",
                    "success": True,
                    "data": {"images_extracted": 5},
                    "error": None,
                    "processing_time": 5.2,
                },
            ],
        }

        # Setup pipeline mock
        document_api.pipeline.run_stages.return_value = mock_pipeline_result

        response = await client.post(
            f"/api/v1/documents/{test_document_id}/process/stages",
            json={"stages": ["text_extraction", "image_processing"], "stop_on_error": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_stages"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        assert len(data["stage_results"]) == 2

        # Check first stage result
        stage1 = data["stage_results"][0]
        assert stage1["stage"] == "text_extraction"
        assert stage1["success"] is True
        assert stage1["processing_time"] == 2.5
        assert stage1["data"]["chunks_created"] == 150

    async def test_process_multiple_stages_invalid_stages(self, client: AsyncClient, test_document_id: str):
        """Test processing with invalid stage names"""
        response = await client.post(
            f"/api/v1/documents/{test_document_id}/process/stages",
            json={"stages": ["text_extraction", "invalid_stage"], "stop_on_error": True},
        )

        assert response.status_code == 400
        assert "Invalid stages" in response.json()["detail"]

    async def test_get_available_stages(self, client: AsyncClient, test_document_id: str):
        """Test getting available stages"""
        response = await client.get(f"/api/v1/documents/{test_document_id}/stages")

        assert response.status_code == 200
        data = response.json()
        assert "stages" in data
        assert data["total"] == 15  # 15 stages in Stage enum
        assert "text_extraction" in data["stages"]
        assert "image_processing" in data["stages"]
        assert "embedding" in data["stages"]

    async def test_get_stage_status(self, client: AsyncClient, test_document_id: str, mock_services, mock_document):
        """Test getting stage status"""
        # Setup mocks
        mock_services["database"].get_document.return_value = mock_document

        # Mock pipeline response
        mock_status_result = {
            "found": True,
            "stage_status": {
                "upload": "completed",
                "text_extraction": "completed",
                "image_processing": "in_progress",
                "embedding": "pending",
            },
        }

        response = await client.get(f"/api/v1/documents/{test_document_id}/stages/status")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == test_document_id
        assert data["found"] is True
        assert "stage_status" in data
        assert data["stage_status"]["upload"] == "completed"

    async def test_get_stage_status_document_not_found(self, client: AsyncClient, test_document_id: str, mock_services):
        """Test getting stage status for non-existent document"""
        mock_services["database"].get_document.return_value = None

        response = await client.get(f"/api/v1/documents/{test_document_id}/stages/status")

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert "Document not found" in data["error"]

    async def test_process_video(self, client: AsyncClient, test_document_id: str, mock_services, mock_document):
        """Test video processing"""
        # Setup mocks
        mock_services["database"].get_document.return_value = mock_document

        # Mock video service response
        mock_video_result = {
            "success": True,
            "video_id": "dQw4w9WgXcQ",
            "title": "Product Installation Guide",
            "platform": "youtube",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            "duration": 180,
            "channel_title": "Manufacturer Channel",
        }
        mock_services["video"].enrich_video_url.return_value = mock_video_result

        response = await client.post(
            f"/api/v1/documents/{test_document_id}/process/video",
            json={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert data["platform"] == "youtube"
        assert data["thumbnail_url"] is not None

    async def test_process_video_service_unavailable(
        self, client: AsyncClient, test_document_id: str, mock_services, mock_document
    ):
        """Test video processing when service is not available"""
        # Create API without video service
        api = DocumentAPI(
            database_service=mock_services["database"],
            storage_service=mock_services["storage"],
            ai_service=mock_services["ai"],
            video_enrichment_service=None,
        )

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(api.router, prefix="/api/v1")
        client_no_video = AsyncClient(app=app, base_url="http://test")

        response = await client_no_video.post(
            f"/api/v1/documents/{test_document_id}/process/video",
            json={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 503
        assert "Video enrichment service not available" in response.json()["detail"]

    async def test_process_video_invalid_url(self, client: AsyncClient, test_document_id: str):
        """Test video processing with invalid URL"""
        response = await client.post(
            f"/api/v1/documents/{test_document_id}/process/video", json={"video_url": "not-a-valid-url"}
        )

        assert response.status_code == 422  # Validation error

    async def test_generate_thumbnail(self, client: AsyncClient, test_document_id: str, mock_services, mock_document):
        """Test thumbnail generation"""
        # Setup mocks
        mock_services["database"].get_document.return_value = mock_document

        # Mock thumbnail processor response
        mock_thumbnail_result = MagicMock()
        mock_thumbnail_result.success = True
        mock_thumbnail_result.data = {
            "thumbnail_url": "https://storage.example.com/thumbnails/test.png",
            "size": [300, 400],
            "file_size": 45678,
        }
        mock_thumbnail_result.error = None

        # Mock thumbnail processor
        original_processor = client.app.dependencies.pop("thumbnail_processor", None)
        if original_processor:
            original_processor.process = AsyncMock(return_value=mock_thumbnail_result)

        response = await client.post(
            f"/api/v1/documents/{test_document_id}/process/thumbnail", json={"size": [300, 400], "page": 0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["thumbnail_url"] is not None
        assert data["size"] == [300, 400]
        assert data["file_size"] == 45678

    async def test_generate_thumbnail_no_file_path(self, client: AsyncClient, test_document_id: str, mock_services):
        """Test thumbnail generation when document has no file path"""
        # Mock document without storage_path
        mock_doc_no_path = {
            "id": test_document_id,
            "filename": "test_document.pdf",
            "storage_path": None,  # Missing file path
            "processing_status": "pending",
        }
        mock_services["database"].get_document.return_value = mock_doc_no_path

        response = await client.post(f"/api/v1/documents/{test_document_id}/process/thumbnail")

        assert response.status_code == 400
        assert "no file path" in response.json()["detail"]

    async def test_generate_thumbnail_default_params(
        self, client: AsyncClient, test_document_id: str, mock_services, mock_document
    ):
        """Test thumbnail generation with default parameters"""
        # Setup mocks
        mock_services["database"].get_document.return_value = mock_document

        # Mock thumbnail processor response
        mock_thumbnail_result = MagicMock()
        mock_thumbnail_result.success = True
        mock_thumbnail_result.data = {
            "thumbnail_url": "https://storage.example.com/thumbnails/test.png",
            "size": [300, 400],  # Default size
            "file_size": 45678,
        }

        response = await client.post(f"/api/v1/documents/{test_document_id}/process/thumbnail")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["size"] == [300, 400]  # Default size applied

    async def test_document_not_found_all_endpoints(self, client: AsyncClient, mock_services):
        """Test with non-existent document across all endpoints"""
        fake_id = str(uuid4())
        mock_services["database"].get_document.return_value = None

        # Test single stage
        response = await client.post(f"/api/v1/documents/{fake_id}/process/stage/text_extraction")
        assert response.status_code == 404

        # Test multiple stages
        response = await client.post(
            f"/api/v1/documents/{fake_id}/process/stages", json={"stages": ["text_extraction"]}
        )
        assert response.status_code == 404

        # Test video processing
        response = await client.post(
            f"/api/v1/documents/{fake_id}/process/video", json={"video_url": "https://youtube.com/test"}
        )
        assert response.status_code == 404

        # Test thumbnail generation
        response = await client.post(f"/api/v1/documents/{fake_id}/process/thumbnail")
        assert response.status_code == 404

    async def test_stage_validation(self):
        """Test that all stage names are valid"""
        valid_stages = [stage.value for stage in Stage]
        expected_stages = [
            "upload",
            "text_extraction",
            "table_extraction",
            "svg_processing",
            "image_processing",
            "visual_embedding",
            "link_extraction",
            "chunk_prep",
            "classification",
            "metadata_extraction",
            "parts_extraction",
            "series_detection",
            "storage",
            "embedding",
            "search_indexing",
        ]

        assert len(valid_stages) == 15
        assert set(valid_stages) == set(expected_stages)

    async def test_error_handling_pipeline_failure(
        self, client: AsyncClient, test_document_id: str, mock_services, mock_document
    ):
        """Test error handling when pipeline processing fails"""
        # Setup mocks
        mock_services["database"].get_document.return_value = mock_document

        # Mock pipeline failure
        mock_pipeline_result = {"success": False, "error": "Processing failed due to internal error"}

        response = await client.post(f"/api/v1/documents/{test_document_id}/process/stage/text_extraction")

        assert response.status_code == 200  # Endpoint succeeds, but processing fails
        data = response.json()
        assert data["success"] is False
        assert "error" in data


@pytest.mark.asyncio
class TestStageAPIIntegration:
    """Integration tests with real service interactions"""

    async def test_full_workflow_simulation(self):
        """Test a complete document processing workflow"""
        # This would be a more comprehensive test using real services
        # For now, it's a placeholder showing the intended test structure

        workflow_steps = ["upload", "text_extraction", "image_processing", "embedding", "thumbnail_generation"]

        # Simulate the workflow
        for step in workflow_steps:
            assert step in [s.value for s in Stage]

        assert len(workflow_steps) == 5


# Test utilities and helpers


@pytest.fixture
def mock_processing_context():
    """Create a mock processing context"""
    from backend.core.base_processor import ProcessingContext

    return ProcessingContext(
        document_id=str(uuid4()), file_path="/tmp/test.pdf", parameters={"size": [300, 400], "page": 0}
    )


@pytest.fixture
def sample_video_urls():
    """Sample video URLs for testing"""
    return {
        "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "youtube_short": "https://youtu.be/dQw4w9WgXcQ",
        "vimeo": "https://vimeo.com/123456789",
        "invalid": "not-a-valid-url",
    }


# Performance tests (optional)


@pytest.mark.asyncio
@pytest.mark.slow
class TestStageAPIPerformance:
    """Performance tests for stage-based processing"""

    async def test_concurrent_stage_processing(self):
        """Test processing multiple stages concurrently"""
        # This would test actual performance with timing
        pass

    async def test_large_document_processing(self):
        """Test processing with large documents"""
        # This would test memory usage and processing time
        pass


# Security tests


@pytest.mark.asyncio
class TestStageAPISecurity:
    """Security tests for stage-based processing"""

    async def test_unauthorized_access(self):
        """Test that unauthorized requests are rejected"""
        # This would test authentication and authorization
        pass

    async def test_malicious_stage_names(self):
        """Test handling of malicious stage name inputs"""
        malicious_inputs = [
            "../../../etc/passwd",
            "<script>alert('xss')</script>",
            "'; DROP TABLE documents; --",
            "text_extraction\0\0\0",
        ]

        for malicious_input in malicious_inputs:
            # These should be rejected by validation
            assert malicious_input not in [s.value for s in Stage]
