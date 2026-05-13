"""
Quick test: What does search_parts return for 41X5345? (PostgreSQL version)
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.db_pool import get_pool

# Load environment
load_all_env_files(PROJECT_ROOT)


async def search_parts(part_number: str):
    """Search for parts in PostgreSQL database"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                p.part_number,
                p.part_name,
                p.description,
                p.compatible_models,
                m.name as manufacturer_name,
                d.filename as document_filename
            FROM krai_parts.parts_catalog p
            LEFT JOIN krai_core.manufacturers m ON p.manufacturer_id = m.id
            LEFT JOIN krai_core.documents d ON p.document_id = d.id
            WHERE p.part_number ILIKE $1
            ORDER BY p.created_at DESC
        """,
            f"%{part_number}%",
        )

        return [dict(row) for row in results]


async def main():
    print("=" * 60)
    print("TESTING: search_parts('41X5345')")
    print("=" * 60)

    parts = await search_parts("41X5345")

    result_data = {"found": len(parts) > 0, "count": len(parts), "parts": parts}

    print("\nRaw JSON result:")
    print(json.dumps(result_data, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("Parsed result:")
    print("=" * 60)
    print(json.dumps(result_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
