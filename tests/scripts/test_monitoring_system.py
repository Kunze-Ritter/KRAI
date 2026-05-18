"""
End-to-End Tests for Monitoring System

Tests the complete monitoring system including:
- Metrics aggregation
- Alert evaluation
- WebSocket broadcasting
- Permission checks
- Database integration
"""

from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

# Import monitoring components
from backend.models.monitoring import (
    Alert,
    AlertSeverity,
    AlertType,
    CreateAlertRule,
    HardwareMetrics,
    PipelineMetrics,
    QueueMetrics,
)
from backend.services.alert_service import AlertService
from backend.services.database_adapter import DatabaseAdapter
from backend.services.metrics_service import MetricsService


class TestMetricsService:
    """Test MetricsService with real database queries."""

    @pytest.fixture
    async def metrics_service(self, mock_database_adapter):
        """Create MetricsService with mocked adapter."""
        from unittest.mock import Mock

        stage_tracker = Mock()
        service = MetricsService(mock_database_adapter, stage_tracker)
        return service

    @pytest.mark.asyncio
    async def test_get_pipeline_metrics(self, metrics_service, mock_database_adapter):
        """Test pipeline metrics aggregation."""
        # Mock database query response
        mock_database_adapter.query_results["pipeline_metrics"] = [
            {
                "total_documents": 1000,
                "documents_pending": 50,
                "documents_processing": 10,
                "documents_completed": 920,
                "documents_failed": 20,
                "success_rate": 97.87,
                "recent_24h_count": 150,
            }
        ]

        metrics = await metrics_service.get_pipeline_metrics()

        assert isinstance(metrics, PipelineMetrics)
        assert metrics.total_documents == 1000
        assert metrics.documents_completed == 920
        assert metrics.documents_failed == 20
        assert metrics.success_rate == 97.87
        assert metrics.current_throughput_docs_per_hour == pytest.approx(6.25, 0.01)

    @pytest.mark.asyncio
    async def test_get_queue_metrics(self, metrics_service, mock_database_adapter):
        """Test queue metrics aggregation."""
        # Mock database query response
        mock_database_adapter.query_results["queue_metrics"] = [
            {
                "total_items": 200,
                "pending_count": 50,
                "processing_count": 10,
                "completed_count": 130,
                "failed_count": 10,
                "avg_processing_time_seconds": 45.5,
            }
        ]

        # Mock task type query
        mock_database_adapter.query_results["task_types"] = [
            {"task_type": "document_processing"},
            {"task_type": "document_processing"},
            {"task_type": "embedding_generation"},
        ]

        metrics = await metrics_service.get_queue_metrics()

        assert isinstance(metrics, QueueMetrics)
        assert metrics.total_items == 200
        assert metrics.pending_count == 50
        assert metrics.processing_count == 10
        assert metrics.avg_wait_time_seconds == 45.5
        assert "document_processing" in metrics.by_task_type

    @pytest.mark.asyncio
    async def test_get_stage_metrics(self, metrics_service, mock_database_adapter):
        """Test stage metrics aggregation."""
        # Mock database query response
        mock_database_adapter.query_results["stage_metrics"] = [
            {
                "stage_name": "text_extraction",
                "total_executions": 1000,
                "completed_count": 980,
                "failed_count": 20,
                "avg_duration_seconds": 12.5,
            },
            {
                "stage_name": "embedding",
                "total_executions": 980,
                "completed_count": 975,
                "failed_count": 5,
                "avg_duration_seconds": 8.3,
            },
        ]

        metrics = await metrics_service.get_stage_metrics()

        assert isinstance(metrics, list)
        assert len(metrics) == 2
        assert metrics[0].stage_name == "text_extraction"
        assert metrics[0].completed_count == 980
        assert metrics[0].success_rate == 98.0
        assert metrics[1].stage_name == "embedding"

    @pytest.mark.asyncio
    async def test_get_hardware_metrics(self, metrics_service):
        """Test hardware metrics collection."""
        metrics = await metrics_service.get_hardware_metrics()

        assert isinstance(metrics, HardwareMetrics)
        assert 0 <= metrics.cpu_percent <= 100
        assert 0 <= metrics.ram_percent <= 100
        assert 0 <= metrics.disk_percent <= 100
        assert isinstance(metrics.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_metrics_caching(self, metrics_service, mock_database_adapter):
        """Test that metrics are cached properly."""
        # Mock response
        mock_database_adapter.query_results["pipeline_metrics"] = [
            {
                "total_documents": 1000,
                "documents_pending": 50,
                "documents_processing": 10,
                "documents_completed": 920,
                "documents_failed": 20,
                "success_rate": 97.87,
                "recent_24h_count": 150,
            }
        ]

        # First call - should hit database
        metrics1 = await metrics_service.get_pipeline_metrics()

        # Second call - should use cache
        metrics2 = await metrics_service.get_pipeline_metrics()

        assert metrics1 == metrics2
        # Verify caching behavior (implementation-specific)

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, metrics_service, mock_database_adapter):
        """Test cache invalidation."""
        # Mock response
        mock_database_adapter.query_results["pipeline_metrics"] = [
            {
                "total_documents": 1000,
                "documents_pending": 50,
                "documents_processing": 10,
                "documents_completed": 920,
                "documents_failed": 20,
                "success_rate": 97.87,
                "recent_24h_count": 150,
            }
        ]

        # Get metrics (cached)
        await metrics_service.get_pipeline_metrics()

        # Invalidate cache
        metrics_service.invalidate_cache("pipeline_metrics")

        # Get metrics again (should hit database)
        await metrics_service.get_pipeline_metrics()

        # Verify cache invalidation behavior (implementation-specific)


class TestAlertService:
    """Test AlertService with alert evaluation."""

    @pytest.fixture
    async def alert_service(self, mock_database_adapter, metrics_service):
        """Create AlertService with mocked adapter."""
        service = AlertService(mock_database_adapter, metrics_service)
        await service.load_alert_configurations()
        return service

    @pytest.mark.asyncio
    async def test_load_alert_configurations(self, alert_service, mock_database_adapter):
        """Test loading alert configurations from database."""
        # Mock database response
        mock_database_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "High CPU Usage",
                "description": "Alert on high CPU",
                "is_enabled": True,
                "error_types": ["hardware_threshold"],
                "stages": [],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": ["admin@example.com"],
                "slack_webhooks": [],
            }
        ]

        configs = await alert_service.load_alert_configurations()

        assert len(configs) > 0
        assert all(isinstance(config, dict) for config in configs)

    @pytest.mark.asyncio
    async def test_add_alert_configuration(self, alert_service, mock_database_adapter):
        """Test adding new alert configuration."""
        # Mock database insert
        mock_database_adapter.query_results["insert_alert"] = [{"id": "rule-new"}]

        new_rule = CreateAlertRule(
            name="Test Alert",
            alert_type=AlertType.HARDWARE_THRESHOLD,
            severity=AlertSeverity.HIGH,
            threshold_value=85.0,
            threshold_operator=">",
            metric_key="ram",
            enabled=True,
        )

        config_id = await alert_service.add_alert_configuration(new_rule)

        assert config_id == "rule-new"

    @pytest.mark.asyncio
    async def test_queue_alert_high_cpu(self, alert_service, mock_database_adapter):
        """Test queueing alert for high CPU usage."""
        # Set up alert configuration
        mock_database_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-cpu",
                "rule_name": "High CPU Usage",
                "description": "Alert on high CPU",
                "is_enabled": True,
                "error_types": ["hardware_threshold"],
                "stages": [],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]
        mock_database_adapter.query_results["existing_alert"] = []
        mock_database_adapter.query_results["insert_alert"] = [{"id": "alert-123"}]

        # Queue alert for high CPU
        error_data = {
            "error_type": "hardware_threshold",
            "stage_name": "monitoring",
            "severity": "high",
            "error_message": "CPU usage at 95%",
            "document_id": None,
        }

        alert_id = await alert_service.queue_alert(error_data)

        assert alert_id == "alert-123"

    @pytest.mark.asyncio
    async def test_queue_alert_processing_failure(self, alert_service, mock_database_adapter):
        """Test queueing alert for processing failures."""
        # Set up alert configuration
        mock_database_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-fail",
                "rule_name": "High Failure Rate",
                "description": "Alert on processing failures",
                "is_enabled": True,
                "error_types": ["processing_failure"],
                "stages": ["text_extraction"],
                "severity_threshold": "high",
                "error_count_threshold": 10,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]
        mock_database_adapter.query_results["existing_alert"] = []
        mock_database_adapter.query_results["insert_alert"] = [{"id": "alert-456"}]

        # Queue alert for processing failure
        error_data = {
            "error_type": "processing_failure",
            "stage_name": "text_extraction",
            "severity": "high",
            "error_message": "Failed to extract text",
            "document_id": "doc-123",
        }

        alert_id = await alert_service.queue_alert(error_data)

        assert alert_id == "alert-456"

    @pytest.mark.asyncio
    async def test_alert_aggregation(self, alert_service, mock_database_adapter):
        """Test that alerts are aggregated within time window."""
        # Set up alert configuration
        mock_database_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-cpu",
                "rule_name": "High CPU Usage",
                "description": "Alert on high CPU",
                "is_enabled": True,
                "error_types": ["hardware_threshold"],
                "stages": [],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]

        # First alert - no existing alert
        mock_database_adapter.query_results["existing_alert"] = []
        mock_database_adapter.query_results["insert_alert"] = [{"id": "alert-123"}]

        error_data = {
            "error_type": "hardware_threshold",
            "stage_name": "monitoring",
            "severity": "high",
            "error_message": "CPU at 95%",
        }

        alert_id_1 = await alert_service.queue_alert(error_data)
        assert alert_id_1 == "alert-123"

        # Second alert - existing alert found, should aggregate
        mock_database_adapter.query_results["existing_alert"] = [{"id": "alert-123", "aggregation_count": 1}]

        alert_id_2 = await alert_service.queue_alert(error_data)
        assert alert_id_2 == "alert-123"  # Same alert ID

    @pytest.mark.asyncio
    async def test_get_alerts_with_filters(self, alert_service, mock_database_adapter):
        """Test getting alerts with filters."""
        # Mock database response
        mock_database_adapter.query_results["pending_alerts"] = [
            {
                "id": "alert-001",
                "alert_type": "hardware_threshold",
                "severity": "high",
                "message": "CPU usage is 95%",
                "details": {"cpu_percent": 95.0},
                "aggregation_key": "High CPU Usage:hardware_threshold:monitoring",
                "aggregation_count": 3,
                "first_occurrence": datetime.utcnow(),
                "last_occurrence": datetime.utcnow(),
                "status": "pending",
                "sent_at": None,
                "created_at": datetime.utcnow(),
            }
        ]
        mock_database_adapter.query_results["count_result"] = [{"count": 1}]

        response = await alert_service.get_alerts(
            limit=50,
            severity_filter=AlertSeverity.HIGH,
            status_filter="pending",
        )

        assert response.total >= 0
        assert response.unacknowledged_count >= 0


class TestMonitoringAPI:
    """Test Monitoring API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, mock_jwt_token):
        """Create authentication headers."""
        return {"Authorization": f"Bearer {mock_jwt_token}"}

    def test_get_pipeline_metrics_endpoint(self, client, auth_headers):
        """Test GET /api/v1/monitoring/pipeline endpoint."""
        response = client.get("/api/v1/monitoring/pipeline", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "success_rate" in data
        assert "current_throughput_docs_per_hour" in data

    def test_get_queue_metrics_endpoint(self, client, auth_headers):
        """Test GET /api/v1/monitoring/queue endpoint."""
        response = client.get("/api/v1/monitoring/queue", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "total_items" in data
        assert "pending_count" in data
        assert "by_task_type" in data

    def test_get_hardware_metrics_endpoint(self, client, auth_headers):
        """Test GET /api/v1/monitoring/metrics endpoint."""
        response = client.get("/api/v1/monitoring/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "cpu_percent" in data
        assert "ram_percent" in data
        assert "disk_percent" in data

    def test_get_alerts_endpoint(self, client, auth_headers):
        """Test GET /api/v1/monitoring/alerts endpoint."""
        response = client.get("/api/v1/monitoring/alerts", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "unacknowledged_count" in data

    def test_create_alert_rule_endpoint(self, client, auth_headers):
        """Test POST /api/v1/monitoring/alert-rules endpoint."""
        new_rule = {
            "name": "Test Alert Rule",
            "alert_type": "hardware_threshold",
            "severity": "medium",
            "threshold_value": 80.0,
            "threshold_operator": ">",
            "metric_key": "ram",
            "enabled": True,
        }

        response = client.post(
            "/api/v1/monitoring/alert-rules",
            json=new_rule,
            headers=auth_headers,
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["success"] is True
        assert "rule_id" in data

    def test_unauthorized_access(self, client):
        """Test that endpoints require authentication."""
        response = client.get("/api/v1/monitoring/pipeline")
        assert response.status_code == 401

    def test_insufficient_permissions(self, client):
        """Test that endpoints check permissions."""
        # Mock token with insufficient permissions
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/monitoring/pipeline", headers=headers)
        assert response.status_code in [401, 403]


class TestWebSocketAPI:
    """Test WebSocket API for real-time updates."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, mock_jwt_token):
        """Test WebSocket connection with authentication."""
        client = TestClient(app)

        with client.websocket_connect(f"/ws/monitoring?token={mock_jwt_token}") as websocket:
            # Should connect successfully
            data = websocket.receive_json()
            assert "event" in data

    @pytest.mark.asyncio
    async def test_websocket_authentication_failure(self):
        """Test WebSocket connection fails with invalid token."""
        client = TestClient(app)

        with pytest.raises(Exception):
            with client.websocket_connect("/ws/monitoring?token=invalid") as websocket:
                pass

    @pytest.mark.asyncio
    async def test_websocket_broadcast_alert(self, mock_jwt_token):
        """Test alert broadcasting over WebSocket."""
        from backend.api.websocket import broadcast_alert

        alert = Alert(
            id="alert-test",
            alert_type=AlertType.HARDWARE_THRESHOLD,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            message="This is a test",
            metadata={},
            triggered_at=datetime.utcnow(),
            acknowledged=False,
        )

        # Broadcast should not raise exception
        await broadcast_alert(alert)


class TestIntegration:
    """Integration tests for complete monitoring flow."""

    @pytest.mark.asyncio
    async def test_complete_monitoring_flow(self, mock_database_adapter, metrics_service, alert_service):
        """Test complete flow: metrics → queue alert → notification."""
        # 1. Get metrics (mocked)
        with patch.object(metrics_service, "get_pipeline_metrics") as mock_pipeline:
            mock_pipeline.return_value = PipelineMetrics(
                total_documents=1000,
                documents_pending=50,
                documents_processing=10,
                documents_completed=920,
                documents_failed=20,
                success_rate=97.87,
                avg_processing_time_seconds=45.0,
                current_throughput_docs_per_hour=25.0,
            )
            pipeline_metrics = await metrics_service.get_pipeline_metrics()
            assert isinstance(pipeline_metrics, PipelineMetrics)

        # 2. Queue alert based on error
        mock_database_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "Test Rule",
                "is_enabled": True,
                "error_types": ["processing_error"],
                "stages": [],
                "severity_threshold": "medium",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]
        mock_database_adapter.query_results["existing_alert"] = []
        mock_database_adapter.query_results["insert_alert"] = [{"id": "alert-123"}]

        error_data = {
            "error_type": "processing_error",
            "stage_name": "text_extraction",
            "severity": "medium",
            "error_message": "Test error",
        }

        alert_id = await alert_service.queue_alert(error_data)
        assert alert_id is not None

    @pytest.mark.asyncio
    async def test_health_check_includes_monitoring(self, client):
        """Test that health check includes monitoring services."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "monitoring" in data["services"]

        monitoring = data["services"]["monitoring"]
        assert "metrics_service" in monitoring
        assert "alert_service" in monitoring
        assert "websocket_connections" in monitoring


# Fixtures


@pytest.fixture
def mock_database_adapter():
    """Create mock DatabaseAdapter."""

    class MockDatabaseAdapter(DatabaseAdapter):
        def __init__(self):
            super().__init__()
            self.queries_executed = []
            self.query_results = {}

        async def execute_query(self, query: str, params: list[Any] = None) -> list[dict[str, Any]]:
            self.queries_executed.append((query, params))
            if "alert_configurations" in query and "SELECT" in query:
                return self.query_results.get("alert_configurations", [])
            if "alerts" in query and "SELECT" in query and "aggregation_key" in query:
                return self.query_results.get("existing_alert", [])
            if "alerts" in query and "INSERT" in query:
                return self.query_results.get("insert_alert", [{"id": "alert-123"}])
            if "alerts" in query and "UPDATE" in query:
                result = Mock()
                result.rowcount = 1
                return result
            if "alerts" in query and "COUNT" in query:
                return self.query_results.get("count_result", [{"count": 0}])
            return []

        # Stub abstract methods
        async def connect(self):
            pass

        async def test_connection(self):
            return True

        async def create_document(self, document):
            return "doc-123"

        async def get_document(self, document_id: str):
            return None

        async def get_document_by_hash(self, file_hash: str):
            return None

        async def update_document(self, document_id: str, updates: dict[str, Any]):
            return True

        async def create_manufacturer(self, manufacturer):
            return "mfr-123"

        async def get_manufacturer_by_name(self, name: str):
            return None

        async def create_product_series(self, series):
            return "series-123"

        async def get_product_series_by_name(self, name: str, manufacturer_id: str):
            return None

        async def create_product(self, product):
            return "prod-123"

        async def get_product_by_model(self, model_number: str, manufacturer_id: str):
            return None

        async def create_chunk(self, chunk):
            return "chunk-123"

        async def create_chunk_async(self, chunk_data: dict[str, Any]):
            return "chunk-123"

        async def get_chunk_by_document_and_index(self, document_id: str, chunk_index: int):
            return None

        async def create_image(self, image):
            return "img-123"

        async def get_image_by_hash(self, image_hash: str):
            return None

        async def get_images_by_document(self, document_id: str):
            return []

        async def create_intelligence_chunk(self, chunk):
            return "intel-123"

        async def create_embedding(self, embedding):
            return "emb-123"

        async def get_embedding_by_chunk_id(self, chunk_id: str):
            return None

        async def get_embeddings_by_chunk_ids(self, chunk_ids: list[str]):
            return []

        async def search_embeddings(
            self, query_embedding: list[float], limit: int = 10, match_threshold: float = 0.7, match_count: int = 10
        ):
            return []

        async def create_error_code(self, error_code):
            return "err-123"

        async def log_search_analytics(self, analytics):
            return "analytics-123"

        async def create_processing_queue_item(self, item):
            return "queue-123"

        async def update_processing_queue_item(self, item_id: str, updates: dict[str, Any]):
            return True

        async def log_audit_event(self, event):
            return "audit-123"

        async def get_system_status(self):
            return {}

        async def count_chunks_by_document(self, document_id: str):
            return 0

        async def count_images_by_document(self, document_id: str):
            return 0

        async def check_embedding_exists(self, chunk_id: str):
            return False

        async def count_links_by_document(self, document_id: str):
            return 0

        async def create_link(self, link_data: dict[str, Any]):
            return "link-123"

        async def create_video(self, video_data: dict[str, Any]):
            return "video-123"

        async def create_print_defect(self, defect):
            return "defect-123"

    return MockDatabaseAdapter()


@pytest.fixture
def mock_jwt_token():
    """Create mock JWT token for testing."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsInBlcm1pc3Npb25zIjpbIm1vbml0b3Jpbmc6cmVhZCIsImFsZXJ0czpyZWFkIl19.test"


@pytest.fixture
async def metrics_service(mock_database_adapter):
    """Create MetricsService for testing."""

    stage_tracker = Mock()
    return MetricsService(mock_database_adapter, stage_tracker)


@pytest.fixture
async def alert_service(mock_database_adapter, metrics_service):
    """Create AlertService for testing."""
    service = AlertService(mock_database_adapter, metrics_service)
    await service.load_alert_configurations()
    return service


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
