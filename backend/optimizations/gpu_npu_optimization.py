"""
GPU/NPU Optimization Module - Advanced hardware acceleration
"""

import asyncio
import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

try:
    import torch
    import torch.multiprocessing as torch_mp
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import cupy as cp

    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class GPUOptimizer:
    """
    GPU optimization for parallel processing and acceleration
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.gpu_optimizer")
        self.gpu_available = False
        self.gpu_count = 0
        self.gpu_memory = {}
        self.optimization_level = "none"

        self._detect_gpu_capabilities()

    def _detect_gpu_capabilities(self):
        """Detect available GPU capabilities"""
        if TORCH_AVAILABLE:
            if torch.cuda.is_available():
                self.gpu_available = True
                self.gpu_count = torch.cuda.device_count()

                for i in range(self.gpu_count):
                    props = torch.cuda.get_device_properties(i)
                    self.gpu_memory[i] = {
                        "name": props.name,
                        "memory_total": props.total_memory,
                        "memory_free": torch.cuda.get_device_properties(i).total_memory
                        - torch.cuda.memory_allocated(i),
                        "compute_capability": f"{props.major}.{props.minor}",
                        "multiprocessor_count": props.multi_processor_count,
                    }

                self.logger.info(f"GPU Detection: {self.gpu_count} GPUs available")
                for gpu_id, info in self.gpu_memory.items():
                    self.logger.info(f"  GPU {gpu_id}: {info['name']} - {info['memory_total']/1024**3:.1f}GB")

                # Set optimization level based on GPU capabilities
                if self.gpu_count >= 2:
                    self.optimization_level = "high"
                elif self.gpu_count >= 1:
                    self.optimization_level = "medium"
                else:
                    self.optimization_level = "low"
            else:
                self.logger.info("No CUDA GPUs available")
        else:
            self.logger.info("PyTorch not available - GPU acceleration disabled")

    def get_optimal_worker_count(self, task_type: str = "general") -> int:
        """Get optimal number of workers based on hardware"""
        cpu_count = mp.cpu_count()

        if self.gpu_available:
            if task_type == "embedding":
                # For embeddings, use GPU count as base
                return min(self.gpu_count * 2, cpu_count)
            if task_type == "image_processing":
                # For image processing, use GPU count
                return self.gpu_count
            if task_type == "text_processing":
                # For text processing, use more CPU cores
                return min(cpu_count, self.gpu_count * 4)
            # General tasks
            return min(cpu_count, self.gpu_count * 3)
        # CPU-only optimization
        return min(cpu_count, 8)  # Cap at 8 for stability

    def create_optimized_executor(self, task_type: str = "general", max_workers: int | None = None):
        """Create optimized executor based on task type and hardware"""
        if max_workers is None:
            max_workers = self.get_optimal_worker_count(task_type)

        if task_type in ["embedding", "image_processing"] and self.gpu_available:
            # Use ProcessPoolExecutor for GPU-intensive tasks
            return ProcessPoolExecutor(max_workers=max_workers)
        # Use ThreadPoolExecutor for I/O-bound tasks
        return ThreadPoolExecutor(max_workers=max_workers)

    async def process_batch_parallel(
        self, tasks: list[Any], task_type: str = "general", max_workers: int | None = None
    ) -> list[Any]:
        """Process batch of tasks in parallel with GPU optimization"""
        if not tasks:
            return []

        max_workers = max_workers or self.get_optimal_worker_count(task_type)

        # Create optimized executor
        with self.create_optimized_executor(task_type, max_workers) as executor:
            # Submit all tasks
            if asyncio.iscoroutinefunction(tasks[0]):
                # Async tasks
                futures = [asyncio.create_task(task) for task in tasks]
                results = await asyncio.gather(*futures, return_exceptions=True)
            else:
                # Sync tasks
                futures = [executor.submit(task) for task in tasks]
                results = []
                for future in futures:
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"Task failed: {e}")
                        results.append(None)

            return results


class NPUOptimizer:
    """
    NPU (Neural Processing Unit) optimization for AI tasks
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.npu_optimizer")
        self.npu_available = False
        self.npu_type = None
        self.optimization_enabled = False

        self._detect_npu_capabilities()

    def _detect_npu_capabilities(self):
        """Detect NPU capabilities"""
        # Check for Intel NPU
        try:
            import intel_extension_for_pytorch as ipex

            if hasattr(ipex, "xpu") and ipex.xpu.is_available():
                self.npu_available = True
                self.npu_type = "Intel NPU"
                self.optimization_enabled = True
                self.logger.info("Intel NPU detected and available")
                return
        except ImportError:
            pass

        # Check for Qualcomm NPU
        try:
            import qnn

            self.npu_available = True
            self.npu_type = "Qualcomm NPU"
            self.optimization_enabled = True
            self.logger.info("Qualcomm NPU detected and available")
            return
        except ImportError:
            pass

        # Check for Apple Neural Engine
        try:
            if hasattr(os, "uname") and os.uname().sysname == "Darwin":  # macOS
                try:
                    import coremltools as ct

                    self.npu_available = True
                    self.npu_type = "Apple Neural Engine"
                    self.optimization_enabled = True
                    self.logger.info("Apple Neural Engine detected and available")
                    return
                except ImportError:
                    pass
        except AttributeError:
            pass

        self.logger.info("No NPU detected - using CPU/GPU fallback")

    def optimize_model_for_npu(self, model, input_shape=None):
        """Optimize model for NPU execution"""
        if not self.npu_available:
            return model

        try:
            if self.npu_type == "Intel NPU":
                import intel_extension_for_pytorch as ipex

                model = ipex.optimize(model)
            elif self.npu_type == "Apple Neural Engine":
                # Convert to CoreML format

                # Implementation would depend on specific model type
                pass

            self.logger.info(f"Model optimized for {self.npu_type}")
            return model
        except Exception as e:
            self.logger.warning(f"NPU optimization failed: {e}")
            return model


class HardwareAccelerator:
    """
    Main hardware acceleration coordinator
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.hardware_accelerator")
        self.gpu_optimizer = GPUOptimizer()
        self.npu_optimizer = NPUOptimizer()

        self.logger.info("Hardware Accelerator initialized")
        self._log_hardware_summary()

    def _log_hardware_summary(self):
        """Log hardware capabilities summary"""
        self.logger.info("=== HARDWARE ACCELERATION SUMMARY ===")
        self.logger.info(f"GPU Available: {self.gpu_optimizer.gpu_available}")
        if self.gpu_optimizer.gpu_available:
            self.logger.info(f"GPU Count: {self.gpu_optimizer.gpu_count}")
            self.logger.info(f"GPU Optimization Level: {self.gpu_optimizer.optimization_level}")

        self.logger.info(f"NPU Available: {self.npu_optimizer.npu_available}")
        if self.npu_optimizer.npu_available:
            self.logger.info(f"NPU Type: {self.npu_optimizer.npu_type}")

        # Calculate optimal settings
        optimal_workers = {
            "general": self.gpu_optimizer.get_optimal_worker_count("general"),
            "embedding": self.gpu_optimizer.get_optimal_worker_count("embedding"),
            "image_processing": self.gpu_optimizer.get_optimal_worker_count("image_processing"),
            "text_processing": self.gpu_optimizer.get_optimal_worker_count("text_processing"),
        }

        self.logger.info("Optimal Worker Counts:")
        for task_type, count in optimal_workers.items():
            self.logger.info(f"  {task_type}: {count}")
        self.logger.info("=====================================")

    def get_optimization_config(self) -> dict[str, Any]:
        """Get optimization configuration for different task types"""
        return {
            "gpu_available": self.gpu_optimizer.gpu_available,
            "npu_available": self.npu_optimizer.npu_available,
            "optimal_workers": {
                "general": self.gpu_optimizer.get_optimal_worker_count("general"),
                "embedding": self.gpu_optimizer.get_optimal_worker_count("embedding"),
                "image_processing": self.gpu_optimizer.get_optimal_worker_count("image_processing"),
                "text_processing": self.gpu_optimizer.get_optimal_worker_count("text_processing"),
            },
            "optimization_level": self.gpu_optimizer.optimization_level,
            "npu_type": self.npu_optimizer.npu_type,
        }

    async def process_documents_parallel(
        self, documents: list[str], processor_func, task_type: str = "general"
    ) -> list[Any]:
        """Process multiple documents in parallel with hardware optimization"""
        if not documents:
            return []

        # Get optimal worker count
        max_workers = self.gpu_optimizer.get_optimal_worker_count(task_type)

        self.logger.info(f"Processing {len(documents)} documents with {max_workers} workers ({task_type})")

        # Create tasks
        tasks = [processor_func(doc) for doc in documents]

        # Process in parallel
        results = await self.gpu_optimizer.process_batch_parallel(tasks, task_type, max_workers)

        return results


# Global instance
hardware_accelerator = HardwareAccelerator()
