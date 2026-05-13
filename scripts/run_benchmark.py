"""
Benchmark Execution Script for KRAI Pipeline Performance Testing

This script measures pipeline performance on benchmark documents, calculates
statistical metrics (avg, P50, P95, P99), and stores/compares baseline results.

Usage:
    python scripts/run_benchmark.py --count 10 --baseline
    python scripts/run_benchmark.py --count 10 --compare
    python scripts/run_benchmark.py --stage embedding --count 10
    python scripts/run_benchmark.py --count 10 --verbose
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.processors.logger import get_logger
from backend.services.database_factory import create_database_adapter
from scripts.scripts_env import load_env

logger = get_logger(__name__)


async def get_benchmark_documents(db, count: int) -> list[dict]:
    """
    Fetch benchmark documents from database.

    Args:
        db: Database adapter instance
        count: Number of documents to fetch

    Returns:
        List of document dictionaries with id, filename, file_size, storage_path, storage_url

    Raises:
        Exception: If no benchmark documents found
    """
    query = """
        SELECT d.id, d.filename, d.file_size, d.storage_path, d.storage_url, d.metadata
        FROM krai_system.benchmark_documents bd
        JOIN krai_core.documents d ON bd.document_id = d.id
        WHERE d.metadata->>'is_benchmark' = 'true'
        ORDER BY bd.selected_at DESC
        LIMIT $1
    """

    try:
        results = await db.fetch_all(query, count)

        if not results:
            raise Exception("No benchmark documents found. Run select_benchmark_documents.py first.")

        if len(results) < count:
            logger.warning(f"⚠️  Only {len(results)} benchmark documents available (requested {count})")

        documents = [dict(row) for row in results]
        logger.info(f"📋 Fetched {len(documents)} benchmark documents")

        return documents

    except Exception as e:
        logger.error(f"❌ Failed to fetch benchmark documents: {e}")
        raise


async def measure_pipeline_performance(
    pipeline: KRMasterPipeline, document: dict, doc_index: int, total_docs: int
) -> dict[str, Any]:
    """
    Measure full pipeline performance for a single document.

    Args:
        pipeline: KRMasterPipeline instance
        document: Document dictionary
        doc_index: Current document index (1-based)
        total_docs: Total number of documents

    Returns:
        Dictionary with performance metrics
    """
    document_id = str(document["id"])
    filename = document["filename"]
    file_size = document.get("file_size", 0)

    logger.info(f"⏱️  Processing document {doc_index}/{total_docs}: {filename}")

    result = {
        "document_id": document_id,
        "filename": filename,
        "file_size": file_size,
        "total_duration_seconds": 0.0,
        "stage_timings": {},
        "success": False,
        "error": None,
    }

    try:
        start_time = time.perf_counter()
        pipeline_start_timestamp = datetime.utcnow()

        # Construct file path from storage_path or storage_url
        file_path = document.get("storage_path") or document.get("storage_url")
        if not file_path:
            raise ValueError(f"No storage_path or storage_url for document {document_id}")

        # Process document through full pipeline
        await pipeline.process_single_document_full_pipeline(
            file_path=file_path, doc_index=doc_index, total_docs=total_docs
        )

        end_time = time.perf_counter()
        total_duration = end_time - start_time

        # Query stage completion markers to get stage-level timings
        stage_query = """
            SELECT stage_name, completed_at
            FROM krai_system.stage_completion_markers
            WHERE document_id = $1
            ORDER BY completed_at ASC
        """

        stage_markers = await pipeline.db.fetch_all(stage_query, document_id)

        # Calculate stage durations using only database timestamps
        stage_timings = {}
        prev_timestamp = pipeline_start_timestamp

        for marker in stage_markers:
            stage_name = marker["stage_name"]
            completed_at = marker["completed_at"]

            # Calculate duration as difference between consecutive timestamps
            stage_duration = (completed_at - prev_timestamp).total_seconds()

            stage_timings[stage_name] = stage_duration
            prev_timestamp = completed_at

        result["total_duration_seconds"] = total_duration
        result["stage_timings"] = stage_timings
        result["success"] = True

        logger.info(f"✅ Completed in {total_duration:.2f}s")

    except Exception as e:
        logger.error(f"❌ Failed to process {filename}: {e}")
        result["error"] = str(e)

    return result


async def measure_stage_performance(pipeline: KRMasterPipeline, document: dict, stage_name: str) -> dict[str, Any]:
    """
    Measure performance of a specific pipeline stage.

    DISABLED: Stage-only benchmark mode does not execute pipeline stages,
    so timings reflect query latency instead of processing time.
    Use full pipeline mode (--stage full_pipeline) to get accurate timings.

    Args:
        pipeline: KRMasterPipeline instance
        document: Document dictionary
        stage_name: Name of the stage to benchmark

    Returns:
        Dictionary with stage performance metrics
    """
    document_id = str(document["id"])
    filename = document["filename"]

    logger.error(
        "❌ Stage-only benchmark mode is disabled. "
        "This mode does not execute pipeline stages and reports query latency instead of processing time. "
        "Use full pipeline mode without --stage flag to get accurate per-stage timings."
    )

    result = {
        "document_id": document_id,
        "filename": filename,
        "stage_name": stage_name,
        "duration_seconds": 0.0,
        "stage_metrics": {},
        "success": False,
        "error": "Stage-only benchmark mode is disabled. Use full pipeline mode for accurate timings.",
    }

    return result


def calculate_statistics(durations: list[float]) -> dict[str, float]:
    """
    Calculate statistical metrics from duration measurements.

    Args:
        durations: List of duration values in seconds

    Returns:
        Dictionary with avg, P50, P95, P99, min, max, std_dev
    """
    if not durations:
        return {
            "avg_seconds": 0.0,
            "p50_seconds": 0.0,
            "p95_seconds": 0.0,
            "p99_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
            "std_dev": 0.0,
        }

    sorted_durations = sorted(durations)
    n = len(sorted_durations)

    stats = {
        "avg_seconds": statistics.mean(sorted_durations),
        "p50_seconds": statistics.median(sorted_durations),
        "min_seconds": min(sorted_durations),
        "max_seconds": max(sorted_durations),
    }

    # Calculate P95
    p95_index = int(n * 0.95)
    if p95_index >= n:
        p95_index = n - 1
    stats["p95_seconds"] = sorted_durations[p95_index]

    # Calculate P99
    p99_index = int(n * 0.99)
    if p99_index >= n:
        p99_index = n - 1
    stats["p99_seconds"] = sorted_durations[p99_index]

    # Calculate standard deviation
    if n > 1:
        stats["std_dev"] = statistics.stdev(sorted_durations)
    else:
        stats["std_dev"] = 0.0

    return stats


async def store_baseline(db, stage_name: str, stats: dict, document_ids: list[str], notes: str | None = None):
    """
    Store baseline performance metrics in database.

    Args:
        db: Database adapter instance
        stage_name: Name of the stage
        stats: Statistics dictionary
        document_ids: List of document UUIDs used for baseline
        notes: Optional notes about the baseline
    """
    query = """
        INSERT INTO krai_system.performance_baselines
            (stage_name, baseline_avg_seconds, baseline_p50_seconds,
             baseline_p95_seconds, baseline_p99_seconds, test_document_ids,
             measurement_date, notes)
        VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7)
        ON CONFLICT (stage_name, DATE(measurement_date))
        DO UPDATE SET
            baseline_avg_seconds = EXCLUDED.baseline_avg_seconds,
            baseline_p50_seconds = EXCLUDED.baseline_p50_seconds,
            baseline_p95_seconds = EXCLUDED.baseline_p95_seconds,
            baseline_p99_seconds = EXCLUDED.baseline_p99_seconds,
            test_document_ids = EXCLUDED.test_document_ids,
            notes = EXCLUDED.notes,
            measurement_date = EXCLUDED.measurement_date
    """

    try:
        await db.execute(
            query,
            stage_name,
            stats["avg_seconds"],
            stats["p50_seconds"],
            stats["p95_seconds"],
            stats["p99_seconds"],
            document_ids,
            notes,
        )

        logger.info(
            f"💾 Stored baseline for '{stage_name}': "
            f"avg={stats['avg_seconds']:.2f}s, "
            f"P50={stats['p50_seconds']:.2f}s, "
            f"P95={stats['p95_seconds']:.2f}s, "
            f"P99={stats['p99_seconds']:.2f}s"
        )

    except Exception as e:
        logger.error(f"❌ Failed to store baseline for {stage_name}: {e}")
        raise


async def persist_current_metrics(
    db, stage_name: str, current_stats: dict, improvement_percentage: float, document_ids: list[str]
):
    """
    Persist current_* metrics and improvement_percentage to the latest baseline row.

    Args:
        db: Database adapter instance
        stage_name: Name of the stage
        current_stats: Current statistics dictionary
        improvement_percentage: Calculated improvement percentage
        document_ids: List of document UUIDs used for current run
    """
    query = """
        UPDATE krai_system.performance_baselines
        SET
            current_avg_seconds = $2,
            current_p50_seconds = $3,
            current_p95_seconds = $4,
            current_p99_seconds = $5,
            improvement_percentage = $6,
            test_document_ids = $7
        WHERE id = (
            SELECT id
            FROM krai_system.performance_baselines
            WHERE stage_name = $1
            ORDER BY measurement_date DESC
            LIMIT 1
        )
        RETURNING id
    """

    try:
        result = await db.execute(
            query,
            stage_name,
            current_stats["avg_seconds"],
            current_stats["p50_seconds"],
            current_stats["p95_seconds"],
            current_stats["p99_seconds"],
            improvement_percentage,
            document_ids,
        )

        if result:
            logger.debug(
                f"💾 Persisted current metrics for '{stage_name}': " f"improvement={improvement_percentage:+.1f}%"
            )

    except Exception as e:
        logger.error(f"❌ Failed to persist current metrics for {stage_name}: {e}")
        raise


async def compare_with_baseline(
    db, stage_name: str, current_stats: dict, document_ids: list[str] | None = None
) -> dict[str, Any]:
    """
    Compare current performance with stored baseline and persist current metrics.

    Args:
        db: Database adapter instance
        stage_name: Name of the stage
        current_stats: Current statistics dictionary
        document_ids: Optional list of document UUIDs used for current run

    Returns:
        Dictionary with comparison results including target_met flag
    """
    query = """
        SELECT * FROM krai_system.performance_baselines
        WHERE stage_name = $1
        ORDER BY measurement_date DESC
        LIMIT 1
    """

    try:
        baseline = await db.fetch_one(query, stage_name)

        if not baseline:
            logger.warning(f"⚠️  No baseline found for stage '{stage_name}'")
            return {
                "baseline_exists": False,
                "baseline_metrics": {},
                "current_metrics": current_stats,
                "improvements": {},
                "overall_status": "no_baseline",
                "target_met": False,
            }

        baseline_metrics = {
            "avg_seconds": float(baseline["baseline_avg_seconds"]),
            "p50_seconds": float(baseline["baseline_p50_seconds"]),
            "p95_seconds": float(baseline["baseline_p95_seconds"]),
            "p99_seconds": float(baseline["baseline_p99_seconds"]),
        }

        # Calculate improvement percentages (positive = improvement, negative = regression)
        improvements = {}
        for metric in ["avg_seconds", "p50_seconds", "p95_seconds", "p99_seconds"]:
            baseline_val = baseline_metrics[metric]
            current_val = current_stats[metric]

            if baseline_val > 0:
                improvement_pct = ((baseline_val - current_val) / baseline_val) * 100
                improvements[metric] = improvement_pct
            else:
                improvements[metric] = 0.0

        # Determine overall status
        avg_improvement = improvements["avg_seconds"]
        if avg_improvement > 5:
            overall_status = "improved"
        elif avg_improvement < -5:
            overall_status = "regressed"
        else:
            overall_status = "unchanged"

        # Check if 30% target is met
        target_met = avg_improvement >= 30.0

        logger.info(
            f"📊 Comparison for '{stage_name}': "
            f"avg {improvements['avg_seconds']:+.1f}%, "
            f"P50 {improvements['p50_seconds']:+.1f}%, "
            f"P95 {improvements['p95_seconds']:+.1f}%, "
            f"P99 {improvements['p99_seconds']:+.1f}%"
        )

        # Persist current metrics to database
        if document_ids:
            await persist_current_metrics(db, stage_name, current_stats, avg_improvement, document_ids)

        return {
            "baseline_exists": True,
            "baseline_metrics": baseline_metrics,
            "current_metrics": current_stats,
            "improvements": improvements,
            "overall_status": overall_status,
            "target_met": target_met,
        }

    except Exception as e:
        logger.error(f"❌ Failed to compare with baseline for {stage_name}: {e}")
        raise


async def run_benchmark(
    count: int,
    stage: str | None = None,
    output_file: Path | None = None,
    store_baseline_flag: bool = False,
    compare_baseline_flag: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Execute benchmark on selected documents.

    Args:
        count: Number of documents to benchmark
        stage: Optional specific stage to benchmark
        output_file: Path to save JSON report
        store_baseline_flag: Whether to store results as baseline
        compare_baseline_flag: Whether to compare with existing baseline
        verbose: Show detailed per-document timings

    Returns:
        Dictionary with benchmark results
    """
    db = None
    pipeline = None

    try:
        # Initialize database adapter
        logger.info("🔌 Connecting to database...")
        db = create_database_adapter()
        await db.connect()

        # Initialize pipeline
        logger.info("🚀 Initializing KRMasterPipeline...")
        pipeline = KRMasterPipeline(db_adapter=db)

        # Fetch benchmark documents
        documents = await get_benchmark_documents(db, count)

        # Initialize results structure
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "document_count": len(documents),
            "stage_filter": stage,
            "environment": {"BENCHMARK_MODE": "true", "DATABASE_HOST": db.config.get("host", "unknown")},
            "statistics": {},
            "comparison": {},
            "documents": [],
            "failures": [],
            "summary": {"total_duration_seconds": 0.0, "successful": 0, "failed": 0},
        }

        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 Starting benchmark: {len(documents)} documents")
        if stage:
            logger.info(f"📍 Stage filter: {stage}")
        logger.info(f"{'='*60}\n")

        benchmark_start = time.perf_counter()

        # Measure performance
        if stage:
            # Benchmark specific stage only
            for i, doc in enumerate(documents, 1):
                result = await measure_stage_performance(pipeline, doc, stage)

                if result["success"]:
                    results["documents"].append(result)
                    results["summary"]["successful"] += 1
                else:
                    results["failures"].append(result)
                    results["summary"]["failed"] += 1

            # Calculate statistics for the stage
            durations = [r["duration_seconds"] for r in results["documents"]]
            stage_stats = calculate_statistics(durations)
            results["statistics"][stage] = stage_stats

            # Store baseline if requested
            if store_baseline_flag and durations:
                doc_ids = [r["document_id"] for r in results["documents"]]
                await store_baseline(db, stage, stage_stats, doc_ids)

            # Compare with baseline if requested
            if compare_baseline_flag and durations:
                doc_ids = [r["document_id"] for r in results["documents"]]
                comparison = await compare_with_baseline(db, stage, stage_stats, doc_ids)
                results["comparison"][stage] = comparison

        else:
            # Benchmark full pipeline
            for i, doc in enumerate(documents, 1):
                result = await measure_pipeline_performance(pipeline, doc, i, len(documents))

                if result["success"]:
                    results["documents"].append(result)
                    results["summary"]["successful"] += 1
                else:
                    results["failures"].append(result)
                    results["summary"]["failed"] += 1

            # Calculate statistics for full pipeline
            full_durations = [r["total_duration_seconds"] for r in results["documents"]]
            full_stats = calculate_statistics(full_durations)
            results["statistics"]["full_pipeline"] = full_stats

            # Calculate statistics for each stage
            stage_durations = {}
            for doc_result in results["documents"]:
                for stage_name, duration in doc_result.get("stage_timings", {}).items():
                    if stage_name not in stage_durations:
                        stage_durations[stage_name] = []
                    stage_durations[stage_name].append(duration)

            results["statistics"]["stages"] = {}
            for stage_name, durations in stage_durations.items():
                results["statistics"]["stages"][stage_name] = calculate_statistics(durations)

            # Store baselines if requested
            if store_baseline_flag:
                doc_ids = [r["document_id"] for r in results["documents"]]

                # Store full pipeline baseline
                if full_durations:
                    await store_baseline(db, "full_pipeline", full_stats, doc_ids)

                # Store stage baselines
                for stage_name, stage_stats in results["statistics"]["stages"].items():
                    await store_baseline(db, stage_name, stage_stats, doc_ids)

            # Compare with baselines if requested
            if compare_baseline_flag:
                doc_ids = [r["document_id"] for r in results["documents"]]

                # Compare full pipeline
                if full_durations:
                    comparison = await compare_with_baseline(db, "full_pipeline", full_stats, doc_ids)
                    results["comparison"]["full_pipeline"] = comparison

                # Compare stages
                for stage_name, stage_stats in results["statistics"]["stages"].items():
                    comparison = await compare_with_baseline(db, stage_name, stage_stats, doc_ids)
                    results["comparison"][stage_name] = comparison

        benchmark_end = time.perf_counter()
        results["summary"]["total_duration_seconds"] = benchmark_end - benchmark_start

        # Validate 30% target if comparison was requested
        target_validation_failed = False
        if compare_baseline_flag and "full_pipeline" in results.get("comparison", {}):
            full_pipeline_comparison = results["comparison"]["full_pipeline"]

            if full_pipeline_comparison.get("baseline_exists"):
                target_met = full_pipeline_comparison.get("target_met", False)
                avg_improvement = full_pipeline_comparison["improvements"].get("avg_seconds", 0.0)

                logger.info("\n" + "=" * 60)
                logger.info("🎯 30% IMPROVEMENT TARGET VALIDATION")
                logger.info("=" * 60)

                if target_met:
                    logger.info(f"✅ PASS: Full pipeline improvement {avg_improvement:+.1f}% meets 30% target")
                    results["summary"]["target_validation"] = "PASS"
                else:
                    logger.error(f"❌ FAIL: Full pipeline improvement {avg_improvement:+.1f}% below 30% target")
                    logger.error(f"   Required: ≥30.0%, Actual: {avg_improvement:+.1f}%")
                    results["summary"]["target_validation"] = "FAIL"
                    target_validation_failed = True

                logger.info("=" * 60 + "\n")

        # Save report to file
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"💾 Report saved to: {output_file}")

        # Print formatted results
        print_benchmark_results(results, verbose)

        # Set flag for exit code handling
        results["target_validation_failed"] = target_validation_failed

        return results

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Benchmark interrupted by user")
        raise

    except Exception as e:
        logger.error(f"❌ Benchmark failed: {e}")
        raise

    finally:
        if db:
            await db.disconnect()
            logger.info("🔌 Database disconnected")


def print_benchmark_results(results: dict, verbose: bool = False):
    """
    Print formatted benchmark results to console.

    Args:
        results: Results dictionary
        verbose: Show detailed per-document timings
    """
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Print header
        console.print(f"\n{'='*80}", style="bold blue")
        console.print("📊 BENCHMARK RESULTS", style="bold blue", justify="center")
        console.print(f"{'='*80}", style="bold blue")

        # Print summary
        console.print(f"\n⏱️  Total Duration: {results['summary']['total_duration_seconds']:.2f}s", style="bold")
        console.print(f"📄 Documents: {results['document_count']}", style="bold")
        console.print(f"✅ Successful: {results['summary']['successful']}", style="green")
        console.print(
            f"❌ Failed: {results['summary']['failed']}", style="red" if results["summary"]["failed"] > 0 else "white"
        )

        # Print statistics table
        if "full_pipeline" in results["statistics"]:
            console.print("\n📊 Full Pipeline Statistics:", style="bold cyan")

            stats_table = Table(show_header=True, header_style="bold magenta")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value (s)", justify="right", style="yellow")

            stats = results["statistics"]["full_pipeline"]
            stats_table.add_row("Average", f"{stats['avg_seconds']:.2f}")
            stats_table.add_row("P50 (Median)", f"{stats['p50_seconds']:.2f}")
            stats_table.add_row("P95", f"{stats['p95_seconds']:.2f}")
            stats_table.add_row("P99", f"{stats['p99_seconds']:.2f}")
            stats_table.add_row("Min", f"{stats['min_seconds']:.2f}")
            stats_table.add_row("Max", f"{stats['max_seconds']:.2f}")
            stats_table.add_row("Std Dev", f"{stats['std_dev']:.2f}")

            console.print(stats_table)

        # Print stage statistics
        if "stages" in results["statistics"]:
            console.print("\n📊 Stage Statistics:", style="bold cyan")

            stage_table = Table(show_header=True, header_style="bold magenta")
            stage_table.add_column("Stage", style="cyan")
            stage_table.add_column("Avg (s)", justify="right")
            stage_table.add_column("P50 (s)", justify="right")
            stage_table.add_column("P95 (s)", justify="right")
            stage_table.add_column("P99 (s)", justify="right")

            for stage_name, stats in results["statistics"]["stages"].items():
                stage_table.add_row(
                    stage_name,
                    f"{stats['avg_seconds']:.2f}",
                    f"{stats['p50_seconds']:.2f}",
                    f"{stats['p95_seconds']:.2f}",
                    f"{stats['p99_seconds']:.2f}",
                )

            console.print(stage_table)

        # Print comparison results
        if results.get("comparison"):
            console.print("\n📈 Baseline Comparison:", style="bold cyan")

            comp_table = Table(show_header=True, header_style="bold magenta")
            comp_table.add_column("Stage", style="cyan")
            comp_table.add_column("Avg Δ%", justify="right")
            comp_table.add_column("P50 Δ%", justify="right")
            comp_table.add_column("P95 Δ%", justify="right")
            comp_table.add_column("P99 Δ%", justify="right")
            comp_table.add_column("Status", justify="center")

            for stage_name, comparison in results["comparison"].items():
                if not comparison.get("baseline_exists"):
                    continue

                improvements = comparison["improvements"]
                status = comparison["overall_status"]

                # Color code status
                if status == "improved":
                    status_str = "[green]✅ Improved[/green]"
                elif status == "regressed":
                    status_str = "[red]❌ Regressed[/red]"
                else:
                    status_str = "[yellow]➖ Unchanged[/yellow]"

                comp_table.add_row(
                    stage_name,
                    f"{improvements['avg_seconds']:+.1f}%",
                    f"{improvements['p50_seconds']:+.1f}%",
                    f"{improvements['p95_seconds']:+.1f}%",
                    f"{improvements['p99_seconds']:+.1f}%",
                    status_str,
                )

            console.print(comp_table)

        # Print detailed per-document timings if verbose
        if verbose and results["documents"]:
            console.print("\n📄 Per-Document Timings:", style="bold cyan")

            doc_table = Table(show_header=True, header_style="bold magenta")
            doc_table.add_column("Document", style="cyan", no_wrap=True)
            doc_table.add_column("Duration (s)", justify="right")
            doc_table.add_column("Status", justify="center")

            for doc in results["documents"]:
                status = "[green]✅[/green]" if doc["success"] else "[red]❌[/red]"
                duration = doc.get("total_duration_seconds") or doc.get("duration_seconds", 0)

                doc_table.add_row(doc["filename"][:50], f"{duration:.2f}", status)

            console.print(doc_table)

        console.print(f"\n{'='*80}", style="bold blue")

    except ImportError:
        # Fallback to simple print if rich is not available
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        print(f"\nTotal Duration: {results['summary']['total_duration_seconds']:.2f}s")
        print(f"Documents: {results['document_count']}")
        print(f"Successful: {results['summary']['successful']}")
        print(f"Failed: {results['summary']['failed']}")

        if "full_pipeline" in results["statistics"]:
            stats = results["statistics"]["full_pipeline"]
            print("\nFull Pipeline Statistics:")
            print(f"  Average: {stats['avg_seconds']:.2f}s")
            print(f"  P50: {stats['p50_seconds']:.2f}s")
            print(f"  P95: {stats['p95_seconds']:.2f}s")
            print(f"  P99: {stats['p99_seconds']:.2f}s")

        print("\n" + "=" * 80)


def main():
    """Main entry point for benchmark script."""
    parser = argparse.ArgumentParser(
        description="Run KRAI pipeline performance benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmark on 10 documents and store as baseline
  python scripts/run_benchmark.py --count 10 --baseline

  # Run benchmark and compare with baseline
  python scripts/run_benchmark.py --count 10 --compare

  # Benchmark specific stage only
  python scripts/run_benchmark.py --stage embedding --count 10

  # Verbose output with per-document timings
  python scripts/run_benchmark.py --count 10 --verbose
        """,
    )

    parser.add_argument("--count", type=int, default=10, help="Number of documents to benchmark (default: 10)")

    parser.add_argument(
        "--stage", type=str, default=None, help="Specific stage to benchmark (optional, default: all stages)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./benchmark_results.json"),
        help="Output report file path (default: ./benchmark_results.json)",
    )

    parser.add_argument("--baseline", action="store_true", help="Store results as baseline (default: False)")

    parser.add_argument("--compare", action="store_true", help="Compare against existing baseline (default: False)")

    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed timing for each document (default: False)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.count <= 0:
        logger.error("❌ Count must be greater than 0")
        return 1

    if args.output.exists() and not args.output.is_file():
        logger.error(f"❌ Output path exists but is not a file: {args.output}")
        return 1

    try:
        # Load environment variables
        load_env()

        # Log configuration
        logger.info("🔧 Benchmark Configuration:")
        logger.info(f"  Document count: {args.count}")
        logger.info(f"  Stage filter: {args.stage or 'all stages'}")
        logger.info(f"  Output file: {args.output}")
        logger.info(f"  Store baseline: {args.baseline}")
        logger.info(f"  Compare baseline: {args.compare}")
        logger.info(f"  Verbose: {args.verbose}")

        # Run benchmark
        results = asyncio.run(
            run_benchmark(
                count=args.count,
                stage=args.stage,
                output_file=args.output,
                store_baseline_flag=args.baseline,
                compare_baseline_flag=args.compare,
                verbose=args.verbose,
            )
        )

        # Check if target validation failed
        if results.get("target_validation_failed", False):
            logger.error("\n❌ Benchmark completed but 30% improvement target was not met")
            return 1

        logger.info("\n✅ Benchmark completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Benchmark interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
