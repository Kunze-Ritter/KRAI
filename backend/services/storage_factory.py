"""
Object Storage Factory

Factory pattern for creating object storage services based on configuration.
Supports MinIO and S3-compatible storage (AWS S3, Wasabi, Backblaze B2).
"""

import logging
import os
from typing import overload
from urllib.parse import urlparse, urlunparse

from .object_storage_service import ObjectStorageService

logger = logging.getLogger("krai.storage.factory")


def create_storage_service(
    storage_type: str | None = None,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    public_url_documents: str | None = None,
    public_url_images: str | None = None,
    public_url_error: str | None = None,
    public_url_parts: str | None = None,
    use_ssl: bool | None = None,
    region: str | None = None,
    bucket_documents: str | None = None,
    bucket_images: str | None = None,
    bucket_videos: str | None = None,
    bucket_error: str | None = None,
    bucket_parts: str | None = None,
    bucket_temp: str | None = None,
) -> ObjectStorageService:
    """
    Create an object storage service based on the specified type.

    Args:
        storage_type: Type of storage backend ('s3', 'minio', 'r2', 'wasabi', etc.)
                      If None, reads from OBJECT_STORAGE_TYPE environment variable (default: 's3')
        endpoint_url: Storage endpoint URL (overrides environment)
        access_key: Access key (overrides environment)
        secret_key: Secret key (overrides environment)
        public_url_documents: Public URL for documents bucket (overrides environment)
        public_url_error: Public URL for error bucket (overrides environment)
        public_url_parts: Public URL for parts bucket (overrides environment)
        use_ssl: Use SSL connection (overrides environment)
        region: Storage region (overrides environment)
        bucket_documents: Documents bucket name (overrides environment)
        bucket_images: Images bucket name (overrides environment)
        bucket_videos: Videos bucket name (overrides environment)
        bucket_error: Error bucket name (overrides environment)
        bucket_parts: Parts bucket name (overrides environment)
        bucket_temp: Temporary bucket name (overrides environment)

    Returns:
        ObjectStorageService: Configured storage service instance

    Raises:
        ValueError: If required configuration is missing

    Environment Variables:
        OBJECT_STORAGE_TYPE: Storage backend type (default: 's3')
        OBJECT_STORAGE_ENDPOINT: Storage endpoint URL
        OBJECT_STORAGE_ACCESS_KEY: Storage access key
        OBJECT_STORAGE_SECRET_KEY: Storage secret key
        OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS: Public URL for documents
        OBJECT_STORAGE_PUBLIC_URL_ERROR: Public URL for error images
        OBJECT_STORAGE_PUBLIC_URL_PARTS: Public URL for parts images
        OBJECT_STORAGE_USE_SSL: Use SSL connection (default: 'true')
        OBJECT_STORAGE_REGION: Storage region (default: 'auto')
        OBJECT_STORAGE_BUCKET_DOCUMENTS: Documents bucket name
        OBJECT_STORAGE_BUCKET_ERROR: Error bucket name
        OBJECT_STORAGE_BUCKET_PARTS: Parts bucket name

        # Note: Only OBJECT_STORAGE_* variables are supported.
    """

    # Determine storage type from parameter or environment
    if storage_type is None:
        storage_type = os.getenv("OBJECT_STORAGE_TYPE", "s3").lower()
    else:
        storage_type = storage_type.lower()

    logger.info(f"Creating object storage service: {storage_type}")

    # Helper function to get env var with default
    @overload
    def get_env_var(var: str, default: str) -> str: ...

    @overload
    def get_env_var(var: str, default: None = None) -> str | None: ...

    def get_env_var(var: str, default: str | None = None) -> str | None:
        return os.getenv(var) or default

    # Load configuration from parameters or environment
    endpoint = endpoint_url or get_env_var("OBJECT_STORAGE_ENDPOINT")

    # Normalize endpoint when running outside Docker and talking to Docker-internal MinIO
    if endpoint:
        try:
            parsed = urlparse(endpoint)
            running_in_docker = os.path.exists("/.dockerenv") or os.getenv("KRAI_IN_DOCKER") == "1"
            if parsed.hostname in ("krai-minio", "minio") and not running_in_docker:
                port_str = f":{parsed.port}" if parsed.port else ""
                netloc = f"127.0.0.1{port_str}"
                original_endpoint = endpoint
                endpoint = urlunparse(parsed._replace(netloc=netloc))
                logger.info(
                    "Overriding object storage endpoint for local execution: %r -> %r",
                    original_endpoint,
                    endpoint,
                )
        except Exception:
            # Best-effort normalization only; fall back silently on errors
            pass

    access_key = access_key or get_env_var("OBJECT_STORAGE_ACCESS_KEY")

    secret_key = secret_key or get_env_var("OBJECT_STORAGE_SECRET_KEY")

    use_ssl_val = use_ssl if use_ssl is not None else get_env_var("OBJECT_STORAGE_USE_SSL", "true")
    use_ssl = str(use_ssl_val).lower() == "true"

    region = region or get_env_var("OBJECT_STORAGE_REGION", "auto")

    # Extract bucket names
    bucket_documents = bucket_documents or get_env_var("OBJECT_STORAGE_BUCKET_DOCUMENTS", "documents")
    bucket_images = bucket_images or get_env_var("OBJECT_STORAGE_BUCKET_IMAGES", "images")
    bucket_error = bucket_error or get_env_var("OBJECT_STORAGE_BUCKET_ERROR")
    bucket_parts = bucket_parts or get_env_var("OBJECT_STORAGE_BUCKET_PARTS")

    public_url_base = get_env_var("OBJECT_STORAGE_PUBLIC_URL", "").rstrip("/")

    public_url_documents = public_url_documents or get_env_var("OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS", "")
    if not public_url_documents and public_url_base:
        public_url_documents = f"{public_url_base}/{bucket_documents}"

    public_url_images = public_url_images or get_env_var("OBJECT_STORAGE_PUBLIC_URL_IMAGES", "")
    if not public_url_images and public_url_base:
        public_url_images = f"{public_url_base}/{bucket_images}"

    public_url_error = public_url_error or get_env_var("OBJECT_STORAGE_PUBLIC_URL_ERROR", "")
    if not public_url_error and public_url_base and bucket_error:
        public_url_error = f"{public_url_base}/{bucket_error}"

    public_url_parts = public_url_parts or get_env_var("OBJECT_STORAGE_PUBLIC_URL_PARTS", "")
    if not public_url_parts and public_url_base and bucket_parts:
        public_url_parts = f"{public_url_base}/{bucket_parts}"

    # Validate required configuration
    if not endpoint:
        raise ValueError("OBJECT_STORAGE_ENDPOINT is required for object storage")
    if not access_key:
        raise ValueError("OBJECT_STORAGE_ACCESS_KEY is required for object storage")
    if not secret_key:
        raise ValueError("OBJECT_STORAGE_SECRET_KEY is required for object storage")

    # Log configuration summary
    logger.info(f"Storage endpoint: {endpoint}")
    logger.info(f"SSL enabled: {use_ssl}")
    logger.info(f"Region: {region}")
    logger.info("Buckets: images")

    # Create service with bucket name parameters
    service = ObjectStorageService(
        access_key_id=access_key,
        secret_access_key=secret_key,
        endpoint_url=endpoint,
        public_url_documents=public_url_documents,
        public_url_images=public_url_images,
        public_url_error=public_url_error,
        public_url_parts=public_url_parts,
        use_ssl=use_ssl,
        region=region,
        bucket_documents=bucket_documents,
        bucket_images=bucket_images,
        bucket_error=bucket_error,
        bucket_parts=bucket_parts,
    )
    logger.info(f"Created {storage_type} object storage service at {endpoint}")
    return service


class StorageFactory:
    """
    Factory class for creating object storage services.

    This class provides a static interface to the create_storage_service function
    for compatibility with existing code that expects a class-based factory.
    """

    @staticmethod
    def create_storage_service(**kwargs) -> ObjectStorageService:
        """
        Create an object storage service.

        This is a static wrapper around the create_storage_service function.
        """
        return create_storage_service(**kwargs)
