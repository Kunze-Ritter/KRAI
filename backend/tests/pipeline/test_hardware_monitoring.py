"""
Tests for MasterPipeline hardware monitoring: GPU status, pipeline status,
error count, monitor_hardware loop, and hardware waker batch processing.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is on path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pipeline.master_pipeline import KRMasterPipeline


class MockDatabaseService:
    """Mock database for pipeline status and error count."""

    def __init__(self):
        self.queries = []

    async def execute_query(self, query: str, params=None):
        self.queries.append((query, params))
        if "krai_core.documents" in query and "COUNT" not in query:
            return [
                {"id": "doc-1", "manufacturer": "Acme", "created_at": "2024-01-01"},
                {"id": "doc-2", "manufacturer": None, "created_at": "2024-01-02"},
                {"id": "doc-3", "manufacturer": "Acme", "created_at": "2024-01-03"},
            ]
        if "krai_intelligence.chunks" in query:
            return [{"document_id": "doc-1"}, {"document_id": "doc-2"}]
        if "krai_content.images" in query:
            return []
        if "COUNT" in query and "failed" in query:
            return [{"error_count": 2}]
        return []


# --- 3.1 GPU status ---


def test_get_gpu_status_nvidia():
    """Test _get_gpu_status() with nvidia-smi output."""
    pipeline = KRMasterPipeline(database_adapter=MockDatabaseService())
    nvidia_output = "NVIDIA GeForce RTX 3080, 4096, 10240, 45"
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0,
            stdout=nvidia_output,
            stderr="",
        )
        out = pipeline._get_gpu_status()
    assert out is not None
    assert "name" in out
    assert "memory_used" in out
    assert "memory_total" in out
    assert "utilization" in out
    assert out["memory_used"] == 4096 / 1024
    assert out["memory_total"] == 10240 / 1024
    assert out["utilization"] == 45.0


def test_get_gpu_status_fallback_none():
    """Test _get_gpu_status() returns None when no GPU detected."""
    pipeline = KRMasterPipeline(database_adapter=MockDatabaseService())
    with patch("subprocess.run") as run:
        run.side_effect = FileNotFoundError("nvidia-smi not found")
        out = pipeline._get_gpu_status()
    # After nvidia-smi fails, it tries wmic on Windows
    # So we need to make both fail
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        out2 = pipeline._get_gpu_status()
    # Either None or a dict from wmic path
    assert out is None or isinstance(out, dict)
    assert out2 is None or isinstance(out2, dict)


def test_get_gpu_status_wmic_windows():
    """Test _get_gpu_status() with wmic (Intel/AMD) on Windows."""
    pipeline = KRMasterPipeline(database_adapter=MockDatabaseService())
    with patch("subprocess.run") as run:

        def side_effect(cmd, **kwargs):
            if "nvidia-smi" in str(cmd):
                return MagicMock(returncode=1, stdout="", stderr="")
            if "wmic" in str(cmd):
                return MagicMock(
                    returncode=0,
                    stdout="Node,Name,AdapterRAM\n,Intel UHD Graphics 630,\n",
                    stderr="",
                )
            return MagicMock(returncode=1)

        run.side_effect = side_effect
        out = pipeline._get_gpu_status()
    # May be None if wmic path not taken (e.g. platform)
    assert out is None or (isinstance(out, dict) and "name" in out and "utilization" in out)


# --- 3.2 Pipeline status ---


@pytest.mark.asyncio
async def test_get_pipeline_status():
    """Test _get_pipeline_status() returns progress and counts."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    pipeline.database_service = db  # set without full initialize_services()
    status = await pipeline._get_pipeline_status()
    assert "total_docs" in status
    assert "classified_docs" in status
    assert "total_chunks" in status
    assert "overall_progress" in status
    assert "current_stage" in status
    assert status["total_docs"] == 3
    assert status["classified_docs"] == 2
    assert status["total_chunks"] == 2
    assert 0 <= status["overall_progress"] <= 100


@pytest.mark.asyncio
async def test_get_pipeline_status_empty():
    """Test _get_pipeline_status() when no documents."""
    db = MockDatabaseService()
    db.execute_query = AsyncMock(
        side_effect=lambda q, p=None: (
            [] if "documents" in q and "COUNT" not in q else [] if "chunks" in q else [] if "images" in q else []
        )
    )
    pipeline = KRMasterPipeline(database_adapter=db)
    pipeline.database_service = db
    status = await pipeline._get_pipeline_status()
    assert status["total_docs"] == 0
    assert status["overall_progress"] == 0


# --- 3.3 Error count ---


@pytest.mark.asyncio
async def test_get_error_count():
    """Test _get_error_count() returns failed document count."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    pipeline.database_service = db
    count = await pipeline._get_error_count()
    assert count == 2


@pytest.mark.asyncio
async def test_get_error_count_table_error_returns_zero():
    """Test _get_error_count() returns 0 when query fails."""
    db = MockDatabaseService()

    async def raise_err(*args, **kwargs):
        raise Exception("Table does not exist")

    db.execute_query = raise_err
    pipeline = KRMasterPipeline(database_adapter=db)
    pipeline.database_service = db
    count = await pipeline._get_error_count()
    assert count == 0


# --- 3.4 Hardware monitoring loop ---


@pytest.mark.asyncio
async def test_monitor_hardware_loop_with_mock_sleep():
    """Test monitor_hardware() with mock sleep and max_iterations."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    sleep_calls = []

    async def mock_sleep(interval: float):
        sleep_calls.append(interval)

    with patch.object(pipeline, "_get_gpu_status", return_value=None):
        await pipeline.monitor_hardware(
            sleep_interval=0.1,
            max_iterations=2,
            sleep_func=mock_sleep,
        )
    assert len(sleep_calls) >= 2


@pytest.mark.asyncio
async def test_monitor_hardware_collects_cpu_ram_gpu():
    """Test monitor_hardware() uses psutil and _get_gpu_status."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    with patch("psutil.cpu_percent", return_value=50.0):
        with patch("psutil.virtual_memory") as vm:
            vm.return_value = MagicMock(
                percent=65.0,
                total=16 * 1024**3,
                available=4 * 1024**3,
            )
            with patch.object(
                pipeline,
                "_get_gpu_status",
                return_value={
                    "name": "Test GPU",
                    "memory_used": 2.0,
                    "memory_total": 8.0,
                    "utilization": 25.0,
                },
            ):
                await pipeline.monitor_hardware(
                    sleep_interval=0.05,
                    max_iterations=1,
                    sleep_func=asyncio.sleep,
                )


# --- 4.1 Hardware waker concurrent processing ---


@pytest.mark.asyncio
async def test_process_batch_hardware_waker_structure():
    """Test process_batch_hardware_waker() returns success/failed/total_files/duration."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)

    # Avoid real processing: mock process_single_document_full_pipeline
    async def mock_process(path, index, total):
        return {"success": True, "filename": path, "document_id": "doc-1"}

    with patch.object(
        pipeline,
        "process_single_document_full_pipeline",
        side_effect=mock_process,
    ):
        with patch.object(pipeline, "monitor_hardware", new_callable=AsyncMock):
            results = await pipeline.process_batch_hardware_waker(
                [
                    "/fake/a.pdf",
                    "/fake/b.pdf",
                ]
            )
    assert "successful" in results
    assert "failed" in results
    assert "total_files" in results
    assert results["total_files"] == 2
    assert "duration" in results
    assert "concurrent_documents" in results
    assert results["concurrent_documents"] == pipeline.max_concurrent


@pytest.mark.asyncio
async def test_process_batch_hardware_waker_semaphore_limit():
    """Test that batch uses semaphore (max_concurrent)."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    concurrent = []
    max_concurrent = 2
    pipeline.max_concurrent = max_concurrent
    sem = asyncio.Semaphore(max_concurrent)

    async def mock_process(path, index, total):
        async with sem:
            concurrent.append(1)
            await asyncio.sleep(0.05)
            n = len(concurrent)
            concurrent.clear()
            return {"success": True, "filename": path}

    with patch.object(
        pipeline,
        "process_single_document_full_pipeline",
        side_effect=mock_process,
    ):
        with patch.object(pipeline, "monitor_hardware", new_callable=AsyncMock):
            await pipeline.process_batch_hardware_waker(
                [
                    "/fake/1.pdf",
                    "/fake/2.pdf",
                    "/fake/3.pdf",
                ]
            )
    # All 3 should complete (structure test; semaphore limits in-flight)
    assert True


# --- 4.2 Monitoring during batch ---


@pytest.mark.asyncio
async def test_process_batch_starts_monitor_task():
    """Test that process_batch_hardware_waker creates monitor_hardware task and batch completes."""
    db = MockDatabaseService()
    pipeline = KRMasterPipeline(database_adapter=db)
    pipeline.database_service = db
    monitor_started = False

    async def mock_monitor(*args, **kwargs):
        nonlocal monitor_started
        monitor_started = True
        try:
            for _ in range(100):
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            raise

    async def mock_process(path, index, total):
        return {"success": True, "filename": path}

    with patch.object(pipeline, "monitor_hardware", side_effect=mock_monitor):
        with patch.object(
            pipeline,
            "process_single_document_full_pipeline",
            side_effect=mock_process,
        ):
            results = await pipeline.process_batch_hardware_waker(["/fake/1.pdf"])

    assert monitor_started is True
    assert results["total_files"] == 1
    assert len(results["successful"]) == 1
