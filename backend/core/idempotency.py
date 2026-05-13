"""
Idempotency Service for Pipeline Processing

This module provides idempotency checking and completion marker management
for pipeline stages. It ensures that processing stages are not re-executed
unnecessarily and handles data change detection through SHA-256 hashing.

Example Usage:
    ```python
    checker = IdempotencyChecker(db_adapter)

    # Check if stage already completed
    marker = await checker.check_completion_marker(doc_id, "pdf_extraction")
    if marker:
        current_hash = checker.compute_data_hash(context)
        if marker['data_hash'] == current_hash:
            # Skip processing - already done
            return cached_result
        else:
            # Data changed - cleanup and re-process
            await checker.cleanup_old_data(doc_id, "pdf_extraction")

    # Process the stage...
    result = await process_stage(context)

    # Mark as completed
    await checker.set_completion_marker(
        doc_id,
        "pdf_extraction",
        current_hash,
        {"processing_time": 1.5, "pages": 100}
    )
    ```
"""

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from backend.services.database_adapter import DatabaseAdapter

if TYPE_CHECKING:
    from backend.core.types import ProcessingContext


def compute_context_hash(context: "ProcessingContext") -> str:
    """
    Compute SHA-256 hash of relevant context fields (standalone function).

    This function is decoupled from the IdempotencyChecker class and can be
    used without a database adapter. It creates a deterministic hash based on
    document metadata and processing context.

    The hash includes: document_id, file_path, file_hash, file_size,
    manufacturer, model, series, and version.

    Args:
        context: Processing context containing document metadata

    Returns:
        64-character hexadecimal SHA-256 hash string

    Example:
        ```python
        from backend.core.idempotency import compute_context_hash
        from backend.core.types import ProcessingContext

        context = ProcessingContext(document_id="doc-123", ...)
        hash_value = compute_context_hash(context)
        print(f"Hash: {hash_value}")  # 64 hex characters
        ```
    """
    hash_data = {
        "document_id": context.document_id,
        "file_path": context.file_path,
        "file_hash": context.file_hash,
        "file_size": context.file_size,
        "manufacturer": context.manufacturer,
        "model": context.model,
        "series": context.series,
        "version": context.version,
    }

    json_str = json.dumps(hash_data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


class IdempotencyChecker:
    """
    Service class for managing idempotency in pipeline processing.

    This class handles completion marker checks, data hash computation,
    and cleanup operations to ensure pipeline stages are idempotent.

    Attributes:
        db_adapter: Database adapter for executing queries
        logger: Logger instance for tracking operations
    """

    def __init__(self, db_adapter: DatabaseAdapter):
        """
        Initialize the IdempotencyChecker.

        Args:
            db_adapter: Database adapter instance for database operations
        """
        self.db_adapter = db_adapter
        self.logger = logging.getLogger(__name__)

    async def check_completion_marker(self, document_id: str, stage_name: str) -> dict[str, Any] | None:
        """
        Check if a completion marker exists for a document and stage.

        Queries the krai_system.stage_completion_markers table to determine
        if a stage has already been completed for a document.

        Args:
            document_id: Unique identifier for the document
            stage_name: Name of the processing stage

        Returns:
            Dictionary containing marker data if found, None otherwise.
            Marker data includes: document_id, stage_name, completed_at,
            data_hash, and metadata (JSONB).

        Raises:
            None - Errors are logged and None is returned

        Example:
            ```python
            marker = await checker.check_completion_marker(
                "doc-123",
                "pdf_extraction"
            )
            if marker:
                print(f"Completed at: {marker['completed_at']}")
                print(f"Data hash: {marker['data_hash']}")
            ```
        """
        if not document_id:
            self.logger.debug(f"Skipping completion marker check for stage {stage_name}: document_id not yet assigned")
            return None

        query = """
            SELECT document_id, stage_name, completed_at, data_hash, metadata
            FROM krai_system.stage_completion_markers
            WHERE document_id = %(document_id)s AND stage_name = %(stage_name)s
        """

        try:
            result = await self.db_adapter.fetch_one(query, {"document_id": document_id, "stage_name": stage_name})

            if result:
                self.logger.debug(f"Completion marker found for document {document_id}, " f"stage {stage_name}")
            else:
                self.logger.debug(f"No completion marker found for document {document_id}, " f"stage {stage_name}")

            return result

        except Exception as e:
            self.logger.error(
                f"Error checking completion marker for document {document_id}, " f"stage {stage_name}: {e}",
                exc_info=True,
            )
            return None

    async def set_completion_marker(
        self, document_id: str, stage_name: str, data_hash: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Set or update a completion marker for a document and stage.

        Uses PostgreSQL's ON CONFLICT clause to perform an upsert operation,
        ensuring that markers are created or updated atomically.

        Args:
            document_id: Unique identifier for the document
            stage_name: Name of the processing stage
            data_hash: SHA-256 hash of input data (64 hex characters)
            metadata: Optional metadata to store (processing time, output summary, etc.)

        Returns:
            True if marker was set successfully, False otherwise

        Raises:
            None - Errors are logged and False is returned

        Example:
            ```python
            success = await checker.set_completion_marker(
                "doc-123",
                "pdf_extraction",
                "a1b2c3d4...",
                {
                    "processing_time": 1.5,
                    "pages_extracted": 100,
                    "retry_count": 0,
                    "processor_version": "1.0.0"
                }
            )
            ```
        """
        if not document_id:
            self.logger.debug(f"Skipping set_completion_marker for stage {stage_name}: document_id not yet assigned")
            return False

        query = """
            INSERT INTO krai_system.stage_completion_markers
            (document_id, stage_name, data_hash, metadata, completed_at)
            VALUES (%(document_id)s, %(stage_name)s, %(data_hash)s, %(metadata)s, CURRENT_TIMESTAMP)
            ON CONFLICT (document_id, stage_name)
            DO UPDATE SET
                data_hash = %(data_hash)s,
                metadata = %(metadata)s,
                completed_at = CURRENT_TIMESTAMP
        """

        try:
            metadata_json = json.dumps(metadata or {}, default=str)
            await self.db_adapter.execute_query(
                query,
                {
                    "document_id": document_id,
                    "stage_name": stage_name,
                    "data_hash": data_hash,
                    "metadata": metadata_json,
                },
            )

            self.logger.info(f"Completion marker set for document {document_id}, " f"stage {stage_name}")
            return True

        except Exception as e:
            self.logger.error(
                f"Error setting completion marker for document {document_id}, " f"stage {stage_name}: {e}",
                exc_info=True,
            )
            return False

    def compute_data_hash(self, context: "ProcessingContext") -> str:
        """
        Compute SHA-256 hash of relevant context fields.

        Creates a deterministic hash based on document metadata and processing
        context. This hash is used to detect when input data has changed and
        re-processing is needed.

        This method delegates to the standalone compute_context_hash function.

        The hash includes: document_id, file_path, file_hash, file_size,
        manufacturer, model, series, and version.

        Args:
            context: Processing context containing document metadata

        Returns:
            64-character hexadecimal SHA-256 hash string

        Example:
            ```python
            hash1 = checker.compute_data_hash(context1)
            hash2 = checker.compute_data_hash(context2)

            if hash1 == hash2:
                print("Data unchanged")
            else:
                print("Data changed - re-processing needed")
            ```
        """
        hash_value = compute_context_hash(context)

        self.logger.debug(f"Computed data hash for document {context.document_id}: {hash_value}")

        return hash_value

    async def cleanup_old_data(self, document_id: str, stage_name: str) -> bool:
        """
        Remove old data for a stage to prepare for re-processing.

        Deletes the completion marker for a document and stage, indicating
        that the stage needs to be re-processed. This is typically called
        when the data hash has changed.

        Note: This method only removes the completion marker. Stage-specific
        data cleanup (e.g., extracted chunks, embeddings) should be handled
        by the individual processors.

        Args:
            document_id: Unique identifier for the document
            stage_name: Name of the processing stage

        Returns:
            True if cleanup was successful, False otherwise

        Raises:
            None - Errors are logged and False is returned

        Example:
            ```python
            marker = await checker.check_completion_marker(doc_id, stage)
            if marker and marker['data_hash'] != current_hash:
                # Data changed - cleanup old marker
                await checker.cleanup_old_data(doc_id, stage)
                # Now re-process the stage...
            ```
        """
        try:
            await self.delete_completion_marker(document_id, stage_name)

            self.logger.info(f"Cleaned up old data for document {document_id}, " f"stage {stage_name}")
            return True

        except Exception as e:
            self.logger.error(
                f"Error cleaning up old data for document {document_id}, " f"stage {stage_name}: {e}", exc_info=True
            )
            return False

    async def delete_completion_marker(self, document_id: str, stage_name: str) -> bool:
        """
        Delete a completion marker from the database.

        Removes the completion marker for a document and stage. This is
        typically called as part of cleanup operations when data has changed.

        Args:
            document_id: Unique identifier for the document
            stage_name: Name of the processing stage

        Returns:
            True if deletion was successful, False otherwise

        Raises:
            None - Errors are logged and False is returned
        """
        query = """
            DELETE FROM krai_system.stage_completion_markers
            WHERE document_id = %(document_id)s AND stage_name = %(stage_name)s
        """

        try:
            await self.db_adapter.execute_query(query, {"document_id": document_id, "stage_name": stage_name})

            self.logger.debug(f"Deleted completion marker for document {document_id}, " f"stage {stage_name}")
            return True

        except Exception as e:
            self.logger.error(
                f"Error deleting completion marker for document {document_id}, " f"stage {stage_name}: {e}",
                exc_info=True,
            )
            return False
