"""
Error Logging Service for Pipeline Error Tracking

Provides dual-target error logging to both PostgreSQL (pipeline_errors table)
and structured JSON log files. Integrates with retry engine for comprehensive
error tracking and correlation.

Usage:
    from backend.services.error_logging_service import ErrorLogger
    from backend.core.retry_engine import ErrorClassifier

    error_logger = ErrorLogger(db_adapter)

    # Log an error
    error_id = await error_logger.log_error(
        context=processing_context,
        error=exception,
        classification=error_classification,
        retry_count=1,
        max_retries=3,
        correlation_id="req_123.embedding.retry_1"
    )

    # Update error status
    await error_logger.update_error_status(
        error_id=error_id,
        status="retrying",
        next_retry_at=datetime.utcnow() + timedelta(seconds=30)
    )

    # Mark error as resolved
    await error_logger.mark_error_resolved(
        error_id=error_id,
        resolved_by="retry_engine",
        notes="Successfully retried after 2 attempts"
    )
"""

import json
import traceback
from datetime import datetime
from typing import Any
from uuid import uuid4

from backend.core.base_processor import ProcessingContext
from backend.core.retry_engine import ErrorClassification
from backend.services.database_adapter import DatabaseAdapter
from backend.services.structured_logger import StructuredLogger


class ErrorLogger:
    """
    Dual-target error logging service for pipeline errors.

    Logs errors to both:
    1. PostgreSQL database (krai_system.pipeline_errors table)
    2. Structured JSON log files (via StructuredLogger)

    Features:
    - Unique error ID generation for tracking
    - Correlation ID support for retry tracking
    - Stack trace capture and storage
    - Error classification (transient/permanent)
    - Status tracking (pending/retrying/resolved/failed)
    - Async operations to avoid blocking pipeline

    Attributes:
        db_adapter (DatabaseAdapter): Database adapter for PostgreSQL operations
        structured_logger (StructuredLogger): JSON file logger
        log_file_path (str): Path to JSON log file
    """

    def __init__(self, db_adapter: DatabaseAdapter, log_file_path: str = "logs/pipeline.log"):
        """
        Initialize the error logger.

        Args:
            db_adapter: Database adapter instance for PostgreSQL operations
            log_file_path: Path to JSON log file (default: logs/pipeline.log)
        """
        self.db_adapter = db_adapter
        self.log_file_path = log_file_path
        self.structured_logger = StructuredLogger(logger_name="pipeline_errors", log_file_path=log_file_path)

    def _generate_error_id(self) -> str:
        """
        Generate a unique error ID.

        Returns:
            Unique error ID in format: err_{uuid_hex[:16]}
        """
        return f"err_{uuid4().hex[:16]}"

    def _extract_stack_trace(self, error: Exception) -> str:
        """
        Extract stack trace from exception.

        Args:
            error: Exception to extract stack trace from

        Returns:
            Formatted stack trace string
        """
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    def _build_error_context(
        self,
        context: ProcessingContext,
        error: Exception,
        classification: ErrorClassification,
        retry_count: int,
        max_retries: int,
        correlation_id: str,
    ) -> dict[str, Any]:
        """
        Build error context dictionary from processing context and error details.

        Args:
            context: Processing context
            error: Exception that occurred
            classification: Error classification from ErrorClassifier
            retry_count: Current retry count
            max_retries: Maximum retry attempts
            correlation_id: Correlation ID for tracking

        Returns:
            Dictionary containing error context
        """
        error_context = {
            "document_id": context.document_id,
            "file_path": context.file_path,
            "document_type": context.document_type,
            "manufacturer": context.manufacturer,
            "model": context.model,
            "series": context.series,
            "version": context.version,
            "language": context.language,
            "file_hash": context.file_hash,
            "file_size": context.file_size,
            "request_id": context.request_id,
            "correlation_id": correlation_id,
            "retry_attempt": context.retry_attempt,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "error_category": classification.error_category,
            "is_transient": classification.is_transient,
            "error_type": classification.error_type,
            "error_message": str(error),
        }

        # Add metadata if present
        if context.metadata:
            error_context["context_metadata"] = context.metadata

        # Add processing config if present
        if context.processing_config:
            error_context["processing_config"] = context.processing_config

        return error_context

    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize context dictionary to remove sensitive data.

        Args:
            context: Context dictionary to sanitize

        Returns:
            Sanitized context dictionary
        """
        # Create a copy to avoid modifying original
        sanitized = dict(context)

        # Remove or mask sensitive fields
        sensitive_fields = ["password", "api_key", "token", "secret", "credential"]

        for key in list(sanitized.keys()):
            # Check if key contains sensitive terms
            if any(term in key.lower() for term in sensitive_fields):
                sanitized[key] = "***REDACTED***"

            # Recursively sanitize nested dicts
            elif isinstance(sanitized[key], dict):
                sanitized[key] = self._sanitize_context(sanitized[key])

        return sanitized

    async def log_error(
        self,
        context: ProcessingContext,
        error: Exception,
        classification: ErrorClassification,
        retry_count: int,
        max_retries: int,
        correlation_id: str,
        stage_name: str | None = None,
    ) -> str:
        """
        Log an error to both database and JSON log file.

        Args:
            context: Processing context
            error: Exception that occurred
            classification: Error classification from ErrorClassifier
            retry_count: Current retry count
            max_retries: Maximum retry attempts
            correlation_id: Correlation ID for tracking
            stage_name: Optional stage name (extracted from correlation_id if not provided)

        Returns:
            Unique error ID for tracking

        Raises:
            Exception: If database operation fails (logged but not raised)
        """
        # Generate unique error ID
        error_id = self._generate_error_id()

        # Extract stack trace
        stack_trace = self._extract_stack_trace(error)

        # Build error context
        error_context = self._build_error_context(
            context=context,
            error=error,
            classification=classification,
            retry_count=retry_count,
            max_retries=max_retries,
            correlation_id=correlation_id,
        )

        # Sanitize context
        sanitized_context = self._sanitize_context(error_context)

        # Extract and normalize stage name from correlation_id if not provided.
        # Format: {request_id}.stage_{stage}.retry_{n} -> persist stage_name as "{stage}" (strip "stage_" prefix).
        # Callers can still override by passing stage_name explicitly.
        if not stage_name and correlation_id:
            parts = correlation_id.split(".")
            if len(parts) >= 2:
                raw = parts[1]
                stage_name = raw[6:] if raw.startswith("stage_") else raw

        # Write to database
        try:
            query = """
                INSERT INTO krai_system.pipeline_errors (
                    error_id, document_id, stage_name, error_type, error_category,
                    error_message, stack_trace, context, retry_count, max_retries,
                    status, is_transient, correlation_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """

            params = [
                error_id,
                context.document_id,
                stage_name or "unknown",
                type(error).__name__,
                classification.error_category,
                str(error),
                stack_trace,
                json.dumps(sanitized_context, default=str),
                retry_count,
                max_retries,
                "pending",
                classification.is_transient,
                correlation_id,
            ]

            await self.db_adapter.execute_query(query, params)

        except Exception as db_error:
            # Log database error but don't fail the entire operation
            await self.structured_logger.log_error(
                error=db_error,
                context={"operation": "database_insert", "error_id": error_id, "document_id": context.document_id},
                correlation_id=correlation_id,
                error_id=f"{error_id}_db_error",
                error_category="database_error",
            )

        # Write to JSON log file
        await self.structured_logger.log_error(
            error=error,
            context=sanitized_context,
            correlation_id=correlation_id,
            error_id=error_id,
            error_category=classification.error_category,
            stage=stage_name,
            retry_count=retry_count,
            max_retries=max_retries,
            is_transient=classification.is_transient,
        )

        return error_id

    async def update_error_status(self, error_id: str, status: str, next_retry_at: datetime | None = None):
        """
        Update the status of an error in the database.

        Args:
            error_id: Unique error identifier
            status: New status (pending/retrying/resolved/failed)
            next_retry_at: Optional next retry timestamp

        Raises:
            Exception: If database operation fails
        """
        query = """
            UPDATE krai_system.pipeline_errors
            SET status = $1,
                next_retry_at = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE error_id = $3
        """

        params = [status, next_retry_at, error_id]

        await self.db_adapter.execute_query(query, params)

        # Log status update to JSON file
        await self.structured_logger.log_info(
            message=f"Error status updated to: {status}",
            context={
                "error_id": error_id,
                "status": status,
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
            },
        )

    async def mark_error_resolved(self, error_id: str, resolved_by: str | None = None, notes: str | None = None):
        """
        Mark an error as resolved in the database.

        Args:
            error_id: Unique error identifier
            resolved_by: Optional identifier of who/what resolved the error
            notes: Optional resolution notes

        Raises:
            Exception: If database operation fails
        """
        query = """
            UPDATE krai_system.pipeline_errors
            SET status = 'resolved',
                resolved_at = CURRENT_TIMESTAMP,
                resolved_by = $1,
                resolution_notes = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE error_id = $3
        """

        params = [resolved_by, notes, error_id]

        await self.db_adapter.execute_query(query, params)

        # Log resolution to JSON file
        await self.structured_logger.log_info(
            message=f"Error resolved: {error_id}",
            context={"error_id": error_id, "resolved_by": resolved_by, "resolution_notes": notes},
        )

    async def get_error_by_id(self, error_id: str) -> dict[str, Any] | None:
        """
        Retrieve error details from database by error ID.

        Args:
            error_id: Unique error identifier

        Returns:
            Dictionary containing error details, or None if not found
        """
        query = """
            SELECT error_id, document_id, stage_name, error_type, error_category,
                   error_message, stack_trace, context, retry_count, max_retries,
                   status, is_transient, correlation_id, created_at, updated_at,
                   next_retry_at, resolved_at, resolved_by, resolution_notes
            FROM krai_system.pipeline_errors
            WHERE error_id = $1
        """

        result = await self.db_adapter.fetch_one(query, [error_id])

        if result:
            # Convert to dictionary
            return dict(result)

        return None

    async def get_errors_by_correlation_id(self, correlation_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all errors for a given correlation ID.

        Useful for tracking all retry attempts for a single processing request.

        Args:
            correlation_id: Correlation ID to search for

        Returns:
            List of error dictionaries
        """
        query = """
            SELECT error_id, document_id, stage_name, error_type, error_category,
                   error_message, stack_trace, context, retry_count, max_retries,
                   status, is_transient, correlation_id, created_at, updated_at,
                   next_retry_at, resolved_at, resolved_by, resolution_notes
            FROM krai_system.pipeline_errors
            WHERE correlation_id = $1
            ORDER BY created_at ASC
        """

        results = await self.db_adapter.fetch_all(query, [correlation_id])

        return [dict(row) for row in results]

    async def get_unresolved_errors(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Retrieve unresolved errors from database.

        Args:
            limit: Maximum number of errors to retrieve

        Returns:
            List of error dictionaries
        """
        query = """
            SELECT error_id, document_id, stage_name, error_type, error_category,
                   error_message, stack_trace, context, retry_count, max_retries,
                   status, is_transient, correlation_id, created_at, updated_at,
                   next_retry_at, resolved_at, resolved_by, resolution_notes
            FROM krai_system.pipeline_errors
            WHERE status IN ('pending', 'retrying')
            ORDER BY created_at DESC
            LIMIT $1
        """

        results = await self.db_adapter.fetch_all(query, [limit])

        return [dict(row) for row in results]
