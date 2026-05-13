"""Master pipeline unit and configuration tests.

This module replaces the legacy manual test harness with a modern pytest-based
suite focused on KRMasterPipeline orchestration helpers:

- Initialization and configuration (max_concurrent, services, processors)
- Processor mapping for the canonical Stage enum
- Single- and multi-stage execution helpers (run_single_stage, run_stages)
- Stage/status helper (`get_available_stages`, `get_stage_status`)

Heavy end-to-end flows and real-database tests live in dedicated E2E and
integration modules; these tests stay fast and rely only on the shared
`mock_master_pipeline` + `mock_database_adapter` fixtures.
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.base_processor import Stage
from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = [pytest.mark.master_pipeline, pytest.mark.unit]


class TestMasterPipelineConfiguration:
    """Basic initialization and configuration tests for KRMasterPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_initialization_with_mocks(
        self,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """Pipeline fixture should provide initialized services and processors.

        This verifies that the `mock_master_pipeline` fixture wires services into
        the KRMasterPipeline instance without touching real env files or
        external systems.
        """

        pipeline = mock_master_pipeline

        # Core services
        assert pipeline.database_service is not None
        assert pipeline.storage_service is not None
        assert pipeline.ai_service is not None
        assert pipeline.config_service is not None
        assert pipeline.features_service is not None

        # Processor registry
        assert isinstance(pipeline.processors, dict)
        assert "upload" in pipeline.processors
        assert "text" in pipeline.processors
        assert "embedding" in pipeline.processors
        assert pipeline.processors["upload"] is not None

        # Concurrency settings must be sane and >= 4 as in implementation
        assert pipeline.max_concurrent >= 4

    def test_get_available_stages_matches_enum(self) -> None:
        """`get_available_stages` should expose all Stage enum values."""

        pipeline = KRMasterPipeline()
        available = pipeline.get_available_stages()

        expected = [stage.value for stage in Stage]
        assert sorted(available) == sorted(expected)


class TestMasterPipelineProcessors:
    """Tests around processor mapping and availability."""

    def test_processor_mapping_covers_core_stages(
        self,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """Ensure the processor registry has handlers for all core stages.

        We intentionally focus on the core runtime keys used by
        `run_single_stage` and `process_single_document_full_pipeline`.
        """

        pipeline = mock_master_pipeline
        processors = pipeline.processors

        required_keys = [
            "upload",
            "text",
            "table",
            "svg",
            "image",
            "visual_embedding",
            "classification",
            "chunk_prep",
            "links",
            "metadata",
            "storage",
            "embedding",
            "search",
        ]

        for key in required_keys:
            assert key in processors, f"Processor key '{key}' missing from registry"

    @pytest.mark.asyncio
    async def test_run_single_stage_invalid_stage_returns_error(
        self,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """Passing an invalid stage name should produce a clean error dict."""

        result = await mock_master_pipeline.run_single_stage("doc-1", "not_a_real_stage")

        assert not result["success"]
        assert "Invalid stage" in result["error"]

    @pytest.mark.asyncio
    async def test_run_single_stage_executes_mapped_processor(
        self,
        mock_master_pipeline: KRMasterPipeline,
        mock_database_adapter,
    ) -> None:
        """`run_single_stage` should call the mapped processor with a context.

        We stub the embedding processor with an async stub so that we exercise
        the mapping and context construction without running the real stage
        implementation.
        """

        pipeline = mock_master_pipeline

        # Seed a minimal document so that get_document() succeeds
        document_id = "doc-embedding-1"
        mock_database_adapter.documents[document_id] = {
            "id": document_id,
            "document_type": "service_manual",
        }

        # Replace embedding processor with an async stub
        calls: dict[str, Any] = {"contexts": []}

        async def _fake_process(context):  # type: ignore[override]
            calls["contexts"].append(context)

            # Mimic a ProcessingResult-like object
            class _Result:
                success = True
                data: dict[str, Any] = {"embeddings_created": 0}

            return _Result()

        stub = AsyncMock(side_effect=_fake_process)

        # The processor object only needs a .process coroutine
        class _Processor:
            async def process(self, context):  # type: ignore[override]
                return await stub(context)

        pipeline.processors["embedding"] = _Processor()
        pipeline.database_service = mock_database_adapter

        result = await pipeline.run_single_stage(document_id, Stage.EMBEDDING)

        assert result["success"] is True
        assert result["stage"] == Stage.EMBEDDING.value
        assert result["processor"] == "embedding"
        assert len(calls["contexts"]) == 1
        ctx = calls["contexts"][0]
        assert getattr(ctx, "document_id") == document_id
        assert getattr(ctx, "document_type") == "service_manual"


class TestMasterPipelineStageExecution:
    """Tests for multi-stage orchestration helpers (run_stages/get_stage_status)."""

    @pytest.mark.asyncio
    async def test_run_stages_stops_on_failure_when_flag_false(
        self,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """When `force_continue_on_errors` is False, pipeline stops on first fail."""

        pipeline = mock_master_pipeline
        pipeline.force_continue_on_errors = False

        # Stub run_single_stage to simulate success -> failure -> success
        async def _run_single_stage(document_id: str, stage: Any) -> dict[str, Any]:
            if stage == "ok-1":
                return {"success": True, "stage": "ok-1"}
            if stage == "fail":
                return {"success": False, "stage": "fail", "error": "boom"}
            return {"success": True, "stage": "ok-2"}

        pipeline.run_single_stage = _run_single_stage  # type: ignore[assignment]

        stages: list[Any] = ["ok-1", "fail", "ok-2"]
        results = await pipeline.run_stages("doc-1", stages)

        assert results["total_stages"] == 3
        assert results["successful"] == 1
        assert results["failed"] == 1
        # Only two stage results should be recorded (stopped after first failure)
        assert len(results["stage_results"]) == 2

    @pytest.mark.asyncio
    async def test_run_stages_continues_on_failure_when_flag_true(
        self,
        mock_master_pipeline: KRMasterPipeline,
    ) -> None:
        """When `force_continue_on_errors` is True, all stages are attempted."""

        pipeline = mock_master_pipeline
        pipeline.force_continue_on_errors = True

        async def _run_single_stage(document_id: str, stage: Any) -> dict[str, Any]:
            return {"success": stage != "fail", "stage": stage}

        pipeline.run_single_stage = _run_single_stage  # type: ignore[assignment]

        stages: list[Any] = ["ok-1", "fail", "ok-2"]
        results = await pipeline.run_stages("doc-1", stages)

        assert results["total_stages"] == 3
        assert results["successful"] == 2
        assert results["failed"] == 1
        assert len(results["stage_results"]) == 3

    @pytest.mark.asyncio
    async def test_get_stage_status_handles_missing_document_gracefully(
        self,
    ) -> None:
        """`get_stage_status` should not raise when the document is missing."""

        pipeline = KRMasterPipeline()

        class _FakeDB:
            async def execute_query(self, *_args, **_kwargs):  # type: ignore[override]
                return []

        pipeline.database_service = _FakeDB()

        status = await pipeline.get_stage_status("non-existent-doc")

        assert status["document_id"] == "non-existent-doc"
        assert status["stage_status"] == {}
        assert status["found"] is False
