#!/usr/bin/env python3
"""
Pipeline Recovery Script
Finds and processes documents stuck in pipeline stages
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from config.ai_config import ConfigService
from core.data_models import ProcessingContext
from processors.classification_processor import ClassificationProcessor
from processors.embedding_processor import EmbeddingProcessor
from processors.metadata_processor import MetadataProcessor
from processors.search_processor import SearchProcessor
from processors.storage_processor import StorageProcessor
from services.ai_service import AIService
from services.database_adapter import create_database_adapter
from services.storage_factory import create_storage_service


class PipelineRecovery:
    def __init__(self):
        self.database_adapter = None
        self.ai_service = None
        self.storage_service = None
        self.config_service = None

    async def initialize(self):
        """Initialize services"""
        print("🔧 Initializing Pipeline Recovery Services...")

        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv()

        # Initialize database adapter
        self.database_adapter = create_database_adapter()

        # Initialize AI service
        self.ai_service = AIService(ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"))
        await self.ai_service.connect()

        # Initialize storage service
        self.storage_service = create_storage_service()
        await self.storage_service.connect()

        # Initialize config service
        self.config_service = ConfigService()

        print("✅ Services initialized")

    async def find_stuck_documents(self):
        """Find documents stuck in pipeline stages"""
        print("🔍 Finding stuck documents...")

        # Find documents with chunks but no classification
        stuck_docs = await self.database_adapter.execute_query(
            """
            SELECT
                d.id,
                d.filename,
                d.file_path,
                d.created_at,
                COUNT(c.id) as chunk_count
            FROM krai_core.documents d
            LEFT JOIN krai_content.chunks c ON d.id = c.document_id
            WHERE d.manufacturer IS NULL AND d.id IN (
                SELECT DISTINCT document_id FROM krai_content.chunks
            )
            GROUP BY d.id, d.filename, d.file_path, d.created_at
            ORDER BY d.created_at ASC
            LIMIT 10
        """
        )

        print(f"📊 Found {len(stuck_docs)} documents stuck in classification stage")
        return stuck_docs

    async def recover_document(self, doc_data):
        """Recover a single document through remaining pipeline stages"""
        doc_id = doc_data["id"]
        filename = doc_data["filename"]
        file_path = doc_data["file_path"] or f"service_documents/{filename}"

        print(f"🔄 Recovering: {filename}")

        try:
            # Create processing context
            context = ProcessingContext(
                document_id=doc_id, file_path=file_path, processing_config={"filename": filename}
            )

            # Stage 4: Classification Processor
            print("  📋 Stage 4: Classification")
            classification_processor = ClassificationProcessor(
                self.database_adapter, self.ai_service, self.config_service
            )
            classification_result = await classification_processor.process(context)

            if classification_result.success:
                print("  ✅ Classification complete")

                # Stage 5: Metadata Processor
                print("  📊 Stage 5: Metadata")
                metadata_processor = MetadataProcessor(self.database_adapter, self.ai_service, self.config_service)
                metadata_result = await metadata_processor.process(context)

                if metadata_result.success:
                    print("  ✅ Metadata complete")

                    # Stage 6: Storage Processor
                    print("  💾 Stage 6: Storage")
                    storage_processor = StorageProcessor(self.database_adapter, self.storage_service)
                    storage_result = await storage_processor.process(context)

                    if storage_result.success:
                        print("  ✅ Storage complete")

                        # Stage 7: Embedding Processor
                        print("  🧠 Stage 7: Embeddings")
                        embedding_processor = EmbeddingProcessor(self.database_adapter, self.ai_service)
                        embedding_result = await embedding_processor.process(context)

                        if embedding_result.success:
                            print("  ✅ Embeddings complete")

                            # Stage 8: Search Processor
                            print("  🔍 Stage 8: Search")
                            search_processor = SearchProcessor(self.database_adapter, self.ai_service)
                            search_result = await search_processor.process(context)

                            if search_result.success:
                                print("  ✅ Search complete")
                                print(f"  🎉 {filename} fully recovered!")
                                return True

            print(f"  ❌ Recovery failed for {filename}")
            return False

        except Exception as e:
            print(f"  ❌ Error recovering {filename}: {e}")
            return False

    async def run_recovery(self):
        """Run the full recovery process"""
        print("🚀 Starting Pipeline Recovery...")

        # Find stuck documents
        stuck_docs = await self.find_stuck_documents()

        if not stuck_docs:
            print("✅ No stuck documents found!")
            return

        # Recover each document
        recovered = 0
        failed = 0

        for doc_data in stuck_docs:
            success = await self.recover_document(doc_data)
            if success:
                recovered += 1
            else:
                failed += 1

            # Small delay between documents
            await asyncio.sleep(1)

        print("\n📊 Recovery Summary:")
        print(f"  ✅ Recovered: {recovered}")
        print(f"  ❌ Failed: {failed}")
        print(f"  📈 Success Rate: {recovered/(recovered+failed)*100:.1f}%")


async def main():
    recovery = PipelineRecovery()
    await recovery.initialize()
    await recovery.run_recovery()


if __name__ == "__main__":
    asyncio.run(main())
