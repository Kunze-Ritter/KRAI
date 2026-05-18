"""
Processor Test Configuration and Fixtures

Comprehensive pytest fixtures for processor testing including:
- Mock DatabaseAdapter with all required methods
- Sample PDF files for various test scenarios
- Temporary test PDF creation
- Mock StageTracker
- Processor test configuration
- Cleanup utilities

This module provides session- and function-scoped fixtures for
testing UploadProcessor, DocumentProcessor, and OptimizedTextProcessor.
"""

import hashlib
import logging
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.core.base_processor import ProcessingContext
from backend.core.data_models import DocumentModel
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.processors.stage_tracker import StageTracker
from backend.services.database_adapter import DatabaseAdapter

# Test configuration
PROCESSOR_TEST_CONFIG = {
    "max_file_size_mb": 100,
    "allowed_extensions": [".pdf"],
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "enable_ocr_fallback": True,
    "enable_hierarchical_chunking": True,
    "pdf_engine": "pymupdf",
    "structured_line_cap": 1000,
    "test_timeout": 600,
    "temp_dir_suffix": "krai_processor_tests",
}


@pytest.fixture(scope="function")
async def mock_database_adapter() -> AsyncGenerator[DatabaseAdapter, None]:
    """
    Mock DatabaseAdapter with all required methods for processor testing.

    Provides realistic mock responses for:
    - Document operations (create, get_by_hash, update)
    - Processing queue operations
    - RPC calls for StageTracker
    - Chunk operations
    - Generic query execution
    """

    class MockDatabaseAdapter(DatabaseAdapter):
        """Mock implementation of DatabaseAdapter for testing."""

        def __init__(self):
            # Skip ABC initialization to avoid abstract method errors
            self.documents = {}  # Mock storage
            self.chunks = {}  # Mock storage (represents vw_chunks in tests)
            self.links = {}  # Mock storage for link records
            self.videos = {}  # Mock storage for video records
            self.error_codes = {}  # Mock storage for error_code records
            self.parts_catalog = {}  # Mock storage for parts_catalog records
            self.document_products = {}  # Mock storage for document_products relations
            self.products = {}  # Mock storage for products
            self.manufacturers = {}  # Mock storage for manufacturers
            self.product_series = {}  # Mock storage for product_series
            self.structured_tables = {}
            self.embeddings_v2 = {}
            # Legacy-style embedding tracking to simulate vw_chunks embeddings
            self.legacy_embeddings = {}
            self.processing_queue = []  # Mock storage
            self.logger = logging.getLogger("mock_database_adapter")

        async def connect(self) -> None:
            """Mock connect - does nothing."""
            pass

        async def test_connection(self) -> bool:
            """Mock test connection - always returns True."""
            return True

        async def disconnect(self) -> None:
            """Mock disconnect - does nothing."""
            pass

        async def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
            """Mock fetch_one - returns first row from execute_query-style result or None."""
            rows = await self.fetch_all(query, params)
            return rows[0] if rows else None

        async def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
            """Mock fetch_all - returns list of dicts (mock execute_query returns list in practice)."""
            result = await self.execute_query(
                query, list(params.values()) if isinstance(params, dict) else (params or [])
            )
            return result if isinstance(result, list) else []

        async def insert_chunk(self, chunk_data: dict[str, Any]) -> str:
            """Mock insert_chunk - insert chunk from dict."""
            return await self.create_chunk_async(chunk_data)

        async def insert_table(self, table_data: dict[str, Any]) -> str:
            """Mock insert_table - insert structured table."""
            return await self.create_structured_table(table_data)

        async def create_unified_embedding(
            self,
            source_id: str,
            source_type: str,
            embedding: list[float],
            model_name: str,
            embedding_context: str | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> str:
            """Mock create_unified_embedding - delegates to create_embedding_v2."""
            return await self.create_embedding_v2(
                source_id=source_id,
                source_type=source_type,
                embedding=embedding,
                model_name=model_name,
                embedding_context=embedding_context or "",
                metadata=metadata or {},
            )

        async def insert_link(self, link_data: dict[str, Any]) -> str:
            """Mock insert_link - insert link record."""
            return await self.create_link(link_data)

        async def insert_part(self, part_data: dict[str, Any]) -> str:
            """Mock insert_part - insert part record."""
            return await self.create_part(part_data)

        async def start_stage(self, document_id: str, stage: str, metadata: dict[str, Any] | None = None) -> bool:
            """Mock start_stage - always success."""
            self.logger.info(f"Mock start_stage: doc={document_id}, stage={stage}")
            return True

        async def complete_stage(self, document_id: str, stage: str, metadata: dict[str, Any] | None = None) -> bool:
            """Mock complete_stage - always success."""
            self.logger.info(f"Mock complete_stage: doc={document_id}, stage={stage}")
            return True

        async def fail_stage(
            self, document_id: str, stage: str, error: str, metadata: dict[str, Any] | None = None
        ) -> bool:
            """Mock fail_stage - always success."""
            self.logger.info(f"Mock fail_stage: doc={document_id}, stage={stage}, error={error}")
            return True

        async def skip_stage(
            self, document_id: str, stage: str, reason: str, metadata: dict[str, Any] | None = None
        ) -> bool:
            """Mock skip_stage - always success."""
            self.logger.info(f"Mock skip_stage: doc={document_id}, stage={stage}, reason={reason}")
            return True

        async def get_stage_status(self, document_id: str, stage: str) -> dict[str, Any] | None:
            """Mock get_stage_status - returns completed for known stages."""
            return {"document_id": document_id, "stage": stage, "status": "completed", "progress": 100.0}

        async def create_document(self, document: DocumentModel) -> str:
            """Mock create document with deduplication."""
            doc_id = str(uuid4())
            self.documents[doc_id] = {
                "id": doc_id,
                "filename": document.filename,
                "file_hash": document.file_hash,
                "file_size": document.file_size,
                "document_type": document.document_type,
                "manufacturer": document.manufacturer,
                "language": document.language,
                "processing_status": (
                    document.processing_status.value
                    if hasattr(document.processing_status, "value")
                    else document.processing_status
                ),
                "status": "uploaded",
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            }
            return doc_id

        async def get_document(self, document_id: str) -> dict[str, Any] | None:
            """Mock get document by ID."""
            return self.documents.get(document_id)

        async def get_document_by_hash(self, file_hash: str) -> dict[str, Any] | None:
            """Mock get document by hash for deduplication."""
            for doc in self.documents.values():
                if doc.get("file_hash") == file_hash:
                    return doc
            return None

        async def update_document(self, document_id: str, updates: dict[str, Any]) -> bool:
            """Mock update document."""
            if document_id in self.documents:
                self.documents[document_id].update(updates)
                return True
            return False

        async def create_processing_queue_item(self, item) -> str:
            """Mock create processing queue item."""
            item_id = str(uuid4())
            self.processing_queue.append(
                {
                    "id": item_id,
                    "document_id": item.document_id,
                    "stage": item.stage,
                    "status": "pending",
                    "created_at": item.created_at,
                }
            )
            return item_id

        async def create_chunk(self, chunk) -> str:
            """Mock create chunk."""
            chunk_id = str(uuid4())
            self.chunks[chunk_id] = {
                "id": chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "char_count": chunk.char_count,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "chunk_type": chunk.chunk_type,
                "metadata": chunk.metadata or {},
                "created_at": chunk.created_at,
            }
            return chunk_id

        async def create_chunk_async(self, chunk_data: dict[str, Any]) -> str:
            """Mock create chunk from dictionary."""
            chunk_id = str(uuid4())
            self.chunks[chunk_id] = chunk_data
            return chunk_id

        async def get_chunk_by_document_and_index(self, document_id: str, chunk_index: int) -> dict[str, Any] | None:
            """Mock get chunk by document and index."""
            for chunk in self.chunks.values():
                if chunk.get("document_id") == document_id and chunk.get("chunk_index") == chunk_index:
                    return chunk
            return None

        async def execute_query(self, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
            """Mock execute query - returns realistic counts for selected views.

            This is used primarily by SearchProcessor tests to count records in
            vw_chunks, vw_embeddings, vw_links and vw_videos, as well as by
            stage statistics helpers.
            """
            params = params or []
            q = query.lower()

            # Stage statistics view used by some diagnostics
            if "vw_stage_statistics" in q:
                return [
                    {
                        "stage_name": "upload",
                        "pending_count": 0,
                        "processing_count": 0,
                        "completed_count": 1,
                        "failed_count": 0,
                        "skipped_count": 0,
                        "avg_duration_seconds": 5.0,
                    },
                    {
                        "stage_name": "text_extraction",
                        "pending_count": 0,
                        "processing_count": 0,
                        "completed_count": 1,
                        "failed_count": 0,
                        "skipped_count": 0,
                        "avg_duration_seconds": 15.0,
                    },
                ]

            # SearchProcessor record counting helpers
            if "from vw_chunks" in q and params:
                document_id = params[0]
                count = len([c for c in self.chunks.values() if c.get("document_id") == document_id])
                return [{"count": count}]

            if "from vw_embeddings" in q and params:
                document_id = params[0]
                count = 0
                for emb in self.embeddings_v2.values():
                    metadata = emb.get("metadata") or {}
                    if metadata.get("document_id") == document_id:
                        count += 1
                return [{"count": count}]

            if "from vw_links" in q and params:
                document_id = params[0]
                count = len([l for l in getattr(self, "links", {}).values() if l.get("document_id") == document_id])
                return [{"count": count}]

            if "from vw_videos" in q and params:
                document_id = params[0]
                count = len([v for v in getattr(self, "videos", {}).values() if v.get("document_id") == document_id])
                return [{"count": count}]

            # Legacy vw_documents helper used by some tests
            if "vw_documents" in q and params:
                document_id = params[0]
                if document_id in self.documents:
                    return [{"stage_status": {"upload": "completed", "text_extraction": "completed"}}]

            return []

        async def rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
            """Mock RPC calls for StageTracker and embedding/search helpers."""
            params = params or {}

            if function_name == "krai_core.start_stage":
                self.logger.info(f"Mock RPC: start_stage {params}")
                return True
            if function_name == "krai_core.update_stage_progress":
                self.logger.info(f"Mock RPC: update_stage_progress {params}")
            elif function_name == "krai_core.complete_stage":
                self.logger.info(f"Mock RPC: complete_stage {params}")
                return True
            elif function_name == "krai_core.fail_stage":
                self.logger.info(f"Mock RPC: fail_stage {params}")
                return True
            elif function_name == "krai_core.skip_stage":
                self.logger.info(f"Mock RPC: skip_stage {params}")
                return True
            elif function_name == "krai_core.get_document_progress":
                return 100.0  # Mock 100% progress
            elif function_name == "krai_core.get_current_stage":
                return "completed"
            elif function_name == "krai_core.can_start_stage":
                return True
            elif function_name == "match_chunks":
                # Used by EmbeddingProcessor.search_similar via Supabase RPC
                query_embedding = params.get("query_embedding") or []
                match_threshold = float(params.get("match_threshold", 0.7))
                match_count = int(params.get("match_count", 10))
                filter_document_id = params.get("filter_document_id")

                results = await self.search_embeddings(
                    query_embedding=query_embedding,
                    limit=match_count,
                    match_threshold=match_threshold,
                    match_count=match_count,
                    document_id=filter_document_id,
                )

                class _RpcResult:
                    def __init__(self, data):
                        self.data = data

                return _RpcResult(results)
            else:
                self.logger.warning(f"Mock RPC: Unknown function {function_name}")
                return None

        async def execute_rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
            """Alias for rpc() to match StageTracker usage."""
            return await self.rpc(function_name, params)

        # Implement other abstract methods with minimal functionality
        async def create_manufacturer(self, manufacturer) -> str:
            return str(uuid4())

        async def get_manufacturer_by_name(self, name: str) -> dict[str, Any] | None:
            return None

        async def create_product_series(self, series) -> str:
            return str(uuid4())

        async def get_product_series_by_name(self, name: str, manufacturer_id: str) -> dict[str, Any] | None:
            return None

        async def create_product(self, product) -> str:
            return str(uuid4())

        async def get_product_by_model(self, model_number: str, manufacturer_id: str) -> dict[str, Any] | None:
            return None

        async def create_image(self, image) -> str:
            return str(uuid4())

        async def get_image_by_hash(self, image_hash: str) -> dict[str, Any] | None:
            return None

        async def get_images_by_document(self, document_id: str) -> list[dict[str, Any]]:
            return []

        async def create_intelligence_chunk(self, chunk) -> str:
            return str(uuid4())

        async def create_embedding(self, embedding) -> str:
            return str(uuid4())

        async def get_embedding_by_chunk_id(self, chunk_id: str) -> dict[str, Any] | None:
            return None

        async def get_embeddings_by_chunk_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
            return [emb for emb in self.embeddings_v2.values() if emb.get("source_id") in chunk_ids]

        async def search_embeddings(
            self,
            query_embedding: list[float],
            limit: int = 10,
            match_threshold: float = 0.7,
            match_count: int = 10,
            document_id: str | None = None,
        ) -> list[dict[str, Any]]:
            """In-memory cosine-similarity search over embeddings_v2.

            Returns a list of dictionaries compatible with match_chunks-style
            RPC results, including chunk_id, content, similarity and metadata.
            """

            if not query_embedding or not self.embeddings_v2:
                return []

            # Local helper to avoid importing numpy
            def _cosine(a: list[float], b: list[float]) -> float:
                if not a or not b or len(a) != len(b):
                    return 0.0
                dot = 0.0
                norm_a = 0.0
                norm_b = 0.0
                for x, y in zip(a, b):
                    dot += x * y
                    norm_a += x * x
                    norm_b += y * y
                if norm_a == 0.0 or norm_b == 0.0:
                    return 0.0
                return dot / (norm_a**0.5 * norm_b**0.5)

            results: list[dict[str, Any]] = []
            for emb in self.embeddings_v2.values():
                emb_vec = emb.get("embedding")
                if not emb_vec:
                    continue

                metadata = emb.get("metadata") or {}
                # Optional document_id filter stored in metadata
                if document_id is not None and metadata.get("document_id") != document_id:
                    continue

                score = _cosine(query_embedding, emb_vec)
                if score < float(match_threshold):
                    continue

                results.append(
                    {
                        "chunk_id": emb.get("source_id"),
                        "content": emb.get("embedding_context", ""),
                        "similarity": score,
                        "metadata": metadata,
                    }
                )

            # Sort by similarity desc and apply limit/match_count
            results.sort(key=lambda r: r.get("similarity", 0.0), reverse=True)
            max_results = match_count or limit or 10
            return results[:max_results]

        async def create_error_code(self, error_code) -> str:
            error_code_id = str(uuid4())
            self.error_codes[error_code_id] = {
                "id": error_code_id,
                "document_id": error_code.document_id,
                "manufacturer": error_code.manufacturer,
                "code": error_code.code,
                "description": error_code.description,
                "solution": error_code.solution,
                "page_number": error_code.page_number,
                "severity": error_code.severity,
                "category": error_code.category,
                "confidence": error_code.confidence,
                "created_at": error_code.created_at,
            }
            return error_code_id

        async def get_error_codes_by_document(self, document_id: str) -> list[dict[str, Any]]:
            return [ec for ec in self.error_codes.values() if ec.get("document_id") == document_id]

        async def create_part(self, part_data: dict[str, Any]) -> str:
            part_id = str(uuid4())
            self.parts_catalog[part_id] = dict(part_data)
            self.parts_catalog[part_id]["id"] = part_id
            return part_id

        async def get_part_by_number_and_manufacturer(
            self, part_number: str, manufacturer_id: str
        ) -> dict[str, Any] | None:
            for part in self.parts_catalog.values():
                if part.get("part_number") == part_number and part.get("manufacturer_id") == manufacturer_id:
                    return part
            return None

        async def get_part_by_number(self, part_number: str) -> dict[str, Any] | None:
            for part in self.parts_catalog.values():
                if part.get("part_number") == part_number:
                    return part
            return None

        async def update_part(self, part_id: str, updates: dict[str, Any]) -> bool:
            if part_id in self.parts_catalog:
                self.parts_catalog[part_id].update(updates)
                return True
            return False

        async def create_product_series(self, series) -> str:
            series_id = str(uuid4())
            self.product_series[series_id] = {
                "id": series_id,
                "series_name": series.series_name,
                "model_pattern": series.model_pattern,
                "series_description": series.series_description,
                "manufacturer_id": series.manufacturer_id,
                "created_at": series.created_at,
            }
            return series_id

        async def get_product_series_by_name_and_pattern(
            self, series_name: str, model_pattern: str, manufacturer_id: str
        ) -> dict[str, Any] | None:
            for series in self.product_series.values():
                if (
                    series.get("series_name") == series_name
                    and series.get("model_pattern") == model_pattern
                    and series.get("manufacturer_id") == manufacturer_id
                ):
                    return series
            return None

        async def get_products_without_series(self, manufacturer_id: str | None = None) -> list[dict[str, Any]]:
            products_without_series = []
            for product in self.products.values():
                if not product.get("series_id"):
                    if manufacturer_id is None or product.get("manufacturer_id") == manufacturer_id:
                        products_without_series.append(product)
            return products_without_series

        async def get_products_by_series(self, series_id: str) -> list[dict[str, Any]]:
            return [p for p in self.products.values() if p.get("series_id") == series_id]

        async def get_product(self, product_id: str) -> dict[str, Any] | None:
            return self.products.get(product_id)

        async def update_product(self, product_id: str, updates: dict[str, Any]) -> bool:
            if product_id in self.products:
                self.products[product_id].update(updates)
                return True
            return False

        async def get_manufacturer(self, manufacturer_id: str) -> dict[str, Any] | None:
            return self.manufacturers.get(manufacturer_id)

        async def log_search_analytics(self, analytics) -> str:
            return str(uuid4())

        async def update_processing_queue_item(self, item_id: str, updates: dict[str, Any]) -> bool:
            return True

        async def log_audit_event(self, event) -> str:
            return str(uuid4())

        async def get_system_status(self) -> dict[str, Any]:
            return {"status": "healthy"}

        async def count_chunks_by_document(self, document_id: str) -> int:
            return len([c for c in self.chunks.values() if c.get("document_id") == document_id])

        async def count_images_by_document(self, document_id: str) -> int:
            return 0

        async def get_intelligence_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
            return [chunk for chunk in self.chunks.values() if chunk.get("document_id") == document_id]

        async def check_embedding_exists(self, chunk_id: str) -> bool:
            return False

        async def count_links_by_document(self, document_id: str) -> int:
            return 0

        async def create_link(self, link_data: dict[str, Any]) -> str:
            link_id = str(uuid4())
            self.links[link_id] = dict(link_data)
            self.links[link_id]["id"] = link_id
            return link_id

        async def create_video(self, video_data: dict[str, Any]) -> str:
            video_id = str(uuid4())
            self.videos[video_id] = dict(video_data)
            self.videos[video_id]["id"] = video_id
            return video_id

        async def create_image(self, image) -> str:
            image_id = str(uuid4())
            # Store image data in mock storage
            self.images = getattr(self, "images", {})
            self.images[image_id] = {
                "id": image_id,
                "document_id": image.document_id,
                "storage_url": image.storage_url,
                "storage_path": image.storage_path,
                "file_hash": image.file_hash,
                "ai_description": image.ai_description,
                "ocr_text": image.ocr_text,
                "ocr_confidence": image.ocr_confidence,
                "ai_confidence": image.ai_confidence,
                "context_caption": image.context_caption,
                "page_header": image.page_header,
                "figure_reference": image.figure_reference,
                "related_error_codes": image.related_error_codes,
                "related_products": image.related_products,
                "surrounding_paragraphs": image.surrounding_paragraphs,
                "related_chunks": image.related_chunks,
                "created_at": image.created_at,
            }
            return image_id

        async def create_image_queue_entry(self, queue_data: dict[str, Any]) -> str:
            """Mock create image queue entry for storage tasks."""
            queue_id = str(uuid4())
            self.image_queue = getattr(self, "image_queue", {})
            self.image_queue[queue_id] = dict(queue_data)
            self.image_queue[queue_id]["id"] = queue_id
            return queue_id

        async def get_image_queue_entries(self, document_id: str) -> list[dict[str, Any]]:
            """Mock get image queue entries by document."""
            self.image_queue = getattr(self, "image_queue", {})
            return [entry for entry in self.image_queue.values() if entry.get("document_id") == document_id]

        async def create_svg_queue_entry(self, queue_data: dict[str, Any]) -> str:
            """Mock create SVG queue entry for storage tasks."""
            queue_id = str(uuid4())
            self.svg_queue = getattr(self, "svg_queue", {})
            self.svg_queue[queue_id] = dict(queue_data)
            self.svg_queue[queue_id]["id"] = queue_id
            return queue_id

        async def get_svg_queue_entries(self, document_id: str) -> list[dict[str, Any]]:
            """Mock get SVG queue entries by document."""
            self.svg_queue = getattr(self, "svg_queue", {})
            return [entry for entry in self.svg_queue.values() if entry.get("document_id") == document_id]

        async def create_chunk(self, chunk) -> str:
            chunk_id = str(uuid4())
            self.chunks[chunk_id] = {
                "id": chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "char_count": chunk.char_count,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "chunk_type": chunk.chunk_type,
                "metadata": chunk.metadata or {},
                "created_at": chunk.created_at,
            }
            return chunk_id

        async def create_embedding(self, embedding) -> str:
            embedding_id = str(uuid4())
            self.embeddings_v2[embedding_id] = {
                "id": embedding_id,
                "source_id": embedding.source_id,
                "source_type": embedding.source_type,
                "embedding": embedding.embedding,
                "model_name": embedding.model_name,
                "embedding_context": embedding.embedding_context,
                "metadata": embedding.metadata or {},
            }
            return embedding_id

        async def create_print_defect(self, defect) -> str:
            return str(uuid4())

        async def create_structured_table(self, table_record: dict[str, Any]) -> str:
            """Mock create structured table record for krai_intelligence.structured_tables."""
            table_id = table_record.get("id") or str(uuid4())
            stored = dict(table_record)
            stored["id"] = table_id
            self.structured_tables[table_id] = stored
            return table_id

        async def get_structured_tables_by_document(self, document_id: str) -> list[dict[str, Any]]:
            """Mock get all structured tables for a document."""
            return [table for table in self.structured_tables.values() if table.get("document_id") == document_id]

        async def create_embedding_v2(
            self,
            source_id: str,
            source_type: str,
            embedding: list[float],
            model_name: str,
            embedding_context: str,
            metadata: dict[str, Any],
        ) -> str:
            """Mock create embedding_v2 record for krai_intelligence.embeddings_v2."""
            embedding_id = str(uuid4())
            self.embeddings_v2[embedding_id] = {
                "id": embedding_id,
                "source_id": source_id,
                "source_type": source_type,
                "embedding": embedding,
                "model_name": model_name,
                "embedding_context": embedding_context,
                "metadata": metadata or {},
            }
            # Track legacy-style mapping from source_id to embedding for tests
            self.legacy_embeddings[source_id] = {
                "id": embedding_id,
                "embedding": embedding,
                "source_type": source_type,
                "metadata": metadata or {},
            }
            return embedding_id

        async def get_embeddings_by_source(
            self,
            source_id: str,
            source_type: str,
        ) -> list[dict[str, Any]]:
            """Mock get embeddings_v2 records by source reference."""
            return [
                emb
                for emb in self.embeddings_v2.values()
                if emb.get("source_id") == source_id and emb.get("source_type") == source_type
            ]

        async def get_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
            """Return all chunks for a document, ordered by chunk_index where present."""
            chunks = [c for c in self.chunks.values() if c.get("document_id") == document_id]
            return sorted(chunks, key=lambda c: c.get("chunk_index", 0))

        async def count_embeddings_by_document(self, document_id: str, source_type: str | None = None) -> int:
            """Count embeddings in embeddings_v2 for a given document.

            Expects document_id to be stored in metadata['document_id'] by callers.
            """
            count = 0
            for emb in self.embeddings_v2.values():
                metadata = emb.get("metadata") or {}
                if metadata.get("document_id") != document_id:
                    continue
                if source_type is not None and emb.get("source_type") != source_type:
                    continue
                count += 1
            return count

        async def get_document_search_status(self, document_id: str) -> dict[str, Any]:
            """Return a lightweight search readiness snapshot for tests."""
            chunks_count = await self.count_chunks_by_document(document_id)
            embeddings_count = await self.count_embeddings_by_document(document_id)
            return {
                "document_id": document_id,
                "search_ready": embeddings_count > 0 and chunks_count > 0,
                "embeddings_count": embeddings_count,
                "chunks_count": chunks_count,
            }

    yield MockDatabaseAdapter()


@pytest.fixture(scope="function")
def sample_pdf_files() -> dict[str, dict[str, Any]]:
    """
    Dictionary with various test PDF scenarios for comprehensive testing.

    Returns:
        Dictionary containing different PDF test scenarios:
        - valid_pdf: Normal service manual PDF
        - corrupted_pdf: Corrupted PDF file
        - empty_pdf: PDF with no pages
        - large_pdf: PDF over size limit
        - ocr_required_pdf: Scanned PDF without text
        - multi_language_pdf: PDF with multiple languages
    """

    # Create temporary directory for test files
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))

    test_files = {}

    # 1. Valid PDF - Create a minimal valid PDF
    valid_pdf_path = temp_dir / "valid_service_manual.pdf"
    try:
        # Create a simple PDF using PyMuPDF if available
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "This is a test service manual PDF.\n\nIt contains technical information.")
        page.insert_text((72, 120), "Manufacturer: TestCorp\nModel: C4080\nLanguage: English")
        doc.save(valid_pdf_path)
        doc.close()

        test_files["valid_pdf"] = {
            "path": valid_pdf_path,
            "size": valid_pdf_path.stat().st_size,
            "exists": True,
            "pages": 1,
            "description": "Valid service manual PDF with text",
        }
    except ImportError:
        # Fallback: create a simple text file with .pdf extension
        valid_pdf_path.write_text("Mock PDF content for testing")
        test_files["valid_pdf"] = {
            "path": valid_pdf_path,
            "size": valid_pdf_path.stat().st_size,
            "exists": True,
            "pages": 1,
            "description": "Mock PDF file (text-based)",
        }

    # 2. Corrupted PDF - invalid PDF content
    corrupted_pdf_path = temp_dir / "corrupted.pdf"
    corrupted_pdf_path.write_bytes(b"This is not a valid PDF file content\x00\x01\x02invalid")
    test_files["corrupted_pdf"] = {
        "path": corrupted_pdf_path,
        "size": corrupted_pdf_path.stat().st_size,
        "exists": True,
        "pages": 0,
        "description": "Corrupted PDF file with invalid content",
    }

    # 3. Empty PDF - zero bytes
    empty_pdf_path = temp_dir / "empty.pdf"
    empty_pdf_path.write_bytes(b"")
    test_files["empty_pdf"] = {
        "path": empty_pdf_path,
        "size": 0,
        "exists": True,
        "pages": 0,
        "description": "Empty PDF file (zero bytes)",
    }

    # 4. Large PDF - create a file larger than max size
    large_pdf_path = temp_dir / "large.pdf"
    large_content = "Large PDF content " * (1024 * 1024)  # ~16MB
    large_pdf_path.write_text(large_content)
    test_files["large_pdf"] = {
        "path": large_pdf_path,
        "size": large_pdf_path.stat().st_size,
        "exists": True,
        "pages": 1,
        "description": f"Large PDF file ({large_pdf_path.stat().st_size / (1024*1024):.1f} MB)",
    }

    # 5. OCR-required PDF - PDF with no extractable text (simulated)
    ocr_pdf_path = temp_dir / "ocr_required.pdf"
    # Write binary data that looks like PDF but has no text (using hex escapes for non-ASCII)
    ocr_pdf_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")
    test_files["ocr_required_pdf"] = {
        "path": ocr_pdf_path,
        "size": ocr_pdf_path.stat().st_size,
        "exists": True,
        "pages": 1,
        "description": "PDF requiring OCR (no extractable text)",
    }

    # 6. Multi-language PDF
    multi_lang_pdf_path = temp_dir / "multi_language.pdf"
    multi_lang_content = """English: This is a service manual.
Deutsch: Dies ist ein Servicehandbuch.
Français: Cececi est un manuel de service.
Español: Este es un manual de servicio."""
    multi_lang_pdf_path.write_text(multi_lang_content)
    test_files["multi_language_pdf"] = {
        "path": multi_lang_pdf_path,
        "size": multi_lang_pdf_path.stat().st_size,
        "exists": True,
        "pages": 1,
        "description": "Multi-language PDF content",
    }

    yield test_files

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_with_tables() -> dict[str, Any]:
    """Create a PDF with several pages containing table-like content."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "tables_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()

        # Page 1: specification table
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "Table 1: Specifications\n\nParameter | Value\n-------- | -----\nSpeed | 75 ppm\nResolution | 1200x1200 dpi\nMemory | 2GB",
        )

        # Page 2: parts list
        page2 = doc.new_page()
        parts_rows = [
            "| Part | Number | Description |",
            "|------|--------|-------------|",
        ]
        for i in range(1, 6):
            parts_rows.append(f"| P{i:03d} | A0{i:03d} | Test Part {i} |")
        page2.insert_text((72, 72), "Table 2: Parts List\n" + "\n".join(parts_rows))

        # Page 3: error codes
        page3 = doc.new_page()
        error_rows = [
            "| Code | Description |",
            "|------|-------------|",
            "| 900.01 | Fuser Unit Error |",
            "| 900.02 | Lamp Error |",
            "| 920.00 | Waste Toner Full |",
        ]
        page3.insert_text((72, 72), "Table 3: Error Codes\n" + "\n".join(error_rows))

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "table_count": 3,
            "description": "PDF with specification, parts list, and error code tables",
        }
    except ImportError:
        pdf_path.write_text("Mock tables PDF for testing")
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "table_count": 0,
            "description": "Mock tables PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_with_images() -> dict[str, Any]:
    """Create a PDF with multiple embedded raster images."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "images_test.pdf"

    info: dict[str, Any]
    try:
        import io

        import fitz
        from PIL import Image

        doc = fitz.open()

        # Helper to insert an image
        def _insert_image(page, x: float, y: float, width: int, height: int, color: tuple) -> None:
            img = Image.new("RGB", (width, height), color=color)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            rect = fitz.Rect(x, y, x + width, y + height)
            page.insert_image(rect, stream=img_bytes)

        # Page 1: landscape and portrait
        page1 = doc.new_page()
        _insert_image(page1, 72, 72, 320, 180, (255, 0, 0))
        _insert_image(page1, 72, 300, 180, 320, (0, 255, 0))

        # Page 2: square and tall image
        page2 = doc.new_page()
        _insert_image(page2, 72, 72, 200, 200, (0, 0, 255))
        _insert_image(page2, 300, 72, 120, 360, (255, 255, 0))

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 2,
            "image_count": 4,
            "description": "PDF with multiple embedded images of varying aspect ratios",
        }
    except ImportError:
        pdf_path.write_text("Mock images PDF for testing")
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "image_count": 0,
            "description": "Mock images PDF (PyMuPDF/Pillow not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_with_svgs() -> dict[str, Any]:
    """Create a PDF with vector graphics suitable for SVG extraction tests."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "svgs_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()

        # Page 1: basic shapes
        page1 = doc.new_page()
        page1.draw_rect(fitz.Rect(50, 50, 250, 200))
        page1.draw_circle(fitz.Point(300, 300), 80)

        # Page 2: more complex paths (approximated with lines)
        page2 = doc.new_page()
        page2.draw_line(fitz.Point(100, 100), fitz.Point(400, 120))
        page2.draw_line(fitz.Point(400, 120), fitz.Point(380, 400))
        page2.draw_line(fitz.Point(380, 400), fitz.Point(100, 380))
        page2.draw_line(fitz.Point(100, 380), fitz.Point(100, 100))
        page2.insert_text((72, 72), "Vector diagram with annotations")

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 2,
            "svg_count": 2,
            "description": "PDF with vector graphics for SVGProcessor tests",
        }
    except ImportError:
        pdf_path.write_text("Mock SVG PDF for testing")
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "svg_count": 0,
            "description": "Mock SVG PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_multimodal() -> dict[str, Any]:
    """Create a PDF with mixed tables, images, SVG-like vector graphics, and text."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "multimodal_test.pdf"

    info: dict[str, Any]
    try:
        import io

        import fitz
        from PIL import Image

        doc = fitz.open()

        # Helper for embedding images
        def _embed_image(page, x: float, y: float, w: int, h: int, color: tuple) -> None:
            img = Image.new("RGB", (w, h), color=color)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            rect = fitz.Rect(x, y, x + w, y + h)
            page.insert_image(rect, stream=data)

        # Page 1: table + image + vector
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "Table 1: Specifications\nParameter | Value\n-------- | -----\nSpeed | 55 ppm\nResolution | 600x600 dpi",
        )
        _embed_image(page1, 300, 100, 180, 120, (200, 200, 255))
        page1.draw_rect(fitz.Rect(80, 260, 260, 340))

        # Page 2: parts list + SVG-like drawing
        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Parts List\n| Part | Number | Description |\n|------|--------|-------------|\n| P001 | A001 | Roller |",
        )
        page2.draw_circle(fitz.Point(200, 300), 60)

        # Page 3: error codes + image
        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "Error Codes\n| Code | Description |\n|------|-------------|\n| 900.01 | Fuser Error |\n| 920.00 | Waste Toner Full |",
        )
        _embed_image(page3, 320, 200, 160, 160, (255, 220, 200))

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "table_count": 3,
            "image_count": 3,
            "svg_count": 3,
            "description": "PDF with mixed tables, images, vector graphics, and text",
        }
    except ImportError:
        pdf_path.write_text("Mock multimodal PDF for testing")
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "table_count": 0,
            "image_count": 0,
            "svg_count": 0,
            "description": "Mock multimodal PDF (PyMuPDF/Pillow not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def create_test_image():
    """Factory for creating simple in-memory test images with Pillow."""

    def _create_test_image(width: int, height: int, color=(255, 255, 255), image_format: str = "PNG"):
        import io

        from PIL import Image

        img = Image.new("RGB", (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format=image_format)
        buf.seek(0)
        return img

    return _create_test_image


@pytest.fixture(scope="function")
def create_test_table_data():
    """Factory for creating pandas DataFrames with synthetic table data."""

    def _create_test_table_data(rows: int, cols: int):
        import pandas as pd

        data = {f"col_{c}": [f"r{r}_c{c}" for r in range(rows)] for c in range(cols)}
        return pd.DataFrame(data)

    return _create_test_table_data


@pytest.fixture(scope="function")
def create_test_svg():
    """Factory for generating simple SVG strings with basic shapes."""

    def _create_test_svg(width: int, height: int, shapes: list[dict[str, Any]] | None = None) -> str:
        shapes = shapes or []
        parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        for shape in shapes:
            if shape.get("type") == "rect":
                parts.append(
                    f"<rect x=\"{shape.get('x', 0)}\" y=\"{shape.get('y', 0)}\" "
                    f"width=\"{shape.get('width', 10)}\" height=\"{shape.get('height', 10)}\" "
                    f"fill=\"{shape.get('fill', '#000')}\" />"
                )
            elif shape.get("type") == "circle":
                parts.append(
                    f"<circle cx=\"{shape.get('cx', 10)}\" cy=\"{shape.get('cy', 10)}\" "
                    f"r=\"{shape.get('r', 5)}\" fill=\"{shape.get('fill', '#000')}\" />"
                )
        parts.append("</svg>")
        return "".join(parts)

    return _create_test_svg


@pytest.fixture(scope="function")
def temp_test_pdf() -> Generator[Path, None, None]:
    """
    Fixture for creating temporary test PDFs with PyMuPDF.

    Yields a temporary directory path where test PDFs can be created.
    Automatically cleans up after the test.
    """
    with tempfile.TemporaryDirectory(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]) as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="function")
def mock_stage_tracker(mock_database_adapter: DatabaseAdapter) -> StageTracker:
    """
    Mock StageTracker with all stage tracking methods.

    Provides a real StageTracker instance connected to the mock database adapter.
    All RPC calls are mocked and logged.
    """
    return StageTracker(database_adapter=mock_database_adapter)


@pytest.fixture(scope="function")
def mock_embedding_service():
    """Mock embedding service that generates deterministic 768-dim vectors."""

    class MockEmbeddingService:
        def __init__(self) -> None:
            self.model_name = "nomic-embed-text:latest"

        def _generate_embedding(self, text: str) -> list[float]:
            if not text:
                return [0.0] * 768
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            for i in range(768):
                byte = digest[i % len(digest)]
                values.append(byte / 255.0)
            return values

    return MockEmbeddingService()


@pytest.fixture(scope="function")
def sample_chunks_with_content() -> list[dict[str, Any]]:
    """Diverse chunk dictionaries for embedding/search tests.

    The content intentionally mixes error codes, parts, troubleshooting steps,
    specifications, and multi-language phrases to exercise similarity search
    and quality metrics.
    """

    document_id = str(uuid4())

    contents = [
        "Error 13.A1.B2: Paper jam in tray 2. Open tray 2 and remove jammed paper.",
        "Tray 2 paper jam error 13.A1.B2 occurs when paper is stuck near the fuser.",
        "Network configuration: set static IP address and configure DNS servers.",
        "Toner replacement procedure for Lexmark CX920 series printers.",
        "Specifications: print speed 75 ppm, resolution 1200 x 1200 dpi, memory 2GB.",
        "Clean the corona wire with a soft, lint-free cloth to fix streaks.",
        "900.01 Fuser unit error: replace the fuser assembly and reset the printer.",
        "Parts list: 6QN29-67005 Fuser Unit, RM1-1234-000 Transfer Roller.",
        "Deutsch: Papierstau in Fach 2 – entfernen Sie das Papier vorsichtig.",
        "Français: bourrage papier dans le bac 2, voir le manuel de service.",
        "Español: atasco de papel en la bandeja 2, retire el papel con cuidado.",
        "User guide: how to configure WiFi printing using WPS push button.",
        "Service mode instructions: enter code 1087 * to open diagnostics menu.",
        "Empty chunk should still be handled gracefully.",
        "Very long troubleshooting instructions: " + "Check paper path. " * 200,
        "Link context: see https://support.example.com/error/13A1B2 for details.",
        "Table summary: Code 900.01 – Fuser Error; Code 920.00 – Waste Toner Full.",
        "Image caption: Rear duplex unit with highlighted jam removal levers.",
        "Video description: How to clear a paper jam in tray 2 step by step.",
        "Generic informational text without technical content.",
    ]

    chunks: list[dict[str, Any]] = []
    for idx, text in enumerate(contents):
        chunks.append(
            {
                "id": str(uuid4()),
                "document_id": document_id,
                "chunk_index": idx,
                "page_start": (idx // 2) + 1,
                "page_end": (idx // 2) + 1,
                "content": text,
                "metadata": {
                    "chunk_type": "text",
                },
            }
        )

    # Add a couple of edge-case chunks
    chunks.append(
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": len(chunks),
            "page_start": 10,
            "page_end": 10,
            "content": "",  # empty content
            "metadata": {"chunk_type": "text"},
        }
    )

    chunks.append(
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": len(chunks),
            "page_start": 11,
            "page_end": 11,
            "content": "特殊文字と絵文字 😊 mixed with ASCII text.",
            "metadata": {"chunk_type": "text"},
        }
    )

    return chunks


@pytest.fixture(scope="function")
def sample_embeddings(mock_embedding_service, sample_chunks_with_content) -> list[dict[str, Any]]:
    """Pre-generated deterministic embeddings for sample chunks.

    Each entry includes chunk_id, embedding vector, original content and
    metadata, suitable for quality and relevance tests.
    """

    embeddings: list[dict[str, Any]] = []
    for chunk in sample_chunks_with_content:
        text = chunk.get("content", "")
        emb = mock_embedding_service._generate_embedding(text)
        embeddings.append(
            {
                "chunk_id": chunk["id"],
                "embedding": emb,
                "content": text,
                "metadata": dict(chunk.get("metadata", {})),
            }
        )
    return embeddings


@pytest.fixture(scope="function")
def mock_ollama_service():
    """Mock Ollama-like service returning deterministic 768-dim embeddings."""

    class MockOllamaService:
        def __init__(self) -> None:
            self.model_name = "embeddinggemma-mock"

        def generate_embedding(self, text: str) -> list[float]:
            if not text:
                return [0.0] * 768
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            for i in range(768):
                byte = digest[i % len(digest)]
                values.append(byte / 255.0)
            return values

    return MockOllamaService()


@pytest.fixture(scope="function")
def search_quality_test_data(sample_chunks_with_content) -> dict[str, Any]:
    """Synthetic query/result hints for search relevance tests.

    The structure is intentionally simple; tests combine this with
    sample_embeddings to assert ranking and threshold behaviour.
    """

    # Map a few canonical queries to phrases we expect to rank highly.
    queries = [
        "paper jam tray 2",
        "network configuration",
        "fuser unit error 900.01",
    ]

    expected_results = {
        "paper jam tray 2": ["Paper jam in tray 2", "tray 2 paper jam"],
        "network configuration": ["Network configuration"],
        "fuser unit error 900.01": ["900.01 Fuser unit error"],
    }

    return {"queries": queries, "expected_results": expected_results}


@pytest.fixture(scope="function")
def embedding_quality_metrics():
    """Helper functions for embedding quality validation.

    Returns a small object exposing cosine_similarity, variance and simple
    distribution checks to keep quality tests focused and readable.
    """

    class Metrics:
        @staticmethod
        def cosine_similarity(a: list[float], b: list[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = 0.0
            norm_a = 0.0
            norm_b = 0.0
            for x, y in zip(a, b):
                dot += x * y
                norm_a += x * x
                norm_b += y * y
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a**0.5 * norm_b**0.5)

        @staticmethod
        def calculate_embedding_variance(vectors: list[list[float]]) -> float:
            if not vectors:
                return 0.0
            dim = len(vectors[0])
            if dim == 0:
                return 0.0

            # Compute mean per dimension
            means = [0.0] * dim
            for vec in vectors:
                for i, v in enumerate(vec):
                    means[i] += v
            count = float(len(vectors))
            means = [m / count for m in means]

            # Compute average variance across dimensions
            var_sum = 0.0
            for vec in vectors:
                for i, v in enumerate(vec):
                    diff = v - means[i]
                    var_sum += diff * diff
            return var_sum / (count * dim)

        @staticmethod
        def check_embedding_distribution(vec: list[float]) -> bool:
            """Basic sanity check: no NaN/Inf and values in a reasonable range."""
            if not vec:
                return False
            for v in vec:
                if not (-1e6 < v < 1e6):
                    return False
            return True

    return Metrics()


@pytest.fixture(scope="function")
def mock_storage_service():
    """Mock ObjectStorageService for image upload/download/delete operations."""

    class MockStorageService:
        def __init__(self) -> None:
            self.uploaded_images: dict[str, dict[str, Any]] = {}

        def upload_image(
            self,
            content: bytes,
            filename: str,
            bucket_type: str = "document_images",
            metadata: dict[str, Any] = None,
        ) -> dict[str, Any]:
            key = f"{bucket_type}/{filename}"
            self.uploaded_images[key] = {
                "content": content,
                "filename": filename,
                "bucket_type": bucket_type,
                "metadata": metadata or {},
            }
            file_hash = hashlib.sha256(content).hexdigest()
            storage_path = key
            public_url = f"https://mock-storage/{storage_path}"
            return {
                "success": True,
                "storage_path": storage_path,
                "public_url": public_url,
                "file_hash": file_hash,
                "bucket": bucket_type,
            }

        def download_image(self, bucket_type: str, key: str) -> bytes:
            record = self.uploaded_images.get(f"{bucket_type}/{key}")
            if not record:
                return b""
            return record["content"]

        def delete_image(self, bucket_type: str, key: str) -> bool:
            full_key = f"{bucket_type}/{key}"
            if full_key in self.uploaded_images:
                del self.uploaded_images[full_key]
                return True
            return False

        def generate_presigned_url(self, bucket_type: str, key: str, expiration: int = 3600) -> str | None:
            if f"{bucket_type}/{key}" in self.uploaded_images:
                return f"https://mock-storage/{bucket_type}/{key}?presigned={expiration}"
            return None

    return MockStorageService()


@pytest.fixture(scope="function")
def mock_ai_service():
    """Mock AIService for image analysis and embeddings without external calls."""

    class MockAIService:
        def __init__(self) -> None:
            self.vision_available = True

        def analyze_image(self, image: bytes, description: str | None = None) -> dict[str, Any]:
            size = len(image) if image else 0
            contains_text = bool(size % 2 == 0)
            image_type = "diagram" if size % 3 == 0 else "photo"
            return {
                "image_type": image_type,
                "description": description or "Mock image analysis",
                "contains_text": contains_text,
                "tags": ["mock", "test"],
                "confidence": 0.9,
            }

        async def generate_embeddings(self, text: str) -> list[float]:
            if not text:
                return [0.0] * 768
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values: list[float] = []
            for i in range(768):
                byte = digest[i % len(digest)]
                values.append(byte / 255.0)
            return values

        async def generate(self, prompt: str, max_tokens: int = 50) -> str:
            """Simulate LLM-based manufacturer detection for classification tests."""
            lower = prompt.lower()
            if "konica" in lower or "bizhub" in lower or "accuriopress" in lower:
                return "Konica Minolta"
            if "laserjet" in lower or "hp " in lower:
                return "HP Inc."
            if "imagerunner" in lower or "canon" in lower:
                return "Canon"
            return "Unknown"

    return MockAIService()


@pytest.fixture(scope="function")
def mock_quality_service(mock_database_adapter: DatabaseAdapter):
    async def _check(document_id: str) -> dict[str, Any]:
        return {
            "passed": True,
            "score": 100.0,
            "issues": [],
            "warnings": [],
            "stats": {"document_id": document_id},
        }

    return SimpleNamespace(
        database_service=mock_database_adapter,
        check_document_quality=_check,
    )


@pytest.fixture(scope="function")
def mock_master_pipeline(
    mock_database_adapter: DatabaseAdapter,
    mock_storage_service,
    mock_ai_service,
    mock_quality_service,
):
    pipeline = KRMasterPipeline(database_adapter=mock_database_adapter)
    pipeline.database_service = mock_database_adapter
    pipeline.storage_service = mock_storage_service
    pipeline.ai_service = mock_ai_service
    pipeline.config_service = SimpleNamespace()
    pipeline.features_service = SimpleNamespace()
    pipeline.quality_service = mock_quality_service
    pipeline.file_locator = SimpleNamespace(find_file=lambda filename: filename)

    class _Processor:
        async def process(self, context):  # type: ignore[override]
            return SimpleNamespace(success=True, data={}, message="ok")

    base_processor = _Processor()
    pipeline.processors = {
        "upload": base_processor,
        "text": base_processor,
        "table": base_processor,
        "svg": base_processor,
        "image": base_processor,
        "visual_embedding": base_processor,
        "classification": base_processor,
        "chunk_prep": base_processor,
        "links": base_processor,
        "metadata": base_processor,
        "storage": base_processor,
        "embedding": base_processor,
        "search": base_processor,
    }

    return pipeline


@pytest.fixture(scope="function")
def processor_test_config() -> dict[str, Any]:
    """
    Configuration for processor tests.

    Returns a dictionary with test configuration including:
    - File size limits
    - Allowed extensions
    - Chunking parameters
    - OCR settings
    - PDF engine selection
    """
    return PROCESSOR_TEST_CONFIG.copy()


@pytest.fixture(scope="function", autouse=True)
async def cleanup_test_documents(mock_database_adapter: DatabaseAdapter):
    """
    Autouse fixture for cleaning up test documents after each test.

    Automatically clears the mock database adapter's storage after each test
    to ensure test isolation.
    """
    yield

    # Cleanup mock storage
    mock_database_adapter.documents.clear()
    mock_database_adapter.chunks.clear()
    mock_database_adapter.processing_queue.clear()
    if hasattr(mock_database_adapter, "structured_tables"):
        mock_database_adapter.structured_tables.clear()
    if hasattr(mock_database_adapter, "embeddings_v2"):
        mock_database_adapter.embeddings_v2.clear()
    if hasattr(mock_database_adapter, "legacy_embeddings"):
        mock_database_adapter.legacy_embeddings.clear()
    if hasattr(mock_database_adapter, "links"):
        mock_database_adapter.links.clear()
    if hasattr(mock_database_adapter, "videos"):
        mock_database_adapter.videos.clear()
    if hasattr(mock_database_adapter, "error_codes"):
        mock_database_adapter.error_codes.clear()
    if hasattr(mock_database_adapter, "parts_catalog"):
        mock_database_adapter.parts_catalog.clear()
    if hasattr(mock_database_adapter, "document_products"):
        mock_database_adapter.document_products.clear()
    if hasattr(mock_database_adapter, "products"):
        mock_database_adapter.products.clear()
    if hasattr(mock_database_adapter, "manufacturers"):
        mock_database_adapter.manufacturers.clear()
    if hasattr(mock_database_adapter, "product_series"):
        mock_database_adapter.product_series.clear()


@pytest.fixture(scope="function")
def processing_context() -> ProcessingContext:
    """
    Create a basic ProcessingContext for testing.

    Returns a ProcessingContext with minimal required fields for processor testing.
    """
    return ProcessingContext(
        document_id=str(uuid4()), file_path=Path("/tmp/test.pdf"), document_type="service_manual", metadata={}
    )


@pytest.fixture(scope="function")
def sample_document_metadata() -> dict[str, Any]:
    """
    Sample document metadata for testing.

    Returns realistic metadata that would be extracted from a service manual PDF.
    """
    return {
        "filename": "test_service_manual.pdf",
        "file_size_bytes": 2048576,  # 2MB
        "page_count": 25,
        "document_type": "service_manual",
        "manufacturer": "TestCorp",
        "model": "C4080",
        "language": "en",
        "title": "Test Service Manual",
        "author": "TestCorp Technical Documentation",
        "creator": "PDF Generator",
        "creation_date": "2024-01-15T10:30:00Z",
        "file_hash": hashlib.sha256(b"test content").hexdigest(),
    }


# Pytest configuration for processor tests is defined at the end of this file


@pytest.fixture(scope="function")
def mock_websocket_callback():
    """
    Mock WebSocket callback for StageTracker testing.

    Returns an AsyncMock that can be used to verify WebSocket events
    are sent during stage tracking.
    """
    callback = AsyncMock()
    return callback


@pytest.fixture(scope="function")
def mock_link_extractor():
    """Mock LinkExtractor returning deterministic links and videos.

    The mock returns a mix of HTTP(S) links, YouTube URLs and direct video files
    with realistic metadata for use in link extraction tests.
    """

    from backend.processors.link_extractor import LinkExtractor

    extractor = MagicMock(spec=LinkExtractor)

    sample_links = [
        {
            "url": "http://example.com/support/page",
            "page_number": 1,
            "description": "Support page",
            "position_data": {"type": "text_extraction"},
            "confidence_score": 0.9,
        },
        {
            "url": "https://youtu.be/ABCDEFGHIJK",
            "page_number": 2,
            "description": "YouTube how-to video",
            "position_data": {"type": "text_extraction"},
            "confidence_score": 0.95,
        },
        {
            "url": "https://cdn.example.com/videos/tutorial.mp4",
            "page_number": 3,
            "description": "Direct MP4 tutorial",
            "position_data": {"type": "text_extraction"},
            "confidence_score": 0.9,
        },
    ]

    sample_videos: list[dict[str, Any]] = []

    extractor.extract_from_document.return_value = {
        "links": sample_links,
        "videos": sample_videos,
        "total_links": len(sample_links),
        "total_videos": len(sample_videos),
    }

    return extractor


@pytest.fixture(scope="function")
def mock_context_extraction_service():
    """Mock ContextExtractionService for link/video context extraction tests."""

    from backend.services.context_extraction_service import ContextExtractionService

    service = MagicMock(spec=ContextExtractionService)

    def _link_context(page_text: str, page_number: int, link_url: str) -> dict[str, Any]:
        return {
            "context_description": f"Context for {link_url} on page {page_number}",
            "page_header": f"Header page {page_number}",
            "related_error_codes": ["900.01"],
            "related_products": ["C4080"],
        }

    def _video_context(page_text: str, page_number: int, video_url: str) -> dict[str, Any]:
        return {
            "context_description": f"Video context for {video_url} on page {page_number}",
            "page_header": f"Header page {page_number}",
            "related_error_codes": ["900.02"],
            "related_products": ["C750i"],
        }

    service.extract_link_context.side_effect = _link_context
    service.extract_video_context.side_effect = _video_context

    return service


@pytest.fixture(scope="function")
def mock_document_type_detector():
    """Mock DocumentTypeDetector returning deterministic type/version tuples."""

    from backend.processors.document_type_detector import DocumentTypeDetector

    detector = MagicMock(spec=DocumentTypeDetector)
    detector.detect.return_value = ("service_manual", "v1.0")
    return detector


@pytest.fixture(scope="function")
def sample_chunks_for_preprocessing() -> list[dict[str, Any]]:
    """Sample chunk dictionaries covering different content patterns.

    Each chunk contains id, document_id, content, metadata, chunk_index,
    page_start and page_end fields suitable for ChunkPreprocessor tests.
    """

    document_id = str(uuid4())

    chunks: list[dict[str, Any]] = [
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 1,
            "content": "Page 1 of 10\nKonica Minolta C4080 Service Manual\nChapter 1\nSafety information",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 1,
            "page_start": 2,
            "page_end": 2,
            "content": "Copyright 2025 Konica Minolta\n900.01 Fuser Unit Error: Paper jam in fuser",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 2,
            "page_start": 3,
            "page_end": 3,
            "content": "Parts List\nPart ABC-1234: Fuser Unit\nPart DEF-5678: Transfer Roller",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 3,
            "page_start": 4,
            "page_end": 4,
            "content": "1. Remove cover\n2. Replace cartridge\n3. Close cover",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 4,
            "page_start": 5,
            "page_end": 5,
            "content": "Resolution: 1200 dpi, Speed: 80 ppm, Weight: 50 kg",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 5,
            "page_start": 6,
            "page_end": 6,
            "content": "Code    Description    Value\n900.01  Fuser Error    Critical",
            "metadata": {},
        },
        {
            "id": str(uuid4()),
            "document_id": document_id,
            "chunk_index": 6,
            "page_start": 7,
            "page_end": 7,
            "content": "This is a general descriptive text chunk without special patterns.",
            "metadata": {},
        },
    ]

    return chunks


@pytest.fixture(scope="function")
def sample_document_metadata_for_classification() -> list[dict[str, Any]]:
    """Sample document metadata dicts for classification processor tests."""

    return [
        {
            "id": str(uuid4()),
            "filename": "HP_LaserJet_M4555_Service_Manual.pdf",
            "title": "HP LaserJet M4555 Service Manual",
            "file_hash": hashlib.sha256(b"hp-service").hexdigest(),
            "page_count": 120,
            "created_at": "D:20250101120000Z",
        },
        {
            "id": str(uuid4()),
            "filename": "Canon_iR_ADV_C5560_Parts_Guide.pdf",
            "title": "Canon imageRUNNER ADVANCE C5560 Parts Catalog",
            "file_hash": hashlib.sha256(b"canon-parts").hexdigest(),
            "page_count": 220,
            "created_at": "D:20240808064126Z",
        },
        {
            "id": str(uuid4()),
            "filename": "bizhub_C4080_User_Guide.pdf",
            "title": "bizhub C4080 User Guide",
            "file_hash": hashlib.sha256(b"km-user").hexdigest(),
            "page_count": 80,
            "created_at": "D:20231201090000Z",
        },
        {
            "id": str(uuid4()),
            "filename": "generic_manual.pdf",
            "title": "Generic Technical Manual",
            "file_hash": hashlib.sha256(b"generic").hexdigest(),
            "page_count": 40,
            "created_at": "",
        },
    ]


@pytest.fixture(scope="function")
def create_test_link() -> Any:
    """Factory to create link dicts with customizable properties."""

    def _factory(
        url: str = "http://example.com",
        page_number: int = 1,
        link_type: str = "external",
        link_category: str = "external",
        description: str = "Example link",
        confidence_score: float = 0.9,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "url": url,
            "page_number": page_number,
            "link_type": link_type,
            "link_category": link_category,
            "description": description,
            "position_data": {"type": "factory"},
            "confidence_score": confidence_score,
        }

    return _factory


@pytest.fixture(scope="function")
def create_test_video() -> Any:
    """Factory to create video metadata dicts with customizable properties."""

    def _factory(
        youtube_id: str | None = None,
        platform: str = "youtube",
        title: str = "Test Video",
        duration: int | None = None,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "youtube_id": youtube_id,
            "platform": platform,
            "title": title,
            "duration": duration,
            "metadata": {},
        }

    return _factory


@pytest.fixture(scope="function")
def create_test_chunk() -> Any:
    """Factory to create chunk dicts with customizable content and metadata."""

    def _factory(
        document_id: str | None = None,
        content: str = "Sample chunk content",
        chunk_type: str | None = None,
        chunk_index: int = 0,
        page_start: int = 1,
        page_end: int = 1,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "document_id": document_id or str(uuid4()),
            "chunk_index": chunk_index,
            "page_start": page_start,
            "page_end": page_end,
            "content": content,
            "metadata": {"chunk_type": chunk_type} if chunk_type else {},
        }

    return _factory


@pytest.fixture(scope="function")
def sample_pdf_with_links() -> dict[str, Any]:
    """Create a PDF with embedded hyperlinks and text URLs for link tests."""

    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "links_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page()

        page.insert_text(
            (72, 72),
            "Visit our support portal at http://support.example.com for help.\n"
            "Watch the tutorial at https://youtu.be/ABCDEFGHIJK for setup.\n"
            "Download drivers from https://download.example.com/drivers.\n",
        )

        link_rect = fitz.Rect(72, 72, 300, 90)
        page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": "http://support.example.com"})

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "description": "PDF with support, YouTube and download links",
        }
    except ImportError:
        pdf_path.write_text(
            "Visit http://support.example.com and https://youtu.be/ABCDEFGHIJK and "
            "https://download.example.com/drivers."
        )
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "description": "Mock links PDF (PyMuPDF not available)",
        }

    def _cleanup() -> None:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    info["_cleanup"] = _cleanup
    return info


@pytest.fixture(scope="function")
def sample_pdf_with_videos() -> dict[str, Any]:
    """Create a PDF with YouTube, Vimeo and direct video URLs as text."""

    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "videos_test.pdf"

    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "YouTube: https://www.youtube.com/watch?v=ABCDEFGHIJK\n"
            "Short: https://youtu.be/ABCDEFGHIJK\n"
            "Vimeo: https://vimeo.com/123456789\n"
            "Direct MP4: https://cdn.example.com/training/video.mp4\n",
        )
        doc.save(pdf_path)
        doc.close()
    except ImportError:
        pdf_path.write_text(
            "https://www.youtube.com/watch?v=ABCDEFGHIJK\n"
            "https://youtu.be/ABCDEFGHIJK\n"
            "https://vimeo.com/123456789\n"
            "https://cdn.example.com/training/video.mp4\n"
        )

    def _cleanup() -> None:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "path": pdf_path,
        "size": pdf_path.stat().st_size,
        "pages": 1,
        "description": "PDF with multiple video URL formats",
        "_cleanup": _cleanup,
    }


@pytest.fixture(scope="function")
def sample_pdf_multipage_links() -> dict[str, Any]:
    """Create a multi-page PDF with links distributed across pages."""

    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "multipage_links_test.pdf"

    try:
        import fitz

        doc = fitz.open()

        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "Error 900.01 details at http://errors.example.com/90001.\n",
        )

        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Product C4080 support: http://support.example.com/c4080.\n",
        )

        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "General info: http://www.example.com/info.\n",
        )

        doc.save(pdf_path)
        doc.close()
    except ImportError:
        pdf_path.write_text(
            "Page1: http://errors.example.com/90001\n"
            "Page2: http://support.example.com/c4080\n"
            "Page3: http://www.example.com/info\n"
        )

    def _cleanup() -> None:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "path": pdf_path,
        "size": pdf_path.stat().st_size,
        "pages": 3,
        "description": "Multi-page PDF with page-specific links",
        "_cleanup": _cleanup,
    }


@pytest.fixture(scope="function")
def mock_error_code_extractor():
    """Mock ErrorCodeExtractor with deterministic extraction methods."""

    from backend.processors.models import ExtractedErrorCode

    extractor = MagicMock()

    def mock_extract_from_text(text: str, manufacturer: str = "AUTO", page_number: int = 1) -> list[ExtractedErrorCode]:
        """Mock extraction returning predefined error codes based on text content."""
        error_codes = []

        # HP Error Codes
        if "13.A1.B2" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="13.A1.B2",
                    error_description="Paper jam in tray 2",
                    solution_text="Remove paper from tray 2 and restart printer",
                    context_text="Error 13.A1.B2: Paper jam in tray 2. Solution: Remove paper from tray 2 and restart printer.",
                    page_number=page_number,
                    severity_level="medium",
                    confidence=0.9,
                )
            )

        if "49.4C02" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="49.4C02",
                    error_description="Firmware error",
                    solution_text="Power cycle printer and update firmware",
                    context_text="Error 49.4C02: Firmware error. Solution: Power cycle printer and update firmware.",
                    page_number=page_number,
                    severity_level="high",
                    confidence=0.85,
                )
            )

        # Konica Minolta Error Codes
        if "C-2557" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="C-2557",
                    error_description="Developer unit error",
                    solution_text="Replace developer unit",
                    context_text="Error C-2557: Developer unit error. Solution: Replace developer unit.",
                    page_number=page_number,
                    severity_level="critical",
                    confidence=0.95,
                )
            )

        if "J-0001" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="J-0001",
                    error_description="Fuser temperature error",
                    solution_text="Check fuser unit and temperature sensor",
                    context_text="Error J-0001: Fuser temperature error. Solution: Check fuser unit and temperature sensor.",
                    page_number=page_number,
                    severity_level="high",
                    confidence=0.88,
                )
            )

        # Lexmark Error Codes
        if "900.01" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="900.01",
                    error_description="Fuser unit error",
                    solution_text="Replace fuser unit",
                    context_text="Error 900.01: Fuser unit error. Solution: Replace fuser unit.",
                    page_number=page_number,
                    severity_level="critical",
                    confidence=0.92,
                )
            )

        if "200.02" in text:
            error_codes.append(
                ExtractedErrorCode(
                    error_code="200.02",
                    error_description="Memory error",
                    solution_text="Check memory modules and restart",
                    context_text="Error 200.02: Memory error. Solution: Check memory modules and restart.",
                    page_number=page_number,
                    severity_level="medium",
                    confidence=0.8,
                )
            )

        return error_codes

    def mock_extract(document_text: str, manufacturer: str = "AUTO") -> list[ExtractedErrorCode]:
        """Mock extract method that processes full document."""
        return mock_extract_from_text(document_text, manufacturer, 1)

    extractor.extract_from_text.side_effect = mock_extract_from_text
    extractor.extract.side_effect = mock_extract

    return extractor


@pytest.fixture(scope="function")
def mock_version_extractor():
    """Mock VersionExtractor with deterministic extraction methods."""

    from backend.processors.version_extractor import ExtractedVersion

    extractor = MagicMock()

    def mock_extract_from_text(text: str, manufacturer: str = "AUTO") -> list[ExtractedVersion]:
        """Mock extraction returning predefined versions based on text content."""
        versions = []

        # Edition patterns
        if "Edition 3, 5/2024" in text:
            versions.append(
                ExtractedVersion(
                    version_string="Edition 3, 5/2024", version_type="edition", confidence=0.9, page_number=1
                )
            )

        if "Edition 4.0" in text:
            versions.append(
                ExtractedVersion(version_string="Edition 4.0", version_type="edition", confidence=0.85, page_number=1)
            )

        # Date patterns
        if "2024/12/25" in text:
            versions.append(
                ExtractedVersion(version_string="2024/12/25", version_type="date", confidence=0.95, page_number=1)
            )

        if "5/2024" in text:
            versions.append(
                ExtractedVersion(version_string="5/2024", version_type="date", confidence=0.8, page_number=1)
            )

        if "November 2024" in text:
            versions.append(
                ExtractedVersion(version_string="November 2024", version_type="date", confidence=0.85, page_number=1)
            )

        # Firmware patterns
        if "FW 4.2" in text:
            versions.append(
                ExtractedVersion(version_string="FW 4.2", version_type="firmware", confidence=0.9, page_number=1)
            )

        if "Firmware 4.2" in text:
            versions.append(
                ExtractedVersion(version_string="Firmware 4.2", version_type="firmware", confidence=0.88, page_number=1)
            )

        # Version patterns
        if "Version 1.0" in text:
            versions.append(
                ExtractedVersion(version_string="Version 1.0", version_type="version", confidence=0.85, page_number=1)
            )

        if "v1.0" in text:
            versions.append(
                ExtractedVersion(version_string="v1.0", version_type="version", confidence=0.8, page_number=1)
            )

        # Revision patterns
        if "Rev 1.0" in text:
            versions.append(
                ExtractedVersion(version_string="Rev 1.0", version_type="revision", confidence=0.9, page_number=1)
            )

        return versions

    def mock_extract_best_version(text: str, manufacturer: str = "AUTO") -> ExtractedVersion | None:
        """Mock best version selection returning highest confidence version."""
        versions = mock_extract_from_text(text, manufacturer)
        return max(versions, key=lambda v: v.confidence) if versions else None

    extractor.extract_from_text.side_effect = mock_extract_from_text
    extractor.extract_best_version.side_effect = mock_extract_best_version

    return extractor


@pytest.fixture(scope="function")
def mock_parts_extractor():
    """Mock parts_extractor function with deterministic extraction."""

    def mock_extract_parts_with_context(text: str, manufacturer: str = "AUTO") -> list[dict[str, Any]]:
        """Mock parts extraction returning predefined parts based on text content."""
        parts = []

        # HP Parts
        if "6QN29-67005" in text:
            parts.append(
                {
                    "part": "6QN29-67005",
                    "context": "Replace part 6QN29-67005 - Fuser Unit",
                    "pattern_name": "hp_main_part",
                    "confidence": 0.9,
                    "manufacturer": "HP",
                }
            )

        if "RM1-1234-000" in text:
            parts.append(
                {
                    "part": "RM1-1234-000",
                    "context": "Install RM1-1234-000 - Transfer Roller",
                    "pattern_name": "hp_component",
                    "confidence": 0.85,
                    "manufacturer": "HP",
                }
            )

        # Konica Minolta Parts
        if "A1DU-R750-00" in text:
            parts.append(
                {
                    "part": "A1DU-R750-00",
                    "context": "A1DU-R750-00 - Developer Unit",
                    "pattern_name": "konica_developer",
                    "confidence": 0.95,
                    "manufacturer": "Konica Minolta",
                }
            )

        if "4062-R750-01" in text:
            parts.append(
                {
                    "part": "4062-R750-01",
                    "context": "Replace 4062-R750-01 - Drum Unit",
                    "pattern_name": "konica_drum",
                    "confidence": 0.88,
                    "manufacturer": "Konica Minolta",
                }
            )

        if "A2K0-R750-02" in text:
            parts.append(
                {
                    "part": "A2K0-R750-02",
                    "context": "A2K0-R750-02 - Transfer Belt",
                    "pattern_name": "konica_transfer_belt",
                    "confidence": 0.9,
                    "manufacturer": "Konica Minolta",
                }
            )

        # Canon Parts
        if "FM3-5945-000" in text:
            parts.append(
                {
                    "part": "FM3-5945-000",
                    "context": "FM3-5945-000 - Fuser Film",
                    "pattern_name": "canon_fuser",
                    "confidence": 0.92,
                    "manufacturer": "Canon",
                }
            )

        if "NPG-59" in text:
            parts.append(
                {
                    "part": "NPG-59",
                    "context": "NPG-59 - Toner Cartridge",
                    "pattern_name": "canon_toner",
                    "confidence": 0.9,
                    "manufacturer": "Canon",
                }
            )

        if "RG3-8213-000" in text:
            parts.append(
                {
                    "part": "RG3-8213-000",
                    "context": "RG3-8213-000 - Drum Unit",
                    "pattern_name": "canon_drum",
                    "confidence": 0.9,
                    "manufacturer": "Canon",
                }
            )

        # Lexmark Parts
        if "40X5852" in text:
            parts.append(
                {
                    "part": "40X5852",
                    "context": "Install 40X5852 - Toner Cartridge",
                    "pattern_name": "lexmark_consumable",
                    "confidence": 0.9,
                    "manufacturer": "Lexmark",
                }
            )

        if "12A8300" in text:
            parts.append(
                {
                    "part": "12A8300",
                    "context": "12A8300 - Fuser Unit",
                    "pattern_name": "lexmark_fuser",
                    "confidence": 0.9,
                    "manufacturer": "Lexmark",
                }
            )

        if "25A0001" in text:
            parts.append(
                {
                    "part": "25A0001",
                    "context": "25A0001 - Transfer Roller",
                    "pattern_name": "lexmark_transfer_roller",
                    "confidence": 0.9,
                    "manufacturer": "Lexmark",
                }
            )

        # Consumables
        if "CE285A" in text:
            parts.append(
                {
                    "part": "CE285A",
                    "context": "CE285A - Black Toner Cartridge",
                    "pattern_name": "hp_consumable",
                    "confidence": 0.95,
                    "manufacturer": "HP",
                }
            )

        if "Q7553X" in text:
            parts.append(
                {
                    "part": "Q7553X",
                    "context": "Q7553X - High Yield Toner",
                    "pattern_name": "hp_consumable",
                    "confidence": 0.9,
                    "manufacturer": "HP",
                }
            )

        if "CE285X" in text:
            parts.append(
                {
                    "part": "CE285X",
                    "context": "CE285X - High Yield Black Toner",
                    "pattern_name": "hp_consumable",
                    "confidence": 0.9,
                    "manufacturer": "HP",
                }
            )

        if "Q7553A" in text:
            parts.append(
                {
                    "part": "Q7553A",
                    "context": "Q7553A - Toner Cartridge",
                    "pattern_name": "hp_consumable",
                    "confidence": 0.9,
                    "manufacturer": "HP",
                }
            )

        return parts

    return mock_extract_parts_with_context


@pytest.fixture(scope="function")
def mock_series_detector():
    """Mock series_detector function with deterministic detection."""

    def mock_detect_series(model_number: str, manufacturer: str = "AUTO") -> dict[str, Any] | None:
        """Mock series detection returning predefined series based on model."""

        # HP LaserJet Series
        if model_number.startswith("M404") or model_number.startswith("M405"):
            return {
                "series_name": "LaserJet Pro M4xx",
                "model_pattern": "M40[0-9]",
                "series_description": "HP LaserJet Pro 400 series monochrome printers",
                "confidence": 0.9,
            }

        if model_number.startswith("M507") or model_number.startswith("M527"):
            return {
                "series_name": "LaserJet Enterprise M5xx",
                "model_pattern": "M5[0-2][0-9]",
                "series_description": "HP LaserJet Enterprise 500 series printers",
                "confidence": 0.85,
            }

        # HP OfficeJet Series
        if "OfficeJet Pro 9" in model_number:
            return {
                "series_name": "OfficeJet Pro 9xxx",
                "model_pattern": "OfficeJet Pro 9[0-9][0-9]",
                "series_description": "HP OfficeJet Pro 9000 series all-in-one printers",
                "confidence": 0.88,
            }

        # Konica Minolta bizhub Series
        if model_number.startswith("C40") or model_number.startswith("C45"):
            return {
                "series_name": "bizhub C4000 Series",
                "model_pattern": "C4[0-5][0-9]",
                "series_description": "Konica Minolta bizhub C4000 series color multifunction printers",
                "confidence": 0.92,
            }

        if "i-Series" in model_number and "A3" in model_number:
            return {
                "series_name": "bizhub i-Series",
                "model_pattern": "i-Series.*A3",
                "series_description": "Konica Minolta bizhub i-Series A3 production printers",
                "confidence": 0.9,
            }

        # Canon imageRUNNER Series
        if "ADVANCE C55" in model_number:
            return {
                "series_name": "imageRUNNER ADVANCE C5500 Series",
                "model_pattern": "ADVANCE C55[0-9][0-9]",
                "series_description": "Canon imageRUNNER ADVANCE C5500 series color multifunction printers",
                "confidence": 0.87,
            }

        # Lexmark CX Series
        if model_number.startswith("CX8") or model_number.startswith("CX9"):
            return {
                "series_name": "CX800 Series",
                "model_pattern": "CX[8-9][0-9][0-9]",
                "series_description": "Lexmark CX800 series color multifunction printers",
                "confidence": 0.85,
            }

        # Kyocera TASKalfa Series
        if model_number.startswith("505") and model_number.endswith("ci"):
            return {
                "series_name": "TASKalfa 5000 Series",
                "model_pattern": "505[0-9]ci",
                "series_description": "Kyocera TASKalfa 5000 series color multifunction printers",
                "confidence": 0.9,
            }

        # Ricoh IM Series
        if model_number.startswith("IM C6"):
            return {
                "series_name": "IM C6000 Series",
                "model_pattern": "IM C6[0-9][0-9]",
                "series_description": "Ricoh IM C6000 series color multifunction printers",
                "confidence": 0.88,
            }

        # Xerox VersaLink Series
        if model_number.startswith("C70") or model_number.startswith("C72"):
            return {
                "series_name": "VersaLink C7000 Series",
                "model_pattern": "C7[0-2][0-9]",
                "series_description": "Xerox VersaLink C7000 series color multifunction printers",
                "confidence": 0.86,
            }

        # Generic fallback
        return {
            "series_name": f"Generic {manufacturer} Series",
            "model_pattern": model_number[:3] + ".*",
            "series_description": f"Generic series for {manufacturer} devices",
            "confidence": 0.5,
        }

    return mock_detect_series


@pytest.fixture(scope="function")
def sample_pdf_with_error_codes() -> dict[str, Any]:
    """Create a PDF with realistic error code patterns for testing."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "error_codes_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()

        # Page 1: HP Error Codes
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "HP LaserJet Error Codes\n\n"
            "Error 13.A1.B2: Paper jam in tray 2. Solution: Remove paper from tray 2 and restart printer.\n"
            "Error 49.4C02: Firmware error. Solution: Power cycle printer and update firmware.\n"
            "Check control panel for specific error location.",
        )

        # Page 2: Konica Minolta Error Codes
        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Konica Minolta bizhub Error Codes\n\n"
            "Error C-2557: Developer unit error. Solution: Replace developer unit.\n"
            "Error J-0001: Fuser temperature error. Solution: Check fuser unit and temperature sensor.\n"
            "Contact service technician if error persists.",
        )

        # Page 3: Lexmark Error Codes
        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "Lexmark Error Codes\n\n"
            "Error 900.01: Fuser unit error. Solution: Replace fuser unit.\n"
            "Error 200.02: Memory error. Solution: Check memory modules and restart.\n"
            "Refer to user manual for detailed troubleshooting steps.",
        )

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "error_codes_count": 6,
            "description": "PDF with HP, Konica Minolta, and Lexmark error codes",
        }
    except ImportError:
        pdf_path.write_text(
            "HP Error 13.A1.B2: Paper jam in tray 2.\n"
            "HP Error 49.4C02: Firmware error.\n"
            "KM Error C-2557: Developer unit error.\n"
            "KM Error J-0001: Fuser temperature error.\n"
            "Lexmark Error 900.01: Fuser unit error.\n"
            "Lexmark Error 200.02: Memory error."
        )
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "error_codes_count": 6,
            "description": "Mock error codes PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_with_parts() -> dict[str, Any]:
    """Create a PDF with realistic part number patterns for testing."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "parts_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()

        # Page 1: HP Parts
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "HP LaserJet Parts List\n\n"
            "Replace part 6QN29-67005 - Fuser Unit\n"
            "Install RM1-1234-000 - Transfer Roller\n"
            "Consumables: CE285A Black Toner, Q7553X High Yield Toner",
        )

        # Page 2: Konica Minolta Parts
        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Konica Minolta bizhub Parts\n\n"
            "A1DU-R750-00 - Developer Unit\n"
            "Replace 4062-R750-01 - Drum Unit\n"
            "Genuine parts recommended for best performance.",
        )

        # Page 3: Canon and Lexmark Parts
        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "Canon and Lexmark Parts\n\n"
            "Canon: FM3-5945-000 - Fuser Film\n"
            "Lexmark: 40X5852 - Toner Cartridge\n"
            "Always use OEM parts for warranty coverage.",
        )

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "parts_count": 7,
            "description": "PDF with HP, Konica Minolta, Canon, and Lexmark parts",
        }
    except ImportError:
        pdf_path.write_text(
            "HP Parts: 6QN29-67005, RM1-1234-000, CE285A, Q7553X\n"
            "KM Parts: A1DU-R750-00, 4062-R750-01\n"
            "Canon Parts: FM3-5945-000\n"
            "Lexmark Parts: 40X5852"
        )
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "parts_count": 7,
            "description": "Mock parts PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_with_versions() -> dict[str, Any]:
    """Create a PDF with realistic version patterns for testing."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "versions_test.pdf"

    info: dict[str, Any]
    try:
        import fitz

        doc = fitz.open()

        # Page 1: Edition and Date versions
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "Service Manual Edition Information\n\n"
            "Edition 3, 5/2024\n"
            "Edition 4.0 - Latest Revision\n"
            "Publication Date: 2024/12/25\n"
            "Updated: November 2024",
        )

        # Page 2: Firmware and Version patterns
        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Firmware and Software Versions\n\n"
            "FW 4.2 - Current Firmware Version\n"
            "Firmware 4.2 - Latest Release\n"
            "Version 1.0 - Software Version\n"
            "v1.0 - Alternative Format",
        )

        # Page 3: Revision patterns
        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "Revision History\n\n"
            "Rev 1.0 - Initial Release\n"
            "Revision 1.0 - First Major Revision\n"
            "Document version control maintained",
        )

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "versions_count": 8,
            "description": "PDF with edition, date, firmware, version, and revision patterns",
        }
    except ImportError:
        pdf_path.write_text(
            "Edition 3, 5/2024\n"
            "Edition 4.0\n"
            "2024/12/25\n"
            "November 2024\n"
            "FW 4.2\n"
            "Firmware 4.2\n"
            "Version 1.0\n"
            "v1.0\n"
            "Rev 1.0\n"
            "Revision 1.0"
        )
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "versions_count": 8,
            "description": "Mock versions PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_pdf_multimodal_metadata() -> dict[str, Any]:
    """Create a PDF with mixed error codes, parts, versions, and images for integration tests."""
    temp_dir = Path(tempfile.mkdtemp(suffix=PROCESSOR_TEST_CONFIG["temp_dir_suffix"]))
    pdf_path = temp_dir / "multimodal_metadata_test.pdf"

    info: dict[str, Any]
    try:
        import io

        import fitz
        from PIL import Image

        doc = fitz.open()

        # Helper for embedding images
        def _embed_image(page, x: float, y: float, w: int, h: int, color: tuple) -> None:
            img = Image.new("RGB", (w, h), color=color)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            rect = fitz.Rect(x, y, x + w, y + h)
            page.insert_image(rect, stream=data)

        # Page 1: Error Codes + Image
        page1 = doc.new_page()
        page1.insert_text(
            (72, 72),
            "HP LaserJet Error Codes - Edition 3, 5/2024\n\n"
            "Error 13.A1.B2: Paper jam in tray 2. Solution: Remove paper from tray 2.\n"
            "Error 49.4C02: Firmware error. Solution: Power cycle printer.\n"
            "Parts: 6QN29-67005 Fuser Unit, RM1-1234-000 Transfer Roller",
        )
        _embed_image(page1, 320, 200, 160, 120, (255, 220, 200))

        # Page 2: Konica Minolta Parts + Version
        page2 = doc.new_page()
        page2.insert_text(
            (72, 72),
            "Konica Minolta bizhub Parts - FW 4.2\n\n"
            "A1DU-R750-00 - Developer Unit\n"
            "4062-R750-01 - Drum Unit\n"
            "Error C-2557: Developer unit failure",
        )
        _embed_image(page2, 300, 100, 180, 140, (200, 220, 255))

        # Page 3: Mixed Content
        page3 = doc.new_page()
        page3.insert_text(
            (72, 72),
            "Multi-Manufacturer Reference - Rev 1.0\n\n"
            "Canon: FM3-5945-000 Fuser Film\n"
            "Lexmark: 40X5852 Toner Cartridge, Error 900.01\n"
            "Version 1.0 - Document Revision",
        )
        _embed_image(page3, 320, 180, 140, 140, (220, 255, 220))

        doc.save(pdf_path)
        doc.close()

        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 3,
            "error_codes_count": 3,
            "parts_count": 5,
            "versions_count": 3,
            "image_count": 3,
            "description": "PDF with mixed error codes, parts, versions, and images",
        }
    except ImportError:
        pdf_path.write_text(
            "HP Error 13.A1.B2, 49.4C02 - Edition 3, 5/2024\n"
            "Parts: 6QN29-67005, RM1-1234-000\n"
            "KM Parts: A1DU-R750-00, 4062-R750-01 - FW 4.2\n"
            "Error C-2557\n"
            "Canon: FM3-5945-000\n"
            "Lexmark: 40X5852, Error 900.01 - Version 1.0"
        )
        info = {
            "path": pdf_path,
            "size": pdf_path.stat().st_size,
            "pages": 1,
            "error_codes_count": 3,
            "parts_count": 5,
            "versions_count": 3,
            "image_count": 0,
            "description": "Mock multimodal PDF (PyMuPDF not available)",
        }

    yield info

    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def create_test_error_code():
    """Factory for creating test ErrorCode objects."""

    def _create_error_code(
        error_code: str = "900.01",
        error_description: str = "Test error description",
        solution_text: str = "Test solution",
        page_number: int = 1,
        severity_level: str = "medium",
        confidence: float = 0.8,
    ):
        from backend.processors.models import ExtractedErrorCode

        return ExtractedErrorCode(
            error_code=error_code,
            error_description=error_description,
            solution_text=solution_text,
            context_text=f"Error {error_code}: {error_description}. Solution: {solution_text}.",
            page_number=page_number,
            severity_level=severity_level,
            confidence=confidence,
        )

    return _create_error_code


@pytest.fixture(scope="function")
def create_test_part():
    """Factory for creating test part dictionaries."""

    def _create_part(
        part_number: str = "TEST-001",
        manufacturer_id: str = "manuf-001",
        part_name: str = "Test Part",
        part_description: str = "Test part description",
        part_category: str = "component",
        document_id: str | None = None,
        chunk_id: str | None = None,
        context: str = "Test context",
    ) -> dict[str, Any]:
        return {
            "part_number": part_number,
            "manufacturer_id": manufacturer_id,
            "part_name": part_name,
            "part_description": part_description,
            "part_category": part_category,
            "document_id": document_id or str(uuid4()),
            "chunk_id": chunk_id or str(uuid4()),
            "context": context,
        }

    return _create_part


@pytest.fixture(scope="function")
def create_test_series():
    """Factory for creating test series dictionaries."""

    def _create_series(
        series_name: str = "Test Series",
        model_pattern: str = "TEST-.*",
        series_description: str = "Test series description",
        manufacturer_id: str = "manuf-001",
    ) -> dict[str, Any]:
        return {
            "series_name": series_name,
            "model_pattern": model_pattern,
            "series_description": series_description,
            "manufacturer_id": manufacturer_id,
        }

    return _create_series


@pytest.fixture(scope="function")
def create_test_product():
    """Factory for creating test product dictionaries."""

    def _create_product(
        model_number: str = "TEST-001", manufacturer_id: str = "manuf-001", series_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "id": str(uuid4()),
            "model_number": model_number,
            "manufacturer_id": manufacturer_id,
            "series_id": series_id,
        }

    return _create_product


@pytest.fixture(scope="function")
def create_sample_chunks_with_parts():
    """Factory for creating sample chunk dictionaries with embedded parts."""

    def _create_chunks(document_id: str | None = None) -> list[dict[str, Any]]:
        doc_id = document_id or str(uuid4())

        return [
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Replace part 6QN29-67005 - Fuser Unit. Check transfer roller RM1-1234-000.",
                "metadata": {"chunk_type": "parts_list"},
            },
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Install A1DU-R750-00 developer unit. Replace drum 4062-R750-01.",
                "metadata": {"chunk_type": "maintenance"},
            },
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Use CE285A black toner cartridge. High yield Q7553X available.",
                "metadata": {"chunk_type": "consumables"},
            },
        ]

    return _create_chunks


@pytest.fixture(scope="function")
def create_sample_error_code_chunks():
    """Factory for creating sample chunk dictionaries with error code patterns."""

    def _create_chunks(document_id: str | None = None) -> list[dict[str, Any]]:
        doc_id = document_id or str(uuid4())

        return [
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 0,
                "page_start": 1,
                "page_end": 1,
                "content": "Error 13.A1.B2: Paper jam in tray 2. Remove paper and restart.",
                "metadata": {"chunk_type": "error_codes"},
            },
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 1,
                "page_start": 2,
                "page_end": 2,
                "content": "Error 49.4C02: Firmware error. Power cycle and update firmware.",
                "metadata": {"chunk_type": "error_codes"},
            },
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 2,
                "page_start": 3,
                "page_end": 3,
                "content": "Error C-2557: Developer unit failure. Replace developer unit.",
                "metadata": {"chunk_type": "error_codes"},
            },
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "chunk_index": 3,
                "page_start": 4,
                "page_end": 4,
                "content": "Error 900.01: Fuser unit error. Replace fuser unit assembly.",
                "metadata": {"chunk_type": "error_codes"},
            },
        ]

    return _create_chunks


@pytest.fixture(scope="function")
def link_enrichment_service_with_mock_scraper(mock_database_adapter):
    """Real LinkEnrichmentService wired to a mocked WebScrapingService.

    Uses the mock_database_adapter for persistence and a simple scraper
    implementation that returns deterministic content, suitable for integration
    tests without external HTTP calls.
    """

    from backend.services.link_enrichment_service import LinkEnrichmentService

    class MockScraper:
        async def scrape_url(self, url: str, force_backend: str | None = None) -> dict[str, Any]:
            backend = force_backend or "firecrawl"
            return {
                "success": True,
                "backend": backend,
                "content": f"Scraped content for {url}",
                "html": f"<html><body>{url}</body></html>",
                "metadata": {"status_code": 200, "content_type": "text/html"},
            }

    class _Result:
        def __init__(self, data=None, count: int | None = None):
            self.data = data or []
            self.count = count

    class MockLinksTable:
        def __init__(self, storage: dict[str, dict[str, Any]]):
            self._storage = storage
            self._filters: dict[str, Any] = {}
            self._schema: str | None = None

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, column: str, value: Any):
            self._filters[column] = value
            return self

        def in_(self, column: str, values: list[Any]):
            self._filters[column] = set(values)
            return self

        def update(self, payload: dict[str, Any]):
            self._update_payload = payload
            return self

        def execute(self):
            results: list[dict[str, Any]] = []
            for link in self._storage.values():
                if "id" in self._filters and link.get("id") != self._filters["id"]:
                    continue
                if "document_id" in self._filters:
                    doc_ids = self._filters["document_id"]
                    if isinstance(doc_ids, set):
                        if link.get("document_id") not in doc_ids:
                            continue
                    elif link.get("document_id") != doc_ids:
                        continue
                results.append(link)

            if hasattr(self, "_update_payload") and results:
                for r in results:
                    r.update(self._update_payload)
                return _Result(data=results)

            return _Result(data=results)

    class MockSupabaseClient:
        def __init__(self, db):
            self._db = db

        def table(self, name: str, schema: str | None = None):
            if name == "links" and schema == "krai_content":
                if not hasattr(self._db, "links"):
                    self._db.links = {}
                return MockLinksTable(self._db.links)
            return MockLinksTable(getattr(self._db, "links", {}))

    mock_database_adapter.service_client = MockSupabaseClient(mock_database_adapter)

    scraper = MockScraper()
    service = LinkEnrichmentService(
        web_scraping_service=scraper,
        database_service=mock_database_adapter,
        config_service=None,
    )

    return service


def pytest_configure(config):
    """Configure pytest with processor-specific markers."""
    config.addinivalue_line("markers", "processor: Tests for processor components")
    config.addinivalue_line("markers", "upload: Tests for UploadProcessor")
    config.addinivalue_line("markers", "text: Tests for TextProcessor")
    config.addinivalue_line("markers", "document: Tests for DocumentProcessor")
    config.addinivalue_line("markers", "chunking: Tests for chunking functionality")
    config.addinivalue_line("markers", "extraction: Tests for text extraction")
    config.addinivalue_line("markers", "stage_tracking: Tests for stage tracking")
    config.addinivalue_line("markers", "table: Tests for TableProcessor")
    config.addinivalue_line("markers", "svg: Tests for SVGProcessor")
    config.addinivalue_line("markers", "image: Tests for ImageProcessor")
    config.addinivalue_line("markers", "visual_embedding: Tests for VisualEmbeddingProcessor")
    config.addinivalue_line("markers", "multimodal: Tests for multi-modal content handling")
    config.addinivalue_line("markers", "slow: Tests that take longer than 10 seconds")
    config.addinivalue_line("markers", "link: Tests for LinkExtractionProcessorAI and link extractor")
    config.addinivalue_line("markers", "chunk_prep: Tests for ChunkPreprocessor")
    config.addinivalue_line("markers", "classification: Tests for ClassificationProcessor and type detection")
    config.addinivalue_line("markers", "link_enrichment: Tests for LinkEnrichmentService integration")
    config.addinivalue_line("markers", "metadata: Tests for MetadataProcessorAI and error code/version extraction")
    config.addinivalue_line("markers", "parts: Tests for PartsProcessor and parts extraction")
    config.addinivalue_line("markers", "series: Tests for SeriesProcessor and series detection")
    config.addinivalue_line("markers", "storage: Tests for StorageProcessor and object storage integration")
    config.addinivalue_line("markers", "error_codes: Tests for error code extraction functionality")
    config.addinivalue_line("markers", "versions: Tests for version extraction functionality")
    config.addinivalue_line("markers", "storage: Tests requiring object storage")
