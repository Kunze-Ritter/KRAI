"""
Progressive Search Implementation
Yields results as they're found for real-time streaming
"""

import logging
import os
import re
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


async def process_query_progressive(query: str, database_service, ai_service) -> AsyncGenerator[str, None]:
    """
    Process query progressively, yielding results as they're found

    This enables real-time streaming to the user:
    1. Search Service Manuals → yield results
    2. Search Parts → yield results
    3. Search Videos → yield results
    4. Search Bulletins → yield results
    """

    # Detect error codes
    error_code_pattern = r"\b[A-Z]?\d{1,3}[.-]\d{1,2}[.-]?\d{0,2}\b|\b[A-Z]\d{4}[A-Z]?\b"
    error_codes = re.findall(error_code_pattern, query, re.IGNORECASE)

    if not error_codes:
        yield "⚠️ Kein Fehlercode erkannt. Bitte geben Sie einen Fehlercode ein (z.B. 'HP 11.00.02').\n"
        return

    # Process first error code
    code = error_codes[0]

    # STEP 1: Search Service Manuals
    yield "# 🔍 Suche in Service Manuals...\n\n"

    try:
        # Fix: Escape % for PostgreSQL query
        search_code = code.replace("%", "")
        error_info = (
            database_service.client.table("vw_error_codes")
            .select("error_code, error_description, manufacturer_id, page_number, document_id, chunk_id")
            .ilike("error_code", f"*{search_code}*")
            .order("confidence_score", desc=True)
            .limit(1)
            .execute()
        )

        if error_info.data:
            result = error_info.data[0]

            # Extract IDs early for use throughout
            mfr_id = result.get("manufacturer_id")
            doc_id = result.get("document_id")
            chunk_id = result.get("chunk_id")

            yield f"## ❌ Fehlercode: {result.get('error_code', code)}\n\n"
            yield f"**Beschreibung:** {result.get('error_description', 'N/A')}\n\n"

            # Check for images
            if chunk_id:
                image_response = (
                    database_service.client.table("vw_images")
                    .select("storage_url, ai_description, manual_description, image_type")
                    .eq("chunk_id", chunk_id)
                    .limit(3)
                    .execute()
                )

                if image_response.data:
                    for img in image_response.data:
                        img_url = img.get("storage_url")
                        # Prefer manual description, fallback to AI description
                        caption = img.get("manual_description") or img.get("ai_description", "")
                        if img_url:
                            yield f"![{caption}]({img_url})\n"
                            if caption:
                                yield f"*{caption}*\n"
                            yield "\n"

            # Get document name
            if doc_id:
                doc_response = (
                    database_service.client.table("vw_documents").select("filename").eq("id", doc_id).limit(1).execute()
                )
                if doc_response.data:
                    doc_name = doc_response.data[0].get("filename", "Service Manual")
                    page = result.get("page_number", "N/A")
                    yield f"📄 **Quelle:** {doc_name} (Seite {page})\n\n"

            # Search for solution in chunks
            chunk_results = (
                database_service.client.table("vw_intelligence_chunks")
                .select("text_chunk")
                .ilike("text_chunk", f"*{search_code}*")
                .limit(5)
                .execute()
            )

            steps = []
            if chunk_results.data:
                # Extract solution steps
                for chunk in chunk_results.data:
                    text = chunk.get("text_chunk", "")
                    if "recommended action" in text.lower() or "procedure" in text.lower():
                        # Extract numbered steps
                        extracted_steps = re.findall(r"\d+\.\s+[^\n]+", text)
                        if extracted_steps:
                            steps = extracted_steps[:5]
                            break

            if steps:
                solution_text = "\n".join(steps)
                translated_solution = solution_text
                enable_translation = os.getenv("ENABLE_SOLUTION_TRANSLATION", "false").lower() == "true"
                if ai_service and hasattr(ai_service, "translate_text"):
                    try:
                        translated_solution = await ai_service.translate_text(
                            solution_text,
                            target_language=os.getenv("SOLUTION_TRANSLATION_LANGUAGE", "de"),
                            enable_translation=enable_translation,
                        )
                    except Exception as translate_error:
                        logger.warning(f"Translation failed, falling back to original text: {translate_error}")
                yield "### ✅ Lösungsschritte:\n\n"
                for line in translated_solution.splitlines():
                    if line.strip():
                        yield f"{line}\n"
                yield "\n"

            yield "---\n\n"

            # STEP 2: Search Parts (based on solution keywords)
            yield "# 🔧 Suche Ersatzteile...\n\n"

            # Extract keywords from solution steps
            solution_text = " ".join(steps) if "steps" in locals() else ""
            keywords = []
            common_parts = [
                "formatter",
                "fuser",
                "scanner",
                "adf",
                "drum",
                "toner",
                "transfer",
                "roller",
                "belt",
                "motor",
                "sensor",
                "board",
            ]

            for keyword in common_parts:
                if keyword in solution_text.lower():
                    keywords.append(keyword)

            if keywords:
                parts_found = []

                for keyword in keywords[:3]:  # Max 3 keywords
                    part_response = (
                        database_service.client.table("vw_parts")
                        .select("part_number, part_name")
                        .eq("manufacturer_id", mfr_id)
                        .ilike("part_name", f"*{keyword}*")
                        .limit(3)
                        .execute()
                    )

                    if part_response.data:
                        parts_found.extend(part_response.data)

                if parts_found:
                    # Deduplicate by part_number
                    seen = set()
                    for part in parts_found:
                        pn = part.get("part_number")
                        if pn and pn not in seen:
                            seen.add(pn)
                            name = part.get("part_name", "N/A")
                            yield f"• **{pn}** - {name}\n"
                    yield "\n"
                else:
                    yield "⚠️ Keine passenden Ersatzteile gefunden.\n\n"
            else:
                yield "⚠️ Keine Ersatzteile in der Lösung erwähnt.\n\n"

            yield "---\n\n"

            # STEP 3: Search Videos (by keywords in title/description)
            yield "# 🎥 Suche Videos...\n\n"

            # Build search keywords from error code and solution
            search_keywords = []

            # Add error code parts (e.g. "66.60" from "66.60.32")
            code_parts = code.split(".")
            if len(code_parts) >= 2:
                search_keywords.append(f"{code_parts[0]}.{code_parts[1]}")

            # Add keywords from solution (formatter, fuser, etc.)
            if "steps" in locals() and steps:
                solution_lower = " ".join(steps).lower()
                for keyword in ["formatter", "fuser", "scanner", "adf", "drum", "maintenance"]:
                    if keyword in solution_lower:
                        search_keywords.append(keyword)

            # Get manufacturer name for search
            mfr_name = None
            if mfr_id:
                mfr_response = (
                    database_service.client.table("vw_manufacturers").select("name").eq("id", mfr_id).limit(1).execute()
                )
                if mfr_response.data:
                    mfr_name = mfr_response.data[0].get("name")
                    search_keywords.append(mfr_name)

            # Search videos by keywords
            videos_found = []
            for keyword in search_keywords[:3]:  # Max 3 keywords
                video_response = (
                    database_service.client.table("vw_videos")
                    .select("title, video_url, youtube_id, platform, duration, description")
                    .or_(f"title.ilike.*{keyword}*,description.ilike.*{keyword}*")
                    .limit(5)
                    .execute()
                )

                if video_response.data:
                    videos_found.extend(video_response.data)

            if videos_found:
                # Deduplicate by URL
                seen_urls = set()
                for video in videos_found[:3]:  # Max 3 videos
                    title = video.get("title", "Video")
                    url = video.get("video_url")
                    yt_id = video.get("youtube_id")
                    duration = video.get("duration")

                    if url:
                        video_link = url
                    elif yt_id:
                        video_link = f"https://youtube.com/watch?v={yt_id}"
                    else:
                        continue

                    if video_link in seen_urls:
                        continue
                    seen_urls.add(video_link)

                    duration_str = f" ({duration//60}:{duration%60:02d})" if duration else ""
                    yield f"• [{title[:60]}{duration_str}]({video_link})\n"
                yield "\n"
            else:
                yield "⚠️ Keine relevanten Videos gefunden.\n\n"

            yield "---\n\n"

            # STEP 4: Search Service Bulletins (documents)
            yield "# 📋 Suche Service Bulletins...\n\n"

            if mfr_id:
                # Search for service bulletin documents
                bulletin_response = (
                    database_service.client.table("vw_documents")
                    .select("filename, document_type, page_count")
                    .eq("manufacturer_id", mfr_id)
                    .ilike("document_type", "*bulletin*")
                    .limit(5)
                    .execute()
                )

                if bulletin_response.data:
                    for doc in bulletin_response.data:
                        filename = doc.get("filename", "N/A")
                        doc_type = doc.get("document_type", "")
                        pages = doc.get("page_count", 0)
                        page_str = f" ({pages} Seiten)" if pages else ""
                        yield f"• **{filename}**{page_str}\n"
                    yield "\n"
                else:
                    yield "⚠️ Keine Service Bulletins gefunden.\n\n"
            else:
                yield "⚠️ Keine Service Bulletins gefunden.\n\n"
        else:
            yield f"⚠️ Fehlercode '{code}' nicht in der Datenbank gefunden.\n"

    except Exception as e:
        logger.error(f"Progressive search error: {e}")
        yield f"❌ Fehler bei der Suche: {e!s}\n"
