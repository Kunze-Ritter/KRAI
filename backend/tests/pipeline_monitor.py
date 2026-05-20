#!/usr/bin/env python3
"""
Pipeline Monitor Script
Real-time monitoring of pipeline stages and bottlenecks
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backend.services.database_adapter import create_database_adapter


class PipelineMonitor:
    def __init__(self):
        self.database_adapter = None

    async def initialize(self):
        """Initialize services"""
        print("🔧 Initializing Pipeline Monitor...")

        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv()

        # Initialize database adapter
        self.database_adapter = create_database_adapter()

        print("✅ Monitor initialized")

    async def get_pipeline_stats(self):
        """Get comprehensive pipeline statistics"""

        # Get document counts by stage
        doc_stats = await self.database_adapter.execute_query(
            """
            SELECT
                COUNT(*) as total_docs,
                COUNT(CASE WHEN manufacturer IS NOT NULL THEN 1 END) as classified_docs,
                COUNT(CASE WHEN manufacturer IS NULL THEN 1 END) as pending_classification,
                COUNT(CASE WHEN id IN (SELECT document_id FROM krai_content.chunks) THEN 1 END) as with_chunks,
                COUNT(CASE WHEN id IN (SELECT document_id FROM krai_content.images) THEN 1 END) as with_images
            FROM krai_core.documents
        """
        )

        # Get chunk and image counts
        chunk_stats = await self.database_adapter.execute_query(
            """
            SELECT
                COUNT(*) as total_chunks,
                COUNT(DISTINCT document_id) as docs_with_chunks,
                MAX(created_at) as latest_chunk
            FROM krai_content.chunks
        """
        )

        image_stats = await self.database_adapter.execute_query(
            """
            SELECT
                COUNT(*) as total_images,
                COUNT(DISTINCT document_id) as docs_with_images,
                MAX(created_at) as latest_image
            FROM krai_content.images
        """
        )

        # Get embedding counts
        embedding_stats = await self.database_adapter.execute_query(
            """
            SELECT
                COUNT(*) as total_embeddings,
                COUNT(DISTINCT chunk_id) as chunks_with_embeddings
            FROM krai_intelligence.embeddings
        """
        )

        return {
            "documents": doc_stats[0] if doc_stats else {},
            "chunks": chunk_stats[0] if chunk_stats else {},
            "images": image_stats[0] if image_stats else {},
            "embeddings": embedding_stats[0] if embedding_stats else {},
        }

    def print_pipeline_status(self, stats):
        """Print formatted pipeline status"""
        docs = stats["documents"]
        chunks = stats["chunks"]
        images = stats["images"]
        embeddings = stats["embeddings"]

        print(f"\n{'='*80}")
        print("🔍 PIPELINE MONITOR - Real-time Status")
        print(f"{'='*80}")

        # Document Pipeline Stages
        print("\n📄 DOCUMENT PIPELINE:")
        print(f"  Total Documents:     {docs.get('total_docs', 0):>6}")
        print(f"  Upload Complete:     {docs.get('total_docs', 0):>6} (100.0%)")
        print(
            f"  Text Processing:     {docs.get('with_chunks', 0):>6} ({docs.get('with_chunks', 0)/max(docs.get('total_docs', 1), 1)*100:.1f}%)"
        )
        print(
            f"  Image Processing:    {docs.get('with_images', 0):>6} ({docs.get('with_images', 0)/max(docs.get('total_docs', 1), 1)*100:.1f}%)"
        )
        print(
            f"  Classification:      {docs.get('classified_docs', 0):>6} ({docs.get('classified_docs', 0)/max(docs.get('total_docs', 1), 1)*100:.1f}%)"
        )

        # Data Processing
        print("\n📊 DATA PROCESSING:")
        print(f"  Total Chunks:        {chunks.get('total_chunks', 0):>6,}")
        print(f"  Total Images:        {images.get('total_images', 0):>6,}")
        print(f"  Total Embeddings:    {embeddings.get('total_embeddings', 0):>6,}")

        # Bottleneck Detection
        print("\n⚠️  BOTTLENECK ANALYSIS:")

        # Check for bottlenecks
        bottlenecks = []

        if docs.get("total_docs", 0) > 0:
            chunk_rate = docs.get("with_chunks", 0) / docs.get("total_docs", 1)
            if chunk_rate < 0.8:
                bottlenecks.append(f"Text Processing: Only {chunk_rate*100:.1f}% of documents have chunks")

            image_rate = docs.get("with_images", 0) / docs.get("total_docs", 1)
            if image_rate < 0.3:
                bottlenecks.append(f"Image Processing: Only {image_rate*100:.1f}% of documents have images")

            class_rate = docs.get("classified_docs", 0) / docs.get("total_docs", 1)
            if class_rate < 0.5:
                bottlenecks.append(f"Classification: Only {class_rate*100:.1f}% of documents classified")

        if bottlenecks:
            for bottleneck in bottlenecks:
                print(f"  🚨 {bottleneck}")
        else:
            print("  ✅ No major bottlenecks detected")

        # Recent Activity
        print("\n📈 RECENT ACTIVITY:")
        if chunks.get("latest_chunk"):
            print(f"  Latest Chunk:        {chunks.get('latest_chunk', 'Never')}")
        if images.get("latest_image"):
            print(f"  Latest Image:        {images.get('latest_image', 'Never')}")

        print(f"{'='*80}")

    async def monitor_loop(self):
        """Main monitoring loop"""
        print("🚀 Starting Pipeline Monitor...")
        print("Press Ctrl+C to stop")

        try:
            while True:
                stats = await self.get_pipeline_stats()
                self.print_pipeline_status(stats)

                # Wait 30 seconds before next update
                await asyncio.sleep(30)

        except KeyboardInterrupt:
            print("\n🛑 Monitor stopped by user")
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")


async def main():
    monitor = PipelineMonitor()
    await monitor.initialize()
    await monitor.monitor_loop()


if __name__ == "__main__":
    asyncio.run(main())
