#!/usr/bin/env python3
"""
Pipeline Processor CLI

Command-line interface for executing individual pipeline stages and managing document processing.
"""

# ruff: noqa: E402  # backend imports follow sys.path.insert below

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.base_processor import ProcessingContext, Stage
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.processors.upload_processor import UploadProcessor
from backend.services.postgresql_adapter import PostgreSQLAdapter


def parse_stage_input(stage_input: str) -> Stage:
    """Parse stage input from command line"""
    # Try to parse as number first
    try:
        stage_num = int(stage_input)
        stage_mapping = {
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
        if stage_num in stage_mapping:
            return stage_mapping[stage_num]
        raise ValueError(f"Invalid stage number: {stage_num}")
    except ValueError:
        # Try to parse as name
        try:
            return Stage(stage_input.lower())
        except ValueError:
            raise ValueError(f"Invalid stage: {stage_input}")


async def list_stages(pipeline: KRMasterPipeline):
    """List all available stages"""
    stages = pipeline.get_available_stages()
    print("\nAvailable Pipeline Stages:")
    print("=" * 50)
    for i, stage in enumerate(stages, 1):
        print(f"  {i:2d}. {stage}")
    print("=" * 50)
    print(f"Total: {len(stages)} stages")


async def show_status(pipeline: KRMasterPipeline, document_id: str):
    """Show current stage status for a document"""
    status = await pipeline.get_stage_status(document_id)

    if not status["found"]:
        print(f"\n❌ Document not found: {document_id}")
        if "error" in status:
            print(f"   Error: {status['error']}")
        return

    print(f"\n📄 Document Status: {document_id}")
    print("=" * 50)

    stage_status = status.get("stage_status", {})
    if stage_status:
        for stage_name, stage_info in stage_status.items():
            status_icon = {"pending": "⏳", "processing": "🔄", "completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(
                stage_info.get("status"), "❓"
            )

            print(f"  {status_icon} {stage_name}: {stage_info.get('status', 'unknown')}")

            if stage_info.get("metadata"):
                metadata = stage_info["metadata"]
                if "progress" in metadata:
                    print(f"     Progress: {metadata['progress']}%")
                if "error" in metadata:
                    print(f"     Error: {metadata['error']}")
    else:
        print("  No stage status available")
    print("=" * 50)


async def run_single_stage(pipeline: KRMasterPipeline, document_id: str, stage_input: str):
    """Run a single stage for a document"""
    try:
        stage = parse_stage_input(stage_input)
        print(f"\n🔄 Running stage: {stage.value} for document: {document_id}")
        print("=" * 50)

        result = await pipeline.run_single_stage(document_id, stage)

        if result["success"]:
            print("✅ Stage completed successfully!")
            if result.get("data"):
                print("\nResult Data:")
                for key, value in result["data"].items():
                    if isinstance(value, int | float | str | bool):
                        print(f"  {key}: {value}")
                    elif isinstance(value, dict | list):
                        print(f"  {key}: {len(value)} items")
                    else:
                        print(f"  {key}: {type(value).__name__}")
        else:
            print("❌ Stage failed!")
            if "error" in result:
                print(f"Error: {result['error']}")

        print("=" * 50)

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("Use --list-stages to see available stages")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


async def run_multiple_stages(pipeline: KRMasterPipeline, document_id: str, stage_inputs: list[str]):
    """Run multiple stages for a document"""
    try:
        stages = [parse_stage_input(s) for s in stage_inputs]
        print(f"\n🔄 Running {len(stages)} stages for document: {document_id}")
        print(f"Stages: {', '.join([s.value for s in stages])}")
        print("=" * 50)

        result = await pipeline.run_stages(document_id, stages)

        print("\n📊 Results Summary:")
        print(f"  Total stages: {result['total_stages']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Success rate: {result['success_rate']:.1f}%")

        print("\n📋 Stage Details:")
        for i, stage_result in enumerate(result["stage_results"], 1):
            stage_name = stage_result.get("stage", "unknown")
            status_icon = "✅" if stage_result["success"] else "❌"
            print(f"  {i}. {status_icon} {stage_name}")

            if not stage_result["success"] and "error" in stage_result:
                print(f"     Error: {stage_result['error']}")

        print("=" * 50)

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("Use --list-stages to see available stages")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


async def run_smart_processing(pipeline: KRMasterPipeline, document_id: str, file_path: str | None = None):
    """Run smart processing (determine which stages to run based on current status)"""
    print(f"\n🧠 Running smart processing for document: {document_id}")
    print("=" * 50)

    # Get current status
    status = await pipeline.get_stage_status(document_id)

    if not status["found"]:
        print(f"❌ Document not found: {document_id}")
        return

    # Determine which stages need to run
    stage_status = status.get("stage_status", {})
    stages_to_run = []

    all_stages = list(Stage)
    for stage in all_stages:
        stage_info = stage_status.get(stage.value, {})
        current_status = stage_info.get("status", "pending")

        if current_status in ["pending", "failed"]:
            stages_to_run.append(stage)
        elif current_status == "processing":
            print(f"⚠️  Stage {stage.value} is currently processing, skipping...")

    if not stages_to_run:
        print("✅ All stages are already completed!")
        return

    print(f"📋 Stages to run: {len(stages_to_run)}")
    for stage in stages_to_run:
        print(f"  - {stage.value}")

    print("\n🔄 Starting smart processing...")

    # Run the stages
    result = await pipeline.run_stages(document_id, stages_to_run)

    print("\n📊 Smart Processing Results:")
    print(f"  Stages attempted: {result['total_stages']}")
    print(f"  Successful: {result['successful']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Success rate: {result['success_rate']:.1f}%")

    print("=" * 50)


async def upload_file(pipeline: KRMasterPipeline, file_path: str, document_type: str = "service_manual") -> str:
    """Upload a file and return the document ID"""
    print(f"\n📤 Uploading file: {file_path}")
    print("=" * 50)

    try:
        # Initialize database adapter
        database_adapter = pipeline.database_service.adapter if hasattr(pipeline.database_service, "adapter") else None
        if not database_adapter:
            # Try to create adapter from environment
            import os

            from dotenv import load_dotenv

            load_dotenv()

            postgres_url = os.getenv("POSTGRES_URL")
            if not postgres_url:
                print("❌ Error: POSTGRES_URL not configured")
                sys.exit(1)

            database_adapter = PostgreSQLAdapter(postgres_url)
            await database_adapter.initialize()

        # Create upload processor
        upload_processor = UploadProcessor(database_adapter)

        # Create processing context
        context = ProcessingContext(document_id=str(uuid4()), file_path=file_path, document_type=document_type)

        # Process upload
        result = await upload_processor.process(context)

        if result.success:
            # document_id lives in result.data or result.metadata, not as a direct attribute
            document_id = (result.data.get("document_id") if result.data else None) or (
                result.metadata.get("document_id") if result.metadata else None
            )
            if not document_id:
                print("❌ Upload succeeded but no document_id returned")
                print(f"   data={result.data}")
                sys.exit(1)
            print("✅ File uploaded successfully!")
            print(f"   Document ID: {document_id}")
            print(f"   Document Type: {document_type}")
            print("=" * 50)
            return document_id
        error_msg = result.error.message if result.error else "Unknown upload error"
        print(f"❌ Upload failed: {error_msg}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Upload error: {e}")
        sys.exit(1)


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="KRAI Pipeline Processor CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available stages
  python pipeline_processor.py --list-stages

  # Upload a file (upload-first flow)
  python pipeline_processor.py --file-path /path/to/file.pdf --stage upload
  python pipeline_processor.py --file-path /path/to/file.pdf --stage 1 --document-type service_manual

  # Run a single stage (requires existing document ID)
  python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stage 5

  # Run multiple stages
  python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --stages 1,2,3

  # Run all stages
  python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --all

  # Show document status
  python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --status

  # Smart processing (run only needed stages)
  python pipeline_processor.py --document-id 123e4567-e89b-12d3-a456-426614174000 --smart
        """,
    )

    parser.add_argument("--document-id", "-d", type=str, help="Document ID (UUID)")

    parser.add_argument("--file-path", "-f", type=str, help="File path (for upload stage)")

    parser.add_argument(
        "--document-type",
        "-t",
        type=str,
        default="service_manual",
        help="Document type for upload (default: service_manual)",
    )

    parser.add_argument("--stage", "-s", type=str, help="Single stage to run (number 1-15 or stage name)")

    parser.add_argument("--stages", type=str, help="Multiple stages to run (comma-separated numbers or names)")

    parser.add_argument("--all", "-a", action="store_true", help="Run all stages")

    parser.add_argument("--list-stages", "-l", action="store_true", help="List all available stages")

    parser.add_argument("--status", action="store_true", help="Show current stage status for document")

    parser.add_argument("--smart", action="store_true", help="Run smart processing (only needed stages)")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.add_argument("--production-test", action="store_true", help="Run production pipeline test with HP E877 PDFs")

    parser.add_argument(
        "--validate-dashboard",
        action="store_true",
        help="Run dashboard validation after production test (Playwright required)",
    )

    parser.add_argument(
        "--thresholds",
        type=str,
        default="config/production_test_thresholds.json",
        help="Path to threshold configuration JSON file",
    )

    parser.add_argument("--min-chunks", type=int, help="Override min chunks threshold")

    parser.add_argument("--min-images", type=int, help="Override min images threshold")

    parser.add_argument("--min-error-codes", type=int, help="Override min error codes threshold")

    parser.add_argument("--min-embedding-coverage", type=float, help="Override min embedding coverage (0.0-1.0)")

    parser.add_argument(
        "--output-dir", type=str, help="Output directory for test results (auto-detected if not specified)"
    )

    parser.add_argument(
        "--pdf-dir", type=str, help="Directory containing HP E877 PDFs (auto-detected if not specified)"
    )

    args = parser.parse_args()

    # Initialize pipeline with database adapter
    from backend.services.database_factory import create_database_adapter

    database_adapter = create_database_adapter()
    await database_adapter.initialize()

    pipeline = KRMasterPipeline(database_adapter=database_adapter)
    await pipeline.initialize_services()

    # Handle production test mode
    if args.production_test:
        from scripts.production_test import ProductionTestOrchestrator

        # Build threshold overrides from CLI arguments
        threshold_overrides = {}
        if args.min_chunks is not None:
            threshold_overrides["min_chunks"] = args.min_chunks
        if args.min_images is not None:
            threshold_overrides["min_images"] = args.min_images
        if args.min_error_codes is not None:
            threshold_overrides["min_error_codes"] = args.min_error_codes
        if args.min_embedding_coverage is not None:
            threshold_overrides["min_embedding_coverage"] = args.min_embedding_coverage

        # Create orchestrator
        orchestrator = ProductionTestOrchestrator(
            pipeline=pipeline,
            thresholds_path=args.thresholds,
            threshold_overrides=threshold_overrides,
            output_dir=args.output_dir,
            pdf_dir=args.pdf_dir,
            validate_dashboard=args.validate_dashboard,
        )

        # Run test and exit with appropriate code
        exit_code = await orchestrator.run()
        sys.exit(exit_code)

    try:
        # Handle upload-first flow
        if args.stage and not args.document_id and args.file_path:
            # Check if stage is upload stage
            try:
                stage = parse_stage_input(args.stage)
                if stage == Stage.UPLOAD:
                    # Upload-first flow
                    document_id = await upload_file(pipeline, args.file_path, args.document_type)
                    print(f"\n🎯 Upload completed! Document ID: {document_id}")
                    print("You can now use this document ID for other stages:")
                    print(f"  python pipeline_processor.py --document-id {document_id} --status")
                    print(f"  python pipeline_processor.py --document-id {document_id} --stages 2,3,4")
                    return
                print("❌ Error: --file-path requires --stage upload or --stage 1")
                print(f"   You requested stage: {stage.value}")
                sys.exit(1)
            except ValueError as e:
                print(f"❌ Error: {e}")
                sys.exit(1)

        # Handle different commands
        if args.list_stages:
            await list_stages(pipeline)

        elif args.status:
            if not args.document_id:
                print("❌ Error: --document-id is required for --status")
                sys.exit(1)
            await show_status(pipeline, args.document_id)

        elif args.stage:
            if not args.document_id:
                print("❌ Error: --document-id is required for --stage (unless using --file-path with upload stage)")
                sys.exit(1)
            await run_single_stage(pipeline, args.document_id, args.stage)

        elif args.stages:
            if not args.document_id:
                print("❌ Error: --document-id is required for --stages")
                sys.exit(1)
            stage_inputs = [s.strip() for s in args.stages.split(",")]
            await run_multiple_stages(pipeline, args.document_id, stage_inputs)

        elif args.all:
            if not args.document_id:
                print("❌ Error: --document-id is required for --all")
                sys.exit(1)
            all_stages = list(Stage)
            await run_multiple_stages(pipeline, args.document_id, [s.value for s in all_stages])

        elif args.smart:
            if not args.document_id:
                print("❌ Error: --document-id is required for --smart")
                sys.exit(1)
            await run_smart_processing(pipeline, args.document_id, args.file_path)

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
