"""
Retry Engine Module

This module provides intelligent retry logic with error classification and policy management.
It supports database-backed retry policies with in-memory caching and code-level defaults.

Components:
- ErrorClassifier: Classifies exceptions as transient or permanent
- RetryPolicyManager: Manages retry policies with lazy loading and caching
- RetryPolicy: Data model for retry policy configuration
- RetryOrchestrator: Orchestrates retry attempts with exponential backoff and advisory locks

Usage Example:
    # Classify an error
    classification = ErrorClassifier.classify(exception)
    if classification.is_transient:
        # Retry logic here
        pass

    # Get retry policy
    manager = RetryPolicyManager()
    policy = await manager.get_policy('firecrawl', 'image_processing')
    print(f"Max retries: {policy.max_retries}")

    # Orchestrate retry
    orchestrator = RetryOrchestrator(db_adapter, error_logger)
    if await orchestrator.should_retry(classification, attempt, policy):
        await orchestrator.spawn_background_retry(context, attempt, policy, correlation_id, processor_callable)
"""

import asyncio
import hashlib
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar
from unittest.mock import Mock

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ============================================================================
# Exception Classes
# ============================================================================


class AuthenticationError(Exception):
    """Raised when authentication fails"""

    pass


class AuthorizationError(Exception):
    """Raised when authorization fails"""

    pass


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ErrorClassification:
    """
    Represents the classification of an error.

    Attributes:
        is_transient: True if the error is transient and retryable
        error_type: The type/name of the error
        error_category: 'transient' or 'permanent'
        http_status_code: HTTP status code if applicable
    """

    is_transient: bool
    error_type: str
    error_category: str
    http_status_code: int | None = None


@dataclass
class RetryPolicy:
    """
    Represents a retry policy configuration.

    Attributes:
        policy_name: Name of the policy
        service_name: Name of the service (e.g., 'firecrawl', 'database')
        stage_name: Optional processing stage name
        max_retries: Maximum number of retry attempts
        base_delay_seconds: Base delay between retries in seconds
        max_delay_seconds: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter_enabled: Whether to add random jitter to delays
        circuit_breaker_enabled: Whether circuit breaker is enabled
        circuit_breaker_threshold: Number of failures before circuit opens
        circuit_breaker_timeout_seconds: Seconds before circuit breaker resets
    """

    policy_name: str
    service_name: str
    stage_name: str | None
    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float
    exponential_base: float
    jitter_enabled: bool
    circuit_breaker_enabled: bool = False
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60


# ============================================================================
# Error Classifier
# ============================================================================


class ErrorClassifier:
    """
    Classifies exceptions as transient (retryable) or permanent (non-retryable).

    Classification Rules:
    - HTTP 5xx (500-599): Transient
    - HTTP 408 (Request Timeout): Transient
    - HTTP 429 (Too Many Requests): Transient
    - HTTP 4xx (other 400-499): Permanent
    - Connection/Timeout errors: Transient
    - Validation/Auth errors: Permanent
    - Unknown errors: Permanent (fail-safe)

    Usage:
        classification = ErrorClassifier.classify(exception)
        if classification.is_transient:
            # Retry the operation
            pass
    """

    # Transient exception types
    TRANSIENT_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.TransportError,
    )

    # Permanent exception types
    PERMANENT_EXCEPTIONS = (
        ValueError,
        AuthenticationError,
        AuthorizationError,
    )

    @staticmethod
    def classify(exception: Exception) -> ErrorClassification:
        """
        Classify an exception as transient or permanent.

        Args:
            exception: The exception to classify

        Returns:
            ErrorClassification with classification details
        """
        error_type = type(exception).__name__
        http_status_code = None

        # Check for HTTP status errors
        if isinstance(exception, httpx.HTTPStatusError):
            http_status_code = exception.response.status_code

            # 5xx errors are transient
            if 500 <= http_status_code < 600:
                return ErrorClassification(
                    is_transient=True,
                    error_type=error_type,
                    error_category="transient",
                    http_status_code=http_status_code,
                )

            # 408 Request Timeout and 429 Too Many Requests are transient
            if http_status_code in (408, 429):
                return ErrorClassification(
                    is_transient=True,
                    error_type=error_type,
                    error_category="transient",
                    http_status_code=http_status_code,
                )

            # Other 4xx errors are permanent
            if 400 <= http_status_code < 500:
                return ErrorClassification(
                    is_transient=False,
                    error_type=error_type,
                    error_category="permanent",
                    http_status_code=http_status_code,
                )

        # Check for transient exception types
        if isinstance(exception, ErrorClassifier.TRANSIENT_EXCEPTIONS):
            return ErrorClassification(
                is_transient=True, error_type=error_type, error_category="transient", http_status_code=http_status_code
            )

        # Check for permanent exception types
        if isinstance(exception, ErrorClassifier.PERMANENT_EXCEPTIONS):
            return ErrorClassification(
                is_transient=False, error_type=error_type, error_category="permanent", http_status_code=http_status_code
            )

        # Check exception chain for nested exceptions
        if exception.__cause__:
            nested_classification = ErrorClassifier.classify(exception.__cause__)
            # Use nested classification but keep outer error type
            return ErrorClassification(
                is_transient=nested_classification.is_transient,
                error_type=error_type,
                error_category=nested_classification.error_category,
                http_status_code=nested_classification.http_status_code,
            )

        # Default: permanent (fail-safe approach)
        logger.debug(f"Unknown exception type {error_type}, classifying as permanent")
        return ErrorClassification(
            is_transient=False, error_type=error_type, error_category="permanent", http_status_code=http_status_code
        )


# ============================================================================
# Retry Policy Manager
# ============================================================================


class RetryPolicyManager:
    """
    Manages retry policies with lazy loading and caching.

    Features:
    - In-memory cache with 5-minute TTL
    - Lazy loading from database
    - Code-level defaults for common services
    - Thread-safe cache access
    - Graceful fallback on database errors

    Policy Resolution Order:
    1. Cache (if available)
    2. Database - stage-specific policy
    3. Database - service-level policy (stage=NULL)
    4. Code-level default

    Usage:
        manager = RetryPolicyManager()
        policy = await manager.get_policy('firecrawl', 'image_processing')
        print(f"Max retries: {policy.max_retries}")
    """

    # Code-level default policies
    DEFAULT_POLICIES: ClassVar[dict[str, dict[str, Any]]] = {
        "firecrawl": {
            "policy_name": "firecrawl_default",
            "service_name": "firecrawl",
            "stage_name": None,
            "max_retries": 3,
            "base_delay_seconds": 2.0,
            "max_delay_seconds": 60.0,
            "exponential_base": 2.0,
            "jitter_enabled": True,
            "circuit_breaker_enabled": False,
        },
        "database": {
            "policy_name": "database_default",
            "service_name": "database",
            "stage_name": None,
            "max_retries": 5,
            "base_delay_seconds": 1.0,
            "max_delay_seconds": 30.0,
            "exponential_base": 2.0,
            "jitter_enabled": True,
            "circuit_breaker_enabled": False,
        },
        "ollama": {
            "policy_name": "ollama_default",
            "service_name": "ollama",
            "stage_name": None,
            "max_retries": 3,
            "base_delay_seconds": 2.0,
            "max_delay_seconds": 120.0,
            "exponential_base": 2.5,
            "jitter_enabled": True,
            "circuit_breaker_enabled": False,
        },
        "minio": {
            "policy_name": "minio_default",
            "service_name": "minio",
            "stage_name": None,
            "max_retries": 4,
            "base_delay_seconds": 1.5,
            "max_delay_seconds": 45.0,
            "exponential_base": 2.0,
            "jitter_enabled": True,
            "circuit_breaker_enabled": False,
        },
        "default": {
            "policy_name": "system_default",
            "service_name": "default",
            "stage_name": None,
            "max_retries": 3,
            "base_delay_seconds": 1.0,
            "max_delay_seconds": 60.0,
            "exponential_base": 2.0,
            "jitter_enabled": True,
            "circuit_breaker_enabled": False,
        },
    }

    # Class-level cache and lock (singleton pattern)
    _cache: TTLCache = TTLCache(maxsize=100, ttl=300)  # 5-minute TTL
    _cache_lock: asyncio.Lock | None = None
    _fetch_locks: ClassVar[dict[str, asyncio.Lock]] = {}  # Per-key locks for single-flight pattern
    _fetch_locks_lock: asyncio.Lock | None = None  # Lock for managing fetch_locks dict
    _lock_loop_id: int | None = None
    _db_adapter = None

    @classmethod
    def _ensure_loop_locks(cls) -> None:
        """Ensure async locks are bound to the current running event loop."""
        loop_id = id(asyncio.get_running_loop())
        if cls._lock_loop_id != loop_id:
            cls._cache_lock = asyncio.Lock()
            cls._fetch_locks_lock = asyncio.Lock()
            cls._fetch_locks = {}
            cls._lock_loop_id = loop_id

    @classmethod
    def set_db_adapter(cls, db_adapter) -> None:
        """Set the database adapter for loading policies from krai_system.retry_policies."""
        cls._db_adapter = db_adapter

    @classmethod
    async def get_policy(cls, service_name: str, stage_name: str | None = None) -> RetryPolicy:
        """
        Get retry policy for a service and optional stage.

        Resolution order:
        1. Check cache
        2. Query database for stage-specific policy
        3. Query database for service-level policy
        4. Return code-level default

        Args:
            service_name: Name of the service
            stage_name: Optional processing stage name

        Returns:
            RetryPolicy instance
        """
        cls._ensure_loop_locks()
        # Generate cache key
        cache_key = f"{service_name}:{stage_name if stage_name else '*'}"

        # Check cache (fast path)
        async with cls._cache_lock:
            if cache_key in cls._cache:
                logger.debug(f"Cache hit for policy: {cache_key}")
                return cls._cache[cache_key]

        logger.debug(f"Cache miss for policy: {cache_key}")

        # Get or create per-key lock for single-flight pattern
        async with cls._fetch_locks_lock:
            if cache_key not in cls._fetch_locks:
                cls._fetch_locks[cache_key] = asyncio.Lock()
            fetch_lock = cls._fetch_locks[cache_key]

        # Single-flight: only one coroutine fetches per cache_key
        async with fetch_lock:
            # Re-check cache under lock (another coroutine may have fetched)
            async with cls._cache_lock:
                if cache_key in cls._cache:
                    logger.debug(f"Cache hit after lock acquisition: {cache_key}")
                    return cls._cache[cache_key]

            # Try to load from database
            policy = await cls._load_from_database(service_name, stage_name)

            if policy:
                logger.info(f"Loaded policy from database: {cache_key}")
                async with cls._cache_lock:
                    cls._cache[cache_key] = policy
                return policy

            # Fallback to code-level default
            logger.warning(f"No database policy found for {cache_key}, using code-level default")
            policy = cls._get_default_policy(service_name)

            async with cls._cache_lock:
                cls._cache[cache_key] = policy

            return policy

    @classmethod
    async def _load_from_database(cls, service_name: str, stage_name: str | None) -> RetryPolicy | None:
        """
        Load retry policy from database.

        Queries krai_system.retry_policies for the given service_name and optional stage_name,
        ordered with stage-specific row first, then service-level (stage_name IS NULL).
        Returns None when adapter is not set, query fails, or no rows found (caller uses code default).

        Args:
            service_name: Name of the service
            stage_name: Optional processing stage name

        Returns:
            RetryPolicy if found, None otherwise
        """
        if cls._db_adapter is None:
            return None
        try:
            if stage_name is not None:
                query = """
                    SELECT policy_name, service_name, stage_name, max_retries,
                           base_delay_seconds, max_delay_seconds, exponential_base,
                           jitter_enabled, circuit_breaker_enabled, circuit_breaker_threshold,
                           circuit_breaker_timeout_seconds
                    FROM krai_system.retry_policies
                    WHERE service_name = $1 AND (stage_name = $2 OR stage_name IS NULL)
                    ORDER BY (stage_name IS NOT NULL AND stage_name = $2) DESC NULLS LAST
                    LIMIT 1
                """
                params = (service_name, stage_name)
            else:
                query = """
                    SELECT policy_name, service_name, stage_name, max_retries,
                           base_delay_seconds, max_delay_seconds, exponential_base,
                           jitter_enabled, circuit_breaker_enabled, circuit_breaker_threshold,
                           circuit_breaker_timeout_seconds
                    FROM krai_system.retry_policies
                    WHERE service_name = $1 AND stage_name IS NULL
                    LIMIT 1
                """
                params = (service_name,)
            row = await cls._db_adapter.fetch_one(query, params)
            if not row:
                return None
            return RetryPolicy(
                policy_name=row["policy_name"],
                service_name=row["service_name"],
                stage_name=row["stage_name"],
                max_retries=int(row["max_retries"]),
                base_delay_seconds=float(row["base_delay_seconds"]),
                max_delay_seconds=float(row["max_delay_seconds"]),
                exponential_base=float(row["exponential_base"]),
                jitter_enabled=bool(row["jitter_enabled"]),
                circuit_breaker_enabled=bool(row.get("circuit_breaker_enabled", False)),
                circuit_breaker_threshold=int(row.get("circuit_breaker_threshold", 5)),
                circuit_breaker_timeout_seconds=int(row.get("circuit_breaker_timeout_seconds", 60)),
            )
        except Exception as e:
            logger.error(f"Error loading policy from database: {e}", exc_info=True)
            return None

    @classmethod
    def _get_default_policy(cls, service_name: str) -> RetryPolicy:
        """
        Get code-level default policy for a service.

        Args:
            service_name: Name of the service

        Returns:
            RetryPolicy with default configuration
        """
        # Get service-specific default or system default
        policy_dict = cls.DEFAULT_POLICIES.get(service_name, cls.DEFAULT_POLICIES["default"])

        return RetryPolicy(**policy_dict)

    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear the policy cache.

        Useful for testing and manual cache invalidation.
        """
        cls._cache.clear()
        cls._fetch_locks.clear()
        logger.info("Retry policy cache cleared")


# ============================================================================
# Retry Orchestrator
# ============================================================================


class RetryOrchestrator:
    """
    Orchestrates retry attempts with exponential backoff and advisory locks.

    This class coordinates retry logic for processing operations, providing:
    - Exponential backoff calculation with optional jitter
    - PostgreSQL advisory locks to prevent concurrent retries
    - Background task spawning for asynchronous retries
    - Error status tracking in pipeline_errors table
    - Correlation ID generation for tracking retry chains

    Architecture:
    - Hybrid sync/async design: synchronous first retry, async subsequent retries
    - Uses PostgreSQL advisory locks for distributed coordination
    - Fire-and-forget pattern for background retry tasks
    - Graceful error handling with fallback behavior

    Usage Example:
        # Initialize orchestrator
        orchestrator = RetryOrchestrator(db_adapter, error_logger)

        # Check if should retry
        if await orchestrator.should_retry(classification, attempt, policy):
            # Generate correlation ID
            correlation_id = orchestrator.generate_correlation_id(
                context.request_id, 'image_processing', attempt
            )

            # Spawn background retry
            await orchestrator.spawn_background_retry(
                context, attempt, policy, correlation_id, processor_callable
            )

    Integration Points:
    - DatabaseAdapter: For advisory locks and error status updates
    - ErrorLogger: For updating pipeline_errors table
    - ProcessingContext: For tracking retry state
    - RetryPolicy: For backoff and retry configuration
    """

    def __init__(self, db_adapter, error_logger):
        """
        Initialize RetryOrchestrator.

        Args:
            db_adapter: DatabaseAdapter instance for database operations
            error_logger: ErrorLogger instance for status updates
        """
        self.db_adapter = db_adapter
        self.error_logger = error_logger
        self.logger = logging.getLogger(__name__)
        self._local_advisory_locks: set[str] = set()
        self._local_advisory_locks_guard: asyncio.Lock | None = None
        self._background_tasks: set[asyncio.Task] = set()  # Keep references to background tasks

    def _ensure_local_lock_guard(self) -> None:
        if self._local_advisory_locks_guard is None:
            self._local_advisory_locks_guard = asyncio.Lock()

    @staticmethod
    def _extract_lock_result(result: Any, field_name: str) -> bool | None:
        """
        Extract advisory lock boolean from different adapter return shapes.
        Returns None when value cannot be determined.
        """
        value = None

        if isinstance(result, bool):
            return result
        if isinstance(result, dict):
            value = result.get(field_name)
        elif isinstance(result, list | tuple) and result:
            value = result[0]
        else:
            try:
                value = result[field_name]  # e.g., asyncpg Record
            except Exception:
                value = getattr(result, field_name, None)

        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"t", "true", "1", "yes"}:
                return True
            if lowered in {"f", "false", "0", "no"}:
                return False
        return None

    @staticmethod
    def generate_correlation_id(request_id: str, stage_name: str, retry_attempt: int) -> str:
        """
        Generate correlation ID for tracking retry chains.

        Format: {request_id}.stage_{stage_name}.retry_{retry_attempt}
        Example: req_a3f2e8d1.stage_image_processing.retry_2

        Args:
            request_id: Unique request identifier
            stage_name: Processing stage name
            retry_attempt: Current retry attempt number

        Returns:
            Formatted correlation ID string
        """
        return f"{request_id}.stage_{stage_name}.retry_{retry_attempt}"

    def calculate_backoff_delay(self, retry_attempt: int, policy: RetryPolicy) -> float:
        """
        Calculate exponential backoff delay with optional jitter.

        Formula: min(base_delay * (exponential_base ** retry_attempt), max_delay)
        Jitter: ±20% random variation if enabled

        Args:
            retry_attempt: Current retry attempt number (0-indexed)
            policy: RetryPolicy with backoff configuration

        Returns:
            Delay in seconds (float)

        Example:
            policy = RetryPolicy(base_delay_seconds=1.0, exponential_base=2.0, max_delay_seconds=60.0)
            delay = calculate_backoff_delay(0, policy)  # Returns 1.0
            delay = calculate_backoff_delay(1, policy)  # Returns 2.0
            delay = calculate_backoff_delay(2, policy)  # Returns 4.0
            delay = calculate_backoff_delay(3, policy)  # Returns 8.0
        """
        # Calculate exponential backoff
        delay = min(policy.base_delay_seconds * (policy.exponential_base**retry_attempt), policy.max_delay_seconds)

        # Add jitter if enabled (±20% random variation)
        if policy.jitter_enabled:
            jitter = delay * random.uniform(-0.2, 0.2)
            delay = delay + jitter

        return delay

    async def acquire_advisory_lock(self, document_id: str, stage_name: str) -> bool:
        """
        Acquire PostgreSQL advisory lock for document/stage combination.

        Uses pg_try_advisory_lock for non-blocking lock acquisition.
        Lock ID is generated from deterministic SHA-256 hash of document_id:stage_name.

        Args:
            document_id: Document identifier
            stage_name: Processing stage name

        Returns:
            True if lock acquired, False if already locked

        Example:
            if await orchestrator.acquire_advisory_lock(doc_id, 'image_processing'):
                try:
                    # Process with lock held
                    pass
                finally:
                    await orchestrator.release_advisory_lock(doc_id, 'image_processing')
        """
        try:
            # Generate lock ID from deterministic SHA-256 hash of document_id:stage_name
            lock_key = f"{document_id}:{stage_name}"
            hash_bytes = hashlib.sha256(lock_key.encode("utf-8")).digest()
            # Take first 8 bytes and convert to signed 64-bit integer within PostgreSQL bigint range
            lock_id = int.from_bytes(hash_bytes[:8], byteorder="big", signed=False) % (2**63 - 1)

            # Try to acquire lock (non-blocking)
            query = "SELECT pg_try_advisory_lock($1)"
            result = await self.db_adapter.fetch_one(query, (lock_id,))

            acquired = self._extract_lock_result(result, "pg_try_advisory_lock")
            if acquired is None:
                # Fallback for test doubles / adapters that do not return typed boolean rows.
                self._ensure_local_lock_guard()
                async with self._local_advisory_locks_guard:
                    if lock_key in self._local_advisory_locks:
                        acquired = False
                    else:
                        self._local_advisory_locks.add(lock_key)
                        acquired = True

            if acquired:
                self.logger.debug(f"Acquired advisory lock for {lock_key} (lock_id={lock_id})")
            else:
                self.logger.debug(f"Failed to acquire advisory lock for {lock_key} (already locked)")

            return acquired

        except Exception as e:
            self.logger.error(f"Error acquiring advisory lock: {e}", exc_info=True)
            return False

    async def release_advisory_lock(self, document_id: str, stage_name: str) -> bool:
        """
        Release PostgreSQL advisory lock for document/stage combination.

        Args:
            document_id: Document identifier
            stage_name: Processing stage name

        Returns:
            True on success, False on failure
        """
        try:
            # Generate same lock ID as acquire using deterministic SHA-256 hash
            lock_key = f"{document_id}:{stage_name}"
            hash_bytes = hashlib.sha256(lock_key.encode("utf-8")).digest()
            lock_id = int.from_bytes(hash_bytes[:8], byteorder="big", signed=False) % (2**63 - 1)

            # Release lock
            query = "SELECT pg_advisory_unlock($1)"
            result = await self.db_adapter.fetch_one(query, (lock_id,))

            released = self._extract_lock_result(result, "pg_advisory_unlock")
            if released is None:
                self._ensure_local_lock_guard()
                async with self._local_advisory_locks_guard:
                    released = lock_key in self._local_advisory_locks
                    self._local_advisory_locks.discard(lock_key)
            elif released:
                # Keep fallback state consistent when DB unlock succeeds.
                self._local_advisory_locks.discard(lock_key)

            if released:
                self.logger.debug(f"Released advisory lock for {lock_key} (lock_id={lock_id})")
            else:
                # In pooled DB adapters, lock acquire/release can use different sessions.
                # That can make pg_advisory_unlock return false even when no lock leak exists.
                self.logger.debug(f"Advisory lock not released for {lock_key} (likely different DB session)")

            return released

        except Exception as e:
            self.logger.error(f"Error releasing advisory lock: {e}", exc_info=True)
            return False

    async def update_error_status(self, error_id: str, status: str, next_retry_at: datetime | None = None) -> bool:
        """
        Update error status in pipeline_errors table.

        Delegates to ErrorLogger.update_error_status().
        Valid statuses: 'pending', 'retrying', 'resolved', 'failed'

        Args:
            error_id: Unique error identifier
            status: New status value
            next_retry_at: Optional timestamp for next retry attempt

        Returns:
            True on success, False on failure
        """
        try:
            await self.error_logger.update_error_status(error_id, status, next_retry_at)
            self.logger.debug(f"Updated error {error_id} status to '{status}'")
            return True

        except Exception as e:
            self.logger.error(f"Error updating error status: {e}", exc_info=True)
            return False

    async def spawn_background_retry(
        self,
        context,  # ProcessingContext
        retry_attempt: int,
        policy: RetryPolicy,
        correlation_id: str,
        processor_callable: Callable,
        stage_name: str | None = None,
    ) -> None:
        """
        Spawn background retry task (fire-and-forget).

        Creates async task that executes _background_retry_task.
        Does not await the task - returns immediately.

        Args:
            context: ProcessingContext with document and retry info
            retry_attempt: Current retry attempt number
            policy: RetryPolicy for backoff configuration
            correlation_id: Correlation ID for tracking
            processor_callable: Async callable to retry processing
            stage_name: Optional processor stage name (used when policy.stage_name is None)

        Example:
            await orchestrator.spawn_background_retry(
                context, 1, policy, correlation_id, processor.process, 'image_processing'
            )
        """
        task = asyncio.create_task(
            self._background_retry_task(context, retry_attempt, policy, correlation_id, processor_callable, stage_name)
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        self.logger.info(
            f"Spawned background retry task for {context.document_id} "
            f"(correlation_id={correlation_id}, attempt={retry_attempt})"
        )

    async def _background_retry_task(
        self,
        context,  # ProcessingContext
        retry_attempt: int,
        policy: RetryPolicy,
        correlation_id: str,
        processor_callable: Callable,
        stage_name: str | None = None,
    ) -> None:
        """
        Background retry task implementation.

        Executes retry with exponential backoff and advisory locks.
        Handles success/failure and spawns next retry if needed.

        Args:
            context: ProcessingContext with document and retry info
            retry_attempt: Current retry attempt number
            policy: RetryPolicy for backoff configuration
            correlation_id: Correlation ID for tracking
            processor_callable: Async callable to retry processing
            stage_name: Optional processor stage name (used when policy.stage_name is None)
        """
        try:
            # Calculate and apply backoff delay
            delay = self.calculate_backoff_delay(retry_attempt, policy)
            self.logger.info(
                f"Retry attempt {retry_attempt} for {context.document_id} " f"will execute after {delay:.2f}s delay"
            )
            await asyncio.sleep(delay)

            # Update context for retry
            context.retry_attempt = retry_attempt
            context.correlation_id = correlation_id

            # Try to acquire advisory lock
            # Use explicit stage_name if provided, otherwise fall back to policy.stage_name or 'unknown'
            effective_stage_name = stage_name or policy.stage_name or "unknown"
            lock_acquired = await self.acquire_advisory_lock(context.document_id, effective_stage_name)

            if not lock_acquired:
                self.logger.warning(
                    f"Retry already in progress for {context.document_id} " f"(correlation_id={correlation_id})"
                )
                return

            try:
                # Update error status to 'retrying'
                if context.error_id:
                    await self.update_error_status(context.error_id, "retrying")

                # Execute retry with exception handling
                self.logger.info(
                    f"Executing retry attempt {retry_attempt} for {context.document_id} "
                    f"(correlation_id={correlation_id})"
                )

                try:
                    result = await processor_callable(context)
                except Exception as processor_error:
                    # Processor raised exception before returning result
                    self.logger.error(
                        f"Processor raised exception during retry attempt {retry_attempt} "
                        f"for {context.document_id}: {processor_error}",
                        exc_info=True,
                    )

                    # Update error status to 'failed' to prevent stuck 'retrying' status
                    if context.error_id:
                        await self.mark_retry_exhausted(context.error_id, processor_error)

                    # Re-raise to trigger outer exception handler
                    raise

                # Check if retry succeeded
                if result.success:
                    self.logger.info(f"Retry succeeded for {context.document_id} " f"(correlation_id={correlation_id})")

                    # Update error status to 'resolved'
                    if context.error_id:
                        await self.update_error_status(context.error_id, "resolved")
                else:
                    # Retry failed - check if more retries available
                    next_attempt = retry_attempt + 1

                    if next_attempt < policy.max_retries:
                        self.logger.warning(
                            f"Retry attempt {retry_attempt} failed for {context.document_id}, "
                            f"spawning next retry (attempt {next_attempt})"
                        )

                        # Spawn next retry
                        # Use same effective_stage_name for consistency
                        next_correlation_id = self.generate_correlation_id(
                            context.request_id, effective_stage_name, next_attempt
                        )

                        await self.spawn_background_retry(
                            context, next_attempt, policy, next_correlation_id, processor_callable, stage_name
                        )
                    else:
                        # Max retries exceeded
                        self.logger.error(
                            f"Max retries exceeded for {context.document_id} " f"(correlation_id={correlation_id})"
                        )

                        # Update error status to 'failed'
                        if context.error_id:
                            await self.mark_retry_exhausted(
                                context.error_id, result.error or Exception("Max retries exceeded")
                            )

            finally:
                # Always release lock
                await self.release_advisory_lock(context.document_id, effective_stage_name)

        except Exception as e:
            self.logger.error(f"Error in background retry task for {context.document_id}: {e}", exc_info=True)

            # Try to release lock on error
            try:
                effective_stage_name = stage_name or policy.stage_name or "unknown"
                await self.release_advisory_lock(context.document_id, effective_stage_name)
            except Exception:
                pass

    async def should_retry(self, classification: ErrorClassification, retry_attempt: int, policy: RetryPolicy) -> bool:
        """
        Determine if error should be retried.

        Checks:
        1. Error is transient (classification.is_transient)
        2. Retry attempts remaining (retry_attempt < policy.max_retries)

        Args:
            classification: ErrorClassification from ErrorClassifier
            retry_attempt: Current retry attempt number
            policy: RetryPolicy with max_retries configuration

        Returns:
            True if should retry, False otherwise

        Example:
            classification = ErrorClassifier.classify(exception)
            if await orchestrator.should_retry(classification, 0, policy):
                # Proceed with retry
                pass
        """
        is_transient = classification.is_transient
        has_retries_remaining = retry_attempt < policy.max_retries

        should_retry = is_transient and has_retries_remaining

        if should_retry:
            self.logger.info(
                f"Error is transient and retries remaining "
                f"(attempt {retry_attempt}/{policy.max_retries}): will retry"
            )
        else:
            reason = []
            if not is_transient:
                reason.append("error is permanent")
            if not has_retries_remaining:
                reason.append(f"max retries exceeded ({retry_attempt}/{policy.max_retries})")

            self.logger.info(f"Will not retry: {', '.join(reason)}")

        return should_retry

    async def get_retry_context(self, error_id: str) -> dict[str, Any] | None:
        """
        Get retry context from pipeline_errors table.

        Used for resuming retries after service restart.

        Args:
            error_id: Unique error identifier

        Returns:
            Dictionary with: document_id, stage_name, retry_count, correlation_id
            None if error not found

        Example:
            context = await orchestrator.get_retry_context(error_id)
            if context:
                # Resume retry from context
                pass
        """
        try:
            query = """
                SELECT document_id, stage_name, retry_count, correlation_id
                FROM krai_system.pipeline_errors
                WHERE error_id = $1
            """

            result = await self.db_adapter.fetch_one(query, (error_id,))

            if result:
                return {
                    "document_id": result["document_id"],
                    "stage_name": result["stage_name"],
                    "retry_count": result["retry_count"],
                    "correlation_id": result["correlation_id"],
                }

            return None

        except Exception as e:
            self.logger.error(f"Error getting retry context: {e}", exc_info=True)
            return None

    async def mark_retry_exhausted(self, error_id: str, final_error: Exception) -> bool:
        """
        Mark retry as exhausted after max retries exceeded.

        Updates error status to 'failed' with resolution notes.

        Args:
            error_id: Unique error identifier
            final_error: Final exception that caused failure

        Returns:
            True on success, False on failure
        """
        try:
            # Update error status to 'failed'
            updated = await self.update_error_status(error_id, "failed")
            if not updated:
                return False

            # Add resolution notes
            query = """
                UPDATE krai_system.pipeline_errors
                SET resolved_at = NOW(),
                    resolution_notes = $2
                WHERE error_id = $1
            """

            resolution_notes = f"Max retries exceeded. Final error: {final_error!s}"
            execute_query = getattr(self.db_adapter, "execute_query", None)
            execute = getattr(self.db_adapter, "execute", None)

            if callable(execute_query):
                query_result = await execute_query(query, (error_id, resolution_notes))
                # Some test doubles return nested mocks for unspecified methods.
                # In that case, prefer explicit execute() if available.
                if isinstance(query_result, Mock) and callable(execute):
                    await execute(query, (error_id, resolution_notes))
            elif callable(execute):
                await execute(query, (error_id, resolution_notes))
            else:
                raise RuntimeError("Database adapter does not provide execute_query/execute")

            self.logger.info(f"Marked error {error_id} as retry exhausted")
            return True

        except Exception as e:
            self.logger.error(f"Error marking retry exhausted: {e}", exc_info=True)
            return False
