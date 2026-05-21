#!/usr/bin/env python3
"""Idempotent runner for the PostgreSQL SQL migrations in database/migrations_postgresql/.

Tracks applied migrations in krai_system.migrations (the backend's migration table;
distinct from Laravel's public.migrations). Applies pending migrations in numeric
filename order, each in its own transaction, and records them.

Usage:
    python scripts/run_migrations.py --status      # show applied vs pending
    python scripts/run_migrations.py               # apply all pending migrations
    python scripts/run_migrations.py --baseline    # mark all on-disk migrations as
                                                    # applied WITHOUT executing them
                                                    # (use when the DB already has the
                                                    #  schema but the table is behind)
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files

load_all_env_files(PROJECT_ROOT)

try:
    import asyncpg
except ImportError:
    print("asyncpg required: pip install asyncpg")
    sys.exit(1)

MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations_postgresql"
_NUM_PREFIX = re.compile(r"^(\d+)_")


def discover_migrations() -> list[Path]:
    """All *.sql migrations sorted by their numeric prefix, then name."""
    files = list(MIGRATIONS_DIR.glob("*.sql"))

    def key(p: Path) -> tuple[int, str]:
        m = _NUM_PREFIX.match(p.name)
        return (int(m.group(1)) if m else 9999, p.name)

    return sorted(files, key=key)


def first_comment(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            return stripped.lstrip("- ").strip()[:250]
        if stripped:
            break
    return ""


async def applied_set(conn: asyncpg.Connection) -> set[str]:
    # The tracking table lives in krai_system, but on a brand-new database that schema
    # doesn't exist until a migration creates it — bootstrap it so tracking works first.
    await conn.execute("CREATE SCHEMA IF NOT EXISTS krai_system")
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS krai_system.migrations (
            migration_name VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW(),
            description TEXT
        )
        """
    )
    rows = await conn.fetch("SELECT migration_name FROM krai_system.migrations")
    return {r["migration_name"] for r in rows}


async def record(conn: asyncpg.Connection, name: str, description: str) -> None:
    await conn.execute(
        """
        INSERT INTO krai_system.migrations (migration_name, applied_at, description)
        VALUES ($1, NOW(), $2)
        ON CONFLICT (migration_name) DO NOTHING
        """,
        name,
        description,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="PostgreSQL SQL migration runner")
    parser.add_argument("--status", action="store_true", help="Show applied vs pending and exit")
    parser.add_argument(
        "--baseline", action="store_true", help="Record all on-disk migrations as applied without executing"
    )
    args = parser.parse_args()

    url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_CONNECTION_URL") or os.getenv("DATABASE_URL")
    if not url:
        print("POSTGRES_URL / DATABASE_CONNECTION_URL not set.")
        sys.exit(1)

    migrations = discover_migrations()
    conn = await asyncpg.connect(url)
    try:
        applied = await applied_set(conn)
        pending = [p for p in migrations if p.stem not in applied]

        if args.status:
            print(f"Applied: {len(applied)} | On disk: {len(migrations)} | Pending: {len(pending)}")
            for p in pending:
                print(f"  PENDING  {p.name}")
            return

        if args.baseline:
            count = 0
            for p in pending:
                await record(conn, p.stem, first_comment(p))
                count += 1
            print(f"Baselined {count} migration(s) as applied (no SQL executed).")
            return

        if not pending:
            print("No pending migrations.")
            return

        for p in pending:
            print(f"Applying {p.name} ...")
            # Execute the whole file in one call: asyncpg's simple-query protocol runs
            # multiple statements and lets Postgres parse dollar-quoted bodies ($$...$$)
            # and comments itself — far more robust than splitting on ';' in Python.
            async with conn.transaction():
                # utf-8-sig strips a leading BOM that some migration files carry
                # (a raw BOM makes Postgres raise a syntax error at the first token).
                await conn.execute(p.read_text(encoding="utf-8-sig"))
                await record(conn, p.stem, first_comment(p))
            print(f"  OK: {p.name}")
        print(f"Applied {len(pending)} migration(s).")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
