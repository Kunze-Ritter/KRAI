"""
Live Pipeline Test - Real Document Processing

Tests the complete pipeline with a real PDF and database connection.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.services.database_adapter import create_database_adapter


def test_database_connection():
    """Test database connection"""
    print("\n" + "=" * 80)
    print("TEST 1: Database Connection")
    print("=" * 80)

    try:
        database_adapter = create_database_adapter()

        # Test query
        result = database_adapter.select("krai_core.documents", columns=["id"], limit=1)

        print("\n✅ Database connected!")
        print("   Documents table accessible")

        return database_adapter

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def find_test_pdf():
    """Find test PDF"""
    print("\n" + "=" * 80)
    print("TEST 2: Find Test PDF")
    print("=" * 80)

    # Try multiple locations
    possible_paths = [
        Path(
            "C:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
        ),
        Path(__file__).parent.parent.parent
        / "AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf",
        Path(__file__).parent.parent.parent / "test.pdf",
    ]

    for pdf_path in possible_paths:
        if pdf_path.exists():
            print("\n✅ Found test PDF!")
            print(f"   Path: {pdf_path}")
            print(f"   Size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")
            return pdf_path

    print("\n❌ No test PDF found")
    print("\nTried:")
    for path in possible_paths:
        print(f"   - {path}")

    return None


def test_pipeline_initialization(database_adapter):
    """Test pipeline initialization"""
    print("\n" + "=" * 80)
    print("TEST 3: Pipeline Initialization")
    print("=" * 80)

    try:
        pipeline = KRMasterPipeline(
            database_adapter=database_adapter,
            manufacturer="Konica Minolta",
            enable_images=True,
            enable_ocr=True,
            enable_vision=True,
            enable_r2_storage=False,  # Skip R2 for test
            enable_embeddings=True,
            max_retries=2,
        )

        print("\n✅ Pipeline initialized!")
        print(f"   Manufacturer: {pipeline.manufacturer}")
        print(f"   Images: {pipeline.enable_images}")
        print(f"   OCR: {pipeline.enable_ocr}")
        print(f"   Vision AI: {pipeline.enable_vision}")
        print(f"   Embeddings: {pipeline.enable_embeddings}")

        return pipeline

    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_full_pipeline(pipeline, pdf_path):
    """Test full pipeline processing"""
    print("\n" + "=" * 80)
    print("TEST 4: Full Pipeline Processing")
    print("=" * 80)
    print("\n>>> Processing document...")
    print(f"   File: {pdf_path.name}")
    print(f"   Size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")
    print("\n>>> This may take 1-2 minutes for large documents...")

    try:
        result = pipeline.process_document(
            file_path=pdf_path, document_type="service_manual", manufacturer="Konica Minolta"
        )

        if result["success"]:
            print("\n" + "=" * 80)
            print("✅ PIPELINE SUCCESS!")
            print("=" * 80)

            print("\n📊 Summary:")
            print(f"   Document ID: {result['document_id']}")
            print(f"   Processing Time: {result['processing_time']:.1f}s")

            # Get stage results
            processing = result["results"].get("processing", {})

            if processing:
                metadata = processing.get("metadata", {})
                print("\n📄 Document:")
                print(f"   Pages: {metadata.get('page_count', 0)}")
                print(f"   Words: {metadata.get('word_count', 0):,}")
                print(f"   Characters: {metadata.get('char_count', 0):,}")

                print("\n📦 Extracted:")
                products = processing.get("products", [])
                error_codes = processing.get("error_codes", [])
                versions = processing.get("versions", [])
                images = processing.get("images", [])
                chunks = processing.get("chunks", [])

                print(f"   Products: {len(products)}")
                if products and len(products) > 0:
                    print(f"      Example: {products[0].get('model_name', 'N/A')}")

                print(f"   Error Codes: {len(error_codes)}")
                if error_codes and len(error_codes) > 0:
                    print(f"      Example: {error_codes[0].get('code', 'N/A')}")

                print(f"   Versions: {len(versions)}")
                if versions and len(versions) > 0:
                    print(f"      Example: {versions[0].get('version_string', 'N/A')}")

                print(f"   Images: {len(images)}")
                if images and len(images) > 0:
                    print(f"      Example: {images[0].get('filename', 'N/A')} ({images[0].get('type', 'unknown')})")

                print(f"   Chunks: {len(chunks)}")

                # Embeddings
                embeddings = result["results"].get("embeddings", {})
                if embeddings and embeddings.get("success"):
                    print("\n🔮 Embeddings:")
                    print(f"   Created: {embeddings.get('embeddings_created', 0)}")
                    print(f"   Time: {embeddings.get('processing_time', 0):.1f}s")
                    rate = embeddings.get("embeddings_created", 0) / max(embeddings.get("processing_time", 1), 1)
                    print(f"   Speed: {rate:.1f} embeddings/second")

            print("\n✅ Document is now searchable!")

            return True

        print("\n" + "=" * 80)
        print("❌ PIPELINE FAILED")
        print("=" * 80)
        print(f"\nError: {result.get('error')}")

        # Show which stages completed
        if "results" in result:
            print("\n📊 Completed Stages:")
            for stage_name, stage_result in result["results"].items():
                status = "✅" if stage_result.get("success") else "❌"
                print(f"   {status} {stage_name}")

        return False

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ EXCEPTION!")
        print("=" * 80)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run live pipeline test"""

    print("\n" + "=" * 80)
    print("   LIVE PIPELINE TEST")
    print("   Real Document + Real Database")
    print("=" * 80)

    # Test 1: Database
    database_adapter = test_database_connection()
    if not database_adapter:
        print("\n⚠️  Cannot continue without database connection")
        return

    # Test 2: Find PDF
    pdf_path = find_test_pdf()
    if not pdf_path:
        print("\n⚠️  Cannot continue without test PDF")
        return

    # Test 3: Initialize Pipeline
    pipeline = test_pipeline_initialization(database_adapter)
    if not pipeline:
        print("\n⚠️  Cannot continue without pipeline")
        return

    # Test 4: Run Pipeline
    success = test_full_pipeline(pipeline, pdf_path)

    # Summary
    print("\n" + "=" * 80)
    print("  FINAL RESULT")
    print("=" * 80)

    if success:
        print("\n  >>> ALL TESTS PASSED!")
        print("\n  The pipeline is working end-to-end!")
        print("  You can now:")
        print("    - Search the document semantically")
        print("    - Query products, error codes, versions")
        print("    - Use the extracted images")
    else:
        print("\n  [!] PIPELINE FAILED")
        print("\n  Check the logs above for details")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
