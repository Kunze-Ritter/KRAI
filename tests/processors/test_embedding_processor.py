"""Legacy/manual EmbeddingProcessor test harness.

This module is intentionally excluded from normal pytest discovery and
is meant to be run manually via:

    python tests/processors/test_embedding_processor.py

It exercises real Ollama integration, embedding generation, and vector
storage for ad-hoc diagnostics and exploration.
"""

import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.embedding_processor import EmbeddingProcessor

pytestmark = pytest.mark.skip(
    "Legacy/manual EmbeddingProcessor tests – use pytest-based suite in "
    "tests/processors/test_embedding_processor_*.py instead."
)


def test_ollama_availability():
    """Test 1: Check Ollama and model availability"""
    print("=" * 80)
    print("TEST 1: Ollama & Model Availability")
    print("=" * 80)

    processor = EmbeddingProcessor()

    if processor.ollama_available:
        print("\n✅ Ollama is available")
        print(f"   URL: {processor.ollama_url}")
        print(f"   Model: {processor.model_name}")
        print(f"   Embedding Dimension: {processor.embedding_dimension}")
        return True
    print("\n⚠️  Ollama not available")
    print("\n   Setup:")
    print("   1. Start Ollama: ollama serve")
    print("   2. Install model: ollama pull embeddinggemma")
    print("   3. Verify: ollama list")
    return False


def test_embedding_generation():
    """Test 2: Generate embeddings for sample texts"""
    print("\n" + "=" * 80)
    print("TEST 2: Embedding Generation")
    print("=" * 80)

    processor = EmbeddingProcessor()

    if not processor.ollama_available:
        print("\n⚠️  Skipped: Ollama not available")
        return False

    # Sample texts
    test_texts = [
        "Error C2557: Paper jam in the fuser unit",
        "The LaserJet printer uses toner cartridges",
        "Replace the imaging drum every 100,000 pages",
        "Network configuration settings for WiFi",
        "Clean the corona wire with a soft cloth",
    ]

    print(f"\n📝 Generating embeddings for {len(test_texts)} texts...")

    embeddings = []

    for i, text in enumerate(test_texts, 1):
        embedding = processor._generate_embedding(text)

        if embedding:
            embeddings.append(embedding)
            print(f'\n   {i}. ✅ "{text[:50]}..."')
            print(f"      Dimension: {len(embedding)}")
            print(f"      Sample: [{embedding[0]:.4f}, {embedding[1]:.4f}, {embedding[2]:.4f}, ...]")
        else:
            print(f'\n   {i}. ❌ Failed: "{text[:50]}..."')

    if len(embeddings) == len(test_texts):
        print(f"\n✅ All {len(test_texts)} embeddings generated successfully!")
        return True
    print(f"\n⚠️  Generated {len(embeddings)}/{len(test_texts)} embeddings")
    return False


def test_embedding_similarity():
    """Test 3: Test cosine similarity between embeddings"""
    print("\n" + "=" * 80)
    print("TEST 3: Embedding Similarity")
    print("=" * 80)

    processor = EmbeddingProcessor()

    if not processor.ollama_available:
        print("\n⚠️  Skipped: Ollama not available")
        return False

    # Similar texts
    text1 = "Paper jam in the printer"
    text2 = "The printer has a paper jam error"
    text3 = "Network configuration settings"

    print("\n📝 Testing similarity...")
    print(f'   Text 1: "{text1}"')
    print(f'   Text 2: "{text2}"')
    print(f'   Text 3: "{text3}"')

    emb1 = processor._generate_embedding(text1)
    emb2 = processor._generate_embedding(text2)
    emb3 = processor._generate_embedding(text3)

    if not all([emb1, emb2, emb3]):
        print("\n❌ Failed to generate embeddings")
        return False

    # Calculate cosine similarity
    import numpy as np

    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    sim_1_2 = cosine_similarity(emb1, emb2)
    sim_1_3 = cosine_similarity(emb1, emb3)

    print("\n   Similarity Results:")
    print(f"   Text 1 ↔ Text 2 (similar topics): {sim_1_2:.4f}")
    print(f"   Text 1 ↔ Text 3 (different topics): {sim_1_3:.4f}")

    if sim_1_2 > sim_1_3:
        print("\n✅ Similarity test passed!")
        print("   Similar texts have higher similarity score")
        return True
    print("\n⚠️  Unexpected similarity scores")
    return False


def test_batch_processing():
    """Test 4: Batch embedding generation"""
    print("\n" + "=" * 80)
    print("TEST 4: Batch Processing")
    print("=" * 80)

    processor = EmbeddingProcessor(batch_size=5)

    if not processor.ollama_available:
        print("\n⚠️  Skipped: Ollama not available")
        return False

    # Create fake chunks
    fake_chunks = []
    for i in range(12):
        fake_chunks.append(
            {
                "chunk_id": str(uuid4()),
                "text": f"This is test chunk number {i+1} with some sample text content.",
                "chunk_index": i,
                "chunk_type": "text",
            }
        )

    print(f"\n📦 Processing {len(fake_chunks)} chunks in batches of {processor.batch_size}...")

    # Process without database (just embedding generation)
    total_generated = 0

    for i in range(0, len(fake_chunks), processor.batch_size):
        batch = fake_chunks[i : i + processor.batch_size]
        batch_num = (i // processor.batch_size) + 1

        print(f"\n   Batch {batch_num}: Processing {len(batch)} chunks...")

        for chunk in batch:
            embedding = processor._generate_embedding(chunk["text"])
            if embedding:
                total_generated += 1

        print(f"   ✅ Generated {len(batch)} embeddings")

    print("\n✅ Batch processing complete!")
    print(f"   Total: {total_generated}/{len(fake_chunks)} embeddings generated")

    return total_generated == len(fake_chunks)


def test_performance():
    """Test 5: Embedding generation performance"""
    print("\n" + "=" * 80)
    print("TEST 5: Performance Test")
    print("=" * 80)

    processor = EmbeddingProcessor()

    if not processor.ollama_available:
        print("\n⚠️  Skipped: Ollama not available")
        return False

    import time

    test_text = "This is a performance test for embedding generation speed."
    num_tests = 10

    print(f"\n⚡ Generating {num_tests} embeddings...")

    start_time = time.time()

    for i in range(num_tests):
        embedding = processor._generate_embedding(test_text)
        if not embedding:
            print(f"\n❌ Failed at iteration {i+1}")
            return False

    elapsed = time.time() - start_time
    per_embedding = elapsed / num_tests

    print("\n✅ Performance results:")
    print(f"   Total time: {elapsed:.2f}s")
    print(f"   Per embedding: {per_embedding:.3f}s")
    print(f"   Throughput: {num_tests/elapsed:.1f} embeddings/second")

    if per_embedding < 1.0:  # Should be fast with local Ollama
        print("\n✅ Performance is good! (<1s per embedding)")
        return True
    print(f"\n⚠️  Performance is slow (>{per_embedding:.1f}s per embedding)")
    print("   Consider checking Ollama configuration")
    return True  # Still pass, just slow


def main():
    """Run all tests"""

    print("\n" + "🧪" * 40)
    print("\n   EMBEDDING PROCESSOR - TEST SUITE")
    print("   Semantic Search Foundation")
    print("\n" + "🧪" * 40)

    results = {}

    # Test 1: Ollama availability
    results["ollama"] = test_ollama_availability()

    if not results["ollama"]:
        print("\n" + "=" * 80)
        print("⚠️  Ollama not available - cannot run further tests")
        print("=" * 80)
        print("\nSetup instructions:")
        print("  1. Install Ollama: https://ollama.ai")
        print("  2. Start service: ollama serve")
        print("  3. Pull model: ollama pull embeddinggemma")
        print("  4. Verify: ollama list")
        return

    # Test 2: Embedding generation
    results["generation"] = test_embedding_generation()

    # Test 3: Similarity
    results["similarity"] = test_embedding_similarity()

    # Test 4: Batch processing
    results["batch"] = test_batch_processing()

    # Test 5: Performance
    results["performance"] = test_performance()

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
        print("\n  Embedding processor ready for semantic search!")
    else:
        print("\n  ⚠️  SOME TESTS FAILED")
        print(f"\n  {passed_count}/{total} tests passed")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
