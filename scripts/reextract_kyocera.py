"""Re-extract error codes for three Kyocera/Lexmark documents using a direct asyncpg connection."""

import asyncio
import sys
from uuid import uuid4

sys.path.insert(0, "/app")

DB_URL = "postgresql://krai_user:Krai_Secure_Pass123!@krai-postgres:5432/krai"

DOC_IDS = [
    "b7846015-4366-43af-95c9-a27e45c7cc90",  # 5058i_6058i_7058i.pdf
    "ecbe1892-d4df-4f2e-a270-71c6b45e874f",  # TASKalfa_4002i.pdf
    "0339103e-7063-4f61-a845-4437e183233f",  # CX92X_XC92x5_SM.pdf
]


class DirectDB:
    """Minimal DB adapter using asyncpg pool directly."""

    def __init__(self, pool):
        self.pool = pool

    async def get_document(self, doc_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, filename, manufacturer, manufacturer_id FROM krai_core.documents WHERE id = $1", doc_id
            )
            return dict(row) if row else None

    async def get_chunks_by_document(self, doc_id):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, text_chunk, page_start, metadata FROM krai_intelligence.chunks "
                "WHERE document_id = $1 ORDER BY page_start",
                doc_id,
            )
            return [dict(r) for r in rows]

    async def create_error_code(self, model):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO krai_intelligence.error_codes
                (id, document_id, error_code, error_description,
                 solution_customer_text, solution_agent_text, solution_technician_text,
                 page_number, confidence_score, extraction_method, severity_level,
                 chunk_id, parent_code, is_category, manufacturer_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                ON CONFLICT DO NOTHING
                """,
                str(uuid4()),
                str(model.document_id or ""),
                model.error_code or "",
                model.error_description or "",
                model.solution_customer_text,
                model.solution_agent_text,
                model.solution_technician_text,
                model.page_number,
                model.confidence_score,
                model.extraction_method or "",
                model.severity_level or "",
                str(model.chunk_id) if model.chunk_id else None,
                model.parent_code,
                model.is_category or False,
                str(model.manufacturer_id) if model.manufacturer_id else None,
            )
        return True

    async def update_document(self, doc_id, data):
        pass


async def main():
    import asyncpg

    from backend.core.base_processor import ProcessingContext
    from backend.processors.metadata_processor_ai import MetadataProcessorAI

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    db = DirectDB(pool)
    proc = MetadataProcessorAI(database_service=db)

    for doc_id in DOC_IDS:
        print(f"Extracting {doc_id}...", flush=True)
        # Debug: check doc
        doc = await db.get_document(doc_id)
        print(f'  doc manufacturer: {doc.get("manufacturer") if doc else "NOT FOUND"}', flush=True)
        chunks = await db.get_chunks_by_document(doc_id)
        print(f"  chunks: {len(chunks)}", flush=True)
        ctx = ProcessingContext(file_path="", document_type="pdf", document_id=doc_id)
        result = await proc.process(ctx)
        print(f"  done: success={result.success} data={result.data}", flush=True)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
