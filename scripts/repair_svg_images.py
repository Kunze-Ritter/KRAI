#!/usr/bin/env python3
"""
repair_svg_images.py

Re-runs the SVG processing stage for documents that completed svg_processor
but have no vector_graphic entries in krai_content.images.

This is a one-time repair script for documents affected by the missing
'payload' column bug (fixed in migration 020).

Usage:
    python scripts/repair_svg_images.py [--dry-run] [--doc-id <uuid>]

Steps performed for each affected document:
  1. Run SVGProcessor against the original PDF  →  creates processing_queue entries
  2. Drain those queue entries  →  inserts rows in krai_content.images
  3. Delete the svg_processor stage_completion_marker  →  marks stage for refresh
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.processors.env_loader import load_all_env_files

load_all_env_files(PROJECT_ROOT)

from backend.core.base_processor import ProcessingContext
from backend.processors.logger import get_logger
from backend.services.database_factory import create_database_adapter

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def get_affected_documents(db) -> list[dict]:
    """Return documents that have svg_processor marker but no vector_graphic images."""
    rows = await db.fetch_all(
        """
        SELECT d.id, d.filename, d.storage_path, d.storage_url
        FROM krai_core.documents d
        JOIN krai_system.stage_completion_markers scm
            ON scm.document_id = d.id AND scm.stage_name = 'svg_processor'
        WHERE NOT EXISTS (
            SELECT 1 FROM krai_content.images i
            WHERE i.document_id = d.id AND i.image_type = 'vector_graphic'
        )
        ORDER BY d.filename
    """
    )
    return [dict(r) for r in rows]


def resolve_pdf_path(storage_path: str | None, filename: str) -> str | None:
    """
    Try to resolve the PDF file path from the stored storage_path.
    Falls back to common locations.
    """
    candidates = []
    if storage_path:
        # Normalize Windows / Linux paths
        win_path = storage_path.replace("/firmwares/", r"C:\Firmwares\\").replace("/", "\\")
        candidates.append(storage_path)
        candidates.append(win_path)

    # Common fallback directories
    for base in [r"C:\Firmwares", r"C:\Firmwares\HP", "input_pdfs", "processed_pdfs"]:
        candidates.append(os.path.join(base, filename))

    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


async def drain_svg_queue_for_document(db, document_id: str, dry_run: bool) -> int:
    """
    Read pending processing_queue entries for this document (task_type='image',
    stage='storage') and create krai_content.images records from their payloads.
    Returns the number of images created.
    """
    rows = await db.fetch_all(
        """
        SELECT id, payload
        FROM krai_system.processing_queue
        WHERE document_id = $1::uuid
          AND stage = 'storage'
          AND task_type = 'image'
          AND status = 'pending'
        ORDER BY created_at
        """,
        [document_id],
    )

    if not rows:
        logger.warning("  No pending queue entries found for document %s", document_id)
        return 0

    created = 0
    for row in rows:
        payload_raw = row["payload"]
        if isinstance(payload_raw, str):
            payload = json.loads(payload_raw)
        else:
            payload = dict(payload_raw) if payload_raw else {}

        image_id = str(uuid.uuid4())
        svg_storage_url = payload.get("svg_storage_url") or ""
        original_svg_content = payload.get("original_svg_content")
        has_png = bool(payload.get("has_png_derivative", False))
        filename = payload.get("filename", "unknown.svg")
        page_number = payload.get("page_number", 0)
        meta = payload.get("metadata") or {}
        svg_size = meta.get("svg_size", 0)

        # If no MinIO URL, only proceed if we have inline SVG content
        if not svg_storage_url and not original_svg_content:
            logger.warning("  Skipping queue entry: no storage_url and no inline content (file=%s)", filename)
            continue

        effective_url = svg_storage_url or "inline"

        if dry_run:
            logger.info(
                "  [DRY RUN] Would create image record: doc=%s page=%s file=%s url=%s",
                document_id,
                page_number,
                filename,
                effective_url,
            )
            created += 1
            continue

        try:
            await db.execute_query(
                """
                INSERT INTO krai_content.images (
                    id, document_id, filename, original_filename,
                    storage_path, storage_url,
                    file_size, image_format,
                    svg_storage_url, original_svg_content,
                    is_vector_graphic, has_png_derivative,
                    page_number, image_index, image_type,
                    contains_text, tags, file_hash
                ) VALUES (
                    $1::uuid, $2::uuid, $3, $4,
                    $5, $6,
                    $7, 'SVG',
                    $8, $9,
                    true, $10,
                    $11, $12, 'vector_graphic',
                    false, '{}'::text[], $13
                )
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    image_id,
                    document_id,
                    filename,
                    filename,
                    effective_url,  # storage_path
                    effective_url,  # storage_url
                    svg_size,
                    svg_storage_url or None,  # svg_storage_url (null if no MinIO)
                    original_svg_content,
                    has_png,
                    page_number,
                    0,  # image_index (unknown)
                    None,  # file_hash
                ],
            )
            # Mark queue entry as completed
            await db.execute_query(
                """
                UPDATE krai_system.processing_queue
                SET status = 'completed'
                WHERE id = $1::uuid
                """,
                [str(row["id"])],
            )
            created += 1
            logger.debug("  Created image record %s for %s", image_id, filename)

        except Exception as exc:
            logger.error("  Failed to create image record for %s: %s", filename, exc)

    return created


async def run_svg_processor_for_document(
    db,
    storage_service,
    ai_service,
    document_id: str,
    pdf_path: str,
    dry_run: bool,
) -> int:
    """
    Run SVGProcessor for one document.  Returns number of queue entries created.
    """
    from backend.processors.svg_processor import SVGProcessor

    processor = SVGProcessor(
        database_service=db,
        storage_service=storage_service,
        ai_service=ai_service,
    )

    context = ProcessingContext(
        document_id=document_id,
        file_path=pdf_path,
        document_type="service_manual",
        file_hash="",
    )

    if dry_run:
        logger.info("  [DRY RUN] Would run SVGProcessor for document %s (%s)", document_id, pdf_path)
        return 0

    logger.info("  Running SVGProcessor for %s ...", pdf_path)
    result = await processor.safe_process(context)
    queued = result.data.get("images_queued", 0) if result.success else 0
    extracted = result.data.get("svgs_extracted", 0) if result.success else 0
    logger.info(
        "  SVGProcessor done: extracted=%s queued=%s success=%s",
        extracted,
        queued,
        result.success,
    )
    if not result.success:
        logger.error("  SVGProcessor error: %s", result.error)
    return queued


async def clear_svg_stage_marker(db, document_id: str, dry_run: bool) -> None:
    if dry_run:
        logger.info("  [DRY RUN] Would delete svg_processor marker for %s", document_id)
        return
    await db.execute_query(
        """
        DELETE FROM krai_system.stage_completion_markers
        WHERE document_id = $1::uuid AND stage_name = 'svg_processor'
        """,
        [document_id],
    )
    logger.debug("  Deleted svg_processor marker for %s", document_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(dry_run: bool, doc_id_filter: str | None) -> None:
    logger.info("=== SVG Image Repair Script ===")
    if dry_run:
        logger.warning("DRY RUN - no changes will be written")

    db = create_database_adapter(database_type="postgresql")
    await db.connect()

    # Import services
    from backend.services.object_storage_service import ObjectStorageService

    try:
        storage_service = ObjectStorageService(
            access_key_id=os.getenv("OBJECT_STORAGE_ACCESS_KEY", ""),
            secret_access_key=os.getenv("OBJECT_STORAGE_SECRET_KEY", ""),
            endpoint_url=os.getenv("OBJECT_STORAGE_ENDPOINT", ""),
            public_url_documents=os.getenv("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS", ""),
            public_url_error=os.getenv("OBJECT_STORAGE_PUBLIC_URL_ERROR", ""),
            public_url_parts=os.getenv("OBJECT_STORAGE_PUBLIC_URL_PARTS", ""),
        )
        await storage_service.connect()
        logger.info("Storage service connected.")
    except Exception as exc:
        logger.warning("Could not initialize/connect storage service (%s) - SVG will not be re-uploaded", exc)
        storage_service = None

    ai_service = None  # Optional – not needed for repair

    try:
        documents = await get_affected_documents(db)

        if doc_id_filter:
            documents = [d for d in documents if str(d["id"]) == doc_id_filter]
            if not documents:
                logger.error("Document %s not found in affected list", doc_id_filter)
                return

        if not documents:
            logger.info("No affected documents found – nothing to repair.")
            return

        logger.info("Found %d affected document(s):", len(documents))
        for d in documents:
            logger.info("  %s  (%s)", d["filename"], d["id"])

        total_queued = 0
        total_created = 0

        for doc in documents:
            doc_id = str(doc["id"])
            filename = doc["filename"]
            storage_path = doc.get("storage_path")

            logger.info("\n--- Processing: %s ---", filename)

            pdf_path = resolve_pdf_path(storage_path, filename)
            if not pdf_path:
                logger.error("  PDF not found for %s (storage_path=%s) – skipping", filename, storage_path)
                continue

            logger.info("  PDF path: %s", pdf_path)

            # Step 1: Clear stale svg_processor marker FIRST so safe_process() re-runs it
            await clear_svg_stage_marker(db, doc_id, dry_run)

            # Step 2: Run SVG processor (re-extracts SVGs, creates queue entries)
            queued = await run_svg_processor_for_document(db, storage_service, ai_service, doc_id, pdf_path, dry_run)
            total_queued += queued

            # Step 3: Drain queue entries → krai_content.images
            created = await drain_svg_queue_for_document(db, doc_id, dry_run)
            total_created += created

            logger.info(
                "  Document %s done: queued=%d, images_created=%d",
                filename,
                queued,
                created,
            )

        logger.info(
            "\n=== Repair complete: %d queue entries created, %d image records written ===",
            total_queued,
            total_created,
        )

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repair missing SVG image records")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--doc-id", help="Limit repair to a single document UUID")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, doc_id_filter=args.doc_id))
