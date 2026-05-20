"""
Stage 1: Upload Processor

Handles document ingestion, validation, deduplication, and queue management.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.base_processor import BaseProcessor, ProcessingContext, ProcessingError, ProcessingResult, Stage
from backend.core.data_models import DocumentModel, DocumentType, ProcessingQueueModel, ProcessingStatus
from backend.processors.logger import get_logger
from backend.services.database_adapter import DatabaseAdapter
from backend.services.object_storage_service import ObjectStorageService
from backend.services.storage_factory import create_storage_service

from .stage_tracker import StageTracker


class UploadProcessor(BaseProcessor):
    """
    Stage 1: Document Upload & Validation

    Responsibilities:
    1. File validation (format, size, corruption)
    2. Duplicate detection (hash-based)
    3. Database record creation
    4. Processing queue management
    """

    def __init__(
        self,
        database_adapter: DatabaseAdapter,
        max_file_size_mb: int = 500,
        allowed_extensions: list | None = None,
        storage_service: ObjectStorageService | None = None,
        upload_documents_to_storage: bool | None = None,
    ):
        """
        Initialize upload processor

        Args:
            database_adapter: Database adapter instance
            max_file_size_mb: Maximum file size in MB
            allowed_extensions: List of allowed file extensions
        """
        super().__init__(name="upload_processor")
        self.stage = Stage.UPLOAD
        self.database = database_adapter
        self.database_service = database_adapter
        self.db_adapter = database_adapter
        self.upload_documents_to_storage = (
            upload_documents_to_storage
            if upload_documents_to_storage is not None
            else str(os.getenv("UPLOAD_DOCUMENTS_TO_STORAGE", "false")).lower() in ("true", "1", "yes", "on")
        )
        self.storage_service = storage_service
        self._storage_connected = False

        if self.upload_documents_to_storage and self.storage_service is None:
            self.storage_service = create_storage_service()

        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        # CURRENT SCOPE: PDF/PDFZ only
        # Support standard PDFs and .pdfz variants (PDFs with custom extension)
        # FUTURE: Extend to support DOCX, images (jpg, png), and video formats (mp4, avi)
        # with appropriate validation and metadata extraction per type
        self.allowed_extensions = allowed_extensions or [".pdf", ".pdfz"]

        # Stage tracking with database adapter
        self.stage_tracker = StageTracker(database_adapter) if database_adapter else None

    async def _ensure_storage_connected(self) -> None:
        if not self.upload_documents_to_storage or self.storage_service is None or self._storage_connected:
            return
        await self.storage_service.connect()
        self._storage_connected = True

    async def _upload_document_to_storage(
        self,
        file_path: Path,
        file_hash: str,
        document_type: str,
    ) -> dict[str, Any]:
        await self._ensure_storage_connected()
        if self.storage_service is None:
            raise ProcessingError(
                "Document storage is enabled but storage_service is not configured",
                self.name,
                "STORAGE_NOT_CONFIGURED",
            )

        content = file_path.read_bytes()
        return await self.storage_service.upload_file(
            content=content,
            filename=file_path.name,
            bucket_type="documents",
            metadata={
                "document_type": document_type,
                "source": "upload_processor",
                "file_hash": file_hash,
            },
        )

    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Async entrypoint used by the pipeline framework.

        Wraps the synchronous ``process_upload`` helper and returns a
        ``ProcessingResult`` so that :meth:`BaseProcessor.safe_process` can
        attach timing information and logging without errors.
        """
        if not hasattr(context, "file_path"):
            raise ProcessingError(
                "Processing context must provide 'file_path'",
                self.name,
                "MISSING_FILE_PATH",
            )

        file_path = Path(context.file_path)
        # Treat missing or empty document_type as default 'service_manual' for robustness
        document_type = getattr(context, "document_type", None) or "service_manual"
        force_reprocess = getattr(context, "force_reprocess", False)

        # Use DatabaseAdapter path
        raw_result = await self._process_with_adapter(
            file_path=file_path,
            document_type=document_type,
            force_reprocess=force_reprocess,
            context=context,
        )

        if not isinstance(raw_result, dict):
            raise ProcessingError(
                "Upload processor returned unexpected result type",
                self.name,
                "INVALID_RESULT_TYPE",
            )

        metadata: dict[str, Any] = {
            "document_id": raw_result.get("document_id"),
            "file_path": str(file_path),
            "stage": self.stage.value,
        }

        inner_meta = raw_result.get("metadata") or {}
        if isinstance(inner_meta, dict):
            metadata.update(inner_meta)

        if "file_hash" not in metadata and "file_hash" in raw_result:
            metadata["file_hash"] = raw_result["file_hash"]

        if raw_result.get("success"):
            return self.create_success_result(data=raw_result, metadata=metadata)

        error_message = raw_result.get("error") or "Upload failed"
        error = ProcessingError(error_message, self.name, "UPLOAD_FAILED")
        return self.create_error_result(error=error, metadata=metadata)

    async def _process_with_adapter(
        self,
        file_path: Path,
        document_type: str,
        force_reprocess: bool,
        context: ProcessingContext | None = None,
    ) -> dict[str, Any]:
        """Adapter-based upload path using DatabaseService/DatabaseAdapter (e.g. PostgreSQLAdapter)."""

        with self.logger_context(stage=self.stage, document_id=None, file=file_path.name) as adapter:
            adapter.info("Processing upload: %s", file_path.name)

        # Step 1: Validate file
        validation_result = self._validate_file(file_path)
        if not validation_result["valid"]:
            return {"success": False, "error": validation_result["error"], "document_id": None}

        # Step 2: Calculate file hash
        file_hash = self._calculate_file_hash(file_path)
        self.logger.debug(f"File hash: {file_hash}")

        # Step 3: Extract basic metadata
        metadata = self._extract_basic_metadata(file_path)

        # Step 4: Check for duplicates via adapter
        existing_doc = None
        if hasattr(self.database, "get_document_by_hash"):
            existing_doc = await self.database.get_document_by_hash(file_hash)

        if existing_doc and not force_reprocess:
            document_id = str(existing_doc.get("id") or existing_doc.get("document_id"))
            with self.logger_context(stage=self.stage, document_id=document_id) as adapter:
                adapter.info("Duplicate found - skipping reprocess")

            # Mark upload stage as skipped for duplicates
            if self.stage_tracker is not None:
                await self.stage_tracker.skip_stage(
                    document_id=document_id, stage_name=self.stage, reason="Duplicate document detected"
                )

            return {
                "success": True,
                "document_id": document_id,
                "status": "duplicate",
                "existing_document": existing_doc,
                "reprocessing": False,
            }

        language = getattr(context, "language", "en") if context is not None else "en"
        storage_result: dict[str, Any] | None = None
        if self.upload_documents_to_storage:
            storage_result = await self._upload_document_to_storage(
                file_path=file_path,
                file_hash=file_hash,
                document_type=document_type,
            )
            metadata["storage_path"] = storage_result.get("storage_path")
            metadata["storage_url"] = storage_result.get("storage_url") or storage_result.get("url")

        try:
            if existing_doc and force_reprocess:
                # Update existing record
                document_id = str(existing_doc.get("id") or existing_doc.get("document_id"))
                with self.logger_context(stage=self.stage, document_id=document_id) as adapter:
                    adapter.info("Reprocessing existing document")

                # Only update columns that are known to exist in krai_core.documents
                updates = {
                    "file_hash": file_hash,
                    "file_size": metadata["file_size_bytes"],
                    "processing_status": ProcessingStatus.PENDING.value,
                }
                if storage_result is not None:
                    updates["storage_path"] = metadata.get("storage_path")
                    updates["storage_url"] = metadata.get("storage_url")
                if hasattr(self.database, "update_document"):
                    await self.database.update_document(document_id, updates)
                status = "reprocessing"
            else:
                # Create new record
                document_type_value = document_type
                try:
                    document_type_value = DocumentType(document_type).value
                except Exception:
                    # Fallback to raw string if enum conversion fails
                    document_type_value = document_type

                doc_model = DocumentModel(
                    filename=file_path.name,
                    original_filename=file_path.name,
                    file_size=metadata["file_size_bytes"],
                    file_hash=file_hash,
                    document_type=document_type_value,
                    language=language,
                    processing_status=ProcessingStatus.PENDING,
                    storage_path=metadata.get("storage_path") or str(file_path),
                    storage_url=metadata.get("storage_url"),
                )

                document_id = await self.database.create_document(doc_model)
                status = "new"
                self.logger.success(f"Created document record: {document_id}")
        except Exception as e:
            return {
                "success": False,
                "error": f"Database error: {e}",
                "document_id": None,
            }

        # Step 6: Add to processing queue via adapter (non-critical)
        try:
            queue_item = ProcessingQueueModel(
                document_id=document_id,
                processor_name=self.name,  # This will be mapped to task_type
                status=ProcessingStatus.PENDING,
                priority=5,
            )
            if hasattr(self.database, "create_processing_queue_item"):
                await self.database.create_processing_queue_item(queue_item)
        except Exception as e:
            # Non-critical: queue table may not exist or schema mismatch
            self.logger.debug(f"Processing queue entry skipped (non-critical): {e}")

        # Step 7: Mark upload stage as completed (only when tracker is available)
        if self.stage_tracker is not None:
            await self.stage_tracker.complete_stage(
                document_id=document_id,
                stage_name=self.stage,
                metadata={
                    "file_hash": file_hash,
                    "file_size": metadata["file_size_bytes"],
                    "page_count": metadata.get("page_count", 0),
                },
            )

        return {
            "success": True,
            "document_id": document_id,
            "status": status,
            "file_hash": file_hash,
            "metadata": metadata,
        }

    def _validate_file(self, file_path: Path) -> dict[str, Any]:
        """Validate file format and size"""

        # Debug logging for file validation
        self.logger.debug(
            "Validating file: %s (suffix=%r) allowed=%s",
            file_path,
            file_path.suffix,
            self.allowed_extensions,
        )

        # Check if file exists
        if not file_path.exists():
            return {"valid": False, "error": f"File not found: {file_path}"}

        # Check file extension
        if file_path.suffix.lower() not in self.allowed_extensions:
            return {
                "valid": False,
                "error": f"Invalid file type '{file_path.suffix}'. Allowed: {self.allowed_extensions}",
            }

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size_bytes:
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return {"valid": False, "error": f"File too large: {actual_mb:.1f}MB (max: {max_mb}MB)"}

        # Check if file is corrupted (basic check - can be opened)
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            try:
                page_count = len(doc)
            finally:
                doc.close()

            if page_count == 0:
                return {"valid": False, "error": "PDF has no pages"}

        except Exception as e:
            return {"valid": False, "error": f"Corrupted or invalid PDF: {e!s}"}

        return {"valid": True, "error": None}

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def _extract_basic_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract basic metadata from PDF"""
        import fitz  # PyMuPDF

        metadata = {
            "filename": file_path.name,
            "file_size_bytes": file_path.stat().st_size,
            "file_modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        }

        try:
            doc = fitz.open(file_path)
            try:
                # PDF metadata
                pdf_meta = doc.metadata
                metadata.update(
                    {
                        "page_count": len(doc),
                        "title": pdf_meta.get("title", "") or file_path.stem,
                        "author": pdf_meta.get("author", ""),
                        "subject": pdf_meta.get("subject", ""),
                        "creator": pdf_meta.get("creator", ""),
                        "producer": pdf_meta.get("producer", ""),
                        "creation_date": pdf_meta.get("creationDate", ""),
                        "modification_date": pdf_meta.get("modDate", ""),
                    }
                )
            finally:
                doc.close()

        except Exception as e:
            self.logger.warning(f"Could not extract PDF metadata: {e}")
            metadata["page_count"] = 0
            metadata["title"] = file_path.stem

        return metadata


class BatchUploadProcessor:
    """Process multiple documents in batch"""

    def __init__(self, database_adapter: DatabaseAdapter, max_file_size_mb: int = 500):
        """Initialize batch processor"""
        self.upload_processor = UploadProcessor(database_adapter, max_file_size_mb)
        self.logger = get_logger()

    async def process_batch(
        self,
        files: list[Path],
        document_type: str = "service_manual",
        force_reprocess: bool = False,
    ) -> list[ProcessingResult]:
        results: list[ProcessingResult] = []

        for file_path in files:
            try:
                context = ProcessingContext(
                    document_id=str(uuid4()),
                    file_path=str(file_path),
                    document_type=document_type,
                )
                context.force_reprocess = force_reprocess
                result = await self.upload_processor.process(context)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {e}")
                error = ProcessingError(str(e), processor="batch_upload_processor", error_code="BATCH_UPLOAD_FAILED")
                failed_metadata = {"file_path": str(file_path), "stage": Stage.UPLOAD.value}
                results.append(
                    ProcessingResult(
                        success=False,
                        processor="batch_upload_processor",
                        status=ProcessingStatus.FAILED,
                        data={},
                        metadata=failed_metadata,
                        error=error,
                    )
                )

        return results

    async def process_directory(
        self,
        directory: Path,
        document_type: str = "service_manual",
        recursive: bool = False,
        force_reprocess: bool = False,
    ) -> dict[str, Any]:
        """
        Process all PDFs in a directory

        Args:
            directory: Directory containing PDFs
            document_type: Type of documents
            recursive: If True, search subdirectories
            force_reprocess: If True, reprocess existing documents

        Returns:
            Dict with processing results
        """
        self.logger.section(f"Batch Upload: {directory}")

        # Find all PDFs
        if recursive:
            pdf_files = list(directory.rglob("*.pdf"))
        else:
            pdf_files = list(directory.glob("*.pdf"))

        self.logger.info(f"Found {len(pdf_files)} PDF files")

        results = {
            "total": len(pdf_files),
            "successful": 0,
            "failed": 0,
            "duplicates": 0,
            "reprocessed": 0,
            "documents": [],
        }

        batch_results = await self.process_batch(
            files=pdf_files,
            document_type=document_type,
            force_reprocess=force_reprocess,
        )

        for pdf_file, result in zip(pdf_files, batch_results):
            if result.success:
                results["successful"] += 1

                status = None
                if isinstance(getattr(result, "data", None), dict):
                    status = result.data.get("status")

                if status == "duplicate":
                    results["duplicates"] += 1
                elif status == "reprocessing":
                    results["reprocessed"] += 1

                document_id = None
                if isinstance(getattr(result, "data", None), dict):
                    document_id = result.data.get("document_id")

                results["documents"].append(
                    {
                        "filename": pdf_file.name,
                        "document_id": document_id,
                        "status": status,
                    }
                )
            else:
                results["failed"] += 1
                error_str = None
                if hasattr(result, "error") and result.error is not None:
                    error_str = str(result.error)
                results["documents"].append(
                    {
                        "filename": pdf_file.name,
                        "error": error_str or "Processing failed",
                    }
                )

        # Summary
        self.logger.section("Batch Upload Summary")
        self.logger.info(f"Total: {results['total']}")
        self.logger.success(f"Successful: {results['successful']}")
        if results["duplicates"] > 0:
            self.logger.info(f"Duplicates skipped: {results['duplicates']}")
        if results["reprocessed"] > 0:
            self.logger.info(f"Reprocessed: {results['reprocessed']}")
        if results["failed"] > 0:
            self.logger.warning(f"Failed: {results['failed']}")

        return results
