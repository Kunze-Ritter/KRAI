#!/usr/bin/env python3
"""
Verify Error Handling Schema (Migration 008)

Verifies that the pipeline resilience database schema is applied correctly:
- Migration 008 recorded in krai_system.migrations
- Tables: stage_completion_markers, pipeline_errors, retry_policies exist with expected columns
- Indexes on pipeline_errors and stage_completion_markers
- RPC functions: start_stage, complete_stage, fail_stage, update_stage_progress
- Test RPC execution with a temporary document

Usage:
    python scripts/verify_error_handling_schema.py
    python scripts/verify_error_handling_schema.py --verbose

Expects: DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD (env or .env)
"""

import argparse
import os
import sys
import uuid

# Load .env if present
if os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".env")):
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    except ImportError:
        pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 required. Install with: pip install psycopg2-binary")
    sys.exit(1)


def get_conn():
    """Create database connection from environment."""
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        dbname=os.getenv("DATABASE_NAME", "krai"),
        user=os.getenv("DATABASE_USER", "krai_user"),
        password=os.getenv("DATABASE_PASSWORD", "krai_secure_password"),
        cursor_factory=RealDictCursor,
    )


def check_migration(conn) -> tuple[bool, str]:
    """Verify migration 008_pipeline_resilience_schema is applied."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM krai_system.migrations WHERE migration_name = %s",
            ("008_pipeline_resilience_schema",),
        )
        row = cur.fetchone()
    if not row:
        return False, "Migration 008_pipeline_resilience_schema not found in krai_system.migrations"
    desc = row.get("description", "")
    if "stage_completion_markers" not in desc or "pipeline_errors" not in desc:
        return False, f"Migration description unexpected: {desc}"
    return True, "Migration 008 present and description matches"


def check_table(conn, schema: str, table: str, required_columns: list[str]) -> tuple[bool, str]:
    """Check table exists and has required columns."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        cols = {r["column_name"] for r in cur.fetchall()}
    if not cols:
        return False, f"Table {schema}.{table} does not exist"
    missing = set(required_columns) - cols
    if missing:
        return False, f"Table {schema}.{table} missing columns: {missing}"
    return True, f"Table {schema}.{table} has required columns"


def check_indexes(conn, table_schema: str, table_name: str, expected_index_prefixes: list[str]) -> tuple[bool, str]:
    """Check indexes exist (by prefix match on index name)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            """,
            (table_schema, table_name),
        )
        names = {r["indexname"] for r in cur.fetchall()}
    found = []
    for prefix in expected_index_prefixes:
        match = [n for n in names if n.startswith(prefix) or prefix in n]
        if match:
            found.append(prefix)
    missing = set(expected_index_prefixes) - set(found)
    if missing:
        return False, f"Indexes missing for {table_schema}.{table_name}: {missing} (found: {list(names)})"
    return True, f"Expected indexes present for {table_schema}.{table_name}"


def check_rpc_functions(conn, expected: list[str]) -> tuple[bool, str]:
    """Check RPC functions exist in krai_core (by proname)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.proname
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'krai_core' AND p.proname = ANY(%s)
            """,
            (expected,),
        )
        found = {r["proname"] for r in cur.fetchall()}
    missing = set(expected) - found
    if missing:
        return False, f"RPC functions missing in krai_core: {missing}"
    return True, f"RPC functions present: {expected}"


def test_rpc_execution(conn, verbose: bool) -> tuple[bool, str]:
    """Create test document, call start_stage, update_stage_progress, complete_stage, fail_stage; then cleanup."""
    doc_id = None
    try:
        with conn.cursor() as cur:
            # Get a valid manufacturer_id if possible
            cur.execute("SELECT id FROM krai_core.manufacturers LIMIT 1")
            mfr = cur.fetchone()
            manufacturer_id = mfr["id"] if mfr else None

            # Insert test document
            doc_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO krai_core.documents (id, filename, processing_status, stage_status)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_id, "_verify_error_handling_schema_", "pending", "{}"),
            )
            conn.commit()

            # start_stage
            cur.execute("SELECT krai_core.start_stage(%s, %s)", (doc_id, "verify_stage"))
            conn.commit()

            cur.execute(
                "SELECT stage_status FROM krai_core.documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            if not row or not row.get("stage_status"):
                return False, "start_stage: stage_status not updated"
            st = row["stage_status"].get("verify_stage") if isinstance(row["stage_status"], dict) else None
            if not st or st.get("status") != "processing":
                return False, f"start_stage: expected status=processing, got {row}"

            # update_stage_progress
            cur.execute(
                "SELECT krai_core.update_stage_progress(%s, %s, %s, %s)",
                (doc_id, "verify_stage", 50.0, "{}"),
            )
            conn.commit()

            cur.execute(
                "SELECT stage_status FROM krai_core.documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            st = row["stage_status"].get("verify_stage") if row and isinstance(row.get("stage_status"), dict) else None
            if not st or st.get("progress") != 50:
                return False, f"update_stage_progress: expected progress=50, got {st}"

            # complete_stage
            cur.execute(
                "SELECT krai_core.complete_stage(%s, %s, %s)",
                (doc_id, "verify_stage", "{}"),
            )
            conn.commit()

            cur.execute(
                "SELECT stage_status FROM krai_core.documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            st = row["stage_status"].get("verify_stage") if row and isinstance(row.get("stage_status"), dict) else None
            if not st or st.get("status") != "completed" or st.get("progress") != 100:
                return False, f"complete_stage: expected status=completed progress=100, got {st}"

            # fail_stage (on a second stage to avoid overwriting completed)
            cur.execute("SELECT krai_core.start_stage(%s, %s)", (doc_id, "verify_fail_stage"))
            conn.commit()
            cur.execute(
                "SELECT krai_core.fail_stage(%s, %s, %s, %s)",
                (doc_id, "verify_fail_stage", "Test error for verification", "{}"),
            )
            conn.commit()

            cur.execute(
                "SELECT stage_status, error_message FROM krai_core.documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            st = (
                row["stage_status"].get("verify_fail_stage")
                if row and isinstance(row.get("stage_status"), dict)
                else None
            )
            if not st or st.get("status") != "failed" or st.get("error") != "Test error for verification":
                return False, f"fail_stage: expected status=failed and error set, got {st}"
            if row.get("error_message") != "Test error for verification":
                return False, "fail_stage: document error_message not set"

        return True, "RPC execution test passed (start_stage, update_stage_progress, complete_stage, fail_stage)"
    except Exception as e:
        return False, f"RPC execution test failed: {e}"
    finally:
        if doc_id:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM krai_core.documents WHERE id = %s", (doc_id,))
                    conn.commit()
            except Exception:
                conn.rollback()


def main():
    parser = argparse.ArgumentParser(description="Verify error handling schema (migration 008)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    verbose = args.verbose

    results: list[tuple[str, bool, str]] = []

    try:
        conn = get_conn()
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    try:
        # 1. Migration
        ok, msg = check_migration(conn)
        results.append(("Migration 008_pipeline_resilience_schema", ok, msg))

        # 2. Tables
        ok, msg = check_table(
            conn,
            "krai_system",
            "stage_completion_markers",
            ["document_id", "stage_name", "completed_at", "data_hash", "metadata"],
        )
        results.append(("Table stage_completion_markers", ok, msg))

        ok, msg = check_table(
            conn,
            "krai_system",
            "pipeline_errors",
            [
                "error_id",
                "document_id",
                "stage_name",
                "error_type",
                "error_category",
                "error_message",
                "stack_trace",
                "context",
                "retry_count",
                "max_retries",
                "status",
                "is_transient",
                "correlation_id",
                "next_retry_at",
                "resolved_at",
                "resolved_by",
                "resolution_notes",
            ],
        )
        results.append(("Table pipeline_errors", ok, msg))

        ok, msg = check_table(
            conn,
            "krai_system",
            "retry_policies",
            [
                "policy_name",
                "service_name",
                "stage_name",
                "max_retries",
                "base_delay_seconds",
                "max_delay_seconds",
                "exponential_base",
                "jitter_enabled",
            ],
        )
        results.append(("Table retry_policies", ok, msg))

        # 3. Default retry policies
        with conn.cursor() as cur:
            cur.execute(
                "SELECT service_name FROM krai_system.retry_policies WHERE service_name = ANY(%s)",
                (["firecrawl", "database", "ollama", "minio"],),
            )
            services = {r["service_name"] for r in cur.fetchall()}
        expected_services = {"firecrawl", "database", "ollama", "minio"}
        missing = expected_services - services
        if missing:
            results.append(("Default retry policies", False, f"Missing policies for: {missing}"))
        else:
            results.append(("Default retry policies", True, "firecrawl, database, ollama, minio present"))

        # 4. Indexes
        ok, msg = check_indexes(
            conn,
            "krai_system",
            "pipeline_errors",
            [
                "idx_pipeline_errors_document",
                "idx_pipeline_errors_stage",
                "idx_pipeline_errors_status",
                "idx_pipeline_errors_correlation",
            ],
        )
        results.append(("Indexes pipeline_errors", ok, msg))

        ok, msg = check_indexes(
            conn,
            "krai_system",
            "stage_completion_markers",
            ["idx_completion_markers_document", "idx_completion_markers_stage"],
        )
        results.append(("Indexes stage_completion_markers", ok, msg))

        # 5. RPC functions
        ok, msg = check_rpc_functions(
            conn,
            ["start_stage", "complete_stage", "fail_stage", "update_stage_progress"],
        )
        results.append(("RPC functions", ok, msg))

        # 6. RPC execution
        ok, msg = test_rpc_execution(conn, verbose)
        results.append(("RPC execution test", ok, msg))

    finally:
        conn.close()

    # Report
    failed = [r for r in results if not r[1]]
    for name, ok, msg in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {msg}")
    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        sys.exit(1)
    print("\nAll checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
