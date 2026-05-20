"""
Vision-based Product & Specification Extraction

Uses Ollama LLaVA for image-based extraction of tables and structured data.
"""

import base64
import json
from pathlib import Path

import fitz  # PyMuPDF
import requests

from .logger import get_logger
from .models import ExtractedProduct


class VisionProductExtractor:
    """Extract products using Vision AI (Ollama LLaVA)"""

    def __init__(
        self,
        vision_model: str | None = None,
        text_model: str | None = None,
        ollama_url: str = "http://localhost:11434",
        debug: bool = False,
    ):
        """
        Initialize Vision extractor

        Args:
            vision_model: Ollama vision model (default: from OLLAMA_MODEL_VISION env)
            text_model: Ollama text model for refinement (default: from OLLAMA_MODEL_EXTRACTION env)
            ollama_url: Ollama API endpoint
            debug: Enable debug logging
        """
        import os

        # Use env variables if not provided
        self.vision_model = vision_model or os.getenv("OLLAMA_MODEL_VISION", "llava:7b")
        self.text_model = (
            text_model or os.getenv("OLLAMA_MODEL_EXTRACTION") or os.getenv("OLLAMA_MODEL_TEXT", "qwen2.5:3b")
        )
        self.ollama_url = ollama_url
        self.debug = debug
        self.logger = get_logger()

    def extract_from_pdf_page(
        self, pdf_path: Path, page_number: int, manufacturer: str, target_section: str = "specification"
    ) -> list[ExtractedProduct]:
        """
        Extract products from a specific PDF page using Vision

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (0-indexed)
            manufacturer: Manufacturer name
            target_section: Type of section (specification, accessories, etc.)

        Returns:
            List of extracted products with specifications
        """
        try:
            # Convert PDF page to image
            image_base64 = self._pdf_page_to_image(pdf_path, page_number)

            # Analyze with vision model
            vision_analysis = self._analyze_with_vision(image_base64, manufacturer, target_section)

            # Refine with text model
            return self._refine_with_text_model(vision_analysis, manufacturer, page_number)

        except Exception as e:
            self.logger.error(f"Vision extraction failed for page {page_number}: {e}")
            return []

    def _pdf_page_to_image(self, pdf_path: Path, page_number: int, dpi: int = 150) -> str:
        """
        Convert PDF page to base64 encoded image

        Args:
            pdf_path: Path to PDF
            page_number: Page number (0-indexed)
            dpi: Image resolution (higher = better quality, slower)

        Returns:
            Base64 encoded PNG image
        """
        doc = fitz.open(pdf_path)
        page = doc[page_number]

        # Render page as image
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 DPI is default
        pix = page.get_pixmap(matrix=mat)

        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")

        # Encode to base64
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        doc.close()

        return img_base64

    def _analyze_with_vision(self, image_base64: str, manufacturer: str, target_section: str) -> str:
        """
        Analyze image with Vision model (LLaVA)

        Returns:
            Raw text analysis from vision model
        """
        if target_section == "specification":
            prompt = f"""Analyze this {manufacturer} product specification page.

Extract ALL products and their specifications from tables and text.

For EACH product, extract:
- Model number (e.g., C4080, MK-746)
- Product type (printer, finisher, feeder, tray, etc.)
- Specifications (speed, resolution, capacity, dimensions, etc.)

Pay special attention to:
- Specification tables
- Option/Accessory lists
- Technical data sheets
- Model number columns

Output as structured text with clear sections for each product."""

        elif target_section == "accessories":
            prompt = f"""Analyze this {manufacturer} accessories/options page.

Extract ALL accessories, options, and compatible products.

For EACH item, extract:
- Model number (e.g., MK-746, SD-513)
- Type (finisher, feeder, tray, cabinet, etc.)
- Compatible with which products
- Specifications (capacity, dimensions, etc.)

Look for:
- Option code tables
- Compatibility matrices
- Accessory lists
- Configuration diagrams

Output as structured text."""

        else:
            prompt = f"Analyze this {manufacturer} document page and extract all product information."

        # Call Ollama Vision API
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1000},
        }

        if self.debug:
            self.logger.debug(f"Calling Vision model: {self.vision_model}")

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def _refine_with_text_model(
        self, vision_analysis: str, manufacturer: str, page_number: int
    ) -> list[ExtractedProduct]:
        """
        Refine vision analysis with text model (qwen2.5)
        Convert to structured JSON
        """
        prompt = f"""Convert this product analysis to structured JSON.

VISION ANALYSIS:
{vision_analysis[:3000]}

TASK: Extract products in JSON array format.

OUTPUT FORMAT (JSON ONLY):
```json
[
  {{
    "model_number": "C4080",
    "product_type": "printer",
    "specifications": {{
      "max_print_speed_ppm": 80,
      "max_resolution_dpi": 1200,
      "max_paper_size": "SRA3",
      "duplex_capable": true,
      "paper_capacity": {{"standard": 3000, "max": 6000}},
      "dimensions": {{"width": 750, "depth": 850, "height": 1200}},
      "monthly_duty_cycle": 300000
    }}
  }},
  {{
    "model_number": "MK-746",
    "product_type": "finisher",
    "specifications": {{
      "type": "booklet_finisher",
      "staple_capacity": 100,
      "compatible_models": ["C4080", "C4070"]
    }}
  }}
]
```

IMPORTANT:
- Return ONLY valid JSON array
- Extract ALL products mentioned
- Include specifications as nested objects
- Use null if value unknown

JSON:"""

        # Call qwen2.5 for structured extraction
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.text_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 2000},
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        json_response = result.get("response", "")

        # Parse to ExtractedProduct objects
        return self._parse_to_products(json_response, manufacturer, page_number)

    def _parse_to_products(self, json_str: str, manufacturer: str, page_number: int) -> list[ExtractedProduct]:
        """Parse JSON string to ExtractedProduct objects"""

        products = []

        try:
            # Clean JSON
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str)

            if isinstance(data, dict):
                data = [data]

            for item in data:
                try:
                    # Get specifications
                    specifications = item.get("specifications", {})

                    # Determine product type
                    product_type_raw = item.get("product_type", "laser_printer").lower()

                    # Map to DB-valid types
                    type_mapping = {
                        "printer": "laser_printer",
                        "multifunction": "laser_multifunction",
                        "mfp": "laser_multifunction",
                        "scanner": "scanner",
                        "copier": "copier",
                        "plotter": "inkjet_plotter",
                        "finisher": "finisher",
                        "feeder": "feeder",
                        "tray": "output_tray",
                        "cabinet": "cabinet",
                        "accessory": "accessory",
                    }
                    product_type = type_mapping.get(product_type_raw, "laser_printer")

                    product = ExtractedProduct(
                        model_number=item.get("model_number", ""),
                        product_series=item.get("product_series"),
                        product_type=product_type,
                        manufacturer_name=manufacturer,
                        confidence=0.80,  # Vision extraction confidence
                        source_page=page_number,
                        extraction_method="vision",
                        specifications=specifications,
                    )
                    products.append(product)

                except Exception as e:
                    if self.debug:
                        self.logger.debug(f"Failed to parse product: {e}")
                    continue

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            if self.debug:
                self.logger.debug(f"Response: {json_str[:500]}")

        return products

    def find_specification_pages(self, pdf_path: Path, max_pages: int = 50) -> list[int]:
        """
        Find pages that likely contain specification tables

        Args:
            pdf_path: Path to PDF
            max_pages: Max pages to scan

        Returns:
            List of page numbers (0-indexed)
        """
        spec_keywords = [
            "specification",
            "technical data",
            "product features",
            "options",
            "accessories",
            "configurations",
            "model",
            "capacity",
            "speed",
            "resolution",
        ]

        candidate_pages = []

        doc = fitz.open(pdf_path)

        for page_num in range(min(max_pages, len(doc))):
            page = doc[page_num]
            text = page.get_text().lower()

            # Count keyword matches
            match_count = sum(1 for kw in spec_keywords if kw in text)

            if match_count >= 3:  # At least 3 keywords
                candidate_pages.append(page_num)

                if self.debug:
                    self.logger.debug(f"Page {page_num}: {match_count} spec keywords found")

        doc.close()

        return candidate_pages
