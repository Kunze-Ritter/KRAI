"""WebSocket API for real-time monitoring updates."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from backend.models.monitoring import (
    Alert,
    HardwareStatus,
    PipelineMetrics,
    QueueMetrics,
    WebSocketEvent,
    WebSocketMessage,
)
from backend.services.auth_service import AuthService
from backend.services.metrics_service import MetricsService

LOGGER = logging.getLogger(__name__)

router = APIRouter()


class WebSocketManager:
    """Manager for WebSocket connections."""

    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: list[WebSocket] = []
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}
        self.logger = LOGGER

    async def connect(self, websocket: WebSocket, user_id: str, permissions: list[str]) -> None:
        """Accept and register WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "permissions": permissions,
            "connected_at": datetime.utcnow(),
        }
        self.logger.info(f"WebSocket connected: user={user_id}, total_connections={len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_metadata:
            user_id = self.connection_metadata[websocket].get("user_id", "unknown")
            del self.connection_metadata[websocket]
            self.logger.info(
                f"WebSocket disconnected: user={user_id}, remaining_connections={len(self.active_connections)}"
            )

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send message to specific connection."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message)
        except Exception as e:
            self.logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: WebSocketMessage, permission_required: str | None = None) -> None:
        """Broadcast message to all authorized connections."""
        disconnected = []

        for connection in self.active_connections:
            try:
                # Check permission if required
                if permission_required:
                    metadata = self.connection_metadata.get(connection, {})
                    permissions = metadata.get("permissions", [])
                    if permission_required not in permissions:
                        continue

                # Send message
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message.model_dump())

            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                self.logger.error(f"Failed to broadcast to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


# Global manager instance
manager = WebSocketManager()


async def broadcast_pipeline_update(pipeline_metrics: PipelineMetrics) -> None:
    """Broadcast pipeline metrics update."""
    message = WebSocketMessage(
        type=WebSocketEvent.PIPELINE_UPDATE.value,
        data=pipeline_metrics.model_dump(),
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_queue_update(queue_metrics: QueueMetrics) -> None:
    """Broadcast queue metrics update."""
    message = WebSocketMessage(
        type=WebSocketEvent.QUEUE_UPDATE.value,
        data=queue_metrics.model_dump(),
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_hardware_update(hardware_status: HardwareStatus) -> None:
    """Broadcast hardware status update."""
    message = WebSocketMessage(
        type=WebSocketEvent.HARDWARE_UPDATE.value,
        data=hardware_status.model_dump(),
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_alert(alert: Alert) -> None:
    """Broadcast alert trigger."""
    message = WebSocketMessage(
        type=WebSocketEvent.ALERT_TRIGGERED.value,
        data=alert.model_dump(),
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_stage_event(
    event_type: WebSocketEvent,
    stage_name: str,
    document_id: str,
    status: str,
) -> None:
    """Broadcast stage event."""
    message = WebSocketMessage(
        type=event_type.value,
        data={
            "stage": stage_name,
            "document_id": document_id,
            "status": status,
        },
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_processor_state_change(
    processor_name: str,
    stage_name: str,
    status: str,
    document_id: str | None = None,
) -> None:
    """Broadcast processor state change event."""
    message = WebSocketMessage(
        type=WebSocketEvent.PROCESSOR_STATE_CHANGE.value,
        data={
            "processor_name": processor_name,
            "stage_name": stage_name,
            "status": status,
            "document_id": document_id,
        },
    )
    await manager.broadcast(message, "monitoring:read")


async def broadcast_stage_update(
    document_id: str,
    stage_name: str,
    status: str,
    progress: int,
    error: str | None = None,
) -> None:
    """Broadcast stage status change to connected clients."""
    event_type = (
        "STAGE_COMPLETED" if status == "completed" else "STAGE_FAILED" if status == "failed" else "STAGE_PROCESSING"
    )

    message = WebSocketMessage(
        type=event_type,
        data={
            "document_id": document_id,
            "stage_name": stage_name,
            "status": status,
            "progress": progress,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    await manager.broadcast(message, "documents:read")


@router.websocket("/ws/monitoring")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """WebSocket endpoint for real-time monitoring updates."""
    auth_service: AuthService | None = None

    try:
        # Import here to avoid circular dependency
        from backend.api.app import ensure_auth_service

        auth_service = ensure_auth_service()

        # Validate JWT token
        payload = await auth_service.decode_access_token(token)

        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return

        # Fetch user permissions
        permissions = await auth_service.get_user_permissions(user_id)

        # Check if user has monitoring:read permission
        if "monitoring:read" not in permissions:
            await websocket.close(code=1008, reason="Insufficient permissions")
            return

        # Connect
        await manager.connect(websocket, user_id, permissions)

        # Send initial data
        try:
            from backend.api.app import get_metrics_service

            metrics_service = await get_metrics_service()

            pipeline_metrics = await metrics_service.get_pipeline_metrics()
            queue_metrics = await metrics_service.get_queue_metrics()
            hardware_metrics = await metrics_service.get_hardware_metrics()

            await websocket.send_json(
                {
                    "type": "initial_data",
                    "data": {
                        "pipeline": pipeline_metrics.model_dump(),
                        "queue": queue_metrics.model_dump(),
                        "hardware": hardware_metrics.model_dump(),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        except Exception as e:
            LOGGER.error(f"Failed to send initial data: {e}")

        # Keep connection alive and handle messages
        last_heartbeat = datetime.utcnow()

        while True:
            try:
                # Wait for message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                    last_heartbeat = datetime.utcnow()

            except TimeoutError:
                # Send heartbeat
                if (datetime.utcnow() - last_heartbeat).total_seconds() > 30:
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                    last_heartbeat = datetime.utcnow()

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        LOGGER.error(f"WebSocket error: {e}", exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")
    finally:
        manager.disconnect(websocket)


async def start_periodic_broadcast(metrics_service: MetricsService, interval_seconds: int = 1) -> None:
    """Start periodic broadcast of metrics to all connected clients."""
    LOGGER.info(f"Starting periodic WebSocket broadcast (interval: {interval_seconds}s)")

    broadcast_count = 0

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            if not manager.active_connections:
                continue

            broadcast_count += 1

            # Broadcast pipeline update every second
            pipeline_metrics = await metrics_service.get_pipeline_metrics()
            await broadcast_pipeline_update(pipeline_metrics)

            # Broadcast queue update every second
            queue_metrics = await metrics_service.get_queue_metrics()
            await broadcast_queue_update(queue_metrics)

            # Broadcast hardware update every 5 seconds
            if broadcast_count % 5 == 0:
                hardware_metrics = await metrics_service.get_hardware_metrics()
                await broadcast_hardware_update(hardware_metrics)

            if broadcast_count % 60 == 0:
                LOGGER.debug(f"Periodic broadcast active: {len(manager.active_connections)} connections")

        except asyncio.CancelledError:
            LOGGER.info("Periodic broadcast stopped")
            break
        except Exception as e:
            LOGGER.error(f"Error in periodic broadcast: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)
