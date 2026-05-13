#!/usr/bin/env python3
"""
anonymize_pii.py

Anonymize personally identifiable information (PII) in database snapshots.
Processes CSV snapshot files to remove sensitive data while preserving technical content.

Usage:
    python scripts/anonymize_pii.py --snapshot-dir ./staging-snapshots/latest --output-dir ./staging-snapshots/anonymized
    python scripts/anonymize_pii.py --snapshot-dir ./staging-snapshots/snapshot_20250116_103000 --dry-run
    python scripts/anonymize_pii.py --snapshot-dir ./staging-snapshots/latest --verbose
"""

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.processors.logger import get_logger
from scripts.scripts_env import load_env

logger = get_logger(__name__)


class PIIAnonymizer:
    """Anonymize PII in database records."""

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
    IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    URL_PATTERN = re.compile(r"https?://[^\s]+")

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.stats = defaultdict(int)

    def _hash_value(self, value: str) -> str:
        """Generate short hash of value."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def anonymize_email(self, text: str) -> tuple[str, int]:
        """Replace email addresses with anonymized versions."""
        count = 0

        def replace_email(match):
            nonlocal count
            count += 1
            email = match.group(0)
            hashed = self._hash_value(email)
            return f"user_{hashed}@example.com"

        result = self.EMAIL_PATTERN.sub(replace_email, text)
        return result, count

    def anonymize_phone(self, text: str) -> tuple[str, int]:
        """Replace phone numbers with anonymized versions."""
        count = 0

        def replace_phone(match):
            nonlocal count
            count += 1
            phone = match.group(0)
            hashed = self._hash_value(phone)[:8]
            return f"555-{hashed}"

        result = self.PHONE_PATTERN.sub(replace_phone, text)
        return result, count

    def anonymize_ip(self, text: str) -> tuple[str, int]:
        """Redact IP addresses."""
        count = 0

        def replace_ip(match):
            nonlocal count
            count += 1
            return "XXX.XXX.XXX.XXX"

        result = self.IP_PATTERN.sub(replace_ip, text)
        return result, count

    def anonymize_url(self, text: str) -> tuple[str, int]:
        """Anonymize URLs while preserving structure."""
        count = 0

        def replace_url(match):
            nonlocal count
            count += 1
            url = match.group(0)
            hashed = self._hash_value(url)[:12]

            if url.startswith("https://"):
                return f"https://example.com/{hashed}"
            return f"http://example.com/{hashed}"

        result = self.URL_PATTERN.sub(replace_url, text)
        return result, count

    def anonymize_text(self, text: str) -> tuple[str, dict[str, int]]:
        """
        Anonymize all PII patterns in text.

        Args:
            text: Text to anonymize

        Returns:
            Tuple of (anonymized_text, pattern_counts)
        """
        if not text:
            return text, {}

        pattern_counts = {}

        text, email_count = self.anonymize_email(text)
        if email_count > 0:
            pattern_counts["emails"] = email_count

        text, phone_count = self.anonymize_phone(text)
        if phone_count > 0:
            pattern_counts["phones"] = phone_count

        text, ip_count = self.anonymize_ip(text)
        if ip_count > 0:
            pattern_counts["ips"] = ip_count

        text, url_count = self.anonymize_url(text)
        if url_count > 0:
            pattern_counts["urls"] = url_count

        return text, pattern_counts

    def anonymize_jsonb(self, data: dict) -> tuple[dict, dict[str, int]]:
        """
        Anonymize PII in JSONB data.

        Args:
            data: JSONB dictionary

        Returns:
            Tuple of (anonymized_data, pattern_counts)
        """
        if not data:
            return data, {}

        total_counts = defaultdict(int)

        def anonymize_recursive(obj):
            if isinstance(obj, str):
                anonymized, counts = self.anonymize_text(obj)
                for pattern, count in counts.items():
                    total_counts[pattern] += count
                return anonymized
            if isinstance(obj, dict):
                return {k: anonymize_recursive(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [anonymize_recursive(item) for item in obj]
            return obj

        anonymized_data = anonymize_recursive(data)
        return anonymized_data, dict(total_counts)


def anonymize_csv_file(
    csv_file: Path, output_file: Path, anonymizer: PIIAnonymizer, text_columns: list[str], jsonb_columns: list[str]
) -> dict[str, int]:
    """
    Anonymize PII in a CSV file.

    Args:
        csv_file: Input CSV file path
        output_file: Output CSV file path
        anonymizer: PIIAnonymizer instance
        text_columns: List of column names containing text to anonymize
        jsonb_columns: List of column names containing JSONB to anonymize

    Returns:
        Dictionary with anonymization statistics
    """
    stats = defaultdict(int)

    with open(csv_file, encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames

        rows = []
        for row in reader:
            for col in text_columns:
                if row.get(col):
                    anonymized, counts = anonymizer.anonymize_text(row[col])
                    row[col] = anonymized
                    for pattern, count in counts.items():
                        stats[f"{col}_{pattern}"] += count

            for col in jsonb_columns:
                if row.get(col):
                    try:
                        data = json.loads(row[col])
                        anonymized, counts = anonymizer.anonymize_jsonb(data)
                        row[col] = json.dumps(anonymized)
                        for pattern, count in counts.items():
                            stats[f"{col}_{pattern}"] += count
                    except json.JSONDecodeError:
                        pass

            rows.append(row)

    with open(output_file, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return dict(stats)


async def anonymize_snapshot(
    snapshot_dir: Path, output_dir: Path, dry_run: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """
    Anonymize PII in database snapshot files.

    Args:
        snapshot_dir: Path to snapshot directory
        output_dir: Path to output directory for anonymized data
        dry_run: If True, preview changes without applying
        verbose: Enable verbose logging

    Returns:
        Dictionary with anonymization results
    """
    logger.info(f"🔒 Anonymizing PII in snapshot: {snapshot_dir}")
    if dry_run:
        logger.warning("⚠️  DRY RUN MODE - No changes will be applied")

    if not output_dir:
        output_dir = snapshot_dir.parent / f"{snapshot_dir.name}_anonymized"

    output_dir.mkdir(parents=True, exist_ok=True)

    anonymizer = PIIAnonymizer(verbose=verbose)
    all_stats = {}

    table_configs = {
        "krai_core_documents.csv": {"text_columns": ["storage_url", "storage_path"], "jsonb_columns": ["metadata"]},
        "krai_intelligence_chunks.csv": {"text_columns": ["text_chunk"], "jsonb_columns": []},
        "krai_content_images.csv": {"text_columns": ["ai_description", "ocr_text", "storage_url"], "jsonb_columns": []},
        "krai_content_videos.csv": {"text_columns": ["storage_url"], "jsonb_columns": []},
        "krai_content_links.csv": {"text_columns": ["url"], "jsonb_columns": []},
        "krai_content_chunks.csv": {"text_columns": [], "jsonb_columns": []},
        "krai_intelligence_embeddings_v2.csv": {"text_columns": ["embedding_context"], "jsonb_columns": ["metadata"]},
    }

    for csv_filename, config in table_configs.items():
        csv_file = snapshot_dir / csv_filename

        if not csv_file.exists():
            logger.warning(f"   ⚠️  CSV file not found: {csv_filename}")
            continue

        logger.info(f"📄 Processing {csv_filename}...")

        output_file = output_dir / csv_filename

        if not dry_run:
            stats = anonymize_csv_file(
                csv_file, output_file, anonymizer, config["text_columns"], config["jsonb_columns"]
            )
            all_stats[csv_filename] = stats

            total_anonymizations = sum(stats.values())
            logger.info(f"   ✓ Anonymized {total_anonymizations} PII instances")
        else:
            logger.info(f"   [DRY RUN] Would process {csv_filename}")

    manifest_file = snapshot_dir / "manifest.json"
    if manifest_file.exists():
        shutil.copy(manifest_file, output_dir / "manifest.json")
        logger.info("   ✓ Copied manifest.json")

    total_anonymizations = sum(sum(table_stats.values()) for table_stats in all_stats.values())

    report = {
        "snapshot_dir": str(snapshot_dir),
        "output_dir": str(output_dir),
        "dry_run": dry_run,
        "total_anonymizations": total_anonymizations,
        "statistics": all_stats,
    }

    report_file = output_dir / "anonymization_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    logger.success("✅ Anonymization complete!")
    logger.info(f"   Total anonymizations: {total_anonymizations}")
    logger.info(f"   Output directory: {output_dir}")
    logger.info(f"   Report saved to: {report_file}")

    if verbose:
        logger.info("\n📊 Detailed Statistics:")
        for table, stats in all_stats.items():
            if stats:
                logger.info(f"\n   {table}:")
                for pattern, count in stats.items():
                    logger.info(f"      {pattern}: {count}")

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Anonymize PII in database snapshots")
    parser.add_argument("--snapshot-dir", type=Path, required=True, help="Path to snapshot directory")
    parser.add_argument(
        "--output-dir", type=Path, help="Output directory for anonymized data (default: <snapshot-dir>_anonymized)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if not args.snapshot_dir.exists():
        logger.error(f"❌ Snapshot directory not found: {args.snapshot_dir}")
        sys.exit(1)

    load_env()

    try:
        import asyncio

        result = asyncio.run(
            anonymize_snapshot(
                snapshot_dir=args.snapshot_dir, output_dir=args.output_dir, dry_run=args.dry_run, verbose=args.verbose
            )
        )

        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
