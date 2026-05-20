"""Video enrichment processor for Brightcove metadata enrichment."""

import json
import os
from datetime import datetime
from typing import Any

from backend.core.base_processor import BaseProcessor, ProcessingError, Stage
from scripts.enrich_video_metadata import VideoEnricher


class VideoEnrichmentProcessor(BaseProcessor):
    """Optional stage to enrich extracted video links with Brightcove metadata."""

    def __init__(
        self,
        database_service=None,
        config: dict[str, Any] | None = None,
        brightcove_client: Any = None,
        enricher: Any = None,
    ):
        super().__init__(name="video_enrichment_processor", config=config or {})
        self.stage = Stage.VIDEO_ENRICHMENT
        self.database_service = database_service
        self.batch_size = int(os.getenv("BRIGHTCOVE_ENRICHMENT_BATCH_SIZE", os.getenv("BRIGHTCOVE_BATCH_SIZE", "10")))
        self.enabled = os.getenv("ENABLE_BRIGHTCOVE_ENRICHMENT", "false").lower() == "true"
        self.brightcove_client = brightcove_client
        if enricher is not None:
            self.enricher = enricher
        else:
            try:
                self.enricher = VideoEnricher(
                    database_adapter=database_service,
                    brightcove_client=brightcove_client,
                )
            except TypeError:
                self.enricher = VideoEnricher(database_adapter=database_service)
        self.logger.info("VideoEnrichmentProcessor initialized (enabled=%s)", self.enabled)

    def get_dependencies(self) -> list[str]:
        return ["link_extraction"]

    def get_required_inputs(self) -> list[str]:
        return ["document_id"]

    def get_output_tables(self) -> list[str]:
        return ["krai_content.videos"]

    async def process(self, context):
        document_id = getattr(context, "document_id", None)
        if not document_id:
            return self.create_error_result(
                ProcessingError("Missing document_id", self.name, "MISSING_INPUT"),
                metadata={"stage": self.stage.value},
            )

        if not self.enabled:
            return self.create_success_result(
                {
                    "enabled": False,
                    "enriched": 0,
                    "failed": 0,
                    "skipped": 0,
                    "message": "Brightcove enrichment disabled",
                },
                metadata={"stage": self.stage.value, "document_id": str(document_id)},
            )

        force_reenrichment = bool(
            (getattr(context, "processing_config", {}) or {}).get("force_video_reenrichment", False)
        )
        stats = {"enriched": 0, "failed": 0, "skipped": 0}

        videos = await self._get_videos_needing_enrichment(str(document_id), force_reenrichment)
        if not videos:
            return self.create_success_result(
                {"enriched": 0, "failed": 0, "skipped": 0, "videos_found": 0},
                metadata={"stage": self.stage.value, "document_id": str(document_id)},
            )

        for idx in range(0, len(videos), self.batch_size):
            batch = videos[idx : idx + self.batch_size]
            for video in batch:
                video_id = str(video.get("id"))
                video_url = video.get("video_url")

                if not video_url:
                    stats["failed"] += 1
                    await self._mark_video_failed(video_id, "Missing video_url")
                    continue

                try:
                    enriched = await self.enricher.enrich_video(video_url, document_id=str(document_id))
                    if enriched.get("error"):
                        stats["failed"] += 1
                        await self._mark_video_failed(video_id, str(enriched["error"]))
                        continue

                    metadata_payload = enriched.get("metadata") or {}
                    credentials_missing = bool(metadata_payload.get("credentials_missing"))
                    enrichment_error = enriched.get("enrichment_error")

                    if credentials_missing:
                        stats["skipped"] += 1
                        await self._update_video(
                            video_id=video_id,
                            updates={
                                "metadata": {
                                    **(video.get("metadata") or {}),
                                    "needs_enrichment": True,
                                    "credentials_missing": True,
                                },
                                "enrichment_error": None,
                            },
                        )
                        continue

                    if enrichment_error:
                        stats["failed"] += 1
                        await self._mark_video_failed(video_id, enrichment_error)
                        continue

                    merged_metadata = {
                        **(video.get("metadata") or {}),
                        **metadata_payload,
                        "needs_enrichment": False,
                    }

                    await self._update_video(
                        video_id=video_id,
                        updates={
                            "title": enriched.get("title"),
                            "description": enriched.get("description"),
                            "duration": enriched.get("duration"),
                            "thumbnail_url": enriched.get("thumbnail_url"),
                            "published_at": enriched.get("published_at"),
                            "tags": enriched.get("tags") or [],
                            "metadata": merged_metadata,
                            "enrichment_error": None,
                            "enriched_at": datetime.utcnow(),
                        },
                    )
                    stats["enriched"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    await self._mark_video_failed(video_id, str(exc))

        result_data = {
            "enabled": True,
            "videos_found": len(videos),
            "enriched": stats["enriched"],
            "failed": stats["failed"],
            "skipped": stats["skipped"],
            "batch_size": self.batch_size,
        }

        if stats["enriched"] > 0:
            return self.create_success_result(
                result_data,
                metadata={"stage": self.stage.value, "document_id": str(document_id)},
            )

        return self.create_error_result(
            ProcessingError("No videos enriched in this run", self.name, "ENRICHMENT_FAILED"),
            data=result_data,
            metadata={"stage": self.stage.value, "document_id": str(document_id)},
        )

    async def _get_videos_needing_enrichment(self, document_id: str, force: bool) -> list[dict[str, Any]]:
        if hasattr(self.database_service, "get_videos_needing_enrichment"):
            return await self.database_service.get_videos_needing_enrichment(
                document_id=document_id,
                limit=self.batch_size * 100,
                force=force,
            )

        where_force = "" if force else "AND (enriched_at IS NULL OR metadata->>'enrichment_error' IS NOT NULL)"
        return await self.database_service.execute_query(
            f"""
            SELECT id, video_url, platform, metadata, enriched_at
            FROM krai_content.videos
            WHERE document_id = $1::uuid
              AND platform IN ('brightcove', 'youtube', 'vimeo')
              AND (
                COALESCE((metadata->>'needs_enrichment')::boolean, false) = true
                OR COALESCE(BTRIM(title), '') = ''
                OR COALESCE(BTRIM(context_description), '') = ''
              )
              {where_force}
            ORDER BY created_at ASC
            LIMIT $2
            """,
            [document_id, self.batch_size * 100],
        )

    async def _update_video(self, video_id: str, updates: dict[str, Any]) -> None:
        if hasattr(self.database_service, "update_video_enrichment"):
            await self.database_service.update_video_enrichment(video_id, updates)
            return

        # Merge non-column fields (tags, enrichment_error) into metadata JSONB
        # krai_content.videos has no standalone tags or enrichment_error columns.
        metadata = dict(updates.get("metadata") or {})
        if updates.get("tags") is not None:
            metadata["tags"] = updates["tags"]
        if "enrichment_error" in updates:
            if updates["enrichment_error"]:
                metadata["enrichment_error"] = updates["enrichment_error"]
            else:
                metadata.pop("enrichment_error", None)

        await self.database_service.execute_query(
            """
            UPDATE krai_content.videos
            SET
                title = COALESCE($2, title),
                description = COALESCE($3, description),
                duration = COALESCE($4, duration),
                thumbnail_url = COALESCE($5, thumbnail_url),
                published_at = COALESCE($6, published_at),
                metadata = COALESCE(metadata, '{}'::jsonb) || COALESCE($7::jsonb, '{}'::jsonb),
                enriched_at = COALESCE($8, enriched_at),
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            [
                video_id,
                updates.get("title"),
                updates.get("description"),
                updates.get("duration"),
                updates.get("thumbnail_url"),
                updates.get("published_at"),
                json.dumps(metadata) if metadata else None,
                updates.get("enriched_at"),
            ],
        )

    async def _mark_video_failed(self, video_id: str, error_message: str) -> None:
        if hasattr(self.database_service, "mark_video_enrichment_failed"):
            await self.database_service.mark_video_enrichment_failed(video_id, error_message)
            return

        await self.database_service.execute_query(
            """
            UPDATE krai_content.videos
            SET
                metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            [video_id, json.dumps({"needs_enrichment": True, "enrichment_error": error_message[:1000]})],
        )
