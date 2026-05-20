"""Transaction management utilities for batch operations."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

try:
    import asyncpg  # type: ignore
except ImportError:  # pragma: no cover - asyncpg optional
    asyncpg = None  # type: ignore

from backend.models.batch import BatchOperationResponse, BatchOperationResult, BatchOperationResultStatus


class TransactionManager:
    """Coordinates transactional execution for batch operations."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._logger = logging.getLogger("krai.services.transaction_manager")

    @property
    def pg_pool(self) -> asyncpg.pool.Pool | None:
        """Expose the asyncpg pool."""

        return self._pool

    def has_transaction_support(self) -> bool:
        """Return True when asyncpg transaction support is available."""

        return self.pg_pool is not None

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncIterator[asyncpg.Connection | None]:  # type: ignore[name-defined]
        """Acquire a transactional connection when asyncpg is available.

        Falls back to a dummy context when no PostgreSQL pool is configured, in which
        case the caller is responsible for compensating transactions.
        """

        if not self._pool:
            self._logger.info(
                "Transaction fallback in use - asyncpg pool unavailable, executing without explicit transaction",
            )
            yield None
            return

        conn = await self._pool.acquire()
        self._logger.debug("Beginning PostgreSQL transaction")
        txn = conn.transaction()
        await txn.start()
        try:
            yield conn
            await txn.commit()
            self._logger.debug("Committed PostgreSQL transaction")
        except Exception:
            self._logger.warning("Rolling back PostgreSQL transaction due to error", exc_info=True)
            await txn.rollback()
            raise
        finally:
            await self._pool.release(conn)

    async def execute_batch_with_transaction(
        self,
        operations: Iterable[Callable[[Any | None], Awaitable[BatchOperationResult]]],
        *,
        rollback_on_error: bool = True,
        total_items: int | None = None,
        progress_callback: Callable[[BatchOperationResult, int, int, int, int], Awaitable[None]] | None = None,
    ) -> BatchOperationResponse:
        """Execute a collection of operations within a transaction scope.

        Each callable is awaited sequentially and receives the transactional connection
        when available (or ``None`` when the fallback path is used).
        """

        start_time = time.perf_counter()
        operations_list = list(operations)
        total_target = total_items if total_items is not None else len(operations_list)
        results: list[BatchOperationResult] = []
        failed = 0
        successful = 0
        processed = 0

        try:
            async with self.begin_transaction() as connection:
                for operation in operations_list:
                    try:
                        result = await operation(connection)
                        results.append(result)
                        processed += 1
                        if result.status == BatchOperationResultStatus.FAILED:
                            failed += 1
                            if rollback_on_error and self.has_transaction_support():
                                raise RuntimeError(
                                    f"Transactional operation failed: {result.error or 'unknown error'}",
                                )
                        else:
                            successful += 1

                        if progress_callback:
                            await progress_callback(result, processed, total_target, successful, failed)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        self._logger.error("Batch operation callable raised an exception", exc_info=True)
                        failed += 1
                        processed += 1
                        failure_result = BatchOperationResult(
                            id=None,
                            status=BatchOperationResultStatus.FAILED,
                            error=str(exc),
                        )
                        results.append(failure_result)
                        if progress_callback:
                            await progress_callback(failure_result, processed, total_target, successful, failed)
                        if rollback_on_error and self.has_transaction_support():
                            raise
        except Exception:
            self._logger.error("Transactional batch execution aborted", exc_info=True)
            execution_ms = int((time.perf_counter() - start_time) * 1000)
            total = total_target if total_target else processed
            return BatchOperationResponse(
                success=False,
                total=total,
                successful=max(successful, 0),
                failed=failed,
                results=results,
                execution_time_ms=execution_ms,
            )

        execution_ms = int((time.perf_counter() - start_time) * 1000)
        total = total_target if total_target else processed
        return BatchOperationResponse(
            success=failed == 0,
            total=total,
            successful=successful,
            failed=failed,
            results=results,
            execution_time_ms=execution_ms,
        )

    async def create_rollback_point(
        self,
        *,
        table: str,
        record_id: str,
        old_values: dict[str, Any],
        changed_by: str | None = None,
    ) -> str:
        """Persist a rollback point in the audit log and return its identifier."""

        rollback_point_id = str(uuid.uuid4())
        payload = {
            "table_name": table,
            "record_id": record_id,
            "operation": "ROLLBACK_POINT",
            "changed_by": changed_by,
            "old_values": old_values,
            "rollback_point_id": rollback_point_id,
            "is_rollback": False,
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Build INSERT query using asyncpg
        columns = list(payload.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = list(payload.values())

        query = f"""
            INSERT INTO krai_system.audit_log ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """

        async with self._pool.acquire() as conn:
            await conn.execute(query, *values)
        self._logger.debug("Created rollback point %s for %s", rollback_point_id, table)
        return rollback_point_id

    async def execute_rollback(self, rollback_point_id: str) -> bool:
        """Restore state using a rollback point previously recorded."""

        query = """
            SELECT table_name, record_id, old_values
            FROM krai_system.audit_log
            WHERE rollback_point_id = $1
            LIMIT 1
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, rollback_point_id)
        data = dict(result) if result else None

        if not data:
            self._logger.warning("Rollback point %s not found", rollback_point_id)
            return False

        table_name = data.get("table_name")
        record_id = data.get("record_id")
        old_values = data.get("old_values") or {}
        if not table_name or not record_id or not old_values:
            self._logger.warning("Rollback point %s incomplete; aborting rollback", rollback_point_id)
            return False

        # Update record with old values
        set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(old_values.keys())]
        update_query = f"""
            UPDATE {table_name}
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """

        async with self._pool.acquire() as conn:
            await conn.execute(update_query, record_id, *list(old_values.values()))

        # Log the rollback
        rollback_payload = {
            "table_name": table_name,
            "record_id": record_id,
            "operation": "ROLLBACK",
            "changed_by": None,
            "new_values": old_values,
            "rollback_point_id": rollback_point_id,
            "is_rollback": True,
            "created_at": datetime.now(UTC).isoformat(),
        }

        columns = list(rollback_payload.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = list(rollback_payload.values())

        audit_query = f"""
            INSERT INTO krai_system.audit_log ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """

        async with self._pool.acquire() as conn:
            await conn.execute(audit_query, *values)
        self._logger.info("Executed rollback for %s via rollback point %s", record_id, rollback_point_id)
        return True

    async def execute_compensating_transaction(self, failed_operations: Iterable[dict[str, Any]]) -> int:
        """Attempt to compensate previously successful operations.

        Each entry is expected to provide a ``rollback_data`` dictionary describing how to
        reverse the action. This method is intentionally defensive—when incomplete data is
        supplied, the operation is skipped and logged.
        """

        compensated = 0
        for item in failed_operations:
            data = item.get("rollback_data") if isinstance(item, dict) else None
            if not data:
                self._logger.debug("Skipping compensating action lacking rollback_data: %s", item)
                continue

            table_name = data.get("table")
            record_id = data.get("record_id") or data.get("id")
            old_values = data.get("old_values")
            new_values = data.get("new_values")
            operation = data.get("operation")

            if not table_name:
                self._logger.debug("Rollback data missing table name: %s", data)
                continue

            try:
                if operation == "delete" and old_values and record_id:
                    # Insert back old values
                    columns = list(old_values.keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    values = list(old_values.values())
                    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    await self._adapter.execute_query(query, values)
                    compensated += 1
                elif operation == "update" and old_values and record_id:
                    # Update with old values
                    set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(old_values.keys())]
                    query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = $1"
                    await self._adapter.execute_query(query, [record_id] + list(old_values.values()))
                    compensated += 1
                elif operation == "create" and record_id:
                    # Delete the created record
                    query = f"DELETE FROM {table_name} WHERE id = $1"
                    await self._adapter.execute_query(query, [record_id])
                    compensated += 1
                elif old_values and record_id:
                    # Default to restoring old_values when operation type is ambiguous.
                    set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(old_values.keys())]
                    query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = $1"
                    await self._adapter.execute_query(query, [record_id] + list(old_values.values()))
                    compensated += 1
                else:
                    self._logger.debug("Insufficient rollback information: %s", data)
                    continue

                # Log the compensating transaction
                audit_payload = {
                    "table_name": table_name,
                    "record_id": record_id,
                    "operation": "ROLLBACK",
                    "changed_by": None,
                    "rollback_point_id": data.get("rollback_point_id"),
                    "is_rollback": True,
                    "old_values": old_values,
                    "new_values": new_values,
                    "created_at": datetime.now(UTC).isoformat(),
                }

                columns = list(audit_payload.keys())
                placeholders = [f"${i+1}" for i in range(len(columns))]
                values = list(audit_payload.values())

                audit_query = (
                    f"INSERT INTO krai_system.audit_log ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                )
                await self._adapter.execute_query(audit_query, values)

            except Exception:  # pragma: no cover - defensive logging
                self._logger.error("Compensating transaction failed for %s", data, exc_info=True)

        return compensated

    async def validate_transaction_scope(self, operations: Iterable[dict[str, Any]]) -> bool:
        """Validate that all operations target the same table for transactional safety."""

        tables = {op.get("table") for op in operations if isinstance(op, dict)}
        if not tables:
            return False
        return len(tables) == 1

    async def estimate_transaction_size(self, operations: Iterable[dict[str, Any]]) -> int:
        """Estimate the approximate payload size for a transaction in bytes."""

        size = 0
        for op in operations:
            if isinstance(op, dict):
                size += len(str(op).encode("utf-8"))
        return size


# Circular import avoidance: DatabaseAdapter is only needed for type checking.
