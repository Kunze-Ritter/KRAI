#!/usr/bin/env python3
"""
Test Correlation ID Format and Tracking

Verifies:
- Format: {request_id}.stage_{stage_name}.retry_{retry_attempt}
- Correlation ID in error logging (DB + JSON)
- Correlation ID in retry chain (retry_0, retry_1, ...)
- Query errors by correlation_id prefix

Usage:
    python scripts/test_correlation_ids.py              # Run format checks and pytest
    python scripts/test_correlation_ids.py --doc      # Print verification steps only
"""

import argparse
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT)


def test_correlation_id_format():
    """Verify correlation ID format without database."""
    from backend.core.retry_engine import RetryOrchestrator

    request_id = "req_a3f2e8d1"
    stage_name = "image_processing"
    for attempt in (0, 1, 2):
        cid = RetryOrchestrator.generate_correlation_id(request_id, stage_name, attempt)
        assert cid == f"req_a3f2e8d1.stage_image_processing.retry_{attempt}", cid
    # Pattern: request_id.stage_<name>.retry_<n>
    pattern = re.compile(r"^req_[a-f0-9]+\.stage_[a-z_]+\.retry_\d+$")
    assert pattern.match("req_a3f2e8d1.stage_image_processing.retry_0")
    assert pattern.match("req_abc.stage_embedding.retry_1")
    print("  [PASS] Correlation ID format: request_id.stage_<name>.retry_<n>")
    return True


def run_pytest() -> int:
    """Run pytest for correlation ID and error logging tests."""
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        os.path.join(ROOT, "backend", "tests", "test_retry_engine.py"),
        os.path.join(ROOT, "backend", "tests", "test_error_logging.py"),
        "-v",
        "--tb=short",
        "-k",
        "correlation or correlation_id or generate_correlation",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", ROOT)
    return subprocess.call(cmd, cwd=ROOT, env=env)


def print_doc():
    """Print verification steps for correlation ID tracking."""
    print(
        """
=== Correlation ID Verification Steps ===

1. Format: RetryOrchestrator.generate_correlation_id(request_id, stage_name, retry_attempt)
   - Example: req_a3f2e8d1.stage_image_processing.retry_0

2. In error logging: log_error(..., correlation_id=...)
   - pipeline_errors.correlation_id stored
   - JSON log contains correlation_id

3. Query by correlation_id:
   SELECT * FROM krai_system.pipeline_errors
   WHERE correlation_id LIKE 'req_<id>%' ORDER BY created_at;

4. Retry chain: retry_0, retry_1, retry_2 for same request_id/stage
   - context.correlation_id and context.retry_attempt updated per retry
   - result.correlation_id and result.error_id in ProcessingResult
"""
    )


def main():
    parser = argparse.ArgumentParser(description="Test correlation ID format and tracking")
    parser.add_argument("--doc", action="store_true", help="Print verification steps only")
    args = parser.parse_args()

    if args.doc:
        print_doc()
        sys.exit(0)

    try:
        test_correlation_id_format()
    except Exception as e:
        print(f"  [FAIL] Correlation ID format: {e}")
        sys.exit(1)

    sys.exit(run_pytest())


if __name__ == "__main__":
    main()
