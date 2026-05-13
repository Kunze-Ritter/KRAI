"""
Beautiful logging setup for processor V2

Uses rich for colored, formatted console output.
"""

import hashlib
import io
import logging
import os
import re
import sys
from datetime import datetime
from logging import Handler
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
    logging.warning("'rich' not installed. Install with: pip install rich. Falling back to basic logging.")


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read integer environment variable with fallback."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


_SANITIZE_MAX_LEN = max(16, _env_int("LOG_SANITIZE_MAX_LEN", 256))
_PII_PATTERNS = (
    (re.compile(r"\b[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\+?\d[\d\s\-()]{7,}\d\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b\d{9,}\b"), "[REDACTED_NUMBER]"),
)


def _mask_pii(text: str) -> str:
    """Mask common PII entities such as emails, phone numbers, and long numbers."""
    masked = text
    for pattern, replacement in _PII_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def sanitize_text(text: str | None, max_length: int | None = None) -> str:
    """
    Apply PII masking and truncate overly long strings for safe logging.

    Args:
        text: Original text value
        max_length: Maximum length after truncation (defaults to LOG_SANITIZE_MAX_LEN)

    Returns:
        Sanitized textual preview suitable for debug output
    """
    if not text:
        return ""

    sanitized = _mask_pii(text)
    limit = max_length or _SANITIZE_MAX_LEN
    if len(sanitized) <= limit:
        return sanitized
    return f"{sanitized[:limit]}… (+{len(sanitized) - limit} chars)"


def sanitize_document_name(name: str | None) -> str:
    """Hash document-identifying names when LOG_REDACT is enabled."""
    if not name:
        return ""

    if _env_bool("LOG_REDACT", False):
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        return f"doc:{digest}"
    return name


def text_stats(text: str | None) -> dict[str, Any]:
    """Return aggregate statistics about a text payload without exposing content."""
    if not text:
        return {"length": 0, "words": 0, "empty": True}

    masked = _mask_pii(text)
    summary: dict[str, Any] = {
        "length": len(masked),
        "words": len(masked.split()),
        "empty": False,
    }

    if len(masked) > _SANITIZE_MAX_LEN:
        summary["truncated"] = True

    if _env_bool("LOG_REDACT", False):
        summary["sha256"] = hashlib.sha256(masked.encode("utf-8")).hexdigest()[:12]

    return summary


def summarize_payload(payload: Any) -> dict[str, Any]:
    """Generate a structure-free summary for logging without exposing raw data."""
    summary: dict[str, Any] = {"type": type(payload).__name__}

    if isinstance(payload, str):
        summary.update(text_stats(payload))
        return summary

    if isinstance(payload, bytes | bytearray):
        summary["length"] = len(payload)
        summary["empty"] = len(payload) == 0
        return summary

    if isinstance(payload, dict):
        summary["keys"] = len(payload)
        summary["key_sample"] = sorted(payload.keys())[:5]
        if "embedding" in payload and isinstance(payload["embedding"], list):
            summary["embedding_length"] = len(payload["embedding"])
        if "prompt" in payload and isinstance(payload["prompt"], str):
            summary["prompt_stats"] = text_stats(payload["prompt"])
        return summary

    if isinstance(payload, list | tuple | set):
        summary["items"] = len(payload)
        return summary

    summary["repr"] = sanitize_text(str(payload)) if payload is not None else ""
    return summary


class ProcessorLogger:
    """Enhanced logger with rich formatting"""

    def __init__(self, name: str = "processor_v2", log_file: Path | None = None):
        self.name = name
        self.log_file = log_file
        self.logger = self._setup_logger()
        self.console: Console | None = None

        if RICH_AVAILABLE:
            self.console = Console()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger with rich handler"""
        logger = logging.getLogger(self.name)
        log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        logger.setLevel(log_level)

        # Remove existing handlers
        logger.handlers.clear()

        console_enabled = _env_bool("LOG_TO_CONSOLE", True)
        console_handler: Handler | None = None

        if RICH_AVAILABLE:
            # Rich console handler
            if console_enabled:
                console_handler = RichHandler(
                    rich_tracebacks=True,
                    markup=True,
                    show_time=True,
                    show_path=False,
                )
                console_handler.setLevel(log_level)
                logger.addHandler(console_handler)
        else:
            # Fallback to basic handler with UTF-8 encoding
            # Force UTF-8 encoding for Windows compatibility with Unicode characters
            if console_enabled:
                try:
                    # Try to wrap stdout.buffer if available
                    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
                    console_handler = logging.StreamHandler(utf8_stdout)
                except AttributeError:
                    # stdout.buffer not available (already wrapped), use stdout directly
                    console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(log_level)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
                )
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

        # File handler (always basic format with UTF-8 encoding)
        log_to_file = _env_bool("LOG_TO_FILE", True) or self.log_file is not None
        if log_to_file:
            log_dir_env = os.getenv("LOG_DIR")
            if log_dir_env:
                log_dir = Path(log_dir_env)
            else:
                log_dir = Path(self.log_file).parent if self.log_file else Path(__file__).parent.parent / "logs"

            log_dir.mkdir(parents=True, exist_ok=True)

            if self.log_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.log_file = log_dir / f"{self.name}_{timestamp}.log"
            else:
                self.log_file = Path(self.log_file)

            rotation_mode = os.getenv("LOG_ROTATION", "size").lower()
            backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

            file_handler: TimedRotatingFileHandler | RotatingFileHandler
            if rotation_mode == "time":
                file_handler = TimedRotatingFileHandler(
                    self.log_file,
                    when=os.getenv("LOG_ROTATION_WHEN", "midnight"),
                    interval=int(os.getenv("LOG_ROTATION_INTERVAL", "1")),
                    backupCount=backup_count,
                    encoding="utf-8",
                )
            else:
                max_bytes = int(os.getenv("LOG_MAX_BYTES", str(10_000_000)))
                file_handler = RotatingFileHandler(
                    self.log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
                )

            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        logger.propagate = False
        return logger

    def info(self, *args: Any, **kwargs: Any):
        """Proxy info logging with support for arbitrary arguments."""
        self.logger.info(*args, **kwargs)

    def success(self, message: str, *args: Any, **kwargs: Any):
        """Log success message"""
        if RICH_AVAILABLE:
            # Remove emoji for Windows compatibility
            wrapped = f"[green]{message}[/green]"
            self.logger.info(wrapped, *args, **kwargs)
        else:
            wrapped = f"[OK] {message}"
            self.logger.info(wrapped, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any):
        """Log warning message"""
        if RICH_AVAILABLE:
            wrapped = f"[yellow]{message}[/yellow]"
            self.logger.warning(wrapped, *args, **kwargs)
        else:
            wrapped = f"[WARN] {message}"
            self.logger.warning(wrapped, *args, **kwargs)

    def error(self, message: str, *args: Any, exc: Exception | None = None, **kwargs: Any):
        """Log error message"""
        if RICH_AVAILABLE:
            wrapped = f"[red]{message}[/red]"
            self.logger.error(wrapped, *args, **kwargs)
        else:
            wrapped = f"[ERROR] {message}"
            self.logger.error(wrapped, *args, **kwargs)

        if exc:
            self.logger.exception(exc)

    def debug(self, *args: Any, **kwargs: Any):
        """Proxy debug logging with support for arbitrary arguments."""
        self.logger.debug(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        """Delegate unknown attributes to underlying logger."""
        return getattr(self.logger, item)

    def section(self, title: str):
        """Print section header"""
        if RICH_AVAILABLE and self.console:
            self.console.rule(f"[bold blue]{title}[/bold blue]")
        else:
            self.logger.info("\n%s", "=" * 60)
            self.logger.info("%s", title)
            self.logger.info("%s", "=" * 60)

    def panel(self, content: str, title: str = "", style: str = "blue"):
        """Print content in a panel"""
        if RICH_AVAILABLE and self.console:
            self.console.print(Panel(content, title=title, style=style))
        else:
            if title:
                self.logger.info("\n%s", title)
            self.logger.info("%s", content)
            self.logger.info("")

    def table(self, data: dict, title: str = ""):
        """Print data as table"""
        if RICH_AVAILABLE and self.console:
            table = Table(title=title, show_header=True)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="green")

            for key, value in data.items():
                table.add_row(str(key), str(value))

            self.console.print(table)
        else:
            if title:
                self.logger.info("\n%s:", title)
            for key, value in data.items():
                self.logger.info("  %s: %s", key, value)

    def progress_bar(self, items: list, description: str = "Processing"):
        """Return progress bar context manager"""
        if RICH_AVAILABLE:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
            )

        # Fallback: simple counter
        class SimpleProgress:
            class _Task:
                def __init__(self, description, total):
                    self.description = description
                    self.total = total
                    self.completed = 0

            def __init__(self, logger):
                self._logger = logger
                self.tasks = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def add_task(self, description, total):
                task_id = len(self.tasks)
                task = self._Task(description, total)
                self.tasks[task_id] = task
                self._logger.debug("Starting task '%s' with total %s", description, total)
                return task_id

            def update(self, task_id, advance=1, **kwargs):
                task = self.tasks.get(task_id)
                if task is None:
                    self._logger.debug("Received update for unknown task_id %s", task_id)
                    return

                description = kwargs.get("description")
                if description:
                    task.description = description

                task.completed += advance
                task.completed = min(task.completed, task.total)
                self._logger.debug("%s: %s/%s", task.description, task.completed, task.total)
                if task.completed >= task.total:
                    self._logger.debug("%s completed", task.description)

        return SimpleProgress(self.logger)


# Global logger instance
_logger_instance: ProcessorLogger | None = None


def get_logger(name: str = "processor_v2", log_file: Path | None = None) -> ProcessorLogger:
    """
    Get or create logger instance

    Args:
        name: Logger name
        log_file: Optional file to log to

    Returns:
        ProcessorLogger instance
    """
    global _logger_instance

    if _logger_instance is None:
        if log_file is None:
            # Default log file location
            log_dir = Path(__file__).parent.parent / "logs"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"processor_v2_{timestamp}.log"

        _logger_instance = ProcessorLogger(name, log_file)

    return _logger_instance


def log_processing_summary(logger: ProcessorLogger, stats: dict, duration_seconds: float):
    """
    Log pretty processing summary

    Args:
        logger: Logger instance
        stats: Dictionary with processing statistics
        duration_seconds: Total processing time
    """
    logger.section("Processing Summary")

    summary = {
        "Duration": f"{duration_seconds:.2f}s",
        "Documents Processed": stats.get("documents_processed", 0),
        "Chunks Created": stats.get("chunks_created", 0),
        "Embeddings Generated": stats.get("embeddings_created", 0),
        "Products Extracted": stats.get("products_extracted", 0),
        "Error Codes Found": stats.get("error_codes_extracted", 0),
        "Validation Failures": stats.get("validation_failures", 0),
        "Average Confidence": f"{stats.get('avg_confidence', 0):.2f}",
    }

    logger.table(summary, title="📊 Statistics")

    # Success/warning/error summary
    if stats.get("validation_failures", 0) > 0:
        logger.warning(f"Had {stats['validation_failures']} validation failures - check logs!")

    if stats.get("avg_confidence", 1.0) < 0.7:
        logger.warning(
            f"Average confidence is low ({stats['avg_confidence']:.2f}) - " "extracted data may be unreliable"
        )

    logger.success(f"Processing completed in {duration_seconds:.2f}s")


# Example usage
if __name__ == "__main__":
    # Test logger
    logger = get_logger()

    logger.section("Testing Logger")
    logger.info("This is an info message")
    logger.success("This is a success message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.debug("This is a debug message (won't show unless DEBUG level)")

    logger.panel("This is panel content", title="Test Panel", style="green")

    test_data = {"chunks_created": 150, "embeddings": 145, "confidence": 0.85}
    logger.table(test_data, title="Test Table")

    logger.success("Logger test complete!")
