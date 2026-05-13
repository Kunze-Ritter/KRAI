"""
SVG Processor - Extract and convert vector graphics from PDFs

Stage 3a of the processing pipeline. Extracts SVG vector graphics (Explosionszeichnungen)
and converts them to PNG for Vision AI analysis.
"""

import asyncio
import base64
import concurrent.futures
import io
import logging
import os
import threading
from typing import Any
from uuid import UUID, uuid4

import fitz
from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage


class SVGProcessor(BaseProcessor):
    """
    SVG Processor for vector graphics extraction and conversion

    Extracts SVG vector graphics from PDFs using PyMuPDF, converts them to PNG
    using svglib + reportlab, and queues them for Vision AI analysis.
    """

    def __init__(self, database_service, storage_service, ai_service=None, dpi: int = 300, max_dimension: int = 2048):
        """
        Initialize SVG Processor

        Args:
            database_service: Database service for queuing images
            storage_service: Storage service (not used directly, but required for interface)
            ai_service: AI service for Vision AI analysis (optional)
            dpi: DPI for SVG to PNG conversion (default: 300)
            max_dimension: Maximum width/height for converted PNGs (default: 2048)
        """
        super().__init__("svg_processor")
        self.database_service = database_service
        self.storage_service = storage_service
        self.ai_service = ai_service
        self.dpi = dpi
        self.max_dimension = max_dimension
        self.svg_inline_storage_threshold_kb = int(os.getenv("SVG_INLINE_STORAGE_THRESHOLD_KB", "100"))
        self._svg_workers = int(os.getenv("SVG_PROCESSING_WORKERS", str(min(8, os.cpu_count() or 4))))
        self._pymupdf_lock = threading.Lock()  # fitz.Document is not thread-safe across pages
        # Reduce svglib log noise (e.g. "Unsupported shape type Group for clipping" – we handle failure and use fallback)
        # Set to CRITICAL so even ERROR-Meldungen von svglib unterdrückt werden.
        logging.getLogger("svglib.svglib").setLevel(logging.CRITICAL)
        self.logger.info(f"SVGProcessor initialized (DPI: {dpi}, max_dimension: {max_dimension})")

    def get_stage(self) -> Stage:
        """Return the processing stage"""
        return Stage.SVG_PROCESSING

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Main processing method for SVG extraction and conversion

        Args:
            context: Processing context with document information

        Returns:
            ProcessingResult with SVG extraction statistics
        """
        import asyncio

        loop = asyncio.get_running_loop()
        # Merke das Event-Loop-Objekt, damit synchroner Code in Threads
        # korrekte Coroutines per run_coroutine_threadsafe einplanen kann.
        self._event_loop = loop

        try:
            # Extract document information
            document_id = UUID(context.document_id)
            pdf_path = context.pdf_path

            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")

            # Process document in thread pool
            result_data = await loop.run_in_executor(None, self.process_document, document_id, pdf_path, context)

            return self.create_success_result(
                data=result_data,
                metadata={
                    "document_id": str(document_id),
                    "stage": self.get_stage().value,
                    "svgs_extracted": result_data.get("svgs_extracted", 0),
                    "svgs_converted": result_data.get("svgs_converted", 0),
                    "images_queued": result_data.get("images_queued", 0),
                },
            )

        except Exception as e:
            error = ProcessingError(f"SVG processing failed: {e!s}", self.name, "SVG_PROCESSING_ERROR")
            return self.create_error_result(error)

    def process_document(self, document_id: UUID, pdf_path: str, context) -> dict[str, Any]:
        """
        Process document to extract and convert SVGs

        Args:
            document_id: Document UUID
            pdf_path: Path to PDF file
            context: Processing context

        Returns:
            Dictionary with processing statistics
        """
        self.logger.info(f"Starting SVG processing for document {document_id}")

        # Open PDF document
        doc = fitz.open(pdf_path)
        try:
            # Extract SVGs from all pages
            all_svgs = []
            page_count = doc.page_count
            for page_num, page in enumerate(doc):
                # Fortschritt auf Seitenebene loggen, z. B. „Seite 10/1023“
                if page_count:
                    self.logger.info(
                        "SVG processing page %s/%s for document %s",
                        page_num + 1,
                        page_count,
                        document_id,
                    )
                page_svgs = self._extract_page_svgs(page, page_num + 1)
                if page_svgs:
                    all_svgs.extend(page_svgs)
                    self.logger.debug(f"Extracted {len(page_svgs)} SVGs from page {page_num + 1}")

            converted_count = 0
            svg_storage_success_count = 0
            vision_skip_count = 0
            vision_enabled = bool(self.ai_service)

            def _process_single_svg(svg_data: dict[str, Any]) -> dict[str, Any]:
                """Process one SVG: upload to storage + optional PNG conversion."""
                svg_data["document_id"] = str(document_id)
                storage_result = self._upload_svg_to_storage(svg_data)
                svg_data.update(storage_result)

                if vision_enabled:
                    png_bytes = self._convert_svg_to_png(svg_data["svg_content"])
                    if not png_bytes and svg_data.get("bounding_box") and svg_data.get("page_number"):
                        with self._pymupdf_lock:
                            png_bytes = self._render_svg_region_with_pymupdf(doc, svg_data)
                    if png_bytes:
                        svg_data["png_bytes"] = png_bytes
                        svg_data["image_type"] = "vector_graphic"
                        svg_data["has_png_derivative"] = True
                    else:
                        svg_data["has_png_derivative"] = False
                        self.logger.info(
                            "Skipping Vision AI for SVG without PNG derivative (document=%s, page=%s, file=%s)",
                            document_id,
                            svg_data.get("page_number"),
                            svg_data.get("filename"),
                        )
                else:
                    svg_data["has_png_derivative"] = False

                return svg_data

            self.logger.info("Processing %d SVGs with %d parallel workers", len(all_svgs), self._svg_workers)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self._svg_workers) as executor:
                all_svgs = list(executor.map(_process_single_svg, all_svgs))

            converted_count = sum(1 for s in all_svgs if s.get("has_png_derivative"))
            svg_storage_success_count = sum(1 for s in all_svgs if s.get("svg_storage_url"))
            vision_skip_count = len(all_svgs) - converted_count

            queued_count = self._queue_svg_images(document_id, all_svgs, context)
        finally:
            doc.close()

        result_data = {
            "svgs_extracted": len(all_svgs),
            "svgs_converted": converted_count,
            "images_queued": queued_count,
            "svg_storage_success": svg_storage_success_count,
            "vision_skipped_due_to_missing_png": vision_skip_count,
            "png_conversion_success_rate": converted_count / len(all_svgs) if all_svgs else 0,
            "svg_storage_success_rate": svg_storage_success_count / len(all_svgs) if all_svgs else 0,
        }

        self.logger.success(
            f"SVG processing completed: {len(all_svgs)} extracted, "
            f"{converted_count} converted, {queued_count} queued"
        )

        return result_data

    def _extract_page_svgs(self, page, page_number: int) -> list[dict[str, Any]]:
        """
        Extract SVG graphics from a PDF page with enhanced multi-graphic support

        Args:
            page: PyMuPDF page object
            page_number: Page number (1-based)

        Returns:
            List of SVG data dictionaries with bounding box information
        """
        svgs = []

        try:
            # Get page dimensions for bounding box calculations
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            # Method 1: Try to extract individual vector graphics through display list analysis
            try:
                # Get the page's display list to analyze individual drawing operations
                dl = page.get_drawings()

                if dl and len(dl) > 1:
                    # Multiple drawing operations detected - extract individual graphics
                    self.logger.debug(f"Page {page_number}: Found {len(dl)} drawing operations")

                    for i, drawing in enumerate(dl):
                        # Extract bounding box for this drawing
                        bbox = drawing["rect"]  # PyMuPDF provides bounding box

                        # Create a clip area for this specific graphic
                        clip_area = fitz.Rect(bbox)

                        # Extract SVG for this specific area
                        try:
                            # Create a temporary page with clipping to isolate this graphic
                            svg_content = page.get_svg_image(clip=clip_area)

                            if svg_content and len(svg_content.strip()) > 0:
                                svg_data = {
                                    "id": str(uuid4()),
                                    "page_number": page_number,
                                    "graphic_index": i,
                                    "svg_content": svg_content,
                                    "svg_size": len(svg_content),
                                    "filename": f"page_{page_number}_graphic_{i+1:02d}.svg",
                                    "bounding_box": {
                                        "x0": bbox.x0,
                                        "y0": bbox.y0,
                                        "x1": bbox.x1,
                                        "y1": bbox.y1,
                                        "width": bbox.width,
                                        "height": bbox.height,
                                        "normalized": {
                                            "x0": bbox.x0 / page_width,
                                            "y0": bbox.y0 / page_height,
                                            "x1": bbox.x1 / page_width,
                                            "y1": bbox.y1 / page_height,
                                            "width": bbox.width / page_width,
                                            "height": bbox.height / page_height,
                                        },
                                    },
                                    "extraction_method": "display_list",
                                }
                                svgs.append(svg_data)

                        except Exception as e:
                            self.logger.debug(f"Failed to extract graphic {i} from page {page_number}: {e}")
                            continue
                else:
                    # Single graphic or no display list - use traditional method
                    pass

            except Exception as e:
                self.logger.debug(f"Display list analysis failed for page {page_number}: {e}")

            # Method 2: Fallback to traditional page-level SVG extraction
            if not svgs:
                # Extract full page SVG content
                svg_content = page.get_svg_image()

                if svg_content and len(svg_content.strip()) > 0:
                    # Create SVG record with page-level bounding box
                    svg_data = {
                        "id": str(uuid4()),
                        "page_number": page_number,
                        "graphic_index": 0,
                        "svg_content": svg_content,
                        "svg_size": len(svg_content),
                        "filename": f"page_{page_number}_vector.svg",
                        "bounding_box": {
                            "x0": 0,
                            "y0": 0,
                            "x1": page_width,
                            "y1": page_height,
                            "width": page_width,
                            "height": page_height,
                            "normalized": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0, "width": 1.0, "height": 1.0},
                        },
                        "extraction_method": "page_level",
                    }
                    svgs.append(svg_data)

                self.logger.debug(f"Extracted page-level SVG from page {page_number} ({len(svg_content)} bytes)")

            # Method 3: Try to identify vector segments through xobject inspection
            if not svgs or len(svgs) == 1:
                try:
                    # Get page's xobjects (embedded graphics)
                    xobjects = page.get_xobjects()

                    if xobjects:
                        self.logger.debug(f"Page {page_number}: Found {len(xobjects)} xobjects")

                        for i, xref in enumerate(xobjects):
                            try:
                                # Extract individual xobject as SVG
                                xobject = page.parent.extract_image(xref)

                                # Check if this is a vector graphic
                                if xobject and "ext" in xobject and xobject["ext"] in ["svg", "pdf"]:
                                    # For vector xobjects, we can extract them directly
                                    svg_data = {
                                        "id": str(uuid4()),
                                        "page_number": page_number,
                                        "graphic_index": len(svgs),
                                        "svg_content": xobject.get("image", ""),
                                        "svg_size": len(xobject.get("image", "")),
                                        "filename": f"page_{page_number}_xobject_{i+1:02d}.svg",
                                        "bounding_box": {
                                            "x0": 0,
                                            "y0": 0,
                                            "x1": page_width,
                                            "y1": page_height,
                                            "width": page_width,
                                            "height": page_height,
                                            "normalized": {
                                                "x0": 0.0,
                                                "y0": 0.0,
                                                "x1": 1.0,
                                                "y1": 1.0,
                                                "width": 1.0,
                                                "height": 1.0,
                                            },
                                        },
                                        "extraction_method": "xobject",
                                        "xref": xref,
                                    }
                                    svgs.append(svg_data)

                            except Exception as e:
                                self.logger.debug(f"Failed to extract xobject {i} from page {page_number}: {e}")
                                continue

                except Exception as e:
                    self.logger.debug(f"Xobject inspection failed for page {page_number}: {e}")

            # Log extraction summary
            if svgs:
                methods = [s["extraction_method"] for s in svgs]
                method_counts = {m: methods.count(m) for m in set(methods)}
                self.logger.info(f"Page {page_number}: Extracted {len(svgs)} SVGs using methods: {method_counts}")

                # Log bounding box information for debugging
                for i, svg in enumerate(svgs):
                    bbox = svg["bounding_box"]
                    self.logger.debug(
                        f"  SVG {i+1}: {bbox['width']:.1f}x{bbox['height']:.1f} at "
                        f"({bbox['x0']:.1f},{bbox['y0']:.1f}) - {svg['extraction_method']}"
                    )

        except Exception as e:
            self.logger.warning(f"Failed to extract SVGs from page {page_number}: {e}")

        return svgs

    def _convert_svg_to_png(self, svg_content: str) -> bytes | None:
        """
        Convert SVG content to PNG bytes

        Args:
            svg_content: SVG content as string

        Returns:
            PNG bytes or None if conversion failed
        """
        try:
            # Convert string to bytes
            svg_bytes = svg_content.encode("utf-8")

            # Create SVG drawing
            drawing = svg2rlg(io.BytesIO(svg_bytes))

            if drawing is None:
                self.logger.info("SVG parsing returned no drawing object; PNG derivative unavailable")
                return None

            # Render to PNG bytes directly
            png_bytes = renderPM.drawToString(drawing, fmt="PNG", dpi=self.dpi)

            # Scale if needed
            if self.max_dimension > 0:
                png_bytes = self._scale_png_if_needed(png_bytes)

            self.logger.debug(f"Converted SVG to PNG ({len(png_bytes)} bytes)")
            return png_bytes

        except Exception as e:
            self.logger.info("SVG to PNG conversion failed; preserving SVG without PNG derivative")
            self.logger.debug(
                "SVG conversion error details: type=%s message=%s svg_size=%s",
                type(e).__name__,
                str(e),
                len(svg_content) if svg_content else 0,
            )
            return None

    def _render_svg_region_with_pymupdf(self, doc: "fitz.Document", svg_data: dict[str, Any]) -> bytes | None:
        """
        Fallback: render the SVG's bounding box region from the PDF page as PNG using PyMuPDF.
        Used when svglib fails (e.g. "Unsupported shape type Group for clipping").
        """
        try:
            page_number = svg_data.get("page_number")
            bbox = svg_data.get("bounding_box") or {}
            x0 = bbox.get("x0", 0)
            y0 = bbox.get("y0", 0)
            x1 = bbox.get("x1")
            y1 = bbox.get("y1")
            if page_number is None or x1 is None or y1 is None:
                return None
            page = doc[page_number - 1]  # 1-based to 0-based
            rect = fitz.Rect(x0, y0, x1, y1)
            if rect.is_empty or rect.is_infinite:
                return None
            pix = page.get_pixmap(clip=rect, dpi=min(self.dpi, 150))  # cap DPI for large regions
            png_bytes = pix.tobytes("png")
            if self.max_dimension > 0:
                png_bytes = self._scale_png_if_needed(png_bytes)
            self.logger.debug(
                "SVG→PNG fallback via PyMuPDF for page %s (clip %.0fx%.0f)",
                page_number,
                rect.width,
                rect.height,
            )
            return png_bytes
        except Exception as e:
            self.logger.debug("PyMuPDF SVG-region fallback failed: %s", e)
            return None

    def _scale_png_if_needed(self, png_bytes: bytes) -> bytes:
        """
        Scale PNG if it exceeds maximum dimensions

        Args:
            png_bytes: Original PNG bytes

        Returns:
            Scaled PNG bytes
        """
        try:
            # Open image to check dimensions
            with Image.open(io.BytesIO(png_bytes)) as img:
                width, height = img.size

                # Check if scaling is needed
                if width <= self.max_dimension and height <= self.max_dimension:
                    return png_bytes

                # Calculate scaling factor
                scale_factor = min(self.max_dimension / width, self.max_dimension / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)

                # Scale image
                scaled_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Convert back to bytes
                buffer = io.BytesIO()
                try:
                    scaled_img.save(buffer, format="PNG", dpi=(self.dpi, self.dpi))
                    scaled_bytes = buffer.getvalue()
                finally:
                    buffer.close()

                self.logger.debug(
                    f"Scaled PNG from {width}x{height} to {new_width}x{new_height} " f"({len(scaled_bytes)} bytes)"
                )

                return scaled_bytes

        except Exception as e:
            self.logger.warning(f"Failed to scale PNG: {e}")
            return png_bytes

    def _upload_svg_to_storage(self, svg_data: dict[str, Any]) -> dict[str, Any]:
        """
        Upload original SVG content and optionally keep inline copy for small payloads.

        Args:
            svg_data: SVG extraction record

        Returns:
            Dictionary with svg_storage_url/original_svg_content/svg_file_hash metadata
        """
        svg_content = svg_data.get("svg_content") or ""
        svg_size = len(svg_content.encode("utf-8"))
        inline_threshold = self.svg_inline_storage_threshold_kb * 1024
        original_svg_content = svg_content if svg_size <= inline_threshold else None

        storage_result: dict[str, Any] = {
            "svg_storage_url": None,
            "original_svg_content": original_svg_content,
            "svg_file_hash": None,
        }

        if not self.storage_service or not hasattr(self.storage_service, "upload_svg_file"):
            self.logger.info("Storage service does not support upload_svg_file; SVG URL will be empty")
            return storage_result

        try:
            metadata = {
                "document_id": svg_data.get("document_id", ""),
                "page_number": svg_data.get("page_number"),
                "graphic_index": svg_data.get("graphic_index"),
                "svg_size": svg_data.get("svg_size", svg_size),
            }
            upload_filename = svg_data.get("filename", f"svg_{uuid4()}.svg")

            coro = self.storage_service.upload_svg_file(
                content=svg_content,
                filename=upload_filename,
                bucket_type="document_images",
                metadata={k: v for k, v in metadata.items() if v is not None},
            )
            # Reuse the running event loop if available (set by process()); otherwise fall back
            loop = getattr(self, "_event_loop", None)
            if loop and loop.is_running():
                future = concurrent.futures.Future()

                def _done(f):
                    try:
                        future.set_result(f.result())
                    except Exception as exc:
                        future.set_exception(exc)

                asyncio.run_coroutine_threadsafe(coro, loop).add_done_callback(_done)
                upload_result = future.result(timeout=60)
            else:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    upload_result = new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            storage_result["svg_storage_url"] = (
                upload_result.get("url") or upload_result.get("public_url") or upload_result.get("storage_url")
            )
            storage_result["svg_file_hash"] = upload_result.get("file_hash")
        except Exception as e:
            self.logger.warning(
                "Failed to upload SVG to storage (page=%s file=%s): %s",
                svg_data.get("page_number"),
                svg_data.get("filename"),
                e,
            )

        return storage_result

    def _queue_svg_images(self, document_id: UUID, svgs: list[dict[str, Any]], context) -> int:
        """
        Queue SVG images for storage, preserving SVG and optional PNG derivative

        Args:
            document_id: Document UUID
            svgs: List of SVG data with storage metadata and optional PNG bytes
            context: Processing context

        Returns:
            Number of images queued
        """
        queued_count = 0

        for svg_data in svgs:
            try:
                png_bytes = svg_data.get("png_bytes")
                has_png_derivative = png_bytes is not None
                svg_storage_url = svg_data.get("svg_storage_url")
                inline_svg = svg_data.get("original_svg_content")

                # Create payload for processing queue
                payload = {
                    "artifact_type": "image",
                    "document_id": str(document_id),
                    "filename": (
                        svg_data["filename"].replace(".svg", ".png") if has_png_derivative else svg_data["filename"]
                    ),
                    "page_number": svg_data["page_number"],
                    "image_type": "vector_graphic",
                    "content": (base64.b64encode(png_bytes).decode("utf-8") if has_png_derivative else None),
                    "svg_storage_url": svg_storage_url,
                    "original_svg_content": inline_svg,
                    "is_vector_graphic": True,
                    "has_png_derivative": has_png_derivative,
                    "metadata": {
                        "svg_size": svg_data["svg_size"],
                        "original_format": "svg",
                        "conversion_dpi": self.dpi,
                        "has_png_derivative": has_png_derivative,
                        "svg_storage_url": svg_storage_url,
                        "is_vector_graphic": True,
                        "extracted_from_page": svg_data["page_number"],
                    },
                }

                # Insert into processing queue using adapter method
                stage_payload = {
                    "document_id": str(document_id),
                    "stage": "storage",
                    "artifact_type": "image",
                    "status": "pending",
                    "payload": payload,
                }

                # Use adapter method if available.
                # _queue_svg_images läuft in einem Worker-Thread (run_in_executor),
                # deshalb planen wir die Coroutine threadsicher auf dem Haupt-Event-Loop ein.
                if hasattr(self.database_service, "create_svg_queue_entry"):
                    import asyncio

                    main_loop = getattr(self, "_event_loop", None)
                    if not isinstance(main_loop, asyncio.AbstractEventLoop):
                        self.logger.warning(
                            "No main event loop recorded on SVGProcessor; skipping SVG queue entry for %s",
                            svg_data["filename"],
                        )
                    elif main_loop.is_closed():
                        self.logger.warning(
                            "Main event loop is closed; skipping SVG queue entry for %s",
                            svg_data["filename"],
                        )
                    elif not main_loop.is_running():
                        self.logger.warning(
                            "Main event loop is not running; skipping SVG queue entry for %s",
                            svg_data["filename"],
                        )
                    else:
                        try:
                            fut = asyncio.run_coroutine_threadsafe(
                                self.database_service.create_svg_queue_entry(stage_payload),
                                main_loop,
                            )
                            fut.result()  # block im Worker-Thread, bis Eintrag erstellt ist
                            queued_count += 1
                            self.logger.debug(f"Queued SVG image: {svg_data['filename']}")
                        except RuntimeError as loop_exc:
                            self.logger.warning(
                                "Event loop unavailable while queueing SVG image %s; skipping entry: %s",
                                svg_data["filename"],
                                loop_exc,
                            )
                        except Exception as loop_exc:
                            self.logger.error(
                                "Failed to enqueue SVG image %s: %s",
                                svg_data["filename"],
                                loop_exc,
                            )
                else:
                    self.logger.warning("Database service does not support SVG queuing")

            except Exception as e:
                self.logger.error(f"Failed to queue SVG image {svg_data['filename']}: {e}")

        self.logger.info(f"Queued {queued_count} SVG images for storage")
        return queued_count

    def get_required_inputs(self) -> list[str]:
        """Get required inputs for SVG processing"""
        return ["pdf_path"]

    def get_outputs(self) -> list[str]:
        """Get outputs produced by SVG processing"""
        return ["svg_images_queued"]

    def get_resource_requirements(self) -> dict[str, Any]:
        """Get resource requirements"""
        return {
            "cpu_intensive": True,  # SVG conversion can be CPU intensive
            "memory_intensive": True,  # Large SVGs require memory
            "gpu_required": False,
            "estimated_ram_gb": 2.0,
            "estimated_gpu_gb": 0.0,
            "parallel_safe": False,  # Sequential processing is better for consistency
        }
