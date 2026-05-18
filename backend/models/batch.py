"""Pydantic models supporting batch operations and task management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator

_ALLOWED_RESOURCE_TYPES = {
    "documents",
    "products",
    "manufacturers",
    "error_codes",
    "videos",
    "images",
}

_ALLOWED_OPERATIONS = {"create", "update", "delete", "status_change"}


class BatchOperationRequest(BaseModel):
    """Base payload for batch operations."""

    resource_type: str = Field(..., description="Target resource type for the batch operation")
    operation: str = Field(..., description="Operation to perform across all items")
    items: list[dict[str, Any]] = Field(..., min_items=1, max_items=100)
    options: dict[str, Any] = Field(default_factory=dict)

    @validator("resource_type")
    def _validate_resource_type(cls, value: str) -> str:
        if value not in _ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return value

    @validator("operation")
    def _validate_operation(cls, value: str) -> str:
        if value not in _ALLOWED_OPERATIONS:
            allowed = ", ".join(sorted(_ALLOWED_OPERATIONS))
            raise ValueError(f"operation must be one of: {allowed}")
        return value

    @root_validator(skip_on_failure=True)
    def _validate_item_count(cls, values: dict[str, Any]) -> dict[str, Any]:
        items = values.get("items") or []
        if not items:
            raise ValueError("items must contain at least one entry")
        if len(items) > 100:
            raise ValueError("items cannot exceed 100 entries per request")
        return values

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "resource_type": "documents",
                "operation": "delete",
                "items": [{"id": "uuid-1"}, {"id": "uuid-2"}],
                "options": {"reason": "cleanup"},
            }
        }


class BatchDeleteRequest(BaseModel):
    """Request payload for synchronous/asynchronous batch deletions."""

    resource_type: str = Field(..., description="Target resource type for deletion")
    ids: list[str] = Field(..., min_items=1, max_items=100, description="Identifiers to delete")

    @validator("resource_type")
    def _validate_resource_type(cls, value: str) -> str:
        if value not in _ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return value

    @validator("ids")
    def _validate_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("ids must contain at least one identifier")
        if len(value) > 100:
            raise ValueError("ids cannot exceed 100 entries per request")
        missing = [idx for idx in value if not idx]
        if missing:
            raise ValueError("ids cannot contain empty values")
        return value

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "resource_type": "documents",
                "ids": ["d1c55d77-3d21-4df9-9cc5-6bcb1b56c0a1", "b2ebf4c4-8e9f-4cf6-bd6c-8afd4359f003"],
            }
        }


class BatchUpdateRequest(BaseModel):
    """Request payload for batch updates."""

    resource_type: str = Field(..., description="Target resource type for update")
    updates: list[dict[str, Any]] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="Collection of update objects with id and update_data",
    )

    @validator("resource_type")
    def _validate_resource_type(cls, value: str) -> str:
        if value not in _ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return value

    @validator("updates")
    def _validate_updates(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise ValueError("updates must contain at least one entry")
        if len(value) > 100:
            raise ValueError("updates cannot exceed 100 entries per request")
        for update in value:
            if "id" not in update or not update["id"]:
                raise ValueError("Each update must include a non-empty 'id'")
            if "update_data" not in update or not isinstance(update["update_data"], dict):
                raise ValueError("Each update must include an 'update_data' object")
            if not update["update_data"]:
                raise ValueError("update_data cannot be empty")
        return value

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "resource_type": "products",
                "updates": [
                    {
                        "id": "f16fca6d-843d-4c82-9891-2b58b4c94f54",
                        "update_data": {"status": "active", "manual_review_required": False},
                    }
                ],
            }
        }


class BatchStatusChangeRequest(BaseModel):
    """Request payload for bulk status changes."""

    resource_type: str = Field(..., description="Target resource type for status change")
    ids: list[str] = Field(..., min_items=1, max_items=100, description="Identifiers to update")
    new_status: str = Field(..., min_length=1, description="Status value to apply")
    reason: str | None = Field(None, max_length=500, description="Optional reason for the change")

    @validator("resource_type")
    def _validate_resource_type(cls, value: str) -> str:
        if value not in _ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return value

    @validator("ids")
    def _validate_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("ids must contain at least one identifier")
        if len(value) > 100:
            raise ValueError("ids cannot exceed 100 entries per request")
        missing = [idx for idx in value if not idx]
        if missing:
            raise ValueError("ids cannot contain empty values")
        return value

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "resource_type": "documents",
                "ids": ["doc-1", "doc-2"],
                "new_status": "archived",
                "reason": "Superseded by latest revision",
            }
        }


class BatchOperationResultStatus(str, Enum):
    """Possible result statuses for each batch item."""

    SUCCESS = "success"
    FAILED = "failed"


class BatchOperationResult(BaseModel):
    """Detailed outcome for a single batch item."""

    id: str | None = Field(None, description="Identifier processed in the operation")
    status: BatchOperationResultStatus = Field(..., description="Outcome for the specific item")
    error: str | None = Field(None, description="Optional error message when status=failed")
    rollback_data: dict[str, Any] | None = Field(
        None, description="Payload required to roll back a successful operation"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "d1c55d77-3d21-4df9-9cc5-6bcb1b56c0a1",
                "status": "success",
                "rollback_data": {"table": "krai_core.documents", "old_values": {"status": "draft"}},
            }
        }


class BatchOperationResponse(BaseModel):
    """Aggregate response for a batch operation."""

    success: bool = Field(..., description="Indicates whether the batch completed without fatal errors")
    total: int = Field(..., ge=0, description="Total number of items processed")
    successful: int = Field(..., ge=0, description="Number of successful items")
    failed: int = Field(..., ge=0, description="Number of failed items")
    results: list[BatchOperationResult] = Field(default_factory=list)
    task_id: str | None = Field(None, description="Task identifier when executed asynchronously")
    execution_time_ms: int | None = Field(
        None, ge=0, description="Execution time in milliseconds for synchronous operations"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "success": True,
                "total": 5,
                "successful": 4,
                "failed": 1,
                "results": [
                    {"id": "uuid-1", "status": "success"},
                    {"id": "uuid-2", "status": "failed", "error": "Foreign key violation"},
                ],
                "execution_time_ms": 823,
            }
        }


class BatchTaskStatus(str, Enum):
    """Lifecycle states for batch processing tasks."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchTaskRequest(BaseModel):
    """Input payload for creating a new batch task."""

    operation_type: str = Field(..., description="Logical operation type (delete/update/status_change)")
    resource_type: str = Field(..., description="Target resource type for the operation")
    payload: dict[str, Any] = Field(default_factory=dict, description="Serialized payload for execution")
    priority: int = Field(5, ge=0, le=10, description="Task priority (higher executes earlier)")
    user_id: str = Field(..., description="User initiating the task")

    @validator("resource_type")
    def _validate_resource_type(cls, value: str) -> str:
        if value not in _ALLOWED_RESOURCE_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_RESOURCE_TYPES))
            raise ValueError(f"resource_type must be one of: {allowed}")
        return value

    @validator("operation_type")
    def _validate_operation_type(cls, value: str) -> str:
        if value not in _ALLOWED_OPERATIONS:
            allowed = ", ".join(sorted(_ALLOWED_OPERATIONS))
            raise ValueError(f"operation_type must be one of: {allowed}")
        return value

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "operation_type": "delete",
                "resource_type": "documents",
                "payload": {"ids": ["uuid-1", "uuid-2"]},
                "priority": 5,
                "user_id": "user-uuid",
            }
        }


class BatchTaskResponse(BaseModel):
    """Status payload returned when querying a batch task."""

    task_id: str = Field(..., description="Unique task identifier")
    status: BatchTaskStatus = Field(..., description="Current execution status")
    progress: float = Field(0.0, ge=0.0, le=100.0, description="Task progress percentage")
    total_items: int = Field(0, ge=0, description="Total number of items queued for the task")
    processed_items: int = Field(0, ge=0, description="Number of items processed so far")
    successful_items: int = Field(0, ge=0, description="Number of items processed successfully")
    failed_items: int = Field(0, ge=0, description="Number of items that failed")
    started_at: datetime | None = Field(None, description="Timestamp when task started")
    completed_at: datetime | None = Field(None, description="Timestamp when task completed")
    error: str | None = Field(None, description="Error message if the task failed")
    results: list[BatchOperationResult] | None = Field(None, description="Detailed results collected during execution")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "task_id": "batch_delete_1730456400",
                "status": "running",
                "progress": 42.0,
                "total_items": 75,
                "processed_items": 32,
                "successful_items": 30,
                "failed_items": 2,
                "started_at": "2025-11-01T12:15:00Z",
                "results": [
                    {"id": "uuid-1", "status": "success"},
                    {"id": "uuid-2", "status": "failed", "error": "Foreign key constraint"},
                ],
            }
        }


class RollbackRequest(BaseModel):
    """Payload for triggering a rollback of a completed batch operation."""

    task_id: str = Field(..., description="Task identifier to roll back")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for initiating rollback")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "task_id": "batch_update_1730459900",
                "reason": "Detected invalid pricing updates during QA review",
            }
        }


class RollbackResponse(BaseModel):
    """Response returned after executing a rollback."""

    success: bool = Field(..., description="Indicates whether the rollback completed successfully")
    rolled_back_count: int = Field(..., ge=0, description="Number of items rolled back")
    message: str = Field(..., description="Human-readable status message")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "success": True,
                "rolled_back_count": 48,
                "message": "Rollback completed successfully",
            }
        }
