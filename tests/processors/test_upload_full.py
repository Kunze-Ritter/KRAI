"""
Comprehensive Upload Processor Tests with Real Database
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

from backend.services.database_adapter import create_database_adapter

# Load environment
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from backend.processors.upload_processor import BatchUploadProcessor, UploadProcessor

logger = get_logger()


class UploadProcessorTester:
    """Comprehensive test suite for Upload Processor"""

    def __init__(self):
        """Initialize tester with database connection"""
        self.database_adapter = create_database_adapter()
        self.processor = UploadProcessor(database_adapter=self.database_adapter, max_file_size_mb=500)
        self.test_results = {"passed": 0, "failed": 0, "tests": []}

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "=" * 80)
        print("🧪 UPLOAD PROCESSOR - COMPREHENSIVE TEST SUITE")
        print("=" * 80)

        # Test 1: File Validation
        self.test_file_validation()

        # Test 2: Hash Calculation
        self.test_hash_calculation()

        # Test 3: Metadata Extraction
        self.test_metadata_extraction()

        # Test 4: Database Operations
        self.test_database_operations()

        # Test 5: Duplicate Detection
        self.test_duplicate_detection()

        # Test 6: Batch Processing
        self.test_batch_processing()

        # Summary
        self.print_summary()

    def test_file_validation(self):
        """Test file validation logic"""
        print("\n" + "-" * 80)
        print("TEST 1: File Validation")
        print("-" * 80)

        # Test 1.1: Non-existent file
        print("\n  1.1 Non-existent file...")
        fake_path = Path("nonexistent.pdf")
        result = self.processor.process_upload(fake_path)

        if not result["success"] and "not found" in result["error"].lower():
            self._pass("Non-existent file correctly rejected")
        else:
            self._fail("Should reject non-existent file")

        # Test 1.2: Valid PDF
        print("\n  1.2 Valid PDF file...")
        test_pdf = self._get_test_pdf()

        if test_pdf and test_pdf.exists():
            result = self.processor.process_upload(test_pdf)
            if result["success"]:
                self._pass(f"Valid PDF accepted: {test_pdf.name}")
            else:
                self._fail(f"Should accept valid PDF: {result.get('error')}")
        else:
            self._skip("No test PDF available")

        # Test 1.3: Wrong file extension
        print("\n  1.3 Wrong file extension...")
        # Create temp non-PDF file
        temp_file = Path("test.txt")
        if not temp_file.exists():
            temp_file.write_text("test")

        result = self.processor.process_upload(temp_file)

        if not result["success"] and "invalid file type" in result["error"].lower():
            self._pass("Non-PDF file correctly rejected")
        else:
            self._fail("Should reject non-PDF files")

        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    def test_hash_calculation(self):
        """Test hash calculation"""
        print("\n" + "-" * 80)
        print("TEST 2: Hash Calculation")
        print("-" * 80)

        test_pdf = self._get_test_pdf()

        if not test_pdf or not test_pdf.exists():
            self._skip("No test PDF available")
            return

        print("\n  2.1 Calculating hash...")
        hash1 = self.processor._calculate_file_hash(test_pdf)

        if hash1 and len(hash1) == 64:  # SHA-256 produces 64 hex chars
            self._pass(f"Hash calculated: {hash1[:16]}...")
        else:
            self._fail("Invalid hash format")

        print("\n  2.2 Hash consistency...")
        hash2 = self.processor._calculate_file_hash(test_pdf)

        if hash1 == hash2:
            self._pass("Hash is consistent across multiple calculations")
        else:
            self._fail("Hash should be consistent")

    def test_metadata_extraction(self):
        """Test metadata extraction"""
        print("\n" + "-" * 80)
        print("TEST 3: Metadata Extraction")
        print("-" * 80)

        test_pdf = self._get_test_pdf()

        if not test_pdf or not test_pdf.exists():
            self._skip("No test PDF available")
            return

        print("\n  3.1 Extracting metadata...")
        metadata = self.processor._extract_basic_metadata(test_pdf)

        # Check required fields
        required_fields = ["filename", "file_size_bytes", "page_count", "title"]
        missing_fields = [f for f in required_fields if f not in metadata]

        if not missing_fields:
            self._pass("All required metadata fields present")
            print(f"      Filename: {metadata['filename']}")
            print(f"      Pages: {metadata['page_count']}")
            print(f"      Size: {metadata['file_size_bytes'] / (1024*1024):.1f} MB")
            print(f"      Title: {metadata['title'][:50]}...")
        else:
            self._fail(f"Missing fields: {missing_fields}")

        print("\n  3.2 Validating page count...")
        if metadata.get("page_count", 0) > 0:
            self._pass(f"Page count: {metadata['page_count']}")
        else:
            self._fail("Page count should be > 0")

    def test_database_operations(self):
        """Test database operations"""
        print("\n" + "-" * 80)
        print("TEST 4: Database Operations")
        print("-" * 80)

        test_pdf = self._get_test_pdf()

        if not test_pdf or not test_pdf.exists():
            self._skip("No test PDF available")
            return

        print("\n  4.1 Creating document record...")
        try:
            result = self.processor.process_upload(test_pdf)

            if result["success"] and result["document_id"]:
                self._pass(f"Document created: {result['document_id']}")

                # Verify in database
                print("\n  4.2 Verifying in database...")
                doc = self.database_adapter.select(
                    "krai_core.documents", columns=["*"], filters={"id": result["document_id"]}
                )

                if doc and len(doc) > 0:
                    self._pass("Document found in database")
                    print(f"      Status: {doc[0].get('status')}")
                    print(f"      Stage: {doc[0].get('processing_stage')}")
                else:
                    self._fail("Document not found in database")

                # Check processing queue
                print("\n  4.3 Checking processing queue...")
                queue = self.database_adapter.select(
                    "krai_system.processing_queue", columns=["*"], filters={"document_id": result["document_id"]}
                )

                if queue and len(queue) > 0:
                    self._pass("Document added to processing queue")
                    print(f"      Queue status: {queue[0].get('status')}")
                else:
                    self._fail("Document not in processing queue")

            else:
                self._fail(f"Upload failed: {result.get('error')}")

        except Exception as e:
            self._fail(f"Database error: {e!s}")

    def test_duplicate_detection(self):
        """Test duplicate detection"""
        print("\n" + "-" * 80)
        print("TEST 5: Duplicate Detection")
        print("-" * 80)

        test_pdf = self._get_test_pdf()

        if not test_pdf or not test_pdf.exists():
            self._skip("No test PDF available")
            return

        print("\n  5.1 First upload...")
        result1 = self.processor.process_upload(test_pdf)

        if result1["success"]:
            print(f"      Document ID: {result1['document_id']}")
            print(f"      Status: {result1['status']}")

            print("\n  5.2 Second upload (duplicate check)...")
            result2 = self.processor.process_upload(test_pdf)

            if result2["success"] and result2["status"] == "duplicate":
                self._pass("Duplicate correctly detected")
                print(f"      Same Document ID: {result2['document_id']}")
            else:
                self._fail(f"Should detect duplicate, got: {result2['status']}")

            print("\n  5.3 Force reprocess...")
            result3 = self.processor.process_upload(test_pdf, force_reprocess=True)

            if result3["success"] and result3["status"] == "reprocessing":
                self._pass("Force reprocess works")
            else:
                self._fail("Force reprocess should work")
        else:
            self._fail(f"First upload failed: {result1.get('error')}")

    def test_batch_processing(self):
        """Test batch processing"""
        print("\n" + "-" * 80)
        print("TEST 6: Batch Processing")
        print("-" * 80)

        # Find test directory with PDFs
        test_dir = Path("c:/Users/haast/Docker/KRAI-minimal")

        print("\n  6.1 Initializing batch processor...")
        batch_processor = BatchUploadProcessor(database_adapter=self.database_adapter, max_file_size_mb=500)

        print(f"\n  6.2 Scanning directory: {test_dir}")
        pdf_files = list(test_dir.glob("*.pdf"))

        if pdf_files:
            print(f"      Found {len(pdf_files)} PDF(s)")
            self._pass("Directory scan successful")

            # Process just first 2 PDFs for testing
            test_files = pdf_files[:2]
            print(f"\n  6.3 Processing {len(test_files)} file(s)...")

            # Manual batch test
            results = {"total": len(test_files), "successful": 0, "failed": 0}

            for pdf_file in test_files:
                try:
                    result = self.processor.process_upload(pdf_file)
                    if result["success"]:
                        results["successful"] += 1
                        print(f"      ✓ {pdf_file.name}")
                    else:
                        results["failed"] += 1
                        print(f"      ✗ {pdf_file.name}: {result['error']}")
                except Exception as e:
                    results["failed"] += 1
                    print(f"      ✗ {pdf_file.name}: {e!s}")

            if results["successful"] > 0:
                self._pass(f"Batch processing: {results['successful']}/{results['total']} successful")
            else:
                self._fail("No files processed successfully")
        else:
            self._skip("No PDF files found in test directory")

    def _get_test_pdf(self) -> Path:
        """Get test PDF file"""
        # Try known locations
        test_paths = [
            Path(
                "c:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
            ),
            Path("../../AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"),
        ]

        for path in test_paths:
            if path.exists():
                return path

        return None

    def _pass(self, message):
        """Record passed test"""
        self.test_results["passed"] += 1
        self.test_results["tests"].append(("PASS", message))
        print(f"    ✓ PASS: {message}")

    def _fail(self, message):
        """Record failed test"""
        self.test_results["failed"] += 1
        self.test_results["tests"].append(("FAIL", message))
        print(f"    ✗ FAIL: {message}")

    def _skip(self, message):
        """Record skipped test"""
        self.test_results["tests"].append(("SKIP", message))
        print(f"    ⊘ SKIP: {message}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)

        total = self.test_results["passed"] + self.test_results["failed"]
        passed = self.test_results["passed"]
        failed = self.test_results["failed"]

        print(f"\nTotal Tests: {total}")
        print(f"✓ Passed: {passed} ({100*passed/total if total > 0 else 0:.1f}%)")
        print(f"✗ Failed: {failed}")

        if failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print("\n⚠️  SOME TESTS FAILED")
            print("\nFailed Tests:")
            for status, message in self.test_results["tests"]:
                if status == "FAIL":
                    print(f"  ✗ {message}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    tester = UploadProcessorTester()
    tester.run_all_tests()
