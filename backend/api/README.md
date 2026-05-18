# KRAI Processing Pipeline API

FastAPI-based REST API for monitoring, managing, and controlling the document processing pipeline.

## 🚀 Quick Start

### Start API Server

```bash
# Windows
cd backend/api
./start_api.bat

# Linux/macOS
python app.py
```

The API will start on `http://localhost:8000`

## 📚 Documentation

Once running, access:
- **Interactive Docs (Swagger):** http://localhost:8000/docs
- **Alternative Docs (ReDoc):** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## 🔌 API Endpoints

### System

#### `GET /`
Root endpoint with API info

**Response:**
```json
{
  "service": "KRAI Processing Pipeline API",
  "version": "0.50.0",
  "status": "running",
  "documentation": "/docs"
}
```

#### `GET /health`
Health check for all services

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-04T07:00:00.000Z",
  "services": {
    "api": {"status": "healthy", "message": "API is running"},
    "database": {"status": "healthy", "message": "Database connected"},
    "ollama": {"status": "healthy", "message": "3 models available"},
    "storage": {"status": "configured", "message": "OBJECT_STORAGE credentials present"}
  }
}
```

### Upload

#### `POST /upload`
Upload a single document

**Request:**
- **file:** PDF file (multipart/form-data)
- **document_type:** Type of document (service_manual, parts_catalog, user_guide)
- **force_reprocess:** Force reprocessing if document exists (boolean)

**Example (curl):**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@document.pdf" \
  -F "document_type=service_manual" \
  -F "force_reprocess=false"
```

**Response:**
```json
{
  "success": true,
  "document_id": "f360e0ad-59fc-4bb3-b176-5928a14d7021",
  "status": "new",
  "message": "Upload successful",
  "metadata": {
    "filename": "document.pdf",
    "page_count": 4386,
    "file_size_bytes": 45678912,
    "title": "Service Manual"
  }
}
```

#### `POST /upload/directory`
Upload all PDFs from a directory

**Request Body:**
```json
{
  "directory_path": "/path/to/pdfs",
  "document_type": "service_manual",
  "recursive": false,
  "force_reprocess": false
}
```

**Response:**
```json
{
  "total": 10,
  "successful": 9,
  "failed": 1,
  "duplicates": 3,
  "reprocessed": 0,
  "documents": [...]
}
```

### Status & Monitoring

#### `GET /status/{document_id}`
Get processing status for a specific document

**Example:**
```bash
curl "http://localhost:8000/status/f360e0ad-59fc-4bb3-b176-5928a14d7021"
```

**Response:**
```json
{
  "document_id": "f360e0ad-59fc-4bb3-b176-5928a14d7021",
  "status": "processing",
  "current_stage": "text_extraction",
  "progress": 25.0,
  "started_at": "2025-10-04T07:00:00.000Z",
  "completed_at": null,
  "error": null
}
```

#### `GET /status`
Get overall pipeline status

**Response:**
```json
{
  "total_documents": 150,
  "in_queue": 5,
  "processing": 2,
  "completed": 140,
  "failed": 3,
  "by_stage": {
    "upload": 5,
    "text_extraction": 2,
    "image_processing": 0,
    "classification": 0,
    "metadata_extraction": 0,
    "storage": 0,
    "embedding": 0,
    "search": 143
  }
}
```

#### `GET /logs/{document_id}`
Get processing logs for a document

**Response:**
```json
{
  "document_id": "f360e0ad-59fc-4bb3-b176-5928a14d7021",
  "log_count": 15,
  "logs": [
    {
      "timestamp": "2025-10-04T07:00:00.000Z",
      "action": "stage_completed",
      "details": {"stage": "text_extraction", "duration": 45.2}
    }
  ]
}
```

#### `GET /metrics`
Get system performance metrics

**Response:**
```json
{
  "timestamp": "2025-10-04T07:00:00.000Z",
  "cpu_usage": 45.2,
  "memory_usage": 8192,
  "gpu_usage": 80.5,
  "documents_per_hour": 12.5,
  "average_processing_time": 185.3
}
```

## 🧪 Testing

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Upload document
curl -X POST "http://localhost:8000/upload" \
  -F "file=@test.pdf" \
  -F "document_type=service_manual"

# Check status
curl http://localhost:8000/status

# Get specific document status
curl http://localhost:8000/status/{document_id}
```

### Testing with Swagger UI

1. Open http://localhost:8000/docs
2. Click "Try it out" on any endpoint
3. Fill in parameters
4. Click "Execute"
5. See response

### Testing with Python

```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# Upload document
with open("test.pdf", "rb") as f:
    files = {"file": f}
    data = {"document_type": "service_manual"}
    response = requests.post(
        "http://localhost:8000/upload",
        files=files,
        data=data
    )
    print(response.json())
```

## 🔧 Configuration

Environment variables (`.env` file):

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_key

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Upload limits
MAX_FILE_SIZE_MB=500

# Object Storage (MinIO / S3-compatible)
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_USE_SSL=false
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_BUCKET_DOCUMENTS=documents
OBJECT_STORAGE_BUCKET_ERROR=error-images
OBJECT_STORAGE_BUCKET_PARTS=parts-images
OBJECT_STORAGE_PUBLIC_URL_DOCUMENTS=http://localhost:9000/documents
OBJECT_STORAGE_PUBLIC_URL_ERROR=http://localhost:9000/error-images
OBJECT_STORAGE_PUBLIC_URL_PARTS=http://localhost:9000/parts-images
```

Use only `OBJECT_STORAGE_*` variables. See `docs/MIGRATION_R2_TO_MINIO.md` for storage migration details.

## 📊 Monitoring

### Real-time Monitoring

The API provides several endpoints for monitoring:

1. **System Health:** `/health` - Check all services
2. **Pipeline Status:** `/status` - Overall progress
3. **Document Status:** `/status/{id}` - Individual documents
4. **Logs:** `/logs/{id}` - Processing logs
5. **Metrics:** `/metrics` - Performance metrics

### Dashboard Integration

The API can be integrated with monitoring dashboards like:
- Grafana
- Prometheus
- Laravel/Filament dashboard (existing at http://localhost:80)

### Webhooks (Future)

Future versions will support webhooks for:
- Document processing completed
- Stage transitions
- Error notifications

## 🐛 Troubleshooting

### API won't start

```bash
# Check Python version
python --version  # Should be 3.9+

# Check dependencies
pip install -r requirements.txt

# Check environment variables
cat .env  # Linux/macOS
type .env  # Windows
```

### Database connection failed

- Check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Test connection: `curl http://localhost:8000/health`
- Check Supabase dashboard

### Ollama not responding

- Check if Ollama is running: `ollama list`
- Start Ollama: `ollama serve`
- Check OLLAMA_BASE_URL in .env

## 🚀 Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
    restart: unless-stopped
```

### Systemd Service (Linux)

```ini
[Unit]
Description=KRAI Processing Pipeline API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/krai/backend/api
ExecStart=/opt/krai/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📝 Development

### Adding New Endpoints

1. Define Pydantic models for request/response
2. Add endpoint function with proper decorators
3. Add dependency injection for services
4. Document with docstrings
5. Test with Swagger UI

### Example:

```python
from fastapi import Depends
from pydantic import BaseModel

class MyRequest(BaseModel):
    param: str

class MyResponse(BaseModel):
    result: str

@app.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(
    request: MyRequest,
    supabase=Depends(get_supabase)
):
    """
    My endpoint description

    Args:
        request: Request parameters

    Returns:
        Result data
    """
    # Implementation
    return MyResponse(result="success")
```

## 📄 License

MIT License - See LICENSE file

## 🙏 Credits

- FastAPI - Modern web framework
- Uvicorn - ASGI server
- Pydantic - Data validation
- Supabase - Database & auth
