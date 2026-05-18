"""Storage Processor - Persist generated assets to storage and database."""

from __future__ import annotations

import io
import os
from pathlib import Path

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage


def _to_jpeg(content_bytes: bytes, quality: int = 85) -> tuple[bytes, str]:
    """Convert image bytes to JPEG with a white background.

    Raster images (PNG/GIF/etc.) are already converted to JPEG by ImageProcessor
    at extraction time, so this function now only handles SVGs from SVGProcessor.
    Already-JPEG and unrecognised formats are returned unchanged.

    Returns (jpeg_bytes, new_filename_extension) where extension is '.jpg'
    on success or '' when the content was unchanged.
    """
    try:
        is_jpeg = content_bytes[:2] == b"\xff\xd8"
        if is_jpeg:
            return content_bytes, ""

        is_svg = content_bytes.lstrip()[:5].lower().startswith(b"<svg") or content_bytes[:4] == b"\xef\xbb\xbf"
        if is_svg:
            # Rasterise SVG → JPEG using svglib + reportlab
            try:
                import tempfile

                from reportlab.graphics import renderPM
                from svglib.svglib import svg2rlg

                with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
                    tf.write(content_bytes)
                    tmp_path = tf.name
                try:
                    drawing = svg2rlg(tmp_path)
                finally:
                    os.unlink(tmp_path)

                if drawing and drawing.width > 0 and drawing.height > 0:
                    buf = io.BytesIO()
                    renderPM.drawToFile(drawing, buf, fmt="JPEG", bg=0xFFFFFF, dpi=150)
                    if buf.tell() > 0:
                        return buf.getvalue(), ".jpg"
            except Exception:
                pass  # Fall through — return original SVG unchanged
            return content_bytes, ""

        # Fallback: try PIL for any unexpected raster format
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(content_bytes))
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
            return buf.getvalue(), ".jpg"
        except Exception:
            pass

        return content_bytes, ""
    except Exception:
        return content_bytes, ""


class StorageProcessor(BaseProcessor):
    """Stage 8 processor responsible for persisting generated artifacts."""

    def __init__(self, database_service=None, storage_service=None, ai_service=None):
        super().__init__(name="storage_processor")
        self.stage = Stage.STORAGE
        self.database_service = database_service
        self.storage_service = storage_service
        self.ai_service = ai_service  # reserved for future use

        if not self.database_service:
            self.logger.warning("StorageProcessor initialized without database service")
        if not self.storage_service:
            self.logger.warning("StorageProcessor initialized without object storage service")

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Store pending artifacts for the given document."""
        document_id = getattr(context, "document_id", None)
        if not document_id:
            raise ValueError("Processing context must include 'document_id'")

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            try:
                images = getattr(context, "images", None) or []
                if images:
                    stored = await self._store_images_from_context(context, adapter)
                    return self._create_result(
                        success=True,
                        message="Storage stage completed",
                        data={"saved_items": stored, "errors": []},
                    )

                adapter.info("No pending artifacts to store")
                return self._create_result(True, "No pending artifacts", {"saved_items": 0})
            except Exception as exc:
                return self._create_result(False, f"Storage stage failed: {exc}", {})

    async def _store_images_from_context(self, context, adapter) -> int:
        if not self.storage_service:
            adapter.debug("Storage service not configured - skipping image upload")
            return 0

        images = getattr(context, "images", None) or []
        if not images:
            return 0

        stored = 0
        document_id = str(getattr(context, "document_id"))
        output_dir = getattr(context, "output_dir", None)

        for index, image in enumerate(images):
            image_id = image.get("id")
            if not image_id:
                continue

            temp_path = image.get("temp_path") or image.get("path")
            if not temp_path:
                continue

            path_obj = Path(temp_path)
            if not path_obj.exists():
                continue

            with open(path_obj, "rb") as fp:
                content_bytes = fp.read()

            original_filename = image.get("filename") or path_obj.name

            # Convert PNG/GIF/RGBA images to JPEG with white background so they
            # render correctly in dark-mode UIs.
            jpeg_bytes, new_ext = _to_jpeg(content_bytes)
            if new_ext:
                content_bytes = jpeg_bytes
                stem = Path(original_filename).stem
                original_filename = stem + new_ext
                image["filename"] = original_filename
                image["format"] = "jpeg"
                metadata_format = "jpeg"
            else:
                metadata_format = image.get("format")

            metadata = {
                "document_id": document_id,
                "image_id": str(image_id),
                "page_number": image.get("page_number"),
                "image_index": int(image.get("image_index") or index),
                "width": image.get("width"),
                "height": image.get("height"),
                "format": metadata_format,
                "extracted_at": image.get("extracted_at"),
            }

            result = await self.storage_service.upload_image(
                content=content_bytes,
                filename=original_filename,
                bucket_type="document_images",
                metadata={k: v for k, v in metadata.items() if v is not None},
            )

            if not result.get("success"):
                continue

            # Use presigned URL when configured (MinIO private buckets); else public URL
            use_presigned = os.getenv("OBJECT_STORAGE_USE_PRESIGNED_URLS", "false").lower() == "true"
            presigned_url = result.get("presigned_url")
            storage_url = (
                presigned_url
                if use_presigned and presigned_url
                else result.get("url") or result.get("public_url") or result.get("storage_url")
            )
            storage_path = result.get("storage_path") or result.get("key")
            file_hash = result.get("file_hash")

            db_filename = storage_path or original_filename

            image["storage_url"] = storage_url
            image["storage_path"] = storage_path
            image["file_hash"] = file_hash
            if presigned_url:
                image["presigned_url"] = presigned_url

            if self.database_service:
                if not storage_url:
                    adapter.warning(
                        "Skipping DB insert for image %s because storage_url is missing (storage_path=%s)",
                        image_id,
                        storage_path,
                    )
                    continue
                await self.database_service.execute_query(
                    """
                    INSERT INTO krai_content.images (
                        id, document_id, filename, original_filename,
                        storage_path, storage_url, file_size, image_format,
                        svg_storage_url, original_svg_content, is_vector_graphic, has_png_derivative,
                        width_px, height_px, page_number, image_index,
                        image_type, ai_description, ai_confidence,
                        contains_text,
                        ocr_text, ocr_confidence,
                        manual_description,
                        tags,
                        file_hash,
                        figure_number, figure_context
                    ) VALUES (
                        $1::uuid, $2::uuid, $3, $4,
                        $5, $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14, $15, $16,
                        $17, $18, $19,
                        $20,
                        $21, $22,
                        $23,
                        $24::text[],
                        $25,
                        $26, $27
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        storage_path = EXCLUDED.storage_path,
                        storage_url = EXCLUDED.storage_url,
                        svg_storage_url = EXCLUDED.svg_storage_url,
                        original_svg_content = EXCLUDED.original_svg_content,
                        is_vector_graphic = EXCLUDED.is_vector_graphic,
                        has_png_derivative = EXCLUDED.has_png_derivative,
                        file_hash = EXCLUDED.file_hash,
                        ai_description = EXCLUDED.ai_description,
                        ai_confidence = EXCLUDED.ai_confidence,
                        contains_text = EXCLUDED.contains_text,
                        ocr_text = EXCLUDED.ocr_text,
                        ocr_confidence = EXCLUDED.ocr_confidence,
                        manual_description = EXCLUDED.manual_description,
                        tags = EXCLUDED.tags,
                        figure_number = EXCLUDED.figure_number,
                        figure_context = EXCLUDED.figure_context,
                        updated_at = NOW()
                    """.strip(),
                    [
                        str(image_id),
                        document_id,
                        db_filename,
                        original_filename,
                        storage_path,
                        storage_url,
                        image.get("size_bytes"),
                        image.get("format"),
                        image.get("svg_storage_url") or image.get("metadata", {}).get("svg_storage_url"),
                        image.get("original_svg_content"),
                        bool(
                            image.get("is_vector_graphic")
                            or image.get("metadata", {}).get("is_vector_graphic")
                            or (str(image.get("format", "")).lower() == "svg")
                        ),
                        bool(
                            image.get("has_png_derivative")
                            if image.get("has_png_derivative") is not None
                            else image.get("metadata", {}).get("has_png_derivative", True)
                        ),
                        image.get("width"),
                        image.get("height"),
                        image.get("page_number"),
                        int(image.get("image_index") or index),
                        image.get("image_type") or image.get("type") or "diagram",
                        image.get("ai_description"),
                        image.get("ai_confidence"),
                        bool(image.get("contains_text") or False),
                        image.get("ocr_text"),
                        image.get("ocr_confidence"),
                        image.get("manual_description"),
                        image.get("tags") or [],
                        file_hash,
                        image.get("figure_number"),
                        image.get("figure_context"),
                    ],
                )

            stored += 1

        if os.getenv("IMAGE_PROCESSOR_CLEANUP", "1") != "0" and output_dir:
            try:
                output_path = Path(output_dir)
                if output_path.exists():
                    for item in output_path.iterdir():
                        if item.is_file():
                            item.unlink()
                    output_path.rmdir()
            except Exception:
                pass

        return stored

    def _create_result(self, success: bool, message: str, data: dict) -> ProcessingResult:
        """Create a processing result object using BaseProcessor helpers"""
        if success:
            return self.create_success_result(data=data, metadata={"message": message})
        error = ProcessingError(message, self.name, "STORAGE_ERROR")
        return self.create_error_result(error=error, metadata={})
