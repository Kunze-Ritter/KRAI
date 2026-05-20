"""
Visual Embedding Processor - Generate visual document embeddings
Stage 3b of the processing pipeline. Uses ColQwen2.5-v0.2 for visual document retrieval.

Features:
- Multi-vector embeddings (768 patches per image)
- Mean pooling to 768-dim for storage efficiency
- GPU acceleration with CPU fallback
- Batch processing for performance
- Integration with embeddings_v2 table
"""

import logging
import os
import time
from typing import Any
from uuid import UUID

import numpy as np
import torch
from PIL import Image

try:
    from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

    COLPALI_AVAILABLE = True
except ImportError:
    COLPALI_AVAILABLE = False
    logging.warning("colpali-engine not available - visual embeddings disabled")

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage

from .stage_tracker import StageTracker


class VisualEmbeddingProcessor(BaseProcessor):
    """Generate visual embeddings for images using ColQwen2.5"""

    def __init__(
        self,
        database_service,
        model_name: str | None = None,
        device: str = "auto",
        batch_size: int = 4,
        embedding_dimension: int = 768,
    ):
        super().__init__(name="VisualEmbeddingProcessor")
        self.stage = Stage.VISUAL_EMBEDDING
        self.database_service = database_service
        self.stage_tracker = StageTracker(database_service) if database_service else None
        self.model_name = model_name or os.getenv("AI_VISUAL_EMBEDDING_MODEL", "vidore/colqwen2.5-v0.2")
        self.batch_size = batch_size
        self.embedding_dimension = embedding_dimension
        self.storage_embedding_dimension = embedding_dimension
        self._logged_embedding_dimension_mismatch = False

        # Device detection
        self.device = self._detect_device(device)

        # Dtype selection (avoid bfloat16 on GPUs that don't support it)
        self.torch_dtype = self._select_torch_dtype()

        # Model loading (lazy)
        self.model = None
        self.processor = None
        self.model_loaded = False

        # Remove custom logger - use BaseProcessor.logger_context instead

        # Check if visual embeddings are enabled
        self.enabled = os.getenv("ENABLE_VISUAL_EMBEDDINGS", "true").lower() == "true"
        if not self.enabled:
            with self.logger_context() as adapter:
                adapter.info("Visual embeddings disabled via ENABLE_VISUAL_EMBEDDINGS")
            return

        # Check dependencies
        if not COLPALI_AVAILABLE:
            with self.logger_context() as adapter:
                adapter.error("colpali-engine not available - visual embeddings disabled")
            self.enabled = False
            return

    def _detect_device(self, device: str) -> str:
        """Detect optimal device for model inference"""
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda:0"
                with self.logger_context() as adapter:
                    adapter.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                with self.logger_context() as adapter:
                    adapter.info("CUDA not available, using CPU")
        else:
            with self.logger_context() as adapter:
                adapter.info(f"Using specified device: {device}")
        return device

    def _select_torch_dtype(self):
        """Select a safe dtype for inference based on device capabilities."""
        if not self.device.startswith("cuda"):
            return torch.float32

        env_dtype = (os.getenv("VISUAL_EMBEDDING_TORCH_DTYPE") or "").strip().lower()
        if env_dtype:
            if env_dtype in ("bf16", "bfloat16"):
                if hasattr(torch.cuda, "is_bf16_supported") and torch.cuda.is_bf16_supported():
                    return torch.bfloat16
                with self.logger_context() as adapter:
                    adapter.warning(
                        "VISUAL_EMBEDDING_TORCH_DTYPE=%s requested but bf16 not supported on this GPU; falling back to float16",
                        env_dtype,
                    )
                return torch.float16
            if env_dtype in ("fp16", "float16", "half"):
                return torch.float16
            if env_dtype in ("fp32", "float32"):
                return torch.float32

            with self.logger_context() as adapter:
                adapter.warning(
                    "Unknown VISUAL_EMBEDDING_TORCH_DTYPE=%s; falling back to float16",
                    env_dtype,
                )

        return torch.float16

    def _load_model(self) -> bool:
        """Lazy load ColQwen2.5 model and processor"""
        if self.model_loaded:
            return True

        try:
            with self.logger_context() as adapter:
                adapter.info(f"Loading ColQwen2.5 model: {self.model_name}")

            # Load model with appropriate dtype
            torch_dtype = self.torch_dtype

            self.model = ColQwen2_5.from_pretrained(
                self.model_name, torch_dtype=torch_dtype, device_map=self.device
            ).eval()

            # Load processor
            self.processor = ColQwen2_5_Processor.from_pretrained(self.model_name)

            self.model_loaded = True
            with self.logger_context() as adapter:
                adapter.info(f"ColQwen2.5 model loaded successfully on {self.device}")

            # Log model info
            if self.device.startswith("cuda"):
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                with self.logger_context() as adapter:
                    adapter.info(f"GPU Memory: {gpu_memory:.1f} GB")

            return True

        except Exception as e:
            with self.logger_context() as adapter:
                adapter.error(f"Failed to load ColQwen2.5 model: {e}")
            self.enabled = False
            return False

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Process images in the context and generate visual embeddings"""
        with self.logger_context(document_id=context.document_id, stage=self.stage.value) as adapter:
            adapter.info(f"Starting visual embedding processing for document {context.document_id}")

            # Start stage tracking
            if self.stage_tracker:
                await self.stage_tracker.start_stage(str(context.document_id), self.stage.value)

            try:
                # Validate context
                if not context.document_id:
                    if self.stage_tracker:
                        await self.stage_tracker.fail_stage(
                            str(context.document_id) if context.document_id else "unknown",
                            self.stage.value,
                            error="Document ID is required",
                        )
                    return self.create_error_result(
                        ProcessingError("Document ID is required", self.name, "MISSING_DOCUMENT_ID"),
                        data={"embeddings_created": 0, "failed_count": 0},
                    )

                if not hasattr(context, "images") or not context.images:
                    adapter.info("No images to process")
                    if self.stage_tracker:
                        await self.stage_tracker.complete_stage(
                            str(context.document_id),
                            self.stage.value,
                            metadata={"embeddings_created": 0, "failed_count": 0},
                        )
                    return self.create_success_result(
                        data={"embeddings_created": 0, "failed_count": 0},
                        metadata={"stage": self.stage.value, "message": "No images to process"},
                    )

                # Process images
                result = await self.process_document(context.document_id, context.images)

                if not isinstance(result, dict):
                    result = {
                        "success": False,
                        "error": "Visual embedding processor returned no result",
                        "embeddings_created": 0,
                        "failed_count": len(context.images) if hasattr(context, "images") else 0,
                    }

                if result.get("success"):
                    if self.stage_tracker:
                        await self.stage_tracker.complete_stage(
                            str(context.document_id),
                            self.stage.value,
                            metadata={
                                "embeddings_created": result.get("embeddings_created", 0),
                                "failed_count": result.get("failed_count", 0),
                            },
                        )
                    return self.create_success_result(
                        data={
                            "embeddings_created": result["embeddings_created"],
                            "failed_count": result["failed_count"],
                            "embedding_ids": result.get("embedding_ids", []),
                        },
                        metadata={"stage": self.stage.value, "processing_time": result.get("processing_time", 0)},
                    )
                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(
                        str(context.document_id), self.stage.value, error=result.get("error", "Unknown error")
                    )
                return self.create_error_result(
                    ProcessingError(
                        result.get("error", "Unknown error"),
                        self.name,
                        "VISUAL_EMBEDDING_FAILED",
                    ),
                    metadata={"stage": self.stage.value},
                    data={"embeddings_created": 0, "failed_count": len(context.images)},
                )

            except Exception as e:
                adapter.error(f"Visual embedding processing failed: {e}")
                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(
                        str(context.document_id) if context.document_id else "unknown", self.stage.value, error=str(e)
                    )
                return self.create_error_result(
                    ProcessingError(str(e), self.name, "VISUAL_EMBEDDING_EXCEPTION"),
                    metadata={"stage": self.stage.value},
                    data={
                        "embeddings_created": 0,
                        "failed_count": len(context.images) if hasattr(context, "images") else 0,
                    },
                )

    async def process_document(self, document_id: UUID, images: list[dict[str, Any]]) -> dict[str, Any]:
        """Process document images and generate embeddings"""
        start_time = time.time()

        # Load model if not loaded
        if not self._load_model():
            return {
                "success": False,
                "error": "Failed to load ColQwen2.5 model",
                "embeddings_created": 0,
                "failed_count": len(images),
            }

        # Start stage tracking
        if self.stage_tracker:
            await self.stage_tracker.start_stage(str(document_id), self.stage.value)

        with self.logger_context(document_id=document_id, stage=self.stage.value) as adapter:
            adapter.info(f"Processing {len(images)} images with ColQwen2.5")

        total_processed = 0
        total_failed = 0
        embeddings_created = []

        try:
            # Process images in batches
            for i in range(0, len(images), self.batch_size):
                batch_images = images[i : i + self.batch_size]
                batch_start = time.time()

                try:
                    # Generate embeddings for batch
                    embeddings = self._embed_batch(batch_images)

                    # Store embeddings
                    batch_results = await self._store_embeddings(document_id, batch_images, embeddings)

                    total_processed += batch_results["success_count"]
                    total_failed += batch_results["failed_count"]
                    embeddings_created.extend(batch_results["embedding_ids"])

                    batch_duration = time.time() - batch_start
                    with self.logger_context() as adapter:
                        adapter.info(
                            f"Batch {i//self.batch_size + 1}: "
                            f"{batch_results['success_count']}/{len(batch_images)} images "
                            f"in {batch_duration:.2f}s"
                        )

                except Exception as e:
                    with self.logger_context() as adapter:
                        adapter.error(f"Batch {i//self.batch_size + 1} failed: {e}")
                    total_failed += len(batch_images)

            processing_time = time.time() - start_time
            if self.stage_tracker:
                await self.stage_tracker.complete_stage(
                    str(document_id),
                    self.stage.value,
                    metadata={
                        "embeddings_created": total_processed,
                        "failed_count": total_failed,
                        "processing_time": processing_time,
                    },
                )

            return {
                "success": True,
                "embeddings_created": total_processed,
                "failed_count": total_failed,
                "embedding_ids": embeddings_created,
                "processing_time": processing_time,
            }

        except Exception as e:
            with self.logger_context(document_id=document_id, stage=self.stage.value) as adapter:
                adapter.error(f"Visual embedding processing failed: {e}")
            if self.stage_tracker:
                await self.stage_tracker.fail_stage(str(document_id), self.stage.value, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "embeddings_created": total_processed,
                "failed_count": total_failed,
            }

    def _embed_batch(self, images: list[dict[str, Any]]) -> list[tuple[int, np.ndarray]]:
        """Generate embeddings for a batch of images"""
        try:
            # Load PIL images from paths
            image_paths = []
            for img in images:
                temp_path = img.get("temp_path")
                if temp_path and os.path.exists(temp_path):
                    image_paths.append(temp_path)
                else:
                    with self.logger_context() as adapter:
                        adapter.warning(f"Image file not found: {temp_path}")
                    image_paths.append(None)

            # Filter out missing images and track original indices
            valid_indices = [i for i, path in enumerate(image_paths) if path is not None]
            valid_paths = [image_paths[i] for i in valid_indices]

            if not valid_paths:
                return []

            # Load and process images
            pil_images = []
            for path in valid_paths:
                try:
                    img = Image.open(path).convert("RGB")
                    pil_images.append(img)
                except Exception as e:
                    with self.logger_context() as adapter:
                        adapter.error(f"Failed to load image {path}: {e}")
                    continue

            if not pil_images:
                return []

            # Process with ColQwen2.5
            # Note: Verify API usage - using process_images for ColQwen2.5
            # The processor expects images as PIL Image objects
            try:
                # Try the correct API for ColQwen2.5
                if hasattr(self.processor, "process_images"):
                    inputs = self.processor.process_images(pil_images)
                else:
                    # Fallback to standard processor
                    inputs = self.processor(images=pil_images, return_tensors="pt")
            except Exception as e:
                with self.logger_context() as adapter:
                    adapter.error(f"Failed to process images with ColQwen2.5: {e}")
                # Try alternative approach
                inputs = self.processor(images=pil_images, return_tensors="pt")

            def _move_tensor(value):
                if not torch.is_tensor(value):
                    return value
                if value.is_floating_point():
                    return value.to(self.device, dtype=self.torch_dtype)
                return value.to(self.device)

            inputs = {k: _move_tensor(v) for k, v in inputs.items()}

            with torch.no_grad():
                # Generate embeddings - verify the correct method
                try:
                    # Try the standard forward pass
                    outputs = self.model(**inputs)
                    # ColQwen2.5 typically returns last_hidden_state
                    if hasattr(outputs, "last_hidden_state"):
                        embeddings = outputs.last_hidden_state
                    elif hasattr(outputs, "pooler_output"):
                        embeddings = outputs.pooler_output.unsqueeze(1)
                    else:
                        # Fallback to the first tensor output
                        embeddings = outputs[0] if isinstance(outputs, list | tuple) else outputs

                except Exception as e:
                    with self.logger_context() as adapter:
                        adapter.error(f"Failed to generate embeddings: {e}")
                    raise e

                # Verify tensor shape
                if len(embeddings.shape) == 3:
                    # Shape: (batch, num_patches, hidden_dim)
                    # Mean pool across patches to get single vector per image
                    aggregated = embeddings.mean(dim=1).cpu().numpy()
                elif len(embeddings.shape) == 2:
                    # Shape: (batch, hidden_dim) - already pooled
                    aggregated = embeddings.cpu().numpy()
                else:
                    with self.logger_context() as adapter:
                        adapter.error(f"Unexpected embedding shape: {embeddings.shape}")
                    raise ValueError(f"Unexpected embedding shape: {embeddings.shape}")

                # Store native dimension instead of zero-padding
                # Record the actual embedding dimension in metadata
                self.embedding_dimension = aggregated.shape[1]
                with self.logger_context() as adapter:
                    adapter.info(f"Visual embedding dimension: {self.embedding_dimension}")

                # Return list of (original_index, embedding) tuples
                result = []
                for i, embedding in enumerate(aggregated):
                    original_index = valid_indices[i]
                    result.append((original_index, embedding))

                return result

        except torch.cuda.OutOfMemoryError as e:
            with self.logger_context() as adapter:
                adapter.error(f"GPU OOM during embedding generation: {e}")
            # Reduce batch size and retry
            if self.batch_size > 1:
                self.batch_size = max(1, self.batch_size // 2)
                with self.logger_context() as adapter:
                    adapter.info(f"Reduced batch size to {self.batch_size} due to GPU OOM")
                return self._embed_batch(images[: self.batch_size])
            raise e
        except Exception as e:
            with self.logger_context() as adapter:
                adapter.error(f"Embedding generation failed: {e}")
            return []

    async def _store_embeddings(
        self, document_id: UUID, images: list[dict[str, Any]], embeddings: list[tuple[int, np.ndarray]]
    ) -> dict[str, Any]:
        """Store embeddings in database"""
        success_count = 0
        failed_count = 0
        embedding_ids = []

        try:
            for original_index, embedding in embeddings:
                if original_index >= len(images):
                    failed_count += 1
                    continue

                img = images[original_index]

                try:
                    try:
                        embedding_list = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                    except Exception:
                        embedding_list = list(embedding)

                    target_dim = int(getattr(self, "storage_embedding_dimension", 768) or 768)
                    actual_dim = len(embedding_list)
                    if actual_dim != target_dim:
                        if not self._logged_embedding_dimension_mismatch:
                            with self.logger_context() as adapter:
                                adapter.warning(
                                    "Visual embedding dimension mismatch (actual=%d target=%d) - padding/truncating to target for DB storage",
                                    actual_dim,
                                    target_dim,
                                )
                            self._logged_embedding_dimension_mismatch = True

                        if actual_dim > target_dim:
                            embedding_list = embedding_list[:target_dim]
                        else:
                            embedding_list = embedding_list + ([0.0] * (target_dim - actual_dim))

                    # Store via database adapter with positional arguments
                    embedding_id = await self.database_service.create_unified_embedding(
                        source_id=img.get("id"),
                        source_type="image",
                        embedding=embedding_list,
                        model_name=self.model_name,
                        embedding_context=img.get("ai_description", "")[:500],
                        metadata={
                            "image_type": img.get("image_type"),
                            "page_number": img.get("page_number"),
                            "width": img.get("width"),
                            "height": img.get("height"),
                            "file_size": img.get("file_size"),
                            "embedding_dimension": self.embedding_dimension,
                            "stored_embedding_dimension": target_dim,
                            "embedding_model": self.model_name,
                        },
                    )

                    embedding_ids.append(embedding_id)
                    success_count += 1

                except Exception as e:
                    with self.logger_context() as adapter:
                        adapter.error(f"Failed to store embedding for image {original_index}: {e}")
                    failed_count += 1

            return {"success_count": success_count, "failed_count": failed_count, "embedding_ids": embedding_ids}

        except Exception as e:
            with self.logger_context() as adapter:
                adapter.error(f"Batch embedding storage failed: {e}")
            return {"success_count": success_count, "failed_count": len(images), "embedding_ids": embedding_ids}

    def get_configuration_status(self) -> dict[str, Any]:
        """Get processor configuration status"""
        return {
            "enabled": self.enabled,
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "embedding_dimension": self.embedding_dimension,
            "model_loaded": self.model_loaded,
            "colpali_available": COLPALI_AVAILABLE,
            "dependencies": {
                "torch": torch.__version__ if "torch" in globals() else "not_installed",
                "transformers": "installed" if COLPALI_AVAILABLE else "not_installed",
            },
        }
