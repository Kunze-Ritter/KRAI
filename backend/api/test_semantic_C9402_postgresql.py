"""
Check if semantic search has better data for C9402 (PostgreSQL version)
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.db_pool import get_pool
from backend.services.embedding_service import EmbeddingService

# Load environment
load_all_env_files(PROJECT_ROOT)


async def semantic_search(query: str, limit: int = 5):
    """Perform semantic search in PostgreSQL database"""
    # Generate embedding for query
    embedding_service = EmbeddingService()
    query_embedding = await embedding_service.generate_embedding(query)

    pool = await get_pool()
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                c.id,
                c.content,
                c.page_number,
                d.filename as document_filename,
                m.name as manufacturer_name,
                1 - (c.embedding <=> $1::vector) as similarity_score
            FROM krai_intelligence.chunks c
            LEFT JOIN krai_core.documents d ON c.document_id = d.id
            LEFT JOIN krai_core.manufacturers m ON d.manufacturer_id = m.id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
        """,
            query_embedding,
            limit,
        )

        return [dict(row) for row in results]


async def main():
    print("=" * 60)
    print("TESTING: semantic_search('C9402 Konica Minolta')")
    print("=" * 60)

    chunks = await semantic_search("C9402 Konica Minolta error solution", limit=5)

    print(f"\nFound: {len(chunks) > 0}")
    print(f"Count: {len(chunks)}")

    if chunks:
        print("\n" + "=" * 60)
        print("TOP 3 RESULTS:")
        print("=" * 60)

        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n--- Result {i} ---")
            print(f"Document: {chunk.get('document_filename', 'Unknown')}")
            print(f"Manufacturer: {chunk.get('manufacturer_name', 'Unknown')}")
            print(f"Page: {chunk.get('page_number', 'Unknown')}")
            print(f"Similarity: {chunk.get('similarity_score', 'Unknown'):.4f}")
            print(f"\nContent ({len(chunk.get('content', ''))} chars):")
            print("-" * 60)
            content = chunk.get("content", "")
            print(content[:800])  # First 800 chars
            print("\n...")
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
