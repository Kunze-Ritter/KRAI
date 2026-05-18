"""
Verify PostgreSQL connection and stage-tracking RPC functions.
Run from project root with env loaded (e.g. .env with POSTGRES_URL).
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root and backend on path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from backend.services.postgresql_adapter import PostgreSQLAdapter


async def test_connection():
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or os.getenv("DATABASE_CONNECTION_URL")
    if not postgres_url:
        print("❌ POSTGRES_URL (or DATABASE_URL/DATABASE_CONNECTION_URL) not set")
        return
    adapter = PostgreSQLAdapter(postgres_url)
    await adapter.connect()

    # Test connection
    result = await adapter.test_connection()
    print(f"✅ Connection test: {result}")

    # Test RPC functions
    doc_id = "123e4567-e89b-12d3-a456-426614174000"

    # Start stage
    await adapter.start_stage(doc_id, "upload")
    print("✅ start_stage executed")

    # Get status
    status = await adapter.get_stage_status(doc_id, "upload")
    print(f"✅ get_stage_status: {status}")

    # Complete stage
    await adapter.complete_stage(doc_id, "upload", {"test": "data"})
    print("✅ complete_stage executed")

    # Fail stage (test)
    await adapter.fail_stage(doc_id, "text_extraction", "Test error")
    print("✅ fail_stage executed")

    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(test_connection())
