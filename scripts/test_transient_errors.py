#!/usr/bin/env python3
"""
Test Transient Errors and Retry Behavior

Runs unit/integration tests for transient error classification and retry logic,
and documents how to simulate real-world transient failures (Ollama down, MinIO down,
PostgreSQL timeout, HTTP 503/429).

Usage:
    python scripts/test_transient_errors.py              # Run pytest only
    python scripts/test_transient_errors.py --simulate   # Print simulation steps only
    python scripts/test_transient_errors.py --all        # Run pytest and print simulation steps
"""

import argparse
import os
import subprocess
import sys

# Project root (parent of scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND = os.path.join(ROOT, "backend")
TESTS = os.path.join(ROOT, "backend", "tests")


def run_pytest(verbose: bool = True) -> int:
    """Run pytest for retry engine and error classification (transient paths)."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        os.path.join(TESTS, "test_retry_engine.py"),
        "-v",
        "--tb=short",
        "-k",
        "transient or retry or ErrorClassifier or RetryOrchestrator or backoff or correlation",
    ]
    if verbose:
        cmd.append("-v")
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", ROOT)
    if ROOT not in env["PYTHONPATH"].split(os.pathsep):
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.call(cmd, cwd=ROOT, env=env)


def print_simulation_steps():
    """Print documented steps to simulate transient errors."""
    print(
        """
=== Transient Error Simulation Steps ===

1. Simulate Ollama service down
   - Stop:  docker stop ollama   (or systemctl stop ollama)
   - Trigger: Run embedding stage (e.g. process a document that reaches embedding stage)
   - Verify: ConnectionError raised, classified as transient; retry attempted with backoff
   - Restart: docker start ollama  (or systemctl start ollama)
   - Verify: Retry succeeds after service restored

2. Simulate MinIO service down
   - Stop:  docker stop minio
   - Trigger: Storage processor (image upload)
   - Verify: ConnectionError, retry attempted
   - Restart: docker start minio
   - Verify: Retry succeeds

3. Simulate PostgreSQL connection timeout
   - Configure DB pool with low timeout or run heavy concurrent queries
   - Verify: TimeoutError classified as transient, retry attempted
   - Verify: Connection pool recovers

4. Simulate HTTP 503 / 429 (mocked)
   - Run: pytest backend/tests/test_retry_engine.py -v -k "503 or 429 or HTTP"
   - Verify: HTTPStatusError(503) and (429) classified as transient, retry with backoff

5. Retry exhaustion
   - Configure policy max_retries=2, keep service down for all attempts
   - Verify: Retries 0 (sync), 1 (async), 2 (async); final status 'failed'
   - Verify: resolution_notes populated in pipeline_errors

6. Correlation ID across retries
   - Trigger transient error and check pipeline_errors:
     SELECT correlation_id, retry_count FROM krai_system.pipeline_errors
     WHERE document_id = '<id>' ORDER BY created_at;
   - Verify: req_<id>.stage_<name>.retry_0, retry_1, retry_2

7. Advisory lock prevents concurrent retries
   - Trigger transient error (background retry holds lock)
   - Trigger same document/stage again
   - Verify: Second attempt returns retry_in_progress
   - Wait for first retry to complete; verify lock released
"""
    )


def main():
    parser = argparse.ArgumentParser(description="Test transient errors and retry behavior")
    parser.add_argument("--simulate", action="store_true", help="Print simulation steps only")
    parser.add_argument("--all", action="store_true", help="Run pytest and print simulation steps")
    parser.add_argument("--no-pytest", action="store_true", help="Skip pytest (use with --simulate)")
    args = parser.parse_args()

    if args.simulate or args.all:
        print_simulation_steps()
    if args.simulate and not args.all:
        sys.exit(0)

    exit_code = run_pytest()
    if args.all:
        print_simulation_steps()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
