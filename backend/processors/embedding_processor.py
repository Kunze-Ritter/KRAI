"""
Embedding Processor - Generate vector embeddings for semantic search

Stage 7 of the processing pipeline.

ARCHITECTURE (Refactored 2026-03-05):
- embedding_config.py: Configuration, session, batch management
- embedding_processor.py: Main facade (this file)

Uses embeddinggemma via Ollama for local, fast embeddings.
Stores vectors in PostgreSQL (krai_intelligence.chunks.embedding) for similarity search.

Features:
- Batch embedding generation
- Ollama integration (embeddinggemma 768-dim)
- pgvector storage in PostgreSQL
- Multi-modal embeddings support (text, image, table) via unified_embeddings table
- Similarity search
- Progress tracking
- Compatibility with vw_chunks view
"""

import asyncio
import json
import os
import platform
import random
import time
from collections import deque
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import requests
from requests import exceptions as requests_exceptions
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.core.base_processor import BaseProcessor, Stage
from backend.pipeline.metrics import metrics
from backend.processors.logger import text_stats

# Import from refactored modules
from .stage_tracker import StageTracker


class EmbeddingProcessor(BaseProcessor):
    """
    Stage 7: Embedding Processor

    Generates vector embeddings for chunks to enable semantic search.
    """

    @staticmethod
    def _make_json_safe(value: Any) -> Any:
        """Recursively convert values to JSON-serializable types."""
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): EmbeddingProcessor._make_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [EmbeddingProcessor._make_json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [EmbeddingProcessor._make_json_safe(v) for v in value]
        if isinstance(value, set):
            return [EmbeddingProcessor._make_json_safe(v) for v in value]
        return value

    def __init__(
        self,
        database_adapter=None,
        ollama_url: str | None = None,
        model_name: str | None = None,
        batch_size: int = 100,
        embedding_dimension: int = 768,
        min_batch_size: int = 25,
        max_batch_size: int = 200,
        batch_adjust_step: int = 10,
        **_legacy_kwargs,
    ):
        """
        Initialize embedding processor

        Args:
            database_adapter: Database adapter/service for storage
            ollama_url: Ollama API URL (default: from env)
            model_name: Embedding model name (default: from OLLAMA_MODEL_EMBEDDING env)
            batch_size: Number of chunks to embed per batch
            embedding_dimension: Dimension of embedding vectors (768 for embeddinggemma, nomic-embed-text)
        """
        super().__init__(name="embedding_processor")
        self.stage = Stage.EMBEDDING
        self.database_adapter = database_adapter
        self.node_id = platform.node() or os.getenv("COMPUTERNAME", "unknown-host")
        self.min_batch_size = max(1, min_batch_size)
        self.max_batch_size = max(self.min_batch_size, max_batch_size)
        self.batch_adjust_step = max(1, batch_adjust_step)
        self.batch_size = max(self.min_batch_size, min(self.max_batch_size, batch_size))
        self.embedding_dimension = embedding_dimension

        # Unified multi-modal embeddings support

        # Phase 5: Context embedding configuration
        self.enable_context_embeddings = os.getenv("ENABLE_CONTEXT_EMBEDDINGS", "true").lower() == "true"
        self.context_embedding_dimension = int(os.getenv("CONTEXT_EMBEDDING_DIMENSION", str(embedding_dimension)))

        # Ollama configuration
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        # Read model from env if not provided
        self.model_name = model_name or os.getenv("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text:latest")

        # HTTP session & retry configuration
        self.request_timeout = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("EMBEDDING_REQUEST_MAX_RETRIES", "4"))
        self.retry_base_delay = float(os.getenv("EMBEDDING_RETRY_BASE_DELAY", "1.0"))
        self.retry_jitter = float(os.getenv("EMBEDDING_RETRY_JITTER", "0.5"))
        self.max_prompt_chars = int(os.getenv("EMBEDDING_MAX_PROMPT_CHARS", "0"))
        self.default_prompt_chars = int(os.getenv("EMBEDDING_DEFAULT_PROMPT_CHARS", "0"))
        self.session = self._create_session()

        # Adaptive batching configuration
        self.target_latency_lower = float(os.getenv("EMBEDDING_TARGET_LATENCY_LOWER", "1.0"))
        self.target_latency_upper = float(os.getenv("EMBEDDING_TARGET_LATENCY_UPPER", "2.0"))
        state_path_env = os.getenv("EMBEDDING_BATCH_STATE_PATH")
        default_state_dir = Path(os.getenv("KRAI_STATE_DIR", Path.cwd() / "state"))
        default_state_dir.mkdir(parents=True, exist_ok=True)
        self.batch_state_path = (
            Path(state_path_env) if state_path_env else default_state_dir / "embedding_batch_state.json"
        )
        self._batch_latency_window: deque = deque(maxlen=50)
        self._consecutive_error_batches = 0
        self._consecutive_successful_batches = 0
        self._error_recovery_threshold = int(os.getenv("EMBEDDING_ERROR_RECOVERY_THRESHOLD", "5"))
        self._load_persisted_batch_size()

        prompt_state_path_env = os.getenv("EMBEDDING_PROMPT_LIMIT_STATE_PATH")
        self.prompt_limit_state_path = (
            Path(prompt_state_path_env)
            if prompt_state_path_env
            else default_state_dir / "embedding_prompt_limit_state.json"
        )
        self.prompt_limit_floor = int(os.getenv("EMBEDDING_PROMPT_LIMIT_FLOOR", "512"))
        self._prompt_limit_by_model: dict[str, int] = {}
        self._load_persisted_prompt_limits()

        # Stage tracker
        if self.database_adapter:
            self.stage_tracker = StageTracker(self.database_adapter)
        else:
            self.stage_tracker = None

        # Check Ollama availability
        self.ollama_available = self._check_ollama()

    def close(self) -> None:
        """Cleanup resources - call when processor is no longer needed."""
        if hasattr(self, "session") and self.session:
            self.session.close()
            self.session = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        with suppress(Exception):
            self.close()

    def _create_session(self) -> requests.Session:
        """Create a persistent HTTP session with retry-aware adapter."""
        session = requests.Session()
        adapter_retries = max(0, self.max_retries - 1)
        retry = Retry(
            total=adapter_retries,
            read=adapter_retries,
            connect=adapter_retries,
            backoff_factor=self.retry_base_delay,
            status_forcelist=[],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=int(os.getenv("EMBEDDING_HTTP_POOL_CONNECTIONS", "10")),
            pool_maxsize=int(os.getenv("EMBEDDING_HTTP_POOL_MAXSIZE", "20")),
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _load_persisted_batch_size(self) -> None:
        """Load persisted batch configuration if available."""
        try:
            if self.batch_state_path.exists():
                with self.batch_state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                node_state = state.get(self.node_id)
                if node_state:
                    persisted_batch = node_state.get("batch_size")
                    if persisted_batch:
                        self.batch_size = max(self.min_batch_size, min(self.max_batch_size, int(persisted_batch)))
                        self.logger.debug("Restored batch_size=%s for node=%s", self.batch_size, self.node_id)
        except Exception as exc:
            self.logger.warning("Failed to load persisted batch size: %s", exc)

    def _persist_batch_size(self) -> None:
        """Persist current batch size to disk for warm starts."""
        try:
            state = {}
            if self.batch_state_path.exists():
                with self.batch_state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
            state[self.node_id] = {"batch_size": self.batch_size, "updated_at": datetime.now(UTC).isoformat()}
            with self.batch_state_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as exc:
            self.logger.warning("Failed to persist batch size: %s", exc)

    def _load_persisted_prompt_limits(self) -> None:
        try:
            if self.prompt_limit_state_path.exists():
                with self.prompt_limit_state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                models = state.get("models") if isinstance(state, dict) else None
                if isinstance(models, dict):
                    self._prompt_limit_by_model = {
                        str(k): int(v) for k, v in models.items() if v is not None and str(v).isdigit() and int(v) > 0
                    }
                elif isinstance(state, dict):
                    self._prompt_limit_by_model = {
                        str(k): int(v) for k, v in state.items() if v is not None and str(v).isdigit() and int(v) > 0
                    }
        except Exception as exc:
            self.logger.warning("Failed to load persisted prompt limits: %s", exc)

    def _persist_prompt_limits(self) -> None:
        try:
            payload = {
                "models": self._prompt_limit_by_model,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            with self.prompt_limit_state_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            self.logger.warning("Failed to persist prompt limits: %s", exc)

    def _update_model_prompt_limit(self, model_name: str, new_limit: int) -> None:
        try:
            new_limit_int = int(new_limit)
        except (TypeError, ValueError):
            return

        if new_limit_int <= 0:
            return

        current = self._prompt_limit_by_model.get(model_name)
        if current is None or new_limit_int < current:
            self._prompt_limit_by_model[model_name] = new_limit_int
            self._persist_prompt_limits()
            if current is None:
                self.logger.info(
                    "Learned embedding prompt limit for model=%s limit=%d",
                    model_name,
                    new_limit_int,
                )
            else:
                self.logger.info(
                    "Reduced embedding prompt limit for model=%s from %d to %d",
                    model_name,
                    current,
                    new_limit_int,
                )

    def _record_batch_latency(self, latency: float) -> None:
        """Track recent batch latencies for adaptive scaling."""
        self._batch_latency_window.append(latency)
        if len(self._batch_latency_window) == self._batch_latency_window.maxlen:
            try:
                import statistics

                p95 = statistics.quantiles(self._batch_latency_window, n=100)[94]
                p99 = statistics.quantiles(self._batch_latency_window, n=100)[98]
                self.logger.debug(
                    "Batch latency percentiles: p95=%.2fs p99=%.2fs",
                    p95,
                    p99,
                )
            except Exception:
                pass

    def _adjust_batch_size(self, latency: float) -> None:
        """Adjust batch size based on observed latency."""
        if latency < self.target_latency_lower and self.batch_size < self.max_batch_size:
            new_size = min(self.max_batch_size, self.batch_size + self.batch_adjust_step)
            if new_size != self.batch_size:
                self.logger.info(
                    "Increasing batch size from %s to %s (latency %.2fs < %.2fs)",
                    self.batch_size,
                    new_size,
                    latency,
                    self.target_latency_lower,
                )
                self.batch_size = new_size
                self._persist_batch_size()
        elif latency > self.target_latency_upper and self.batch_size > self.min_batch_size:
            new_size = max(self.min_batch_size, self.batch_size - self.batch_adjust_step)
            if new_size != self.batch_size:
                self.logger.info(
                    "Decreasing batch size from %s to %s (latency %.2fs > %.2fs)",
                    self.batch_size,
                    new_size,
                    latency,
                    self.target_latency_upper,
                )
                self.batch_size = new_size
                self._persist_batch_size()

    def _adjust_batch_size_on_errors(self, failed_count: int) -> None:
        """Decrease batch size when embedding failures occur; persists new size."""
        if failed_count <= 0 or self.batch_size <= self.min_batch_size:
            return
        # Scale down more aggressively with higher failure counts
        step = min(self.batch_adjust_step * max(1, (failed_count + 1) // 2), self.batch_size - self.min_batch_size)
        new_size = max(self.min_batch_size, self.batch_size - step)
        if new_size != self.batch_size:
            self.logger.info(
                "Decreasing batch size from %s to %s (embedding failures=%d)",
                self.batch_size,
                new_size,
                failed_count,
            )
            self.batch_size = new_size
            self._persist_batch_size()

    def _on_batch_success(self) -> None:
        """Track successful batch; optionally recover batch size after consecutive successes."""
        self._consecutive_error_batches = 0
        self._consecutive_successful_batches += 1
        if (
            self._consecutive_successful_batches >= self._error_recovery_threshold
            and self.batch_size < self.max_batch_size
        ):
            new_size = min(self.max_batch_size, self.batch_size + self.batch_adjust_step)
            if new_size != self.batch_size:
                self.logger.info(
                    "Recovering batch size from %s to %s (%d consecutive successful batches)",
                    self.batch_size,
                    new_size,
                    self._consecutive_successful_batches,
                )
                self.batch_size = new_size
                self._persist_batch_size()
                self._consecutive_successful_batches = 0

    def _on_batch_errors(self, failed_count: int) -> None:
        """Track batch errors and reduce batch size."""
        self._consecutive_successful_batches = 0
        self._consecutive_error_batches += 1
        self._adjust_batch_size_on_errors(failed_count)

    def _check_ollama(self) -> bool:
        """Check if Ollama is available and has the embedding model"""
        with self.logger_context(stage=self.stage):
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)

                if response.status_code == 200:
                    models = response.json().get("models", [])

                    model_names = [m.get("name", "").lower() for m in models]

                    if any(self.model_name in name for name in model_names):
                        self.logger.success(f"Ollama available with {self.model_name}")
                        return True
                    self.logger.warning(f"Model {self.model_name} not found in Ollama")
                    self.logger.info(f"Install with: ollama pull {self.model_name}")
                    return False

                self.logger.warning("Ollama not responding")
                return False

            except Exception as e:
                self.logger.warning(f"Ollama check failed: {e}")
                self.logger.info("Make sure Ollama is running: ollama serve")
                return False

    def is_configured(self) -> bool:
        """Check if embedding processor is properly configured"""
        return self.ollama_available and self.database_adapter is not None

    def get_configuration_status(self) -> dict[str, Any]:
        """Get detailed configuration status for debugging"""
        return {
            "is_configured": self.is_configured(),
            "ollama_available": self.ollama_available,
            "ollama_url": self.ollama_url,
            "model_name": self.model_name,
            "database_configured": self.database_adapter is not None,
            "embedding_dimension": self.embedding_dimension,
            "batch_size": self.batch_size,
        }

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

    async def process(self, context) -> dict[str, Any]:
        """Async pipeline entrypoint wrapping `process_document`."""
        if not hasattr(context, "document_id"):
            raise ValueError("Processing context must include 'document_id'")

        chunks = getattr(context, "chunks", None)
        if chunks is None:
            chunks = getattr(context, "chunk_data", None)

        if chunks is None:
            # Context carries no chunks (e.g. smart-processing resumption path).
            # Fall back to fetching un-embedded chunks for this document from the DB.
            if self.database_adapter:
                try:
                    rows = await self.database_adapter.execute_query(
                        """
                        SELECT id AS chunk_id, text_chunk AS text, chunk_index, page_start,
                               page_end, metadata
                        FROM krai_intelligence.chunks
                        WHERE document_id = $1::uuid
                          AND embedding IS NULL
                        ORDER BY chunk_index ASC
                        """,
                        [str(context.document_id)],
                    )
                    chunks = rows or []
                    if chunks:
                        self.logger.info(
                            "Loaded %d un-embedded chunks from DB for document %s",
                            len(chunks),
                            context.document_id,
                        )
                    else:
                        self.logger.info(
                            "All chunks already embedded for document %s — nothing to do",
                            context.document_id,
                        )
                        return {
                            "success": True,
                            "embeddings_created": 0,
                            "message": "All chunks already embedded",
                        }
                except Exception as exc:
                    self.logger.error("Failed to load chunks from DB: %s", exc)
                    return {
                        "success": False,
                        "error": f"No chunks in context and DB fetch failed: {exc}",
                        "embeddings_created": 0,
                    }
            else:
                return {
                    "success": False,
                    "error": "No chunks provided for embedding generation",
                    "embeddings_created": 0,
                }

        # Normalize chunk payloads so downstream code can rely on `chunk_id` + `text`.
        normalized_chunks: list[dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            normalized: dict[str, Any]
            if isinstance(chunk, dict):
                normalized = dict(chunk)
            else:
                normalized = {"text": chunk}

            chunk_id = normalized.get("chunk_id") or normalized.get("id")
            if chunk_id is not None:
                normalized["chunk_id"] = chunk_id

            text_value = (
                normalized.get("text")
                or normalized.get("chunk_text")
                or normalized.get("text_chunk")
                or normalized.get("content")
            )
            if text_value is None:
                text_value = ""
            if not isinstance(text_value, str):
                text_value = str(text_value)
            normalized["text"] = text_value
            normalized["_chunk_index"] = idx
            normalized_chunks.append(normalized)

        track_stage = getattr(context, "track_stage", True)

        manufacturer = getattr(context, "manufacturer", None) or getattr(context, "processing_config", {}).get(
            "manufacturer"
        )
        document_type = getattr(context, "document_type", None) or getattr(context, "processing_config", {}).get(
            "document_type"
        )

        with metrics.stage_timer(
            stage=self.stage.value, manufacturer=manufacturer or "unknown", document_type=document_type or "unknown"
        ) as timer:
            try:
                result = await self.process_document(context.document_id, normalized_chunks, track_stage)
            except Exception as exc:
                timer.stop(success=False, error_label=str(exc))
                raise
            else:
                timer.stop(
                    success=bool(result.get("success")),
                    error_label=str(result.get("error")) if result.get("error") else None,
                )

        # After processing text chunks, handle image and table embeddings if available
        if hasattr(context, "image_embeddings") and context.image_embeddings:
            image_result = await self.store_embeddings_batch(
                context.image_embeddings,
                context=context,
                document_id=context.document_id,
            )
            self.logger.info(f"Stored {image_result['success_count']} image embeddings")

        if hasattr(context, "table_embeddings") and context.table_embeddings:
            table_result = await self.store_embeddings_batch(
                context.table_embeddings,
                context=context,
                document_id=context.document_id,
            )
            self.logger.info(f"Stored {table_result['success_count']} table embeddings")

        return result

    async def process_document(
        self,
        document_id: UUID,
        chunks: list[dict[str, Any]],
        track_stage: bool = True,
    ) -> dict[str, Any]:
        """
        Generate embeddings for all chunks in a document

        Args:
            document_id: Document UUID
            chunks: List of chunk dicts with 'text' field

        Returns:
            Dict with processing results
        """
        if not self.is_configured():
            return {"success": False, "error": "Embedding processor not configured", "embeddings_created": 0}

        # Start stage tracking
        stage_tracker = self.stage_tracker if track_stage and self.stage_tracker else None

        if stage_tracker:
            await self.stage_tracker.start_stage(str(document_id), self.stage.value)

        with self.logger_context(document_id=document_id, stage=self.stage) as adapter:
            try:
                adapter.info("Generating embeddings for %d chunks...", len(chunks))
                start_time = time.time()
                total_embedded = 0
                failed_chunks = []

                total_chunks = len(chunks)
                batch_index = 0
                processed_count = 0
                progress_batch_size = max(1, total_chunks // 10) if total_chunks else 1
                total_characters = 0
                total_non_empty_chunks = 0
                total_truncated_chunks = 0

                while processed_count < total_chunks:
                    batch_index += 1
                    current_batch_size = self.batch_size
                    batch = chunks[processed_count : processed_count + current_batch_size]
                    if not batch:
                        break

                    total_batches = max(1, (total_chunks + current_batch_size - 1) // current_batch_size)

                    adapter.debug(
                        "Processing batch %d/%d (%d chunks, size=%d)...",
                        batch_index,
                        total_batches,
                        len(batch),
                        current_batch_size,
                    )

                    batch_start = time.perf_counter()
                    batch_result = await self._embed_batch(batch, document_id)
                    batch_latency = time.perf_counter() - batch_start

                    batch_stats = [text_stats(chunk.get("text", "")) for chunk in batch]
                    batch_total_chars = sum(stat["length"] for stat in batch_stats)
                    batch_non_empty = sum(1 for stat in batch_stats if not stat["empty"])
                    batch_truncated = sum(1 for stat in batch_stats if stat.get("truncated"))
                    total_characters += batch_total_chars
                    total_non_empty_chunks += batch_non_empty
                    total_truncated_chunks += batch_truncated
                    avg_chars = (batch_total_chars / len(batch)) if batch else 0.0

                    adapter.debug(
                        "Batch %d text stats: total_chars=%d avg_chars=%.1f non_empty=%d truncated=%d",
                        batch_index,
                        batch_total_chars,
                        avg_chars,
                        batch_non_empty,
                        batch_truncated,
                    )

                    if batch_latency > 0:
                        self._record_batch_latency(batch_latency)
                        self._adjust_batch_size(batch_latency)

                    failed_count = len(batch_result["failed_chunks"])
                    if failed_count > 0:
                        self._on_batch_errors(failed_count)
                    else:
                        self._on_batch_success()

                    total_embedded += batch_result["success_count"]
                    failed_chunks.extend(batch_result["failed_chunks"])
                    processed_count += len(batch)
                    if (processed_count % progress_batch_size == 0) or (processed_count == total_chunks):
                        adapter.warning(
                            "Embedding progress: %d/%d (%.0f%%)",
                            processed_count,
                            total_chunks,
                            (processed_count / total_chunks) * 100 if total_chunks else 100,
                        )

                    if self.stage_tracker:
                        progress = (processed_count / total_chunks) * 100
                        await self.stage_tracker.update_stage_progress(
                            str(document_id),
                            self.stage.value,
                            progress,
                            metadata={
                                "chunks_embedded": total_embedded,
                                "batch": f"{batch_index}/{total_batches}",
                                "batch_latency": round(batch_latency, 3),
                                "batch_chars": batch_total_chars,
                                "batch_non_empty": batch_non_empty,
                                "batch_truncated": batch_truncated,
                            },
                        )

                processing_time = time.time() - start_time
                chunks_per_second = (total_embedded / processing_time) if processing_time else 0.0

                # Phase 5: Generate context embeddings for media items (NEW!)
                context_embeddings_created = 0
                if self.enable_context_embeddings:
                    try:
                        adapter.info("Generating context embeddings for media items...")
                        context_start = time.time()
                        context_embeddings_created = await self._generate_context_embeddings(
                            document_id=document_id,
                            adapter=adapter,
                        )
                        context_time = time.time() - context_start
                        adapter.info(
                            "Generated %d context embeddings in %.1fs", context_embeddings_created, context_time
                        )
                    except Exception as e:
                        adapter.error("Failed to generate context embeddings: %s", e)
                        # Don't fail the entire embedding stage for context embedding errors

                if stage_tracker:
                    metadata = {
                        "embeddings_created": total_embedded,
                        "context_embeddings_created": context_embeddings_created,
                        "processing_time": round(processing_time, 2),
                        "chunks_per_second": round(chunks_per_second, 2),
                        "failed_chunks": len(failed_chunks),
                        "total_characters": total_characters,
                        "non_empty_chunks": total_non_empty_chunks,
                        "truncated_chunks": total_truncated_chunks,
                    }

                    if total_embedded == 0 and failed_chunks:
                        await stage_tracker.fail_stage(
                            str(document_id), self.stage.value, f"Failed to embed all {len(failed_chunks)} chunks"
                        )
                    else:
                        if failed_chunks:
                            metadata["status"] = "partial"
                        await stage_tracker.complete_stage(str(document_id), self.stage.value, metadata=metadata)

                self.logger.success(
                    "Created %d embeddings in %.1fs (%.1f chunks/s) | total_chars=%d truncated=%d",
                    total_embedded,
                    processing_time,
                    chunks_per_second,
                    total_characters,
                    total_truncated_chunks,
                )

                partial_success = total_embedded > 0 and len(failed_chunks) > 0

                if partial_success:
                    self.logger.warning(
                        f"Embedding generation partial: {total_embedded} succeeded, {len(failed_chunks)} failed"
                    )

                return {
                    "success": total_embedded > 0,
                    "partial_success": partial_success,
                    "embeddings_created": total_embedded,
                    "context_embeddings_created": context_embeddings_created,
                    "error": (
                        f"Failed to embed all {len(failed_chunks)} chunks"
                        if total_embedded == 0 and len(failed_chunks) > 0
                        else None
                    ),
                    "failed_count": len(failed_chunks),
                    "failed_chunks": failed_chunks,
                    "processing_time": processing_time,
                }

            except Exception as e:
                error_msg = f"Embedding generation failed: {e}"
                self.logger.error(error_msg)
                adapter.error("Embedding generation failed: %s", e)

                if self.stage_tracker:
                    await self.stage_tracker.fail_stage(str(document_id), self.stage.value, error_msg)

                return {"success": False, "error": error_msg, "embeddings_created": 0}

    async def _embed_batch(self, chunks: list[dict[str, Any]], document_id: UUID) -> dict[str, Any]:
        """
        Generate embeddings for a batch of chunks (parallel requests to Ollama).
        """
        parallel = int(os.getenv("EMBEDDING_PARALLEL_REQUESTS", "4"))
        semaphore = asyncio.Semaphore(parallel)
        loop = asyncio.get_event_loop()
        success_count = 0
        failed_chunks = []

        async def _embed_one(chunk: dict[str, Any]) -> dict[str, Any]:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            text_value = (
                chunk.get("text") or chunk.get("chunk_text") or chunk.get("text_chunk") or chunk.get("content") or ""
            )
            if not isinstance(text_value, str):
                text_value = str(text_value)

            async with semaphore:
                try:
                    embedding = await loop.run_in_executor(None, self._generate_embedding, text_value)
                except Exception as exc:
                    return {"ok": False, "chunk_id": chunk_id, "error": str(exc)}

            if embedding is None:
                return {"ok": False, "chunk_id": chunk_id, "error": "Failed to generate embedding"}

            try:
                stored = await self._store_embedding(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    embedding=embedding,
                    chunk_data=chunk,
                )
            except Exception as exc:
                return {"ok": False, "chunk_id": chunk_id, "error": str(exc)}

            if stored:
                return {"ok": True, "chunk_id": chunk_id}
            return {"ok": False, "chunk_id": chunk_id, "error": "Failed to store embedding"}

        results = await asyncio.gather(*[_embed_one(c) for c in chunks], return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failed_chunks.append({"chunk_id": None, "error": str(result)})
            elif result.get("ok"):
                success_count += 1
            else:
                failed_chunks.append({"chunk_id": result.get("chunk_id"), "error": result.get("error")})

        return {"success_count": success_count, "failed_chunks": failed_chunks}

    def _generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate embedding for text using Ollama

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None
        """
        max_attempts = max(1, self.max_retries)
        last_error = None
        text_len = len(text or "")
        prompt_limit = self.max_prompt_chars if self.max_prompt_chars > 0 else text_len
        if self.default_prompt_chars > 0:
            prompt_limit = min(prompt_limit, self.default_prompt_chars)
        learned_limit = self._prompt_limit_by_model.get(self.model_name)
        if learned_limit:
            prompt_limit = min(prompt_limit, learned_limit)
        for attempt in range(1, max_attempts + 1):
            try:
                prompt = text
                if prompt and prompt_limit > 0 and len(prompt) > prompt_limit:
                    prompt = prompt[:prompt_limit]
                response = self.session.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": prompt},
                    timeout=self.request_timeout,
                )

                if response.status_code == 200:
                    try:
                        result = response.json()
                    except ValueError as json_error:
                        self.logger.error(
                            "Embedding API returned invalid JSON (attempt %d/%d): %s | body=%s",
                            attempt,
                            max_attempts,
                            json_error,
                            response.text[:200],
                        )
                        last_error = f"invalid_json: {json_error}"
                        return None

                    embedding = result.get("embedding")

                    if embedding and len(embedding) == self.embedding_dimension:
                        if attempt > 1:
                            self.logger.info("Embedding request succeeded after %d retries", attempt - 1)
                        return embedding

                    self.logger.error(
                        "Embedding response missing or malformed 'embedding' field (len=%s) [attempt %d/%d]: %s",
                        len(embedding) if embedding else 0,
                        attempt,
                        max_attempts,
                        str(result)[:200],
                    )
                    last_error = "malformed_embedding"
                    return None

                body_text = response.text or ""
                body_preview = body_text[:500]
                lower_body = body_text.lower()

                if "exceeds the context length" in lower_body:
                    floor = max(1, int(self.prompt_limit_floor))
                    if prompt_limit <= floor:
                        self.logger.error(
                            "Embedding API rejected prompt due to context length even after truncation (prompt_len=%d model=%s body=%s)",
                            len(prompt or ""),
                            self.model_name,
                            body_preview,
                        )
                        last_error = "context_length_exceeded"
                        return None

                    previous_limit = prompt_limit
                    shrink_factor = 0.25 if previous_limit >= 4096 else 0.5
                    new_limit = max(floor, int(previous_limit * shrink_factor) - 64)
                    if new_limit == prompt_limit:
                        new_limit = max(floor, prompt_limit - 1)
                    prompt_limit = new_limit
                    self._update_model_prompt_limit(self.model_name, prompt_limit)

                    self.logger.debug(
                        "Embedding API prompt too long for model context (attempt %d/%d model=%s new_prompt_limit=%d body=%s) - retrying with truncation",
                        attempt,
                        max_attempts,
                        self.model_name,
                        prompt_limit,
                        body_preview,
                    )
                    last_error = "context_length_exceeded"
                    continue

                # Determine if transient
                if response.status_code >= 500:
                    text_length = len(text or "")
                    retry_delay = self.retry_base_delay * (2 ** (attempt - 1))
                    jitter = random.uniform(0, self.retry_jitter)
                    sleep_time = retry_delay + jitter
                    if attempt < max_attempts:
                        self.logger.warning(
                            "Embedding API transient error %s on attempt %d/%d (text_len=%d model=%s body=%s) - retrying in %.2fs",
                            response.status_code,
                            attempt,
                            max_attempts,
                            text_length,
                            self.model_name,
                            body_preview,
                            sleep_time,
                        )
                        time.sleep(sleep_time)
                        last_error = f"status_{response.status_code}"
                        continue
                    last_error = f"status_{response.status_code}"

                else:
                    self.logger.error("Embedding API error %s: %s", response.status_code, response.text[:200])
                    last_error = f"status_{response.status_code}"
                    return None

            except (
                requests_exceptions.ConnectionError,
                requests_exceptions.Timeout,
                requests_exceptions.RetryError,
            ) as exc:
                retry_delay = self.retry_base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, self.retry_jitter)
                sleep_time = retry_delay + jitter
                if attempt < max_attempts:
                    self.logger.warning(
                        "Embedding request connection issue on attempt %d/%d: %s - retrying in %.2fs",
                        attempt,
                        max_attempts,
                        exc,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    last_error = f"connection_error: {exc}"
                    continue
                self.logger.error(
                    "Embedding request failed after %d attempts due to connection issues: %s", max_attempts, exc
                )
                last_error = f"connection_error: {exc}"
                return None
            except Exception as exc:
                self.logger.error("Embedding generation error on attempt %d/%d: %s", attempt, max_attempts, exc)
                last_error = str(exc)
                return None

            # If we reached here due to non-retriable status or after retries exhausted
            break

        self.logger.error(
            "Embedding generation failed after %d attempts%s",
            max_attempts,
            f" (last_error={last_error})" if last_error else "",
        )
        return None

    async def _store_embedding(
        self,
        chunk_id: str,
        document_id: UUID,
        embedding: list[float],
        chunk_data: dict[str, Any],
    ) -> bool:
        """
        Store embedding in krai_intelligence.chunks (embedding column)

        Args:
            chunk_id: Chunk ID
            document_id: Document UUID
            embedding: Embedding vector
            chunk_data: Chunk metadata

        Returns:
            True if successful
        """
        if not self.database_adapter:
            return False

        try:
            # Prepare record for krai_intelligence.chunks table
            # Note: This uses direct PostgreSQL writes (krai_intelligence.chunks)

            # Preserve existing metadata from chunk (includes header metadata, etc.)
            existing_metadata = chunk_data.get("metadata", {})
            if isinstance(existing_metadata, str):
                try:
                    existing_metadata = json.loads(existing_metadata)
                except Exception:
                    existing_metadata = {}
            if not isinstance(existing_metadata, dict):
                existing_metadata = {}

            # Update with required fields (don't overwrite if already exists)
            metadata = {
                "char_count": existing_metadata.get("char_count", len(chunk_data.get("text", ""))),
                "word_count": existing_metadata.get("word_count", len(chunk_data.get("text", "").split())),
                "chunk_type": existing_metadata.get("chunk_type", chunk_data.get("chunk_type", "text")),
                "embedded_at": datetime.now(UTC).isoformat(),
            }

            # Merge with existing metadata (preserve header_metadata, etc.)
            for key, value in existing_metadata.items():
                if key not in metadata:  # Don't overwrite the standard fields
                    metadata[key] = value

            embedding_literal = self._vector_literal(embedding)
            metadata_update = self._make_json_safe(metadata)

            await self.database_adapter.execute_query(
                """
                UPDATE krai_intelligence.chunks
                SET
                    embedding = $2::vector,
                    metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb,
                    updated_at = NOW()
                WHERE id = $1
                """.strip(),
                [str(chunk_id), embedding_literal, json.dumps(metadata_update)],
            )

            await self._store_unified_embedding(
                source_id=str(chunk_id),
                source_type="text",
                embedding=embedding,
                embedding_context=(chunk_data.get("text", "") or "")[:500],
                metadata={
                    "chunk_type": chunk_data.get("chunk_type", "text"),
                    "page_start": chunk_data.get("page_start"),
                    "page_end": chunk_data.get("page_end"),
                    "chunk_index": chunk_data.get("chunk_index", 0),
                    "document_id": str(document_id),
                },
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to store embedding (chunk={chunk_id}): {e}")
            return False

    async def _store_unified_embedding(
        self,
        source_id: str,
        source_type: str,  # 'text', 'image', 'table'
        embedding: list[float],
        embedding_context: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Store embedding in unified_embeddings table for unified multi-modal search

        Args:
            source_id: Source ID (chunk_id, image_id, table_id)
            source_type: Type of source ('text', 'image', 'table')
            document_id: Document UUID
            embedding: Embedding vector
            embedding_context: Context text for the embedding
            metadata: Additional metadata

        Returns:
            True if successful
        """
        if not self.database_adapter:
            return False

        try:
            # Prepare record for unified_embeddings table
            embedding_data = {
                "source_id": source_id,
                "source_type": source_type,
                "model_name": self.model_name,
                "embedding": embedding,  # pgvector will handle this
                "embedding_context": embedding_context[:500] if embedding_context else None,
                "metadata": metadata or {},
            }

            embedding_data = self._make_json_safe(embedding_data)

            embedding_literal = self._vector_literal(embedding)
            await self.database_adapter.execute_query(
                """
                INSERT INTO krai_intelligence.unified_embeddings
                    (source_id, source_type, embedding, model_name, embedding_context, metadata)
                VALUES
                    ($1::uuid, $2, $3::vector, $4, $5, $6::jsonb)
                """.strip(),
                [
                    str(source_id),
                    source_type,
                    embedding_literal,
                    self.model_name,
                    embedding_context[:500] if embedding_context else None,
                    json.dumps(embedding_data.get("metadata") or {}),
                ],
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to store unified embedding ({source_type}={source_id}): {e}")
            return False

    async def store_embeddings_batch(
        self,
        embeddings: list[dict[str, Any]],
        *,
        context: Any | None = None,
        document_id: Any | None = None,
    ) -> dict[str, Any]:
        """
        Store batch of embeddings (text, image, table) in unified_embeddings

        Args:
            embeddings: List of embedding dictionaries with keys:
                - source_id: Source ID
                - source_type: Type ('text', 'image', 'table')
                - embedding: Embedding vector
                - embedding_context: Context text
                - metadata: Additional metadata

        Returns:
            Dict with success_count, failed_count
        """
        if not self.database_adapter:
            return {"success_count": 0, "failed_count": len(embeddings)}

        success_count = 0
        failed_count = 0
        embeddings_created = 0
        errors = []

        try:
            for emb_data in embeddings:
                try:
                    # Validate source_type
                    source_type = emb_data.get("source_type")
                    if source_type not in ["text", "image", "table", "context"]:
                        self.logger.warning(f"Invalid source_type: {source_type}")
                        failed_count += 1
                        continue

                    # Store embedding
                    success = await self._store_unified_embedding(
                        source_id=str(emb_data["source_id"]),
                        source_type=emb_data["source_type"],
                        embedding=emb_data["embedding"],
                        embedding_context=emb_data.get("embedding_context"),
                        metadata=emb_data.get("metadata"),
                    )

                    if success:
                        success_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    self.logger.error(f"Failed to store batch embedding: {e}")
                    failed_count += 1

            # Process image embeddings if available (from VisualEmbeddingProcessor)
            # Note: This is currently disabled as VisualEmbeddingProcessor stores embeddings directly
            # If you want EmbeddingProcessor to handle image embeddings, set ENABLE_IMAGE_EMBEDDINGS_HANDLING=true
            if (
                os.getenv("ENABLE_IMAGE_EMBEDDINGS_HANDLING", "false").lower() == "true"
                and hasattr(context, "image_embeddings")
                and context.image_embeddings
                and document_id is not None
            ):
                self.logger.info(f"Processing {len(context.image_embeddings)} image embeddings")
                for img_emb in context.image_embeddings:
                    try:
                        await self._store_image_embedding(
                            img_emb["id"], img_emb["embedding"], img_emb.get("metadata", {}), document_id
                        )
                        embeddings_created += 1
                    except Exception as e:
                        self.logger.error(f"Failed to store image embedding: {e}")
                        errors.append(f"Image embedding storage failed: {e}")

            # Process table embeddings if available (from TableProcessor)
            # Note: This is currently disabled as TableProcessor stores embeddings directly
            # If you want EmbeddingProcessor to handle table embeddings, set ENABLE_TABLE_EMBEDDINGS_HANDLING=true
            if (
                os.getenv("ENABLE_TABLE_EMBEDDINGS_HANDLING", "false").lower() == "true"
                and hasattr(context, "table_embeddings")
                and context.table_embeddings
                and document_id is not None
            ):
                self.logger.info(f"Processing {len(context.table_embeddings)} table embeddings")
                for table_emb in context.table_embeddings:
                    try:
                        await self._store_table_embedding(
                            table_emb["id"], table_emb["embedding"], table_emb.get("metadata", {}), document_id
                        )
                        embeddings_created += 1
                    except Exception as e:
                        self.logger.error(f"Failed to store table embedding: {e}")
                        errors.append(f"Table embedding storage failed: {e}")

            self.logger.info(f"Batch embedding storage: {success_count} success, {failed_count} failed")
            return {"success_count": success_count, "failed_count": failed_count}

        except Exception as e:
            self.logger.error(f"Batch embedding storage failed: {e}")
            return {"success_count": success_count, "failed_count": len(embeddings)}

    def search_similar(
        self,
        query_text: str,
        limit: int = 10,
        document_id: UUID | None = None,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search for similar chunks using vector similarity

        Args:
            query_text: Search query
            limit: Number of results to return
            document_id: Optional filter by document
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of similar chunks with scores
        """
        if not self.is_configured():
            self.logger.warning("Search not available - processor not configured")
            return []

        try:
            # Generate embedding for query
            query_embedding = self._generate_embedding(query_text)

            if query_embedding is None:
                self.logger.error("Failed to generate query embedding")
                return []

            self.logger.warning("Similarity search is not available in sync mode")
            return []

        except Exception as e:
            self.logger.error(f"Similarity search failed: {e}")
            return []

    async def _generate_context_embeddings(self, document_id: UUID, adapter) -> int:
        """
        Generate embeddings for context fields of media items (images, videos, links).

        Args:
            document_id: Document UUID
            adapter: Logger adapter

        Returns:
            Number of context embeddings created
        """
        if not self.database_adapter:
            adapter.debug("Context embeddings unavailable - skipping")
            return 0

        total_context_embeddings = 0

        try:
            images_result = await self.database_adapter.execute_query(
                """
                SELECT id, context_caption, page_header, related_error_codes, related_products, surrounding_paragraphs
                FROM krai_content.images
                WHERE document_id = $1 AND context_caption IS NOT NULL
                """.strip(),
                [str(document_id)],
            )

            if images_result:
                adapter.info(f"Processing {len(images_result)} images with context")
                image_embeddings = []

                for image in images_result:
                    # Combine context fields for embedding
                    context_parts = []

                    if image.get("context_caption"):
                        context_parts.append(image["context_caption"])
                    if image.get("page_header"):
                        context_parts.append(image["page_header"])
                    if image.get("figure_reference"):
                        context_parts.append(image["figure_reference"])

                    # Add related entities
                    if image.get("related_error_codes"):
                        context_parts.extend([f"Error: {code}" for code in image["related_error_codes"]])
                    if image.get("related_products"):
                        context_parts.extend([f"Product: {product}" for product in image["related_products"]])
                    if image.get("surrounding_paragraphs"):
                        context_parts.extend(image["surrounding_paragraphs"])

                    if context_parts:
                        context_text = " | ".join(context_parts)

                        # Generate embedding
                        embedding = self._generate_embedding(context_text)
                        if embedding:
                            image_embeddings.append(
                                {
                                    "source_id": image["id"],
                                    "source_type": "context",
                                    "embedding": embedding,
                                    "embedding_context": context_text,
                                    "metadata": {
                                        "media_type": "image",
                                        "media_id": image["id"],
                                        "document_id": str(document_id),
                                    },
                                }
                            )

                # Store image context embeddings
                if image_embeddings:
                    result = await self.store_embeddings_batch(
                        image_embeddings,
                        document_id=document_id,
                    )
                    total_context_embeddings += result.get("success_count", 0)
                    adapter.info(f"Stored {result.get('success_count', 0)} image context embeddings")

            videos_result = await self.database_adapter.execute_query(
                """
                SELECT id, context_description, related_products
                FROM krai_content.videos
                WHERE document_id = $1 AND context_description IS NOT NULL
                """.strip(),
                [str(document_id)],
            )

            if videos_result:
                adapter.info(f"Processing {len(videos_result)} videos with context")
                video_embeddings = []

                for video in videos_result:
                    context_parts = []

                    if video.get("context_description"):
                        context_parts.append(video["context_description"])
                    if video.get("page_header"):
                        context_parts.append(video["page_header"])

                    if video.get("related_error_codes"):
                        context_parts.extend([f"Error: {code}" for code in video["related_error_codes"]])
                    if video.get("related_products"):
                        context_parts.extend([f"Product: {product}" for product in video["related_products"]])

                    if context_parts:
                        context_text = " | ".join(context_parts)

                        embedding = self._generate_embedding(context_text)
                        if embedding:
                            video_embeddings.append(
                                {
                                    "source_id": video["id"],
                                    "source_type": "context",
                                    "embedding": embedding,
                                    "embedding_context": context_text,
                                    "metadata": {
                                        "media_type": "video",
                                        "media_id": video["id"],
                                        "document_id": str(document_id),
                                    },
                                }
                            )

                if video_embeddings:
                    result = await self.store_embeddings_batch(
                        video_embeddings,
                        document_id=document_id,
                    )
                    total_context_embeddings += result.get("success_count", 0)
                    adapter.info(f"Stored {result.get('success_count', 0)} video context embeddings")

            links_result = await self.database_adapter.execute_query(
                """
                SELECT id, context_description, related_error_codes
                FROM krai_content.links
                WHERE document_id = $1 AND context_description IS NOT NULL
                """.strip(),
                [str(document_id)],
            )

            if links_result:
                adapter.info(f"Processing {len(links_result)} links with context")
                link_embeddings = []

                for link in links_result:
                    context_parts = []

                    if link.get("context_description"):
                        context_parts.append(link["context_description"])
                    if link.get("page_header"):
                        context_parts.append(link["page_header"])

                    if link.get("related_error_codes"):
                        context_parts.extend([f"Error: {code}" for code in link["related_error_codes"]])
                    if link.get("related_products"):
                        context_parts.extend([f"Product: {product}" for product in link["related_products"]])

                    if context_parts:
                        context_text = " | ".join(context_parts)

                        embedding = self._generate_embedding(context_text)
                        if embedding:
                            link_embeddings.append(
                                {
                                    "source_id": link["id"],
                                    "source_type": "context",
                                    "embedding": embedding,
                                    "embedding_context": context_text,
                                    "metadata": {
                                        "media_type": "link",
                                        "media_id": link["id"],
                                        "document_id": str(document_id),
                                    },
                                }
                            )

                if link_embeddings:
                    result = await self.store_embeddings_batch(
                        link_embeddings,
                        document_id=document_id,
                    )
                    total_context_embeddings += result.get("success_count", 0)
                    adapter.info(f"Stored {result.get('success_count', 0)} link context embeddings")

            try:
                tables_result = await self.database_adapter.execute_query(
                    """
                    SELECT id, context_text, caption, metadata
                    FROM krai_intelligence.structured_tables
                    WHERE document_id = $1 AND context_text IS NOT NULL
                    """.strip(),
                    [str(document_id)],
                )
            except Exception as table_query_error:
                adapter.debug(
                    "structured_tables context columns unavailable, using fallback query: %s",
                    table_query_error,
                )
                tables_result = await self.database_adapter.execute_query(
                    """
                    SELECT id, table_markdown, metadata
                    FROM krai_intelligence.structured_tables
                    WHERE document_id = $1
                    """.strip(),
                    [str(document_id)],
                )

            if tables_result:
                adapter.info(f"Processing {len(tables_result)} tables with context")
                table_embeddings = []

                for table in tables_result:
                    # Combine context fields for embedding
                    context_parts = []

                    metadata = table.get("metadata")
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    if not isinstance(metadata, dict):
                        metadata = {}

                    context_text_field = table.get("context_text") or metadata.get("context_text")
                    caption_field = table.get("caption") or metadata.get("caption")
                    page_header_field = table.get("page_header") or metadata.get("page_header")
                    markdown_field = table.get("table_markdown")

                    if context_text_field:
                        context_parts.append(context_text_field)
                    if caption_field:
                        context_parts.append(caption_field)
                    if page_header_field:
                        context_parts.append(page_header_field)
                    if markdown_field:
                        context_parts.append(markdown_field)

                    if context_parts:
                        context_text = " | ".join(context_parts)

                        # Generate embedding
                        embedding = self._generate_embedding(context_text)
                        if embedding:
                            table_embeddings.append(
                                {
                                    "source_id": table["id"],
                                    "source_type": "context",
                                    "embedding": embedding,
                                    "embedding_context": context_text,
                                    "metadata": {
                                        "media_type": "table",
                                        "media_id": table["id"],
                                        "document_id": str(document_id),
                                    },
                                }
                            )

                # Store table context embeddings
                if table_embeddings:
                    result = await self.store_embeddings_batch(
                        table_embeddings,
                        document_id=document_id,
                    )
                    total_context_embeddings += result.get("success_count", 0)
                    adapter.info(f"Stored {result.get('success_count', 0)} table context embeddings")

            return total_context_embeddings

        except Exception as e:
            adapter.error(f"Failed to generate context embeddings: {e}")
            return 0


# Example usage
if __name__ == "__main__":
    processor = EmbeddingProcessor()

    if processor.is_configured():
        print("✅ Embedding Processor configured")
        print(f"   Model: {processor.model_name}")
        print(f"   Dimension: {processor.embedding_dimension}")
        print(f"   Batch size: {processor.batch_size}")

        # Test embedding
        test_text = "This is a test sentence for embedding generation."
        embedding = processor._generate_embedding(test_text)

        if embedding:
            print("\n✅ Test embedding generated!")
            print(f"   Dimension: {len(embedding)}")
            print(f"   Sample values: {embedding[:5]}...")
        else:
            print("\n❌ Test embedding failed")
    else:
        print("⚠️  Embedding Processor not configured")
        print("\nRequirements:")
        print("  1. Ollama running: ollama serve")
        print("  2. Model installed: ollama pull embeddinggemma")
        print("  3. Database adapter configured")
