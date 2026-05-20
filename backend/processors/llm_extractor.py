"""
LLM-based Product & Specification Extraction

Uses local Ollama LLM for intelligent extraction.
"""

import json
from typing import Any

import requests
from pydantic import ValidationError

from .logger import get_logger
from .models import ExtractedProduct


class LLMProductExtractor:
    """Extract products and specifications using local LLM"""

    def __init__(self, model_name: str | None = None, ollama_url: str = "http://localhost:11434", debug: bool = False):
        """
        Initialize LLM extractor

        Args:
            model_name: Ollama model to use (default: from OLLAMA_MODEL_TEXT env)
            ollama_url: Ollama API endpoint
            debug: Enable debug logging
        """
        import os

        # Use env variable if model_name not provided
        # Prefer OLLAMA_MODEL_EXTRACTION (specialized for JSON/structured output)
        # Fallback to OLLAMA_MODEL_TEXT for backwards compatibility
        if model_name is None:
            model_name = os.getenv("OLLAMA_MODEL_EXTRACTION") or os.getenv("OLLAMA_MODEL_TEXT", "qwen2.5:3b")
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.debug = debug
        self.logger = get_logger()

    def extract_from_specification_section(
        self, text: str, manufacturer: str, page_number: int = 1
    ) -> list[ExtractedProduct]:
        """
        Extract products and specs from specification section

        Args:
            text: Text from specification section
            manufacturer: Manufacturer name
            page_number: Source page number

        Returns:
            List of extracted products with specifications
        """
        prompt = self._build_extraction_prompt(text, manufacturer)

        try:
            response = self._call_ollama(prompt)
            products = self._parse_llm_response(response, manufacturer, page_number)

            if self.debug:
                self.logger.debug(f"LLM extracted {len(products)} products with specs")

            return products

        except Exception as e:
            self.logger.error(f"LLM extraction failed: {e}")
            return []

    def _build_extraction_prompt(self, text: str, manufacturer: str) -> str:
        """Build universal extraction prompt for LLM"""

        # Limit text to reasonable size for LLM (32K tokens ≈ 128K chars)
        # Use first 100K chars to capture product info from beginning
        max_chars = 100000
        text_sample = text[:max_chars] if len(text) > max_chars else text

        return f"""Extract ALL products (printers, accessories, options) from this {manufacturer} technical document.

IMPORTANT: ALL products in this document are {manufacturer} products! Do NOT extract products from other manufacturers.

TEXT:
{text_sample}

INSTRUCTIONS:
1. Find ALL product model numbers, series names, and types
2. IMPORTANT: Extract the product series/family name (e.g., "AccurioPress", "LaserJet", "bizhub")
3. Extract specifications (speed, resolution, capacity, dimensions, etc.)
4. Include accessories, options, finishers, feeders, trays
5. Return ONLY valid JSON array (empty array if no products found)
6. ALL products MUST be {manufacturer} products - ignore references to other brands

JSON FORMAT:
[
  {{
    "model_number": "REQUIRED - e.g. C4080, MK-746, SD-513",
    "product_series": "IMPORTANT - Product series/family (e.g. AccurioPress, LaserJet, bizhub, OfficeJet, ECOSYS)",
    "product_type": "printer|accessory|finisher|feeder|tray|cabinet|consumable",
    "specifications": {{
      "ANY_SPEC_NAME": "ANY_VALUE",
      "max_print_speed_ppm": 80,
      "max_resolution_dpi": 1200,
      "paper_capacity": {{"standard": 3000, "max": 6000}},
      "dimensions": {{"width": 750, "depth": 850, "height": 1200}},
      "compatible_models": ["C4080", "C4070"],
      "... add any other specs you find ..."
    }}
  }}
]

RULES:
- ALL products are {manufacturer} products
- Extract numerical values WITHOUT units (80 ppm -> 80)
- Use nested objects for complex specs
- Use null if value unknown
- Return [] if NO products found
- Be flexible with spec names

JSON:"""

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API (supports both old and new API)"""

        # Try new API first (/api/chat)
        url_chat = f"{self.ollama_url}/api/chat"
        payload_chat = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 2000},
        }

        try:
            response = requests.post(url_chat, json=payload_chat, timeout=300)
            response.raise_for_status()
            result = response.json()
            llm_response = result.get("message", {}).get("content", "")

            if self.debug:
                self.logger.debug("✅ Used new Ollama API (/api/chat)")
                self.logger.debug(f"Response length: {len(llm_response)}")

            return llm_response

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 405:
                # Fall back to old API (/api/generate)
                self.logger.warning("New API not supported, falling back to old API (/api/generate)")

                url_generate = f"{self.ollama_url}/api/generate"
                payload_generate = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 2000},
                }

                response = requests.post(url_generate, json=payload_generate, timeout=300)
                response.raise_for_status()
                result = response.json()
                llm_response = result.get("response", "")

                if self.debug:
                    self.logger.debug("✅ Used old Ollama API (/api/generate)")
                    self.logger.debug(f"Response length: {len(llm_response)}")

                return llm_response
            raise

    def _parse_llm_response(self, response: str, manufacturer: str, page_number: int) -> list[ExtractedProduct]:
        """Parse LLM JSON response into ExtractedProduct objects"""

        products = []

        try:
            # Extract JSON from response (LLM might add markdown)
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            json_str = json_str.strip()

            # Try to parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Try to fix common JSON issues
                self.logger.warning(f"⚠️  Initial JSON parse failed: {e}")
                self.logger.info("   Attempting to recover partial JSON...")

                # Try to fix unterminated strings by finding the last complete object
                try:
                    if json_str.startswith("["):
                        # Array of products - try to extract complete objects
                        data = self._extract_partial_json_array(json_str)
                        self.logger.info(
                            f"   ✅ Recovered {len(data) if isinstance(data, list) else 1} items from partial JSON"
                        )
                    elif json_str.startswith("{"):
                        # Single object - try to close it
                        data = self._extract_partial_json_object(json_str)
                        self.logger.info("   ✅ Recovered partial JSON object")
                    else:
                        raise  # Re-raise if we can't handle it
                except Exception as recovery_error:
                    self.logger.error(f"   ❌ JSON recovery failed: {recovery_error}")
                    self.logger.debug(f"   Problematic JSON (first 500 chars): {json_str[:500]}")
                    raise  # Re-raise original error

            # Handle different response formats
            if isinstance(data, dict):
                # Check if LLM wrapped it in a "products" key
                if "products" in data:  # noqa: SIM401
                    data = data["products"]
                else:
                    # Single product object
                    data = [data]

            # Ensure it's a list
            if not isinstance(data, list):
                data = [data]

            for item in data:
                try:
                    # Determine product type
                    product_type_raw = item.get("product_type", "laser_printer")

                    # Handle case where LLM returns array instead of string
                    if isinstance(product_type_raw, list):
                        product_type_raw = product_type_raw[0] if product_type_raw else "laser_printer"

                    product_type_raw = str(product_type_raw).lower()

                    # Map LLM types to DB-valid types
                    # First, map generic types to specific types
                    type_mapping = {
                        # Generic to specific
                        "printer": "laser_printer",
                        "multifunction": "laser_multifunction",
                        "mfp": "laser_multifunction",
                        "all-in-one": "laser_multifunction",
                        "scanner": "scanner",
                        "copier": "copier",
                        "plotter": "inkjet_plotter",
                        # Accessories
                        "finisher": "finisher",
                        "booklet finisher": "booklet_finisher",
                        "saddle finisher": "finisher",
                        "stapler finisher": "stapler_finisher",
                        "folder": "folder",
                        "stapler": "stapler_finisher",
                        "feeder": "feeder",
                        "paper feeder": "paper_feeder",
                        "paper deck": "feeder",
                        "envelope feeder": "envelope_feeder",
                        "tray": "output_tray",
                        "paper tray": "output_tray",
                        "bypass tray": "output_tray",
                        "multi-bypass": "output_tray",
                        "cabinet": "cabinet",
                        "paper cabinet": "cabinet",
                        "option": "accessory",
                        "accessory": "accessory",
                        "consumable": "consumable",
                    }
                    product_type = type_mapping.get(product_type_raw, "laser_printer")

                    # Build specifications JSONB (exclude core fields)
                    specifications = {
                        k: v
                        for k, v in item.items()
                        if k not in ["model_number", "product_series", "product_type"] and v is not None
                    }

                    product = ExtractedProduct(
                        model_number=item.get("model_number", ""),
                        product_series=item.get("product_series"),
                        product_type=product_type,
                        manufacturer_name=manufacturer,
                        confidence=0.85,  # LLM extraction confidence
                        specifications=specifications,
                    )

                    # Debug logging for product series
                    if product.product_series:
                        self.logger.debug(f"   Series: {product.product_series}")
                    else:
                        self.logger.debug("   Series: None (not extracted)")

                    products.append(product)

                except ValidationError as e:
                    if self.debug:
                        self.logger.debug(f"Product validation failed: {e}")
                    continue

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON: {e}")
            if self.debug:
                self.logger.debug(f"Response was: {response[:500]}")

        if self.debug and len(products) == 0:
            self.logger.warning(f"LLM returned 0 products. Response: {response[:500]}")

        return products

    def _extract_partial_json_array(self, json_str: str) -> list:
        """Extract complete JSON objects from a partial array"""
        objects = []
        depth = 0
        current_obj = ""
        in_string = False
        escape_next = False

        for i, char in enumerate(json_str):
            if escape_next:
                current_obj += char
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                current_obj += char
                continue

            if char == '"' and not escape_next:
                in_string = not in_string

            if not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    current_obj += char

                    # Complete object found
                    if depth == 0 and current_obj.strip():
                        try:
                            obj = json.loads(current_obj)
                            objects.append(obj)
                            self.logger.info("   ✅ Recovered 1 complete object from partial JSON")
                        except (json.JSONDecodeError, ValueError):
                            pass
                        current_obj = ""
                        continue

            if depth > 0 or (depth == 0 and char == "{"):
                current_obj += char

        if objects:
            self.logger.success(f"✅ Successfully recovered {len(objects)} objects from partial JSON")
        return objects

    def _extract_partial_json_object(self, json_str: str) -> dict:
        """Try to extract a valid object from partial JSON"""
        # Find the last complete key-value pair
        try:
            # Try progressively shorter strings
            for end in range(len(json_str), 0, -1):
                test_str = json_str[:end].rstrip()

                # Try to close the object
                if not test_str.endswith("}"):
                    test_str += "}"

                try:
                    obj = json.loads(test_str)
                    self.logger.info(f"   ✅ Recovered partial object (truncated at char {end})")
                    return obj
                except (json.JSONDecodeError, ValueError):
                    continue
        except Exception:
            pass

        # If all else fails, return empty dict
        self.logger.error("   ❌ Could not recover any valid JSON")
        return {}

    def detect_specification_section(self, page_texts: dict[int, str]) -> dict[str, Any] | None:
        """
        Detect if document has a specification section

        Returns:
            Dict with page_number and text if found, else None
        """
        keywords = [
            "product specification",
            "specifications",
            "technical specifications",
            "product features",
            "system specifications",
        ]

        for page_num, text in page_texts.items():
            text_lower = text.lower()
            for keyword in keywords:
                if keyword in text_lower:
                    # Extract section (next ~1000 chars)
                    start_idx = text_lower.index(keyword)
                    section_text = text[start_idx : start_idx + 3000]

                    self.logger.info(f"Found specification section on page {page_num}")
                    return {"page_number": page_num, "text": section_text, "keyword": keyword}

        return None
