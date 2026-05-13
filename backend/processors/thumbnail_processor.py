"""
Thumbnail Processor for KRAI Engine

Generates document thumbnails using PyMuPDF page rendering.
Creates PNG thumbnails from PDF first pages and uploads to storage.
"""

import io
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingResult
from backend.services.object_storage_service import ObjectStorageService


class ThumbnailProcessor(BaseProcessor):
    """
    Processor for generating document thumbnails from PDF files.

    Renders the first page of a PDF to a pixmap, resizes to thumbnail dimensions,
    and uploads to object storage. Updates document record with thumbnail URL.
    """

    def __init__(
        self,
        database_service,
        storage_service: ObjectStorageService,
        default_size: tuple = (300, 400),
        default_page: int = 0,
    ):
        """
        Initialize ThumbnailProcessor

        Args:
            database_service: Database service for document updates
            storage_service: Storage service for thumbnail uploads
            default_size: Default thumbnail size (width, height)
            default_page: Default page to render (0-indexed)
        """
        super().__init__("thumbnail")
        self.database_service = database_service
        self.storage_service = storage_service
        self.default_size = default_size
        self.default_page = default_page
        self.logger = logging.getLogger(__name__)

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Generate thumbnail for document

        Args:
            context: Processing context containing document_id and file_path

        Returns:
            ProcessingResult with thumbnail URL and metadata
        """
        try:
            # Extract parameters from context
            document_id = context.document_id
            file_path = context.file_path
            thumbnail_size = context.processing_config.get("size", self.default_size)
            page_number = context.processing_config.get("page", self.default_page)

            self.logger.info(f"Generating thumbnail for document {document_id} from {file_path}")

            # Validate inputs
            if not document_id:
                return self.create_error_result(
                    ProcessingError("Document ID is required", "thumbnail", "MISSING_DOCUMENT_ID")
                )

            if not file_path or not Path(file_path).exists():
                return self.create_error_result(
                    ProcessingError(f"File not found: {file_path}", "thumbnail", "FILE_NOT_FOUND")
                )

            # Generate thumbnail
            thumbnail_result = await self._generate_thumbnail(file_path, thumbnail_size, page_number)

            if not thumbnail_result["success"]:
                return self.create_error_result(
                    ProcessingError(thumbnail_result["error"], "thumbnail", "GENERATION_FAILED")
                )

            # Upload to storage
            upload_result = await self._upload_thumbnail(thumbnail_result["image_bytes"], document_id, thumbnail_size)

            if not upload_result["success"]:
                return self.create_error_result(ProcessingError(upload_result["error"], "thumbnail", "UPLOAD_FAILED"))

            # Update document record
            await self._update_document_thumbnail(document_id, upload_result["thumbnail_url"])

            self.logger.info(f"Thumbnail generated successfully: {upload_result['thumbnail_url']}")

            return self.create_success_result(
                data={
                    "thumbnail_url": upload_result["thumbnail_url"],
                    "size": thumbnail_size,
                    "file_size": upload_result["file_size"],
                    "page_rendered": page_number,
                },
                metadata={
                    "document_id": document_id,
                    "file_path": file_path,
                    "page_number": page_number,
                    "thumbnail_size": thumbnail_size,
                },
            )

        except Exception as e:
            self.logger.error(f"Thumbnail generation failed: {e!s}")
            return self.create_error_result(
                ProcessingError(f"Thumbnail generation failed: {e!s}", "thumbnail", "UNEXPECTED_ERROR")
            )

    async def _generate_thumbnail(self, file_path: str, size: tuple, page_number: int) -> dict[str, Any]:
        """
        Generate thumbnail from PDF page

        Args:
            file_path: Path to PDF file
            size: Thumbnail size (width, height)
            page_number: Page number to render (0-indexed)

        Returns:
            Dict with success status and image bytes or error
        """
        try:
            # Open PDF
            doc = fitz.open(file_path)

            # Validate page number
            if page_number >= len(doc):
                doc.close()
                return {"success": False, "error": f"Page {page_number} not found (PDF has {len(doc)} pages)"}

            # Get page
            page = doc[page_number]

            # Render page to pixmap with 2x zoom for quality
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_data))

            # Resize to thumbnail dimensions
            pil_image = pil_image.resize(size, Image.Resampling.LANCZOS)

            # Convert to bytes
            img_byte_array = io.BytesIO()
            pil_image.save(img_byte_array, format="PNG")
            image_bytes = img_byte_array.getvalue()

            # Cleanup
            doc.close()
            img_byte_array.close()

            return {"success": True, "image_bytes": image_bytes, "original_size": (pix.width, pix.height)}

        except Exception as e:
            self.logger.error(f"PDF rendering failed: {e!s}")
            return {"success": False, "error": f"PDF rendering failed: {e!s}"}

    async def _upload_thumbnail(self, image_bytes: bytes, document_id: str, size: tuple) -> dict[str, Any]:
        """
        Upload thumbnail to storage

        Args:
            image_bytes: Thumbnail image bytes
            document_id: Document ID for filename
            size: Thumbnail size for filename

        Returns:
            Dict with success status and thumbnail URL or error
        """
        try:
            # Generate filename
            filename = f"thumbnails/{document_id}_{'x'.join(map(str, size))}.png"

            # Upload to storage
            thumbnail_url = await self.storage_service.upload_file(
                file_data=image_bytes, filename=filename, content_type="image/png"
            )

            if not thumbnail_url:
                return {"success": False, "error": "Failed to upload thumbnail to storage"}

            return {"success": True, "thumbnail_url": thumbnail_url, "file_size": len(image_bytes)}

        except Exception as e:
            self.logger.error(f"Thumbnail upload failed: {e!s}")
            return {"success": False, "error": f"Thumbnail upload failed: {e!s}"}

    async def _update_document_thumbnail(self, document_id: str, thumbnail_url: str):
        """
        Update document record with thumbnail URL

        Args:
            document_id: Document ID
            thumbnail_url: URL of generated thumbnail
        """
        try:
            await self.database_service.update_document(
                document_id=document_id, updates={"thumbnail_url": thumbnail_url}
            )

        except Exception as e:
            self.logger.error(f"Failed to update document thumbnail: {e!s}")
            # Don't fail the entire process if database update fails
            pass
