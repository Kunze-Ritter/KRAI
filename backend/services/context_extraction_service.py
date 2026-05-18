"""
Context Extraction Service - Extract context for images, videos, links, tables

Description: Extracts surrounding text, figure references, page headers, error codes,
and products from page text for all media types in the KRAI document processing pipeline.

Features:
- Reusable across all processors (ImageProcessor, LinkProcessor, TableProcessor)
- Regex-based extraction for error codes and products
- Configurable context window size
- Bbox-based text extraction for images
- Figure reference detection (Figure 3.2, Abb. 1, etc.)
- Page header extraction
- Surrounding paragraph extraction

Author: KRAI Development Team
Version: 1.0.0
"""

import logging
import re
from typing import Any


class ContextExtractionService:
    """
    Centralized context extraction service for media elements.

    Extracts context information from page text including:
    - Surrounding text (configurable window)
    - Figure references
    - Page headers
    - Error codes (XX.XX.XX format)
    - Product codes (C4080, AccurioPress C4080, etc.)
    - Surrounding paragraphs
    """

    def __init__(
        self,
        context_window_size: int = 200,
        enable_error_code_extraction: bool = True,
        enable_product_extraction: bool = True,
    ):
        """
        Initialize the context extraction service.

        Args:
            context_window_size: Number of characters to extract before/after media elements
            enable_error_code_extraction: Whether to extract error codes
            enable_product_extraction: Whether to extract product codes
        """
        self.context_window_size = context_window_size
        self.enable_error_code_extraction = enable_error_code_extraction
        self.enable_product_extraction = enable_product_extraction

        self.logger = logging.getLogger(__name__)

        # Compile regex patterns for better performance
        self._compile_regex_patterns()

    def _compile_regex_patterns(self):
        """Compile frequently used regex patterns for performance."""
        # Figure reference patterns (from table_processor.py lines 398-408)
        self.figure_patterns = [
            re.compile(r"Figure\s+\d+\.?\d*", re.IGNORECASE),
            re.compile(r"Fig\.\s+\d+\.?\d*", re.IGNORECASE),
            re.compile(r"Abb\.\s+\d+\.?\d*", re.IGNORECASE),
            re.compile(r"Abbildung\s+\d+\.?\d*", re.IGNORECASE),
        ]

        # Error code patterns — ordered from most specific to least specific
        # HP: XX.XX.XX with alphanumeric segments (e.g. 10.03.12, 53.A0.10, 50.FF.02)
        # Konica Minolta/Ricoh: C-NNNN or SC-NNN
        # Generic: XX.XX.XX all-numeric
        self.error_code_patterns = [
            re.compile(r"\b[0-9A-Fa-f]{2}\.[0-9A-Fa-fXx]{2}\.[0-9A-Fa-fXx]{2}\b"),  # HP alphanumeric
            re.compile(r"\b[A-Z]{1,2}-?\d{3,5}\b"),  # Konica Minolta (C-2801), Ricoh (SC542)
        ]
        # Keep single pattern alias for backward-compat callers
        self.error_code_pattern = self.error_code_patterns[0]

        # Product patterns (from chunker.py lines 438-444)
        self.product_patterns = [
            re.compile(r"[A-Z]\d{4}[a-z]*(?:/[A-Z]\d{4}[a-z]*)*"),  # C4080, C4080/C4070
            re.compile(r"AccurioPress\s+[A-Z]\d{4}", re.IGNORECASE),
            re.compile(r"bizhub\s+[A-Z]?\d{3,4}", re.IGNORECASE),
            re.compile(r"Taskalfa\s+[A-Z]\d{4}", re.IGNORECASE),
        ]

    def extract_image_context(
        self, page_text: str, page_number: int, image_bbox: tuple | None = None, page_path: str | None = None
    ) -> dict[str, Any]:
        """
        Extract context for an image from page text.

        Args:
            page_text: Full text content of the page
            page_number: Page number (1-based)
            image_bbox: Optional bounding box (x0, y0, x1, y1) for precise text extraction
            page_path: Optional PDF file path for bbox-aware extraction

        Returns:
            Dict containing context information:
            - context_caption: Surrounding text (±200 chars)
            - figure_reference: Figure reference if found
            - page_header: Page header/title
            - related_error_codes: List of error codes on page
            - related_products: List of products on page
            - surrounding_paragraphs: Paragraphs before/after image
        """
        context_data = {
            "context_caption": None,
            "figure_reference": None,
            "page_header": None,
            "related_error_codes": [],
            "related_products": [],
            "surrounding_paragraphs": [],
        }

        try:
            # Extract surrounding text
            context_data["context_caption"] = self._extract_surrounding_text(
                page_text, image_bbox, self.context_window_size, page_path, page_number
            )

            # Extract figure reference
            context_data["figure_reference"] = self._extract_figure_reference(page_text)

            # Extract page header
            context_data["page_header"] = self._extract_page_header(page_text, page_path, page_number)

            # Extract error codes
            if self.enable_error_code_extraction:
                context_data["related_error_codes"] = self._extract_error_codes(page_text)

            # Extract products
            if self.enable_product_extraction:
                context_data["related_products"] = self._extract_products(page_text)

            # Extract surrounding paragraphs
            context_data["surrounding_paragraphs"] = self._extract_surrounding_paragraphs(page_text)

            self.logger.debug(
                "Extracted context for image on page %d: %d error codes, %d products",
                page_number,
                len(context_data["related_error_codes"]),
                len(context_data["related_products"]),
            )

        except Exception as e:
            self.logger.error("Error extracting context for image on page %d: %s", page_number, str(e))

        return context_data

    def extract_link_context(self, page_text: str, page_number: int, link_url: str) -> dict[str, Any]:
        """
        Extract context for a link from page text.

        Args:
            page_text: Full text content of the page
            page_number: Page number (1-based)
            link_url: URL of the link

        Returns:
            Dict containing context information:
            - context_description: Paragraph containing the link
            - page_header: Page header/title
            - related_error_codes: List of error codes on page
            - related_products: List of products on page
        """
        context_data = {
            "context_description": None,
            "page_header": None,
            "related_error_codes": [],
            "related_products": [],
        }

        try:
            # Extract context description (paragraph containing link)
            context_data["context_description"] = self._extract_link_context_description(page_text, link_url)

            # Extract page header
            context_data["page_header"] = self._extract_page_header(page_text, None, page_number)

            # Extract error codes
            if self.enable_error_code_extraction:
                context_data["related_error_codes"] = self._extract_error_codes(page_text)

            # Extract products
            if self.enable_product_extraction:
                context_data["related_products"] = self._extract_products(page_text)

            self.logger.debug(
                "Extracted context for link on page %d: %d error codes, %d products",
                page_number,
                len(context_data["related_error_codes"]),
                len(context_data["related_products"]),
            )

        except Exception as e:
            self.logger.error("Error extracting context for link on page %d: %s", page_number, str(e))

        return context_data

    def extract_video_context(self, page_text: str, page_number: int, video_url: str) -> dict[str, Any]:
        """
        Extract context for a video from page text.

        Args:
            page_text: Full text content of the page
            page_number: Page number (1-based)
            video_url: URL of the video

        Returns:
            Dict containing context information (same structure as link context):
            - context_description: Paragraph containing the video
            - page_header: Page header/title
            - related_error_codes: List of error codes on page
            - related_products: List of products on page
        """
        # Videos are essentially links, so reuse link context extraction
        return self.extract_link_context(page_text, page_number, video_url)

    def _extract_surrounding_text(
        self,
        page_text: str,
        bbox: tuple | None,
        radius: int = 200,
        page_path: str | None = None,
        page_number: int | None = None,
    ) -> str | None:
        """
        Extract surrounding text around a bounding box or from page.

        Args:
            page_text: Full page text
            bbox: Optional bounding box (x0, y0, x1, y1)
            radius: Number of characters to extract before/after
            page_path: Optional PDF file path for bbox-aware extraction
            page_number: Optional page number for bbox-aware extraction

        Returns:
            Surrounding text or None if no text available
        """
        if not page_text or not page_text.strip():
            return None

        # If no bbox provided, return first/last N characters of page
        if bbox is None:
            if len(page_text) <= radius * 2:
                return page_text.strip()
            # Return text from middle of page
            start = len(page_text) // 2 - radius
            end = len(page_text) // 2 + radius
            return page_text[start:end].strip()

        # Implement bbox-based text extraction using PyMuPDF
        if page_path and page_number is not None:
            try:
                import fitz  # PyMuPDF

                # Open PDF and get the specific page
                pdf_document = fitz.open(page_path)
                page = pdf_document[page_number - 1]  # page_number is 1-based

                # Extract text from regions above and below the bbox
                page_rect = page.rect

                # Region above bbox (top of page to bbox.y0)
                above_rect = fitz.Rect(0, 0, page_rect.width, bbox[1])
                above_text = page.get_text(clip=above_rect).strip()

                # Region below bbox (bbox.y1 to bottom of page)
                below_rect = fitz.Rect(0, bbox[3], page_rect.width, page_rect.height)
                below_text = page.get_text(clip=below_rect).strip()

                # Get last 200 characters from above and first 200 from below
                context_above = above_text[-radius:] if above_text else ""
                context_below = below_text[:radius] if below_text else ""

                context = f"{context_above} ... {context_below}".strip()

                pdf_document.close()

                return context if context else page_text[: radius * 2].strip()

            except Exception as e:
                self.logger.debug(f"Bbox-aware extraction failed: {e}, falling back to page text")

        # Fallback: return portion of page text
        if len(page_text) <= radius * 2:
            return page_text.strip()
        start = len(page_text) // 2 - radius
        end = len(page_text) // 2 + radius
        return page_text[start:end].strip()

    def _extract_figure_reference(self, page_text: str) -> str | None:
        """
        Extract figure reference from page text.

        Args:
            page_text: Page text to search

        Returns:
            First figure reference found or None
        """
        if not page_text:
            return None

        for pattern in self.figure_patterns:
            match = pattern.search(page_text)
            if match:
                return match.group(0)

        return None

    def _extract_page_header(
        self, page_text: str, page_path: str | None = None, page_number: int | None = None
    ) -> str | None:
        """
        Extract page header from page text.

        Args:
            page_text: Full text content of the page
            page_path: Optional PDF file path for bbox-aware extraction
            page_number: Optional page number for bbox-aware extraction

        Returns:
            Page header text or None if no header found
        """
        if not page_text or not page_text.strip():
            return None

        # If page_path and page_number provided, use bbox-aware extraction
        if page_path and page_number is not None:
            try:
                import fitz  # PyMuPDF

                # Open PDF and get the specific page
                pdf_document = fitz.open(page_path)
                page = pdf_document[page_number - 1]  # page_number is 1-based

                # Extract text from top 50 points of the page
                page_rect = page.rect
                header_rect = fitz.Rect(0, 0, page_rect.width, 50)
                header_text = page.get_text(clip=header_rect).strip()

                pdf_document.close()

                if header_text:
                    # Return first non-empty line from header text
                    lines = header_text.split("\n")
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 3:  # Skip very short lines
                            return line

            except Exception as e:
                self.logger.debug(f"Bbox-aware header extraction failed: {e}, falling back to page text")

        # Fallback: return first non-empty line of page text
        lines = page_text.split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) > 3:  # Skip very short lines
                return line

        return None

    def _extract_error_codes(self, text: str) -> list[str]:
        """
        Extract error codes from text.

        Args:
            text: Text to search for error codes

        Returns:
            List of unique error codes found
        """
        if not text:
            return []

        matches: list[str] = []
        for pattern in self.error_code_patterns:
            matches.extend(pattern.findall(text))
        return list(set(matches))

    def _extract_products(self, text: str) -> list[str]:
        """
        Extract product codes from text.

        Args:
            text: Text to search for product codes

        Returns:
            List of unique products found
        """
        if not text:
            return []

        products = []
        for pattern in self.product_patterns:
            matches = pattern.findall(text)
            products.extend(matches)

        return list(set(products))  # Remove duplicates

    def _extract_surrounding_paragraphs(self, page_text: str, target_position: int = None) -> list[str]:
        """
        Extract surrounding paragraphs from page text.

        Args:
            page_text: Full page text
            target_position: Position in text to extract around (optional)

        Returns:
            List of surrounding paragraphs (up to 2 before and 2 after)
        """
        if not page_text:
            return []

        # Split page into paragraphs
        paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

        if len(paragraphs) <= 4:
            return paragraphs

        # If no target position, return middle paragraphs
        if target_position is None:
            target_position = len(paragraphs) // 2

        # Extract paragraphs around target position
        start_idx = max(0, target_position - 2)
        end_idx = min(len(paragraphs), target_position + 2)

        return paragraphs[start_idx:end_idx]

    def _extract_link_context_description(self, page_text: str, link_url: str) -> str | None:
        """
        Extract context description for a link.

        Args:
            page_text: Page text containing the link
            link_url: URL of the link

        Returns:
            Paragraph containing the link or None
        """
        if not page_text or not link_url:
            return None

        # Split into paragraphs and find one containing the URL
        paragraphs = page_text.split("\n\n")
        for paragraph in paragraphs:
            if link_url in paragraph:
                return paragraph.strip()

        # If not found in paragraphs, try line-by-line
        lines = page_text.split("\n")
        for line in lines:
            if link_url in line:
                return line.strip()

        return None
