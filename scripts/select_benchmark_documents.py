#!/usr/bin/env python3
"""
select_benchmark_documents.py

Select representative documents from a snapshot for benchmark testing.
Stratifies selection by document type, manufacturer, and page count.

Usage:
    python scripts/select_benchmark_documents.py --snapshot-dir ./staging-snapshots/latest
    python scripts/select_benchmark_documents.py --snapshot-dir ./staging-snapshots/snapshot_20250116_103000 --count 20
    python scripts/select_benchmark_documents.py --snapshot-dir ./staging-snapshots/latest --min-size 2097152 --max-size 52428800
"""

import argparse
import asyncio
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from backend.services.database_factory import create_database_adapter
from scripts.scripts_env import load_env

logger = get_logger(__name__)


async def select_benchmark_documents(
    snapshot_dir: Path, count: int, min_size: int, max_size: int, output_file: Path
) -> dict[str, Any]:
    """
    Select representative documents for benchmarking.

    Args:
        snapshot_dir: Path to snapshot directory
        count: Number of documents to select
        min_size: Minimum file size in bytes
        max_size: Maximum file size in bytes
        output_file: Path to output report file

    Returns:
        Dictionary with selection results and statistics
    """
    logger.info(f"🔍 Selecting {count} benchmark documents from {snapshot_dir}")
    logger.info(f"   Size range: {min_size / 1024 / 1024:.2f} MB - {max_size / 1024 / 1024:.2f} MB")

    db = create_database_adapter(database_type="postgresql")

    try:
        await db.connect()
        logger.info("✓ Connected to database")

        query = """
            SELECT
                id,
                filename,
                file_size,
                document_type,
                manufacturer_id,
                page_count,
                processing_status,
                created_at,
                metadata,
                storage_path,
                storage_url
            FROM krai_core.documents
            WHERE file_size BETWEEN $1 AND $2
                AND processing_status = 'completed'
            ORDER BY created_at DESC
        """

        logger.info("📊 Querying documents...")
        results = await db.fetch_all(query, min_size, max_size)

        if not results:
            logger.error("❌ No documents found matching criteria")
            return {"success": False, "error": "No documents found", "selected_count": 0}

        logger.info(f"   Found {len(results)} candidate documents")

        documents = [dict(row) for row in results]

        stratified_docs = stratify_documents(documents, count)

        if len(stratified_docs) < count:
            logger.warning(f"⚠️  Only {len(stratified_docs)} documents available (requested {count})")

        stats = calculate_statistics(stratified_docs)
        logger.info("📈 Document statistics:")
        logger.info(f"   Avg size: {stats['avg_size'] / 1024 / 1024:.2f} MB")
        logger.info(f"   Avg pages: {stats['avg_page_count']:.1f}")
        logger.info(f"   Document types: {', '.join(stats['document_types'].keys())}")

        document_ids = [doc["id"] for doc in stratified_docs]

        update_query = """
            UPDATE krai_core.documents
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{is_benchmark}',
                'true'::jsonb
            )
            WHERE id = ANY($1)
        """

        logger.info(f"💾 Updating {len(document_ids)} documents with benchmark flag...")
        await db.execute(update_query, document_ids)
        logger.info("   ✓ Metadata updated")

        snapshot_id = snapshot_dir.name.replace("snapshot_", "")

        insert_benchmark_query = """
            INSERT INTO krai_system.benchmark_documents
                (document_id, snapshot_id, file_size, selected_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (document_id, snapshot_id) DO UPDATE
            SET file_size = EXCLUDED.file_size,
                selected_at = EXCLUDED.selected_at
        """

        logger.info(f"💾 Inserting {len(stratified_docs)} documents into benchmark_documents table...")
        for doc in stratified_docs:
            await db.execute(insert_benchmark_query, doc["id"], snapshot_id, doc["file_size"])
        logger.info("   ✓ Benchmark documents table updated")

        benchmark_dir = snapshot_dir / "benchmark-documents"
        benchmark_dir.mkdir(exist_ok=True)
        logger.info(f"📁 Created benchmark directory: {benchmark_dir}")

        report = {
            "timestamp": snapshot_dir.name.replace("snapshot_", ""),
            "selection_criteria": {
                "count": count,
                "min_size_mb": min_size / 1024 / 1024,
                "max_size_mb": max_size / 1024 / 1024,
            },
            "selected_count": len(stratified_docs),
            "statistics": stats,
            "documents": [
                {
                    "id": str(doc["id"]),
                    "filename": doc["filename"],
                    "file_size_mb": doc["file_size"] / 1024 / 1024,
                    "document_type": doc["document_type"],
                    "manufacturer_id": str(doc["manufacturer_id"]) if doc["manufacturer_id"] else None,
                    "page_count": doc["page_count"],
                    "storage_path": doc["storage_path"],
                    "storage_url": doc["storage_url"],
                }
                for doc in stratified_docs
            ],
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.success(f"✅ Selection complete! Report saved to {output_file}")
        logger.info(f"   Selected {len(stratified_docs)} documents")
        logger.info(f"   Benchmark directory: {benchmark_dir}")

        return report

    except Exception as e:
        logger.error(f"❌ Error selecting documents: {e}")
        raise
    finally:
        await db.disconnect()


def stratify_documents(documents: list[dict], target_count: int) -> list[dict]:
    """
    Stratify documents by type, manufacturer, and page count.

    Args:
        documents: List of document dictionaries
        target_count: Target number of documents to select

    Returns:
        List of selected documents
    """
    by_type = defaultdict(list)
    for doc in documents:
        doc_type = doc.get("document_type") or "unknown"
        by_type[doc_type].append(doc)

    selected = []
    types = list(by_type.keys())
    per_type = max(1, target_count // len(types))

    for doc_type in types:
        type_docs = by_type[doc_type]

        type_docs.sort(key=lambda d: (d.get("page_count") or 0, d.get("file_size") or 0))

        step = max(1, len(type_docs) // per_type)
        type_selected = type_docs[::step][:per_type]
        selected.extend(type_selected)

    if len(selected) < target_count:
        remaining = target_count - len(selected)
        selected_ids = {doc["id"] for doc in selected}
        unselected = [doc for doc in documents if doc["id"] not in selected_ids]
        selected.extend(unselected[:remaining])

    return selected[:target_count]


def calculate_statistics(documents: list[dict]) -> dict[str, Any]:
    """
    Calculate statistics for selected documents.

    Args:
        documents: List of document dictionaries

    Returns:
        Dictionary with statistics
    """
    sizes = [doc["file_size"] for doc in documents if doc.get("file_size")]
    page_counts = [doc["page_count"] for doc in documents if doc.get("page_count")]

    type_counts = defaultdict(int)
    for doc in documents:
        doc_type = doc.get("document_type") or "unknown"
        type_counts[doc_type] += 1

    manufacturer_counts = defaultdict(int)
    for doc in documents:
        mfr_id = doc.get("manufacturer_id")
        if mfr_id:
            manufacturer_counts[str(mfr_id)] += 1

    return {
        "total_documents": len(documents),
        "avg_size": statistics.mean(sizes) if sizes else 0,
        "median_size": statistics.median(sizes) if sizes else 0,
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
        "avg_page_count": statistics.mean(page_counts) if page_counts else 0,
        "median_page_count": statistics.median(page_counts) if page_counts else 0,
        "document_types": dict(type_counts),
        "manufacturer_distribution": dict(manufacturer_counts),
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Select representative documents for benchmark testing")
    parser.add_argument("--snapshot-dir", type=Path, required=True, help="Path to snapshot directory")
    parser.add_argument("--count", type=int, default=10, help="Number of documents to select (default: 10)")
    parser.add_argument("--min-size", type=int, default=1048576, help="Minimum file size in bytes (default: 1MB)")
    parser.add_argument("--max-size", type=int, default=104857600, help="Maximum file size in bytes (default: 100MB)")
    parser.add_argument(
        "--output", type=Path, help="Output report file (default: <snapshot-dir>/benchmark_selection_report.json)"
    )

    args = parser.parse_args()

    if not args.snapshot_dir.exists():
        logger.error(f"❌ Snapshot directory not found: {args.snapshot_dir}")
        sys.exit(1)

    output_file = args.output or (args.snapshot_dir / "benchmark_selection_report.json")

    load_env()

    try:
        result = asyncio.run(
            select_benchmark_documents(
                snapshot_dir=args.snapshot_dir,
                count=args.count,
                min_size=args.min_size,
                max_size=args.max_size,
                output_file=output_file,
            )
        )

        if result.get("success", True):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
