"""
Structured Logger for JSON-based Error Logging

Provides JSON-formatted logging with file rotation for pipeline error tracking.
Supports correlation IDs, error IDs, and rich contextual metadata.

Usage:
    logger = StructuredLogger("pipeline", "logs/pipeline.log")
    await logger.log_error(
        error=exception,
        context={"document_id": "123", "stage": "embedding"},
        correlation_id="req_123.embedding.retry_1",
        error_id="err_abc123"
    )
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


class StructuredLogger:
    """
    JSON-based structured logger with file rotation.

    Features:
    - JSON-formatted log entries for easy parsing
    - Automatic file rotation (100MB max, 10 backup files)
    - Async writes to avoid blocking the pipeline
    - Correlation ID and error ID tracking
    - Rich contextual metadata support

    Attributes:
        logger_name (str): Name of the logger instance
        log_file_path (str): Path to the log file
        max_bytes (int): Maximum file size before rotation (default: 100MB)
        backup_count (int): Number of backup files to keep (default: 10)
    """

    def __init__(
        self,
        logger_name: str,
        log_file_path: str,
        max_bytes: int = 100 * 1024 * 1024,
        backup_count: int = 10,  # 100MB
    ):
        """
        Initialize the structured logger.

        Args:
            logger_name: Name for the logger instance
            log_file_path: Path where log file should be created
            max_bytes: Maximum file size before rotation (default: 100MB)
            backup_count: Number of backup files to keep (default: 10)
        """
        self.logger_name = logger_name
        self.log_file_path = log_file_path
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # Ensure log directory exists
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure logger
        self._logger = logging.getLogger(f"structured.{logger_name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False  # Don't propagate to root logger

        # Remove existing handlers to avoid duplicates
        self._logger.handlers.clear()

        # Add rotating file handler
        handler = RotatingFileHandler(log_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        handler.setLevel(logging.DEBUG)

        # Use plain formatter - we'll format as JSON ourselves
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def _format_json(
        self,
        level: str,
        message: str,
        error_id: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        stage: str | None = None,
        document_id: str | None = None,
        error_type: str | None = None,
        error_category: str | None = None,
        stack_trace: str | None = None,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> str:
        """
        Format log entry as JSON.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            error_id: Unique error identifier
            correlation_id: Correlation ID for tracking
            request_id: Request ID
            stage: Processing stage name
            document_id: Document ID being processed
            error_type: Exception class name
            error_category: Error category (transient/permanent)
            stack_trace: Stack trace string
            context: Additional contextual data
            **kwargs: Additional fields to include

        Returns:
            JSON-formatted log entry string
        """
        log_entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
        }

        # Add optional fields if provided
        if error_id:
            log_entry["error_id"] = error_id
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        if request_id:
            log_entry["request_id"] = request_id
        if stage:
            log_entry["stage"] = stage
        if document_id:
            log_entry["document_id"] = document_id
        if error_type:
            log_entry["error_type"] = error_type
        if error_category:
            log_entry["error_category"] = error_category
        if stack_trace:
            log_entry["stack_trace"] = stack_trace
        if context:
            log_entry["context"] = context

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in log_entry and value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)

    async def _async_write(self, log_entry: str, level: int):
        """
        Asynchronously write log entry to file.

        Args:
            log_entry: Formatted JSON log entry
            level: Logging level constant
        """
        # Run the blocking log operation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._logger.log(level, log_entry))

    async def log_error(
        self,
        error: Exception,
        context: dict[str, Any],
        correlation_id: str,
        error_id: str,
        error_category: str | None = None,
        **kwargs,
    ):
        """
        Log an error with full context.

        Args:
            error: Exception that occurred
            context: Contextual data (document_id, stage, etc.)
            correlation_id: Correlation ID for tracking
            error_id: Unique error identifier
            error_category: Error category (transient/permanent)
            **kwargs: Additional fields to include
        """
        stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error else None
        stage = kwargs.pop("stage", context.get("stage"))

        log_entry = self._format_json(
            level="ERROR",
            message=str(error),
            error_id=error_id,
            correlation_id=correlation_id,
            request_id=context.get("request_id"),
            stage=stage,
            document_id=context.get("document_id"),
            error_type=type(error).__name__,
            error_category=error_category,
            stack_trace=stack_trace,
            context=context,
            **kwargs,
        )

        await self._async_write(log_entry, logging.ERROR)

    async def log_warning(self, message: str, context: dict[str, Any], correlation_id: str | None = None, **kwargs):
        """
        Log a warning message.

        Args:
            message: Warning message
            context: Contextual data
            correlation_id: Optional correlation ID
            **kwargs: Additional fields to include
        """
        log_entry = self._format_json(
            level="WARNING",
            message=message,
            correlation_id=correlation_id,
            request_id=context.get("request_id"),
            stage=context.get("stage"),
            document_id=context.get("document_id"),
            context=context,
            **kwargs,
        )

        await self._async_write(log_entry, logging.WARNING)

    async def log_info(self, message: str, context: dict[str, Any], correlation_id: str | None = None, **kwargs):
        """
        Log an info message.

        Args:
            message: Info message
            context: Contextual data
            correlation_id: Optional correlation ID
            **kwargs: Additional fields to include
        """
        log_entry = self._format_json(
            level="INFO",
            message=message,
            correlation_id=correlation_id,
            request_id=context.get("request_id"),
            stage=context.get("stage"),
            document_id=context.get("document_id"),
            context=context,
            **kwargs,
        )

        await self._async_write(log_entry, logging.INFO)

    async def log_debug(self, message: str, context: dict[str, Any], correlation_id: str | None = None, **kwargs):
        """
        Log a debug message.

        Args:
            message: Debug message
            context: Contextual data
            correlation_id: Optional correlation ID
            **kwargs: Additional fields to include
        """
        log_entry = self._format_json(
            level="DEBUG",
            message=message,
            correlation_id=correlation_id,
            request_id=context.get("request_id"),
            stage=context.get("stage"),
            document_id=context.get("document_id"),
            context=context,
            **kwargs,
        )

        await self._async_write(log_entry, logging.DEBUG)
