#!/usr/bin/env python3
"""
Test Permanent Error Handling

Runs unit tests for permanent error classification (ValueError, HTTP 4xx except 408/429,
auth errors) and verifies that permanent errors are not retried and are logged correctly.

Usage:
    python scripts/test_permanent_errors.py              # Run pytest
    python scripts/test_permanent_errors.py --simulate  # Print simulation steps only
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
TESTS = os.path.join(ROOT, "backend", "tests")


def run_pytest(verbose: bool = True) -> int:
    """Run pytest for permanent error classification and no-retry behavior."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        os.path.join(TESTS, "test_retry_engine.py"),
        "-v",
        "--tb=short",
        "-k",
        "permanent or 4xx or 401 or 403 or ValueError or Authentication or Authorization or ErrorClassifier",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", ROOT)
    if ROOT not in env["PYTHONPATH"].split(os.pathsep):
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call(cmd, cwd=ROOT, env=env)


def print_simulation_steps():
    """Print documented steps to verify permanent error handling."""
    print(
        """
=== Permanent Error Simulation Steps ===

1. Validation error: Trigger processor with invalid input (e.g. corrupted PDF)
   - Verify: ValueError classified as permanent, no retry, error logged with is_transient=False

2. Authentication: Mock external API HTTP 401
   - Verify: HTTPStatusError(401) permanent, no retry

3. Authorization: Mock external API HTTP 403
   - Verify: HTTPStatusError(403) permanent, no retry

4. File not found: Non-existent file path
   - Verify: FileNotFoundError permanent, no retry

5. Logging: Trigger permanent error and check DB
   - SELECT error_category, is_transient, status, retry_count FROM krai_system.pipeline_errors
     WHERE document_id = '<id>' ORDER BY created_at DESC LIMIT 1;
   - Verify: error_category=permanent, is_transient=False, status=failed, retry_count=0

6. Correlation ID: Permanent error has single correlation_id
   - Format: req_<id>.stage_<name>.retry_0 (no retry_1, retry_2)
"""
    )


def main():
    parser = argparse.ArgumentParser(description="Test permanent error handling")
    parser.add_argument("--simulate", action="store_true", help="Print simulation steps only")
    args = parser.parse_args()

    if args.simulate:
        print_simulation_steps()
        sys.exit(0)

    sys.exit(run_pytest())


if __name__ == "__main__":
    main()
