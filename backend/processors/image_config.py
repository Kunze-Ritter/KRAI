"""Image Processor Configuration Module

Configuration, session management, vision guards, and constants
for image processor. Separated for better maintainability.
"""

import os
import sys
from collections import deque
from typing import Any

import requests
from PIL import Image, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_MIN_IMAGE_SIZE = 10000
DEFAULT_MAX_IMAGES_PER_DOC = 999999


def load_image_config(
    min_image_size: int = DEFAULT_MIN_IMAGE_SIZE,
    max_images_per_doc: int = DEFAULT_MAX_IMAGES_PER_DOC,
    enable_ocr: bool = True,
    enable_vision: bool = True,
) -> dict[str, Any]:
    """Load image processor configuration from environment."""
    cpu_count = os.cpu_count() or 4

    return {
        "min_image_size": min_image_size,
        "max_images_per_doc": max_images_per_doc,
        "enable_ocr": enable_ocr,
        "enable_vision": enable_vision,
        "cleanup_temp_images": os.getenv("IMAGE_PROCESSOR_CLEANUP", "1") != "0",
        "request_timeout": float(os.getenv("VISION_REQUEST_TIMEOUT", "60")),
        "max_retries": int(os.getenv("VISION_REQUEST_MAX_RETRIES", "4")),
        "retry_base_delay": float(os.getenv("VISION_RETRY_BASE_DELAY", "1.5")),
        "retry_jitter": float(os.getenv("VISION_RETRY_JITTER", "0.5")),
        "ocr_max_workers": max(1, cpu_count // 2),
        "preprocess_enabled": os.getenv("OCR_PREPROCESSING_ENABLED", "1") != "0",
        "preprocess_grayscale": os.getenv("OCR_PREPROCESS_GRAYSCALE", "1") != "0",
        "preprocess_binarize": os.getenv("OCR_PREPROCESS_BINARIZE", "1") != "0",
        "preprocess_upscale": int(os.getenv("OCR_PREPROCESS_UPSCALE", "1")),
        "max_image_mb": float(os.getenv("VISION_MAX_IMAGE_MB", "12.0")),
        "max_images_per_document": int(os.getenv("VISION_MAX_IMAGES_PER_DOCUMENT", "80")),
        "circuit_breaker_threshold": int(os.getenv("VISION_FAILURE_THRESHOLD", "5")),
        "circuit_breaker_timeout": float(os.getenv("VISION_BREAKER_TIMEOUT", "120")),
        "global_vision_limit": int(os.getenv("VISION_GLOBAL_LIMIT", "500")),
        "global_vision_window": float(os.getenv("VISION_GLOBAL_WINDOW_SECONDS", "3600")),
        "vision_model_cache_ttl": float(os.getenv("VISION_MODEL_CACHE_TTL_SECONDS", "300")),
    }


def create_image_session(
    max_retries: int = 4,
    retry_base_delay: float = 1.5,
    retry_jitter: float = 0.5,
) -> requests.Session:
    """Create HTTP session with retry configuration."""
    session = requests.Session()
    adapter_retries = max(0, max_retries - 1)
    retry = Retry(
        total=adapter_retries,
        read=adapter_retries,
        connect=adapter_retries,
        backoff_factor=retry_base_delay,
        status_forcelist=[],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def apply_image_preprocessing(
    pil_image: Image.Image,
    enabled: bool = True,
    grayscale: bool = True,
    binarize: bool = True,
    upscale: int = 1,
) -> Image.Image:
    """Apply preprocessing to image for better OCR results."""
    if not enabled:
        return pil_image

    processed = pil_image
    if grayscale:
        processed = ImageOps.grayscale(processed)

    if upscale > 1:
        new_size = (
            max(1, processed.width * upscale),
            max(1, processed.height * upscale),
        )
        processed = processed.resize(new_size, Image.BICUBIC)

    if binarize:
        processed = processed.convert("L")
        processed = processed.point(lambda x: 255 if x > 180 else 0, "1")

    return processed


class VisionGuard:
    """Vision AI guardrails and quota management."""

    def __init__(
        self,
        max_images_per_document: int = 80,
        max_image_mb: float = 12.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 120.0,
        global_limit: int = 500,
        global_window: float = 3600.0,
        cache_ttl: float = 300.0,
    ):
        self.max_images_per_document = max_images_per_document
        self.max_image_mb = max_image_mb
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.global_limit = global_limit
        self.global_window = global_window
        self.cache_ttl = cache_ttl

        self._failure_count = 0
        self._breaker_until: float | None = None
        self._usage: deque[float] = deque()
        self._model_cache: str | None = None
        self._model_checked_at: float = 0.0

    def allows(self, image: dict[str, Any], processed_count: int) -> bool:
        """Check if vision processing is allowed for this image."""
        if processed_count >= self.max_images_per_document:
            return False

        size_mb = image.get("size_bytes", 0) / (1024 * 1024)
        if size_mb > self.max_image_mb:
            return False

        if self._breaker_until is not None:
            import time

            if time.time() < self._breaker_until:
                return False

        return True

    def record_failure(self, reason: str) -> None:
        """Record a vision failure for circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self.circuit_breaker_threshold:
            import time

            self._breaker_until = time.time() + self.circuit_breaker_timeout

    def record_usage(self) -> None:
        """Record vision API usage for quota tracking."""
        import time

        now = time.time()
        self._usage.append(now)
        cutoff = now - self.global_window
        while self._usage and self._usage[0] < cutoff:
            self._usage.popleft()

    def quota_allows(self) -> bool:
        """Check if global quota allows more vision requests."""
        return len(self._usage) < self.global_limit

    def reset_failures(self) -> None:
        """Reset failure count after successful requests."""
        self._failure_count = 0
        self._breaker_until = None

    @property
    def model_cache(self) -> str | None:
        return self._model_cache

    @model_cache.setter
    def model_cache(self, value: str | None) -> None:
        self._model_cache = value


def calculate_latency_percentiles(samples: list[float]) -> tuple[float, float]:
    """Calculate p50 and p95 from latency samples."""
    if not samples:
        return 0.0, 0.0
    sorted_samples = sorted(samples)
    n = len(sorted_samples)
    p50_idx = int(n * 0.5)
    p95_idx = min(int(n * 0.95), n - 1)
    return sorted_samples[p50_idx], sorted_samples[p95_idx]


def check_tesseract_availability() -> tuple[bool, str]:
    """Check if Tesseract OCR is available."""
    try:
        import pytesseract

        if sys.platform == "win32":
            possible_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break

        version = pytesseract.get_tesseract_version()
        return True, str(version)
    except ImportError:
        return False, "pytesseract not installed"
    except Exception as e:
        return False, str(e)
