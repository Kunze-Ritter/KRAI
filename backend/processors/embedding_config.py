"""Embedding Configuration Module

Configuration, session management, batch persistence, and constants
for embedding processor. Separated for better maintainability.
"""

import json
import os
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_EMBEDDING_DIMENSION = 768
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "nomic-embed-text:latest"


def load_embedding_config(
    ollama_url: str | None = None,
    model_name: str | None = None,
    batch_size: int = 100,
    embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    min_batch_size: int = 25,
    max_batch_size: int = 200,
) -> dict[str, Any]:
    """Load embedding processor configuration from environment."""

    return {
        "ollama_url": ollama_url or os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        "model_name": model_name or os.getenv("OLLAMA_MODEL_EMBEDDING", DEFAULT_MODEL),
        "embedding_dimension": embedding_dimension,
        "batch_size": batch_size,
        "min_batch_size": min_batch_size,
        "max_batch_size": max_batch_size,
        "request_timeout": float(os.getenv("EMBEDDING_REQUEST_TIMEOUT", "30")),
        "max_retries": int(os.getenv("EMBEDDING_REQUEST_MAX_RETRIES", "4")),
        "retry_base_delay": float(os.getenv("EMBEDDING_RETRY_BASE_DELAY", "1.0")),
        "retry_jitter": float(os.getenv("EMBEDDING_RETRY_JITTER", "0.5")),
        "target_latency_lower": float(os.getenv("EMBEDDING_TARGET_LATENCY_LOWER", "1.0")),
        "target_latency_upper": float(os.getenv("EMBEDDING_TARGET_LATENCY_UPPER", "2.0")),
        "enable_context_embeddings": os.getenv("ENABLE_CONTEXT_EMBEDDINGS", "true").lower() == "true",
    }


def create_embedding_session(
    max_retries: int = 4,
    retry_base_delay: float = 1.0,
) -> requests.Session:
    """Create a persistent HTTP session with retry-aware adapter."""
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
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=int(os.getenv("EMBEDDING_HTTP_POOL_CONNECTIONS", "10")),
        pool_maxsize=int(os.getenv("EMBEDDING_HTTP_POOL_MAXSIZE", "20")),
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class BatchStateManager:
    """Manages adaptive batch size persistence."""

    def __init__(
        self,
        node_id: str,
        batch_size: int,
        min_batch_size: int = 25,
        max_batch_size: int = 200,
        batch_adjust_step: int = 10,
    ):
        self.node_id = node_id
        self.batch_size = batch_size
        self.min_batch_size = max(1, min_batch_size)
        self.max_batch_size = max(self.min_batch_size, max_batch_size)
        self.batch_adjust_step = max(1, batch_adjust_step)
        self._batch_latency_window: deque = deque(maxlen=50)
        self._consecutive_error_batches = 0
        self._consecutive_successful_batches = 0
        self._error_recovery_threshold = int(os.getenv("EMBEDDING_ERROR_RECOVERY_THRESHOLD", "5"))

        state_path_env = os.getenv("EMBEDDING_BATCH_STATE_PATH")
        default_state_dir = Path(os.getenv("KRAI_STATE_DIR", Path.cwd() / "state"))
        default_state_dir.mkdir(parents=True, exist_ok=True)
        self.batch_state_path = (
            Path(state_path_env) if state_path_env else default_state_dir / "embedding_batch_state.json"
        )

    def load_persisted(self) -> None:
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
        except Exception:
            pass  # Silently fail - will use defaults

    def persist(self) -> None:
        """Persist current batch size to disk for warm starts."""
        try:
            state = {}
            if self.batch_state_path.exists():
                with self.batch_state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
            state[self.node_id] = {"batch_size": self.batch_size, "updated_at": datetime.now(UTC).isoformat()}
            with self.batch_state_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass  # Silently fail

    def record_latency(self, latency: float) -> None:
        """Track recent batch latencies for adaptive scaling."""
        self._batch_latency_window.append(latency)

    def adjust_batch_size(self, latency: float) -> None:
        """Adjust batch size based on observed latency."""

        target_lower = float(os.getenv("EMBEDDING_TARGET_LATENCY_LOWER", "1.0"))
        target_upper = float(os.getenv("EMBEDDING_TARGET_LATENCY_UPPER", "2.0"))

        if latency < target_lower and self.batch_size < self.max_batch_size:
            new_size = min(self.max_batch_size, self.batch_size + self.batch_adjust_step)
            if new_size != self.batch_size:
                self.batch_size = new_size
                self.persist()
        elif latency > target_upper and self.batch_size > self.min_batch_size:
            new_size = max(self.min_batch_size, self.batch_size - self.batch_adjust_step)
            if new_size != self.batch_size:
                self.batch_size = new_size
                self.persist()


class PromptLimitManager:
    """Manages prompt limit persistence per model."""

    def __init__(self, node_id: str, prompt_limit_floor: int = 512):
        self.node_id = node_id
        self.prompt_limit_floor = prompt_limit_floor
        self._prompt_limit_by_model: dict[str, int] = {}

        prompt_state_path_env = os.getenv("EMBEDDING_PROMPT_LIMIT_STATE_PATH")
        default_state_dir = Path(os.getenv("KRAI_STATE_DIR", Path.cwd() / "state"))
        self.prompt_limit_state_path = (
            Path(prompt_state_path_env)
            if prompt_state_path_env
            else default_state_dir / "embedding_prompt_limit_state.json"
        )

    def load_persisted(self) -> None:
        """Load persisted prompt limits."""
        try:
            if self.prompt_limit_state_path.exists():
                with self.prompt_limit_state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                models = state.get("models") if isinstance(state, dict) else None
                if isinstance(models, dict):
                    self._prompt_limit_by_model = {
                        str(k): int(v) for k, v in models.items() if v is not None and str(v).isdigit() and int(v) > 0
                    }
        except Exception:
            pass

    def persist(self) -> None:
        """Persist prompt limits."""
        try:
            payload = {
                "models": self._prompt_limit_by_model,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            with self.prompt_limit_state_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def update_limit(self, model_name: str, new_limit: int) -> None:
        """Update prompt limit for a model."""
        try:
            new_limit_int = int(new_limit)
        except (TypeError, ValueError):
            return

        if new_limit_int <= 0:
            return

        current = self._prompt_limit_by_model.get(model_name)
        if current is None or new_limit_int < current:
            self._prompt_limit_by_model[model_name] = new_limit_int
            self.persist()
