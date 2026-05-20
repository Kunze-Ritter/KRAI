"""
Test script for improved colored logging system
Demonstrates all logging features
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from backend.utils.colored_logging import (
    apply_colored_logging_globally,
    log_duration,
    log_metric,
    log_progress,
    log_section,
)


def test_logging():
    """Test all logging features"""

    # Setup colored logging
    apply_colored_logging_globally(level=logging.DEBUG)
    logger = logging.getLogger("test.logger")

    print("\n" + "=" * 80)
    print("COLORED LOGGING SYSTEM TEST".center(80))
    print("=" * 80 + "\n")

    # Test section header
    log_section("STAGE 1: Basic Logging Levels")

    # Test all log levels
    logger.debug("This is a debug message for detailed troubleshooting")
    time.sleep(0.3)

    logger.info("This is an info message with important information")
    time.sleep(0.3)

    logger.success("This is a success message - operation completed!")
    time.sleep(0.3)

    logger.warning("This is a warning message - something might be wrong")
    time.sleep(0.3)

    logger.error("This is an error message - something went wrong")
    time.sleep(0.3)

    logger.critical("This is a critical message - system failure!")
    time.sleep(0.5)

    # Test section with different separator
    log_section("STAGE 2: Progress Indicators", char="-")

    # Simulate progress
    total_items = 10
    for i in range(total_items + 1):
        log_progress(i, total_items, f"Processing item {i}", "test.progress")
        time.sleep(0.2)

    logger.success("All items processed successfully")
    time.sleep(0.5)

    # Test metrics
    log_section("STAGE 3: Metrics & Performance")

    log_metric("Documents Processed", 42, "files", "test.metrics")
    time.sleep(0.2)

    log_metric("Errors Found", 3, "errors", "test.metrics")
    time.sleep(0.2)

    log_metric("Success Rate", "92.5%", "", "test.metrics")
    time.sleep(0.2)

    log_duration("Total Processing Time", 154.7, "test.metrics")
    time.sleep(0.2)

    log_duration("Average per Document", 3.68, "test.metrics")
    time.sleep(0.5)

    # Test long logger names
    log_section("STAGE 4: Edge Cases")

    long_logger = logging.getLogger("very.long.nested.logger.name.that.should.be.shortened")
    long_logger.info("This logger has a very long name that will be shortened")
    time.sleep(0.3)

    # Test multiline messages
    logger.info("This is a message\nwith multiple lines\nfor better readability")
    time.sleep(0.3)

    # Test exception logging
    try:
        1 / 0
    except Exception:
        logger.error("Exception occurred during division", exc_info=True)

    time.sleep(0.5)

    # Final section
    log_section("TEST COMPLETE", char="=", width=80)
    logger.success("Logging system test completed successfully!")

    print("\n" + "=" * 80)
    print("All logging features demonstrated!".center(80))
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_logging()
