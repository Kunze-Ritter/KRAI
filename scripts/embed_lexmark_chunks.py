"""
Generate embeddings for Lexmark subtitle chunks (processing_status='pending').

Uses Ollama nomic-embed-text directly via HTTP.
Updates krai_intelligence.chunks.embedding in batches.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import aiohttp
import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files

load_all_env_files(PROJECT_ROOT)

from backend.services.database_factory import create_database_adapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("embed_lexmark")

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text:latest"
BATCH_SIZE = 32
EXPECTED_DIM = 768


async def resolve_manufacturer_id(pool: asyncpg.Pool, name: str) -> str | None:
    """Look up manufacturer UUID by name (case-insensitive)."""
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT id FROM krai_core.manufacturers WHERE LOWER(name) = LOWER($1) LIMIT 1",
            name,
        )
    return str(row) if row else None


async def fetch_pending_chunks(pool: asyncpg.Pool, manufacturer_id: str, limit: int | None) -> list[dict]:
    """Return subtitle chunks with processing_status='pending' for the given manufacturer."""
    limit_sql = f"LIMIT {limit}" if limit else ""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT c.id, c.text_chunk
            FROM krai_intelligence.chunks c
            WHERE c.processing_status = 'pending'
              AND c.embedding IS NULL
              AND c.metadata->>'chunk_type' = 'video_subtitle'
              AND c.metadata->>'source' = 'lexmark_support'
            ORDER BY c.created_at ASC
            {limit_sql}
            """
        )
    return [{"id": str(r["id"]), "text": r["text_chunk"]} for r in rows]


async def generate_embedding(session: aiohttp.ClientSession, text: str) -> list[float] | None:
    """Call Ollama embeddings API for a single text."""
    try:
        async with session.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("embedding")
    except Exception as exc:
        logger.warning("Embedding error: %s", exc)
    return None


async def update_chunk(pool: asyncpg.Pool, chunk_id: str, embedding: list[float], dry_run: bool) -> bool:
    """Write embedding to DB and mark chunk as completed."""
    if dry_run:
        return True
    vector_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE krai_intelligence.chunks
            SET embedding         = $1::vector,
                processing_status = 'completed',
                updated_at        = NOW()
            WHERE id = $2::uuid
            """,
            vector_str,
            chunk_id,
        )
    return True


async def main(limit: int | None, batch_size: int, dry_run: bool) -> None:
    logger.info("=" * 60)
    logger.info("Lexmark Subtitle Embedding Generator")
    if dry_run:
        logger.info("DRY RUN – keine DB-Änderungen")
    logger.info("=" * 60)

    db = create_database_adapter()
    await db.connect()
    pool = db.pg_pool

    try:
        manufacturer_id = await resolve_manufacturer_id(pool, "Lexmark")
        if not manufacturer_id:
            logger.error("Manufacturer 'Lexmark' not found in database.")
            return

        chunks = await fetch_pending_chunks(pool, manufacturer_id, limit)
        logger.info("Chunks zu embedden: %d", len(chunks))

        if not chunks:
            logger.info("Nichts zu tun.")
            return

        stats = {"ok": 0, "errors": 0}
        dimension_verified = False
        connector = aiohttp.TCPConnector(limit=8)

        async with aiohttp.ClientSession(connector=connector) as session:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]

                tasks = [generate_embedding(session, c["text"]) for c in batch]
                embeddings = await asyncio.gather(*tasks)

                for chunk, emb in zip(batch, embeddings):
                    if emb is None:
                        stats["errors"] += 1
                        logger.warning("Kein Embedding für Chunk %s", chunk["id"][:8])
                        continue

                    # Fail-fast dimension check on first successful embedding
                    if not dimension_verified:
                        if len(emb) != EXPECTED_DIM:
                            logger.error(
                                "Falsches Embedding-Modell! Erwartet %d Dimensionen, "
                                "erhalten %d. Prüfe EMBED_MODEL in embed_lexmark_chunks.py.",
                                EXPECTED_DIM,
                                len(emb),
                            )
                            return
                        dimension_verified = True

                    await update_chunk(pool, chunk["id"], emb, dry_run)
                    stats["ok"] += 1

                done = min(i + batch_size, len(chunks))
                logger.info(
                    "Fortschritt: %d / %d  (ok=%d, fehler=%d)",
                    done,
                    len(chunks),
                    stats["ok"],
                    stats["errors"],
                )
                await asyncio.sleep(0.1)

        logger.info("=" * 60)
        logger.info("Ergebnis")
        logger.info("  Embeddings erstellt : %d", stats["ok"])
        logger.info("  Fehler              : %d", stats["errors"])
        logger.info("=" * 60)

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate embeddings for Lexmark subtitle chunks")
    parser.add_argument("--limit", type=int, default=None, help="Max chunks to process")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="No DB changes")
    args = parser.parse_args()

    asyncio.run(main(args.limit, args.batch_size, args.dry_run))
