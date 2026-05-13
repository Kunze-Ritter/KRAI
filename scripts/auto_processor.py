"""Auto Processor

Automatically processes PDFs from input_pdfs/ folder using KRMasterPipeline with stage-based processing.
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.processors.__version__ import __commit__, __date__, __version__
from backend.processors.logger import get_logger

logger = get_logger()

# Show version banner
logger.info("=" * 80)
logger.info(f"  KRAI AUTO PROCESSOR v{__version__}")
logger.info(f"  Build: {__commit__} | Date: {__date__}")
logger.info("=" * 80)
logger.info("")


class AutoProcessor:
    """Automatically process PDFs with complete pipeline"""

    def __init__(
        self,
        input_dir: str = "input_pdfs",
        processed_dir: str = "processed_pdfs",
        move_processed: bool = True,
    ):
        """Initialize auto processor"""
        self.logger = get_logger()

        # Check Ollama before starting
        self._check_ollama()

        # Convert to absolute paths relative to project root
        project_root = Path(__file__).parent.parent.parent
        self.input_dir = project_root / input_dir if not Path(input_dir).is_absolute() else Path(input_dir)
        self.processed_dir = (
            project_root / processed_dir if not Path(processed_dir).is_absolute() else Path(processed_dir)
        )

        self.logger.info(f"Input directory: {self.input_dir}")
        self.logger.info(f"Processed directory: {self.processed_dir}")

        self.pipeline = KRMasterPipeline()
        self.move_processed = move_processed

        # Create directories if they don't exist
        self.input_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)

    async def initialize(self) -> None:
        """Initialize async pipeline services."""
        await self.pipeline.initialize_services()

    def _check_ollama(self):
        """Check if Ollama is running and try to start if not"""
        from utils.ollama_checker import ensure_ollama_running, get_ollama_models

        self.logger.info("=" * 80)
        self.logger.info("CHECKING OLLAMA...")
        self.logger.info("=" * 80)

        is_running, message = ensure_ollama_running(auto_start=True)

        if is_running:
            self.logger.info(message)

            # Show available models
            models = get_ollama_models()
            if models:
                self.logger.info(f"Available models: {', '.join(models[:5])}")
                if len(models) > 5:
                    self.logger.info(f"   ... and {len(models) - 5} more")
            else:
                self.logger.warning("No models found. Install with: ollama pull llama3.2")
        else:
            self.logger.error(message)
            self.logger.warning("⚠️ Processing will continue but LLM features will be disabled!")
            self.logger.warning("   Install Ollama: https://ollama.ai")

            # Wait for user to see the message
            import time

            time.sleep(2)

        self.logger.info("")

    async def process_all_pdfs(self) -> dict:
        """
        Process all PDFs in input_pdfs/ folder

        Returns:
            Dict with statistics
        """
        self.logger.info("=" * 80)
        self.logger.info("AUTO PROCESSOR - PROCESSING ALL PDFs")
        self.logger.info("=" * 80)

        stats = {
            "pdfs_found": 0,
            "pdfs_processed": 0,
            "pdfs_failed": 0,
            "total_parts_found": 0,
            "total_series_created": 0,
        }

        # Find all PDFs (including .pdfz compressed)
        pdf_files = list(self.input_dir.rglob("*.pdf")) + list(self.input_dir.rglob("*.pdfz"))
        stats["pdfs_found"] = len(pdf_files)

        if not pdf_files:
            self.logger.warning(f"No PDFs found in {self.input_dir}")
            return stats

        self.logger.info(f"Found {len(pdf_files)} PDFs to process")
        self.logger.info("")

        for pdf_path in pdf_files:
            self.logger.info("=" * 80)
            self.logger.info(f"PROCESSING: {pdf_path.name}")
            self.logger.info("=" * 80)

            try:
                result = await self.process_single_pdf(pdf_path)

                if result["success"]:
                    stats["pdfs_processed"] += 1
                    stats["total_parts_found"] += result.get("parts_found", 0)
                    stats["total_series_created"] += result.get("series_created", 0)

                    if self.move_processed:
                        # Move to processed folder
                        self._move_to_processed(pdf_path)
                else:
                    stats["pdfs_failed"] += 1
                    self.logger.error(f"Failed: {result.get('error')}")

            except Exception as e:
                stats["pdfs_failed"] += 1
                self.logger.error(f"Error processing {pdf_path.name}: {e}")

            self.logger.info("")

        # Final summary
        self.logger.info("=" * 80)
        self.logger.info("AUTO PROCESSOR COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"PDFs found: {stats['pdfs_found']}")
        self.logger.info(f"PDFs processed: {stats['pdfs_processed']}")
        self.logger.info(f"PDFs failed: {stats['pdfs_failed']}")
        self.logger.info(f"Total parts found: {stats['total_parts_found']}")
        self.logger.info(f"Total series created: {stats['total_series_created']}")

        return stats

    async def process_single_pdf(self, pdf_path: Path) -> dict:
        """
        Process single PDF with complete pipeline

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with result
        """
        try:
            full_result = await self.pipeline.process_single_document_full_pipeline(
                str(pdf_path),
                1,
                1,
            )

            result = {
                "success": bool(full_result.get("success")),
                "document_id": full_result.get("document_id"),
                "parts_found": int(full_result.get("parts_found", 0) or 0),
                "series_created": int(full_result.get("series_created", 0) or 0),
            }
            if not result["success"]:
                result["error"] = full_result.get("error", "Unknown error")
            return result
        except Exception as e:
            self.logger.error(f"Error in process_single_pdf: {e}")
            return {
                "success": False,
                "document_id": None,
                "parts_found": 0,
                "series_created": 0,
                "error": str(e),
            }

    def _enrich_videos_background(self):
        """Enrich videos in background (non-blocking)"""
        import subprocess
        import sys

        try:
            # Get path to video enrichment script (in project root/scripts)
            script_path = Path(__file__).parent.parent.parent / "scripts" / "enrich_video_metadata.py"

            if not script_path.exists():
                self.logger.warning("Video enrichment script not found")
                return

            # Start enrichment in background
            self.logger.info("🎬 Starting video enrichment in background...")

            # Run in background (non-blocking)
            subprocess.Popen(
                [sys.executable, str(script_path), "--limit", "10"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self.logger.info("✅ Video enrichment started in background")

        except Exception as e:
            self.logger.warning(f"Could not start video enrichment: {e}")

    def _move_to_processed(self, pdf_path: Path):
        """Move PDF to processed folder"""
        try:
            dest_path = self.processed_dir / pdf_path.name

            # If file exists in processed, add timestamp
            if dest_path.exists():
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = self.processed_dir / f"{pdf_path.stem}_{timestamp}.pdf"

            shutil.move(str(pdf_path), str(dest_path))
            self.logger.info(f"✅ Moved to: {dest_path}")

            # Also move log file if exists
            log_file = pdf_path.parent / f"{pdf_path.stem}.log.txt"
            if log_file.exists():
                log_dest = self.processed_dir / f"{pdf_path.stem}.log.txt"
                shutil.move(str(log_file), str(log_dest))

        except Exception as e:
            self.logger.warning(f"Could not move file: {e}")


async def main():
    """Run auto processor"""
    parser = argparse.ArgumentParser(description="Auto-process PDFs with KRMasterPipeline")
    parser.add_argument("--input-dir", default="input_pdfs", help="Directory containing PDFs")
    parser.add_argument("--processed-dir", default="processed_pdfs", help="Directory for processed PDFs")
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="Do not move successfully processed PDFs out of input directory",
    )
    args = parser.parse_args()

    processor = AutoProcessor(
        input_dir=args.input_dir,
        processed_dir=args.processed_dir,
        move_processed=not args.no_move,
    )
    await processor.initialize()
    stats = await processor.process_all_pdfs()

    print("\n" + "=" * 80)
    print("FINAL STATISTICS")
    print("=" * 80)
    print(f"PDFs processed: {stats['pdfs_processed']}/{stats['pdfs_found']}")
    print(f"PDFs failed: {stats['pdfs_failed']}")
    print(f"Total parts found: {stats['total_parts_found']}")
    print(f"Total series created: {stats['total_series_created']}")


if __name__ == "__main__":
    asyncio.run(main())
