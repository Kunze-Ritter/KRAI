"""
Check what's actually stored in the database for C9402 (PostgreSQL version)
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.db_pool import get_pool

# Load environment
load_all_env_files(PROJECT_ROOT)


async def main():
    print("=" * 60)
    print("CHECKING ERROR CODE C9402 IN DATABASE")
    print("=" * 60)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Query error codes
        results = await conn.fetch(
            """
            SELECT
                ec.error_code,
                ec.error_description,
                ec.solution_text,
                c.page_number,
                ec.document_id
            FROM krai_intelligence.error_codes ec
            LEFT JOIN krai_intelligence.chunks c ON ec.chunk_id = c.id
            WHERE ec.error_code ILIKE $1
            LIMIT 3
        """,
            "%C9402%",
        )

        if results:
            print(f"\nFound {len(results)} entries for C9402\n")

            for i, error in enumerate(results, 1):
                print(f"--- Entry {i} ---")
                print(f"Error Code: {error['error_code']}")
                print(f"Description: {error['error_description']}")
                print(f"Page: {error['page_number']}")
                print(f"Document ID: {error['document_id']}")
                print("\nSolution Text:")
                print(f"Length: {len(error['solution_text'])} characters")
                print(f"Content: {error['solution_text'][:500]}")
                print(f"\n{'='*60}\n")
        else:
            print("\n❌ No entries found for C9402")


if __name__ == "__main__":
    asyncio.run(main())
