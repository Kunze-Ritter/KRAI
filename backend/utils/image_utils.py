"""
Image Utilities for KR-AI-Engine
Image processing and analysis utilities
"""

import io
import logging
from typing import Any, cast

from PIL import Image


class ImageProcessor:
    """
    Image processor for KR-AI-Engine

    Handles:
    - Image format conversion
    - Image resizing
    - Image analysis
    - OCR preprocessing
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.image_utils")
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for image processor"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - ImageProcessor - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def analyze_image(self, image_data: bytes) -> dict[str, Any]:
        """
        Analyze image properties

        Args:
            image_data: Image data as bytes

        Returns:
            Image analysis results
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            analysis = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image_data),
                "aspect_ratio": image.width / image.height,
                "is_landscape": image.width > image.height,
                "is_portrait": image.height > image.width,
                "is_square": image.width == image.height,
            }

            self.logger.info(f"Analyzed image: {analysis['width']}x{analysis['height']} {analysis['format']}")
            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze image: {e}")
            return {}

    def resize_image(self, image_data: bytes, max_width: int = 1920, max_height: int = 1080) -> bytes:
        """
        Resize image while maintaining aspect ratio

        Args:
            image_data: Image data as bytes
            max_width: Maximum width
            max_height: Maximum height

        Returns:
            Resized image data
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Calculate new size maintaining aspect ratio
            ratio = min(max_width / image.width, max_height / image.height)
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)

            # Resize image
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert back to bytes
            output = io.BytesIO()
            resized_image.save(output, format=image.format or "PNG")
            resized_data = output.getvalue()

            self.logger.info(f"Resized image from {image.width}x{image.height} to {new_width}x{new_height}")
            return resized_data

        except Exception as e:
            self.logger.error(f"Failed to resize image: {e}")
            return image_data

    def convert_format(self, image_data: bytes, target_format: str = "PNG") -> bytes:
        """
        Convert image to target format

        Args:
            image_data: Image data as bytes
            target_format: Target format (PNG, JPEG, etc.)

        Returns:
            Converted image data
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # Convert to target format
            output = io.BytesIO()
            image.save(output, format=target_format)
            converted_data = output.getvalue()

            self.logger.info(f"Converted image to {target_format}")
            return converted_data

        except Exception as e:
            self.logger.error(f"Failed to convert image format: {e}")
            return image_data

    def optimize_for_ocr(self, image_data: bytes) -> bytes:
        """
        Optimize image for OCR processing

        Args:
            image_data: Image data as bytes

        Returns:
            Optimized image data
        """
        try:
            image = cast(Image.Image, Image.open(io.BytesIO(image_data)))

            # Convert to grayscale if needed
            if image.mode != "L":
                image = image.convert("L")

            # Enhance contrast
            from PIL import ImageEnhance

            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)

            # Convert back to bytes
            output = io.BytesIO()
            image.save(output, format="PNG")
            optimized_data = output.getvalue()

            self.logger.info("Optimized image for OCR")
            return optimized_data

        except Exception as e:
            self.logger.error(f"Failed to optimize image for OCR: {e}")
            return image_data
