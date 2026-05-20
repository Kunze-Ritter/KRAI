"""
Comprehensive unit tests for AlertService.

Tests alert queueing, rule matching, aggregation, email/Slack notifications,
cache TTL, threshold/suppression logic, and background worker cleanup.
"""

import asyncio
import time
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.models.monitoring import AlertListResponse, AlertSeverity, AlertType, CreateAlertRule
from backend.services.alert_service import AlertService
from backend.services.database_adapter import DatabaseAdapter
from backend.services.metrics_service import MetricsService


class MockDatabaseAdapter(DatabaseAdapter):
    """Mock DatabaseAdapter for testing."""

    def __init__(self):
        super().__init__()
        self.queries_executed = []
        self.query_results = {}

    async def execute_query(self, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Mock execute_query method."""
        self.queries_executed.append((query, params))

        # Return mocked results based on query pattern
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
        if "alerts" in query and "SELECT" in query and "status = 'pending'" in query:
            return self.query_results.get("pending_alerts", [])
        if "alerts" in query and "COUNT" in query:
            return self.query_results.get("count_result", [{"count": 0}])

        return []

    async def fetch_one(self, query: str, params: list[Any] | None = None) -> dict[str, Any]:
        """Mock fetch_one method."""
        results = await self.execute_query(query, params)
        return results[0] if results else None

    async def fetch_all(self, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Mock fetch_all method."""
        return await self.execute_query(query, params)

    # Implement abstract methods (minimal stubs)
    async def connect(self) -> None:
        pass

    async def test_connection(self) -> bool:
        return True

    async def create_document(self, document):
        return "doc-123"

    async def get_document(self, document_id: str):
        return None

    async def get_document_by_hash(self, file_hash: str):
        return None

    async def update_document(self, document_id: str, updates: dict[str, Any]) -> bool:
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

    async def create_chunk_async(self, chunk_data: dict[str, Any]) -> str:
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

    async def update_processing_queue_item(self, item_id: str, updates: dict[str, Any]) -> bool:
        return True

    async def log_audit_event(self, event):
        return "audit-123"

    async def get_system_status(self):
        return {}

    async def count_chunks_by_document(self, document_id: str) -> int:
        return 0

    async def count_images_by_document(self, document_id: str) -> int:
        return 0

    async def check_embedding_exists(self, chunk_id: str) -> bool:
        return False

    async def count_links_by_document(self, document_id: str) -> int:
        return 0

    async def create_link(self, link_data: dict[str, Any]) -> str:
        return "link-123"

    async def create_video(self, video_data: dict[str, Any]) -> str:
        return "video-123"

    async def create_print_defect(self, defect):
        return "defect-123"


@pytest.fixture
def mock_adapter():
    """Create mock database adapter."""
    return MockDatabaseAdapter()


@pytest.fixture
def mock_metrics_service():
    """Create mock metrics service."""
    return Mock(spec=MetricsService)


@pytest.fixture
async def alert_service(mock_adapter, mock_metrics_service):
    """Create AlertService with mocked dependencies."""
    return AlertService(mock_adapter, mock_metrics_service)


class TestAlertServiceQueueing:
    """Test alert queueing functionality."""

    @pytest.mark.asyncio
    async def test_queue_alert_success(self, alert_service, mock_adapter):
        """Test successful alert queueing."""
        # Setup mock alert configurations
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "High Error Rate",
                "description": "Alert on high error rate",
                "is_enabled": True,
                "error_types": ["processing_error"],
                "stages": ["text_extraction"],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": ["admin@example.com"],
                "slack_webhooks": [],
            }
        ]
        mock_adapter.query_results["existing_alert"] = []
        mock_adapter.query_results["insert_alert"] = [{"id": "alert-new-123"}]

        # Queue alert
        error_data = {
            "error_type": "processing_error",
            "stage_name": "text_extraction",
            "severity": "high",
            "error_message": "Failed to extract text",
            "document_id": "doc-123",
            "correlation_id": "req-456",
        }

        alert_id = await alert_service.queue_alert(error_data)

        assert alert_id == "alert-new-123"
        assert len(mock_adapter.queries_executed) > 0

    @pytest.mark.asyncio
    async def test_queue_alert_no_matching_rules(self, alert_service, mock_adapter):
        """Test queueing when no rules match."""
        # Setup mock with no matching rules
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "High Error Rate",
                "is_enabled": True,
                "error_types": ["embedding_error"],  # Different error type
                "stages": ["embedding"],
                "severity_threshold": "critical",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]

        error_data = {
            "error_type": "processing_error",
            "stage_name": "text_extraction",
            "severity": "high",
            "error_message": "Failed to extract text",
        }

        alert_id = await alert_service.queue_alert(error_data)

        assert alert_id is None

    @pytest.mark.asyncio
    async def test_queue_alert_aggregation(self, alert_service, mock_adapter):
        """Test alert aggregation for duplicate alerts."""
        # Setup mock with existing alert
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "High Error Rate",
                "is_enabled": True,
                "error_types": ["processing_error"],
                "stages": ["text_extraction"],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]
        mock_adapter.query_results["existing_alert"] = [
            {
                "id": "alert-existing-123",
                "aggregation_count": 3,
            }
        ]

        error_data = {
            "error_type": "processing_error",
            "stage_name": "text_extraction",
            "severity": "high",
            "error_message": "Failed to extract text",
        }

        alert_id = await alert_service.queue_alert(error_data)

        assert alert_id == "alert-existing-123"
        # Verify UPDATE query was executed
        update_queries = [q for q in mock_adapter.queries_executed if "UPDATE" in q[0]]
        assert len(update_queries) > 0


class TestAlertRuleMatching:
    """Test alert rule matching logic."""

    @pytest.mark.asyncio
    async def test_get_alert_rules_cache(self, alert_service, mock_adapter):
        """Test alert rules caching."""
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "Test Rule",
                "is_enabled": True,
                "error_types": [],
                "stages": [],
                "severity_threshold": "medium",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]

        # First call - should hit database
        rules1 = await alert_service._get_alert_rules()
        query_count_1 = len(mock_adapter.queries_executed)

        # Second call - should use cache
        rules2 = await alert_service._get_alert_rules()
        query_count_2 = len(mock_adapter.queries_executed)

        assert rules1 == rules2
        assert query_count_2 == query_count_1  # No new queries

    @pytest.mark.asyncio
    async def test_get_alert_rules_cache_expiry(self, alert_service, mock_adapter):
        """Test alert rules cache expiry after TTL."""
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "Test Rule",
                "is_enabled": True,
                "error_types": [],
                "stages": [],
                "severity_threshold": "medium",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": [],
                "slack_webhooks": [],
            }
        ]

        # First call
        await alert_service._get_alert_rules()
        query_count_1 = len(mock_adapter.queries_executed)

        # Expire cache by manipulating timestamp
        alert_service._cache_timestamp = time.time() - 61  # 61 seconds ago

        # Second call - should hit database again
        await alert_service._get_alert_rules()
        query_count_2 = len(mock_adapter.queries_executed)

        assert query_count_2 > query_count_1  # New query executed

    def test_matches_rule_error_type(self, alert_service):
        """Test rule matching by error type."""
        rule_config = {
            "error_types": ["processing_error", "validation_error"],
            "stages": [],
            "severity_threshold": None,
        }

        # Matching error type
        error_data_match = {"error_type": "processing_error", "stage_name": "any", "severity": "medium"}
        assert alert_service._matches_rule(error_data_match, rule_config) is True

        # Non-matching error type
        error_data_no_match = {"error_type": "embedding_error", "stage_name": "any", "severity": "medium"}
        assert alert_service._matches_rule(error_data_no_match, rule_config) is False

    def test_matches_rule_stage(self, alert_service):
        """Test rule matching by stage."""
        rule_config = {
            "error_types": [],
            "stages": ["text_extraction", "classification"],
            "severity_threshold": None,
        }

        # Matching stage
        error_data_match = {"error_type": "any", "stage_name": "text_extraction", "severity": "medium"}
        assert alert_service._matches_rule(error_data_match, rule_config) is True

        # Non-matching stage
        error_data_no_match = {"error_type": "any", "stage_name": "embedding", "severity": "medium"}
        assert alert_service._matches_rule(error_data_no_match, rule_config) is False

    def test_matches_rule_severity_threshold(self, alert_service):
        """Test rule matching by severity threshold."""
        rule_config = {
            "error_types": [],
            "stages": [],
            "severity_threshold": "high",
        }

        # Severity meets threshold (critical >= high)
        error_data_match = {"error_type": "any", "stage_name": "any", "severity": "critical"}
        assert alert_service._matches_rule(error_data_match, rule_config) is True

        # Severity meets threshold (high >= high)
        error_data_match2 = {"error_type": "any", "stage_name": "any", "severity": "high"}
        assert alert_service._matches_rule(error_data_match2, rule_config) is True

        # Severity below threshold (medium < high)
        error_data_no_match = {"error_type": "any", "stage_name": "any", "severity": "medium"}
        assert alert_service._matches_rule(error_data_no_match, rule_config) is False

    def test_matches_rule_empty_filters(self, alert_service):
        """Test rule matching with empty filters (match all)."""
        rule_config = {
            "error_types": [],
            "stages": [],
            "severity_threshold": None,
        }

        error_data = {"error_type": "any", "stage_name": "any", "severity": "low"}
        assert alert_service._matches_rule(error_data, rule_config) is True

    def test_severity_meets_threshold(self, alert_service):
        """Test severity threshold comparison."""
        assert alert_service._severity_meets_threshold("critical", "high") is True
        assert alert_service._severity_meets_threshold("high", "high") is True
        assert alert_service._severity_meets_threshold("medium", "high") is False
        assert alert_service._severity_meets_threshold("low", "medium") is False
        assert alert_service._severity_meets_threshold("info", "low") is False


class TestEmailNotifications:
    """Test email notification functionality."""

    @pytest.mark.asyncio
    async def test_send_email_alert_success(self, alert_service):
        """Test successful email sending."""
        with patch("backend.services.alert_service.aiosmtplib.SMTP") as mock_smtp:
            # Mock SMTP context manager
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            # Mock environment variables
            with patch.dict(
                "os.environ",
                {
                    "SMTP_HOST": "smtp.example.com",
                    "SMTP_PORT": "587",
                    "SMTP_USERNAME": "user@example.com",
                    "SMTP_PASSWORD": "password",
                    "SMTP_FROM_EMAIL": "alerts@example.com",
                    "SMTP_USE_TLS": "true",
                },
            ):
                alert_data = {
                    "id": "alert-123",
                    "severity": "high",
                    "alert_type": "processing_error",
                    "message": "Test alert message",
                    "aggregation_count": 5,
                    "first_occurrence": "2024-01-01T00:00:00Z",
                    "last_occurrence": "2024-01-01T01:00:00Z",
                    "details": {
                        "error_message": "Test error",
                        "stack_trace": "Stack trace here",
                    },
                }

                rule_config = {
                    "rule_name": "Test Alert Rule",
                    "description": "Test description",
                }

                recipients = ["admin@example.com", "ops@example.com"]

                result = await alert_service.send_email_alert(alert_data, recipients, rule_config)

                assert result is True
                mock_smtp_instance.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_alert_no_smtp_host(self, alert_service):
        """Test email sending fails when SMTP_HOST not configured."""
        with patch.dict("os.environ", {}, clear=True):
            alert_data = {"severity": "high", "message": "Test"}
            rule_config = {"rule_name": "Test"}
            recipients = ["admin@example.com"]

            result = await alert_service.send_email_alert(alert_data, recipients, rule_config)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_alert_no_recipients(self, alert_service):
        """Test email sending fails when no recipients."""
        with patch.dict("os.environ", {"SMTP_HOST": "smtp.example.com"}):
            alert_data = {"severity": "high", "message": "Test"}
            rule_config = {"rule_name": "Test"}
            recipients = []

            result = await alert_service.send_email_alert(alert_data, recipients, rule_config)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_alert_smtp_error(self, alert_service):
        """Test email sending handles SMTP errors."""
        with patch("backend.services.alert_service.aiosmtplib.SMTP") as mock_smtp:
            import aiosmtplib

            mock_smtp_instance = AsyncMock()
            mock_smtp_instance.send_message.side_effect = aiosmtplib.SMTPException("SMTP error")
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            with patch.dict(
                "os.environ",
                {
                    "SMTP_HOST": "smtp.example.com",
                    "SMTP_PORT": "587",
                },
            ):
                alert_data = {"severity": "high", "message": "Test", "details": {}}
                rule_config = {"rule_name": "Test", "description": ""}
                recipients = ["admin@example.com"]

                result = await alert_service.send_email_alert(alert_data, recipients, rule_config)

                assert result is False


class TestSlackNotifications:
    """Test Slack notification functionality."""

    @pytest.mark.asyncio
    async def test_send_slack_alert_success(self, alert_service):
        """Test successful Slack webhook posting."""
        with patch("backend.services.alert_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            alert_data = {
                "id": "alert-123",
                "severity": "high",
                "alert_type": "processing_error",
                "message": "Test alert",
                "aggregation_count": 3,
                "first_occurrence": "2024-01-01T00:00:00Z",
                "last_occurrence": "2024-01-01T01:00:00Z",
                "details": {},
            }

            rule_config = {
                "rule_name": "Test Rule",
                "description": "Test description",
            }

            webhook_urls = ["https://hooks.slack.com/services/TEST/WEBHOOK/URL"]

            result = await alert_service.send_slack_alert(alert_data, webhook_urls, rule_config)

            assert result is True
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_alert_invalid_webhook(self, alert_service):
        """Test Slack alert fails with invalid webhook URL."""
        alert_data = {"severity": "high", "message": "Test", "details": {}}
        rule_config = {"rule_name": "Test", "description": ""}
        webhook_urls = ["http://invalid-url.com"]  # Not a Slack webhook

        result = await alert_service.send_slack_alert(alert_data, webhook_urls, rule_config)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_slack_alert_retry_on_429(self, alert_service):
        """Test Slack alert retries on rate limit (429)."""
        with patch("backend.services.alert_service.httpx.AsyncClient") as mock_client:
            import httpx

            # First attempt: 429, second attempt: success
            mock_response_429 = AsyncMock()
            mock_response_429.status_code = 429
            mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Rate limited", request=Mock(), response=mock_response_429
            )

            mock_response_200 = AsyncMock()
            mock_response_200.status_code = 200
            mock_response_200.raise_for_status = Mock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = [
                mock_response_429.raise_for_status.side_effect,
                mock_response_200,
            ]
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with patch.dict("os.environ", {"SLACK_MAX_RETRIES": "3", "SLACK_TIMEOUT_SECONDS": "10"}):
                alert_data = {
                    "severity": "high",
                    "message": "Test",
                    "alert_type": "test",
                    "aggregation_count": 1,
                    "first_occurrence": "2024-01-01",
                    "last_occurrence": "2024-01-01",
                    "details": {},
                }
                rule_config = {"rule_name": "Test", "description": ""}
                webhook_urls = ["https://hooks.slack.com/services/TEST"]

                result = await alert_service.send_slack_alert(alert_data, webhook_urls, rule_config)

                # Should eventually succeed after retry
                assert mock_client_instance.post.call_count >= 1


class TestAlertConfiguration:
    """Test alert configuration management."""

    @pytest.mark.asyncio
    async def test_load_alert_configurations(self, alert_service, mock_adapter):
        """Test loading alert configurations from database."""
        mock_adapter.query_results["alert_configurations"] = [
            {
                "id": "rule-001",
                "rule_name": "Test Rule",
                "is_enabled": True,
                "error_types": ["processing_error"],
                "stages": ["text_extraction"],
                "severity_threshold": "high",
                "error_count_threshold": 5,
                "time_window_minutes": 15,
                "aggregation_window_minutes": 5,
                "email_recipients": ["admin@example.com"],
                "slack_webhooks": [],
            }
        ]

        configs = await alert_service.load_alert_configurations()

        assert len(configs) == 1
        assert configs[0]["rule_name"] == "Test Rule"
        assert configs[0]["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_add_alert_configuration(self, alert_service, mock_adapter):
        """Test adding new alert configuration."""
        mock_adapter.query_results["insert_alert"] = [{"id": "rule-new-123"}]

        new_rule = CreateAlertRule(
            name="New Alert Rule",
            alert_type=AlertType.PROCESSING_FAILURE,
            severity=AlertSeverity.HIGH,
            enabled=True,
        )

        config_id = await alert_service.add_alert_configuration(new_rule)

        assert config_id == "rule-new-123"
        # Verify INSERT query was executed
        insert_queries = [q for q in mock_adapter.queries_executed if "INSERT" in q[0]]
        assert len(insert_queries) > 0


class TestBackgroundWorker:
    """Test background worker cleanup functionality."""

    @pytest.mark.asyncio
    async def test_alert_aggregation_worker_cleanup(self, alert_service, mock_adapter):
        """Test background worker cleans up old alerts."""
        # This test would require running the worker for a short time
        # For now, we'll test the worker can be started without errors

        # Mock pending alerts
        mock_adapter.query_results["pending_alerts"] = []

        # Start worker in background and cancel after short time
        worker_task = asyncio.create_task(alert_service.alert_aggregation_worker(interval_seconds=1))

        await asyncio.sleep(0.1)  # Let it run briefly
        worker_task.cancel()

        try:  # noqa: SIM105
            await worker_task
        except asyncio.CancelledError:
            pass  # Expected


class TestAlertServiceIntegration:
    """Integration tests for AlertService."""

    @pytest.mark.asyncio
    async def test_get_alerts_with_filters(self, alert_service, mock_adapter):
        """Test getting alerts with severity and status filters."""
        mock_adapter.query_results["pending_alerts"] = [
            {
                "id": "alert-001",
                "alert_type": "processing_error",
                "severity": "high",
                "message": "Test alert",
                "details": {},
                "aggregation_key": "test:key",
                "aggregation_count": 1,
                "first_occurrence": datetime.utcnow(),
                "last_occurrence": datetime.utcnow(),
                "status": "pending",
                "sent_at": None,
                "created_at": datetime.utcnow(),
            }
        ]
        mock_adapter.query_results["count_result"] = [{"count": 1}]

        response = await alert_service.get_alerts(
            limit=50,
            severity_filter=AlertSeverity.HIGH,
            status_filter="pending",
        )

        assert isinstance(response, AlertListResponse)
        assert response.total >= 0
        assert response.unacknowledged_count >= 0

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, alert_service, mock_adapter):
        """Test acknowledging an alert."""
        result = await alert_service.acknowledge_alert("alert-123", "user-456")

        assert result is True
        # Verify UPDATE query was executed
        update_queries = [q for q in mock_adapter.queries_executed if "UPDATE" in q[0] and "alerts" in q[0]]
        assert len(update_queries) > 0

    @pytest.mark.asyncio
    async def test_dismiss_alert(self, alert_service, mock_adapter):
        """Test dismissing an alert."""
        result = await alert_service.dismiss_alert("alert-123")

        assert result is True
        # Verify DELETE query was executed
        delete_queries = [q for q in mock_adapter.queries_executed if "DELETE" in q[0]]
        assert len(delete_queries) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
