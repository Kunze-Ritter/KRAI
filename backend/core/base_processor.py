"""
Base Processor Interface
Foundation for all 8 specialized processors in the KR-AI-Engine pipeline
"""

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from backend.core.retry_engine import ErrorClassifier, RetryOrchestrator, RetryPolicyManager
from backend.core.types import ProcessingContext, ProcessingError, ProcessingResult, ProcessingStatus, Stage
from backend.processors.logger import get_logger

if TYPE_CHECKING:
    from backend.core.idempotency import IdempotencyChecker
    from backend.services.error_logging_service import ErrorLogger
    from backend.services.performance_service import PerformanceCollector


class BaseProcessor(ABC):
    """
    Base class for all processors in the KR-AI-Engine pipeline

    Follows the enhanced processing pipeline with multi-modal support:
    1. Upload Processor → krai_core.documents (Database only)
    2. Text Processor → krai_content.chunks + krai_intelligence.chunks
    2b. Table Processor → krai_intelligence.structured_tables
    3a. SVG Processor → Convert vector graphics to PNG for Vision AI
    3. Image Processor → krai_content.images (Object Storage)
    3b. Visual Embedding Processor → krai_intelligence.unified_embeddings (source_type='image')
    4. Classification Processor → krai_core.manufacturers, products, product_series
    5. Metadata Processor → krai_intelligence.error_codes
    6. Storage Processor → MinIO Object Storage (images only)
    7. Text Chunking → krai_intelligence.chunks
    8. Embedding Processor → krai_intelligence.chunks (with embedding column) + unified_embeddings (source_type='text')
    9. Finalization → krai_system.processing_queue
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
        processor_logger = get_logger(name=f"processor.{name}")
        self.logger = processor_logger  # ProcessorLogger interface (info, success, etc.)
        self.log = processor_logger
        self._base_logger = processor_logger.logger
        self._base_extra: dict[str, Any] = {"processor": self.name}
        self._logger_adapter = logging.LoggerAdapter(self._base_logger, dict(self._base_extra))
        self._idempotency_checker: IdempotencyChecker | None = None  # Lazy initialized
        self._error_logger: ErrorLogger | None = None  # Lazy initialized
        self._retry_orchestrator: RetryOrchestrator | None = None  # Lazy initialized
        self._performance_collector: PerformanceCollector | None = None
        self.service_name: str = config.get("service_name", "default") if config else "default"

    @contextlib.contextmanager
    def logger_context(self, document_id: str | UUID | None = None, stage: Stage | str | None = None, **extra: Any):
        """Attach contextual fields (processor/document/stage) to logger."""

        merged_extra: dict[str, Any] = dict(self._base_extra)
        if document_id is not None:
            merged_extra["document_id"] = str(document_id)
        if stage is not None:
            merged_extra["stage"] = stage.value if isinstance(stage, Stage) else stage
        merged_extra.update({k: v for k, v in extra.items() if v is not None})

        adapter = logging.LoggerAdapter(self._base_logger, merged_extra)
        previous_adapter = self._logger_adapter
        self._logger_adapter = adapter
        try:
            yield adapter
        finally:
            self._logger_adapter = previous_adapter

    def set_performance_collector(self, collector: "PerformanceCollector") -> None:
        """Set the performance collector for metrics collection."""
        self._performance_collector = collector

    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Main processing method - MUST be implemented by subclasses

        Args:
            context: Processing context with document information

        Returns:
            ProcessingResult: Result of the processing operation

        Raises:
            ProcessingError: If processing fails (Error = Stopp!)
        """
        pass

    def get_required_inputs(self) -> list[str]:
        """
        Get list of required input data for this processor.

        Subclasses can override to declare specific requirements. Defaults to []
        """
        return []

    def get_outputs(self) -> list[str]:
        """
        Get list of output data produced by this processor.

        Subclasses can override to declare structured outputs. Defaults to []
        """
        return []

    def validate_inputs(self, context: ProcessingContext) -> bool:
        """
        Validate that all required inputs are present

        Args:
            context: Processing context to validate

        Returns:
            bool: True if inputs are valid

        Raises:
            ProcessingError: If validation fails
        """
        required_inputs = self.get_required_inputs()

        for input_key in required_inputs:
            if not hasattr(context, input_key) or getattr(context, input_key) is None:
                raise ProcessingError(f"Missing required input: {input_key}", self.name, "MISSING_INPUT")

        return True

    def log_processing_start(self, context: ProcessingContext) -> None:
        """Log the start of processing"""
        with self.logger_context(document_id=context.document_id) as adapter:
            adapter.info(
                "Starting %s processing for document %s",
                self.name,
                context.document_id,
            )
            adapter.debug("Context: %s", context)

    def log_processing_end(self, result: ProcessingResult | dict[str, Any]) -> None:
        """Log the end of processing"""
        document_id = None
        stage = None
        if isinstance(result, dict):
            result_metadata = result.get("metadata")
            if isinstance(result_metadata, dict):
                document_id = result_metadata.get("document_id") or result_metadata.get("document")
                stage = result_metadata.get("stage")
            success = bool(result.get("success"))
            processing_time = float(result.get("processing_time") or 0.0)
            error_value = result.get("error")
        else:
            if result.metadata:
                document_id = result.metadata.get("document_id") or result.metadata.get("document")
                stage = result.metadata.get("stage")
            success = result.success
            processing_time = result.processing_time
            error_value = result.error

        with self.logger_context(document_id=document_id, stage=stage) as adapter:
            if success:
                adapter.info(
                    "Completed %s processing in %.2fs",
                    self.name,
                    processing_time,
                )
                self.logger.success(f"{self.name} completed in {processing_time:.2f}s")
            else:
                adapter.error(
                    "Failed %s processing: %s",
                    self.name,
                    error_value,
                )
                self.logger.error(f"{self.name} failed: {error_value}")

    def _normalize_process_result(
        self,
        result: ProcessingResult | dict[str, Any],
        context: ProcessingContext,
        correlation_id: str,
        attempt: int,
    ) -> ProcessingResult:
        """Normalize processor outputs to ProcessingResult for safe_process downstream logic."""
        if isinstance(result, ProcessingResult):
            if not result.metadata:
                result.metadata = {}
            result.metadata.setdefault("document_id", str(context.document_id))
            result.metadata.setdefault("correlation_id", correlation_id)
            result.metadata.setdefault("retry_attempt", attempt)
            return result

        if isinstance(result, dict):
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            metadata = dict(metadata)
            metadata.setdefault("document_id", str(context.document_id))
            metadata.setdefault("correlation_id", correlation_id)
            metadata.setdefault("retry_attempt", attempt)

            success = bool(result.get("success", True))
            error_value = result.get("error")
            normalized_error: ProcessingError | None = None
            if not success and error_value:
                if isinstance(error_value, ProcessingError):
                    normalized_error = error_value
                else:
                    normalized_error = ProcessingError(str(error_value), self.name, "PROCESSING_ERROR")

            return ProcessingResult(
                success=success,
                processor=self.name,
                status=ProcessingStatus.COMPLETED if success else ProcessingStatus.FAILED,
                data=result,
                metadata=metadata,
                error=normalized_error,
            )

        raise TypeError(f"{self.name}.process() must return ProcessingResult or dict, got {type(result).__name__}")

    def create_success_result(self, data: dict[str, Any], metadata: dict[str, Any] | None = None) -> ProcessingResult:
        """Create a successful processing result"""
        return ProcessingResult(
            success=True,
            processor=self.name,
            status=ProcessingStatus.COMPLETED,
            data=data,
            metadata=metadata or {},
            processing_time=0.0,  # Will be set by caller
        )

    def create_error_result(
        self,
        error: ProcessingError,
        metadata: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ProcessingResult:
        """Create a failed processing result with error_id and correlation_id support"""
        result_metadata = metadata or {}
        return ProcessingResult(
            success=False,
            processor=self.name,
            status=ProcessingStatus.FAILED,
            data=data or {},
            metadata=result_metadata,
            error=error,
            processing_time=0.0,  # Will be set by caller
        )

    def create_retrying_result(self, correlation_id: str, metadata: dict[str, Any] | None = None) -> ProcessingResult:
        """Create a result indicating async retry is in progress"""
        result_metadata = metadata or {}
        result_metadata["correlation_id"] = correlation_id
        return ProcessingResult(
            success=False,
            processor=self.name,
            status=ProcessingStatus.IN_PROGRESS,
            data={"message": "Async retry in progress", "correlation_id": correlation_id},
            metadata=result_metadata,
            processing_time=0.0,
        )

    def create_result(
        self, status: str, data: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None
    ) -> ProcessingResult:
        """Create a generic processing result for special cases"""
        return ProcessingResult(
            success=(status == ProcessingStatus.COMPLETED),
            processor=self.name,
            status=status,
            data=data or {},
            metadata=metadata or {},
            processing_time=0.0,
        )

    async def safe_process(self, context: ProcessingContext) -> ProcessingResult:
        """
        Safely execute processing with hybrid retry loop.

        Implements intelligent retry logic with:
        - Synchronous first retry (immediate with short delay)
        - Asynchronous subsequent retries (background tasks with exponential backoff)
        - Idempotency checks to prevent duplicate processing
        - PostgreSQL advisory locks to prevent concurrent retries
        - Error classification and logging

        Retry Flow:
        1. First attempt: Execute immediately
        2. First retry (attempt 0): Synchronous retry after base_delay
        3. Subsequent retries: Spawn background tasks with exponential backoff

        Args:
            context: Processing context with document information

        Returns:
            ProcessingResult: Result of processing (success, failure, or retrying)

        Correlation ID Format:
            {request_id}.stage_{stage_name}.retry_{attempt}
            Example: req_a3f2e8d1.stage_image_processing.retry_2
        """
        # Phase A: Initialization
        # Generate request_id if not present
        if not hasattr(context, "request_id") or not context.request_id:
            context.request_id = f"req_{uuid4().hex[:8]}"

        # Ensure RetryPolicyManager can load policies from DB when adapter is available.
        adapter = (
            getattr(self, "db_adapter", None)
            or getattr(self, "database_service", None)
            or getattr(self, "database_adapter", None)
        )
        if adapter is not None:
            RetryPolicyManager.set_db_adapter(adapter)

        # Load retry policy
        retry_policy = await RetryPolicyManager.get_policy(self.service_name, self.name)

        # Get retry components (with graceful degradation)
        error_logger = self._get_error_logger()
        orchestrator = self._get_retry_orchestrator()

        # Initialize timing
        start_time = datetime.utcnow()

        # Phase B: Hybrid Retry Loop
        for attempt in range(retry_policy.max_retries + 1):
            # Generate correlation_id for this attempt
            correlation_id = f"{context.request_id}.stage_{self.name}.retry_{attempt}"
            context.correlation_id = correlation_id
            context.retry_attempt = attempt

            # Phase C: Idempotency Check
            marker = await self._check_completion_marker(context)
            if marker:
                current_hash = self._compute_data_hash(context)
                if marker.get("data_hash") == current_hash:
                    # Data unchanged - skip processing
                    self.logger.info(f"Skipping {self.name} for document {context.document_id} - already processed")
                    return self.create_result(
                        status=ProcessingStatus.COMPLETED,
                        data={"skipped": "already_processed", "marker": marker},
                        metadata={"correlation_id": correlation_id},
                    )
                # Data changed - cleanup and continue
                self.logger.info(f"Data changed for {context.document_id} - cleaning up old data")
                await self._cleanup_old_data(context)

            # Phase D: Advisory Lock Acquisition
            lock_acquired = False
            if orchestrator:
                lock_acquired = await orchestrator.acquire_advisory_lock(context.document_id, self.name)

                # If lock not acquired and this is a retry, another process is handling it
                if not lock_acquired and attempt > 0:
                    self.logger.info(f"Retry already in progress for {context.document_id} (attempt {attempt})")
                    return self.create_result(
                        status="retry_in_progress",
                        data={"message": "Another retry is in progress"},
                        metadata={"correlation_id": correlation_id},
                    )

            try:
                # Phase E: Processing Execution
                try:
                    # Validate inputs
                    self.validate_inputs(context)

                    # Log start
                    self.log_processing_start(context)

                    # Execute processing
                    result = await self.process(context)
                    result = self._normalize_process_result(result, context, correlation_id, attempt)

                    # Calculate processing time
                    processing_time = (datetime.utcnow() - start_time).total_seconds()
                    if isinstance(result, dict):
                        result["processing_time"] = processing_time
                    else:
                        result.processing_time = processing_time

                    # Set completion marker
                    await self._set_completion_marker(
                        context,
                        {
                            "processing_time": processing_time,
                            "retry_attempt": attempt,
                            "correlation_id": correlation_id,
                        },
                    )

                    # Log end
                    self.log_processing_end(result)

                    # Collect performance metrics (success path)
                    if self._performance_collector:
                        try:
                            await self._performance_collector.collect_stage_metrics(self.name, result, success=True)
                            await self._performance_collector.store_stage_metric(
                                document_id=str(context.document_id),
                                stage_name=self.name,
                                processing_time=processing_time,
                                success=True,
                                correlation_id=correlation_id,
                            )
                        except Exception as metrics_error:
                            self.logger.debug(f"Failed to collect performance metrics: {metrics_error}")

                    return result

                # Phase F: Exception Handling
                except Exception as e:
                    # Classify error
                    classification = ErrorClassifier.classify(e)

                    # Log error
                    error_id = None
                    if error_logger:
                        try:
                            error_id = await error_logger.log_error(
                                context=context,
                                error=e,
                                classification=classification,
                                retry_count=attempt,
                                max_retries=retry_policy.max_retries,
                                correlation_id=correlation_id,
                                stage_name=self.name,
                            )
                            context.error_id = error_id
                        except Exception as log_error:
                            self.logger.error(f"Failed to log error: {log_error}", exc_info=True)

                    # Phase G: Retry Decision Logic
                    is_transient = classification.is_transient
                    has_retries_remaining = attempt < retry_policy.max_retries

                    if is_transient and has_retries_remaining:
                        if orchestrator:
                            # Orchestrator available - use hybrid retry strategy
                            if attempt == 0:
                                # First retry: Synchronous
                                self.logger.info(
                                    f"Transient error on attempt {attempt}, retrying synchronously "
                                    f"after {retry_policy.base_delay_seconds}s"
                                )
                                await asyncio.sleep(retry_policy.base_delay_seconds)
                                # Continue loop for immediate retry
                                continue
                            # Subsequent retries: Asynchronous
                            # Generate new correlation_id for next attempt
                            next_correlation_id = RetryOrchestrator.generate_correlation_id(
                                context.request_id, self.name, attempt + 1
                            )
                            self.logger.info(f"Transient error on attempt {attempt}, spawning background retry")
                            await orchestrator.spawn_background_retry(
                                context,
                                attempt + 1,
                                retry_policy,
                                next_correlation_id,
                                self.safe_process,
                                self.name,
                            )
                            return self.create_retrying_result(next_correlation_id, metadata={"error_id": error_id})
                        # Fallback: Orchestrator unavailable but error is transient
                        # Perform synchronous retry to avoid treating transient errors as permanent
                        self.logger.warning(
                            f"Retry orchestrator unavailable, falling back to synchronous retry "
                            f"for transient error on attempt {attempt}"
                        )
                        await asyncio.sleep(retry_policy.base_delay_seconds)
                        # Continue loop for immediate retry
                        continue
                    # Permanent error or max retries exceeded
                    processing_time = (datetime.utcnow() - start_time).total_seconds()

                    if isinstance(e, ProcessingError):
                        error = e
                    else:
                        error = ProcessingError(f"Error after {attempt} attempts: {e!s}", self.name, "PROCESSING_ERROR")

                    result = self.create_error_result(
                        error,
                        metadata={
                            "correlation_id": correlation_id,
                            "error_id": error_id,
                            "retry_attempt": attempt,
                            "error_category": classification.error_category,
                            "document_id": str(context.document_id),
                        },
                    )
                    if isinstance(result, dict):
                        result["processing_time"] = processing_time
                    else:
                        result.processing_time = processing_time
                    self.log_processing_end(result)

                    # Collect performance metrics (failure path)
                    if self._performance_collector:
                        try:
                            await self._performance_collector.collect_stage_metrics(
                                self.name, result, success=False, error_message=str(error)
                            )
                            await self._performance_collector.store_stage_metric(
                                document_id=str(context.document_id),
                                stage_name=self.name,
                                processing_time=processing_time,
                                success=False,
                                error_message=str(error),
                                correlation_id=correlation_id,
                            )
                        except Exception as metrics_error:
                            self.logger.debug(f"Failed to collect failure metrics: {metrics_error}")

                    return result

            finally:
                # Phase H: Lock Release
                if orchestrator and lock_acquired:
                    await orchestrator.release_advisory_lock(context.document_id, self.name)

        # Should never reach here, but handle gracefully
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        error = ProcessingError("Max retries exceeded", self.name, "MAX_RETRIES_EXCEEDED")
        result = self.create_error_result(error, metadata={"document_id": str(context.document_id)})
        if isinstance(result, dict):
            result["processing_time"] = processing_time
        else:
            result.processing_time = processing_time
        if self._performance_collector:
            try:
                await self._performance_collector.collect_stage_metrics(
                    self.name, result, success=False, error_message=str(error)
                )
                await self._performance_collector.store_stage_metric(
                    document_id=str(context.document_id),
                    stage_name=self.name,
                    processing_time=processing_time,
                    success=False,
                    error_message=str(error),
                    correlation_id=getattr(context, "correlation_id", None),
                )
            except Exception as metrics_error:
                self.logger.debug(f"Failed to collect failure metrics: {metrics_error}")
        return result

    def get_resource_requirements(self) -> dict[str, Any]:
        """
        Get resource requirements for this processor

        Returns:
            Dict[str, Any]: Resource requirements
        """
        return {
            "cpu_intensive": False,
            "memory_intensive": False,
            "gpu_required": False,
            "estimated_ram_gb": 1.0,
            "estimated_gpu_gb": 0.0,
            "parallel_safe": True,
        }

    def get_dependencies(self) -> list[str]:
        """
        Get list of processors this processor depends on

        Returns:
            List[str]: List of processor names this depends on
        """
        return []

    def get_output_tables(self) -> list[str]:
        """
        Get list of database tables this processor writes to

        Returns:
            List[str]: List of table names
        """
        return []

    def get_storage_buckets(self) -> list[str]:
        """
        Get list of storage buckets this processor uses

        Returns:
            List[str]: List of bucket names
        """
        return []

    def _get_idempotency_checker(self) -> Optional["IdempotencyChecker"]:
        """
        Get or initialize the IdempotencyChecker instance.

        Returns:
            IdempotencyChecker instance if database adapter is available, None otherwise
        """
        if self._idempotency_checker is None:
            # Lazy initialization - requires database adapter
            # Subclasses may set db_adapter, database_service, or database_adapter
            adapter = (
                getattr(self, "db_adapter", None)
                or getattr(self, "database_service", None)
                or getattr(self, "database_adapter", None)
            )
            if adapter is not None:
                # Lazy import to break circular dependency
                from backend.core.idempotency import IdempotencyChecker

                self._idempotency_checker = IdempotencyChecker(adapter)
        return self._idempotency_checker

    def _get_error_logger(self) -> Optional["ErrorLogger"]:
        """
        Get or initialize the ErrorLogger instance.

        Returns:
            ErrorLogger instance if database adapter is available, None otherwise
        """
        if self._error_logger is None:
            adapter = (
                getattr(self, "db_adapter", None)
                or getattr(self, "database_service", None)
                or getattr(self, "database_adapter", None)
            )
            if adapter is not None:
                try:
                    from backend.services.error_logging_service import ErrorLogger

                    self._error_logger = ErrorLogger(adapter)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize ErrorLogger: {e}")
        return self._error_logger

    def _get_retry_orchestrator(self) -> RetryOrchestrator | None:
        """
        Get or initialize the RetryOrchestrator instance.

        Returns:
            RetryOrchestrator instance if database adapter and error logger are available, None otherwise
        """
        if self._retry_orchestrator is None:
            error_logger = self._get_error_logger()
            adapter = (
                getattr(self, "db_adapter", None)
                or getattr(self, "database_service", None)
                or getattr(self, "database_adapter", None)
            )
            if adapter is not None and error_logger:
                try:
                    self._retry_orchestrator = RetryOrchestrator(adapter, error_logger)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize RetryOrchestrator: {e}")
        return self._retry_orchestrator

    async def _check_completion_marker(self, context: ProcessingContext) -> dict[str, Any] | None:
        """
        Check if a completion marker exists for this stage and document.

        This method delegates to IdempotencyChecker to query the database
        for existing completion markers. Use this to determine if a stage
        has already been processed.

        Args:
            context: Processing context containing document_id

        Returns:
            Dictionary containing marker data if found, None otherwise.
            Marker includes: document_id, stage_name, completed_at, data_hash, metadata

        Example:
            ```python
            marker = await self._check_completion_marker(context)
            if marker:
                # Stage already completed
                current_hash = self._compute_data_hash(context)
                if marker['data_hash'] == current_hash:
                    # Data unchanged - skip processing
                    return cached_result
            ```
        """
        checker = self._get_idempotency_checker()
        if checker is None:
            self.logger.warning(
                f"Idempotency checker not available for {self.name} - " "database adapter not configured"
            )
            return None

        return await checker.check_completion_marker(context.document_id, self.name)

    async def _set_completion_marker(self, context: ProcessingContext, metadata: dict[str, Any] | None = None) -> bool:
        """
        Mark this stage as completed for the document.

        This method delegates to IdempotencyChecker to insert or update
        a completion marker in the database. Call this after successful
        processing to prevent re-execution.

        Args:
            context: Processing context containing document_id
            metadata: Optional metadata to store (processing time, output summary, etc.)

        Returns:
            True if marker was set successfully, False otherwise

        Example:
            ```python
            # After successful processing
            success = await self._set_completion_marker(
                context,
                {
                    "processing_time": result.processing_time,
                    "chunks_created": len(chunks),
                    "retry_count": context.retry_attempt
                }
            )
            ```
        """
        checker = self._get_idempotency_checker()
        if checker is None:
            self.logger.warning(
                f"Idempotency checker not available for {self.name} - " "database adapter not configured"
            )
            return False

        data_hash = self._compute_data_hash(context)
        return await checker.set_completion_marker(context.document_id, self.name, data_hash, metadata)

    async def _cleanup_old_data(self, context: ProcessingContext) -> bool:
        """
        Remove old data for this stage to prepare for re-processing.

        This method delegates to IdempotencyChecker to delete the completion
        marker. Call this when data has changed and re-processing is needed.

        Note: This only removes the completion marker. Stage-specific data
        cleanup (e.g., chunks, embeddings) should be handled by the processor.

        Args:
            context: Processing context containing document_id

        Returns:
            True if cleanup was successful, False otherwise

        Example:
            ```python
            marker = await self._check_completion_marker(context)
            if marker:
                current_hash = self._compute_data_hash(context)
                if marker['data_hash'] != current_hash:
                    # Data changed - cleanup and re-process
                    await self._cleanup_old_data(context)
                    # Continue with processing...
            ```
        """
        checker = self._get_idempotency_checker()
        if checker is None:
            self.logger.warning(
                f"Idempotency checker not available for {self.name} - " "database adapter not configured"
            )
            return False

        return await checker.cleanup_old_data(context.document_id, self.name)

    def _compute_data_hash(self, context: ProcessingContext) -> str:
        """
        Calculate SHA-256 hash of input data.

        Uses the standalone compute_context_hash function, which works without
        requiring a database adapter. This allows hash computation to be decoupled
        from database availability.

        Args:
            context: Processing context containing document metadata

        Returns:
            64-character hexadecimal SHA-256 hash string

        Example:
            ```python
            hash1 = self._compute_data_hash(context1)
            hash2 = self._compute_data_hash(context2)

            if hash1 == hash2:
                # Data unchanged
                pass
            else:
                # Data changed - re-processing needed
                pass
            ```
        """
        # Use standalone hash function - no DB required
        from backend.core.idempotency import compute_context_hash

        return compute_context_hash(context)
