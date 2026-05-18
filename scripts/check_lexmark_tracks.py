"""Check main KRAI pipeline processing status."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files

load_all_env_files(PROJECT_ROOT)

from backend.services.database_factory import create_database_adapter


async def main():
    db = create_database_adapter()
    await db.connect()
    pool = db.pg_pool

    async with pool.acquire() as conn:
        # Documents by processing_status
        doc_stats = await conn.fetch(
            """
            SELECT processing_status, COUNT(*) as cnt
            FROM krai_core.documents
            GROUP BY processing_status
            ORDER BY cnt DESC
        """
        )

        # Documents by document_type
        doc_types = await conn.fetch(
            """
            SELECT COALESCE(document_type, 'NULL') as document_type, COUNT(*) as cnt
            FROM krai_core.documents
            GROUP BY document_type
            ORDER BY cnt DESC
            LIMIT 10
        """
        )

        # Stage tracking (last 10 activities)
        stages = (
            await conn.fetch(
                """
            SELECT stage_name, status, COUNT(*) as cnt
            FROM krai_system.stage_tracking
            GROUP BY stage_name, status
            ORDER BY stage_name, status
        """
            )
            if await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='krai_system' AND table_name='stage_tracking')"
            )
            else []
        )

        # Chunks overall
        chunk_total = await conn.fetchval("SELECT COUNT(*) FROM krai_intelligence.chunks")
        chunk_embedded = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_intelligence.chunks WHERE embedding IS NOT NULL"
        )
        chunk_pending = await conn.fetchval(
            "SELECT COUNT(*) FROM krai_intelligence.chunks WHERE processing_status = 'pending'"
        )

        # Recent errors
        errors = await conn.fetch(
            """
            SELECT LEFT(processing_error, 80) as err, COUNT(*) as cnt
            FROM krai_core.documents
            WHERE processing_error IS NOT NULL
            GROUP BY LEFT(processing_error, 80)
            ORDER BY cnt DESC
            LIMIT 5
        """
        )

    print("=" * 60)
    print("  KRAI Pipeline Status")
    print("=" * 60)

    print("\n  [Dokumente nach Status]")
    for r in doc_stats:
        print(f"    {r['processing_status']:<25} {r['cnt']:>6}")

    print("\n  [Dokumente nach Typ (Top 10)]")
    for r in doc_types:
        print(f"    {r['document_type']:<35} {r['cnt']:>6}")

    print("\n  [Chunks gesamt]")
    print(f"    {'Gesamt':<25} {chunk_total:>6}")
    print(f"    {'Mit Embedding':<25} {chunk_embedded:>6}")
    print(f"    {'Pending (ohne Embedding)':<25} {chunk_pending:>6}")

    if stages:
        print("\n  [Stage Tracking]")
        for r in stages:
            print(f"    {r['stage_name']:<25} {r['status']:<15} {r['cnt']:>5}")

    if errors:
        print("\n  [Häufige Fehler]")
        for r in errors:
            print(f"    ({r['cnt']}x) {r['err']}")

    print("=" * 60)
    await db.disconnect()


asyncio.run(main())
