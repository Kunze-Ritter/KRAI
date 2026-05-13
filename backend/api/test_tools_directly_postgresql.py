"""
Direct test of KRAI Tools without Agent (PostgreSQL version)
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


async def search_parts(part_query: str):
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
            WHERE p.part_number ILIKE $1 OR p.part_name ILIKE $1
            ORDER BY p.created_at DESC
        """,
            f"%{part_query}%",
        )

        return [dict(row) for row in results]


async def main():
    print("=" * 60)
    print("TESTING KRAI TOOLS DIRECTLY")
    print("=" * 60)

    # Test 1: Search for C9402
    print("\n1. Testing search_error_codes('C9402')...")
    error_codes = await search_error_codes("C9402")
    data = {"found": len(error_codes) > 0, "count": len(error_codes), "error_codes": error_codes}
    print(f"   Found: {data.get('found')}")
    print(f"   Raw data keys: {list(data.keys())}")
    if data.get("found"):
        print(f"   Count: {data.get('count')}")
        print(
            f"   First result: {data['error_codes'][0]['error_code']} - {data['error_codes'][0].get('error_description', '')[:60]}..."
        )

    # Test 2: Search for 10.00.33
    print("\n2. Testing search_error_codes('10.00.33')...")
    error_codes = await search_error_codes("10.00.33")
    data = {"found": len(error_codes) > 0, "count": len(error_codes), "error_codes": error_codes}
    print(f"   Found: {data.get('found')}")
    if data.get("found"):
        print(f"   Count: {data.get('count')}")
        print(
            f"   First result: {data['error_codes'][0]['error_code']} - {data['error_codes'][0].get('error_description', '')[:60]}..."
        )
        print(f"   Manufacturer: {data['error_codes'][0].get('manufacturer_name', 'Unknown')}")
        print(f"   Document: {data['error_codes'][0].get('document_filename', 'Unknown')}")

    # Test 3: Search for HP 10.00.33
    print("\n3. Testing search_error_codes('HP Fehler 10.00.33')...")
    error_codes = await search_error_codes("HP Fehler 10.00.33")
    data = {"found": len(error_codes) > 0, "count": len(error_codes), "error_codes": error_codes}
    print(f"   Found: {data.get('found')}")
    if data.get("found"):
        print(f"   Count: {data.get('count')}")
        for i, res in enumerate(data["error_codes"][:3]):
            print(f"   Result {i+1}: {res['error_code']} - Manufacturer: {res.get('manufacturer_name', 'Unknown')}")

    # Test 4: Search parts
    print("\n4. Testing search_parts('Fuser')...")
    parts = await search_parts("Fuser")
    data = {"found": len(parts) > 0, "count": len(parts), "parts": parts}
    print(f"   Found: {data.get('found')}")
    if data.get("found"):
        print(f"   Count: {data.get('count')}")

    # Test 5: Search parts for Lexmark
    print("\n5. Testing search_parts('41X5345')...")
    parts = await search_parts("41X5345")
    data = {"found": len(parts) > 0, "count": len(parts), "parts": parts}
    print(f"   Found: {data.get('found')}")
    if data.get("found"):
        print(f"   Count: {data.get('count')}")
        print(f"   First result: {data['parts'][0]['part_number']}")
        print(f"   Manufacturer: {data['parts'][0].get('manufacturer_name', 'Unknown')}")
        print(f"   Full data: {json.dumps(data['parts'][0], indent=2, ensure_ascii=False)}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
