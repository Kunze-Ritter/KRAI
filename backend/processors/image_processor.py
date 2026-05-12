"""
Image Processor - Extract and analyze images from PDFs

Stage 3 of the processing pipeline.

ARCHITECTURE (Refactored 2026-03-05):
- image_config.py: Configuration, session, vision guards, preprocessing
- image_processor.py: Main facade (this file)

Features:
- Extract images from PDFs (PyMuPDF)
- Filter relevant images (skip logos, headers, etc.)
- OCR for text in images (Tesseract)
- Vision AI analysis (LLaVA via Ollama)
- Image classification (diagram, table, photo, etc.)
- Integration with Image Storage Processor
"""

import base64
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import statistics
import sys
import tempfile
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

import fitz  # PyMuPDF
import requests
from PIL import Image, ImageOps
from requests import exceptions as requests_exceptions
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingResult, Stage
from backend.pipeline.metrics import metrics
from backend.processors.logger import sanitize_document_name, text_stats
from backend.services.context_extraction_service import ContextExtractionService

from .stage_tracker import StageTracker


def _raster_to_jpeg(image_bytes: bytes, original_ext: str, quality: int = 85) -> tuple[bytes, str]:
    """Convert raster image bytes to JPEG with a white background.

    JPEG images are returned unchanged. Unrecognised formats are also returned
    unchanged (with the original extension) so the pipeline can still store them.
    """
    is_jpeg = image_bytes[:2] == b"\xff\xd8"
    if is_jpeg:
        return image_bytes, "jpg"

    is_raster = image_bytes[:4] in (b"\x89PNG", b"GIF8", b"RIFF") or original_ext.lower() in (
        "png",
        "gif",
        "webp",
        "bmp",
        "tiff",
        "tif",
    )
    if not is_raster:
        return image_bytes, original_ext

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "jpg"
    except Exception:
        return image_bytes, original_ext


class ImageProcessor(BaseProcessor):
    """
    Stage 3: Image Processor

    Extracts and analyzes images from service manuals.
    """

    def __init__(
        self,
        database_service=None,
        storage_service=None,
        ai_service=None,
        min_image_size: int = 10000,  # Min 100x100px
        max_images_per_doc: int = 999999,  # Unlimited (user will check manually)
        enable_ocr: bool = True,
        enable_vision: bool = True,
    ):
        """
        Initialize image processor

        Args:
            database_service: Database adapter/service for stage tracking
            min_image_size: Minimum image size in pixels (width * height)
            max_images_per_doc: Maximum images to extract per document (default: unlimited)
            enable_ocr: Enable OCR with Tesseract
            enable_vision: Enable Vision AI with LLaVA
        """
        super().__init__(name="image_processor")
        self.stage = Stage.IMAGE_PROCESSING
        self.min_image_size = min_image_size
        self.max_images_per_doc = max_images_per_doc
        self.enable_ocr = enable_ocr
        self.enable_vision = enable_vision
        self.storage_service = storage_service
        self.ai_service = ai_service
        self.database_service = database_service
        self.cleanup_temp_images = os.getenv("IMAGE_PROCESSOR_CLEANUP", "1") != "0"

        # Stage tracker
        if self.database_service:
            self.stage_tracker = StageTracker(self.database_service)
        else:
            self.stage_tracker = None

        # HTTP session configuration
        self.request_timeout = float(os.getenv("VISION_REQUEST_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("VISION_REQUEST_MAX_RETRIES", "4"))
        self.retry_base_delay = float(os.getenv("VISION_RETRY_BASE_DELAY", "1.5"))
        self.retry_jitter = float(os.getenv("VISION_RETRY_JITTER", "0.5"))
        self.session = self._create_session()

        # OCR threading configuration
        cpu_count = os.cpu_count() or 4
        max_workers_config = int(os.getenv("OCR_MAX_WORKERS", max(1, cpu_count // 2)))
        self.ocr_executor = ThreadPoolExecutor(max_workers=max_workers_config)
        self.ocr_latency_window: deque[float] = deque(maxlen=200)

        # Preprocessing configuration
        self.preprocess_enabled = os.getenv("OCR_PREPROCESSING_ENABLED", "1") != "0"
        self.preprocess_grayscale = os.getenv("OCR_PREPROCESS_GRAYSCALE", "1") != "0"
        self.preprocess_binarize = os.getenv("OCR_PREPROCESS_BINARIZE", "1") != "0"
        self.preprocess_upscale = int(os.getenv("OCR_PREPROCESS_UPSCALE", "1"))  # scale factor

        # Vision guardrails
        self.max_image_mb = float(os.getenv("VISION_MAX_IMAGE_MB", "12.0"))
        self.max_images_per_document = int(os.getenv("VISION_MAX_IMAGES_PER_DOCUMENT", "80"))
        self.circuit_breaker_threshold = int(os.getenv("VISION_FAILURE_THRESHOLD", "5"))
        self.circuit_breaker_timeout = float(os.getenv("VISION_BREAKER_TIMEOUT", "120"))
        self._vision_failure_count = 0
        self._vision_breaker_until: float | None = None
        self.global_vision_limit = int(os.getenv("VISION_GLOBAL_LIMIT", "500"))
        self.global_vision_window = float(os.getenv("VISION_GLOBAL_WINDOW_SECONDS", "3600"))
        self._vision_usage: deque[float] = deque()
        self._vision_model_cache: str | None = None
        self._vision_model_checked_at: float = 0.0
        self.vision_model_cache_ttl = float(os.getenv("VISION_MODEL_CACHE_TTL_SECONDS", "300"))

        # Check OCR availability
        if self.enable_ocr:
            try:
                import pytesseract

                # Configure Tesseract path (Windows) - BEFORE testing version
                if sys.platform == "win32":
                    possible_paths = [
                        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
                    ]

                    # Try to find Tesseract
                    for path in possible_paths:
                        if os.path.exists(path):
                            pytesseract.pytesseract.tesseract_cmd = path
                            self.logger.debug(f"Configured Tesseract: {path}")
                            break

                # Test if Tesseract binary is actually installed
                version = pytesseract.get_tesseract_version()
                self.ocr_available = True
                self.logger.info(f"✅ OCR (Tesseract) available - v{version}")
            except ImportError:
                self.ocr_available = False
                self.logger.warning("⚠️  pytesseract not installed - run: pip install pytesseract")
            except Exception as e:
                self.ocr_available = False
                self.logger.warning(f"⚠️  Tesseract OCR not available: {e}")
                self.logger.info("   Install Tesseract OCR:")
                self.logger.info("   • Windows: https://github.com/UB-Mannheim/tesseract/wiki")
                self.logger.info("   • Linux: sudo apt install tesseract-ocr")
                self.logger.info("   • macOS: brew install tesseract")
        else:
            self.ocr_available = False

        # Check Vision AI availability
        if self.enable_vision:
            self.vision_available = self._check_vision_availability()
        else:
            self.vision_available = False

        # Context extraction configuration
        self.context_service = ContextExtractionService()
        self.enable_context_extraction = os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() == "true"
        self.logger.info(f"Context extraction enabled: {self.enable_context_extraction}")

    def close(self) -> None:
        """Cleanup resources - call when processor is no longer needed."""
        if hasattr(self, "ocr_executor") and self.ocr_executor:
            self.ocr_executor.shutdown(wait=True)
            self.ocr_executor = None
        if hasattr(self, "session") and self.session:
            self.session.close()
            self.session = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        with contextlib.suppress(Exception):
            self.close()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        adapter_retries = max(0, self.max_retries - 1)
        retry = Retry(
            total=adapter_retries,
            read=adapter_retries,
            connect=adapter_retries,
            backoff_factor=self.retry_base_delay,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=int(os.getenv("VISION_HTTP_POOL_CONNECTIONS", "10")),
            pool_maxsize=int(os.getenv("VISION_HTTP_POOL_MAXSIZE", "20")),
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _apply_preprocessing(self, pil_image: Image.Image) -> Image.Image:
        if not self.preprocess_enabled:
            return pil_image

        processed = pil_image
        if self.preprocess_grayscale:
            processed = ImageOps.grayscale(processed)

        if self.preprocess_upscale > 1:
            new_size = (
                max(1, processed.width * self.preprocess_upscale),
                max(1, processed.height * self.preprocess_upscale),
            )
            processed = processed.resize(new_size, Image.BICUBIC)

        if self.preprocess_binarize:
            processed = processed.convert("L")
            processed = processed.point(lambda x: 255 if x > 180 else 0, "1")

        return processed

    def _vision_guard_allows(self, image: dict[str, Any], processed_count: int) -> bool:
        if processed_count >= self.max_images_per_document:
            self.logger.info(
                "Vision guardrails dropping %s - document limit %d reached",
                image["filename"],
                self.max_images_per_document,
            )
            return False

        size_mb = image.get("size_bytes", 0) / (1024 * 1024)
        if size_mb > self.max_image_mb:
            self.logger.warning(
                "Vision guardrails dropping %s - size %.2fMB exceeds cap %.2fMB",
                image["filename"],
                size_mb,
                self.max_image_mb,
            )
            return False

        if self._vision_breaker_until and time.time() < self._vision_breaker_until:
            self.logger.warning(
                "Vision circuit breaker open (until %.0f) - skipping %s",
                self._vision_breaker_until,
                image["filename"],
            )
            return False

        return True

    def _record_ocr_latency(self, latency: float) -> None:
        self.ocr_latency_window.append(latency)
        while len(self.ocr_latency_window) > self.ocr_latency_window.maxlen:
            self.ocr_latency_window.popleft()

    @staticmethod
    def _calculate_percentiles(samples: list[float]) -> tuple[float, float]:
        if len(samples) < 5:
            return 0.0, 0.0
        try:
            p95 = statistics.quantiles(samples, n=100)[94]
            p99 = statistics.quantiles(samples, n=100)[98]
            return p95, p99
        except Exception:
            return 0.0, 0.0

    def _vision_quota_allows(self) -> bool:
        now = time.time()
        while self._vision_usage and (now - self._vision_usage[0]) > self.global_vision_window:
            self._vision_usage.popleft()
        allowed = len(self._vision_usage) < self.global_vision_limit
        if not allowed:
            self.logger.warning(
                "Vision guardrails global limit reached (%d in %.0fs window)",
                self.global_vision_limit,
                self.global_vision_window,
            )
        return allowed

    def _record_vision_usage(self) -> None:
        now = time.time()
        self._vision_usage.append(now)

    def _reset_vision_failures(self) -> None:
        if self._vision_failure_count:
            self.logger.debug("Vision circuit breaker reset after successful request")
        self._vision_failure_count = 0
        self._vision_breaker_until = None

    def _record_vision_failure(self, reason: str) -> None:
        self._vision_failure_count += 1
        self.logger.warning(
            "Vision request failed (%s) - failure count %d/%d",
            reason,
            self._vision_failure_count,
            self.circuit_breaker_threshold,
        )
        if self._vision_failure_count >= self.circuit_breaker_threshold:
            self._vision_breaker_until = time.time() + self.circuit_breaker_timeout
            self.logger.error(
                "Vision circuit breaker OPEN for %.0fs after %d consecutive failures",
                self.circuit_breaker_timeout,
                self._vision_failure_count,
            )

    def _get_vision_model_name(self) -> str | None:
        now = time.time()
        if self._vision_model_cache and (now - self._vision_model_checked_at) < self.vision_model_cache_ttl:
            return self._vision_model_cache

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        try:
            parsed = urlparse(ollama_url)
            running_in_docker = os.path.exists("/.dockerenv") or os.getenv("KRAI_IN_DOCKER") == "1"
            if parsed.hostname in ("krai-ollama", "ollama") and not running_in_docker:
                port_str = f":{parsed.port}" if parsed.port else ""
                netloc = f"127.0.0.1{port_str}"
                ollama_url = urlunparse(parsed._replace(netloc=netloc))
        except Exception:
            pass

        try:
            response = self.session.get(
                f"{ollama_url}/api/tags",
                timeout=self.request_timeout,
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                vision_models = [
                    m for m in models if "llava" in m.get("name", "").lower() or "bakllava" in m.get("name", "").lower()
                ]
                if vision_models:
                    self._vision_model_cache = vision_models[0]["name"]
                    self._vision_model_checked_at = now
                    self.logger.debug(
                        "Cached vision model '%s' (ttl %.0fs)",
                        self._vision_model_cache,
                        self.vision_model_cache_ttl,
                    )
                    return self._vision_model_cache
                self.logger.warning("No vision models found in Ollama")
            else:
                self.logger.warning(
                    "Vision model discovery failed with status %s",
                    response.status_code,
                )
        except Exception as exc:
            self.logger.warning("Vision model discovery error: %s", exc)

        self._vision_model_cache = None
        self._vision_model_checked_at = now
        return None

    def _check_vision_availability(self) -> bool:
        """Check if Vision AI (LLaVA) is available via Ollama"""
        try:
            model_name = self._get_vision_model_name()
            if model_name:
                self.logger.success(f"Vision AI available: {model_name}")
                return True
            self.logger.warning("Vision AI unavailable - no suitable models discovered")
            return False

        except Exception as e:
            self.logger.warning(f"Vision AI check failed: {e}")
            return False

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Async pipeline entrypoint wrapping `process_document`."""
        if not hasattr(context, "document_id") or not hasattr(context, "file_path"):
            raise ValueError("Processing context must include 'document_id' and 'file_path'")

        document_id = getattr(context, "document_id")
        pdf_path = Path(context.file_path)
        output_dir = getattr(context, "output_dir", None)

        manufacturer = getattr(context, "manufacturer", None) or getattr(context, "processing_config", {}).get(
            "manufacturer"
        )
        document_type = getattr(context, "document_type", None) or getattr(context, "processing_config", {}).get(
            "document_type"
        )

        with metrics.stage_timer(
            stage=self.stage.value, manufacturer=manufacturer or "unknown", document_type=document_type or "unknown"
        ) as timer:
            try:
                raw_result = await self.process_document(
                    document_id,
                    pdf_path,
                    output_dir,
                    context=context,
                )

                if raw_result.get("success"):
                    timer.stop(success=True)
                    return self.create_success_result(
                        data=raw_result,
                        metadata={
                            "images_processed": raw_result.get("images_processed", 0),
                            "total_extracted": raw_result.get("total_extracted", 0),
                        },
                    )
                error_msg = str(raw_result.get("error", "Unknown error"))
                timer.stop(success=False, error_label=error_msg)
                from backend.core.base_processor import ProcessingError

                error = ProcessingError(error_msg, self.name, "IMAGE_PROCESSING_FAILED")
                return self.create_error_result(error=error, metadata={})

            except Exception as exc:
                timer.stop(success=False, error_label=str(exc))
                from backend.core.base_processor import ProcessingError

                error = ProcessingError(str(exc), self.name, "IMAGE_PROCESSING_EXCEPTION")
                return self.create_error_result(error=error, metadata={})

    async def process_document(
        self,
        document_id: UUID,
        pdf_path: Path,
        output_dir: Path | None = None,
        context: Any | None = None,  # Phase 5: ProcessingContext for page_texts
    ) -> dict[str, Any]:
        """
        Process all images in a PDF document

        Args:
            document_id: Document UUID
            pdf_path: Path to PDF file
            output_dir: Directory to save extracted images (optional)

        Returns:
            Dict with processing results
        """
        if not pdf_path.exists():
            return {"success": False, "error": f"PDF not found: {pdf_path}", "images": []}

        # Start stage tracking
        if self.stage_tracker:
            await self.stage_tracker.start_stage(str(document_id), self.stage.value)

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            try:
                safe_pdf_name = sanitize_document_name(pdf_path.name)
                adapter.info("Processing images from: %s", safe_pdf_name)

                # Create output directory
                if output_dir is None:
                    output_dir = Path(tempfile.gettempdir()) / "krai_temp_images" / str(document_id)

                output_dir.mkdir(parents=True, exist_ok=True)

                # Extract images
                extracted_images = self._extract_images(pdf_path, output_dir)

                if not extracted_images:
                    if self.stage_tracker:
                        await self.stage_tracker.skip_stage(
                            str(document_id), self.stage.value, reason="No images found in document"
                        )
                    return {
                        "success": True,
                        "images_processed": 0,
                        "images": [],
                        "vision_enabled": self.enable_vision and self.vision_available,
                        "ocr_enabled": self.enable_ocr and self.ocr_available,
                        "message": "No images found in document",
                    }

                adapter.info("Extracted %d images", len(extracted_images))

                # Phase 5: Extract context for images (NEW!)
                if self.enable_context_extraction and context:
                    page_texts = await self._load_page_texts(context, pdf_path, adapter)
                    if page_texts:
                        extracted_images = await self._extract_image_contexts(
                            images=extracted_images,
                            page_texts=page_texts,
                            adapter=adapter,
                            pdf_path=pdf_path,  # Pass PDF path for bbox-aware extraction
                            document_id=document_id,  # Pass document ID for related chunks
                        )

                # Filter images (skip logos, headers, etc.)
                filtered_images = self._filter_images(extracted_images)

                adapter.info(
                    "Filtered to %d relevant images (removed %d logos/headers)",
                    len(filtered_images),
                    len(extracted_images) - len(filtered_images),
                )

                # Classify images
                classified_images = self._classify_images(filtered_images)

                # OCR if enabled
                if self.ocr_available and self.enable_ocr:
                    adapter.info("Running OCR on images...")
                    classified_images = self._run_ocr(classified_images)

                # Vision AI if enabled
                if self.vision_available and self.enable_vision:
                    adapter.info("Running Vision AI analysis...")
                    classified_images = self._run_vision_ai(classified_images)

                storage_task_count = 0
                if context is not None:
                    for image in classified_images:
                        if not image.get("id"):
                            image["id"] = str(uuid4())
                        if image.get("path") and not image.get("temp_path"):
                            image["temp_path"] = image.get("path")
                        if image.get("type") and not image.get("image_type"):
                            image["image_type"] = image.get("type")
                    context.images = classified_images
                    context.output_dir = output_dir

                # Persist images to krai_content.images and propagate IDs
                if self.database_service and classified_images:
                    storage_task_count = await self._queue_storage_tasks(
                        document_id,
                        classified_images,
                        adapter,
                    )
                    adapter.info("Persisted %d images to krai_content.images", storage_task_count)

                # Complete stage tracking
                if self.stage_tracker:
                    await self.stage_tracker.complete_stage(
                        str(document_id),
                        self.stage.value,
                        metadata={
                            "images_extracted": len(extracted_images),
                            "images_filtered": len(filtered_images),
                            "images_classified": len(classified_images),
                            "images_with_context": sum(1 for img in classified_images if img.get("context_caption")),
                            "storage_tasks_created": storage_task_count,
                        },
                    )

                # Clean up temporary images if configured and queued successfully
                if self.cleanup_temp_images and storage_task_count > 0:
                    self._cleanup_output_dir(output_dir, adapter)

                result = {
                    "success": True,
                    "images": classified_images,
                    "images_processed": len(classified_images),
                    "total_extracted": len(extracted_images),
                    "total_filtered": len(filtered_images),
                    "output_dir": str(output_dir) if output_dir else None,
                    "storage_tasks_created": storage_task_count,
                }
                self.logger.success(f"Processed {len(classified_images)} images (extracted {len(extracted_images)})")
                return result

            except Exception as e:
                error_msg = f"Image processing failed: {e}"
                adapter.error("Image processing failed: %s", e)

                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(str(document_id), self.stage.value, error_msg)

                return {"success": False, "error": error_msg, "images": []}

    def _extract_images(self, pdf_path: Path, output_dir: Path) -> list[dict[str, Any]]:
        """
        Extract all images from PDF using PyMuPDF

        Args:
            pdf_path: Path to PDF
            output_dir: Output directory for images

        Returns:
            List of extracted image info dicts
        """
        images = []

        try:
            # Open PDF
            pdf_document = fitz.open(str(pdf_path))

            image_counter = 0

            try:
                # Iterate through pages
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]

                    # Get images on page
                    image_list = page.get_images(full=True)

                    for img_index, img_info in enumerate(image_list):
                        if image_counter >= self.max_images_per_doc:
                            self.logger.warning(f"Reached max images limit: {self.max_images_per_doc}")
                            break

                        try:
                            # Extract image
                            xref = img_info[0]
                            base_image = pdf_document.extract_image(xref)

                            image_bytes = base_image["image"]
                            image_ext = base_image["ext"]

                            # Skip SVGs — they are handled by SVGProcessor
                            if image_ext.lower() in ("svg", "svgz"):
                                continue

                            # Convert to JPEG with white background immediately so no
                            # PNG/GIF files ever reach disk or storage.
                            image_bytes, image_ext = _raster_to_jpeg(image_bytes, image_ext)

                            # Open with PIL to get dimensions
                            with Image.open(io.BytesIO(image_bytes)) as pil_image:
                                width, height = pil_image.size

                            # Check minimum size
                            if width * height < self.min_image_size:
                                continue

                            # Compute image bounding box using display list
                            image_bbox = self._get_image_bbox(page, img_index)

                            # Save image
                            image_filename = f"page_{page_num:04d}_img_{img_index:03d}.{image_ext}"
                            image_path = output_dir / image_filename

                            with open(image_path, "wb") as img_file:
                                img_file.write(image_bytes)

                            # Store image info
                            images.append(
                                {
                                    "path": str(image_path),
                                    "filename": image_filename,
                                    "page_number": page_num + 1,  # 1-indexed - standardized key
                                    "width": width,
                                    "height": height,
                                    "format": image_ext,
                                    "size_bytes": len(image_bytes),
                                    "bbox": image_bbox,  # Add bounding box
                                    "extracted_at": datetime.utcnow().isoformat(),
                                }
                            )

                            image_counter += 1

                        except Exception as e:
                            self.logger.debug(f"Failed to extract image {img_index} from page {page_num}: {e}")
                            continue

                    if image_counter >= self.max_images_per_doc:
                        break
            finally:
                pdf_document.close()

            return images

        except Exception as e:
            self.logger.error(f"Image extraction failed: {e}")
            return []

    def _get_image_bbox(self, page, img_index: int) -> tuple | None:
        """
        Compute bounding box for an image using the page's display list.

        Args:
            page: PyMuPDF page object
            img_index: Index of the image in the page's image list

        Returns:
            Bounding box as tuple (x0, y0, x1, y1) or None if not found
        """
        try:
            # Get images on page to match xref
            image_list = page.get_images(full=True)
            if img_index >= len(image_list):
                return None

            target_xref = image_list[img_index][0]

            # Preferred method (PyMuPDF): query rects for this image xref
            try:
                rects = page.get_image_rects(target_xref)
                if rects:
                    rect = rects[0]
                    return (rect.x0, rect.y0, rect.x1, rect.y1)
            except Exception:
                pass

            # Fallback: use page.get_text('rawdict') to find image positions
            try:
                text_dict = page.get_text("rawdict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") == 1 and "xref" in block and block["xref"] == target_xref:
                        bbox = block.get("bbox")
                        if bbox and len(bbox) == 4:
                            return tuple(bbox)
            except Exception:
                pass

            # If no specific bbox found, return None
            return None

        except Exception as e:
            self.logger.debug(f"Failed to compute image bbox for index {img_index}: {e}")
            return None

    async def _queue_storage_tasks(self, document_id: UUID, images: list[dict[str, Any]], adapter) -> int:
        """
        Persist each processed image to krai_content.images via the database adapter.
        Propagate generated image IDs back into in-memory image dicts.
        Returns the count of successfully written images.
        """
        if not self.database_service or not hasattr(self.database_service, "create_image"):
            adapter.warning("Database service does not support create_image - skipping persistence")
            return 0

        from backend.core.data_models import ImageModel, ImageType

        def _map_image_type(val: Any) -> str:
            if not val:
                return ImageType.DIAGRAM.value
            s = str(val).lower()
            if s in ("diagram", "screenshot", "photo", "chart", "schematic", "flowchart"):
                return s
            if s == "table":
                return ImageType.DIAGRAM.value
            return ImageType.DIAGRAM.value

        def _compute_file_hash(img: dict[str, Any]) -> str:
            path = img.get("temp_path") or img.get("path") or ""
            size = img.get("size_bytes", 0)
            page = img.get("page_number", 0)
            return hashlib.sha256(f"{path}|{size}|{page}".encode()).hexdigest()

        success_count = 0
        for idx, img in enumerate(images):
            temp_path = img.get("temp_path") or img.get("path")
            if not temp_path or not os.path.exists(temp_path):
                adapter.debug("Skipping image without valid temp_path: %s", img.get("filename"))
                continue

            try:
                file_hash = _compute_file_hash(img)
                storage_path = temp_path
                storage_url = f"file://{temp_path}"

                image_model = ImageModel(
                    document_id=str(document_id),
                    filename=img.get("filename", f"img_{idx}.png"),
                    original_filename=img.get("filename", f"img_{idx}.png"),
                    storage_path=storage_path,
                    storage_url=storage_url,
                    file_size=img.get("size_bytes", 0),
                    image_format=(img.get("format") or "png").upper()[:10],
                    width_px=img.get("width", 0),
                    height_px=img.get("height", 0),
                    page_number=int(img.get("page_number", 1)),
                    image_index=idx,
                    image_type=_map_image_type(img.get("type") or img.get("image_type")),
                    ai_description=img.get("ai_description") or None,
                    ai_confidence=float(img.get("ai_confidence", 0.5)),
                    contains_text=bool(img.get("contains_text", False)),
                    ocr_text=img.get("ocr_text") or None,
                    ocr_confidence=float(img.get("ocr_confidence", 0.0)),
                    file_hash=file_hash,
                    context_caption=img.get("context_caption"),
                    page_header=img.get("page_header"),
                    figure_reference=img.get("figure_reference"),
                    related_error_codes=img.get("related_error_codes") or [],
                    related_products=img.get("related_products") or [],
                    surrounding_paragraphs=img.get("surrounding_paragraphs") or [],
                )

                db_id = await self.database_service.create_image(image_model)
                img["id"] = db_id
                success_count += 1
                adapter.debug("Persisted image %s -> id=%s", img.get("filename"), db_id)
            except Exception as e:
                adapter.warning("Failed to persist image %s: %s", img.get("filename"), e)

        return success_count

    def _cleanup_output_dir(self, output_dir: Path, adapter) -> None:
        try:
            if not output_dir or not output_dir.exists():
                return

            for item in output_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                except Exception as exc:
                    adapter.debug("Failed to cleanup %s: %s", item, exc)

            output_dir.rmdir()
        except Exception as exc:
            adapter.debug("Failed to cleanup output directory %s: %s", output_dir, exc)

    def _filter_images(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out non-relevant images (logos, headers, etc.)

        Args:
            images: List of extracted images

        Returns:
            Filtered list of images
        """
        filtered = []

        for img in images:
            # Skip very small images (likely logos/icons)
            if img["width"] < 100 or img["height"] < 100:
                continue

            # Skip very large images (likely full-page scans)
            if img["width"] > 4000 or img["height"] > 4000:
                continue

            # Skip extreme aspect ratios (likely headers/footers)
            aspect_ratio = img["width"] / img["height"]
            if aspect_ratio > 10 or aspect_ratio < 0.1:
                continue

            filtered.append(img)

        return filtered

    def _classify_images(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Classify images by type (diagram, table, photo, etc.)

        Simple heuristic-based classification.
        Vision AI will provide better classification later.

        Args:
            images: List of images

        Returns:
            Images with 'type' field added
        """
        for img in images:
            # Simple heuristic classification
            aspect_ratio = img["width"] / img["height"]

            # Tables tend to be wide
            if aspect_ratio > 2.0:
                img["type"] = "table"
            # Diagrams tend to be squarish
            elif 0.7 <= aspect_ratio <= 1.3:
                img["type"] = "diagram"
            # Charts can be various shapes
            elif aspect_ratio > 1.3:
                img["type"] = "chart"
            else:
                img["type"] = "unknown"

            # This will be improved by Vision AI
            img["classification_method"] = "heuristic"

        return images

    def _run_ocr(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Run OCR on images to extract text

        Args:
            images: List of images

        Returns:
            Images with 'ocr_text' field added
        """
        if not self.ocr_available:
            return images

        try:
            import pytesseract

            success_count = 0
            futures = []
            start_time = time.perf_counter()

            def ocr_task(img: dict[str, Any]) -> tuple[dict[str, Any], bool, float]:
                try:
                    pil_image = Image.open(img["path"])
                    pil_image = self._apply_preprocessing(pil_image)

                    task_start = time.perf_counter()
                    ocr_data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
                    latency = time.perf_counter() - task_start

                    text_parts = [word for word in ocr_data["text"] if word.strip()]
                    ocr_text = " ".join(text_parts)

                    confidences = [int(conf) for conf in ocr_data["conf"] if int(conf) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

                    img["ocr_text"] = ocr_text.strip()
                    img["ocr_confidence"] = round(avg_confidence / 100, 2)
                    img["contains_text"] = len(ocr_text.strip()) > 0

                    return img, bool(ocr_text.strip()), latency
                except Exception as exc:  # pragma: no cover - best effort
                    self.logger.debug("OCR failed for %s: %s", img.get("filename"), exc)
                    img["ocr_text"] = ""
                    img["ocr_confidence"] = 0.0
                    img["contains_text"] = False
                    return img, False, 0.0

            with self.logger.progress_bar(images, "Running OCR") as progress:
                task = progress.add_task("OCR processing", total=len(images))

                for img in images:
                    futures.append(self.ocr_executor.submit(ocr_task, img))

                for future in as_completed(futures):
                    processed_img, has_text, latency = future.result()
                    if latency > 0:
                        self._record_ocr_latency(latency)
                        p95, p99 = self._calculate_percentiles(list(self.ocr_latency_window))
                        if p95 or p99:
                            self.logger.debug("OCR latency percentiles: p95=%.3fs p99=%.3fs", p95, p99)
                    if has_text:
                        success_count += 1
                    progress.update(task, advance=1, description=f"OCR: {success_count} images with text")

            duration = time.perf_counter() - start_time
            self.logger.success(
                "✅ OCR processed %d/%d images with text (%.2fs)",
                success_count,
                len(images),
                duration,
            )

            return images

        except Exception as e:
            self.logger.error(f"OCR processing failed: {e}")
            return images

    def _run_vision_ai(
        self,
        images: list[dict[str, Any]],
        max_images: int = 50,  # Increased from 20 to process more diagrams/technical drawings
    ) -> list[dict[str, Any]]:
        """
        Run Vision AI (LLaVA) on images

        Args:
            images: List of images
            max_images: Maximum images to process (default: 50, ~10-15 min processing time)

        Returns:
            Images with 'ai_description' and 'ai_confidence' fields added
        """
        if not self.vision_available:
            self.logger.debug("Vision AI not available, skipping")
            return images

        # Limit to max_images to avoid overwhelming the system
        images_to_process = images[:max_images]
        skipped_count = len(images) - len(images_to_process)

        if skipped_count > 0:
            self.logger.info(
                f"Processing first {len(images_to_process)} images (skipping {skipped_count} to avoid overload)"
            )
        else:
            self.logger.info(f"Processing {len(images_to_process)} images with Vision AI...")

        try:
            if not self._vision_quota_allows():
                self.logger.warning("Global vision quota exceeded - skipping vision analysis")
                return images

            model_name = self._get_vision_model_name()
            if not model_name:
                return images

            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

            # Ensure URL has a scheme so urlparse() can reliably detect hostname
            if ollama_url and "://" not in ollama_url:
                ollama_url = f"http://{ollama_url}"

            try:
                parsed = urlparse(ollama_url)
                running_in_docker = os.path.exists("/.dockerenv") or os.getenv("KRAI_IN_DOCKER") == "1"
                if parsed.hostname in ("krai-ollama", "ollama") and not running_in_docker:
                    port_str = f":{parsed.port}" if parsed.port else ""
                    netloc = f"127.0.0.1{port_str}"
                    ollama_url = urlunparse(parsed._replace(netloc=netloc))
            except Exception:
                pass

            success_count = 0
            processed_count = 0
            total_images = len(images_to_process)
            batch_size = max(1, total_images // 10) if total_images else 1

            for i, img in enumerate(images_to_process):
                if i % batch_size == 0 or i == total_images - 1:
                    self.logger.warning(
                        "Image processing: %d/%d (%.0f%%)",
                        i + 1,
                        total_images,
                        ((i + 1) / total_images) * 100 if total_images else 100,
                    )

                if img.get("has_png_derivative") is False:
                    self.logger.debug(
                        "Skipping Vision AI for %s because PNG derivative is unavailable",
                        img.get("filename"),
                    )
                    continue

                if not self._vision_guard_allows(img, processed_count):
                    continue

                if not self._vision_quota_allows():
                    self.logger.warning("Vision quota reached mid-run - stopping vision analysis")
                    break

                processed_count += 1
                try:
                    with open(img["path"], "rb") as f:
                        image_data = base64.b64encode(f.read()).decode("utf-8")

                    prompt = (
                        "Analyze this technical diagram or image from a service manual.\n"
                        "Describe what you see in 2-3 sentences. Focus on:\n"
                        "- Type of component or diagram (e.g., circuit board, exploded view, flowchart)\n"
                        "- Key parts or elements visible\n"
                        "- Any labels or numbers you can read\n\n"
                        "Keep it concise and technical."
                    )

                    max_attempts = max(1, self.max_retries)
                    last_error = None
                    succeeded = False

                    for attempt in range(1, max_attempts + 1):
                        try:
                            self._record_vision_usage()
                            response = self.session.post(
                                f"{ollama_url}/api/generate",
                                json={
                                    "model": model_name,
                                    "prompt": prompt,
                                    "images": [image_data],
                                    "stream": False,
                                },
                                timeout=self.request_timeout,
                            )

                            if response.status_code == 200:
                                result = response.json()
                                description = result.get("response", "").strip()
                                img["ai_description"] = description
                                img["ai_confidence"] = 0.8
                                img["contains_text"] = any(
                                    keyword in description.lower() for keyword in ["label", "text", "number", "code"]
                                )
                                success_count += 1
                                self._reset_vision_failures()
                                metrics.record_vision_result(model_name, True)
                                desc_stats = text_stats(description)
                                self.logger.debug(
                                    "Vision analysis stats for %s: %s",
                                    img.get("filename"),
                                    desc_stats,
                                )
                                succeeded = True
                                break

                            last_error = f"status_{response.status_code}"
                            if response.status_code >= 500 and attempt < max_attempts:
                                delay = self.retry_base_delay * (2 ** (attempt - 1)) + random.uniform(
                                    0, self.retry_jitter
                                )
                                self.logger.warning(
                                    "Vision API transient error %s on attempt %d/%d for %s - retrying in %.2fs",
                                    response.status_code,
                                    attempt,
                                    max_attempts,
                                    img["filename"],
                                    delay,
                                )
                                time.sleep(delay)
                                continue

                            if response.status_code >= 500:
                                self.logger.error(
                                    "Vision API persistent server error %s for %s after %d attempts",
                                    response.status_code,
                                    img["filename"],
                                    attempt,
                                )
                            else:
                                self.logger.warning(
                                    "Vision API returned HTTP %s for %s (attempt %d/%d) - not retrying",
                                    response.status_code,
                                    img["filename"],
                                    attempt,
                                    max_attempts,
                                )

                            self._record_vision_failure(last_error or "unexpected_status")
                            img["ai_description"] = ""
                            img["ai_confidence"] = 0.0
                            break

                        except (requests_exceptions.Timeout, requests_exceptions.ConnectionError) as exc:
                            last_error = str(exc)
                            if attempt < max_attempts:
                                delay = self.retry_base_delay * (2 ** (attempt - 1)) + random.uniform(
                                    0, self.retry_jitter
                                )
                                self.logger.warning(
                                    "Vision request error on attempt %d/%d for %s: %s - retrying in %.2fs",
                                    attempt,
                                    max_attempts,
                                    img["filename"],
                                    exc,
                                    delay,
                                )
                                time.sleep(delay)
                                continue
                            self.logger.error(
                                "Vision request failed for %s after %d attempts due to connection issues: %s",
                                img["filename"],
                                attempt,
                                exc,
                            )
                            self._record_vision_failure("connection_error")
                            img["ai_description"] = ""
                            img["ai_confidence"] = 0.0
                            break
                        except Exception as exc:
                            last_error = str(exc)
                            self._record_vision_failure("exception")
                            img["ai_description"] = ""
                            img["ai_confidence"] = 0.0
                            self.logger.debug(
                                "Vision AI failed for %s: %s",
                                img.get("filename"),
                                exc,
                            )
                            break
                    else:  # pragma: no cover - defensive
                        self._record_vision_failure(last_error or "unknown")

                    if not succeeded:
                        metrics.record_vision_result(model_name, False, error_label=last_error or "failed")

                except Exception as exc:
                    self._record_vision_failure("read_error")
                    self.logger.debug("Vision preprocessing failed for %s: %s", img.get("filename"), exc)
                    img["ai_description"] = ""
                    img["ai_confidence"] = 0.0
                    metrics.record_vision_result(model_name, False, error_label="read_error")

                if self._vision_breaker_until and time.time() < self._vision_breaker_until:
                    self.logger.warning("Vision circuit breaker triggered mid-run - stopping analysis")
                    break

            self.logger.success(
                "✅ Vision AI analyzed %d/%d permitted images",
                success_count,
                processed_count,
            )

            return images

        except Exception as e:
            self.logger.error(f"Vision AI processing failed: {e}")
            return images

    def analyze_page(self, pdf_path: Path, page_number: int, prompt: str) -> dict[str, Any] | None:
        """
        Analyze a specific PDF page with Vision AI

        Args:
            pdf_path: Path to PDF file
            page_number: Page number to analyze (0-indexed)
            prompt: Custom prompt for Vision AI

        Returns:
            Dict with analysis results or None if failed
        """
        try:
            if not self.vision_available:
                self.logger.warning("Vision AI not available")
                return None

            # Extract page as image
            doc = fitz.open(pdf_path)
            try:
                if page_number >= len(doc):
                    self.logger.warning(f"Page {page_number} out of range (doc has {len(doc)} pages)")
                    return None

                page = doc[page_number]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                img_data = pix.tobytes("png")
            finally:
                doc.close()

            # Analyze with Vision AI
            img_base64 = base64.b64encode(img_data).decode("utf-8")

            if self._vision_breaker_until and time.time() < self._vision_breaker_until:
                self.logger.warning("Vision circuit breaker open - analyze_page aborted")
                return None

            if not self._vision_quota_allows():
                self.logger.warning("Vision quota reached - analyze_page aborted")
                return None

            self._record_vision_usage()

            model_name = self._get_vision_model_name() or "llava:latest"
            response = self.session.post(
                "http://localhost:11434/api/generate",
                json={"model": model_name, "prompt": prompt, "images": [img_base64], "stream": False},
                timeout=self.request_timeout,
            )

            if response.status_code == 200:
                result_text = response.json().get("response", "")
                metrics.record_vision_result(model_name, True)

                # Try to parse as JSON
                try:
                    # Extract JSON from response (might have extra text)
                    import re

                    json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    return {"found": False, "raw_response": result_text}
                except json.JSONDecodeError:
                    return {"found": False, "raw_response": result_text}
            else:
                self.logger.warning(f"Vision API error: {response.status_code}")
                metrics.record_vision_result(model_name, False, error_label=f"status_{response.status_code}")
                return None

        except Exception as e:
            metrics.record_vision_result(model_name if "model_name" in locals() else None, False, error_label=str(e))
            self.logger.error(f"analyze_page failed: {e}")
            return None

    async def _load_page_texts(self, context, pdf_path: Path, adapter) -> dict[int, str] | None:
        """
        Load page texts for context extraction with three-tier fallback.

        Args:
            context: ProcessingContext containing page_texts if available
            pdf_path: Path to PDF file
            adapter: Logger adapter

        Returns:
            Dict mapping page_number to page_text, or None if not available
        """
        # Tier 1: Check context.page_texts (from TextProcessor)
        if hasattr(context, "page_texts") and context.page_texts:
            adapter.debug("Using page_texts from context (%d pages)", len(context.page_texts))
            return context.page_texts

        # Tier 2: Rebuild from database chunks
        if self.database_service:
            try:
                adapter.debug("Attempting to rebuild page_texts from database chunks")
                # Get document_id from context
                document_id = getattr(context, "document_id", None)
                if document_id:
                    rows = await self.database_service.execute_query(
                        """
                        SELECT page_start, page_end, text_chunk
                        FROM krai_intelligence.chunks
                        WHERE document_id = $1
                        ORDER BY chunk_index
                        """.strip(),
                        [str(document_id)],
                    )

                    if rows:
                        page_texts: dict[int, str] = {}
                        for chunk in rows:
                            page_start = chunk.get("page_start") or 1
                            page_end = chunk.get("page_end") or page_start
                            content = chunk.get("text_chunk", "") or ""

                            for page_num in range(int(page_start), int(page_end) + 1):
                                page_texts[page_num] = page_texts.get(page_num, "") + content + "\n"

                        if page_texts:
                            adapter.debug("Rebuilt page_texts from %d chunks", len(rows))
                            return page_texts
                else:
                    adapter.warning("No document_id available for chunk reconstruction")
            except Exception as e:
                adapter.warning("Failed to rebuild page_texts from database: %s", e)

        # Tier 3: Re-extract from PDF using TextExtractor
        try:
            adapter.debug("Re-extracting page_texts from PDF")
            from .text_extractor import TextExtractor

            text_extractor = TextExtractor()
            page_texts, metadata = text_extractor.extract_text(pdf_path)

            if page_texts:
                adapter.debug("Re-extracted %d pages from PDF", len(page_texts))
                return page_texts
            adapter.warning("No text extracted from PDF for context")

        except Exception as e:
            adapter.error("Failed to re-extract page_texts from PDF: %s", e)

        return None

    async def _extract_image_contexts(
        self,
        images: list[dict],
        page_texts: dict[int, str],
        adapter,
        pdf_path: Path | None = None,
        document_id: UUID | None = None,
    ) -> list[dict]:
        """
        Extract context for all images using ContextExtractionService.

        Args:
            images: List of image dictionaries
            page_texts: Dict mapping page_number to page_text
            adapter: Logger adapter
            pdf_path: Optional PDF path for bbox-aware extraction
            document_id: Optional document ID for related chunks extraction

        Returns:
            List of images with context metadata added
        """
        images_with_context: list[dict] = []
        related_chunks_cache: dict[int, list[str]] = {}

        for image in images:
            page_number = image.get("page_number")
            if not page_number or page_number not in page_texts:
                adapter.warning("No page text available for image on page %d", page_number)
                images_with_context.append(image)
                continue

            page_text = page_texts[page_number]
            image_bbox = image.get("bbox")  # Optional bounding box

            try:
                # Extract context using ContextExtractionService
                context_data = self.context_service.extract_image_context(
                    page_text=page_text,
                    page_number=page_number,
                    image_bbox=image_bbox,
                    page_path=str(pdf_path),  # Pass PDF path for bbox-aware extraction
                )

                # Merge context data into image dict
                image.update(
                    {
                        "context_caption": context_data["context_caption"],
                        "page_header": context_data["page_header"],
                        "figure_reference": context_data.get("figure_reference"),
                        "related_error_codes": context_data["related_error_codes"],
                        "related_products": context_data["related_products"],
                        "surrounding_paragraphs": context_data["surrounding_paragraphs"],
                        "related_chunks": related_chunks_cache.get(page_number, []),
                    }
                )

                if page_number not in related_chunks_cache:
                    related_chunks_cache[page_number] = await self._get_related_chunks(
                        page_number, document_id, adapter
                    )
                    image["related_chunks"] = related_chunks_cache.get(page_number, [])

                images_with_context.append(image)

            except Exception as e:
                adapter.error("Failed to extract context for image on page %d: %s", page_number, e)
                images_with_context.append(image)

        adapter.info("Extracted context for %d images", len(images_with_context))
        return images_with_context

    async def _get_related_chunks(self, page_number: int, document_id: UUID, adapter) -> list[str]:
        """
        Extract related chunk IDs for a given page number.

        Args:
            page_number: Page number to find chunks for
            document_id: Document ID to query chunks
            adapter: Logger adapter

        Returns:
            List of chunk IDs that include the given page
        """
        if not self.database_service or not document_id:
            return []

        try:
            rows = await self.database_service.execute_query(
                """
                SELECT id
                FROM krai_intelligence.chunks
                WHERE document_id = $1
                  AND COALESCE(page_start, 0) <= $2
                  AND COALESCE(page_end, page_start) >= $2
                """.strip(),
                [str(document_id), int(page_number)],
            )

            if rows:
                chunk_ids = [str(chunk["id"]) for chunk in rows]
                adapter.debug(f"Found {len(chunk_ids)} related chunks for page {page_number}")
                return chunk_ids

            return []

        except Exception as e:
            adapter.warning(f"Failed to get related chunks for page {page_number}: {e}")
            return []


# Example usage
if __name__ == "__main__":
    processor = ImageProcessor()

    # Test with a PDF
    pdf_path = Path("../../AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf")

    if pdf_path.exists():
        print(f"Processing: {pdf_path.name}")

        result = processor.process_document(document_id=uuid4(), pdf_path=pdf_path)

        if result["success"]:
            print(f"\n✅ Extracted {result['total_extracted']} images")
            print(f"✅ Filtered to {result['total_filtered']} relevant images")
            print(f"✅ Saved to: {result['output_dir']}")
        else:
            print(f"\n❌ Failed: {result['error']}")
    else:
        print("Test PDF not found")
