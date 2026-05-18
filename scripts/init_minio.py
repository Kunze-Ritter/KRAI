#!/usr/bin/env python3
"""
MinIO Initialization Script for KRAI

This script initializes MinIO with required buckets and verifies connectivity.
It can be run standalone or as part of Docker initialization.

Usage:
    python scripts/init_minio.py              # Initialize all buckets
    python scripts/init_minio.py --verify-only  # Check connectivity only
    python scripts/init_minio.py --bucket documents  # Initialize specific bucket
"""

import argparse
import asyncio
import os
import sys

try:
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    EndpointConnectionError = Exception
    BOTO3_AVAILABLE = False


class MinIOInitializer:
    """MinIO initialization and management class"""

    def __init__(self):
        """Load configuration from environment variables"""
        self.endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT", "http://localhost:9000")
        self.access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin123")
        self.region = os.getenv("OBJECT_STORAGE_REGION", "us-east-1")
        self.use_ssl = os.getenv("OBJECT_STORAGE_USE_SSL", "false").lower() == "true"

        # Bucket configurations
        self.all_buckets = {
            "documents": os.getenv("OBJECT_STORAGE_BUCKET_DOCUMENTS", "documents"),
            "images": os.getenv("OBJECT_STORAGE_BUCKET_IMAGES", "images"),
            "videos": os.getenv("OBJECT_STORAGE_BUCKET_VIDEOS", "videos"),
            "temp": os.getenv("OBJECT_STORAGE_BUCKET_TEMP", "temp"),
        }

        legacy_enabled = os.getenv("INIT_MINIO_CREATE_LEGACY_BUCKETS", "false").lower() == "true"
        enabled_bucket_types = ["images"]
        if legacy_enabled:
            enabled_bucket_types.extend(["documents", "videos", "temp"])

        self.buckets = {bucket_type: self.all_buckets[bucket_type] for bucket_type in enabled_bucket_types}

        self.client = None

    def create_s3_client(self) -> bool:
        """Create boto3 S3 client with MinIO endpoint"""
        try:
            if not BOTO3_AVAILABLE:
                print("❌ boto3 not available. Install with: pip install boto3")
                return False

            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
                verify=not self.use_ssl,  # Don't verify SSL for local MinIO
            )

            print(f"✅ Created S3 client for {self.endpoint}")
            return True

        except Exception as e:
            print(f"❌ Failed to create S3 client: {e}")
            return False

    async def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """Create bucket if it doesn't exist"""
        try:
            # Check if bucket exists
            self.client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' already exists")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            status_code = e.response["ResponseMetadata"]["HTTPStatusCode"]
            if error_code == "404" or status_code == 404 or error_code == "NoSuchBucket":
                # Bucket doesn't exist, create it
                try:
                    self.client.create_bucket(Bucket=bucket_name)
                    print(f"✅ Created bucket '{bucket_name}'")
                    return True
                except ClientError as create_error:
                    print(f"❌ Failed to create bucket '{bucket_name}': {create_error}")
                    return False
            else:
                print(f"❌ Error checking bucket '{bucket_name}': {e}")
                return False

    def set_bucket_policy(self, bucket_name: str, policy_type: str = "private") -> bool:
        """Set bucket policy (public or private)"""
        try:
            if policy_type == "public":
                # Public read policy for images and videos
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicReadGetObject",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{bucket_name}/*",
                        }
                    ],
                }

                self.client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                print(f"✅ Set public policy for bucket '{bucket_name}'")

            else:
                # Remove policy for private buckets
                try:
                    self.client.delete_bucket_policy(Bucket=bucket_name)
                    print(f"✅ Set private policy for bucket '{bucket_name}'")
                except ClientError:
                    # Policy might not exist, that's fine
                    print(f"✅ Bucket '{bucket_name}' is already private")

            return True

        except Exception as e:
            print(f"⚠️ Warning: Could not set policy for bucket '{bucket_name}': {e}")
            return False

    async def verify_connectivity(self) -> bool:
        """Verify MinIO connectivity"""
        try:
            if not self.client:
                print("❌ S3 client not initialized")
                return False

            # Test basic operation by listing buckets
            response = self.client.list_buckets()
            print(f"✅ Connected to MinIO at {self.endpoint}")
            print(f"📊 Found {len(response['Buckets'])} existing buckets")

            existing_buckets = [bucket["Name"] for bucket in response["Buckets"]]
            if existing_buckets:
                print(f"📦 Existing buckets: {', '.join(existing_buckets)}")

            return True

        except EndpointConnectionError:
            print(f"❌ Cannot connect to MinIO at {self.endpoint}")
            print("💡 Make sure MinIO is running: docker-compose up -d krai-minio")
            return False
        except NoCredentialsError:
            print("❌ Invalid credentials for MinIO")
            print("💡 Check OBJECT_STORAGE_ACCESS_KEY and OBJECT_STORAGE_SECRET_KEY")
            return False
        except Exception as e:
            print(f"❌ Failed to verify connectivity: {e}")
            return False

    async def initialize_bucket(self, bucket_type: str) -> bool:
        """Initialize a specific bucket"""
        if bucket_type not in self.all_buckets:
            print(f"❌ Invalid bucket type: {bucket_type}")
            print(f"💡 Valid types: {', '.join(self.all_buckets.keys())}")
            return False

        bucket_name = self.all_buckets[bucket_type]

        print(f"\n🔧 Initializing bucket '{bucket_name}' ({bucket_type})...")

        # Create bucket
        if not await self.ensure_bucket_exists(bucket_name):
            return False

        # Set policy based on bucket type
        if bucket_type in ["images", "videos"]:
            policy_type = "public"
        else:
            policy_type = "private"

        self.set_bucket_policy(bucket_name, policy_type)

        print(f"✅ Bucket '{bucket_name}' ready for use")
        return True

    async def initialize_all(self) -> bool:
        """Initialize all required buckets"""
        print("🚀 Initializing MinIO buckets for KRAI...")

        success = True
        for bucket_type in self.buckets.keys():
            if not await self.initialize_bucket(bucket_type):
                success = False

        return success

    async def run_with_retry(self, operation, max_retries: int = 5, delay: float = 2.0):
        """Run operation with retry logic for startup timing"""
        for attempt in range(max_retries):
            try:
                return await operation()
            except EndpointConnectionError as e:
                if attempt == max_retries - 1:
                    raise e

                print(f"⏳ Waiting for MinIO to start... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay * (2**attempt))  # Exponential backoff


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Initialize MinIO for KRAI")
    parser.add_argument("--verify-only", action="store_true", help="Only verify connectivity, do not create buckets")
    parser.add_argument("--bucket", type=str, help="Initialize specific bucket only")

    args = parser.parse_args()

    print("🔧 MinIO Initialization Script for KRAI")
    print("=" * 50)

    # Initialize MinIO client
    initializer = MinIOInitializer()

    if not initializer.create_s3_client():
        sys.exit(1)

    # Verify connectivity
    print("\n🔍 Verifying MinIO connectivity...")
    if not await initializer.run_with_retry(initializer.verify_connectivity):
        sys.exit(1)

    if args.verify_only:
        print("\n✅ MinIO connectivity verified successfully!")
        sys.exit(0)

    # Initialize buckets
    if args.bucket:
        # Initialize specific bucket
        success = await initializer.initialize_bucket(args.bucket)
    else:
        # Initialize all buckets
        success = await initializer.run_with_retry(initializer.initialize_all)

    if success:
        print("\n🎉 MinIO initialization completed successfully!")
        print("\n📋 Summary:")
        for bucket_type, bucket_name in initializer.buckets.items():
            policy = "public" if bucket_type in ["images", "videos"] else "private"
            print(f"  📦 {bucket_name} ({bucket_type}) - {policy} access")

        print("\n🌐 MinIO Console: http://localhost:9001")
        print(f"🔑 Username: {initializer.access_key}")
        print(f"🔑 Password: {initializer.secret_key}")
        sys.exit(0)
    else:
        print("\n❌ MinIO initialization failed!")
        sys.exit(1)


if __name__ == "__main__":
    # Import json here to avoid issues if script is run without boto3
    import json

    asyncio.run(main())
