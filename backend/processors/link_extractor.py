"""
Link Extractor - Extract URLs and Video Links from Documents

Extracts:
- PDF annotations/hyperlinks
- URLs from text (http://, https://)
- YouTube video links with metadata
- Support/Download links
"""

import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import requests

from backend.utils.link_cleaner import clean_url, merge_multiline_url

from .logger import get_logger

logger = get_logger(name="krai.link_extractor")

try:
    import pdfplumber

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pdfplumber not available - PDF link extraction disabled")


class LinkExtractor:
    """Extract and process links from documents"""

    def __init__(self, youtube_api_key: str | None = None):
        """
        Initialize link extractor

        Args:
            youtube_api_key: Optional YouTube Data API key for metadata
        """
        self.logger = get_logger()
        self.youtube_api_key = youtube_api_key

        # URL patterns
        self.url_pattern = re.compile(
            r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b"
            r"(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)",
            re.IGNORECASE,
        )

        # YouTube patterns
        self.youtube_patterns = [
            re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})", re.IGNORECASE),
            re.compile(r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})", re.IGNORECASE),
            re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})", re.IGNORECASE),
        ]

    @staticmethod
    def _decode_pdf_value(value) -> str:
        """Best-effort decoder for PDF annotation values that may be bytes."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if not isinstance(value, bytes | bytearray):
            return str(value)

        raw = bytes(value)
        # Avoid UTF-16 truncation errors on odd-length payloads.
        if len(raw) % 2 == 1:
            raw = raw[:-1]

        encodings = ["utf-8", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"]
        for encoding in encodings:
            try:
                return raw.decode(encoding).strip()
            except Exception:  # nosec B112
                continue

        return raw.decode("utf-8", errors="ignore").strip()

    def extract_from_document(
        self,
        pdf_path: Path,
        page_texts: dict[int, str],
        document_id: UUID,
    ) -> dict[str, Any]:
        """
        Extract all links from document

        Args:
            pdf_path: Path to PDF file
            page_texts: Dictionary of {page_number: text}
            document_id: Document UUID

        Returns:
            Dict with extracted links and videos
        """
        all_links = []
        all_videos = []

        # Extract from PDF annotations
        if PDF_AVAILABLE and pdf_path.exists():
            pdf_links = self._extract_pdf_links(pdf_path)
            all_links.extend(pdf_links)

        # Extract from text
        for page_num, text in page_texts.items():
            text_links = self._extract_text_links(text, page_num)
            all_links.extend(text_links)

        # Deduplicate links
        unique_links = self._deduplicate_links(all_links)

        # Classify and enrich links
        enriched_links = []
        for link in unique_links:
            link["document_id"] = str(document_id)
            link["id"] = str(uuid4())

            url = link["url"]

            # Check for direct video files FIRST (before other checks)
            if self._is_direct_video_url(url):
                # Direct video file (MP4, WebM, etc.)
                video_metadata = self._create_direct_video_metadata(
                    url, link["id"], page_number=link.get("page_number")
                )
                all_videos.append(video_metadata)
                link["video_id"] = video_metadata["id"]
                link["link_type"] = "video"
                link["link_category"] = "direct"

            # Check if YouTube
            elif youtube_id := self._extract_youtube_id(url):
                # Get YouTube metadata
                video_metadata = self._fetch_youtube_metadata(youtube_id)
                if video_metadata:
                    video_metadata["link_id"] = link["id"]
                    video_metadata["id"] = str(uuid4())
                    video_metadata["video_url"] = video_metadata.get("video_url") or url
                    video_metadata["page_number"] = link.get("page_number")
                    all_videos.append(video_metadata)
                    link["video_id"] = video_metadata["id"]
                    link["link_type"] = "video"
                    link["link_category"] = "youtube"
                else:
                    link["link_type"] = "video"
                    link["link_category"] = "youtube"

            # Check for other video platforms
            elif self._is_video_platform(url):
                platform = self._detect_video_platform(url)
                video_metadata = self._create_generic_video_metadata(
                    url, link["id"], platform, page_number=link.get("page_number")
                )
                all_videos.append(video_metadata)
                link["video_id"] = video_metadata["id"]
                link["link_type"] = "video"
                link["link_category"] = platform

            else:
                # Classify link type
                link["link_type"] = self._classify_link(url)
                link["link_category"] = self._categorize_link(url)

            enriched_links.append(link)

        self.logger.success(f"Extracted {len(enriched_links)} unique links ({len(all_videos)} videos)")

        return {
            "links": enriched_links,
            "videos": all_videos,
            "total_links": len(enriched_links),
            "total_videos": len(all_videos),
        }

    def _extract_pdf_links(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract links from PDF annotations"""
        links = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Some PDFs contain malformed annotation metadata; isolate per-page failures.
                    try:
                        annots = page.annots if hasattr(page, "annots") else None
                    except Exception as page_error:
                        self.logger.debug(
                            "Skipping annotations for page %s due to parse error: %s",
                            page_num,
                            page_error,
                        )
                        continue

                    if annots:
                        for annot in annots:
                            try:
                                if "uri" in annot or "URI" in annot:
                                    url_raw = annot.get("uri") or annot.get("URI")
                                    url_text = self._decode_pdf_value(url_raw)

                                    # Clean URL
                                    url = clean_url(url_text) if url_text else None

                                    if url:
                                        # Safely decode description (can be bytes in arbitrary encodings).
                                        desc_raw = annot.get("contents", "")
                                        description = self._decode_pdf_value(desc_raw)

                                        links.append(
                                            {
                                                "url": url,
                                                "page_number": page_num,
                                                "description": description,
                                                "position_data": {"rect": annot.get("rect"), "type": "pdf_annotation"},
                                                "confidence_score": 1.0,  # PDF annotations are reliable
                                            }
                                        )
                            except Exception as annot_error:
                                # Skip problematic annotations silently
                                self.logger.debug(f"Skipped annotation on page {page_num}: {annot_error}")
        except Exception as e:
            self.logger.warning(f"Failed to extract PDF links: {e}")

        return links

    def _extract_text_links(self, text: str, page_num: int) -> list[dict[str, Any]]:
        """Extract URLs from text using regex"""
        links = []
        potential_incomplete_urls = []

        # Find all URLs
        matches = self.url_pattern.finditer(text)

        for match in matches:
            url = match.group(0)

            # Filter placeholder URLs (x.x.x.x, 0.0.0.0, etc.)
            if self._is_placeholder_url(url):
                self.logger.debug(f"Skipping placeholder URL: {url}")
                continue

            # Clean URL (remove trailing punctuation, etc.)
            cleaned_url = clean_url(url)

            if not cleaned_url:
                # Store as potentially incomplete (might continue on next line)
                potential_incomplete_urls.append({"original": url, "position": match.end()})
                continue

            url = cleaned_url

            # Get context around URL (150 chars before/after for better descriptions)
            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 150)
            context = text[start:end].strip()

            # Clean context: remove excessive whitespace, newlines
            context = " ".join(context.split())

            # Extract better description from context
            description = self._extract_link_description(context, url)

            links.append(
                {
                    "url": url,
                    "page_number": page_num,
                    "description": description,
                    "position_data": {"char_start": match.start(), "char_end": match.end(), "type": "text_extraction"},
                    "confidence_score": 0.9,  # Text extraction is pretty reliable
                }
            )

        # Try to merge incomplete URLs with next line content
        if potential_incomplete_urls:
            # Split text into lines
            lines = text.split("\n")

            for incomplete in potential_incomplete_urls:
                original_url = incomplete["original"]

                # Find which line this URL is on
                for i, line in enumerate(lines):
                    if original_url in line:
                        # Try to merge with next line
                        if i + 1 < len(lines):
                            merged_url = merge_multiline_url(line, lines[i + 1])
                            if merged_url:
                                self.logger.debug(f"Merged multiline URL: {merged_url}")
                                links.append(
                                    {
                                        "url": merged_url,
                                        "page_number": page_num,
                                        "description": f"{line} {lines[i + 1]}",
                                        "position_data": {"type": "text_multiline"},
                                        "confidence_score": 0.7,  # Lower confidence for merged URLs
                                    }
                                )
                        break

        return links

    def _extract_youtube_id(self, url: str) -> str | None:
        """Extract YouTube video ID from URL"""
        for pattern in self.youtube_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def _fetch_youtube_metadata(self, youtube_id: str) -> dict[str, Any] | None:
        """
        Fetch YouTube video metadata

        If API key is available, uses YouTube Data API.
        Otherwise, uses oembed (limited data).
        """
        try:
            api_key = (self.youtube_api_key or "").strip()
            if api_key and api_key.lower() not in {"your-youtube-api-key-here", "changeme", "placeholder"}:
                # Use YouTube Data API v3
                url = "https://www.googleapis.com/youtube/v3/videos"
                params = {"part": "snippet,contentDetails,statistics", "id": youtube_id, "key": api_key}

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                if data.get("items"):
                    item = data["items"][0]
                    snippet = item.get("snippet", {})
                    details = item.get("contentDetails", {})

                    # Parse duration (PT15M33S -> seconds)
                    duration = self._parse_youtube_duration(details.get("duration", ""))

                    thumbnail_url = snippet.get("thumbnails", {}).get("high", {}).get("url") or snippet.get(
                        "thumbnails", {}
                    ).get("default", {}).get("url")

                    return {
                        "youtube_id": youtube_id,
                        "title": snippet.get("title"),
                        "description": snippet.get("description"),
                        "thumbnail_url": thumbnail_url,
                        "duration": duration,
                        "channel_id": snippet.get("channelId"),
                        "channel_title": snippet.get("channelTitle"),
                        "published_at": snippet.get("publishedAt"),
                        "metadata": {
                            "category_id": snippet.get("categoryId"),
                            "tags": snippet.get("tags", []),
                            "default_language": snippet.get("defaultLanguage"),
                        },
                    }
            else:
                # Fallback to oEmbed (no API key required, limited data)
                url = "https://www.youtube.com/oembed"
                params = {"url": f"https://www.youtube.com/watch?v={youtube_id}", "format": "json"}

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()

                return {
                    "youtube_id": youtube_id,
                    "title": data.get("title"),
                    "description": None,
                    "thumbnail_url": data.get("thumbnail_url"),
                    "duration": None,
                    "channel_id": None,
                    "channel_title": data.get("author_name"),
                    "published_at": None,
                    "metadata": {"provider_name": data.get("provider_name"), "provider_url": data.get("provider_url")},
                }

        except Exception as e:
            self.logger.warning(f"Failed to fetch YouTube metadata for {youtube_id}: {e}")
            return None

    def analyze_video_thumbnail(
        self,
        video_metadata: dict[str, Any],
        enable_ocr: bool = True,
        enable_vision: bool = True,
    ) -> dict[str, Any]:
        """
        Analyze video thumbnail with OCR and Vision AI

        Args:
            video_metadata: Video metadata dict with thumbnail_url
            enable_ocr: Run OCR on thumbnail
            enable_vision: Run Vision AI on thumbnail

        Returns:
            Updated video_metadata with thumbnail_ocr_text and thumbnail_ai_description
        """
        thumbnail_url = video_metadata.get("thumbnail_url")
        if not thumbnail_url:
            return video_metadata

        try:
            import base64
            from io import BytesIO

            import requests
            from PIL import Image

            # Download thumbnail
            response = requests.get(thumbnail_url, timeout=10)
            if response.status_code != 200:
                return video_metadata

            thumbnail_image = Image.open(BytesIO(response.content))

            # OCR on thumbnail
            if enable_ocr:
                try:
                    import os
                    import sys

                    import pytesseract

                    # Configure Tesseract path (Windows) - BEFORE using OCR
                    if sys.platform == "win32":
                        possible_paths = [
                            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        ]
                        for path in possible_paths:
                            if os.path.exists(path):
                                pytesseract.pytesseract.tesseract_cmd = path
                                break

                    ocr_text = pytesseract.image_to_string(thumbnail_image)
                    if ocr_text.strip():
                        video_metadata["thumbnail_ocr_text"] = ocr_text.strip()
                        self.logger.debug(f"OCR extracted {len(ocr_text)} chars from video thumbnail")
                except Exception as e:
                    self.logger.debug(f"Thumbnail OCR failed: {e}")

            # Vision AI on thumbnail
            if enable_vision:
                try:
                    import os

                    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

                    # Check for vision model
                    models_response = requests.get(f"{ollama_url}/api/tags", timeout=2)
                    models = models_response.json().get("models", [])
                    vision_models = [m for m in models if "llava" in m.get("name", "").lower()]

                    if vision_models:
                        # Convert image to base64
                        buffer = BytesIO()
                        thumbnail_image.save(buffer, format="JPEG")
                        image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

                        # Analyze with LLaVA
                        prompt = """Briefly describe this video thumbnail in 1-2 sentences.
What is shown? Is it a tutorial, demonstration, or presentation?
Any visible text or product names?"""

                        vision_response = requests.post(
                            f"{ollama_url}/api/generate",
                            json={
                                "model": vision_models[0]["name"],
                                "prompt": prompt,
                                "images": [image_data],
                                "stream": False,
                            },
                            timeout=20,
                        )

                        if vision_response.status_code == 200:
                            description = vision_response.json().get("response", "").strip()
                            if description:
                                video_metadata["thumbnail_ai_description"] = description
                                self.logger.debug(f"Vision AI analyzed thumbnail: {description[:50]}...")
                except Exception as e:
                    self.logger.debug(f"Thumbnail Vision AI failed: {e}")

            return video_metadata

        except Exception as e:
            self.logger.debug(f"Thumbnail analysis failed: {e}")
            return video_metadata

    def _parse_youtube_duration(self, duration_str: str) -> int | None:
        """
        Parse YouTube duration string to seconds

        Examples:
            PT15M33S -> 933 seconds
            PT1H2M10S -> 3730 seconds
            PT45S -> 45 seconds
        """
        if not duration_str:
            return None

        pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
        match = pattern.match(duration_str)

        if not match:
            return None

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    def _classify_link(self, url: str) -> str:
        """
        Classify link type based on URL

        Valid types (per database constraint):
        - 'video', 'external', 'tutorial', 'support', 'download', 'email', 'phone'
        """
        url_lower = url.lower()

        # Email links
        if url_lower.startswith("mailto:"):
            return "email"

        # Phone links
        if url_lower.startswith("tel:"):
            return "phone"

        # Support links
        if "support" in url_lower or "help" in url_lower or "kb" in url_lower:
            return "support"

        # Download links
        if (
            "download" in url_lower
            or "driver" in url_lower
            or "software" in url_lower
            or any(ext in url_lower for ext in [".pdf", ".zip", ".exe", ".dmg", ".pkg"])
        ):
            return "download"

        # Video/Tutorial links
        if "video" in url_lower or "youtube" in url_lower or "vimeo" in url_lower:
            return "video"
        if "tutorial" in url_lower or "how-to" in url_lower or "guide" in url_lower:
            return "tutorial"

        # Default: external
        return "external"

    def _categorize_link(self, url: str) -> str:
        """Categorize link by domain/platform"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if "youtube.com" in domain or "youtu.be" in domain:
            return "youtube"
        if "vimeo.com" in domain:
            return "vimeo"
        if "support" in domain or "kb" in domain:
            return "support_portal"
        if "download" in domain or "driver" in domain:
            return "download_portal"
        return "external"

    def _is_direct_video_url(self, url: str) -> bool:
        """
        Check if URL is a direct video file

        Supported formats:
        - MP4 (most common)
        - WebM (web standard)
        - MOV (Apple/QuickTime)
        - AVI (legacy)
        - MKV (Matroska)
        - M4V (Apple)
        - FLV (Flash - legacy)
        - WMV (Windows Media)
        - MPEG/MPG (legacy)
        - 3GP (mobile)
        """
        video_extensions = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".flv", ".wmv", ".mpeg", ".mpg", ".3gp")
        return url.lower().endswith(video_extensions)

    def _create_direct_video_metadata(
        self,
        url: str,
        link_id: str,
        page_number: int | None = None,
    ) -> dict[str, Any]:
        """
        Create video metadata dict for direct video file
        This will be enriched later by enrich_video_metadata.py

        Args:
            url: Direct video URL
            link_id: Link ID

        Returns:
            Video metadata dict
        """
        from urllib.parse import urlparse

        # Extract filename
        parsed = urlparse(url)
        filename = parsed.path.split("/")[-1]
        title = filename.replace("-", " ").replace("_", " ").rsplit(".", 1)[0]

        return {
            "id": str(uuid4()),
            "link_id": link_id,
            "youtube_id": None,
            "platform": "direct",
            "video_url": url,
            "page_number": page_number,
            "title": title,
            "description": f"Direct video file: {filename}",
            "thumbnail_url": None,  # Will be generated by enrichment
            "duration": None,  # Will be extracted by enrichment
            "metadata": {"filename": filename, "needs_enrichment": True},  # Flag for enrichment script
        }

    def _is_video_platform(self, url: str) -> bool:
        """Check if URL is from a known video platform"""
        url_lower = url.lower()

        video_platforms = [
            "vimeo.com",
            "brightcove",
            "wistia.com",
            "wistia.net",
            "vidyard.com",
            "jwplayer.com",
            "jwplatform.com",
            "kaltura.com",
            "ustream.tv",
            "video.ibm.com",
            "panopto.com",
            "loom.com",
            "streamyard.com",
            "twitch.tv",
            "facebook.com/watch",
            "fb.watch",
            "instagram.com/p/",
            "instagram.com/reel/",
            "tiktok.com",
            "linkedin.com/posts/",
            "dailymotion.com",
            "youku.com",
            "bilibili.com",
            "rutube.ru",
            "komododecks.com",
            "sproutvideo.com",
            "vzaar.com",
            "cincopa.com",
            "twentythree.com",
            "movingimage.com",
        ]

        return any(platform in url_lower for platform in video_platforms)

    def _detect_video_platform(self, url: str) -> str:
        """Detect which video platform the URL is from"""
        url_lower = url.lower()

        # Map domains to platform names
        platform_map = {
            "vimeo.com": "vimeo",
            "brightcove": "brightcove",
            "wistia.com": "wistia",
            "wistia.net": "wistia",
            "vidyard.com": "vidyard",
            "jwplayer.com": "jwplayer",
            "jwplatform.com": "jwplayer",
            "kaltura.com": "kaltura",
            "ustream.tv": "ibm_video",
            "video.ibm.com": "ibm_video",
            "panopto.com": "panopto",
            "loom.com": "loom",
            "streamyard.com": "streamyard",
            "twitch.tv": "twitch",
            "facebook.com": "facebook",
            "fb.watch": "facebook",
            "instagram.com": "instagram",
            "tiktok.com": "tiktok",
            "linkedin.com": "linkedin",
            "dailymotion.com": "dailymotion",
            "youku.com": "youku",
            "bilibili.com": "bilibili",
            "rutube.ru": "rutube",
            "komododecks.com": "komododecks",
            "sproutvideo.com": "sproutvideo",
            "vzaar.com": "vzaar",
            "cincopa.com": "cincopa",
            "twentythree.com": "twentythree",
            "movingimage.com": "movingimage",
        }

        for domain, platform in platform_map.items():
            if domain in url_lower:
                return platform

        return "unknown"

    def _create_generic_video_metadata(
        self,
        url: str,
        link_id: str,
        platform: str,
        page_number: int | None = None,
    ) -> dict[str, Any]:
        """
        Create video metadata dict for non-YouTube platforms (Vimeo, Brightcove, etc.)

        Args:
            url: Video URL
            link_id: Link ID
            platform: Platform name (vimeo, brightcove, etc.)

        Returns:
            Video metadata dict
        """
        from urllib.parse import urlparse

        # Try to extract video ID from URL
        parsed = urlparse(url)
        video_id = None

        if platform == "vimeo":
            # Vimeo: https://vimeo.com/123456789
            path_parts = parsed.path.strip("/").split("/")
            if path_parts:
                video_id = path_parts[0]
        elif platform == "brightcove":
            # Brightcove: various formats, try to extract ID from query params
            query_params = parse_qs(parsed.query)
            video_id = query_params.get("videoId", [None])[0] or query_params.get("bctid", [None])[0]

        # Generate title from URL if no ID found
        title = f"{platform.title()} Video"
        if video_id:
            title = f"{platform.title()} Video {video_id}"

        return {
            "id": str(uuid4()),
            "link_id": link_id,
            "youtube_id": None,
            "platform": platform,
            "video_url": url,
            "page_number": page_number,
            "title": title,
            "description": f"{platform.title()} video - enrichment needed",
            "thumbnail_url": None,
            "duration": None,
            "metadata": {"video_id": video_id, "needs_enrichment": True, "platform": platform},
        }

    def _deduplicate_links(self, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate links, keep best version"""
        seen_urls = {}

        for link in links:
            url = link["url"]

            # Normalize URL for comparison
            url_normalized = url.lower().rstrip("/")

            if url_normalized not in seen_urls:
                seen_urls[url_normalized] = link
            else:
                # Keep link with higher confidence or more info
                existing = seen_urls[url_normalized]
                replacement = existing
                if (
                    link.get("confidence_score", 0) > existing.get("confidence_score", 0)
                    or (link.get("description") and not existing.get("description"))
                    or (link.get("page_number") and not existing.get("page_number"))
                ):
                    replacement = link

                other = existing if replacement is link else link
                # Preserve useful fields from both candidates (especially page_number).
                for key in ("page_number", "description", "context", "context_text"):
                    if not replacement.get(key) and other.get(key):
                        replacement[key] = other.get(key)

                seen_urls[url_normalized] = replacement

        return list(seen_urls.values())

    def _is_placeholder_url(self, url: str) -> bool:
        """
        Check if URL is a placeholder (x.x.x.x, 0.0.0.0, etc.)

        Returns:
            True if URL is a placeholder and should be skipped
        """
        import re

        # Check for x.x.x.x pattern
        if re.search(r"[xX]\.[xX]\.[xX]\.[xX]", url):
            return True

        # Check for 0.0.0.0 or 127.0.0.1 (localhost)
        if "0.0.0.0" in url or "127.0.0.1" in url:
            return True

        # Check for well-known placeholder hostnames based on parsed netloc.
        # This intentionally treats subdomains like support.example.com as REAL
        # links while filtering only bare example.com/example.org/test.com/localhost.
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        placeholder_hosts = {"example.com", "example.org", "test.com", "localhost"}
        return host in placeholder_hosts

    def _extract_link_description(self, context: str, url: str) -> str:
        """
        Extract meaningful description from context around URL

        Args:
            context: Text context around URL
            url: The URL itself

        Returns:
            Clean description string
        """
        # Remove the URL itself from context
        description = context.replace(url, "").strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "Click here:",
            "Visit:",
            "See:",
            "Go to:",
            "Link:",
            "URL:",
            "Website:",
            "Download:",
            "More info:",
            "For more information:",
            "Access the following URL:",
        ]

        for prefix in prefixes_to_remove:
            if description.lower().startswith(prefix.lower()):
                description = description[len(prefix) :].strip()

        # If description is too short or just punctuation, try to extract sentence
        if len(description) < 10 or not any(c.isalnum() for c in description):
            # Try to find sentence containing the URL
            sentences = context.split(".")
            for sentence in sentences:
                if url in sentence:
                    description = sentence.replace(url, "").strip()
                    break

        # Limit length
        if len(description) > 300:
            description = description[:297] + "..."

        # Final cleanup
        description = description.strip(".,;:- \t\n")

        return description if description else context[:100]
