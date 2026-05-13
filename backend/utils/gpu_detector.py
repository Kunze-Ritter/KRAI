"""
GPU Detector - Automatische VRAM-Erkennung
Wählt optimales Ollama Vision Model basierend auf GPU
"""

import logging
import subprocess
import sys
from typing import Any, cast

# Fix encoding for Windows PowerShell
if sys.platform == "win32":
    import codecs

    sys.stdout: Any = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")  # type: ignore
    sys.stderr: Any = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")  # type: ignore

logger = logging.getLogger("krai.gpu_detector")


def get_gpu_info() -> dict[str, Any]:
    """
    Erkennt GPU und verfügbares VRAM

    Returns:
        {
            'gpu_available': bool,
            'gpu_name': str,
            'vram_gb': float,
            'recommended_vision_model': str
        }
    """
    result = {
        "gpu_available": False,
        "gpu_name": "CPU Only",
        "vram_gb": 0,
        "recommended_vision_model": "llava:7b",  # Safe default
    }

    try:
        # Try GPUtil first (NVIDIA)
        try:
            import GPUtil

            gpus = GPUtil.getGPUs()

            if gpus:
                gpu = gpus[0]  # Use first GPU
                result["gpu_available"] = True
                result["gpu_name"] = gpu.name
                result["vram_gb"] = gpu.memoryTotal / 1024  # MB to GB

                logger.info(f"GPU detected: {gpu.name} with {result['vram_gb']:.1f} GB VRAM")
        except ImportError:
            logger.debug("GPUtil not available, trying nvidia-smi...")

            # Fallback: nvidia-smi
            try:
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )

                lines = output.strip().split("\n")
                if lines:
                    parts = lines[0].split(",")
                    result["gpu_available"] = True
                    result["gpu_name"] = parts[0].strip()
                    result["vram_gb"] = float(parts[1].strip()) / 1024  # MB to GB

                    logger.info(
                        f"GPU detected via nvidia-smi: {result['gpu_name']} with {result['vram_gb']:.1f} GB VRAM"
                    )
            except Exception as e:
                logger.debug(f"nvidia-smi failed: {e}")

        # Determine best model based on VRAM
        vram = cast(float, result["vram_gb"])

        if vram >= 20:
            # High-end: 3090/4090, A6000, etc.
            result["recommended_vision_model"] = "llava:34b"
            result["reason"] = f"{vram:.1f}GB VRAM - Using best quality model (34B)"
        elif vram >= 12:
            # Mid-high: 3080Ti, 4070Ti, etc.
            result["recommended_vision_model"] = "llava:latest"
            result["reason"] = f"{vram:.1f}GB VRAM - Using high quality model (13B)"
        elif vram >= 8:
            # Mid: 3060Ti, 4060Ti, etc.
            result["recommended_vision_model"] = "llava:latest"
            result["reason"] = f"{vram:.1f}GB VRAM - Using standard model (13B)"
        elif vram >= 4:
            # Low-mid: 1660, 2060, etc.
            result["recommended_vision_model"] = "llava:7b"
            result["reason"] = f"{vram:.1f}GB VRAM - Using optimized model (7B)"
        else:
            # Very low or CPU only
            result["recommended_vision_model"] = "llava:7b"
            result["reason"] = f"{vram:.1f}GB VRAM - Using minimal model (7B)"

        logger.info(f"Recommendation: {result['recommended_vision_model']} - {result.get('reason', 'Default')}")

    except Exception as e:
        logger.error(f"GPU detection failed: {e}")
        result["reason"] = "Detection failed, using safe default"

    return result


def print_gpu_info():
    """Print GPU info in user-friendly format"""
    info = get_gpu_info()

    print("\n" + "=" * 60)
    print("🎮 GPU DETECTION")
    print("=" * 60)

    if info["gpu_available"]:
        print(f"GPU: {info['gpu_name']}")
        print(f"VRAM: {info['vram_gb']:.1f} GB")
        print(f"\n✅ Recommended Vision Model: {info['recommended_vision_model']}")
        print(f"📝 Reason: {info.get('reason', 'Auto-detected')}")
    else:
        print("GPU: Not detected (CPU mode)")
        print(f"Recommended: {info['recommended_vision_model']} (safe default)")

    print("=" * 60 + "\n")

    return info


def get_recommended_vision_model() -> str:
    """
    Get recommended vision model for current system

    Returns:
        Model name (e.g., 'llava:7b', 'llava:latest', 'llava:34b')
    """
    info = get_gpu_info()
    return cast(str, info["recommended_vision_model"])


if __name__ == "__main__":
    # Test GPU detection
    print_gpu_info()
