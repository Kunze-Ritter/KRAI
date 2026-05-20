"""
Image Storage Processor V2 - WITH HASH DEDUPLICATION

Handles EXTRACTED IMAGE storage on S3-compatible storage with:
- MD5 hash-based deduplication (no duplicate uploads!)
- Flat storage structure: {hash}.{extension}
- Database tracking in krai_content.images
- Automatic metadata extraction
- Integration with database adapter
- Supports MinIO and S3-compatible storage (AWS S3, Wasabi, Backblaze B2)

Storage Structure:
    OLD: documents/{doc_id}/images/page_0001_diagram_img.png
    NEW: a1b2c0d0f.png (just the hash!)

Deduplication Flow:
    1. Calculate MD5 hash of image
    2. Check if hash exists in DB
    3. If exists: Return existing URL (skip upload)
    4. If new: Upload to object storage + Insert to DB
"""

import os
from pathlib import Path as FilePath

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*args, **kwargs):
        return None  # Fallback accepts any args


# Load .env
env_path = FilePath(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import boto3
from botocore.client import Config

from .logger import get_logger


class ImageStorageProcessor:
    """
    Image Storage with Hash-based Deduplication

    Features:
    - MD5 hash calculation
    - Automatic deduplication
    - S3-compatible storage (MinIO, S3, R2, etc.)
    - Database tracking (krai_content.images)
    - Flat structure (no folders)
    """

    def __init__(self, database_adapter=None):
        """
        Initialize image storage processor

        Args:
            database_adapter: Database adapter for DB tracking
        """
        self.logger = get_logger()
        self.db_client = database_adapter

        # Object Storage Configuration
        self.access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY")
        self.secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY")
        self.endpoint_url = os.getenv("OBJECT_STORAGE_ENDPOINT")
        if not self.endpoint_url:
            raise ValueError("OBJECT_STORAGE_ENDPOINT must be set in .env")
        self.bucket_name = os.getenv("OBJECT_STORAGE_BUCKET_DOCUMENTS")
        self.public_url = os.getenv("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS")

        # Initialize S3-compatible client
        self.storage_client = None
        if all([self.access_key, self.secret_key, self.endpoint_url, self.bucket_name]):
            try:
                self.storage_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    config=Config(signature_version="s3v4"),
                    region_name="auto",
                )
                self.logger.info("S3-compatible storage client initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize storage client: {e}")
        else:
            self.logger.warning("Object storage credentials incomplete - storage disabled")

    def is_configured(self) -> bool:
        """Check if object storage and database are configured"""
        return self.storage_client is not None and self.db_client is not None

    def calculate_image_hash(self, image_path: Path) -> str:
        """
        Calculate MD5 hash of image file

        Args:
            image_path: Path to image file

        Returns:
            MD5 hash as hex string
        """
        md5_hash = hashlib.md5(usedforsecurity=False)

        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)

        return md5_hash.hexdigest()

    async def check_image_exists(self, file_hash: str) -> dict[str, Any] | None:
        """
        Check if image with this hash already exists in DB

        Args:
            file_hash: MD5 hash of image

        Returns:
            Existing image record or None
        """
        if not self.db_client:
            return None

        try:
            # Use DatabaseAdapter interface method
            return await self.db_client.get_image_by_hash(file_hash)

        except Exception as e:
            self.logger.debug(f"Error checking image existence: {e}")
            return None

    async def upload_image(
        self,
        image_path: Path,
        document_id: UUID,
        page_number: int,
        image_type: str = "diagram",
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Upload single image with deduplication

        Args:
            image_path: Path to image file
            document_id: Document UUID
            page_number: Page number
            image_type: Type of image
            metadata: Additional metadata

        Returns:
            Result dict with storage_url
        """
        if not self.is_configured():
            return {"success": False, "error": "Storage not configured", "storage_url": None, "deduplicated": False}

        try:
            # 1. Calculate hash
            file_hash = self.calculate_image_hash(image_path)

            # 2. Check if already exists
            existing = await self.check_image_exists(file_hash)

            if existing:
                # Image already exists - just create new mapping
                self.logger.debug(f"Image deduplicated: {file_hash[:8]}... (already exists)")

                # Create new document_image mapping if needed
                return {
                    "success": True,
                    "storage_url": existing["storage_url"],
                    "storage_path": existing["storage_path"],
                    "file_hash": file_hash,
                    "deduplicated": True,
                    "existing_id": existing["id"],
                }

            # 3. New image - upload to object storage
            extension = image_path.suffix.lstrip(".")
            is_svg = extension.lower() == "svg"
            has_png_derivative = bool(metadata.get("has_png_derivative", not is_svg)) if metadata else (not is_svg)
            storage_path = f"svg/{file_hash}.svg" if is_svg else f"{file_hash}.{extension}"

            # Upload to object storage
            with open(image_path, "rb") as f:
                self.storage_client.upload_fileobj(
                    f,
                    self.bucket_name,
                    storage_path,
                    ExtraArgs={
                        "Metadata": {
                            "document-id": str(document_id),
                            "page-number": str(page_number),
                            "image-type": image_type,
                            "file-hash": file_hash,
                            "is-vector-graphic": str(is_svg).lower(),
                            "has-png-derivative": str(has_png_derivative).lower(),
                            "upload-timestamp": datetime.utcnow().isoformat(),
                        },
                        "ContentType": (
                            "image/svg+xml" if is_svg else (mimetypes.guess_type(image_path)[0] or "image/png")
                        ),
                    },
                )

            # Generate public URL
            if self.public_url:
                storage_url = f"{self.public_url}/{storage_path}"
            else:
                storage_url = f"{self.endpoint_url}/{self.bucket_name}/{storage_path}"

            svg_storage_url = storage_url if is_svg else (metadata.get("svg_storage_url") if metadata else None)
            if is_svg and metadata and metadata.get("png_storage_url"):
                # Keep storage_url backward-compatible with raster consumers when a PNG derivative exists.
                storage_url = metadata["png_storage_url"]

            # 4. Insert to database using DatabaseAdapter
            from backend.core.data_models import ImageModel

            image_model = ImageModel(
                document_id=str(document_id),
                filename=storage_path,
                original_filename=image_path.name,
                storage_path=storage_path,
                storage_url=storage_url,
                svg_storage_url=svg_storage_url,
                original_svg_content=metadata.get("original_svg_content") if metadata else None,
                is_vector_graphic=is_svg,
                has_png_derivative=has_png_derivative,
                file_hash=file_hash,
                file_size=image_path.stat().st_size,
                image_format=extension.lower(),
                page_number=page_number,
                image_type=image_type,
                width_px=metadata.get("width") if metadata else None,
                height_px=metadata.get("height") if metadata else None,
                ai_description=metadata.get("ai_description") if metadata else None,
                ai_confidence=metadata.get("ai_confidence") if metadata else None,
                contains_text=metadata.get("contains_text") if metadata else None,
                ocr_text=metadata.get("ocr_text") if metadata else None,
                ocr_confidence=metadata.get("ocr_confidence") if metadata else None,
            )

            if is_svg and hasattr(self.db_client, "create_image_with_svg"):
                db_id = await self.db_client.create_image_with_svg(image_model)
            else:
                db_id = await self.db_client.create_image(image_model)

            self.logger.debug(f"Uploaded new image: {file_hash[:8]}... -> {storage_path}")

            return {
                "success": True,
                "storage_url": storage_url,
                "storage_path": storage_path,
                "file_hash": file_hash,
                "deduplicated": False,
                "db_id": db_id,
            }

        except Exception as e:
            self.logger.error(f"Failed to upload image: {e}")
            return {"success": False, "error": str(e), "storage_url": None, "deduplicated": False}

    async def upload_images(
        self, document_id: UUID, images: list[dict[str, Any]], document_type: str = "service_manual"
    ) -> dict[str, Any]:
        """
        Upload multiple images with deduplication

        Args:
            document_id: Document UUID
            images: List of dicts with 'path', 'page_num', 'type', etc.
            document_type: Type of document

        Returns:
            Dict with upload results
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Storage not configured",
                "uploaded_count": 0,
                "deduplicated_count": 0,
                "urls": [],
            }

        uploaded_count = 0
        deduplicated_count = 0
        failed_count = 0
        urls = []

        self.logger.info(f"Uploading {len(images)} images to object storage (with deduplication)...")

        for idx, image_info in enumerate(images):
            image_path = Path(image_info.get("path"))

            if not image_path.exists():
                failed_count += 1
                continue

            # Upload with deduplication
            result = await self.upload_image(
                image_path=image_path,
                document_id=document_id,
                page_number=image_info.get("page_num", 0),
                image_type=image_info.get("type", "diagram"),
                metadata=image_info.get("metadata"),
            )

            if result["success"]:
                if result["deduplicated"]:
                    deduplicated_count += 1
                else:
                    uploaded_count += 1

                urls.append(
                    {
                        "page_num": image_info.get("page_num"),
                        "type": image_info.get("type"),
                        "url": result["storage_url"],
                        "hash": result["file_hash"],
                        "deduplicated": result["deduplicated"],
                    }
                )
            else:
                failed_count += 1

            # Progress logging every 500 images
            if (idx + 1) % 500 == 0:
                self.logger.info(
                    f"Progress: {idx + 1}/{len(images)} "
                    f"(Uploaded: {uploaded_count}, Deduplicated: {deduplicated_count})"
                )

        total_processed = uploaded_count + deduplicated_count

        self.logger.success(
            f"Processed {total_processed}/{len(images)} images "
            f"(New: {uploaded_count}, Deduplicated: {deduplicated_count}, Failed: {failed_count})"
        )

        return {
            "success": failed_count == 0,
            "uploaded_count": uploaded_count,
            "deduplicated_count": deduplicated_count,
            "failed_count": failed_count,
            "total_processed": total_processed,
            "urls": urls,
        }

    async def get_storage_stats(self) -> dict[str, Any]:
        """
        Get storage statistics from DB

        Returns:
            Dict with statistics
        """
        if not self.db_client:
            return {}

        try:
            # Total images count
            total_query = "SELECT COUNT(*) as count FROM krai_content.images"
            total_result = await self.db_client.fetch_one(total_query, [])
            total_images = total_result["count"] if total_result else 0

            # Unique hashes (deduplicated images)
            unique_query = "SELECT COUNT(DISTINCT file_hash) as count FROM krai_content.images"
            unique_result = await self.db_client.fetch_one(unique_query, [])
            unique_hashes = unique_result["count"] if unique_result else 0

            # Total size
            size_query = "SELECT COALESCE(SUM(file_size), 0) as total_size FROM krai_content.images"
            size_result = await self.db_client.fetch_one(size_query, [])
            total_size = size_result["total_size"] if size_result else 0

            return {
                "total_images": total_images,
                "unique_images": unique_hashes,
                "deduplication_rate": round((1 - unique_hashes / max(total_images, 1)) * 100, 2),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
            }

        except Exception as e:
            self.logger.debug(f"Error getting storage stats: {e}")
            return {}

    def cleanup_orphaned_images(self) -> dict[str, Any]:
        """
        Cleanup images not referenced by any document

        Returns:
            Cleanup results
        """
        # TODO: Implement cleanup logic
        pass


# Convenience function
async def upload_images_to_storage(
    document_id: UUID, images: list[dict[str, Any]], database_adapter=None
) -> dict[str, Any]:
    """
    Convenience function to upload images to object storage

    Args:
        document_id: Document UUID
        images: List of image dicts
        database_adapter: Database adapter

    Returns:
        Upload results
    """
    processor = ImageStorageProcessor(database_adapter=database_adapter)
    return await processor.upload_images(document_id, images)
