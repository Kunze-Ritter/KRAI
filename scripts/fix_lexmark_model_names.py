#!/usr/bin/env python3
"""One-time fix: strip 'Lexmark ' prefix from model_name in krai_core.products."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files
from backend.services.database_factory import create_database_adapter

load_all_env_files(PROJECT_ROOT)

LEXMARK_ID = "93974db7-e28e-4cd8-9ac9-5f2e1bdf7403"


async def main():
    db = create_database_adapter()
    await db.connect()
    pool = db._ensure_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE krai_core.products
            SET model_name = TRIM(LEADING 'Lexmark ' FROM model_name),
                updated_at = NOW()
            WHERE manufacturer_id = $1::uuid
              AND model_name LIKE 'Lexmark %'
            """,
            LEXMARK_ID,
        )
        print(f"Updated: {result}")

        rows = await conn.fetch(
            f"SELECT model_number, model_name FROM krai_core.products "
            f"WHERE manufacturer_id = '{LEXMARK_ID}' ORDER BY model_number LIMIT 5"
        )
        print("\nNach dem Fix (erste 5):")
        for r in rows:
            print(f"  {r['model_number']}  →  {r['model_name']}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
