"""
Apply migration 019: add the missing stage column to krai_system.processing_queue.
"""

import asyncio
import os
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

MIGRATION_FILE = PROJECT_ROOT / "database" / "migrations_postgresql" / "019_add_processing_queue_stage_column.sql"


def read_statements(path: Path) -> list[str]:
    """Split a SQL file into standalone statements."""
    text = path.read_text(encoding="utf-8")
    statements: list[str] = []
    current: list[str] = []
    depth = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None
    i = 0

    def _match_dollar_tag(start: int) -> str | None:
        if start >= len(text) or text[start] != "$":
            return None
        end = start + 1
        while end < len(text) and text[end] != "$":
            ch = text[end]
            if not (ch.isalnum() or ch == "_"):
                return None
            end += 1
        if end < len(text) and text[end] == "$":
            return text[start : end + 1]
        return None

    while i < len(text):
        c = text[i]
        if in_line_comment:
            current.append(c)
            if c == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            current.append(c)
            if c == "*" and i + 1 < len(text) and text[i + 1] == "/":
                current.append("/")
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if text.startswith(dollar_tag, i):
                current.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            current.append(c)
            i += 1
            continue

        if in_single_quote:
            current.append(c)
            if c == "'" and i + 1 < len(text) and text[i + 1] == "'":
                current.append("'")
                i += 2
                continue
            if c == "'":
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            current.append(c)
            if c == '"' and i + 1 < len(text) and text[i + 1] == '"':
                current.append('"')
                i += 2
                continue
            if c == '"':
                in_double_quote = False
            i += 1
            continue

        if c == "-" and i + 1 < len(text) and text[i + 1] == "-":
            current.append("-")
            current.append("-")
            i += 2
            in_line_comment = True
            continue

        if c == "/" and i + 1 < len(text) and text[i + 1] == "*":
            current.append("/")
            current.append("*")
            i += 2
            in_block_comment = True
            continue

        if c == "'":
            current.append(c)
            in_single_quote = True
            i += 1
            continue

        if c == '"':
            current.append(c)
            in_double_quote = True
            i += 1
            continue

        tag = _match_dollar_tag(i)
        if tag is not None:
            current.append(tag)
            i += len(tag)
            dollar_tag = tag
            continue

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
        for i, stmt in enumerate(statements, start=1):
            try:
                await conn.execute(stmt)
                print(f"  [{i}/{len(statements)}] OK")
            except asyncpg.PostgresError as exc:
                msg = str(exc).lower()
                if ('column "stage"' in msg and "already exists" in msg) or "column stage already exists" in msg:
                    print(f"  [{i}/{len(statements)}] SKIP (stage column already present)")
                    continue
                raise
        print("Migration 019 applied successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
