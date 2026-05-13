"""Link Extraction Processor (AI) - Extract links using AI assistance and enrichment.

Supports Firecrawl-based link enrichment for improved context and structured extraction.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from uuid import UUID

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage
from backend.services.config_service import ConfigService
from backend.services.context_extraction_service import ContextExtractionService
from backend.services.link_enrichment_service import LinkEnrichmentService
from backend.services.structured_extraction_service import StructuredExtractionService
from backend.services.web_scraping_service import create_web_scraping_service

from .link_extractor import LinkExtractor
from .text_extractor import TextExtractor


class LinkExtractionProcessorAI(BaseProcessor):
    """Stage 6 processor: Extract links and videos using heuristics + AI support."""

    def __init__(
        self,
        database_service=None,
        ai_service=None,
        youtube_api_key: str | None = None,
        link_enrichment_service: LinkEnrichmentService | None = None,
        config_service: ConfigService | None = None,
    ):
        super().__init__(name="link_extraction_processor")
        self.stage = Stage.LINK_EXTRACTION
        self.database_service = database_service
        self.ai_service = ai_service
        self.config_service = config_service

        # Prefer explicit API key, fallback to environment variable
        self.youtube_api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")
        self.link_extractor = LinkExtractor(youtube_api_key=self.youtube_api_key)

        enable_ocr = os.getenv("ENABLE_OCR_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}
        pdf_engine = os.getenv("PDF_ENGINE", "pymupdf")
        self.text_extractor = TextExtractor(prefer_engine=pdf_engine, enable_ocr_fallback=enable_ocr)

        # Phase 5: Context extraction configuration
        self.context_service = ContextExtractionService()
        self.enable_context_extraction = os.getenv("ENABLE_CONTEXT_EXTRACTION", "true").lower() == "true"

        self.enable_link_enrichment = os.getenv("ENABLE_LINK_ENRICHMENT", "false").lower() == "true"
        self.link_enrichment_service = link_enrichment_service

        if self.enable_link_enrichment and not self.link_enrichment_service and self.database_service:
            scraper_service = create_web_scraping_service(config_service=self.config_service)
            self.link_enrichment_service = LinkEnrichmentService(
                web_scraping_service=scraper_service,
                database_service=self.database_service,
                config_service=self.config_service,
            )

        # Initialize structured extraction service if enrichment is enabled
        self.enable_structured_extraction = os.getenv("ENABLE_STRUCTURED_EXTRACTION", "false").lower() == "true"
        self.structured_extraction_service: StructuredExtractionService | None = None
        if self.enable_structured_extraction and self.enable_link_enrichment and self.link_enrichment_service:
            self.structured_extraction_service = StructuredExtractionService(
                web_scraping_service=self.link_enrichment_service._scraper,
                database_service=self.database_service,
                config_service=self.config_service,
            )

        self.logger.info(
            "Link enrichment: %s",
            "enabled" if self.enable_link_enrichment and self.link_enrichment_service else "disabled",
        )
        self.logger.info(
            "Structured extraction: %s",
            "enabled" if self.enable_structured_extraction and self.structured_extraction_service else "disabled",
        )

        if not self.database_service:
            self.logger.warning("LinkExtractionProcessorAI initialized without database service")
        else:
            self.logger.info("LinkExtractionProcessorAI initialized")

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Extract links for the provided processing context."""
        file_path = Path(context.file_path)
        document_id = getattr(context, "document_id", None)

        if not document_id:
            raise ValueError("Processing context must include 'document_id'")

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            adapter.info("Starting link extraction")

            if not file_path.exists():
                adapter.error("File not found: %s", file_path)
                return self._create_result(False, f"File not found: {file_path}", {})

            page_texts = await self._load_page_texts(context, file_path, adapter)
            if not page_texts:
                adapter.warning("No page texts available for link extraction")
                return self._create_result(False, "No page texts available for link extraction", {})

            extraction_result = self.link_extractor.extract_from_document(
                pdf_path=file_path, page_texts=page_texts, document_id=document_id
            )

            links = extraction_result.get("links", [])
            videos = extraction_result.get("videos", [])

            if not links and not videos:
                adapter.info("No links or videos found")
                return self._create_result(True, "No links found", {"links_found": 0, "videos_found": 0})

            self.logger.success(f"Extracted {len(links)} links and {len(videos)} videos")

            manufacturer_id, series_id = await self._get_document_manufacturer_series(str(document_id), adapter)
            enriched_links = self._enrich_links(links, context, manufacturer_id, series_id)
            enriched_videos = self._enrich_videos(videos, manufacturer_id, series_id, document_id)

            # Phase 5: Extract context for links and videos (NEW!)
            if self.enable_context_extraction and context:
                page_texts = await self._load_page_texts(context, file_path, adapter)
                if page_texts:
                    enriched_links = await self._extract_link_contexts(
                        links=enriched_links,
                        page_texts=page_texts,
                        adapter=adapter,
                        document_id=document_id,  # Pass document ID for related chunks
                    )

            # Phase 5: Extract context for videos (NEW!)
            if self.enable_context_extraction and page_texts:
                enriched_videos = await self._extract_video_contexts(
                    videos=enriched_videos,
                    page_texts=page_texts,
                    adapter=adapter,
                    document_id=document_id,  # Pass document ID for related chunks
                )

            link_id_map = await self._save_links_to_db(enriched_links, str(document_id), adapter)
            await self._save_videos_to_db(enriched_videos, link_id_map, adapter)

            if self.enable_link_enrichment and self.link_enrichment_service:
                await self._enrich_document_links(enriched_links, adapter)
                adapter.info("Link enrichment completed")

            return self._create_result(
                True,
                "Link extraction completed",
                {
                    "links_found": len(enriched_links),
                    "videos_found": len(enriched_videos),
                    "links_extracted": len(enriched_links),
                    "video_links_created": len(enriched_videos),
                },
            )

    async def _enrich_document_links(
        self,
        links: list[dict],
        adapter,
    ) -> None:
        """Enrich links with scraped content using LinkEnrichmentService."""

        if not self.link_enrichment_service:
            return

        link_data = [(link.get("id"), link.get("url")) for link in links if link.get("id") and link.get("url")]

        if not link_data:
            adapter.debug("No links to enrich")
            return

        adapter.info("Enriching %s links with scraped content", len(link_data))

        try:
            result = await self.link_enrichment_service.enrich_links_batch(
                link_ids=[link_id for link_id, _ in link_data],
                max_concurrent=3,
            )

            adapter.info(
                "Link enrichment complete: %s enriched, %s failed, %s skipped",
                result.get("enriched", 0),
                result.get("failed", 0),
                result.get("skipped", 0),
            )

            # Trigger structured extraction for enriched links if enabled
            if self.enable_structured_extraction and self.structured_extraction_service:
                await self._run_structured_extraction_on_links(link_data, adapter)
        except Exception as exc:  # pragma: no cover - defensive guard
            adapter.error(f"Link enrichment failed: {exc}")

    async def _run_structured_extraction_on_links(
        self,
        link_data: list[tuple[str, str]],
        adapter,
    ) -> None:
        """Run structured extraction batch on enriched links."""
        if not self.structured_extraction_service:
            return

        link_ids = [link_id for link_id, _ in link_data if link_id]
        if not link_ids:
            adapter.debug("No link IDs available for structured extraction")
            return

        adapter.info("Running structured extraction on %s enriched links", len(link_ids))

        try:
            extraction_result = await self.structured_extraction_service.batch_extract(
                source_ids=link_ids,
                source_type="link",
                max_concurrent=2,
            )
            adapter.info(
                "Structured extraction complete: %s completed, %s failed, %s total",
                extraction_result.get("completed", 0),
                extraction_result.get("failed", 0),
                extraction_result.get("total", 0),
            )
        except Exception as exc:
            adapter.error("Structured extraction batch failed: %s", exc)

    async def _load_page_texts(self, context, file_path: Path, adapter) -> dict[int, str]:
        """Load page texts from context, database, or by re-extracting from PDF."""
        if hasattr(context, "page_texts") and context.page_texts:
            return context.page_texts

        # Attempt to rebuild from chunks stored in the database
        if self.database_service:
            try:
                rows = await self.database_service.execute_query(
                    """
                    SELECT page_start, text_chunk
                    FROM krai_intelligence.chunks
                    WHERE document_id = $1
                    ORDER BY chunk_index
                    """.strip(),
                    [str(context.document_id)],
                )

                page_texts: dict[int, list[str]] = {}
                for row in rows or []:
                    page = row.get("page_start")
                    content = row.get("text_chunk") or ""
                    if page is not None and content:
                        page_texts.setdefault(page, []).append(content)

                if page_texts:
                    return {page: "\n".join(parts) for page, parts in page_texts.items()}
            except Exception as exc:
                adapter.debug("Failed to load page texts from database: %s", exc)

        # Fallback: Re-run text extraction on the PDF
        try:
            page_texts, _ = self.text_extractor.extract_text(file_path)
            return page_texts
        except Exception as exc:
            adapter.error("Failed to extract text for link stage: %s", exc)
            return {}

    async def _get_document_manufacturer_series(self, document_id: str, adapter) -> tuple[str | None, str | None]:
        """Retrieve manufacturer_id and series_id for the document."""
        if not self.database_service:
            return None, None

        try:
            result = await self.database_service.execute_query(
                "SELECT product_id FROM krai_core.document_products WHERE document_id = $1 LIMIT 1",
                [document_id],
            )

            if result:
                product_id = result[0].get("product_id")
                if product_id:
                    product = await self.database_service.execute_query(
                        "SELECT manufacturer_id, series_id FROM krai_core.products WHERE id = $1 LIMIT 1",
                        [str(product_id)],
                    )
                    if product:
                        product_row = product[0]
                        return product_row.get("manufacturer_id"), product_row.get("series_id")
        except Exception as exc:
            adapter.debug("Failed to fetch manufacturer/series: %s", exc)

        return None, None

    def _enrich_links(
        self, links: list[dict], context, manufacturer_id: str | None, series_id: str | None
    ) -> list[dict]:
        """Attach document metadata to links and derive related error codes."""
        if not links:
            return []

        for link in links:
            link.setdefault("document_id", str(context.document_id))
            link.setdefault("manufacturer", context.manufacturer)
            link["manufacturer_id"] = manufacturer_id
            link["series_id"] = series_id

            related_codes = self._extract_error_codes_from_link(link, context)
            if related_codes:
                link["related_error_codes"] = related_codes

        return links

    def _enrich_videos(
        self, videos: list[dict], manufacturer_id: str | None, series_id: str | None, document_id: str
    ) -> list[dict]:
        """Attach additional metadata for video records."""
        if not videos:
            return []

        for video in videos:
            video["manufacturer_id"] = manufacturer_id
            video["series_id"] = series_id
            video.setdefault("document_id", str(document_id))

        return videos

    def _extract_error_codes_from_link(self, link: dict, context) -> list[str]:
        """Extract error codes from context or link description."""
        codes: list[str] = []

        if hasattr(context, "error_codes") and context.error_codes:
            for code_info in context.error_codes:
                if isinstance(code_info, dict) and code_info.get("code"):
                    codes.append(code_info["code"])

        description = link.get("description") or ""
        if description:
            matches = re.findall(r"\b[A-Z]-?\d{3,4}\b", description)
            codes.extend(matches)

        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                unique_codes.append(code)
                seen.add(code)

        return unique_codes

    async def _save_links_to_db(self, links: list[dict], document_id: str, adapter) -> dict[str, str]:
        """Persist links to the database. Returns a URL → link_id map."""
        if not links or not self.database_service:
            return {}

        link_id_map: dict[str, str] = {}

        for link in links:
            try:
                url = link.get("url")
                if not url:
                    continue

                link_payload = {
                    "document_id": document_id,
                    "url": url,
                    "description": link.get("description"),
                    "link_type": link.get("link_type", "external"),
                    "link_category": link.get("link_category", "external"),
                    "page_number": link.get("page_number"),
                    "position_data": json.dumps(link.get("position_data") or {}),
                    "confidence_score": link.get("confidence_score", 0.5),
                    "manufacturer_id": link.get("manufacturer_id"),
                    "series_id": link.get("series_id"),
                    "related_error_codes": link.get("related_error_codes") or [],
                    # Phase 5: Context extraction fields
                    "context_description": link.get("context_description"),
                    "related_chunks": link.get("related_chunks", []),
                    "metadata": json.dumps(
                        {
                            **(link.get("scraped_metadata") or {}),
                            "scrape_status": link.get("scrape_status", "pending"),
                            "scraped_at": link.get("scraped_at"),
                        }
                    ),
                }

                existing_rows = await self.database_service.execute_query(
                    "SELECT id FROM krai_content.links WHERE document_id = $1 AND url = $2 LIMIT 1",
                    [document_id, url],
                )
                existing_id = existing_rows[0].get("id") if existing_rows else None

                if existing_id:
                    update_rows = await self.database_service.execute_query(
                        """
                        UPDATE krai_content.links
                        SET
                            description = $2,
                            link_type = $3,
                            link_category = $4,
                            page_number = $5,
                            position_data = $6::jsonb,
                            confidence_score = $7,
                            manufacturer_id = $8,
                            series_id = $9,
                            related_error_codes = $10::text[],
                            context_description = $11,
                            related_chunks = $12::uuid[],
                            metadata = $13::jsonb,
                            updated_at = NOW()
                        WHERE id = $1
                        RETURNING id
                        """.strip(),
                        [
                            str(existing_id),
                            link_payload["description"],
                            link_payload["link_type"],
                            link_payload["link_category"],
                            link_payload["page_number"],
                            link_payload["position_data"],
                            link_payload["confidence_score"],
                            link_payload["manufacturer_id"],
                            link_payload["series_id"],
                            link_payload["related_error_codes"],
                            link_payload["context_description"],
                            link_payload["related_chunks"],
                            link_payload["metadata"],
                        ],
                    )
                    link_id = update_rows[0].get("id") if update_rows else str(existing_id)
                else:
                    insert_rows = await self.database_service.execute_query(
                        """
                        INSERT INTO krai_content.links
                            (document_id, url, description, link_type, link_category, page_number,
                             position_data, confidence_score, manufacturer_id, series_id,
                             related_error_codes, context_description, related_chunks, metadata)
                        VALUES
                            ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10,
                             $11::text[], $12, $13::uuid[], $14::jsonb)
                        RETURNING id
                        """.strip(),
                        [
                            document_id,
                            url,
                            link_payload["description"],
                            link_payload["link_type"],
                            link_payload["link_category"],
                            link_payload["page_number"],
                            link_payload["position_data"],
                            link_payload["confidence_score"],
                            link_payload["manufacturer_id"],
                            link_payload["series_id"],
                            link_payload["related_error_codes"],
                            link_payload["context_description"],
                            link_payload["related_chunks"],
                            link_payload["metadata"],
                        ],
                    )
                    link_id = insert_rows[0].get("id") if insert_rows else None

                if link_id:
                    link_id_map[url] = str(link_id)
                    link["id"] = str(link_id)

            except Exception as exc:
                adapter.warning("Failed to persist link %s: %s", link.get("url"), exc)

        return link_id_map

    async def _save_videos_to_db(self, videos: list[dict], link_id_map: dict[str, str], adapter):
        """Persist associated videos to the database."""
        if not videos or not self.database_service:
            return

        for video in videos:
            try:
                video_url = video.get("source_url") or video.get("url") or video.get("video_url")
                link_id = link_id_map.get(video_url) if video_url else video.get("link_id")

                if not link_id:
                    continue

                video_payload = {
                    "link_id": link_id,
                    "document_id": video.get("document_id"),
                    "youtube_id": video.get("youtube_id"),
                    "title": video.get("title"),
                    "description": video.get("description"),
                    "thumbnail_url": video.get("thumbnail_url"),
                    "duration": video.get("duration"),
                    "platform": video.get("link_category") or video.get("platform") or "youtube",
                    "video_url": video_url,
                    "metadata": json.dumps(video.get("metadata") or {}),
                    "manufacturer_id": video.get("manufacturer_id"),
                    "series_id": video.get("series_id"),
                    # Phase 5: Context extraction fields
                    "context_description": video.get("context_description"),
                    "page_number": video.get("page_number"),
                    "related_products": video.get("related_products", []),
                    "related_chunks": video.get("related_chunks", []),
                }

                existing: list[dict] = []
                if video_payload["youtube_id"]:
                    existing = await self.database_service.execute_query(
                        "SELECT id FROM krai_content.videos WHERE youtube_id = $1 LIMIT 1",
                        [video_payload["youtube_id"]],
                    )
                elif video_payload["video_url"]:
                    existing = await self.database_service.execute_query(
                        """
                        SELECT id
                        FROM krai_content.videos
                        WHERE video_url = $1 AND youtube_id IS NULL
                        LIMIT 1
                        """.strip(),
                        [video_payload["video_url"]],
                    )

                if existing:
                    await self.database_service.execute_query(
                        """
                        UPDATE krai_content.videos
                        SET
                            link_id = $2,
                            document_id = $3,
                            youtube_id = $4,
                            platform = $5,
                            video_url = $6,
                            title = $7,
                            description = $8,
                            thumbnail_url = $9,
                            duration = $10,
                            manufacturer_id = $11,
                            series_id = $12,
                            metadata = $13::jsonb,
                            context_description = $14,
                            related_products = $15::text[],
                            related_chunks = $16::uuid[],
                            page_number = $17,
                            updated_at = NOW()
                        WHERE id = $1
                        """.strip(),
                        [
                            str(existing[0]["id"]),
                            link_id,
                            video_payload["document_id"],
                            video_payload["youtube_id"],
                            video_payload["platform"],
                            video_payload["video_url"],
                            video_payload["title"],
                            video_payload["description"],
                            video_payload["thumbnail_url"],
                            video_payload["duration"],
                            video_payload["manufacturer_id"],
                            video_payload["series_id"],
                            video_payload["metadata"],
                            video_payload["context_description"],
                            video_payload["related_products"],
                            video_payload["related_chunks"],
                            video_payload["page_number"],
                        ],
                    )
                    continue

                await self.database_service.execute_query(
                    """
                    INSERT INTO krai_content.videos
                        (link_id, document_id, youtube_id, platform, video_url, title, description, thumbnail_url,
                         duration, manufacturer_id, series_id, metadata, context_description,
                         related_products, related_chunks, page_number)
                    VALUES
                        ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13,
                         $14::text[], $15::uuid[], $16)
                    """.strip(),
                    [
                        link_id,
                        video_payload["document_id"],
                        video_payload["youtube_id"],
                        video_payload["platform"],
                        video_payload["video_url"],
                        video_payload["title"],
                        video_payload["description"],
                        video_payload["thumbnail_url"],
                        video_payload["duration"],
                        video_payload["manufacturer_id"],
                        video_payload["series_id"],
                        video_payload["metadata"],
                        video_payload["context_description"],
                        video_payload["related_products"],
                        video_payload["related_chunks"],
                        video_payload["page_number"],
                    ],
                )

            except Exception as exc:
                adapter.warning("Failed to persist video %s: %s", video.get("title"), exc)

    async def _extract_link_contexts(
        self, links: list[dict], page_texts: dict[int, str], adapter, document_id: UUID | None = None
    ) -> list[dict]:
        """
        Extract context for all links using ContextExtractionService.

        Args:
            links: List of link dictionaries
            page_texts: Dict mapping page_number to page_text
            adapter: Logger adapter
            document_id: Optional document ID for related chunks extraction

        Returns:
            List of links with context metadata added
        """
        links_with_context: list[dict] = []
        related_chunks_cache: dict[int, list[str]] = {}

        for link in links:
            page_number = link.get("page_number")
            if not page_number or page_number not in page_texts:
                adapter.warning("No page text available for link on page %s", page_number)
                links_with_context.append(link)
                continue

            page_text = page_texts[page_number]
            link_url = link.get("url")

            try:
                # Extract context using ContextExtractionService
                context_data = self.context_service.extract_link_context(
                    page_text=page_text, page_number=page_number, link_url=link_url
                )

                # Add context data to link dict
                link["context_description"] = context_data["context_description"]
                link["related_products"] = context_data.get("related_products", [])
                if page_number not in related_chunks_cache:
                    related_chunks_cache[page_number] = await self._get_related_chunks(
                        page_number, document_id, adapter
                    )
                link["related_chunks"] = related_chunks_cache.get(page_number, [])
                # related_error_codes already exists in link enrichment

                links_with_context.append(link)

            except Exception as e:
                adapter.error("Failed to extract context for link on page %s: %s", page_number, e)
                links_with_context.append(link)

        adapter.info("Extracted context for %d links", len(links_with_context))
        return links_with_context

    async def _get_related_chunks(self, page_number: int, document_id: UUID, adapter) -> list[str]:
        """
        Extract related chunk IDs for a given page number.

        Args:
            page_number: Page number to find chunks for
            document_id: Document ID to query chunks
            adapter: Logger adapter

        Returns:
            List of chunk IDs that include the given page
        """
        if not self.database_service or not document_id:
            return []

        try:
            rows = await self.database_service.execute_query(
                """
                SELECT id
                FROM krai_intelligence.chunks
                WHERE document_id = $1
                  AND COALESCE(page_start, 0) <= $2
                  AND COALESCE(page_end, page_start) >= $2
                """.strip(),
                [str(document_id), int(page_number)],
            )

            if rows:
                chunk_ids = [str(chunk["id"]) for chunk in rows]
                adapter.debug(f"Found {len(chunk_ids)} related chunks for page {page_number}")
                return chunk_ids

            return []

        except Exception as e:
            adapter.warning(f"Failed to get related chunks for page {page_number}: {e}")
            return []

    async def _extract_video_contexts(
        self, videos: list[dict], page_texts: dict[int, str], adapter, document_id: UUID | None = None
    ) -> list[dict]:
        """
        Extract context for all videos using ContextExtractionService.

        Args:
            videos: List of video dictionaries
            page_texts: Dict mapping page_number to page_text
            adapter: Logger adapter
            document_id: Optional document ID for related chunks extraction

        Returns:
            List of videos with context metadata added
        """
        videos_with_context: list[dict] = []
        related_chunks_cache: dict[int, list[str]] = {}

        for video in videos:
            page_number = video.get("page_number")
            if not page_number or page_number not in page_texts:
                adapter.warning("No page text available for video on page %s", page_number)
                videos_with_context.append(video)
                continue

            page_text = page_texts[page_number]
            video_url = video.get("source_url") or video.get("url") or video.get("video_url")

            try:
                # Extract context using ContextExtractionService
                context_data = self.context_service.extract_video_context(
                    page_text=page_text, page_number=page_number, video_url=video_url
                )

                # Add context data to video dict
                video["context_description"] = context_data["context_description"]
                video["page_header"] = context_data["page_header"]
                video["related_error_codes"] = context_data.get("related_error_codes", [])
                video["related_products"] = context_data.get("related_products", [])
                if page_number not in related_chunks_cache:
                    related_chunks_cache[page_number] = await self._get_related_chunks(
                        page_number, document_id, adapter
                    )
                video["related_chunks"] = related_chunks_cache.get(page_number, [])

                videos_with_context.append(video)

            except Exception as e:
                adapter.error("Failed to extract context for video on page %s: %s", page_number, e)
                videos_with_context.append(video)

        adapter.info("Extracted context for %d videos", len(videos_with_context))
        return videos_with_context

    def _create_result(self, success: bool, message: str, data: dict) -> ProcessingResult:
        """Create a processing result object using BaseProcessor helpers"""
        if success:
            return self.create_success_result(data=data, metadata={"message": message})
        error = ProcessingError(message, self.name, "LINK_EXTRACTION_ERROR")
        return self.create_error_result(error=error, metadata={})
