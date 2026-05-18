#!/usr/bin/env python3
"""
Fast stage-check runner for targeted quality validation.

Typical use:
  python scripts/run_stage_checks.py -d <doc1> -d <doc2> --stages 9,10,11
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.base_processor import Stage
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.services.database_factory import create_database_adapter
from scripts._env import load_env

STAGE_NUMBER_MAP: dict[int, Stage] = {
    1: Stage.UPLOAD,
    2: Stage.TEXT_EXTRACTION,
    3: Stage.TABLE_EXTRACTION,
    4: Stage.SVG_PROCESSING,
    5: Stage.IMAGE_PROCESSING,
    6: Stage.VISUAL_EMBEDDING,
    7: Stage.LINK_EXTRACTION,
    8: Stage.CHUNK_PREPROCESSING,
    9: Stage.CLASSIFICATION,
    10: Stage.METADATA_EXTRACTION,
    11: Stage.PARTS_EXTRACTION,
    12: Stage.SERIES_DETECTION,
    13: Stage.STORAGE,
    14: Stage.EMBEDDING,
    15: Stage.SEARCH_INDEXING,
}

STAGE_MARKER_MAP: dict[Stage, str] = {
    Stage.UPLOAD: "upload_processor",
    Stage.TEXT_EXTRACTION: "text_processor",
    Stage.TABLE_EXTRACTION: "table_processor",
    Stage.SVG_PROCESSING: "svg_processor",
    Stage.IMAGE_PROCESSING: "image_processor",
    Stage.VISUAL_EMBEDDING: "visual_embedding_processor",
    Stage.LINK_EXTRACTION: "link_extraction_processor",
    Stage.CHUNK_PREPROCESSING: "chunk_preprocessor",
    Stage.CLASSIFICATION: "classification_processor",
    Stage.METADATA_EXTRACTION: "metadata_processor_ai",
    Stage.PARTS_EXTRACTION: "parts_processor",
    Stage.SERIES_DETECTION: "series_processor",
    Stage.STORAGE: "storage_processor",
    Stage.EMBEDDING: "embedding_processor",
    Stage.SEARCH_INDEXING: "search_processor",
}


def parse_stage_item(value: str) -> Stage:
    value = value.strip()
    try:
        return STAGE_NUMBER_MAP[int(value)]
    except ValueError:
        return Stage(value.lower())
    except KeyError as exc:
        raise ValueError(f"Invalid stage number: {value}") from exc


def parse_stages(stages_arg: str) -> list[Stage]:
    stages: list[Stage] = []
    for item in stages_arg.split(","):
        if not item.strip():
            continue
        stages.append(parse_stage_item(item))
    if not stages:
        raise ValueError("No stages provided")
    return stages


async def reset_stage_markers(db_adapter, document_ids: list[str], stages: list[Stage]) -> int:
    marker_names = [STAGE_MARKER_MAP[s] for s in stages if s in STAGE_MARKER_MAP]
    if not marker_names:
        return 0
    result = await db_adapter.execute_query(
        """
        DELETE FROM krai_system.stage_completion_markers
        WHERE document_id = ANY($1::uuid[])
          AND stage_name = ANY($2::text[])
        """,
        [document_ids, marker_names],
    )
    return int(getattr(result, "rowcount", 0))


async def collect_metrics(db_adapter, document_id: str) -> dict[str, int]:
    error_code_row = await db_adapter.fetch_one(
        """
        SELECT COUNT(*)::int AS count
        FROM krai_intelligence.error_codes
        WHERE document_id = $1::uuid
        """,
        [document_id],
    )

    parts_row = await db_adapter.fetch_one(
        """
        SELECT COUNT(DISTINCT p.id)::int AS count
        FROM krai_core.document_products dp
        JOIN krai_parts.parts_catalog p
          ON p.product_id = dp.product_id
        WHERE dp.document_id = $1::uuid
        """,
        [document_id],
    )

    return {
        "error_codes": int(error_code_row["count"]) if error_code_row else 0,
        "parts_for_document_products": int(parts_row["count"]) if parts_row else 0,
    }


async def run(args: argparse.Namespace) -> int:
    if args.quiet:
        logging.disable(logging.INFO)
        logging.getLogger().setLevel(logging.WARNING)
        for logger_name in ("krai", "backend", "httpx", "asyncpg"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    load_env(extra_files=[".env.database"])
    stages = parse_stages(args.stages)

    db_adapter = create_database_adapter()
    await db_adapter.initialize()

    pipeline = KRMasterPipeline(database_adapter=db_adapter)
    await pipeline.initialize_services()

    try:
        if args.reset_markers:
            deleted = await reset_stage_markers(db_adapter, args.document_id, stages)
            print(f"markers_deleted={deleted}")

        total_failed = 0

        for doc_id in args.document_id:
            print(f"\n=== Document {doc_id} ===")
            result = await pipeline.run_stages(doc_id, stages)

            print(
                "summary:",
                f"total={result['total_stages']}",
                f"ok={result['successful']}",
                f"failed={result['failed']}",
                f"success_rate={result['success_rate']:.1f}%",
            )

            for stage_result in result.get("stage_results", []):
                stage_name = stage_result.get("stage", "unknown")
                ok = bool(stage_result.get("success"))
                status = "OK" if ok else "FAIL"
                print(f"  - {stage_name}: {status}")
                if not ok and args.show_errors:
                    print(f"    error: {stage_result.get('error', 'unknown')}")

            metrics = await collect_metrics(db_adapter, doc_id)
            print(
                "metrics:",
                f"error_codes={metrics['error_codes']}",
                f"parts={metrics['parts_for_document_products']}",
            )

            total_failed += int(result.get("failed", 0))

        if args.strict and total_failed > 0:
            return 1
        return 0
    finally:
        await db_adapter.disconnect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fast, targeted stage checks")
    parser.add_argument(
        "--document-id",
        "-d",
        action="append",
        required=True,
        help="Document UUID (repeat for multiple documents)",
    )
    parser.add_argument(
        "--stages",
        default="9,10,11",
        help="Comma-separated stage numbers or names (default: 9,10,11)",
    )
    parser.add_argument(
        "--reset-markers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reset completion markers for the selected stages before run",
    )
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit with code 1 when any stage fails",
    )
    parser.add_argument(
        "--show-errors",
        action="store_true",
        help="Print detailed stage errors when available",
    )
    parser.add_argument(
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reduce pipeline log noise and keep output concise",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(f"fatal: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
