"""
Test Image Processor

Tests image extraction, filtering, OCR, and Vision AI.
"""

import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.image_processor import ImageProcessor


def test_image_extraction():
    """Test 1: Extract images from PDF"""
    print("=" * 80)
    print("TEST 1: Image Extraction")
    print("=" * 80)

    # Find test PDF
    test_pdf = Path("../../AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf")

    if not test_pdf.exists():
        test_pdf = Path(
            "C:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
        )

    if not test_pdf.exists():
        print("\n⚠️  Test PDF not found")
        return False

    print(f"\n📄 Processing: {test_pdf.name}")

    # Initialize processor
    processor = ImageProcessor(
        min_image_size=10000,  # 100x100px minimum
        max_images_per_doc=50,  # Limit for testing
        enable_ocr=False,  # Disable for speed
        enable_vision=False,  # Disable for speed
    )

    # Process document
    try:
        result = processor.process_document(document_id=uuid4(), pdf_path=test_pdf)

        if result["success"]:
            print("\n✅ Image extraction successful!")
            print(f"   Extracted: {result['total_extracted']} images")
            print(f"   Filtered: {result['total_filtered']} relevant images")
            print(f"   Output: {result['output_dir']}")

            # Show sample images
            if result["images"]:
                print("\n   📸 Sample Images:")
                for i, img in enumerate(result["images"][:5], 1):
                    print(f"      {i}. Page {img['page_num']:4d}: {img['filename']}")
                    print(f"         Size: {img['width']}x{img['height']}px, Type: {img['type']}")

                if len(result["images"]) > 5:
                    print(f"      ... and {len(result['images']) - 5} more")

            return True
        print(f"\n❌ Extraction failed: {result.get('error')}")
        return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ocr():
    """Test 2: OCR on extracted images"""
    print("\n" + "=" * 80)
    print("TEST 2: OCR (Tesseract)")
    print("=" * 80)

    processor = ImageProcessor(enable_ocr=True, enable_vision=False)

    if not processor.ocr_available:
        print("\n⚠️  OCR not available")
        print("   Install: pip install pytesseract")
        print("   And install Tesseract: https://github.com/tesseract-ocr/tesseract")
        return False

    print("\n✅ OCR is available")
    return True


def test_vision_ai():
    """Test 3: Vision AI availability"""
    print("\n" + "=" * 80)
    print("TEST 3: Vision AI (LLaVA/Ollama)")
    print("=" * 80)

    processor = ImageProcessor(enable_ocr=False, enable_vision=True)

    if not processor.vision_available:
        print("\n⚠️  Vision AI not available")
        print("   Make sure:")
        print("   1. Ollama is running: ollama serve")
        print("   2. LLaVA model is installed: ollama pull llava")
        print("   3. Or use bakllava: ollama pull bakllava")
        return False

    print("\n✅ Vision AI is available")
    return True


def test_image_classification():
    """Test 4: Image classification"""
    print("\n" + "=" * 80)
    print("TEST 4: Image Classification")
    print("=" * 80)

    # Find a small test PDF or use temp images
    test_images = list(Path("temp_images").rglob("*.png"))[:5] if Path("temp_images").exists() else []

    if not test_images:
        print("\n⚠️  No test images found")
        print("   Run test 1 first to extract images")
        return False

    processor = ImageProcessor()

    # Classify sample images
    print(f"\n📸 Classifying {len(test_images)} images...")

    image_dicts = []
    for img_path in test_images:
        from PIL import Image

        img = Image.open(img_path)
        width, height = img.size

        image_dicts.append({"path": str(img_path), "filename": img_path.name, "width": width, "height": height})

    classified = processor._classify_images(image_dicts)

    print("\n   Results:")
    for img in classified:
        aspect = img["width"] / img["height"]
        print(f"   {img['filename']}: {img['type']} (aspect: {aspect:.2f})")

    print("\n✅ Classification complete")
    return True


def main():
    """Run all tests"""

    print("\n" + "🧪" * 40)
    print("\n   IMAGE PROCESSOR - TEST SUITE")
    print("\n" + "🧪" * 40)

    results = {}

    # Test 1: Extraction
    results["extraction"] = test_image_extraction()

    # Test 2: OCR
    results["ocr"] = test_ocr()

    # Test 3: Vision AI
    results["vision"] = test_vision_ai()

    # Test 4: Classification
    results["classification"] = test_image_classification()

    # Summary
    print("\n" + "=" * 80)
    print("  📊 TEST SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Results: {passed_count}/{total} passed")

    for test_name, test_passed in results.items():
        status = "✅" if test_passed else "⚠️"
        print(f"    {status} {test_name}")

    if passed_count == total:
        print("\n  🎉 ALL TESTS PASSED!")
        print("\n  Core extraction + OCR + Vision AI all working!")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        print(f"\n  {passed_count}/{total} tests passed")

        if results.get("extraction"):
            print("\n  ✅ Core extraction works!")
        if not results.get("ocr") or not results.get("vision"):
            print("  ⚠️  OCR and/or Vision AI are optional features (missing dependencies)")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
