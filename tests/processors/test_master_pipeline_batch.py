"""Batch and concurrency tests for KRMasterPipeline.

These tests focus on the high-level batch helper `process_batch_hardware_waker`.
They rely on the `mock_master_pipeline` fixture from `tests/processors/conftest.py`
so that no real external systems are touched.

Covered scenarios:
- All documents succeed and are aggregated correctly
- Concurrency is limited by `max_concurrent` via asyncio.Semaphore
- Mixed success / failure / exceptions are reported in the batch result
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from backend.pipeline.master_pipeline import KRMasterPipeline

pytestmark = [
    pytest.mark.master_pipeline,
    pytest.mark.batch,
    pytest.mark.concurrency,
]


class TestBatchHardwareWakerSuccess:
    @pytest.mark.asyncio
    async def test_all_documents_success(self, mock_master_pipeline: KRMasterPipeline, tmp_path: Path) -> None:
        """All files succeed and are returned in the successful list.

        We stub `process_single_document_full_pipeline` to always succeed and
        verify the aggregation fields on the batch result.
        """

        pipeline = mock_master_pipeline
        files = [tmp_path / f"file_{i}.pdf" for i in range(3)]
        for f in files:
            f.write_text("dummy")

        calls: list[dict[str, Any]] = []

        async def fake_single(file_path: str, doc_index: int, total_docs: int) -> dict[str, Any]:
            calls.append(
                {
                    "file_path": file_path,
                    "doc_index": doc_index,
                    "total_docs": total_docs,
                }
            )
            return {
                "success": True,
                "document_id": f"doc-{doc_index}",
                "filename": Path(file_path).name,
            }

        async def fake_monitor() -> None:
            # Short-lived monitor so we do not leak background tasks in tests
            await asyncio.sleep(0)

        # Patch methods on pipeline
        pipeline.process_single_document_full_pipeline = fake_single  # type: ignore[assignment]
        pipeline.monitor_hardware = fake_monitor  # type: ignore[assignment]

        result = await pipeline.process_batch_hardware_waker([str(f) for f in files])

        assert result["total_files"] == len(files)
        assert len(result["successful"]) == len(files)
        assert len(result["failed"]) == 0
        assert result["concurrent_documents"] == pipeline.max_concurrent
        assert result["success_rate"] == pytest.approx(100.0)
        assert result["duration"] >= 0

        called_filenames = {c["filename"] for c in result["successful"]}
        assert called_filenames == {f.name for f in files}
        assert len(calls) == len(files)


class TestBatchHardwareWakerConcurrency:
    @pytest.mark.asyncio
    async def test_concurrency_limited_by_max_concurrent(
        self,
        mock_master_pipeline: KRMasterPipeline,
        tmp_path: Path,
    ) -> None:
        """Ensure no more than `max_concurrent` documents run at the same time."""

        pipeline = mock_master_pipeline
        pipeline.max_concurrent = 2

        files = [tmp_path / f"concurrent_{i}.pdf" for i in range(4)]
        for f in files:
            f.write_text("content")

        active = 0
        max_active = 0
        lock = asyncio.Lock()

        async def fake_single(file_path: str, doc_index: int, total_docs: int) -> dict[str, Any]:
            nonlocal active, max_active
            async with lock:
                active += 1
                if active > max_active:
                    max_active = active
            # Small sleep to allow overlap
            await asyncio.sleep(0.02)
            async with lock:
                active -= 1
            return {
                "success": True,
                "document_id": f"doc-{doc_index}",
                "filename": Path(file_path).name,
            }

        async def fake_monitor() -> None:
            await asyncio.sleep(0)

        pipeline.process_single_document_full_pipeline = fake_single  # type: ignore[assignment]
        pipeline.monitor_hardware = fake_monitor  # type: ignore[assignment]

        result = await pipeline.process_batch_hardware_waker([str(f) for f in files])

        assert result["total_files"] == len(files)
        assert len(result["successful"]) == len(files)
        assert max_active <= pipeline.max_concurrent
        # Sanity check that there was at least some overlap
        assert max_active >= 2


class TestBatchHardwareWakerFailures:
    @pytest.mark.asyncio
    async def test_mixed_success_failure_and_exceptions(
        self,
        mock_master_pipeline: KRMasterPipeline,
        tmp_path: Path,
    ) -> None:
        """Batch result should reflect per-file failures and exceptions."""

        pipeline = mock_master_pipeline
        files = [tmp_path / f"mixed_{i}.pdf" for i in range(4)]
        for f in files:
            f.write_text("x")

        async def fake_single(file_path: str, doc_index: int, total_docs: int) -> dict[str, Any]:
            # 1 and 4 succeed, 2 returns failure dict, 3 raises exception
            if doc_index == 2:
                return {
                    "success": False,
                    "error": "explicit failure",
                    "filename": Path(file_path).name,
                }
            if doc_index == 3:
                raise RuntimeError("boom in doc 3")
            return {
                "success": True,
                "document_id": f"doc-{doc_index}",
                "filename": Path(file_path).name,
            }

        async def fake_monitor() -> None:
            await asyncio.sleep(0)

        pipeline.process_single_document_full_pipeline = fake_single  # type: ignore[assignment]
        pipeline.monitor_hardware = fake_monitor  # type: ignore[assignment]

        result = await pipeline.process_batch_hardware_waker([str(f) for f in files])

        assert result["total_files"] == len(files)
        assert len(result["successful"]) == 2
        assert len(result["failed"]) == 2
        assert result["success_rate"] == pytest.approx(2 / 4 * 100)

        errors = [f["error"] for f in result["failed"]]
        assert any("explicit failure" in e for e in errors)
        assert any("boom in doc 3" in e for e in errors)

        filenames_failed = {f["filename"] for f in result["failed"]}
        # Second and third docs failed (indices 1 and 2)
        assert filenames_failed == {files[1].name, files[2].name}
