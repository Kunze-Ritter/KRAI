# Monitoring API Documentation

## Overview

The KRAI Monitoring System provides comprehensive real-time monitoring of the document processing pipeline, including metrics aggregation, alert management, and WebSocket-based live updates.

## Table of Contents

- [Authentication](#authentication)
- [Permissions](#permissions)
- [Pipeline Monitoring](#pipeline-monitoring)
- [Queue Monitoring](#queue-monitoring)
- [Hardware Metrics](#hardware-metrics)
- [Data Quality Metrics](#data-quality-metrics)
- [Alert Management](#alert-management)
- [Alert Rules](#alert-rules)
- [WebSocket API](#websocket-api)
- [Legacy Endpoints](#legacy-endpoints)

---

## Authentication

All monitoring endpoints require authentication via JWT Bearer token:

```http
Authorization: Bearer <your_jwt_token>
```

## Permissions

The monitoring system uses the following permissions:

| Permission | Description | Required For |
|------------|-------------|--------------|
| `monitoring:read` | View monitoring data and metrics | All GET endpoints, WebSocket connection |
| `monitoring:write` | Modify monitoring settings | Legacy reset/start endpoints |
| `alerts:read` | View alerts | Alert list endpoints |
| `alerts:write` | Acknowledge/dismiss alerts | Alert modification endpoints |
| `alerts:manage` | Manage alert rules | Create/update/delete alert rules |

### Role Permissions

| Role | Permissions |
|------|-------------|
| **ADMIN** | All monitoring and alert permissions |
| **EDITOR** | `monitoring:read`, `alerts:read`, `alerts:write` |
| **VIEWER** | `monitoring:read`, `alerts:read` |

---

## Pipeline Monitoring

### Get Pipeline Status

Get comprehensive pipeline metrics including document counts, success rates, and throughput.

**Endpoint:** `GET /api/v1/monitoring/pipeline`

**Permissions:** `monitoring:read`

**Response:**

```json
{
  "total_documents": 1250,
  "documents_pending": 45,
  "documents_processing": 12,
  "documents_completed": 1180,
  "documents_failed": 13,
  "success_rate": 98.91,
  "avg_processing_time_seconds": 42.5,
  "current_throughput_docs_per_hour": 28.5
}
```

**Fields:**

- `total_documents`: Total number of documents in the system
- `documents_pending`: Documents waiting to be processed
- `documents_processing`: Documents currently being processed
- `documents_completed`: Successfully processed documents
- `documents_failed`: Failed documents
- `success_rate`: Percentage of successful processing (0-100)
- `avg_processing_time_seconds`: Average time to process a document
- `current_throughput_docs_per_hour`: Documents processed per hour (24h average)

**Performance:** Uses server-side aggregated view `vw_pipeline_metrics_aggregated` for optimal performance.

---

## Queue Monitoring

### Get Queue Status

Get processing queue metrics including pending items, processing times, and task type breakdown.

**Endpoint:** `GET /api/v1/monitoring/queue`

**Permissions:** `monitoring:read`

**Response:**

```json
{
  "total_items": 157,
  "pending_count": 45,
  "processing_count": 12,
  "completed_count": 95,
  "failed_count": 5,
  "avg_wait_time_seconds": 8.3,
  "by_task_type": {
    "document_processing": 120,
    "embedding_generation": 25,
    "image_extraction": 12
  }
}
```

**Fields:**

- `total_items`: Total queue items
- `pending_count`: Items waiting to be processed
- `processing_count`: Items currently processing
- `completed_count`: Successfully completed items
- `failed_count`: Failed items
- `avg_wait_time_seconds`: Average time from scheduled to started
- `by_task_type`: Breakdown of items by task type

**Performance:** Uses server-side aggregated view `vw_queue_metrics_aggregated`.

### Get Queue Items

Get detailed queue items with optional filtering.

**Endpoint:** `GET /api/v1/monitoring/queue/items`

**Permissions:** `monitoring:read`

**Query Parameters:**

- `limit` (optional, default: 100): Maximum number of items to return
- `status` (optional): Filter by status (`pending`, `processing`, `completed`, `failed`)

**Response:**

```json
{
  "items": [
    {
      "id": "queue-001",
      "task_type": "document_processing",
      "status": "processing",
      "priority": 5,
      "scheduled_at": "2025-11-02T10:30:00Z",
      "started_at": "2025-11-02T10:30:05Z",
      "metadata": {
        "document_id": "doc-123",
        "filename": "manual.pdf"
      }
    }
  ],
  "total": 157
}
```

---

## Hardware Metrics

### Get Hardware Status

Get current hardware utilization metrics.

**Endpoint:** `GET /api/v1/monitoring/metrics`

**Permissions:** `monitoring:read`

**Response:**

```json
{
  "cpu_percent": 45.2,
  "ram_percent": 62.8,
  "disk_percent": 38.5,
  "timestamp": "2025-11-02T10:35:00Z"
}
```

**Fields:**

- `cpu_percent`: CPU utilization (0-100)
- `ram_percent`: RAM utilization (0-100)
- `disk_percent`: Disk utilization (0-100)
- `timestamp`: When metrics were collected

**Cache:** 1 second TTL for hardware metrics.

---

## Data Quality Metrics

### Get Data Quality Status

Get data quality metrics including duplicates and validation errors.

**Endpoint:** `GET /api/v1/monitoring/data-quality`

**Permissions:** `monitoring:read`

**Response:**

```json
{
  "duplicate_metrics": {
    "total_duplicates": 23,
    "by_hash": 15,
    "by_filename": 8,
    "duplicate_documents": [
      {
        "file_hash": "abc123...",
        "count": 3,
        "filenames": ["manual_v1.pdf", "manual_v2.pdf", "manual_copy.pdf"]
      }
    ]
  },
  "validation_metrics": {
    "total_validation_errors": 8,
    "errors_by_stage": {
      "text_extraction": 3,
      "classification": 2,
      "embedding": 3
    },
    "documents_with_errors": [
      {
        "document_id": "doc-456",
        "stage": "text_extraction",
        "error": "OCR failed - image quality too low"
      }
    ]
  },
  "processing_metrics": {
    "total_processed": 1000,
    "successful": 970,
    "failed": 30,
    "success_rate": 97.0,
    "avg_processing_time": 45.3,
    "processing_by_type": {
      "service_manual": 600,
      "user_guide": 300,
      "technical_spec": 100
    }
  }
}
```

**Performance:** Uses RPC functions `get_duplicate_hashes()` and `get_duplicate_filenames()` for efficient duplicate detection.

---

## Alert Management

### Get Alerts

Get list of alerts with optional filtering.

**Endpoint:** `GET /api/v1/monitoring/alerts`

**Permissions:** `alerts:read`

**Query Parameters:**

- `limit` (optional, default: 50): Maximum number of alerts
- `severity` (optional): Filter by severity (`low`, `medium`, `high`, `critical`)
- `acknowledged` (optional): Filter by acknowledgment status (`true`, `false`)

**Response:**

```json
{
  "alerts": [
    {
      "id": "alert-001",
      "alert_type": "processing_failure",
      "severity": "high",
      "title": "High Processing Failure Rate",
      "message": "Processing failure rate is 12.5%, exceeding threshold of 10%",
      "metadata": {
        "current_value": 12.5,
        "threshold": 10.0,
        "success_rate": 87.5
      },
      "triggered_at": "2025-11-02T10:30:00Z",
      "acknowledged": false,
      "acknowledged_at": null,
      "acknowledged_by": null
    }
  ],
  "total": 5,
  "unacknowledged_count": 3
}
```

### Acknowledge Alert

Mark an alert as acknowledged.

**Endpoint:** `POST /api/v1/monitoring/alerts/{alert_id}/acknowledge`

**Permissions:** `alerts:write`

**Response:**

```json
{
  "success": true,
  "alert_id": "alert-001"
}
```

### Dismiss Alert

Dismiss an alert (marks as acknowledged and archives).

**Endpoint:** `POST /api/v1/monitoring/alerts/{alert_id}/dismiss`

**Permissions:** `alerts:write`

**Response:**

```json
{
  "success": true,
  "alert_id": "alert-001"
}
```

---

## Alert Rules

### Get Alert Rules

Get list of all alert rules.

**Endpoint:** `GET /api/v1/monitoring/alert-rules`

**Permissions:** `monitoring:read`

**Response:**

```json
[
  {
    "id": "rule-001",
    "name": "High Processing Failure Rate",
    "alert_type": "processing_failure",
    "severity": "high",
    "threshold_value": 10.0,
    "threshold_operator": ">",
    "metric_key": null,
    "enabled": true
  },
  {
    "id": "rule-002",
    "name": "High CPU Usage",
    "alert_type": "hardware_threshold",
    "severity": "high",
    "threshold_value": 90.0,
    "threshold_operator": ">",
    "metric_key": "cpu",
    "enabled": true
  }
]
```

**Alert Types:**

- `processing_failure`: Processing failure rate threshold
- `queue_overflow`: Queue size threshold
- `hardware_threshold`: CPU/RAM/Disk threshold
- `data_quality`: Duplicate or validation error threshold
- `system_error`: System-level errors

**Severity Levels:**

- `low`: Informational
- `medium`: Warning
- `high`: Requires attention
- `critical`: Immediate action required

**Metric Keys:**

For `hardware_threshold`:
- `cpu`: CPU utilization
- `ram`: RAM utilization

For `data_quality`:
- `duplicates`: Duplicate document count
- `validation_errors`: Validation error count

### Create Alert Rule

Create a new alert rule.

**Endpoint:** `POST /api/v1/monitoring/alert-rules`

**Permissions:** `alerts:manage`

**Request Body:**

```json
{
  "name": "High RAM Usage",
  "alert_type": "hardware_threshold",
  "severity": "high",
  "threshold_value": 85.0,
  "threshold_operator": ">",
  "metric_key": "ram",
  "enabled": true
}
```

**Response:**

```json
{
  "success": true,
  "rule_id": "rule-003"
}
```

### Update Alert Rule

Update an existing alert rule.

**Endpoint:** `PUT /api/v1/monitoring/alert-rules/{rule_id}`

**Permissions:** `alerts:manage`

**Request Body:**

```json
{
  "threshold_value": 90.0,
  "enabled": false
}
```

**Response:**

```json
{
  "success": true
}
```

### Delete Alert Rule

Delete an alert rule.

**Endpoint:** `DELETE /api/v1/monitoring/alert-rules/{rule_id}`

**Permissions:** `alerts:manage`

**Response:**

```json
{
  "success": true
}
```

---

## WebSocket API

### Connect to WebSocket

Establish a WebSocket connection for real-time monitoring updates.

**Endpoint:** `ws://localhost:8000/ws/monitoring?token=<jwt_token>`

**Permissions:** `monitoring:read`

**Query Parameters:**

- `token` (required): JWT access token for authentication

**Connection Flow:**

1. Client connects with JWT token
2. Server validates token and fetches user permissions
3. Server sends initial monitoring data
4. Server broadcasts updates based on user permissions

### WebSocket Events

The server sends JSON messages with the following structure:

```json
{
  "event": "pipeline_update",
  "data": {
    "total_documents": 1250,
    "documents_completed": 1180,
    "success_rate": 98.91
  },
  "timestamp": "2025-11-02T10:35:00Z"
}
```

**Event Types:**

| Event | Description | Permission Required |
|-------|-------------|---------------------|
| `pipeline_update` | Pipeline metrics changed | `monitoring:read` |
| `queue_update` | Queue status changed | `monitoring:read` |
| `hardware_update` | Hardware metrics changed | `monitoring:read` |
| `alert_triggered` | New alert triggered | `alerts:read` |
| `stage_completed` | Stage completed for document | `monitoring:read` |
| `stage_failed` | Stage failed for document | `monitoring:read` |

**Example: Alert Triggered**

```json
{
  "event": "alert_triggered",
  "data": {
    "id": "alert-001",
    "alert_type": "processing_failure",
    "severity": "high",
    "title": "High Processing Failure Rate",
    "message": "Processing failure rate is 12.5%, exceeding threshold of 10%",
    "triggered_at": "2025-11-02T10:30:00Z"
  },
  "timestamp": "2025-11-02T10:30:00Z"
}
```

**Example: Stage Completed**

```json
{
  "event": "stage_completed",
  "data": {
    "stage_name": "text_extraction",
    "document_id": "doc-123",
    "status": "completed"
  },
  "timestamp": "2025-11-02T10:30:05Z"
}
```

### Broadcast Frequency

- **Pipeline/Queue/Hardware updates:** Every 10 seconds
- **Alert triggers:** Immediate broadcast
- **Stage events:** Real-time as they occur

### Error Handling

If authentication fails or permissions are insufficient, the WebSocket connection will be closed with an appropriate code:

- `1008`: Invalid token or insufficient permissions
- `1011`: Internal server error

---

## Legacy Endpoints

The following endpoints are deprecated and maintained for backward compatibility. Use the new endpoints above instead.

### Get Pipeline Status (Legacy)

**Endpoint:** `GET /api/v1/monitoring/status`

**Status:** ⚠️ DEPRECATED - Use `/api/v1/monitoring/pipeline` instead

**Permissions:** `monitoring:read`

### Get Stage Status (Legacy)

**Endpoint:** `GET /api/v1/monitoring/stages`

**Status:** ⚠️ DEPRECATED - Use `/api/v1/monitoring/pipeline` instead

**Permissions:** `monitoring:read`

### Get Hardware Status (Legacy)

**Endpoint:** `GET /api/v1/monitoring/hardware`

**Status:** ⚠️ DEPRECATED - Use `/api/v1/monitoring/metrics` instead

**Permissions:** `monitoring:read`

### Reset Monitoring (Legacy)

**Endpoint:** `POST /api/v1/monitoring/reset`

**Status:** ⚠️ DEPRECATED - Admin only

**Permissions:** `monitoring:write`

### Start Monitoring (Legacy)

**Endpoint:** `POST /api/v1/monitoring/start`

**Status:** ⚠️ DEPRECATED - Admin only

**Permissions:** `monitoring:write`

---

## Performance Optimization

### Server-Side Aggregation

All metrics endpoints use server-side aggregated views for optimal performance:

- **Pipeline metrics:** `vw_pipeline_metrics_aggregated`
- **Queue metrics:** `vw_queue_metrics_aggregated`
- **Stage metrics:** `vw_stage_metrics_aggregated`

This eliminates full table scans and Python-side aggregation, ensuring scalability with large datasets.

### Caching

Metrics are cached with the following TTLs:

- **Pipeline/Queue/Stage metrics:** 5 seconds
- **Hardware metrics:** 1 second
- **Data quality metrics:** 5 seconds

Cache can be invalidated manually via the `MetricsService.invalidate_cache()` method.

### Database Indexes

The following indexes optimize monitoring queries:

```sql
-- Alerts
CREATE INDEX idx_alerts_triggered_at ON krai_system.alerts(triggered_at DESC);
CREATE INDEX idx_alerts_severity ON krai_system.alerts(severity);
CREATE INDEX idx_alerts_acknowledged ON krai_system.alerts(acknowledged);
CREATE INDEX idx_alerts_type ON krai_system.alerts(alert_type);

-- Alert Rules
CREATE INDEX idx_alert_rules_enabled ON krai_system.alert_rules(enabled);

-- System Metrics
CREATE INDEX idx_system_metrics_type ON krai_system.system_metrics(metric_type);
CREATE INDEX idx_system_metrics_timestamp ON krai_system.system_metrics(collection_timestamp DESC);
```

---

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**

```json
{
  "detail": "Invalid parameter: severity must be one of [low, medium, high, critical]"
}
```

**401 Unauthorized:**

```json
{
  "detail": "Not authenticated"
}
```

**403 Forbidden:**

```json
{
  "detail": "Insufficient permissions: monitoring:read required"
}
```

**404 Not Found:**

```json
{
  "detail": "Alert not found"
}
```

**500 Internal Server Error:**

```json
{
  "detail": "Failed to get pipeline metrics: Database connection error"
}
```

---

## Health Check

The monitoring system status is included in the main health check endpoint:

**Endpoint:** `GET /health`

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-11-02T10:35:00Z",
  "services": {
    "monitoring": {
      "status": "healthy",
      "message": "Monitoring services active",
      "metrics_service": "initialized",
      "alert_service": "initialized",
      "websocket_connections": 5
    }
  }
}
```

---

## Example Usage

### Python Client

```python
import requests
import websocket
import json

# Authentication
token = "your_jwt_token"
headers = {"Authorization": f"Bearer {token}"}

# Get pipeline metrics
response = requests.get(
    "http://localhost:8000/api/v1/monitoring/pipeline",
    headers=headers
)
metrics = response.json()
print(f"Success rate: {metrics['success_rate']}%")

# WebSocket connection
def on_message(ws, message):
    data = json.loads(message)
    print(f"Event: {data['event']}")
    print(f"Data: {data['data']}")

ws = websocket.WebSocketApp(
    f"ws://localhost:8000/ws/monitoring?token={token}",
    on_message=on_message
)
ws.run_forever()
```

### JavaScript Client

```javascript
// Fetch pipeline metrics
const response = await fetch('/api/v1/monitoring/pipeline', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const metrics = await response.json();
console.log(`Success rate: ${metrics.success_rate}%`);

// WebSocket connection
const ws = new WebSocket(`ws://localhost:8000/ws/monitoring?token=${token}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Event: ${data.event}`);
  console.log(`Data:`, data.data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

---

## Migration Guide

If you're using legacy endpoints, migrate to the new API:

| Legacy Endpoint | New Endpoint | Notes |
|----------------|--------------|-------|
| `GET /monitoring/status` | `GET /api/v1/monitoring/pipeline` | Returns same data structure |
| `GET /monitoring/stages` | `GET /api/v1/monitoring/pipeline` | Stage data included in pipeline response |
| `GET /monitoring/hardware` | `GET /api/v1/monitoring/metrics` | Returns same data structure |
| `POST /monitoring/reset` | N/A | Deprecated - use database operations |
| `POST /monitoring/start` | N/A | Deprecated - automatic tracking |

---

## Support

For issues or questions about the Monitoring API:

1. Check the logs: `backend/logs/monitoring.log`
2. Verify permissions in the database: `krai_users.users` table
3. Check alert rules: `krai_system.alert_rules` table
4. Review active alerts: `krai_system.vw_active_alerts` view

---

**Last Updated:** 2025-11-02
**API Version:** 1.0
**Status:** Production Ready
