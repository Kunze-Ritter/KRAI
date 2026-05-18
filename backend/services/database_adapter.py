"""
Abstract Database Adapter

Defines the interface that all database adapters must implement.
This provides a clean abstraction layer for different database backends.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.

    All database adapters must inherit from this class and implement
    the defined abstract methods to ensure consistent interface.
    """

    def __init__(self):
        """Initialize the database adapter."""
        self.logger = logging.getLogger(self.__class__.__name__)

    # Connection Management
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the database."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if database connection is working."""
        pass

    # Query Execution
    @abstractmethod
    async def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Execute query and return first result."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute query and return all results."""
        pass

    @abstractmethod
    async def execute_query(self, query: str, params: dict[str, Any] | None = None) -> str:
        """Execute query and return result identifier."""
        pass

    @abstractmethod
    async def rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
        """Execute stored procedure/function."""
        pass

    @abstractmethod
    async def execute_rpc(self, function_name: str, params: dict[str, Any] | None = None) -> Any:
        """Execute stored procedure/function (alias for rpc)."""
        pass

    # Document Operations
    @abstractmethod
    async def create_document(self, document: dict[str, Any]) -> str:
        """Create a new document record."""
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Retrieve document by ID."""
        pass

    @abstractmethod
    async def get_document_by_hash(self, file_hash: str) -> dict[str, Any] | None:
        """Retrieve document by file hash."""
        pass

    @abstractmethod
    async def update_document(self, document_id: str, updates: dict[str, Any]) -> bool:
        """Update document record."""
        pass

    # Chunk Operations
    @abstractmethod
    async def insert_chunk(self, chunk_data: dict[str, Any]) -> str:
        """Insert a text chunk."""
        pass

    @abstractmethod
    async def get_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Retrieve all chunks for a document."""
        pass

    @abstractmethod
    async def get_intelligence_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Retrieve intelligence chunks for a document."""
        pass

    # Image Operations
    @abstractmethod
    async def create_image(self, image_data: dict[str, Any]) -> str:
        """Create an image record."""
        pass

    async def insert_image(self, image_data: dict[str, Any]) -> str:
        """Insert an image record (alias for create_image)."""
        return await self.create_image(image_data)

    @abstractmethod
    async def get_images_by_document(self, document_id: str) -> list[dict[str, Any]]:
        """Retrieve all images for a document."""
        pass

    # Table Operations
    @abstractmethod
    async def insert_table(self, table_data: dict[str, Any]) -> str:
        """Insert a table record."""
        pass

    # Embedding Operations
    @abstractmethod
    async def create_embedding(self, embedding_data: dict[str, Any]) -> str:
        """Create an embedding record."""
        pass

    async def insert_embedding(self, embedding_data: dict[str, Any]) -> str:
        """Insert an embedding record (alias for create_embedding)."""
        return await self.create_embedding(embedding_data)

    @abstractmethod
    async def create_unified_embedding(
        self,
        source_id: str,
        source_type: str,
        embedding: list[float],
        model_name: str,
        embedding_context: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a unified embedding record."""
        pass

    # Link Operations
    @abstractmethod
    async def insert_link(self, link_data: dict[str, Any]) -> str:
        """Insert a link record (link extraction)."""
        pass

    # Parts Operations
    @abstractmethod
    async def insert_part(self, part_data: dict[str, Any]) -> str:
        """Insert a part record into parts catalog."""
        pass

    # Stage Tracking
    @abstractmethod
    async def start_stage(self, document_id: str, stage: str, metadata: dict[str, Any] | None = None) -> bool:
        """Start processing stage for document."""
        pass

    @abstractmethod
    async def complete_stage(self, document_id: str, stage: str, metadata: dict[str, Any] | None = None) -> bool:
        """Complete processing stage for document."""
        pass

    @abstractmethod
    async def fail_stage(
        self, document_id: str, stage: str, error: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Mark stage as failed for document."""
        pass

    @abstractmethod
    async def skip_stage(
        self, document_id: str, stage: str, reason: str, metadata: dict[str, Any] | None = None
    ) -> bool:
        """Skip processing stage for document."""
        pass

    @abstractmethod
    async def get_stage_status(self, document_id: str, stage: str) -> dict[str, Any] | None:
        """Get status of processing stage for document."""
        pass

    # Processing Queue
    @abstractmethod
    async def create_processing_queue_item(self, queue_item: dict[str, Any]) -> str:
        """Create item in processing queue."""
        pass
