"""
AI Model Configuration with Hardware Auto-Detection
Intelligente Modell-Auswahl basierend auf verfügbarer Hardware
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum

import psutil

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model Performance Tiers"""

    CONSERVATIVE = "conservative"  # 7B Models
    BALANCED = "balanced"  # 13B Models
    HIGH_PERFORMANCE = "high_performance"  # 70B Models


@dataclass
class HardwareSpecs:
    """Hardware specifications"""

    total_ram_gb: float
    available_ram_gb: float
    cpu_cores: int
    cpu_threads: int
    cpu_frequency_mhz: float
    gpu_available: bool
    gpu_memory_gb: float | None = None
    gpu_name: str | None = None
    gpu_driver_version: str | None = None


@dataclass
class ModelConfig:
    """AI Model configuration"""

    text_classification: str
    embeddings: str
    vision: str
    visual_embeddings: str  # Visual embeddings for images (ColQwen2.5)
    table_embeddings: str  # Table embeddings for structured data
    tier: ModelTier
    estimated_ram_usage_gb: float
    parallel_processing: bool
    gpu_acceleration: bool = True
    estimated_gpu_usage_gb: float = 0.0
    visual_embedding_dimension: int = 768
    table_embedding_dimension: int = 768


class HardwareDetector:
    """Hardware detection and model recommendation"""

    def __init__(self):
        self.specs = self._detect_hardware()

    def _detect_hardware(self) -> HardwareSpecs:
        """Detect system hardware specifications"""
        # RAM Detection
        total_ram_bytes = psutil.virtual_memory().total
        available_ram_bytes = psutil.virtual_memory().available
        total_ram_gb = total_ram_bytes / (1024**3)
        available_ram_gb = available_ram_bytes / (1024**3)

        # CPU Detection
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)
        cpu_frequency = psutil.cpu_freq()
        cpu_frequency_mhz = cpu_frequency.max if cpu_frequency else 0

        # GPU Detection (enhanced)
        gpu_available = self._detect_gpu()
        gpu_memory_gb = self._get_gpu_memory() if gpu_available else None
        gpu_name = self._get_gpu_name() if gpu_available else None
        gpu_driver_version = self._get_gpu_driver_version() if gpu_available else None

        return HardwareSpecs(
            total_ram_gb=total_ram_gb,
            available_ram_gb=available_ram_gb,
            cpu_cores=cpu_cores,
            cpu_threads=cpu_threads,
            cpu_frequency_mhz=cpu_frequency_mhz,
            gpu_available=gpu_available,
            gpu_memory_gb=gpu_memory_gb,
            gpu_name=gpu_name,
            gpu_driver_version=gpu_driver_version,
        )

    def _detect_gpu(self) -> bool:
        """Detect if GPU is available"""
        gpu_found = False

        # Method 1: Check CUDA (NVIDIA)
        try:
            import torch

            if torch.cuda.is_available():
                print(f"   [OK] CUDA GPU detected: {torch.cuda.get_device_name(0)}")
                gpu_found = True
        except ImportError:
            pass

        # Method 2: Check nvidia-smi (NVIDIA)
        if not gpu_found:
            try:
                import subprocess

                result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("   [OK] NVIDIA GPU detected via nvidia-smi")
                    gpu_found = True
            except Exception as e:
                logger.debug(f"nvidia-smi detection failed: {e}")

        # Method 3: Check Intel GPU (Windows)
        if not gpu_found:
            try:
                import subprocess

                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True
                )
                if result.returncode == 0 and "Intel" in result.stdout:
                    print("   [OK] Intel GPU detected via wmic")
                    gpu_found = True
            except Exception as e:
                logger.debug(f"Intel GPU detection via wmic failed: {e}")

        # Method 4: Check AMD GPU (Windows)
        if not gpu_found:
            try:
                import subprocess

                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True
                )
                if result.returncode == 0 and any(keyword in result.stdout for keyword in ["AMD", "Radeon"]):
                    print("   [OK] AMD GPU detected via wmic")
                    gpu_found = True
            except Exception as e:
                logger.debug(f"AMD GPU detection via wmic failed: {e}")

        # Method 5: Generic GPU detection (Windows)
        if not gpu_found:
            try:
                import subprocess

                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    gpu_lines = [
                        line.strip() for line in result.stdout.split("\n") if line.strip() and line.strip() != "Name"
                    ]
                    if gpu_lines:
                        print(f"   [OK] GPU detected via wmic: {gpu_lines[0]}")
                        gpu_found = True
            except Exception as e:
                logger.debug(f"Generic GPU detection via wmic failed: {e}")

        if not gpu_found:
            print("   [NO] No GPU detected")

        return gpu_found

    def _get_gpu_memory(self) -> float | None:
        """Get GPU memory in GB"""
        # Method 1: CUDA
        try:
            import torch

            if torch.cuda.is_available():
                memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                print(f"   [MEM] GPU Memory: {memory_gb:.1f} GB (CUDA)")
                return memory_gb
        except Exception as e:
            logger.debug(f"CUDA GPU memory detection failed: {e}")

        # Method 2: nvidia-smi
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                memory_mb = int(result.stdout.strip())
                memory_gb = memory_mb / 1024
                print(f"   [MEM] GPU Memory: {memory_gb:.1f} GB (nvidia-smi)")
                return memory_gb
        except Exception as e:
            logger.debug(f"nvidia-smi memory detection failed: {e}")

        # Method 3: wmic (Windows) - estimate based on GPU name
        try:
            import subprocess

            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"], capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
                for line in lines:
                    if "Name" not in line and "Intel" in line:
                        print("   [MEM] GPU Memory: ~2.0 GB (Intel GPU estimate)")
                        return 2.0
                    if "Name" not in line and any(keyword in line for keyword in ["AMD", "Radeon"]):
                        print("   [MEM] GPU Memory: ~4.0 GB (AMD GPU estimate)")
                        return 4.0
        except Exception as e:
            logger.debug(f"wmic GPU memory detection failed: {e}")

        print("   [MEM] GPU Memory: Unknown")
        return None

    def _get_gpu_name(self) -> str | None:
        """Get GPU name"""
        # Method 1: CUDA
        try:
            import torch

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                print(f"   [GPU] GPU Name: {gpu_name} (CUDA)")
                return gpu_name
        except Exception as e:
            logger.debug(f"CUDA GPU name detection failed: {e}")

        # Method 2: nvidia-smi
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True
            )
            if result.returncode == 0:
                gpu_name = result.stdout.strip()
                print(f"   [GPU] GPU Name: {gpu_name} (nvidia-smi)")
                return gpu_name
        except Exception as e:
            logger.debug(f"nvidia-smi GPU name detection failed: {e}")

        # Method 3: wmic (Windows)
        try:
            import subprocess

            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"], capture_output=True, text=True
            )
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split("\n") if line.strip() and line.strip() != "Name"]
                if lines:
                    gpu_name = lines[0]
                    print(f"   [GPU] GPU Name: {gpu_name} (wmic)")
                    return gpu_name
        except Exception as e:
            logger.debug(f"wmic GPU name detection failed: {e}")

        print("   [GPU] GPU Name: Unknown")
        return None

    def _get_gpu_driver_version(self) -> str | None:
        """Get GPU driver version"""
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"nvidia-smi driver version detection failed: {e}")
        return None

    def _check_colqwen_requirements(self) -> bool:
        """Check if system meets ColQwen2.5 requirements"""
        try:
            import torch
            import transformers

            # Check torch version >= 2.2.0
            torch_version = torch.__version__.split(".")
            if int(torch_version[0]) < 2 or (int(torch_version[0]) == 2 and int(torch_version[1]) < 2):
                print(f"   [REQ] PyTorch version too old: {torch.__version__} (need >= 2.2.0)")
                return False

            # Check transformers version >= 4.45.0
            transformers_version = transformers.__version__.split(".")
            if int(transformers_version[0]) < 4 or (
                int(transformers_version[0]) == 4 and int(transformers_version[1]) < 45
            ):
                print(f"   [REQ] Transformers version too old: {transformers.__version__} (need >= 4.45.0)")
                return False

            # Check GPU VRAM >= 4GB (if GPU available)
            if self.specs.gpu_available and self.specs.gpu_memory_gb and self.specs.gpu_memory_gb < 4.0:
                print(f"   [REQ] GPU VRAM insufficient: {self.specs.gpu_memory_gb:.1f} GB (need >= 4GB)")
                return False

            print("   [REQ] ColQwen2.5 requirements met")
            return True

        except ImportError as e:
            print(f"   [REQ] Missing dependencies for ColQwen2.5: {e}")
            return False

    def _get_visual_embedding_model(self) -> str:
        """Get visual embedding model based on hardware"""
        # Read from environment or use default
        model = os.getenv("AI_VISUAL_EMBEDDING_MODEL", "vidore/colqwen2.5-v0.2")

        # Check if requirements are met
        if self._check_colqwen_requirements():
            print(f"   [VIS] Using visual embedding model: {model}")
            return model
        print("   [VIS] ColQwen2.5 requirements not met, visual embeddings disabled")
        return None

    def recommend_model_tier(self) -> ModelTier:
        """Recommend model tier based on hardware"""
        ram_gb = self.specs.total_ram_gb
        cores = self.specs.cpu_cores
        gpu_available = self.specs.gpu_available
        gpu_memory_gb = self.specs.gpu_memory_gb or 0

        # High Performance: 32+ GB RAM, 8+ cores, OR 8+ GB GPU VRAM
        if (ram_gb >= 32 and cores >= 8) or (gpu_available and gpu_memory_gb >= 8):
            return ModelTier.HIGH_PERFORMANCE

        # Balanced: 16-32 GB RAM, 4+ cores, OR 4+ GB GPU VRAM
        if (ram_gb >= 16 and cores >= 4) or (gpu_available and gpu_memory_gb >= 4):
            return ModelTier.BALANCED

        # Conservative: <16 GB RAM or <4 cores, OR <4 GB GPU VRAM
        return ModelTier.CONSERVATIVE

    def get_model_config(self, tier: ModelTier | None = None) -> ModelConfig:
        """Get model configuration for specified tier"""
        if tier is None:
            tier = self.recommend_model_tier()

        # GPU-optimized configurations
        gpu_available = self.specs.gpu_available

        # Read embedding model from env
        embedding_model = os.getenv("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text:latest")

        configs = {
            ModelTier.CONSERVATIVE: ModelConfig(
                text_classification="llama3.2:3b",
                embeddings=embedding_model,
                vision="llava:7b",
                visual_embeddings=os.getenv("AI_VISUAL_EMBEDDING_MODEL", "vidore/colqwen2.5-v0.2"),
                table_embeddings=embedding_model,
                tier=ModelTier.CONSERVATIVE,
                estimated_ram_usage_gb=8.0,
                parallel_processing=True,
                gpu_acceleration=gpu_available,
                estimated_gpu_usage_gb=6.0 if gpu_available else 0.0,  # +2GB for visual embeddings
            ),
            ModelTier.BALANCED: ModelConfig(
                text_classification="llama3.2:latest",
                embeddings=embedding_model,
                vision="llava:latest",
                visual_embeddings=os.getenv("AI_VISUAL_EMBEDDING_MODEL", "vidore/colqwen2.5-v0.2"),
                table_embeddings=embedding_model,
                tier=ModelTier.BALANCED,
                estimated_ram_usage_gb=16.0,
                parallel_processing=True,
                gpu_acceleration=gpu_available,
                estimated_gpu_usage_gb=8.0 if gpu_available else 0.0,  # +2GB for visual embeddings
            ),
            ModelTier.HIGH_PERFORMANCE: ModelConfig(
                text_classification="llama3.2:latest",
                embeddings=embedding_model,
                vision="llava:latest",
                visual_embeddings=os.getenv("AI_VISUAL_EMBEDDING_MODEL", "vidore/colqwen2.5-v0.2"),
                table_embeddings=embedding_model,
                tier=ModelTier.HIGH_PERFORMANCE,
                estimated_ram_usage_gb=16.0,
                parallel_processing=True,
                gpu_acceleration=gpu_available,
                estimated_gpu_usage_gb=10.0 if gpu_available else 0.0,  # +4GB for visual embeddings
            ),
        }

        return configs[tier]


class AIConfigManager:
    """AI Configuration Manager with auto-detection"""

    def __init__(self):
        self.detector = HardwareDetector()
        self.config = None
        self._load_config()

    def _load_config(self):
        """Load AI configuration based on hardware detection"""
        tier = self.detector.recommend_model_tier()
        self.config = self.detector.get_model_config(tier)

        print("Hardware Detection:")
        print(f"   RAM: {self.detector.specs.total_ram_gb:.1f} GB")
        print(f"   CPU: {self.detector.specs.cpu_cores} cores, {self.detector.specs.cpu_threads} threads")
        if self.detector.specs.gpu_available:
            print(f"   GPU: {self.detector.specs.gpu_name} ({self.detector.specs.gpu_memory_gb:.1f} GB VRAM)")
            print(f"   GPU Driver: {self.detector.specs.gpu_driver_version}")
        else:
            print("   GPU: Not Available")
        print(f"   Recommended Tier: {tier.value}")
        print(f"   GPU Acceleration: {'Enabled' if self.config.gpu_acceleration else 'Disabled'}")
        print(f"   Selected Models: {self.config.text_classification}, {self.config.embeddings}, {self.config.vision}")

    def get_config(self) -> ModelConfig:
        """Get current model configuration"""
        return self.config

    def get_ollama_models(self) -> dict[str, str]:
        """Get Ollama model names for different tasks"""
        return {
            "text_classification": self.config.text_classification,
            "embeddings": self.config.embeddings,
            "vision": self.config.vision,
            "visual_embeddings": self.config.visual_embeddings,
            "table_embeddings": self.config.table_embeddings,
        }

    def get_model_requirements(self) -> dict[str, any]:
        """Get model requirements for resource management"""
        return {
            "estimated_ram_gb": self.config.estimated_ram_usage_gb,
            "parallel_processing": self.config.parallel_processing,
            "tier": self.config.tier.value,
            "hardware_specs": {
                "total_ram_gb": self.detector.specs.total_ram_gb,
                "cpu_cores": self.detector.specs.cpu_cores,
                "gpu_available": self.detector.specs.gpu_available,
            },
        }


# Global AI Configuration
ai_config = AIConfigManager()


# Export for easy access
def get_ai_config() -> ModelConfig:
    """Get current AI configuration"""
    return ai_config.get_config()


def get_ollama_models() -> dict[str, str]:
    """Get Ollama model names"""
    return ai_config.get_ollama_models()


def get_model_requirements() -> dict[str, any]:
    """Get model requirements"""
    return ai_config.get_model_requirements()


# Model-specific configurations
OLLAMA_MODELS = {
    "text_classification": {
        "llama3.2:7b": {
            "ram_usage_gb": 4.0,
            "context_length": 8192,
            "languages": ["en", "de"],
            "specialization": "general",
        },
        "llama3.2:latest": {
            "ram_usage_gb": 8.0,
            "context_length": 8192,
            "languages": ["en", "de"],
            "specialization": "general",
        },
        "llama3.2:70b": {
            "ram_usage_gb": 40.0,
            "context_length": 8192,
            "languages": ["en", "de"],
            "specialization": "general",
        },
    },
    "embeddings": {
        "embeddinggemma:latest": {
            "ram_usage_gb": 2.0,
            "embedding_dimensions": 768,
            "languages": ["en", "de"],
            "specialization": "multilingual",
        }
    },
    "vision": {
        "llava:7b": {
            "ram_usage_gb": 4.0,
            "image_resolution": "336x336",
            "languages": ["en", "de"],
            "specialization": "general_vision",
        },
        "llava:latest": {
            "ram_usage_gb": 8.0,
            "image_resolution": "336x336",
            "languages": ["en", "de"],
            "specialization": "general_vision",
        },
        "llava:34b": {
            "ram_usage_gb": 20.0,
            "image_resolution": "336x336",
            "languages": ["en", "de"],
            "specialization": "general_vision",
        },
    },
}

# Visual embedding models (ColQwen2.5)
VISUAL_EMBEDDING_MODELS = {
    "colqwen2.5-v0.2": {
        "ram_usage_gb": 4.0,
        "gpu_vram_gb": 4.0,
        "embedding_dimensions": 768,  # After mean pooling
        "languages": ["multilingual"],
        "specialization": "visual_document_retrieval",
        "model_type": "colbert_style_multi_vector",
    }
}

# Table embedding models (reuse text models)
TABLE_EMBEDDING_MODELS = {
    "nomic-embed-text:latest": {
        "ram_usage_gb": 2.0,
        "embedding_dimensions": 768,
        "languages": ["en", "de"],
        "specialization": "structured_data",
    }
}

# Task-specific model assignments
TASK_MODELS = {
    "document_classification": "text_classification",
    "manufacturer_detection": "text_classification",
    "model_extraction": "text_classification",
    "features_extraction": "text_classification",
    "error_code_extraction": "text_classification",
    "version_extraction": "text_classification",
    "text_chunking": "text_classification",
    "semantic_search": "embeddings",
    "image_ocr": "vision",
    "image_classification": "vision",
    "defect_detection": "vision",
}
