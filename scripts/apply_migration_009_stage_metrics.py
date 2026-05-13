"""
Apply migration 009: create krai_system.stage_metrics table.
Uses POSTGRES_URL from environment (.env / env.database).
Run from project root: python scripts/apply_migration_009_stage_metrics.py
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load env (same as pipeline/scripts)
from backend.processors.env_loader import load_all_env_files

load_all_env_files(PROJECT_ROOT)

try:
    import asyncpg
except ImportError:
    print("asyncpg required: pip install asyncpg")
    sys.exit(1)


MIGRATION_FILE = PROJECT_ROOT / "database" / "migrations_postgresql" / "009_add_stage_metrics_table.sql"


def read_statements(path: Path) -> list[str]:
    """Split SQL file into single statements (semicolon outside parentheses)."""
    text = path.read_text(encoding="utf-8")
    statements = []
    current = []
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
            current.append(c)
        elif c == ")":
            depth -= 1
            current.append(c)
        elif c == ";" and depth == 0:
            stmt = "".join(current).strip()
            if stmt and not all(line.strip().startswith("--") or not line.strip() for line in stmt.splitlines()):
                statements.append(stmt + ";")
            current = []
        else:
            current.append(c)
        i += 1
    if current:
        stmt = "".join(current).strip()
        if stmt:
            statements.append(stmt + ";")
    return statements


async def main():
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_CONNECTION_URL") or os.getenv("DATABASE_URL")
    if not postgres_url:
        print("POSTGRES_URL (or DATABASE_CONNECTION_URL / DATABASE_URL) not set.")
        sys.exit(1)

    if not MIGRATION_FILE.exists():
        print(f"Migration file not found: {MIGRATION_FILE}")
        sys.exit(1)

    statements = read_statements(MIGRATION_FILE)
    print(f"Applying {len(statements)} statement(s) from {MIGRATION_FILE.name} ...")

    conn = await asyncpg.connect(postgres_url)
    try:
        for i, stmt in enumerate(statements, 1):
            # First line of statement for logging
            first_line = stmt.split("\n")[0][:60].strip()
            await conn.execute(stmt)
            print(f"  [{i}/{len(statements)}] OK: {first_line}")
        print("Migration 009 (stage_metrics) applied successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
