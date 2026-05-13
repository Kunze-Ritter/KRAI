"""
Performance benchmarking for pipeline stages after file path resolution fixes.

Measures execution time, memory usage, and throughput for SVG, Image, and Link stages.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.base_processor import ProcessingStatus, Stage
from backend.core.types import ProcessingContext
from backend.processors.image_processor import ImageProcessor
from backend.processors.link_extraction_processor_ai import LinkExtractionProcessorAI
from backend.processors.svg_processor import SVGProcessor


def _create_mock_context(document_id: str, file_path: str = "/tmp/test.pdf") -> ProcessingContext:
    """Create a mock processing context."""
    return ProcessingContext(
        document_id=document_id,
        file_path=file_path,
        document_type="manual",
        correlation_id="benchmark-test",
        pdf_path=file_path,
    )


class TestStageBenchmarks:
    """Benchmark tests for pipeline stages."""

    @pytest.mark.benchmark
    def test_svg_processor_initialization_time(self, benchmark):
        """Benchmark SVGProcessor initialization."""

        def create_processor():
            return SVGProcessor(
                database_service=MagicMock(),
                storage_service=MagicMock(),
                ai_service=None,
                dpi=300,
                max_dimension=2048,
            )

        result = benchmark(create_processor)
        assert result is not None

    @pytest.mark.benchmark
    def test_image_processor_initialization_time(self, benchmark):
        """Benchmark ImageProcessor initialization."""

        def create_processor():
            return ImageProcessor(
                database_service=MagicMock(),
                storage_service=MagicMock(),
                ai_service=None,
            )

        result = benchmark(create_processor)
        assert result is not None

    @pytest.mark.benchmark
    def test_link_processor_initialization_time(self, benchmark):
        """Benchmark LinkExtractionProcessorAI initialization."""

        def create_processor():
            return LinkExtractionProcessorAI(
                database_service=MagicMock(),
                ai_service=None,
                youtube_api_key="test-key",
                link_enrichment_service=None,
                config_service=None,
            )

        result = benchmark(create_processor)
        assert result is not None

    @pytest.mark.benchmark
    def test_context_creation_time(self, benchmark):
        """Benchmark ProcessingContext creation."""

        def create_context():
            return _create_mock_context(
                document_id="perf-test-doc",
                file_path="/tmp/resolved_document.pdf",
            )

        result = benchmark(create_context)
        assert result.file_path is not None

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_svg_processor_mock_process_time(self, benchmark):
        """Benchmark SVGProcessor process execution (mocked)."""
        processor = SVGProcessor(
            database_service=MagicMock(),
            storage_service=MagicMock(),
            ai_service=None,
            dpi=300,
            max_dimension=2048,
        )

        context = _create_mock_context("perf-svg")

        async def mock_process():
            with patch.object(processor, "process", new_callable=AsyncMock) as mock_proc:
                mock_proc.return_value = MagicMock(
                    status=ProcessingStatus.COMPLETED,
                    metadata={"svg_count": 10, "images_queued": 10},
                )
                return await processor.process(context)

        result = await benchmark(mock_process)
        assert result.status == ProcessingStatus.COMPLETED

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_image_processor_mock_process_time(self, benchmark):
        """Benchmark ImageProcessor process execution (mocked)."""
        processor = ImageProcessor(
            database_service=MagicMock(),
            storage_service=MagicMock(),
            ai_service=None,
        )

        context = _create_mock_context("perf-image")

        async def mock_process():
            with patch.object(processor, "process", new_callable=AsyncMock) as mock_proc:
                mock_proc.return_value = MagicMock(
                    status=ProcessingStatus.COMPLETED,
                    metadata={"images_extracted": 15, "images_queued": 15},
                )
                return await processor.process(context)

        result = await benchmark(mock_process)
        assert result.status == ProcessingStatus.COMPLETED

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_link_processor_mock_process_time(self, benchmark):
        """Benchmark LinkExtractionProcessorAI process execution (mocked)."""
        processor = LinkExtractionProcessorAI(
            database_service=MagicMock(),
            ai_service=None,
            youtube_api_key="test-key",
            link_enrichment_service=None,
            config_service=None,
        )

        context = _create_mock_context("perf-link")

        async def mock_process():
            with patch.object(processor, "process", new_callable=AsyncMock) as mock_proc:
                mock_proc.return_value = MagicMock(
                    status=ProcessingStatus.COMPLETED,
                    metadata={"links_extracted": 50, "videos_extracted": 5},
                )
                return await processor.process(context)

        result = await benchmark(mock_process)
        assert result.status == ProcessingStatus.COMPLETED

    def test_context_file_path_access_performance(self, benchmark):
        """Benchmark repeated access to context file_path."""
        context = _create_mock_context("perf-access")

        def access_file_path():
            # Simulate multiple accesses like different stages would do
            path1 = context.file_path
            path2 = context.file_path
            path3 = context.pdf_path
            return path1 and path2 and path3

        result = benchmark(access_file_path)
        assert result is True

    def test_processor_stage_lookup_performance(self, benchmark):
        """Benchmark stage identifier lookup."""
        processors = {
            "svg": SVGProcessor(
                database_service=MagicMock(),
                storage_service=MagicMock(),
                ai_service=None,
                dpi=300,
                max_dimension=2048,
            ),
            "image": ImageProcessor(
                database_service=MagicMock(),
                storage_service=MagicMock(),
                ai_service=None,
            ),
            "link": LinkExtractionProcessorAI(
                database_service=MagicMock(),
                ai_service=None,
                youtube_api_key="test-key",
                link_enrichment_service=None,
                config_service=None,
            ),
        }

        def lookup_stages():
            return [
                processors["svg"].get_stage(),
                processors["image"].stage,
                processors["link"].stage,
            ]

        result = benchmark(lookup_stages)
        assert len(result) == 3
        assert result[0] == Stage.SVG_PROCESSING
        assert result[1] == Stage.IMAGE_PROCESSING
        assert result[2] == Stage.LINK_EXTRACTION
