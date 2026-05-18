"""
Check what's in the database for C9402 (PostgreSQL version)
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


async def search_error_codes(error_code: str):
    """Search for error codes in PostgreSQL database"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                ec.error_code,
                ec.error_description,
                ec.solution_text,
                m.name as manufacturer_name,
                d.filename as document_filename,
                c.page_number
            FROM krai_intelligence.error_codes ec
            LEFT JOIN krai_core.manufacturers m ON ec.manufacturer_id = m.id
            LEFT JOIN krai_core.documents d ON ec.document_id = d.id
            LEFT JOIN krai_intelligence.chunks c ON ec.chunk_id = c.id
            WHERE ec.error_code ILIKE $1
            ORDER BY ec.created_at DESC
        """,
            f"%{error_code}%",
        )

        return [dict(row) for row in results]


async def main():
    print("=" * 60)
    print("TESTING: search_error_codes('C9402')")
    print("=" * 60)

    error_codes = await search_error_codes("C9402")

    print(f"\nFound: {len(error_codes) > 0}")
    print(f"Count: {len(error_codes)}")

    if error_codes:
        print("\n" + "=" * 60)
        print("FIRST RESULT:")
        print("=" * 60)

        first = error_codes[0]

        print(f"\nError Code: {first.get('error_code')}")
        print(f"Description: {first.get('error_description')}")
        print(f"Manufacturer: {first.get('manufacturer_name')}")
        print(f"Document: {first.get('document_filename')}")
        print(f"Page: {first.get('page_number')}")

        print(f"\n{'='*60}")
        print("SOLUTION TEXT (FULL):")
        print("=" * 60)
        solution = first.get("solution_text", "")
        print(solution)
        print(f"\n{'='*60}")
        print(f"Solution length: {len(solution)} characters")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
