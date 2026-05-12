"""
Object Storage Service for KR-AI-Engine
Generic S3-compatible object storage service
Supports MinIO and S3-compatible storage (AWS S3, Wasabi, Backblaze B2)
Configurable via environment variables for vendor-agnostic storage
"""

import hashlib
import json
import logging
import mimetypes
import os
from datetime import UTC, datetime
from typing import Any

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    Config = None
    BOTO3_AVAILABLE = False


class ObjectStorageService:
    """
    Generic S3-compatible object storage service

    Handles image storage for KR-AI-Engine with configurable buckets:
    - Document images: Images extracted from documents
    - Error images: Defect detection images
    - Parts images: Parts catalog images

    Bucket names are configurable via environment variables.
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str,
        public_url_documents: str,
        public_url_error: str,
        public_url_parts: str,
        public_url_images: str = "",
        use_ssl: bool = True,
        region: str = "auto",
        bucket_documents: str | None = None,
        bucket_images: str | None = None,
        bucket_error: str | None = None,
        bucket_parts: str | None = None,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.use_ssl = use_ssl
        self.region = region
        self.public_urls = {
            "documents": public_url_documents,
            "images": public_url_images,
            "error": public_url_error,
            "parts": public_url_parts,
        }
        self.client = None
        self.logger = logging.getLogger("krai.storage")
        self._setup_logging()

        images_bucket_override = bucket_images or os.getenv("OBJECT_STORAGE_BUCKET_IMAGES")
        documents_bucket_name = bucket_documents or os.getenv("OBJECT_STORAGE_BUCKET_DOCUMENTS", "documents")

        if not images_bucket_override:
            images_bucket_override = "images"

        self._document_images_bucket_override = images_bucket_override
        self._documents_bucket_name = documents_bucket_name

        error_bucket = bucket_error or os.getenv("OBJECT_STORAGE_BUCKET_ERROR")
        parts_bucket = bucket_parts or os.getenv("OBJECT_STORAGE_BUCKET_PARTS")

        # Bucket configurations (only configure optional buckets when explicitly provided)
        self.buckets = {
            "documents": documents_bucket_name,
            "document_images": images_bucket_override,
        }

        if error_bucket:
            self.buckets["error_images"] = error_bucket

        if parts_bucket:
            self.buckets["parts_images"] = parts_bucket

        self.public_read_bucket_types = {
            bucket_type
            for bucket_type, public_url in {
                "documents": public_url_documents,
                "document_images": public_url_images,
                "error_images": public_url_error,
                "parts_images": public_url_parts,
            }.items()
            if public_url
        }

    def _setup_logging(self):
        """Setup logging for storage service"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - Storage - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    async def connect(self):
        """Connect to S3-compatible storage"""
        try:
            if not BOTO3_AVAILABLE:
                allow_mock = os.getenv("OBJECT_STORAGE_ALLOW_MOCK", "false").lower() == "true"
                if allow_mock:
                    self.logger.warning("Boto3 not available. Running in mock mode.")
                    return
                raise RuntimeError(
                    "boto3 is not installed - object storage uploads are disabled. "
                    "Install boto3 or set OBJECT_STORAGE_ALLOW_MOCK=true to run without uploads."
                )

            # Create S3 client
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
                config=Config(signature_version="s3v4"),
            )

            self.logger.info(f"Connected to S3-compatible storage at {self.endpoint_url}")

            # Ensure buckets exist
            await self._ensure_buckets_exist()
            await self._ensure_bucket_access_policies()

        except Exception as e:
            self.logger.error(f"Failed to connect to object storage: {e}")
            raise

    async def _ensure_buckets_exist(self):
        """Ensure all required buckets exist"""
        if self.client is None:
            self.logger.info("Skipping bucket creation (mock mode)")
            return

        for bucket_type, bucket_name in self.buckets.items():
            try:
                await self._create_bucket_if_not_exists(bucket_name)
                self.logger.info(f"Bucket {bucket_name} ready")
            except Exception as e:
                self.logger.error(f"Failed to ensure bucket {bucket_name}: {e}")
                raise

    async def _ensure_bucket_access_policies(self):
        """Ensure buckets behind configured public URLs are anonymously readable."""
        if self.client is None:
            return

        if os.getenv("OBJECT_STORAGE_AUTO_PUBLIC_READ", "true").lower() != "true":
            self.logger.info("Skipping public-read bucket policy enforcement")
            return

        for bucket_type, bucket_name in self.buckets.items():
            if bucket_type not in self.public_read_bucket_types:
                continue
            await self._set_public_read_policy(bucket_name)

    async def _set_public_read_policy(self, bucket_name: str):
        """Allow anonymous GetObject access for a bucket."""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                }
            ],
        }
        self.client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        self.logger.info("Applied public-read policy to bucket %s", bucket_name)

    async def _create_bucket_if_not_exists(self, bucket_name: str):
        """Create bucket if it doesn't exist"""
        try:
            if self.client is None:
                self.logger.info(f"Bucket {bucket_name} creation skipped (mock mode)")
                return

            self.client.head_bucket(Bucket=bucket_name)
            self.logger.debug(f"Bucket {bucket_name} already exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # Bucket doesn't exist, create it
                self.client.create_bucket(Bucket=bucket_name)
                self.logger.info(f"Created bucket {bucket_name}")
            else:
                raise

    def _generate_file_hash(self, content: bytes) -> str:
        """Generate SHA256 hash for file content"""
        return hashlib.sha256(content).hexdigest()

    def _generate_storage_path(self, file_hash: str, bucket_type: str = "document_images") -> str:
        """Generate storage path for an object."""
        prefix_map = {
            "documents": "documents",
            "document_images": "images",
            "error_images": "error",
            "parts_images": "parts",
        }
        bucket_name = None
        if hasattr(self, "buckets"):
            bucket_name = self.buckets.get(bucket_type)

        if bucket_name and hasattr(self, "buckets"):
            shared_bucket = sum(1 for name in self.buckets.values() if name == bucket_name) > 1
            if not shared_bucket:
                return file_hash

        prefix = prefix_map.get(bucket_type, "images")
        return f"{prefix}/{file_hash}"

    def _get_content_type(self, filename: str) -> str:
        """Get content type for file"""
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    def _resolve_base_url(self, bucket_type: str, bucket_name: str) -> str:
        """Resolve public base URL for a bucket type."""
        if bucket_type == "documents":
            base_url = self.public_urls["documents"]
        elif bucket_type == "document_images":
            base_url = self.public_urls.get("images") or self.public_urls["documents"]
        elif bucket_type == "error_images":
            base_url = self.public_urls.get("error", "")
        elif bucket_type == "parts_images":
            base_url = self.public_urls.get("parts", "")
        else:
            base_url = self.public_urls["documents"]

        if (
            bucket_type == "document_images"
            and self._document_images_bucket_override
            and not self.public_urls.get("images")
        ):
            base_url = ""

        if not base_url:
            base_url = f"{self.endpoint_url}/{bucket_name}"
        return base_url

    def _looks_like_svg(self, content: bytes, filename: str, metadata: dict[str, Any] | None = None) -> bool:
        """Detect SVG uploads by extension, metadata hints, or payload signature."""
        filename_lower = (filename or "").lower()
        if filename_lower.endswith(".svg"):
            return True

        metadata = metadata or {}
        format_hint = str(metadata.get("format", "")).lower()
        content_type_hint = str(metadata.get("content_type", "")).lower()
        if format_hint == "svg" or content_type_hint == "image/svg+xml":
            return True

        head = content[:256].lstrip().lower()
        return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)

    async def upload_svg_file(
        self,
        content: str | bytes,
        filename: str,
        bucket_type: str = "document_images",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upload SVG content with enforced SVG content type and deduplication."""
        svg_bytes = content.encode("utf-8") if isinstance(content, str) else content
        metadata = dict(metadata or {})
        metadata["format"] = "svg"
        metadata["content_type"] = "image/svg+xml"

        try:
            if self.client is None:
                allow_mock = os.getenv("OBJECT_STORAGE_ALLOW_MOCK", "false").lower() == "true"
                if not allow_mock:
                    raise RuntimeError(
                        "Object storage client is not connected. "
                        "Ensure boto3 is installed and connect() succeeded, or set OBJECT_STORAGE_ALLOW_MOCK=true."
                    )

                file_hash = self._generate_file_hash(svg_bytes)
                storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)
                bucket_name = self.buckets.get(bucket_type, "krai-documents")
                base_url = self._resolve_base_url(bucket_type, bucket_name)
                public_url = f"{base_url}/{storage_path}"
                return {
                    "success": True,
                    "bucket": bucket_name,
                    "key": storage_path,
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "url": public_url,
                    "storage_url": public_url,
                    "presigned_url": None,
                    "file_hash": file_hash,
                    "size": len(svg_bytes),
                    "content_type": "image/svg+xml",
                    "metadata": metadata,
                }

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]
            file_hash = self._generate_file_hash(svg_bytes)

            duplicate = await self.check_duplicate(file_hash, bucket_type)
            if duplicate:
                self.logger.info(f"Duplicate SVG found with hash {file_hash[:16]}...: {duplicate['key']}")
                dup_result = {
                    "success": True,
                    "file_hash": file_hash,
                    "storage_path": duplicate["key"],
                    "storage_url": duplicate["url"],
                    "url": duplicate["url"],
                    "bucket": duplicate["bucket"],
                    "is_duplicate": True,
                }
                try:
                    presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                    dup_result["presigned_url"] = self.client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": duplicate["bucket"], "Key": duplicate["key"]},
                        ExpiresIn=presigned_expiry,
                    )
                except Exception:
                    dup_result["presigned_url"] = None
                return dup_result

            storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)
            file_metadata = {
                "original_filename": filename,
                "file_hash": file_hash,
                "upload_timestamp": datetime.now(UTC).isoformat(),
                "content_type": "image/svg+xml",
            }
            for key, value in metadata.items():
                file_metadata[key] = str(value)

            self.client.put_object(
                Bucket=bucket_name,
                Key=storage_path,
                Body=svg_bytes,
                ContentType="image/svg+xml",
                Metadata=file_metadata,
            )

            presigned_url = None
            try:
                presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                presigned_url = self.client.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket_name, "Key": storage_path}, ExpiresIn=presigned_expiry
                )
            except Exception as presign_err:
                self.logger.debug("Failed to generate presigned URL: %s", presign_err)

            base_url = self._resolve_base_url(bucket_type, bucket_name)
            public_url = f"{base_url}/{storage_path}"
            self.logger.info(f"Uploaded SVG {filename} to {bucket_name}/{storage_path}")
            return {
                "success": True,
                "bucket": bucket_name,
                "key": storage_path,
                "storage_path": storage_path,
                "public_url": public_url,
                "url": public_url,
                "storage_url": public_url,
                "presigned_url": presigned_url,
                "file_hash": file_hash,
                "is_duplicate": False,
                "size": len(svg_bytes),
                "content_type": "image/svg+xml",
                "metadata": file_metadata,
            }
        except Exception as e:
            self.logger.error(f"Failed to upload SVG {filename}: {e}")
            raise

    async def upload_image(
        self,
        content: bytes,
        filename: str,
        bucket_type: str = "document_images",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload image to object storage

        Args:
            content: Image file content as bytes
            filename: Original filename
            bucket_type: Type of bucket (document_images, error_images, parts_images)
            metadata: Additional metadata

        Returns:
            Dict with storage information
        """
        if self._looks_like_svg(content, filename, metadata):
            return await self.upload_svg_file(
                content=content,
                filename=filename,
                bucket_type=bucket_type,
                metadata=metadata,
            )

        try:
            if self.client is None:
                allow_mock = os.getenv("OBJECT_STORAGE_ALLOW_MOCK", "false").lower() == "true"
                if not allow_mock:
                    raise RuntimeError(
                        "Object storage client is not connected. "
                        "Ensure boto3 is installed and connect() succeeded, or set OBJECT_STORAGE_ALLOW_MOCK=true."
                    )
                # Mock mode for testing
                file_hash = hashlib.sha256(content).hexdigest()
                storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)

                # Generate public URL based on bucket type
                if bucket_type == "document_images":
                    base_url = self.public_urls.get("images") or self.public_urls["documents"]
                elif bucket_type == "error_images":
                    base_url = self.public_urls.get("error", "")
                elif bucket_type == "parts_images":
                    base_url = self.public_urls.get("parts", "")
                else:
                    base_url = self.public_urls["documents"]

                bucket_name = self.buckets.get(bucket_type, "krai-documents")
                if (
                    bucket_type == "document_images"
                    and self._document_images_bucket_override
                    and not self.public_urls.get("images")
                ):
                    base_url = ""

                if not base_url:
                    base_url = f"{self.endpoint_url}/{bucket_name}"

                public_url = f"{base_url}/{storage_path}"

                result = {
                    "success": True,
                    "bucket": self.buckets.get(bucket_type, "krai-documents"),
                    "key": storage_path,
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "url": public_url,
                    "presigned_url": None,
                    "file_hash": file_hash,
                    "size": len(content),
                    "content_type": self._get_content_type(filename),
                    "metadata": metadata or {},
                }

                self.logger.info(f"Uploaded image {filename} to {bucket_type}/{storage_path} (mock)")
                return result

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]

            # Generate file hash for deduplication
            file_hash = self._generate_file_hash(content)

            # Check for duplicate file by hash
            duplicate = await self.check_duplicate(file_hash, bucket_type)
            if duplicate:
                self.logger.info(f"Duplicate file found with hash {file_hash[:16]}...: {duplicate['key']}")
                dup_result = {
                    "success": True,
                    "file_hash": file_hash,
                    "storage_path": duplicate["key"],
                    "storage_url": duplicate["url"],
                    "bucket": duplicate["bucket"],
                    "is_duplicate": True,
                }
                if self.client:
                    try:
                        presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                        dup_result["presigned_url"] = self.client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": duplicate["bucket"], "Key": duplicate["key"]},
                            ExpiresIn=presigned_expiry,
                        )
                    except Exception:
                        dup_result["presigned_url"] = None
                else:
                    dup_result["presigned_url"] = None
                return dup_result

            # Generate storage path
            storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)

            # Prepare metadata (all values must be strings for S3)
            file_metadata = {
                "original_filename": filename,
                "file_hash": file_hash,
                "upload_timestamp": datetime.now(UTC).isoformat(),
                "content_type": self._get_content_type(filename),
            }

            if metadata:
                # Convert all metadata values to strings
                for key, value in metadata.items():
                    if isinstance(value, int | float | bool):
                        file_metadata[key] = str(value)
                    elif isinstance(value, str):
                        file_metadata[key] = value
                    else:
                        file_metadata[key] = str(value)

            # Upload to R2
            self.client.put_object(
                Bucket=bucket_name,
                Key=storage_path,
                Body=content,
                ContentType=self._get_content_type(filename),
                Metadata=file_metadata,
            )

            # Generate presigned URL for download (MinIO, private buckets)
            presigned_url = None
            try:
                presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                presigned_url = self.client.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket_name, "Key": storage_path}, ExpiresIn=presigned_expiry
                )
            except Exception as presign_err:
                self.logger.debug("Failed to generate presigned URL: %s", presign_err)

            # Generate public URL based on bucket type
            if bucket_type == "document_images":
                base_url = self.public_urls.get("images") or self.public_urls["documents"]
            elif bucket_type == "error_images":
                base_url = self.public_urls.get("error", "")
            elif bucket_type == "parts_images":
                base_url = self.public_urls.get("parts", "")
            else:
                base_url = self.public_urls["documents"]

            if (
                bucket_type == "document_images"
                and self._document_images_bucket_override
                and not self.public_urls.get("images")
            ):
                base_url = ""

            if not base_url:
                base_url = f"{self.endpoint_url}/{bucket_name}"

            public_url = f"{base_url}/{storage_path}"

            result = {
                "success": True,
                "bucket": bucket_name,
                "key": storage_path,
                "storage_path": storage_path,
                "public_url": public_url,
                "url": public_url,
                "storage_url": public_url,
                "presigned_url": presigned_url,
                "file_hash": file_hash,
                "is_duplicate": False,
                "size": len(content),
                "content_type": self._get_content_type(filename),
                "metadata": file_metadata,
            }

            self.logger.info(f"Uploaded image {filename} to {bucket_name}/{storage_path}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to upload image {filename}: {e}")
            raise

    async def upload_file(
        self,
        content: bytes,
        filename: str,
        bucket_type: str = "documents",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload a generic file to object storage."""
        try:
            if self.client is None:
                allow_mock = os.getenv("OBJECT_STORAGE_ALLOW_MOCK", "false").lower() == "true"
                if not allow_mock:
                    raise RuntimeError(
                        "Object storage client is not connected. "
                        "Ensure boto3 is installed and connect() succeeded, or set OBJECT_STORAGE_ALLOW_MOCK=true."
                    )

                file_hash = hashlib.sha256(content).hexdigest()
                storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)
                bucket_name = self.buckets.get(bucket_type, self._documents_bucket_name)
                base_url = self._resolve_base_url(bucket_type, bucket_name)
                public_url = f"{base_url}/{storage_path}"
                return {
                    "success": True,
                    "bucket": bucket_name,
                    "key": storage_path,
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "url": public_url,
                    "storage_url": public_url,
                    "presigned_url": None,
                    "file_hash": file_hash,
                    "size": len(content),
                    "content_type": self._get_content_type(filename),
                    "metadata": metadata or {},
                }

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]
            file_hash = self._generate_file_hash(content)

            duplicate = await self.check_duplicate(file_hash, bucket_type)
            if duplicate:
                self.logger.info(f"Duplicate file found with hash {file_hash[:16]}...: {duplicate['key']}")
                dup_result = {
                    "success": True,
                    "file_hash": file_hash,
                    "storage_path": duplicate["key"],
                    "storage_url": duplicate["url"],
                    "url": duplicate["url"],
                    "bucket": duplicate["bucket"],
                    "is_duplicate": True,
                }
                try:
                    presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                    dup_result["presigned_url"] = self.client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": duplicate["bucket"], "Key": duplicate["key"]},
                        ExpiresIn=presigned_expiry,
                    )
                except Exception:
                    dup_result["presigned_url"] = None
                return dup_result

            storage_path = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)
            file_metadata = {
                "original_filename": filename,
                "file_hash": file_hash,
                "upload_timestamp": datetime.now(UTC).isoformat(),
                "content_type": self._get_content_type(filename),
            }
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, int | float | bool):
                        file_metadata[key] = str(value)
                    elif isinstance(value, str):
                        file_metadata[key] = value
                    else:
                        file_metadata[key] = str(value)

            self.client.put_object(
                Bucket=bucket_name,
                Key=storage_path,
                Body=content,
                ContentType=self._get_content_type(filename),
                Metadata=file_metadata,
            )

            presigned_url = None
            try:
                presigned_expiry = int(os.getenv("OBJECT_STORAGE_PRESIGNED_EXPIRY_SECONDS", "3600"))
                presigned_url = self.client.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket_name, "Key": storage_path}, ExpiresIn=presigned_expiry
                )
            except Exception as presign_err:
                self.logger.debug("Failed to generate presigned URL: %s", presign_err)

            base_url = self._resolve_base_url(bucket_type, bucket_name)
            public_url = f"{base_url}/{storage_path}"
            self.logger.info(f"Uploaded file {filename} to {bucket_name}/{storage_path}")
            return {
                "success": True,
                "bucket": bucket_name,
                "key": storage_path,
                "storage_path": storage_path,
                "public_url": public_url,
                "url": public_url,
                "storage_url": public_url,
                "presigned_url": presigned_url,
                "file_hash": file_hash,
                "is_duplicate": False,
                "size": len(content),
                "content_type": self._get_content_type(filename),
                "metadata": file_metadata,
            }
        except Exception as e:
            self.logger.error(f"Failed to upload file {filename}: {e}")
            raise

    async def download_image(self, bucket_type: str, key: str) -> bytes:
        """
        Download image from object storage

        Args:
            bucket_type: Type of bucket
            key: Storage key/path

        Returns:
            Image content as bytes
        """
        try:
            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot download in mock mode.")
                return b""

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]

            response = self.client.get_object(Bucket=bucket_name, Key=key)
            content = response["Body"].read()

            self.logger.info(f"Downloaded image from {bucket_name}/{key}")
            return content

        except Exception as e:
            self.logger.error(f"Failed to download image {bucket_type}/{key}: {e}")
            raise

    async def download_file(self, bucket_type: str, key: str) -> bytes:
        """Download an arbitrary file from object storage."""
        try:
            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot download in mock mode.")
                raise RuntimeError("Object storage client not connected")

            bucket_name = self.buckets[bucket_type]
            response = self.client.get_object(Bucket=bucket_name, Key=key)
            return response["Body"].read()

        except Exception as e:
            self.logger.error(f"Failed to download file {bucket_type}/{key}: {e}")
            raise

    async def delete_image(self, bucket_type: str, key: str) -> bool:
        """
        Delete image from object storage

        Args:
            bucket_type: Type of bucket
            key: Storage key/path

        Returns:
            True if deleted successfully
        """
        try:
            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot delete in mock mode.")
                return True  # Assume success in mock mode

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]

            self.client.delete_object(Bucket=bucket_name, Key=key)

            self.logger.info(f"Deleted image from {bucket_name}/{key}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete image {bucket_type}/{key}: {e}")
            raise

    async def get_image_metadata(self, bucket_type: str, key: str) -> dict[str, Any]:
        """
        Get image metadata from object storage

        Args:
            bucket_type: Type of bucket
            key: Storage key/path

        Returns:
            Image metadata
        """
        try:
            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot get metadata in mock mode.")
                return {}

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]

            response = self.client.head_object(Bucket=bucket_name, Key=key)

            return {
                "size": response["ContentLength"],
                "content_type": response["ContentType"],
                "last_modified": response["LastModified"],
                "metadata": response.get("Metadata", {}),
            }

        except Exception as e:
            self.logger.error(f"Failed to get metadata for {bucket_type}/{key}: {e}")
            raise

    async def list_images(self, bucket_type: str, prefix: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """
        List images in bucket

        Args:
            bucket_type: Type of bucket
            prefix: Optional prefix filter
            limit: Maximum number of results

        Returns:
            List of image information
        """
        try:
            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot list images in mock mode.")
                return []

            if bucket_type not in self.buckets:
                raise ValueError(f"Invalid bucket type: {bucket_type}")

            bucket_name = self.buckets[bucket_type]

            kwargs = {"Bucket": bucket_name, "MaxKeys": limit}

            if prefix:
                kwargs["Prefix"] = prefix

            response = self.client.list_objects_v2(**kwargs)

            images = []
            for obj in response.get("Contents", []):
                # Determine public URL based on bucket type
                public_url = ""
                if bucket_type == "document_images":
                    public_url = self.public_urls.get("images") or self.public_urls["documents"]
                elif bucket_type == "error_images":
                    public_url = self.public_urls["error"]
                elif bucket_type == "parts_images":
                    public_url = self.public_urls["parts"]
                else:
                    public_url = self.public_urls["documents"]

                if (
                    bucket_type == "document_images"
                    and self._document_images_bucket_override
                    and not self.public_urls.get("images")
                ):
                    public_url = ""

                if not public_url:
                    public_url = f"{self.endpoint_url}/{bucket_name}"

                images.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "url": f"{public_url}/{obj['Key']}",
                    }
                )

            self.logger.info(f"Listed {len(images)} images from {bucket_name}")
            return images

        except Exception as e:
            self.logger.error(f"Failed to list images from {bucket_type}: {e}")
            raise

    async def check_duplicate(self, file_hash: str, bucket_type: str | None = None) -> dict[str, Any] | None:
        """
        Check for duplicate file by hash

        Args:
            file_hash: SHA256 hash of file content
            bucket_type: Optional bucket type to search

        Returns:
            Duplicate file info if found, None otherwise
        """
        try:
            if self.client is None:
                self.logger.warning("Object storage client not available. Cannot check duplicates in mock mode.")
                return None

            if bucket_type:
                if bucket_type not in self.buckets:
                    raise ValueError(f"Invalid bucket type: {bucket_type}")

                bucket_name = self.buckets[bucket_type]
                expected_key = self._generate_storage_path(file_hash=file_hash, bucket_type=bucket_type)

                try:
                    head_response = self.client.head_object(Bucket=bucket_name, Key=expected_key)

                    if bucket_type == "document_images":
                        base_url = self.public_urls.get("images") or self.public_urls["documents"]
                    elif bucket_type == "error_images":
                        base_url = self.public_urls["error"]
                    elif bucket_type == "parts_images":
                        base_url = self.public_urls["parts"]
                    else:
                        base_url = self.public_urls["documents"]

                    if (
                        bucket_type == "document_images"
                        and self._document_images_bucket_override
                        and not self.public_urls.get("images")
                    ):
                        base_url = ""

                    if not base_url:
                        base_url = f"{self.endpoint_url}/{bucket_name}"

                    return {
                        "bucket": bucket_name,
                        "key": expected_key,
                        "url": f"{base_url}/{expected_key}",
                        "size": head_response.get("ContentLength"),
                        "last_modified": head_response.get("LastModified"),
                    }
                except ClientError as e:
                    error_code = (e.response.get("Error", {}) or {}).get("Code")
                    if error_code not in ("404", "NoSuchKey", "NotFound"):
                        raise

                if bucket_type == "document_images" and expected_key == file_hash:
                    legacy_key = f"images/{file_hash}"
                    try:
                        head_response = self.client.head_object(Bucket=bucket_name, Key=legacy_key)

                        base_url = self.public_urls.get("images") or self.public_urls["documents"]
                        if (
                            bucket_type == "document_images"
                            and self._document_images_bucket_override
                            and not self.public_urls.get("images")
                        ):
                            base_url = ""
                        if not base_url:
                            base_url = f"{self.endpoint_url}/{bucket_name}"

                        return {
                            "bucket": bucket_name,
                            "key": legacy_key,
                            "url": f"{base_url}/{legacy_key}",
                            "size": head_response.get("ContentLength"),
                            "last_modified": head_response.get("LastModified"),
                        }
                    except ClientError as legacy_error:
                        legacy_code = (legacy_error.response.get("Error", {}) or {}).get("Code")
                        if legacy_code not in ("404", "NoSuchKey", "NotFound"):
                            raise

            buckets_to_search = [bucket_type] if bucket_type else list(self.buckets.keys())

            for bucket_key in buckets_to_search:
                try:
                    # Map bucket type to actual bucket name
                    bucket_name = self.buckets.get(bucket_key, bucket_key)

                    # List all objects and check metadata for hash
                    response = self.client.list_objects_v2(Bucket=bucket_name)

                    for obj in response.get("Contents", []):
                        # Get object metadata
                        head_response = self.client.head_object(Bucket=bucket_name, Key=obj["Key"])
                        metadata = head_response.get("Metadata", {})

                        if metadata.get("file_hash") == file_hash:
                            # Determine public URL based on bucket type
                            public_url = ""
                            if bucket_key == "document_images":
                                public_url = self.public_urls.get("images") or self.public_urls["documents"]
                            elif bucket_key == "error_images":
                                public_url = self.public_urls["error"]
                            elif bucket_key == "parts_images":
                                public_url = self.public_urls["parts"]
                            else:
                                public_url = self.public_urls["documents"]

                            if (
                                bucket_key == "document_images"
                                and self._document_images_bucket_override
                                and not self.public_urls.get("images")
                            ):
                                public_url = ""

                            if not public_url:
                                public_url = f"{self.endpoint_url}/{bucket_name}"

                            return {
                                "bucket": bucket_name,
                                "key": obj["Key"],
                                "url": f"{public_url}/{obj['Key']}",
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"],
                            }

                except ClientError:
                    # Bucket might not exist or be accessible
                    continue

            return None

        except Exception as e:
            self.logger.error(f"Failed to check for duplicate {file_hash}: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Perform storage health check"""
        try:
            if self.client is None:
                return {
                    "status": "healthy",
                    "mode": "mock",
                    "response_time_ms": 0,
                    "buckets": list(self.buckets.values()),
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            start_time = datetime.now(UTC)

            # Test basic operation
            self.client.head_bucket(Bucket=self.buckets["document_images"])

            response_time = (datetime.now(UTC) - start_time).total_seconds()

            return {
                "status": "healthy",
                "mode": "connected",
                "response_time_ms": response_time * 1000,
                "buckets": list(self.buckets.values()),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now(UTC).isoformat()}
