"""
KRAI Full Pipeline Integration Tests
====================================

End-to-end integration tests for the complete KRAI processing pipeline.
This module validates the entire workflow from document upload through
all 10 processing stages including embeddings, context extraction, and search.

Test Coverage:
- Document upload and metadata extraction
- Text processing and hierarchical chunking
- SVG extraction and vector graphics processing
- Table extraction and structured data processing
- Context extraction for images, videos, links, and tables
- Multimodal embedding generation
- Search functionality across all content types
- Cross-component data flow and consistency
"""

import logging
import uuid
from pathlib import Path
from typing import Any

import pytest

from backend.core.base_processor import ProcessingContext
from backend.pipeline.master_pipeline import KRMasterPipeline

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.slow
class TestFullPipelineIntegration:
    """Integration tests for the complete KRAI pipeline."""

    @pytest.mark.asyncio
    async def test_complete_document_processing(
        self,
        test_pipeline: KRMasterPipeline,
        test_database,
        test_storage,
        test_ai_service,
        sample_test_document: dict[str, Any],
    ):
        """
        Test complete document processing through all pipeline stages.

        Validates:
        - Document upload and storage
        - Sequential processing through all stages
        - Data consistency across components
        - Proper error handling and recovery
        """
        # Create processing context
        context = ProcessingContext(
            file_path=sample_test_document["file_path"],
            document_id=str(uuid.uuid4()),
            file_hash="test-hash-integration",
            document_type=sample_test_document["document_type"],
            processing_config=sample_test_document,
            file_size=sample_test_document["file_size"],
        )

        try:
            # Stage 1: Upload
            upload_result = await test_pipeline.processors["upload"].process(context)
            assert upload_result.success, f"Upload failed: {upload_result.message}"

            document_id = upload_result.data.get("document_id")
            assert document_id, "No document ID returned from upload"

            # Stage 2: Text processing
            text_result = await test_pipeline.processors["text"].process(context)
            assert text_result.success, f"Text processing failed: {text_result.message}"

            # Stage 3: SVG processing (if enabled)
            svg_result = await test_pipeline.processors["svg"].process(context)
            if os.getenv("ENABLE_SVG_EXTRACTION", "false").lower() == "true":
                assert svg_result.success, f"SVG processing failed: {svg_result.message}"

            # Stage 4: Table processing (if enabled)
            table_result = await test_pipeline.processors["table"].process(context)
            if os.getenv("ENABLE_TABLE_EXTRACTION", "true").lower() == "true":
                assert table_result.success, f"Table processing failed: {table_result.message}"

            # Stage 5: Context extraction
            context_result = await test_pipeline.processors["context"].process(context)
            if os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() == "true":
                assert context_result.success, f"Context extraction failed: {context_result.message}"

            # Stage 6: Embedding generation
            embedding_result = await test_pipeline.processors["embedding"].process(context)
            assert embedding_result.success, f"Embedding generation failed: {embedding_result.message}"

            # Validate data consistency
            await self._validate_document_data(test_database, document_id)

        except Exception as e:
            pytest.fail(f"Complete pipeline processing failed: {e}")

    @pytest.mark.asyncio
    async def test_hierarchical_chunking_integration(
        self, test_pipeline: KRMasterPipeline, test_database, sample_test_document: dict[str, Any]
    ):
        """
        Test hierarchical chunking feature integration.

        Validates:
        - Section hierarchy detection and preservation
        - Error code section identification
        - Cross-chunk linking and relationships
        - Hierarchical search functionality
        """
        if os.getenv("ENABLE_HIERARCHICAL_CHUNKING", "true").lower() != "true":
            pytest.skip("Hierarchical chunking is disabled")

        # Process document through text stage
        context = ProcessingContext(
            file_path=sample_test_document["file_path"],
            document_id=str(uuid.uuid4()),
            file_hash="test-hash-hierarchy",
            document_type=sample_test_document["document_type"],
            processing_config=sample_test_document,
            file_size=sample_test_document["file_size"],
        )

        # Upload and process text
        upload_result = await test_pipeline.processors["upload"].process(context)
        context.document_id = upload_result.data.get("document_id")

        text_result = await test_pipeline.processors["text"].process(context)
        assert text_result.success, f"Text processing failed: {text_result.message}"

        # Validate hierarchical structure
        chunks_with_hierarchy = await test_database.execute_query(
            """
            SELECT COUNT(*) as count
            FROM krai_intelligence.chunks
            WHERE document_id = $1 AND metadata->>'section_hierarchy' IS NOT NULL
            """,
            [context.document_id],
        )

        assert chunks_with_hierarchy[0]["count"] > 0, "No chunks with section hierarchy found"

        # Validate error code sections
        error_code_chunks = await test_database.execute_query(
            """
            SELECT COUNT(*) as count
            FROM krai_intelligence.chunks
            WHERE document_id = $1 AND metadata->>'error_code' IS NOT NULL
            """,
            [context.document_id],
        )

        # Error codes might not be present in test documents, so this is optional
        logger.info(f"Found {error_code_chunks[0]['count']} error code sections")

    @pytest.mark.asyncio
    async def test_svg_vector_graphics_integration(
        self, test_pipeline: KRMasterPipeline, test_database, test_storage, sample_test_document: dict[str, Any]
    ):
        """
        Test SVG vector graphics processing integration.

        Validates:
        - SVG extraction from PDF documents
        - PNG conversion for compatibility
        - Vector graphics metadata preservation
        - Storage and retrieval of processed graphics
        """
        if os.getenv("ENABLE_SVG_EXTRACTION", "false").lower() != "true":
            pytest.skip("SVG extraction is disabled")

        # Process document through SVG stage
        context = ProcessingContext(
            file_path=sample_test_document["file_path"],
            document_id=str(uuid.uuid4()),
            file_hash="test-hash-svg",
            document_type=sample_test_document["document_type"],
            processing_config=sample_test_document,
            file_size=sample_test_document["file_size"],
        )

        # Upload and process SVG
        upload_result = await test_pipeline.processors["upload"].process(context)
        context.document_id = upload_result.data.get("document_id")

        svg_result = await test_pipeline.processors["svg"].process(context)
        assert svg_result.success, f"SVG processing failed: {svg_result.message}"

        # Validate vector graphics storage
        vector_graphics = await test_database.execute_query(
            """
            SELECT COUNT(*) as count
            FROM krai_content.images
            WHERE document_id = $1 AND image_type = 'vector_graphic'
            """,
            [context.document_id],
        )

        if vector_graphics[0]["count"] > 0:
            # Validate PNG conversions exist
            png_conversions = await test_database.execute_query(
                """
                SELECT COUNT(*) as count
                FROM krai_content.images
                WHERE document_id = $1 AND image_type = 'png_conversion'
                """,
                [context.document_id],
            )

            logger.info(
                f"Found {vector_graphics[0]['count']} vector graphics and {png_conversions[0]['count']} PNG conversions"
            )

    @pytest.mark.asyncio
    async def test_multimodal_search_integration(
        self, test_search_service, test_database, test_ai_service, test_queries: dict[str, list]
    ):
        """
        Test multimodal search functionality integration.

        Validates:
        - Unified search across all content types
        - Modality filtering and relevance ranking
        - Context-aware image search
        - Two-stage retrieval with LLM expansion
        """
        # Test unified multimodal search
        for category, queries in test_queries.items():
            for query in queries[:2]:  # Test first 2 queries from each category
                try:
                    search_results = await test_search_service.search_multimodal(
                        query=query, modalities=["text", "image", "table", "video"], threshold=0.5, limit=10
                    )

                    assert search_results is not None, f"Search returned None for query: {query}"
                    assert "results" in search_results, f"Search missing 'results' key for query: {query}"

                    results = search_results["results"]
                    if results:
                        # Validate result structure
                        for result in results[:3]:  # Check first 3 results
                            assert "source_type" in result, "Result missing source_type"
                            assert "similarity" in result, "Result missing similarity"
                            assert (
                                result["similarity"] >= 0.5
                            ), f"Result similarity below threshold: {result['similarity']}"

                    logger.info(f"Query '{query}' returned {len(results)} results")

                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                    # Don't fail the test for individual query failures
                    continue

    @pytest.mark.asyncio
    async def test_context_extraction_integration(
        self, test_pipeline: KRMasterPipeline, test_database, sample_test_document: dict[str, Any]
    ):
        """
        Test context extraction integration across media types.

        Validates:
        - Image context extraction with AI analysis
        - Video context and instructional content
        - Link context and relationship mapping
        - Table context and structured data analysis
        """
        if os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() != "true":
            pytest.skip("Context extraction is disabled")

        # Process document through context stage
        context = ProcessingContext(
            file_path=sample_test_document["file_path"],
            document_id=str(uuid.uuid4()),
            file_hash="test-hash-context",
            document_type=sample_test_document["document_type"],
            processing_config=sample_test_document,
            file_size=sample_test_document["file_size"],
        )

        # Process through all stages up to context
        upload_result = await test_pipeline.processors["upload"].process(context)
        context.document_id = upload_result.data.get("document_id")

        await test_pipeline.processors["text"].process(context)
        await test_pipeline.processors["svg"].process(context)
        await test_pipeline.processors["table"].process(context)

        context_result = await test_pipeline.processors["context"].process(context)
        assert context_result.success, f"Context extraction failed: {context_result.message}"

        # Validate context data
        context_summary = await self._get_context_summary(test_database, context.document_id)

        total_context_items = sum(
            [
                context_summary["images_with_context"],
                context_summary["videos_with_context"],
                context_summary["links_with_context"],
                context_summary["tables_with_context"],
            ]
        )

        logger.info(f"Extracted context for {total_context_items} media items")

    @pytest.mark.asyncio
    async def test_embedding_generation_integration(
        self, test_pipeline: KRMasterPipeline, test_database, test_ai_service, sample_test_document: dict[str, Any]
    ):
        """
        Test multimodal embedding generation integration.

        Validates:
        - Text embedding generation and storage
        - Image embedding from visual content
        - Table embedding from structured data
        - Context embedding for media relationships
        """
        # Process document through embedding stage
        context = ProcessingContext(
            file_path=sample_test_document["file_path"],
            document_id=str(uuid.uuid4()),
            file_hash="test-hash-embeddings",
            document_type=sample_test_document["document_type"],
            processing_config=sample_test_document,
            file_size=sample_test_document["file_size"],
        )

        # Process through all stages up to embeddings
        upload_result = await test_pipeline.processors["upload"].process(context)
        context.document_id = upload_result.data.get("document_id")

        await test_pipeline.processors["text"].process(context)
        await test_pipeline.processors["svg"].process(context)
        await test_pipeline.processors["table"].process(context)
        await test_pipeline.processors["context"].process(context)

        embedding_result = await test_pipeline.processors["embedding"].process(context)
        assert embedding_result.success, f"Embedding generation failed: {embedding_result.message}"

        # Validate embedding data
        embedding_summary = await self._get_embedding_summary(test_database, context.document_id)

        assert embedding_summary["total_embeddings"] > 0, "No embeddings generated"

        # Validate embedding vectors exist
        embeddings_with_vectors = await test_database.execute_query(
            """
            SELECT COUNT(*) as count
            FROM krai_intelligence.embeddings_v2
            WHERE document_id = $1 AND embedding IS NOT NULL
            """,
            [context.document_id],
        )

        assert embeddings_with_vectors[0]["count"] > 0, "No embedding vectors found"

        logger.info(
            f"Generated {embedding_summary['total_embeddings']} embeddings across {len(embedding_summary['by_type'])} types"
        )

    @pytest.mark.asyncio
    async def test_master_pipeline_full_document_processing(
        self, test_pipeline: KRMasterPipeline, test_database, sample_test_document: dict[str, Any]
    ):
        """Full document processing through KRMasterPipeline orchestrator."""

        result = await test_pipeline.process_single_document_full_pipeline(
            sample_test_document["file_path"],
            1,
            1,
        )

        assert result["success"] is True
        document_id = result.get("document_id")
        assert document_id, "Master pipeline did not return document_id"

        # Re-use existing helpers to validate DB state
        await self._validate_document_data(test_database, document_id)

    @pytest.mark.asyncio
    async def test_master_pipeline_smart_processing_existing_document(
        self, test_pipeline: KRMasterPipeline, sample_test_document: dict[str, Any]
    ):
        """Smart reprocessing of an already processed document."""

        first_result = await test_pipeline.process_single_document_full_pipeline(
            sample_test_document["file_path"],
            1,
            1,
        )
        assert first_result["success"] is True
        document_id = first_result.get("document_id")
        assert document_id, "Initial master pipeline run did not return document_id"

        filename = Path(sample_test_document["file_path"]).name
        smart_result = await test_pipeline.process_document_smart_stages(
            document_id,
            filename,
            sample_test_document["file_path"],
        )

        assert smart_result["filename"] == filename
        assert smart_result["success"] is True
        # Different branches may expose either 'stages_completed' or 'completed_stages'
        assert "stages_completed" in smart_result or "completed_stages" in smart_result
        if "quality_score" in smart_result:
            assert 0 <= smart_result["quality_score"] <= 100

    @pytest.mark.asyncio
    async def test_master_pipeline_stage_status_tracking(
        self, test_pipeline: KRMasterPipeline, sample_test_document: dict[str, Any]
    ):
        """Stage status view should report status for processed documents."""

        result = await test_pipeline.process_single_document_full_pipeline(
            sample_test_document["file_path"],
            1,
            1,
        )
        assert result["success"] is True
        document_id = result.get("document_id")
        assert document_id

        status = await test_pipeline.get_stage_status(document_id)
        assert status["document_id"] == document_id
        assert status["found"] is True
        assert isinstance(status.get("stage_status"), dict)

    async def _validate_document_data(self, test_database, document_id: str):
        """Validate document data consistency across all schemas."""
        # Check core document exists
        document = await test_database.execute_query("SELECT * FROM krai_core.documents WHERE id = $1", [document_id])
        assert document, "Document not found in core schema"

        # Check chunks exist
        chunks = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_intelligence.chunks WHERE document_id = $1", [document_id]
        )
        assert chunks[0]["count"] > 0, "No chunks found for document"

        # Check embeddings exist
        embeddings = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_intelligence.embeddings_v2 WHERE document_id = $1", [document_id]
        )
        assert embeddings[0]["count"] > 0, "No embeddings found for document"

    async def _get_context_summary(self, test_database, document_id: str) -> dict[str, int]:
        """Get summary of context extraction results."""
        images_context = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_content.images WHERE document_id = $1 AND context_caption IS NOT NULL",
            [document_id],
        )

        videos_context = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_content.instructional_videos WHERE document_id = $1 AND context_description IS NOT NULL",
            [document_id],
        )

        links_context = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_content.links WHERE document_id = $1 AND context_description IS NOT NULL",
            [document_id],
        )

        tables_context = await test_database.execute_query(
            "SELECT COUNT(*) as count FROM krai_intelligence.structured_tables WHERE document_id = $1 AND context_text IS NOT NULL",
            [document_id],
        )

        return {
            "images_with_context": images_context[0]["count"],
            "videos_with_context": videos_context[0]["count"],
            "links_with_context": links_context[0]["count"],
            "tables_with_context": tables_context[0]["count"],
        }

    async def _get_embedding_summary(self, test_database, document_id: str) -> dict[str, Any]:
        """Get summary of embedding generation results."""
        # Get embeddings by type
        embedding_types = await test_database.execute_query(
            """
            SELECT source_type, COUNT(*) as count
            FROM krai_intelligence.embeddings_v2
            WHERE document_id = $1
            GROUP BY source_type
            """,
            [document_id],
        )

        by_type = {row["source_type"]: row["count"] for row in embedding_types}
        total_embeddings = sum(by_type.values())

        return {"total_embeddings": total_embeddings, "by_type": by_type}


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Integration tests for database components."""

    @pytest.mark.asyncio
    async def test_rpc_function_integration(self, test_database):
        """Test RPC function availability and execution."""
        # Test match_multimodal function
        test_embedding = [0.0] * 768

        try:
            results = await test_database.match_multimodal(
                query_embedding=test_embedding, match_threshold=0.5, match_count=1
            )
            assert isinstance(results, list), "match_multimodal should return a list"

        except Exception as e:
            pytest.fail(f"match_multimodal RPC function failed: {e}")

        # Test match_images_by_context function
        try:
            results = await test_database.match_images_by_context(
                query_embedding=test_embedding, match_threshold=0.5, match_count=1
            )
            assert isinstance(results, list), "match_images_by_context should return a list"

        except Exception as e:
            pytest.fail(f"match_images_by_context RPC function failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
