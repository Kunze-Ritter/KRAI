#!/usr/bin/env python3
"""
validate_snapshot.py

Validate snapshot integrity and verify PII anonymization.
Checks file existence, foreign key relationships, and residual PII.

Usage:
    python scripts/validate_snapshot.py --snapshot-dir ./staging-snapshots/latest
    python scripts/validate_snapshot.py --snapshot-dir ./staging-snapshots/anonymized --check-pii
    python scripts/validate_snapshot.py --snapshot-dir ./staging-snapshots/snapshot_20250116_103000 --verbose
"""

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from backend.services.database_factory import create_database_adapter
from scripts.scripts_env import load_env

logger = get_logger(__name__)


class PIIDetector:
    """Detect PII patterns in text."""

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?!555-)\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    IP_PATTERN = re.compile(r"\b(?!XXX\.XXX\.XXX\.XXX)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    URL_PATTERN = re.compile(r"https?://(?!example\.com)[^\s]+")

    @classmethod
    def detect_pii(cls, text: str) -> dict[str, list[str]]:
        """
        Detect PII patterns in text.

        Args:
            text: Text to scan

        Returns:
            Dictionary mapping pattern type to list of matches
        """
        if not text:
            return {}

        findings = {}

        emails = cls.EMAIL_PATTERN.findall(text)
        if emails:
            findings["emails"] = emails

        phones = cls.PHONE_PATTERN.findall(text)
        if phones:
            findings["phones"] = phones

        ips = cls.IP_PATTERN.findall(text)
        if ips:
            findings["ips"] = ips

        urls = cls.URL_PATTERN.findall(text)
        if urls:
            findings["urls"] = urls

        return findings


async def validate_manifest(snapshot_dir: Path) -> tuple[bool, dict[str, Any]]:
    """
    Validate snapshot manifest file.

    Args:
        snapshot_dir: Path to snapshot directory

    Returns:
        Tuple of (is_valid, manifest_data)
    """
    logger.info("📋 Validating manifest file...")

    manifest_file = snapshot_dir / "manifest.json"

    if not manifest_file.exists():
        logger.error(f"   ❌ Manifest file not found: {manifest_file}")
        return False, {}

    try:
        with open(manifest_file) as f:
            manifest = json.load(f)

        required_fields = ["timestamp", "export_date", "days", "tables", "total_rows"]
        missing_fields = [field for field in required_fields if field not in manifest]

        if missing_fields:
            logger.error(f"   ❌ Missing required fields: {', '.join(missing_fields)}")
            return False, manifest

        logger.info("   ✓ Manifest valid")
        logger.info(f"   Export date: {manifest['export_date']}")
        logger.info(f"   Total rows: {manifest['total_rows']}")

        return True, manifest

    except json.JSONDecodeError as e:
        logger.error(f"   ❌ Invalid JSON in manifest: {e}")
        return False, {}
    except Exception as e:
        logger.error(f"   ❌ Error reading manifest: {e}")
        return False, {}


async def validate_csv_files(snapshot_dir: Path, manifest: dict[str, Any]) -> bool:
    """
    Validate that all expected CSV files exist.

    Args:
        snapshot_dir: Path to snapshot directory
        manifest: Manifest data

    Returns:
        True if all files exist
    """
    logger.info("📁 Validating CSV files...")

    all_valid = True

    for table_name, expected_count in manifest.get("tables", {}).items():
        schema, table = table_name.split(".")
        csv_file = snapshot_dir / f"{schema}_{table}.csv"

        if not csv_file.exists():
            logger.error(f"   ❌ Missing CSV file: {csv_file}")
            all_valid = False
        else:
            file_size = csv_file.stat().st_size
            logger.info(f"   ✓ {table_name}: {file_size / 1024 / 1024:.2f} MB")

    return all_valid


async def validate_foreign_keys(db: Any) -> dict[str, Any]:
    """
    Validate foreign key relationships.

    Args:
        db: Database adapter

    Returns:
        Dictionary with validation results
    """
    logger.info("🔗 Validating foreign key relationships...")

    results = {"valid": True, "checks": []}

    checks = [
        {
            "name": "chunks.document_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_intelligence.chunks c
                LEFT JOIN krai_core.documents d ON c.document_id = d.id
                WHERE c.document_id IS NOT NULL AND d.id IS NULL
            """,
        },
        {
            "name": "images.document_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_content.images i
                LEFT JOIN krai_core.documents d ON i.document_id = d.id
                WHERE i.document_id IS NOT NULL AND d.id IS NULL
            """,
        },
        {
            "name": "videos.document_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_content.videos v
                LEFT JOIN krai_core.documents d ON v.document_id = d.id
                WHERE v.document_id IS NOT NULL AND d.id IS NULL
            """,
        },
        {
            "name": "links.document_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_content.links l
                LEFT JOIN krai_core.documents d ON l.document_id = d.id
                WHERE l.document_id IS NOT NULL AND d.id IS NULL
            """,
        },
        {
            "name": "content.chunks.document_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_content.chunks cc
                LEFT JOIN krai_core.documents d ON cc.document_id = d.id
                WHERE cc.document_id IS NOT NULL AND d.id IS NULL
            """,
        },
        {
            "name": "embeddings_v2.source_id → documents.id",
            "query": """
                SELECT COUNT(*)
                FROM krai_intelligence.embeddings_v2 e
                LEFT JOIN krai_core.documents d ON e.source_id = d.id
                WHERE e.source_type = 'document' AND e.source_id IS NOT NULL AND d.id IS NULL
            """,
        },
    ]

    for check in checks:
        try:
            result = await db.fetch_one(check["query"])
            orphan_count = result[0] if result else 0

            check_result = {"name": check["name"], "orphaned_records": orphan_count, "valid": orphan_count == 0}

            results["checks"].append(check_result)

            if orphan_count == 0:
                logger.info(f"   ✓ {check['name']}: OK")
            else:
                logger.error(f"   ❌ {check['name']}: {orphan_count} orphaned records")
                results["valid"] = False

        except Exception as e:
            logger.error(f"   ❌ {check['name']}: Error - {e}")
            results["valid"] = False

    return results


async def validate_document_counts(db: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Validate document counts match manifest.

    Args:
        db: Database adapter
        manifest: Manifest data

    Returns:
        Dictionary with validation results
    """
    logger.info("📊 Validating document counts...")

    results = {"valid": True, "tables": []}

    for table_name, expected_count in manifest.get("tables", {}).items():
        try:
            query = f"SELECT COUNT(*) FROM {table_name}"
            result = await db.fetch_one(query)
            actual_count = result[0] if result else 0

            table_result = {
                "table": table_name,
                "expected": expected_count,
                "actual": actual_count,
                "valid": actual_count == expected_count,
            }

            results["tables"].append(table_result)

            if actual_count == expected_count:
                logger.info(f"   ✓ {table_name}: {actual_count} rows (matches manifest)")
            else:
                logger.warning(f"   ⚠️  {table_name}: {actual_count} rows (expected {expected_count})")
                results["valid"] = False

        except Exception as e:
            logger.error(f"   ❌ {table_name}: Error - {e}")
            results["valid"] = False

    return results


async def check_residual_pii(db: Any) -> dict[str, Any]:
    """
    Check for residual PII in anonymized data.

    Args:
        db: Database adapter

    Returns:
        Dictionary with PII detection results
    """
    logger.info("🔍 Checking for residual PII...")

    detector = PIIDetector()
    results = {"pii_found": False, "findings": defaultdict(list)}

    logger.info("   Scanning documents metadata...")
    doc_query = "SELECT id, metadata, storage_url, storage_path FROM krai_core.documents LIMIT 100"
    docs = await db.fetch_all(doc_query)

    for doc in docs:
        if doc["metadata"]:
            metadata_str = json.dumps(doc["metadata"])
            pii = detector.detect_pii(metadata_str)
            if pii:
                results["pii_found"] = True
                results["findings"]["documents_metadata"].append({"id": str(doc["id"]), "pii": pii})

        if doc["storage_url"]:
            pii = detector.detect_pii(doc["storage_url"])
            if pii:
                results["pii_found"] = True
                results["findings"]["documents_storage_url"].append({"id": str(doc["id"]), "pii": pii})

    logger.info("   Scanning chunks text...")
    chunk_query = "SELECT id, text_chunk FROM krai_intelligence.chunks WHERE text_chunk IS NOT NULL LIMIT 100"
    chunks = await db.fetch_all(chunk_query)

    for chunk in chunks:
        if chunk["text_chunk"]:
            pii = detector.detect_pii(chunk["text_chunk"])
            if pii:
                results["pii_found"] = True
                results["findings"]["chunks_text"].append({"id": str(chunk["id"]), "pii": pii})

    logger.info("   Scanning images...")
    image_query = "SELECT id, ai_description, ocr_text, storage_url FROM krai_content.images LIMIT 100"
    images = await db.fetch_all(image_query)

    for image in images:
        if image["ai_description"]:
            pii = detector.detect_pii(image["ai_description"])
            if pii:
                results["pii_found"] = True
                results["findings"]["images_ai_description"].append({"id": str(image["id"]), "pii": pii})

        if image["ocr_text"]:
            pii = detector.detect_pii(image["ocr_text"])
            if pii:
                results["pii_found"] = True
                results["findings"]["images_ocr_text"].append({"id": str(image["id"]), "pii": pii})

    if results["pii_found"]:
        logger.error("   ❌ Residual PII detected!")
        for field, findings in results["findings"].items():
            logger.error(f"      {field}: {len(findings)} instances")
    else:
        logger.info("   ✓ No residual PII detected")

    return dict(results)


async def validate_benchmark_documents(snapshot_dir: Path) -> dict[str, Any]:
    """
    Validate benchmark document selection.

    Args:
        snapshot_dir: Path to snapshot directory

    Returns:
        Dictionary with validation results
    """
    logger.info("📚 Validating benchmark documents...")

    report_file = snapshot_dir / "benchmark_selection_report.json"
    benchmark_dir = snapshot_dir / "benchmark-documents"

    if not report_file.exists():
        logger.warning("   ⚠️  Benchmark selection report not found (optional)")
        return {"valid": True, "skipped": True}

    try:
        with open(report_file) as f:
            report = json.load(f)

        results = {"valid": True, "selected_count": report.get("selected_count", 0), "missing_files": []}

        logger.info(f"   Selected documents: {results['selected_count']}")

        if benchmark_dir.exists():
            logger.info("   ✓ Benchmark directory exists")
        else:
            logger.warning(f"   ⚠️  Benchmark directory not found: {benchmark_dir}")

        return results

    except Exception as e:
        logger.error(f"   ❌ Error validating benchmark documents: {e}")
        return {"valid": False, "error": str(e)}


async def validate_snapshot(snapshot_dir: Path, check_pii: bool = False, verbose: bool = False) -> dict[str, Any]:
    """
    Validate snapshot integrity.

    Args:
        snapshot_dir: Path to snapshot directory
        check_pii: If True, check for residual PII
        verbose: Enable verbose logging

    Returns:
        Dictionary with validation results
    """
    logger.info(f"🔍 Validating snapshot: {snapshot_dir}")

    validation_results = {
        "snapshot_dir": str(snapshot_dir),
        "timestamp": snapshot_dir.name.replace("snapshot_", ""),
        "checks": {},
        "overall_valid": True,
    }

    manifest_valid, manifest = await validate_manifest(snapshot_dir)
    validation_results["checks"]["manifest"] = {"valid": manifest_valid, "data": manifest}
    if not manifest_valid:
        validation_results["overall_valid"] = False

    csv_valid = await validate_csv_files(snapshot_dir, manifest)
    validation_results["checks"]["csv_files"] = {"valid": csv_valid}
    if not csv_valid:
        validation_results["overall_valid"] = False

    db = create_database_adapter(database_type="postgresql")

    try:
        await db.connect()
        logger.info("✓ Connected to database")

        fk_results = await validate_foreign_keys(db)
        validation_results["checks"]["foreign_keys"] = fk_results
        if not fk_results["valid"]:
            validation_results["overall_valid"] = False

        count_results = await validate_document_counts(db, manifest)
        validation_results["checks"]["document_counts"] = count_results
        if not count_results["valid"]:
            validation_results["overall_valid"] = False

        if check_pii:
            pii_results = await check_residual_pii(db)
            validation_results["checks"]["pii_detection"] = pii_results
            if pii_results["pii_found"]:
                validation_results["overall_valid"] = False

    except Exception as e:
        logger.error(f"❌ Database validation error: {e}")
        validation_results["overall_valid"] = False
        validation_results["error"] = str(e)
    finally:
        await db.disconnect()

    benchmark_results = await validate_benchmark_documents(snapshot_dir)
    validation_results["checks"]["benchmark_documents"] = benchmark_results

    report_file = snapshot_dir / "validation_report.json"
    with open(report_file, "w") as f:
        json.dump(validation_results, f, indent=2, default=str)

    if validation_results["overall_valid"]:
        logger.success("✅ Snapshot validation passed!")
    else:
        logger.error("❌ Snapshot validation failed!")

    logger.info(f"   Report saved to: {report_file}")

    return validation_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate snapshot integrity and PII anonymization")
    parser.add_argument("--snapshot-dir", type=Path, required=True, help="Path to snapshot directory")
    parser.add_argument("--check-pii", action="store_true", help="Check for residual PII in anonymized data")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if not args.snapshot_dir.exists():
        logger.error(f"❌ Snapshot directory not found: {args.snapshot_dir}")
        sys.exit(1)

    load_env()

    try:
        result = asyncio.run(
            validate_snapshot(snapshot_dir=args.snapshot_dir, check_pii=args.check_pii, verbose=args.verbose)
        )

        if result.get("overall_valid", False):
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
