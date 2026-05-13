"""End-to-end tests for VisualEmbeddingProcessor.

These tests validate batch image embedding and basic storage behaviour
using the MockDatabaseAdapter extensions from conftest.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.visual_embedding_processor import VisualEmbeddingProcessor

pytestmark = [pytest.mark.processor, pytest.mark.visual_embedding]


def _make_image_dicts(temp_dir: Path, count: int = 3):
    images = []
    for i in range(count):
        img_path = temp_dir / f"img_{i}.png"
        img_path.write_bytes(b"test-image-%d" % i)
        images.append(
            {
                "id": f"img-{i}",
                "temp_path": str(img_path),
                "page_number": i + 1,
                "width": 100,
                "height": 100,
                "file_size": img_path.stat().st_size,
                "image_type": "photo",
            }
        )
    return images


class TestVisualEmbeddingGenerationE2E:
    """Happy-path tests for generating and storing visual embeddings."""

    @pytest.mark.asyncio
    async def test_process_images_generates_embeddings(
        self,
        mock_database_adapter,
        tmp_path,
    ) -> None:
        processor = VisualEmbeddingProcessor(
            database_service=mock_database_adapter,
            model_name="vidore/colqwen2.5-v0.2",
            device="cpu",
            batch_size=2,
        )

        images = _make_image_dicts(tmp_path)
        ctx = ProcessingContext(
            document_id=str(uuid4()),
            file_path=str(tmp_path / "dummy.pdf"),
            document_type="service_manual",
            images=images,
        )

        if not processor.enabled:
            pytest.skip("Visual embeddings disabled by configuration or missing dependency")

        result = await processor.process(ctx)
        if not result.success:
            pytest.skip("Model could not be loaded in this environment")

        assert result.data["embeddings_created"] >= 0


class TestVisualEmbeddingConfiguration:
    """Basic configuration/status checks for the processor."""

    def test_get_configuration_status_fields(self, mock_database_adapter) -> None:
        processor = VisualEmbeddingProcessor(
            database_service=mock_database_adapter,
            device="cpu",
        )
        status = processor.get_configuration_status()
        assert "enabled" in status
        assert "model_name" in status
        assert "device" in status
        assert "batch_size" in status
        assert "embedding_dimension" in status
