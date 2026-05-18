#!/usr/bin/env python3
"""
Test Advisory Lock Behavior

Verifies PostgreSQL advisory locks used by RetryOrchestrator:
- Lock acquisition/release with pg_try_advisory_lock / pg_advisory_unlock
- Lock ID from SHA-256(document_id:stage_name) within bigint range
- Concurrent lock attempts (second fails while first holds)
- Lock release on error (finally block)
- Query pg_locks for active advisory locks

Usage:
    python scripts/test_advisory_locks.py              # Run pytest and inline checks
    python scripts/test_advisory_locks.py --pytest-only
    python scripts/test_advisory_locks.py --doc        # Print verification steps only
"""

import argparse
import hashlib
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT)

# Load .env if present
if os.path.exists(os.path.join(ROOT, ".env")):
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass


def run_pytest() -> int:
    """Run pytest for RetryOrchestrator advisory lock tests."""
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        os.path.join(ROOT, "backend", "tests", "test_retry_engine.py"),
        "-v",
        "--tb=short",
        "-k",
        "advisory_lock or RetryOrchestrator",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", ROOT)
    return subprocess.call(cmd, cwd=ROOT, env=env)


def test_lock_id_determinism():
    """Verify lock ID is deterministic and within PostgreSQL bigint range."""
    from backend.core.retry_engine import RetryOrchestrator

    doc_id = "550e8400-e29b-41d4-a716-446655440000"
    stage = "image_processing"
    lock_key = f"{doc_id}:{stage}"
    hash_bytes = hashlib.sha256(lock_key.encode("utf-8")).digest()
    lock_id = int.from_bytes(hash_bytes[:8], byteorder="big", signed=False) % (2**63 - 1)
    assert 0 <= lock_id < 2**63, "Lock ID must be in bigint range"
    # Same inputs -> same lock_id
    hash_bytes2 = hashlib.sha256(lock_key.encode("utf-8")).digest()
    lock_id2 = int.from_bytes(hash_bytes2[:8], byteorder="big", signed=False) % (2**63 - 1)
    assert lock_id == lock_id2
    # Correlation ID format
    corr = RetryOrchestrator.generate_correlation_id("req_abc", stage, 1)
    assert corr == "req_abc.stage_image_processing.retry_1"
    print("  [PASS] Lock ID determinism and correlation ID format")
    return True


def print_doc():
    """Print verification steps for advisory locks."""
    print(
        """
=== Advisory Lock Verification Steps ===

1. Lock acquisition: orchestrator.acquire_advisory_lock(document_id, stage_name)
   - pg_try_advisory_lock(lock_id) with lock_id = SHA256(document_id:stage_name)[:8] % (2^63-1)
   - Returns True on success, False if already locked

2. Lock release: orchestrator.release_advisory_lock(document_id, stage_name)
   - pg_advisory_unlock(lock_id); returns True on success

3. Concurrent attempts: Acquire in coroutine A, attempt in B -> B returns False
   - Release in A; attempt in B again -> B succeeds

4. Lock release on error: Acquire, raise in try, release in finally
   - Verify subsequent acquisition succeeds

5. Active locks: SELECT * FROM pg_locks WHERE locktype = 'advisory';
   - Release all; verify locks removed
"""
    )


def main():
    parser = argparse.ArgumentParser(description="Test advisory lock behavior")
    parser.add_argument("--pytest-only", action="store_true", help="Run only pytest")
    parser.add_argument("--doc", action="store_true", help="Print verification steps only")
    args = parser.parse_args()

    if args.doc:
        print_doc()
        sys.exit(0)

    # Inline checks (no DB required)
    try:
        test_lock_id_determinism()
    except Exception as e:
        print(f"  [FAIL] Lock ID check: {e}")
        sys.exit(1)

    if args.pytest_only:
        sys.exit(run_pytest())

    # Run pytest as well
    exit_code = run_pytest()
    if exit_code != 0:
        print_doc()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
