#!/usr/bin/env python3
"""
Comprehensive Deduplication Verification Script (PostgreSQL version)
Überprüft alle Komponenten auf korrekte Deduplikation
"""

import asyncio
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

import boto3

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.processors.env_loader import load_all_env_files
from backend.services.db_pool import get_pool

# Load environment variables
project_root = Path(__file__).parent.parent.parent
load_all_env_files(project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DeduplicationVerifier:
    def __init__(self):
        self.pool = None

        # R2 credentials

        if all([r2_access_key, r2_secret_key, r2_endpoint_url]):
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=r2_endpoint_url,
                aws_access_key_id=r2_access_key,
                aws_secret_access_key=r2_secret_key,
                region_name="auto",
            )
        else:
            self.s3_client = None

        self.verification_results = {}

    async def connect(self):
        """Connect to database"""
        self.pool = await get_pool()
        logger.info("Connected to PostgreSQL database")

    async def verify_documents_deduplication(self):
        """Verify documents deduplication"""
        logger.info("Checking documents deduplication...")

        try:
            async with self.pool.acquire() as conn:
                # Get all documents
                documents = await conn.fetch(
                    """
                    SELECT id, file_hash, filename, created_at
                    FROM krai_core.documents
                """
                )

                # Group by file_hash
                hash_groups = defaultdict(list)
                for doc in documents:
                    hash_groups[doc["file_hash"]].append(dict(doc))

                # Find duplicates
                duplicates = {hash_val: docs for hash_val, docs in hash_groups.items() if len(docs) > 1}

                self.verification_results["documents"] = {
                    "total_documents": len(documents),
                    "unique_hashes": len(hash_groups),
                    "duplicate_groups": len(duplicates),
                    "duplicate_documents": sum(len(docs) - 1 for docs in duplicates.values()),
                    "duplicates_found": duplicates,
                }

                if duplicates:
                    logger.warning(
                        f"Found {len(duplicates)} duplicate document groups with {sum(len(docs) - 1 for docs in duplicates.values())} duplicate documents"
                    )
                    for hash_val, docs in list(duplicates.items())[:3]:  # Show first 3
                        logger.warning(f"  Hash {hash_val[:16]}...: {len(docs)} duplicates")
                else:
                    logger.info("No document duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify documents deduplication: {e}")
            self.verification_results["documents"] = {"error": str(e)}

    async def verify_images_deduplication(self):
        """Verify images deduplication"""
        logger.info("Checking images deduplication...")

        try:
            async with self.pool.acquire() as conn:
                # Get all images
                images = await conn.fetch(
                    """
                    SELECT id, file_hash, filename, created_at
                    FROM krai_content.images
                """
                )

                # Group by file_hash
                hash_groups = defaultdict(list)
                for img in images:
                    hash_groups[img["file_hash"]].append(dict(img))

                # Find duplicates
                duplicates = {hash_val: imgs for hash_val, imgs in hash_groups.items() if len(imgs) > 1}

                self.verification_results["images"] = {
                    "total_images": len(images),
                    "unique_hashes": len(hash_groups),
                    "duplicate_groups": len(duplicates),
                    "duplicate_images": sum(len(imgs) - 1 for imgs in duplicates.values()),
                    "duplicates_found": duplicates,
                }

                if duplicates:
                    logger.warning(
                        f"Found {len(duplicates)} duplicate image groups with {sum(len(imgs) - 1 for imgs in duplicates.values())} duplicate images"
                    )
                    for hash_val, imgs in list(duplicates.items())[:3]:  # Show first 3
                        logger.warning(f"  Hash {hash_val[:16]}...: {len(imgs)} duplicates")
                else:
                    logger.info("No image duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify images deduplication: {e}")
            self.verification_results["images"] = {"error": str(e)}

    async def verify_chunks_deduplication(self):
        """Verify chunks deduplication"""
        logger.info("Checking chunks deduplication...")

        try:
            async with self.pool.acquire() as conn:
                # Get all chunks
                chunks = await conn.fetch(
                    """
                    SELECT id, content_hash, document_id, created_at
                    FROM krai_intelligence.chunks
                """
                )

                # Group by content_hash
                hash_groups = defaultdict(list)
                for chunk in chunks:
                    hash_groups[chunk["content_hash"]].append(dict(chunk))

                # Find duplicates
                duplicates = {hash_val: chs for hash_val, chs in hash_groups.items() if len(chs) > 1}

                self.verification_results["chunks"] = {
                    "total_chunks": len(chunks),
                    "unique_hashes": len(hash_groups),
                    "duplicate_groups": len(duplicates),
                    "duplicate_chunks": sum(len(chs) - 1 for chs in duplicates.values()),
                    "duplicates_found": duplicates,
                }

                if duplicates:
                    logger.warning(
                        f"Found {len(duplicates)} duplicate chunk groups with {sum(len(chs) - 1 for chs in duplicates.values())} duplicate chunks"
                    )
                    for hash_val, chs in list(duplicates.items())[:3]:  # Show first 3
                        logger.warning(f"  Hash {hash_val[:16]}...: {len(chs)} duplicates")
                else:
                    logger.info("No chunk duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify chunks deduplication: {e}")
            self.verification_results["chunks"] = {"error": str(e)}

    async def verify_embeddings_deduplication(self):
        """Verify embeddings deduplication"""
        logger.info("Checking embeddings deduplication...")

        try:
            async with self.pool.acquire() as conn:
                # Get all embeddings (embeddings are in chunks table)
                embeddings = await conn.fetch(
                    """
                    SELECT id, chunk_id, created_at
                    FROM krai_intelligence.chunks
                    WHERE embedding IS NOT NULL
                """
                )

                # Group by chunk_id (should be 1:1 relationship)
                chunk_groups = defaultdict(list)
                for emb in embeddings:
                    # chunk_id is actually the id itself in this case
                    chunk_groups[emb["id"]].append(dict(emb))

                # Find duplicates (shouldn't exist)
                duplicates = {chunk_id: embs for chunk_id, embs in chunk_groups.items() if len(embs) > 1}

                self.verification_results["embeddings"] = {
                    "total_embeddings": len(embeddings),
                    "unique_chunk_ids": len(chunk_groups),
                    "duplicate_groups": len(duplicates),
                    "duplicate_embeddings": sum(len(embs) - 1 for embs in duplicates.values()),
                    "duplicates_found": duplicates,
                }

                if duplicates:
                    logger.warning(
                        f"Found {len(duplicates)} duplicate embedding groups with {sum(len(embs) - 1 for embs in duplicates.values())} duplicate embeddings"
                    )
                    for chunk_id, embs in list(duplicates.items())[:3]:  # Show first 3
                        logger.warning(f"  Chunk {str(chunk_id)[:16]}...: {len(embs)} duplicates")
                else:
                    logger.info("No embedding duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify embeddings deduplication: {e}")
            self.verification_results["embeddings"] = {"error": str(e)}

    async def verify_manufacturers_deduplication(self):
        """Verify manufacturers deduplication"""
        logger.info("Checking manufacturers deduplication...")

        try:
            async with self.pool.acquire() as conn:
                # Get all manufacturers
                manufacturers = await conn.fetch(
                    """
                    SELECT id, name, created_at
                    FROM krai_core.manufacturers
                """
                )

                # Group by name (case insensitive)
                name_groups = defaultdict(list)
                for mfg in manufacturers:
                    name_groups[mfg["name"].lower()].append(dict(mfg))

                # Find duplicates
                duplicates = {name: mfgs for name, mfgs in name_groups.items() if len(mfgs) > 1}

                self.verification_results["manufacturers"] = {
                    "total_manufacturers": len(manufacturers),
                    "unique_names": len(name_groups),
                    "duplicate_groups": len(duplicates),
                    "duplicate_manufacturers": sum(len(mfgs) - 1 for mfgs in duplicates.values()),
                    "duplicates_found": duplicates,
                }

                if duplicates:
                    logger.warning(
                        f"Found {len(duplicates)} duplicate manufacturer groups with {sum(len(mfgs) - 1 for mfgs in duplicates.values())} duplicate manufacturers"
                    )
                    for name, mfgs in list(duplicates.items())[:3]:  # Show first 3
                        logger.warning(f"  Name '{name}': {len(mfgs)} duplicates")
                else:
                    logger.info("No manufacturer duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify manufacturers deduplication: {e}")
            self.verification_results["manufacturers"] = {"error": str(e)}

    def verify_r2_deduplication(self):
        """Verify R2 object storage deduplication"""
        logger.info("Checking R2 object storage deduplication...")

        if not self.s3_client:
            logger.warning("R2 client not available - skipping R2 verification")
            self.verification_results["r2"] = {"error": "R2 client not available"}
            return

        try:
            # List all objects in krai-documents-images bucket
            objects = []
            bucket_name = "krai-documents-images"

            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects.append({"name": obj["Key"], "size": obj["Size"], "etag": obj["ETag"]})

            # Group by ETag (content hash)
            etag_groups = defaultdict(list)
            for obj in objects:
                etag_groups[obj["etag"]].append(obj)

            # Find duplicates
            duplicates = {etag: objs for etag, objs in etag_groups.items() if len(objs) > 1}

            self.verification_results["r2"] = {
                "total_objects": len(objects),
                "unique_etags": len(etag_groups),
                "duplicate_groups": len(duplicates),
                "duplicate_objects": sum(len(objs) - 1 for objs in duplicates.values()),
                "duplicates_found": duplicates,
            }

            if duplicates:
                logger.warning(
                    f"Found {len(duplicates)} duplicate object groups with {sum(len(objs) - 1 for objs in duplicates.values())} duplicate objects"
                )
                for etag, objs in list(duplicates.items())[:3]:  # Show first 3
                    logger.warning(f"  ETag {etag[:16]}...: {len(objs)} duplicates")
            else:
                logger.info("No R2 object duplicates found")

        except Exception as e:
            logger.error(f"Failed to verify R2 deduplication: {e}")
            self.verification_results["r2"] = {"error": str(e)}

    def print_summary(self):
        """Print comprehensive deduplication summary"""
        logger.info("\n" + "=" * 60)
        logger.info("COMPREHENSIVE DEDUPLICATION VERIFICATION SUMMARY")
        logger.info("=" * 60)

        total_duplicates = 0
        components_with_duplicates = 0

        for component, results in self.verification_results.items():
            if "error" in results:
                logger.error(f"\n{component.upper()}: ERROR - {results['error']}")
                continue

            duplicates = results.get("duplicate_groups", 0)
            if duplicates > 0:
                components_with_duplicates += 1
                total_duplicates += results.get(
                    "duplicate_objects",
                    results.get(
                        "duplicate_documents",
                        results.get(
                            "duplicate_images",
                            results.get(
                                "duplicate_chunks",
                                results.get("duplicate_embeddings", results.get("duplicate_manufacturers", 0)),
                            ),
                        ),
                    ),
                )

            status = "CLEAN" if duplicates == 0 else f"{duplicates} DUPLICATE GROUPS"
            logger.info(f"\n{component.upper()}: {status}")

            if component == "documents":
                logger.info(f"  Total Documents: {results.get('total_documents', 0):,}")
                logger.info(f"  Unique Hashes: {results.get('unique_hashes', 0):,}")
                logger.info(f"  Duplicate Documents: {results.get('duplicate_documents', 0):,}")
            elif component == "images":
                logger.info(f"  Total Images: {results.get('total_images', 0):,}")
                logger.info(f"  Unique Hashes: {results.get('unique_hashes', 0):,}")
                logger.info(f"  Duplicate Images: {results.get('duplicate_images', 0):,}")
            elif component == "chunks":
                logger.info(f"  Total Chunks: {results.get('total_chunks', 0):,}")
                logger.info(f"  Unique Hashes: {results.get('unique_hashes', 0):,}")
                logger.info(f"  Duplicate Chunks: {results.get('duplicate_chunks', 0):,}")
            elif component == "embeddings":
                logger.info(f"  Total Embeddings: {results.get('total_embeddings', 0):,}")
                logger.info(f"  Unique Chunk IDs: {results.get('unique_chunk_ids', 0):,}")
                logger.info(f"  Duplicate Embeddings: {results.get('duplicate_embeddings', 0):,}")
            elif component == "manufacturers":
                logger.info(f"  Total Manufacturers: {results.get('total_manufacturers', 0):,}")
                logger.info(f"  Unique Names: {results.get('unique_names', 0):,}")
                logger.info(f"  Duplicate Manufacturers: {results.get('duplicate_manufacturers', 0):,}")
            elif component == "r2":
                logger.info(f"  Total Objects: {results.get('total_objects', 0):,}")
                logger.info(f"  Unique ETags: {results.get('unique_etags', 0):,}")
                logger.info(f"  Duplicate Objects: {results.get('duplicate_objects', 0):,}")

        logger.info("\n" + "=" * 60)
        if components_with_duplicates == 0:
            logger.info("OVERALL STATUS: ✅ ALL COMPONENTS CLEAN - NO DUPLICATES FOUND")
        else:
            logger.warning(
                f"OVERALL STATUS: ⚠️ {components_with_duplicates} COMPONENTS HAVE DUPLICATES ({total_duplicates} total duplicate items)"
            )
        logger.info("=" * 60)


async def main():
    """Main verification function"""
    logger.info("Starting Comprehensive Deduplication Verification")

    verifier = DeduplicationVerifier()

    try:
        await verifier.connect()

        # Verify all components
        await verifier.verify_documents_deduplication()
        await verifier.verify_images_deduplication()
        await verifier.verify_chunks_deduplication()
        await verifier.verify_embeddings_deduplication()
        await verifier.verify_manufacturers_deduplication()

        # R2 verification (synchronous)
        verifier.verify_r2_deduplication()

        # Print summary
        verifier.print_summary()

    except Exception as e:
        logger.error(f"Deduplication verification failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
