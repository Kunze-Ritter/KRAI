"""
Video Enrichment Service
Wraps the video enrichment script for use in the API
"""

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

try:
    from enrich_video_metadata import VideoEnricher
except ImportError as e:
    logger.warning(f"⚠️ VideoEnricher not available: {e}")
    VideoEnricher = None


class VideoEnrichmentService:
    """Service for enriching video links with metadata"""

    def __init__(self):
        """Initialize video enrichment service"""
        self.enricher = None
        logger.info("✅ Video Enrichment Service initialized")

    async def process_videos(self, limit: int | None = None, force: bool = False) -> dict[str, Any]:
        """
        Process and enrich video links

        Args:
            limit: Maximum number of videos to process
            force: Re-process already enriched videos

        Returns:
            Dictionary with enrichment results
        """
        try:
            if VideoEnricher is None:
                raise RuntimeError("VideoEnricher not available - check dependencies")

            logger.info(f"🎬 Starting video enrichment (limit={limit}, force={force})")

            # Create enricher instance
            enricher = VideoEnricher()

            # Process videos
            await enricher.process_unenriched_links(limit=limit, force=force)

            # Get results
            result = {
                "enriched": enricher.enriched_count,
                "errors": enricher.error_count,
                "checked": enricher.checked_count,
            }

            # Close enricher
            await enricher.close()

            logger.info(f"✅ Video enrichment complete: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Error in video enrichment: {e}")
            raise

    async def enrich_video_url(
        self, url: str, document_id: str | None = None, manufacturer_id: str | None = None
    ) -> dict[str, Any]:
        """
        Enrich a single video URL and save to database

        Args:
            url: Video URL to enrich
            document_id: Optional document ID to link to
            manufacturer_id: Optional manufacturer ID to link to

        Returns:
            Dictionary with video metadata including database ID
        """
        try:
            if VideoEnricher is None:
                raise RuntimeError("VideoEnricher not available - check dependencies")

            logger.info(f"🎬 Enriching single video: {url}")

            # Create enricher instance
            enricher = VideoEnricher()

            # Enrich the video (get metadata)
            metadata = await enricher.enrich_single_url(
                url=url, document_id=document_id, manufacturer_id=manufacturer_id
            )

            # Check for errors
            if "error" in metadata:
                await enricher.close()
                return metadata

            # Save to database with deduplication
            db_client = enricher._get_database_adapter()

            # Check for existing video (deduplication)
            platform = metadata.get("platform")
            existing = None

            # Use detected manufacturer_id from metadata if not provided
            final_manufacturer_id = manufacturer_id or metadata.get("manufacturer_id")

            if platform == "youtube":
                # Deduplicate by youtube_id
                youtube_id = metadata.get("video_id")
                if youtube_id:
                    result = db_client.table("vw_videos").select("*").eq("youtube_id", youtube_id).limit(1).execute()
                    if result.data:
                        existing = result.data[0]
            else:
                # Deduplicate by video_url
                result = db_client.table("vw_videos").select("*").eq("video_url", url).limit(1).execute()
                if result.data:
                    existing = result.data[0]

            if existing:
                logger.info(f"🔗 Video already exists in database (ID: {existing['id']})")
                video_db_id = existing["id"]
            else:
                # Insert new video

                video_data = {
                    "link_id": None,  # No link for direct API enrichment
                    "youtube_id": metadata.get("video_id") if platform == "youtube" else None,
                    "platform": platform,
                    "video_url": url,
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "duration": metadata.get("duration"),
                    "channel_title": metadata.get("channel_title"),
                    "manufacturer_id": final_manufacturer_id,
                    "document_id": document_id,
                    "metadata": metadata.get("metadata", {}),
                }

                # Add platform-specific metadata
                if platform == "vimeo":
                    video_data["metadata"]["vimeo_id"] = metadata.get("video_id")
                elif platform == "brightcove":
                    video_data["metadata"]["brightcove_id"] = metadata.get("video_id")
                elif platform == "direct":
                    # Add models to metadata
                    if metadata.get("models"):
                        video_data["metadata"]["models"] = metadata.get("models")

                insert_result = db_client.table("vw_videos").insert(video_data).execute()

                if not insert_result.data:
                    logger.error("Failed to insert video into database")
                    await enricher.close()
                    return {**metadata, "error": "Failed to save to database"}

                video_db_id = insert_result.data[0]["id"]
                logger.info(f"✅ Video saved to database (ID: {video_db_id})")

            # Link video to products if models were detected
            if metadata.get("models") and final_manufacturer_id:
                try:
                    from utils.manufacturer_utils import link_video_to_products

                    linked_products = await link_video_to_products(
                        video_id=video_db_id, model_names=metadata.get("models"), manufacturer_id=final_manufacturer_id
                    )

                    if linked_products:
                        logger.info(f"🔗 Linked video to {len(linked_products)} products")
                except Exception as e:
                    logger.error(f"❌ Error linking video to products: {e}")

            # Close enricher
            await enricher.close()

            # Return metadata with database ID
            return {
                **metadata,
                "database_id": video_db_id,
                "saved": True,
                "linked_products": len(metadata.get("models", [])) if final_manufacturer_id else 0,
            }

        except Exception as e:
            logger.error(f"❌ Error enriching video: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Health check for video enrichment service"""
        try:
            # Check if YouTube API key is configured
            youtube_key = os.getenv("YOUTUBE_API_KEY")

            return {
                "status": "healthy",
                "youtube_api_configured": bool(youtube_key and youtube_key != "your_youtube_api_key_here"),
                "supported_platforms": ["youtube", "vimeo", "brightcove"],
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
