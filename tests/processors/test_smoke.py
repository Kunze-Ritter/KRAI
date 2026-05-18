from uuid import uuid4

import pytest

from backend.core.base_processor import ProcessingContext
from backend.processors.text_processor_optimized import OptimizedTextProcessor
from backend.processors.upload_processor import UploadProcessor

pytestmark = pytest.mark.smoke


@pytest.mark.asyncio
async def test_upload_processor_smoke(mock_database_adapter, sample_pdf_files, processor_test_config):
    processor = UploadProcessor(
        database_adapter=mock_database_adapter,
        max_file_size_mb=processor_test_config["max_file_size_mb"],
    )

    valid_pdf = sample_pdf_files["valid_pdf"]
    context = ProcessingContext(
        document_id=str(uuid4()),
        file_path=str(valid_pdf["path"]),
        document_type="service_manual",
    )

    result = await processor.process(context)

    assert result.success is True
    assert result.data is not None
    assert "document_id" in result.data


@pytest.mark.asyncio
async def test_optimized_text_processor_smoke(mock_database_adapter, sample_pdf_files, processor_test_config):
    processor = OptimizedTextProcessor(
        database_service=mock_database_adapter,
        config_service=None,
    )

    valid_pdf = sample_pdf_files["valid_pdf"]
    context = ProcessingContext(
        document_id=str(uuid4()),
        file_path=str(valid_pdf["path"]),
        metadata={"filename": valid_pdf["path"].name},
    )

    result = await processor.process(context)

    assert result.success is True
    assert isinstance(result.data, dict)
