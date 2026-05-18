#!/usr/bin/env python3
"""
Force Smart Processing Script
Verarbeitet alle Dokumente in der DB mit Smart Processing
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.krai_master_pipeline import KRMasterPipeline

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Main function to force smart processing for all documents"""
    logger.info("Starting Force Smart Processing for ALL documents")

    try:
        # Initialize pipeline
        pipeline = KRMasterPipeline()
        await pipeline.initialize_services()

        # Get ALL documents from database
        print("\n=== FORCE SMART PROCESSING - ALL DOCUMENTS ===")
        all_docs = pipeline.database_service.client.table("vw_documents").select("*").execute()

        if not all_docs.data:
            logger.info("No documents found in database!")
            return

        print(f"Found {len(all_docs.data)} total documents - forcing smart processing...")

        # Process all documents with smart processing
        results = {"successful": [], "failed": [], "total_files": len(all_docs.data)}

        for i, doc in enumerate(all_docs.data):
            print(f"\n[{i+1}/{len(all_docs.data)}] Forced Smart processing: {doc['filename']}")
            file_path = f"../service_documents/{doc['filename']}"

            result = await pipeline.process_document_smart_stages(doc["id"], doc["filename"], file_path)

            if result["success"]:
                results["successful"].append(result)
                print(f"✅ Successfully processed: {result['filename']}")
                if "completed_stages" in result:
                    print(f"   Completed stages: {', '.join(result['completed_stages'])}")
            else:
                results["failed"].append(result)
                print(
                    f"❌ Failed to process: {result.get('filename', 'Unknown')} - {result.get('error', 'Unknown error')}"
                )

        # Calculate success rate
        results["success_rate"] = len(results["successful"]) / len(all_docs.data) * 100

        # Print summary
        print("\n" + "=" * 80)
        print("FORCE SMART PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total Documents: {results['total_files']}")
        print(f"Successful: {len(results['successful'])}")
        print(f"Failed: {len(results['failed'])}")
        print(f"Success Rate: {results['success_rate']:.1f}%")
        print("=" * 80)

        if results["failed"]:
            print("\nFAILED DOCUMENTS:")
            for result in results["failed"]:
                print(f"  - {result.get('filename', 'Unknown')}: {result.get('error', 'Unknown error')}")

        logger.info("Force Smart Processing completed!")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
