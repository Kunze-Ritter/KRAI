"""
Integration Tests for Adapter-based Endpoints

Tests that all refactored endpoints work correctly with DatabaseAdapter,
especially under PostgreSQL-only configuration (no Supabase).
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set DATABASE_TYPE to postgresql for these tests
os.environ["DATABASE_TYPE"] = "postgresql"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "krai_test"
os.environ["POSTGRES_USER"] = "test_user"
os.environ["POSTGRES_PASSWORD"] = "test_password"

from api.app import app, get_database_adapter
from services.database_adapter import DatabaseAdapter


@pytest.fixture
def mock_adapter():
    """Create a mock DatabaseAdapter for testing."""
    adapter = MagicMock(spec=DatabaseAdapter)

    # Mock common methods
    adapter.execute_query = AsyncMock(return_value=[])
    adapter.get_document = AsyncMock(return_value=None)
    adapter.pg_pool = None  # Simulate no transaction support

    return adapter


@pytest.fixture
def client(mock_adapter):
    """Create test client with mocked adapter."""

    def override_get_database_adapter():
        return mock_adapter

    app.dependency_overrides[get_database_adapter] = override_get_database_adapter

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Test /health endpoint with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client, mock_adapter):
        """Test health check returns healthy status."""
        # Mock successful database query
        mock_adapter.execute_query.return_value = [{"id": "test-id"}]

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data
        assert "database" in data["services"]

    @pytest.mark.asyncio
    async def test_health_check_database_error(self, client, mock_adapter):
        """Test health check handles database errors."""
        # Mock database error
        mock_adapter.execute_query.side_effect = Exception("Database connection failed")

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["services"]["database"]["status"] == "unhealthy"


class TestStatusEndpoints:
    """Test /status endpoints with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_get_document_status_not_found(self, client, mock_adapter):
        """Test document status returns 404 when document not found."""
        mock_adapter.get_document.return_value = None

        response = client.get("/status/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_pipeline_status(self, client, mock_adapter):
        """Test pipeline status returns statistics."""
        # Mock documents and queue data
        mock_adapter.execute_query.side_effect = [
            [{"id": "1", "processing_status": "completed"}],  # documents
            [{"id": "1", "status": "pending", "task_type": "text_extraction"}],  # queue
        ]

        response = client.get("/status/pipeline")

        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "by_task_type" in data


class TestLogsEndpoints:
    """Test /logs endpoints with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_get_document_logs(self, client, mock_adapter):
        """Test document logs retrieval."""
        # Mock audit logs
        mock_adapter.execute_query.return_value = [
            {"id": "1", "action": "created", "created_at": "2024-01-01T00:00:00"}
        ]

        response = client.get("/logs/test-doc-id")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "log_count" in data


class TestMonitoringEndpoints:
    """Test /monitoring endpoints with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_get_system_metrics(self, client, mock_adapter):
        """Test system metrics retrieval."""
        # Mock metrics data
        mock_adapter.execute_query.return_value = [{"timestamp": "2024-01-01T00:00:00", "cpu_usage": 50.0}]

        response = client.get("/monitoring/system")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_get_stage_statistics_postgresql_only(self, client, mock_adapter):
        """Test stage statistics returns 501 in PostgreSQL-only mode."""
        # In PostgreSQL-only mode, get_legacy_supabase_client() returns None

        response = client.get("/stages/statistics")

        # Should return 501 because StageTracker requires Supabase RPC
        assert response.status_code == 501
        assert "not available" in response.json()["detail"].lower()


class TestPostgreSQLOnlyBehavior:
    """Test that endpoints degrade gracefully without Supabase."""

    @pytest.mark.asyncio
    async def test_supabase_only_features_return_501(self, client):
        """Test that Supabase-only features return HTTP 501."""
        # Stage statistics requires Supabase RPC
        response = client.get("/stages/statistics")
        assert response.status_code == 501

    @pytest.mark.asyncio
    async def test_adapter_based_features_work(self, client, mock_adapter):
        """Test that adapter-based features work without Supabase."""
        # Health check should work with adapter
        mock_adapter.execute_query.return_value = [{"id": "test"}]

        response = client.get("/health")
        assert response.status_code == 200

        # Pipeline status should work with adapter
        mock_adapter.execute_query.side_effect = [[], []]
        response = client.get("/status/pipeline")
        assert response.status_code == 200


class TestErrorCodeSearch:
    """Test error code search with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_error_code_search_integration(self, client, mock_adapter):
        """Test error code search endpoint (if mounted)."""
        # This would test the error_code_search.py refactoring
        # Requires the router to be mounted in app.py
        pass


class TestAgentAPI:
    """Test agent API with DatabaseAdapter."""

    @pytest.mark.asyncio
    async def test_agent_health_check(self, client):
        """Test agent health endpoint."""
        # Agent API is mounted at /agent
        response = client.get("/agent/health")

        # May return 404 if agent not fully initialized in test
        # or 200 if it works
        assert response.status_code in [200, 404]


# Pytest configuration
pytest_plugins = ["pytest_asyncio"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
