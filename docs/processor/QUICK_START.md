# Pipeline Quick Start Guide

This guide provides practical examples for using the KRAI document processing pipeline through CLI, API, and dashboard interfaces.

## Prerequisites

### System Requirements
- Docker services running (PostgreSQL, MinIO, Ollama)
- Python 3.9+ with required dependencies
- Sufficient disk space for document storage
- GPU recommended for embedding and vision tasks

### Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Start services
docker-compose up -d

# Install Python dependencies
pip install -r requirements.txt
```

### Verify Services
```bash
# Check PostgreSQL
docker exec krai-postgres psql -U krai_user -d krai -c "SELECT 1"

# Check MinIO
curl http://localhost:9000/minio/health/live

# Check Ollama
curl http://localhost:11434/api/tags

# Check Backend API
curl http://localhost:8000/health
```

## CLI Usage

### Basic Commands

#### Process Single Document (Full Pipeline)
```bash
python scripts/pipeline_processor.py --file /path/to/document.pdf \
  --document-type service_manual \
  --language en
```

#### Process Specific Stages
```bash
# Single stage by name
python scripts/pipeline_processor.py --document-id <uuid> --stage text_extraction

# Multiple stages by number
python scripts/pipeline_processor.py --document-id <uuid> --stages 1,2,5

# Multiple stages by name
python scripts/pipeline_processor.py --document-id <uuid> --stages text_extraction,image_processing
```

#### Smart Processing (Skip Completed)
```bash
python scripts/pipeline_processor.py --document-id <uuid> --smart
```

#### Batch Processing
```bash
# Process directory
python scripts/pipeline_processor.py --batch --directory /path/to/documents/

# Process with specific stages
python scripts/pipeline_processor.py --batch --directory /path/to/pdfs/ --stages 1,2,3
```

#### Status and Information
```bash
# List all available stages
python scripts/pipeline_processor.py --list-stages

# Check document status
python scripts/pipeline_processor.py --document-id <uuid> --status

# Show detailed stage information
python scripts/pipeline_processor.py --document-id <uuid> --status --verbose
```

### Advanced CLI Examples

#### Text-Only Processing
```bash
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages text_extraction,chunk_prep,embedding,search_indexing
```

#### Images-Only Processing
```bash
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages image_processing,visual_embedding,storage
```

#### Debug Failed Stage
```bash
# Re-run failed stage with verbose logging
python scripts/pipeline_processor.py --document-id <uuid> \
  --stage metadata_extraction --verbose --debug
```

#### Custom Configuration
```bash
python scripts/pipeline_processor.py --document-id <uuid> \
  --stage embedding --model nomic-embed-text --batch-size 10
```

## API Usage

### Authentication
```bash
# Get JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Store token for subsequent requests
export TOKEN="your_jwt_token_here"
```

### Document Upload
```bash
# Upload document
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf" \
  -F "document_type=service_manual" \
  -F "language=en" \
  -F "manufacturer=brother"
```

### Stage Processing

#### Single Stage
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/text_extraction \
  -H "Authorization: Bearer $TOKEN"
```

#### Multiple Stages
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stages": ["text_extraction", "image_processing"],
    "stop_on_error": true,
    "priority": "high"
  }'
```

#### Smart Processing
```bash
curl -X POST http://localhost:8000/documents/{id}/process/smart \
  -H "Authorization: Bearer $TOKEN"
```

### Status Monitoring

#### Get Stage Status
```bash
curl http://localhost:8000/documents/{id}/stages/status \
  -H "Authorization: Bearer $TOKEN"
```

#### Get Available Stages
```bash
curl http://localhost:8000/documents/{id}/stages \
  -H "Authorization: Bearer $TOKEN"
```

#### Get Processing History
```bash
curl http://localhost:8000/documents/{id}/processing/history \
  -H "Authorization: Bearer $TOKEN"
```

### Advanced API Examples

#### Process with Custom Parameters
```bash
curl -X POST http://localhost:8000/documents/{id}/process/stage/embedding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "batch_size": 5,
    "normalize": true
  }'
```

#### Batch Process Multiple Documents
```bash
curl -X POST http://localhost:8000/documents/batch/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["uuid1", "uuid2", "uuid3"],
    "stages": ["text_extraction", "embedding"],
    "parallel": true
  }'
```

## Dashboard Usage

### Access Dashboard
```bash
# Navigate to Laravel Dashboard
http://localhost/admin

# Login with admin credentials
Username: admin
Password: your_admin_password
```

### Document Upload via Dashboard

1. **Navigate to Documents**: Click "Documents" in the sidebar
2. **Upload Document**: Click "New Document" button
3. **Fill Metadata**:
   - Upload PDF file
   - Select document type
   - Choose language
   - Optional: Specify manufacturer
4. **Processing Options**:
   - "Auto-process all stages" (default)
   - "Select specific stages" (advanced)
5. **Save**: Click "Save" to upload and start processing

### Stage Processing via Dashboard

#### Single Stage Processing
1. **Select Document**: Go to Documents list, click on document
2. **Stage Actions**: Click "Stage verarbeiten" dropdown
3. **Choose Stage**: Select desired stage from dropdown
4. **Execute**: Click "Process" to start stage

#### Multiple Stage Processing
1. **Select Document**: Open document details
2. **Bulk Actions**: Click "Mehrere Stages verarbeiten"
3. **Select Stages**: Check desired stages in modal
4. **Configure Options**:
   - Stop on error (yes/no)
   - Processing priority
5. **Execute**: Click "Process Selected Stages"

#### Smart Processing
1. **Select Document**: Open document details
2. **Smart Process**: Click "Smart verarbeiten"
3. **Review**: System shows which stages will run
4. **Execute**: Click "Start Smart Processing"

### Status Monitoring

#### Document Status Grid
- **Color-coded badges** for each stage:
  - 🟢 Green: Completed
  - 🟡 Yellow: In Progress
  - 🔴 Red: Failed
  - ⚪ Gray: Pending

#### Detailed Status View
1. **Open Document**: Click document in list
2. **Stage Details**: Scroll to "Processing Status" section
3. **Stage Information**:
   - Start/end times
   - Processing duration
   - Error messages (if failed)
   - Retry options

#### Real-time Updates
- **WebSocket Connection**: Live status updates
- **Auto-refresh**: Status updates automatically
- **Notifications**: Browser notifications for completed/failed stages

### Advanced Dashboard Features

#### Bulk Operations
1. **Select Multiple Documents**: Use checkboxes in Documents list
2. **Bulk Actions**: Click "Aktionen" dropdown
3. **Available Actions**:
   - "Process Stages" - Run specific stages on selected documents
   - "Smart Process" - Skip completed stages
   - "Reprocess Failed" - Retry failed stages
   - "Export Status" - Download status report

#### Search and Filter
1. **Filter by Status**: Show only documents with specific stage statuses
2. **Search by Content**: Search within document text
3. **Filter by Metadata**: Manufacturer, document type, date range
4. **Custom Filters**: Save frequently used filter combinations

#### Performance Monitoring
1. **Processing Statistics**: "Analytics" → "Pipeline Performance"
2. **Stage Performance**: Average processing times per stage
3. **Resource Usage**: CPU, memory, GPU utilization
4. **Error Rates**: Failure rates by stage and document type

## Python SDK Usage

### Basic Setup
```python
from backend.pipeline.master_pipeline import KRMasterPipeline
from backend.core.base_processor import Stage
from backend.config.database_config import get_database_adapter

# Initialize database adapter
db_adapter = get_database_adapter()

# Initialize pipeline
pipeline = KRMasterPipeline(
    database_adapter=db_adapter,
    force_continue_on_errors=True
)
```

### Document Processing

#### Full Pipeline
```python
# Process document through all stages
result = await pipeline.process_document(
    file_path="/path/to/document.pdf",
    document_type="service_manual",
    language="en"
)

print(f"Document ID: {result.document_id}")
print(f"Processing Status: {result.status}")
```

#### Single Stage
```python
# Process specific stage
result = await pipeline.run_single_stage(
    document_id="uuid",
    stage_name=Stage.TEXT_EXTRACTION.value
)

print(f"Stage Status: {result.status}")
print(f"Processing Time: {result.duration} seconds")
```

#### Multiple Stages
```python
# Process multiple stages
stages = [
    Stage.TEXT_EXTRACTION.value,
    Stage.IMAGE_PROCESSING.value,
    Stage.EMBEDDING.value
]

result = await pipeline.run_stages(
    document_id="uuid",
    stages=stages,
    stop_on_error=True
)

print(f"Completed Stages: {result.completed_stages}")
print(f"Failed Stages: {result.failed_stages}")
```

#### Smart Processing
```python
# Skip completed stages
result = await pipeline.smart_process_document(document_id="uuid")

print(f"Stages Executed: {result.executed_stages}")
print(f"Stages Skipped: {result.skipped_stages}")
```

### Status Monitoring

#### Get Stage Status
```python
# Get all stage status
status = await pipeline.get_stage_status(document_id="uuid")

for stage_name, stage_info in status.items():
    print(f"{stage_name}: {stage_info['status']}")
    if stage_info['status'] == 'failed':
        print(f"  Error: {stage_info['error']}")
```

#### Get Processing History
```python
# Get processing history
history = await pipeline.get_processing_history(document_id="uuid")

for entry in history:
    print(f"Stage: {entry['stage_name']}")
    print(f"Started: {entry['started_at']}")
    print(f"Duration: {entry['duration']} seconds")
    print(f"Status: {entry['status']}")
```

### Advanced SDK Usage

#### Custom Stage Configuration
```python
# Configure stage with custom parameters
result = await pipeline.run_single_stage(
    document_id="uuid",
    stage_name=Stage.EMBEDDING.value,
    model="nomic-embed-text",
    batch_size=10,
    normalize=True
)
```

#### Batch Processing
```python
# Process multiple documents
document_ids = ["uuid1", "uuid2", "uuid3"]
stages = [Stage.TEXT_EXTRACTION.value, Stage.EMBEDDING.value]

results = await pipeline.batch_process_documents(
    document_ids=document_ids,
    stages=stages,
    parallel=True,
    max_concurrent=3
)

for doc_id, result in results.items():
    print(f"{doc_id}: {result.status}")
```

#### Error Handling
```python
try:
    result = await pipeline.run_single_stage(
        document_id="uuid",
        stage_name=Stage.METADATA_EXTRACTION.value
    )
except ProcessingError as e:
    print(f"Processing failed: {e}")
    print(f"Stage: {e.stage_name}")
    print(f"Document: {e.document_id}")
    print(f"Error: {e.error_message}")
```

## Common Workflows

### Full Document Processing
```bash
# CLI
python scripts/pipeline_processor.py --file manual.pdf --document-type service_manual

# API
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@manual.pdf" -F "document_type=service_manual"

# Dashboard: Upload with "Auto-process all stages"
```

### Text-Only Processing
```bash
# CLI
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages text_extraction,chunk_prep,embedding,search_indexing

# API
curl -X POST http://localhost:8000/documents/{id}/process/stages \
  -d '{"stages": ["text_extraction", "chunk_prep", "embedding", "search_indexing"]}'
```

### Images-Only Processing
```bash
# CLI
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages image_processing,visual_embedding,storage

# Dashboard: Select stages "IMAGE_PROCESSING", "VISUAL_EMBEDDING", "STORAGE"
```

### Reprocess Failed Stages
```bash
# Check status
python scripts/pipeline_processor.py --document-id <uuid> --status

# Re-run failed stage
python scripts/pipeline_processor.py --document-id <uuid> --stage metadata_extraction

# Or smart processing (skips completed)
python scripts/pipeline_processor.py --document-id <uuid> --smart
```

### Incremental Processing
```bash
# Start with basic stages
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages upload,text_extraction,chunk_prep

# Add enrichment later
python scripts/pipeline_processor.py --document-id <uuid> \
  --stages embedding,search_indexing
```

## Monitoring

### Log Monitoring
```bash
# Follow backend logs
docker logs krai-engine -f

# Filter by document
docker logs krai-engine | grep "document_id=uuid"

# Filter by stage
docker logs krai-engine | grep "stage=embedding"
```

### Database Monitoring
```bash
# Check document status
psql -h localhost -U krai_user -d krai -c "
SELECT id, filename, stage_status
FROM krai_core.documents
WHERE id = 'uuid';
"

# Check processing statistics
psql -h localhost -U krai_user -d krai -c "
SELECT
    stage_status->>'status' as status,
    COUNT(*) as count
FROM krai_core.documents, jsonb_each(stage_status)
GROUP BY stage_status->>'status';
"
```

### Performance Monitoring
```bash
# Check system resources
docker stats

# Check GPU usage (if available)
nvidia-smi

# Check database performance
docker exec krai-postgres psql -U krai_user -d krai -c "
SELECT
    schemaname,
    tablename,
    n_tup_ins,
    n_tup_upd,
    n_tup_del
FROM pg_stat_user_tables;
"
```

## Troubleshooting

### Common Issues

#### Stage Fails with Error
```bash
# Check detailed logs
python scripts/pipeline_processor.py --document-id <uuid> --stage <stage_name> --verbose

# Check stage dependencies
python scripts/pipeline_processor.py --document-id <uuid> --status

# Retry failed stage
python scripts/pipeline_processor.py --document-id <uuid> --stage <stage_name>
```

#### Dependencies Missing
```bash
# Check if prerequisite stages completed
python scripts/pipeline_processor.py --document-id <uuid> --status

# Run missing dependencies
python scripts/pipeline_processor.py --document-id <uuid> --stages <dependency_stages>
```

#### Timeout Issues
```bash
# Increase timeout in configuration
export PROCESSING_TIMEOUT=300

# Or process stages individually
python scripts/pipeline_processor.py --document-id <uuid> --stages 1,2,3
```

#### Resource Issues
```bash
# Check available memory
free -h

# Check disk space
df -h

# Check GPU memory
nvidia-smi

# Reduce batch size for memory-intensive stages
python scripts/pipeline_processor.py --document-id <uuid> --stage embedding --batch-size 5
```

### Error Messages and Solutions

#### "Stage dependency not met"
- **Cause**: Prerequisite stage not completed
- **Solution**: Run prerequisite stage first
- **Command**: Check status with `--status`, run missing stages

#### "GPU memory insufficient"
- **Cause**: Not enough GPU memory for embeddings
- **Solution**: Reduce batch size or use CPU
- **Command**: `--batch-size 5` or `--device cpu`

#### "Document not found"
- **Cause**: Invalid document ID
- **Solution**: Check document ID in database
- **Command**: `psql -h localhost -U krai_user -d krai -c "SELECT id FROM krai_core.documents LIMIT 10;"`

#### "Storage upload failed"
- **Cause**: MinIO connection issues
- **Solution**: Check MinIO service and permissions
- **Command**: `docker logs krai-minio`, `curl http://localhost:9000/minio/health/live`

### Performance Tips

1. **Batch Processing**: Process multiple documents together for better resource utilization
2. **Selective Stages**: Skip unnecessary stages (e.g., text-only processing)
3. **GPU Optimization**: Ensure NVIDIA Container Toolkit for embedding stages
4. **Memory Management**: Adjust batch sizes based on available memory
5. **Parallel Processing**: Use `--parallel` flag for independent stages

## Related Documentation

- **Pipeline Architecture**: `docs/processor/PIPELINE_ARCHITECTURE.md`
- **Stage Reference**: `docs/processor/STAGE_REFERENCE.md`
- **API Documentation**: `docs/api/STAGE_BASED_PROCESSING.md`
- **Dashboard Integration**: `docs/LARAVEL_DASHBOARD_INTEGRATION.md`
- **Troubleshooting**: `docs/processor/TROUBLESHOOTING.md`
- **Architecture**: `docs/ARCHITECTURE.md`
