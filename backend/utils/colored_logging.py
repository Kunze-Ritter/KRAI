"""
Colored Logging - Improved Terminal Output
Cyan = INFO, Yellow = WARNING, Red = ERROR, Green = SUCCESS
"""

import logging
import sys


# ANSI Color Codes
class Colors:
    """ANSI Color codes for terminal output"""

    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Backgrounds
    BG_RED = "\033[101m"
    BG_YELLOW = "\033[103m"
    BG_GREEN = "\033[102m"


# Custom log level for SUCCESS
SUCCESS = 25  # Between INFO (20) and WARNING (30)
logging.addLevelName(SUCCESS, "SUCCESS")


class ColoredFormatter(logging.Formatter):
    """Custom formatter with improved colored output"""

    def __init__(self, *args, compact=False, **kwargs):
        """
        Initialize formatter

        Args:
            compact: If True, uses single-line format. If False, uses two-line format.
        """
        super().__init__(*args, **kwargs)
        self.compact = compact

    # Level colors and icons
    LEVEL_CONFIG = {
        logging.DEBUG: {"color": Colors.GRAY, "icon": "🔍", "label": "DEBUG"},
        logging.INFO: {"color": Colors.CYAN, "icon": "ℹ️ ", "label": "INFO"},
        SUCCESS: {"color": Colors.GREEN, "icon": "✅", "label": "SUCCESS"},
        logging.WARNING: {"color": Colors.YELLOW, "icon": "⚠️ ", "label": "WARNING"},
        logging.ERROR: {"color": Colors.RED, "icon": "❌", "label": "ERROR"},
        logging.CRITICAL: {"color": Colors.BG_RED + Colors.WHITE + Colors.BOLD, "icon": "🔥", "label": "CRITICAL"},
    }

    def format(self, record):
        # Get configuration for this log level
        config = self.LEVEL_CONFIG.get(record.levelno, {"color": Colors.WHITE, "icon": "•", "label": record.levelname})

        # Format timestamp
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        # Get logger name (shortened if too long)
        logger_name = record.name
        if len(logger_name) > 30:
            # Shorten long logger names
            parts = logger_name.split(".")
            if len(parts) > 2:
                logger_name = f"{parts[0]}...{parts[-1]}"

        # Get colors and icons
        color = config["color"]
        icon = config["icon"]
        label = config["label"]
        message = record.getMessage()

        if self.compact:
            # COMPACT MODE: Single line with timestamp
            timestamp_str = f"{Colors.WHITE}{Colors.BOLD}{timestamp}{Colors.RESET}"
            colored_line = f"{timestamp_str} {color}{icon} [{label:8}] " f"{logger_name:25} │ {message}{Colors.RESET}"
            result = colored_line
        else:
            # TWO-LINE MODE: Timestamp on separate line
            timestamp_str = f"{Colors.WHITE}{Colors.BOLD}{timestamp}{Colors.RESET}"
            colored_line = f"{color}{icon} [{label:8}] " f"{logger_name:30} │ {message}{Colors.RESET}"
            result = f"{timestamp_str}\n{colored_line}"

        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            result += f"\n{color}{exc_text}{Colors.RESET}"

        return result


def setup_colored_logging(logger_name=None, level=logging.INFO, compact=True):
    """
    Setup colored logging for a logger

    Args:
        logger_name: Name of logger (None = root logger)
        level: Logging level (default: INFO)
        compact: If True, single-line format. If False, two-line format (default: True)

    Returns:
        Logger instance with colored output
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create console handler with colored formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Set colored formatter
    colored_formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", compact=compact
    )
    console_handler.setFormatter(colored_formatter)

    logger.addHandler(console_handler)

    # Prevent duplicate logs
    logger.propagate = False

    return logger


def apply_colored_logging_globally(level=logging.INFO, compact=True):
    """
    Apply colored logging to ALL loggers

    Args:
        level: Logging level (default: INFO)
        compact: If True, single-line format. If False, two-line format (default: True)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove all existing handlers
    root_logger.handlers = []

    # Add colored console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    colored_formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", compact=compact
    )
    console_handler.setFormatter(colored_formatter)

    root_logger.addHandler(console_handler)

    return root_logger


# Add success method to Logger class
def success(self, message, *args, **kwargs):
    """Log a success message"""
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


logging.Logger.success = success


# Convenience functions
def log_success(message, logger_name=None):
    """Log success message in GREEN"""
    logger = logging.getLogger(logger_name)
    logger.success(message)


def log_error(message, logger_name=None):
    """Log error message in RED"""
    logger = logging.getLogger(logger_name)
    logger.error(message)


def log_warning(message, logger_name=None):
    """Log warning message in YELLOW"""
    logger = logging.getLogger(logger_name)
    logger.warning(message)


def log_info(message, logger_name=None):
    """Log info message in CYAN"""
    logger = logging.getLogger(logger_name)
    logger.info(message)


# Keep old function names for backwards compatibility
success = log_success
error = log_error
warning = log_warning
info = log_info


# Additional helper functions
def log_section(title, logger_name=None, char="=", width=80):
    """
    Log a section header for better visual separation

    Example:
        ========================================
        STAGE 5: Metadata Extraction
        ========================================
    """
    separator = char * width

    # Print without timestamp for cleaner look
    print(f"\n{Colors.BOLD}{Colors.CYAN}{separator}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(width)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{separator}{Colors.RESET}\n")


def log_progress(current, total, message="", logger_name=None):
    """
    Log progress with a visual indicator

    Example: [=====>    ] 50% - Processing images...
    """
    logger = logging.getLogger(logger_name)

    if total == 0:
        percentage = 100
    else:
        percentage = int((current / total) * 100)

    # Create progress bar (20 chars wide)
    bar_width = 20
    filled = int(bar_width * current / total) if total > 0 else bar_width
    bar = "=" * filled + ">" if filled < bar_width else "=" * bar_width
    bar = bar.ljust(bar_width)

    progress_msg = f"[{bar}] {percentage:3d}% ({current}/{total})"
    if message:
        progress_msg += f" - {message}"

    logger.info(progress_msg)


def log_metric(name, value, unit="", logger_name=None):
    """
    Log a metric in a structured format

    Example: 📊 Documents Processed: 42 files
    """
    logger = logging.getLogger(logger_name)
    metric_msg = f"📊 {name}: {value}"
    if unit:
        metric_msg += f" {unit}"

    logger.info(metric_msg)


def log_duration(name, seconds, logger_name=None):
    """
    Log duration in human-readable format

    Example: ⏱️  Processing Time: 2m 34s
    """
    logger = logging.getLogger(logger_name)

    if seconds < 60:
        duration_str = f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        duration_str = f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        duration_str = f"{hours}h {minutes}m"

    logger.info(f"⏱️  {name}: {duration_str}")
