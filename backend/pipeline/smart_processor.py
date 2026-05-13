"""
KR-AI-Engine Smart Processor
============================
Ein neues Script das das Upload-Problem umgeht und direkt Smart Processing macht
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from backend.core.base_processor import ProcessingContext
from backend.processors.classification_processor import ClassificationProcessor
from backend.processors.embedding_processor import EmbeddingProcessor
from backend.processors.image_processor import ImageProcessor
from backend.processors.metadata_processor_ai import MetadataProcessorAI
from backend.processors.search_processor import SearchProcessor
from backend.processors.storage_processor import StorageProcessor
from backend.processors.text_processor_optimized import OptimizedTextProcessor
from backend.services.ai_service import AIService
from backend.services.config_service import ConfigService

# Import services
from backend.services.database_factory import create_database_adapter
from backend.services.features_service import FeaturesService
from backend.services.storage_factory import create_storage_service


class KRSmartProcessor:
    """Smart Processor der das Upload-Problem umgeht"""

    def __init__(self):
        self.database_service = None
        self.storage_service = None
        self.ai_service = None
        self.config_service = None
        self.features_service = None
        self.processors = {}

    async def initialize_services(self):
        """Initialize all services"""
        print("Initializing KR Smart Processor...")

        # Load environment variables
        env_files = ["env.database", "env.storage", "env.ai", "env.system", ".env"]

        base_paths = [".", "..", "../..", "../../.."]

        env_loaded = False
        for env_file in env_files:
            for base_path in base_paths:
                env_path = os.path.join(base_path, env_file)
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    env_loaded = True
                    print(f"✅ Loaded: {env_path}")

        if not env_loaded:
            raise RuntimeError("No .env files found")

        # Initialize services (PostgreSQL adapter)
        self.database_service = create_database_adapter()
        await self.database_service.connect()

        self.storage_service = create_storage_service()
        # Storage service factory supports MinIO, S3, R2, etc.
        await self.storage_service.connect()

        self.ai_service = AIService(ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"))
        await self.ai_service.connect()

        self.config_service = ConfigService()
        self.features_service = FeaturesService(self.ai_service, self.database_service)

        # Initialize processors
        self.processors = {
            "text": OptimizedTextProcessor(self.database_service, self.config_service),
            "image": ImageProcessor(self.database_service, self.storage_service, self.ai_service),
            "classification": ClassificationProcessor(self.database_service, self.ai_service, self.features_service),
            "metadata": MetadataProcessorAI(self.database_service, self.ai_service, self.config_service),
            "storage": StorageProcessor(self.database_service, self.storage_service),
            "embedding": EmbeddingProcessor(self.database_service, self.ai_service),
            "search": SearchProcessor(self.database_service, self.ai_service),
        }
        print("All services initialized!")

    async def get_all_documents(self):
        """Get all documents from database"""
        try:
            rows = await self.database_service.execute_query("SELECT * FROM public.vw_documents")
            return rows if rows else []
        except Exception as e:
            print(f"Error getting documents: {e}")
            return []

    async def process_document_smart_stages(self, document_id: str, filename: str, file_path: str) -> dict:
        """Process only the missing stages for a document"""
        try:
            print(f"\n🔄 Smart Processing: {filename}")
            print(f"   Document ID: {document_id}")

            # Create processing context
            context = ProcessingContext(
                file_path=file_path,
                document_id=document_id,
                file_hash="",
                document_type="",
                processing_config={"filename": filename},
                file_size=0,
            )

            # Get document info from database
            doc_info = await self.database_service.get_document(document_id)
            if doc_info:
                context.file_hash = doc_info.file_hash if doc_info.file_hash else ""
                context.document_type = doc_info.document_type if doc_info.document_type else ""

            completed_stages = []
            failed_stages = []

            # Check and process missing stages
            stages_to_check = [
                ("text", "Text Processing", self.processors["text"]),
                ("image", "Image Processing", self.processors["image"]),
                ("classification", "Classification", self.processors["classification"]),
                ("metadata", "Metadata", self.processors["metadata"]),
                ("storage", "Storage", self.processors["storage"]),
                ("embedding", "Embeddings", self.processors["embedding"]),
                ("search", "Search", self.processors["search"]),
            ]

            for stage_name, stage_display, processor in stages_to_check:
                print(f"   🔍 Checking {stage_display}...")

                # Simple check if stage is needed
                if stage_name == "text":
                    # Check if chunks exist
                    chunks_count = await self.database_service.count_chunks_by_document(document_id)
                    if chunks_count > 0:
                        print(f"   ✅ {stage_display} already completed")
                        continue
                elif stage_name == "image":
                    # Check if images exist
                    images_count = await self.database_service.count_images_by_document(document_id)
                    if images_count > 0:
                        print(f"   ✅ {stage_display} already completed")
                        continue
                elif stage_name == "classification":
                    # Check if document is classified
                    if doc_info and doc_info.manufacturer_id:
                        print(f"   ✅ {stage_display} already completed")
                        continue
                elif stage_name == "embedding":
                    # Check if embeddings exist via view alias
                    rows = await self.database_service.execute_query(
                        "SELECT COUNT(*) AS cnt FROM public.vw_embeddings WHERE document_id = %s", [document_id]
                    )
                    embedding_count = rows[0]["cnt"] if rows else 0
                    if embedding_count > 0:
                        print(f"   ✅ {stage_display} already completed")
                        continue

                # Process stage
                print(f"   🔄 Processing {stage_display}...")
                try:
                    result = await processor.process(context)
                    if result.success:
                        completed_stages.append(stage_name)
                        print(f"   ✅ {stage_display} completed")

                        # Show some stats
                        if stage_name == "text" and hasattr(result, "data"):
                            chunks_count = result.data.get("chunks_created", 0)
                            if chunks_count > 0:
                                print(f"      📄 Created {chunks_count} chunks")
                        elif stage_name == "image" and hasattr(result, "data"):
                            images_count = result.data.get("images_processed", 0)
                            if images_count > 0:
                                print(f"      🖼️  Processed {images_count} images")
                        elif stage_name == "embedding" and hasattr(result, "data"):
                            embeddings_count = result.data.get("embeddings_created", 0)
                            if embeddings_count > 0:
                                print(f"      🔮 Created {embeddings_count} embeddings")
                    else:
                        failed_stages.append(stage_name)
                        print(f"   ❌ {stage_display} failed: {result.message}")
                except Exception as e:
                    failed_stages.append(stage_name)
                    print(f"   ❌ {stage_display} error: {e}")

            # Update document status
            if not failed_stages:
                await self.database_service.update_document_status(document_id, "completed")
                print(f"   ✅ Document {filename} fully processed!")
            else:
                await self.database_service.update_document_status(document_id, "failed")
                print(f"   ⚠️  Document {filename} partially processed (failed: {failed_stages})")

            return {
                "success": len(failed_stages) == 0,
                "filename": filename,
                "completed_stages": completed_stages,
                "failed_stages": failed_stages,
            }

        except Exception as e:
            print(f"Error in smart processing: {e}")
            return {"success": False, "filename": filename, "error": str(e)}


async def main():
    """Main function"""
    print("🚀 KR-AI-ENGINE SMART PROCESSOR")
    print("=" * 50)
    print("Umgeht das Upload-Problem und macht direkt Smart Processing!")
    print("=" * 50)

    # Initialize processor
    processor = KRSmartProcessor()
    await processor.initialize_services()

    # Get all documents
    print("\n📋 Getting all documents from database...")
    documents = await processor.get_all_documents()

    if not documents:
        print("❌ No documents found in database!")
        return

    print(f"✅ Found {len(documents)} documents")

    # Show first few documents
    print("\n📄 First 5 documents:")
    for i, doc in enumerate(documents[:5]):
        print(f"   {i+1}. {doc.get('filename', 'Unknown')} - Status: {doc.get('processing_status', 'unknown')}")

    if len(documents) > 5:
        print(f"   ... and {len(documents) - 5} more")

    # Ask for confirmation
    response = input(f"\n🔄 Process ALL {len(documents)} documents with Smart Processing? (y/n): ").lower().strip()
    if response != "y":
        print("❌ Processing cancelled.")
        return

    # Process all documents
    results = {"successful": [], "failed": [], "total": len(documents)}

    for i, doc in enumerate(documents):
        document_id = doc["id"]
        filename = doc.get("filename", f"Document_{document_id}")
        file_path = f"../service_documents/{filename}"

        print(f"\n[{i+1}/{len(documents)}] Processing: {filename}")

        result = await processor.process_document_smart_stages(document_id, filename, file_path)

        if result["success"]:
            results["successful"].append(result)
        else:
            results["failed"].append(result)

    # Show summary
    print(f"\n{'='*50}")
    print("🎯 SMART PROCESSING SUMMARY")
    print(f"{'='*50}")
    print(f"Total Documents: {results['total']}")
    print(f"Successful: {len(results['successful'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Success Rate: {len(results['successful'])/results['total']*100:.1f}%")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
