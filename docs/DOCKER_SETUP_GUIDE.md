# Docker Setup Guide for KRAI Phase 6

## Table of Contents

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start-5-minutes)
- [Phase 6 Features Setup](#phase-6-features-setup)
- [Detailed Setup](#detailed-setup)
- [Service Configuration](#service-configuration)
- [Phase 6 Configuration](#phase-6-configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)
- [Migration from Cloud](#migration-from-cloud)

## Introduction

### Why Local Docker Setup?

- **Zero Cloud Costs**: Save $50-100/month compared to managed PostgreSQL + S3 + Ollama hosting
- **Faster Development**: No network latency, local debugging capabilities
- **Full Control**: No vendor lock-in, customize everything
- **Privacy & Security**: Data stays on your local machine
- **Offline Development**: Work without internet connection
- **Phase 6 Features**: Access to advanced multimodal AI capabilities locally

### Phase 6 Architecture Overview

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Backend App   │    │      n8n        │    │  pgAdmin Web    │
│   (Python)      │    │   (Workflows)   │    │   Interface     │
│  + Phase 6 AI   │    │ + Multimodal    │    │ + Enhanced UI   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      MinIO      │    │     Ollama      │
│   (Database)    │    │  (Object Store) │    │   (AI Service)  │
│ + Multimodal    │    │ + Deduplication │    │ + Vision AI     │
│   Port: 5432    │    │ Port: 9000/9001 │    │   Port: 11434   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                      ▲                      ▲
         └──────────────────────┼──────────────────────┘
                                │
                    ┌─────────────────┐
                    │  krai-network   │
                    │   (Docker)      │
                    └─────────────────┘
```

### Phase 6 New Features

- **Hierarchical Document Structure Detection** with section linking
- **SVG Vector Graphics Processing** with Vision AI analysis
- **Multimodal Search** across text, images, videos, tables, and links
- **Advanced Context Extraction** for all media types
- **Enhanced Vector Embeddings** with unified multimodal support
- **Cross-Chunk Linking** for improved navigation

## Prerequisites

### System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Docker Desktop**: 4.25+ with Docker Compose v2
- **RAM**: 16GB minimum (32GB+ recommended for Phase 6 multimodal AI processing)
- **Storage**: 100GB free disk space (for models, data, and Phase 6 features)
- **CPU**: 6+ cores recommended (for parallel multimodal processing)
- **GPU**: NVIDIA GPU with 12GB+ VRAM (recommended for Phase 6 Vision AI and SVG processing)

### Phase 6 Additional Requirements

- **Vector Graphics Support**: Modern GPU for SVG to PNG conversion
- **Multimodal Processing**: Additional RAM for context extraction
- **Enhanced Storage**: Space for multimodal embeddings and context data
- **Network Bandwidth**: For downloading larger AI models (llava-phi3, etc.)

### Software Installation

#### Docker Desktop

1. Download from [docker.com](https://www.docker.com/products/docker-desktop)
2. Install and start Docker Desktop
3. Verify installation: `docker --version` and `docker-compose --version`

#### NVIDIA GPU Support (Optional)

1. Install NVIDIA drivers (latest version)
2. Install NVIDIA Container Toolkit:

   ```bash
   # For Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/ \
     nvidia-docker.list \
     | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

#### Python 3.11+

1. Download from [python.org](https://www.python.org/downloads/)
2. Or use system package manager: `brew install python@3.11` (macOS)

## Quick Start (5 Minutes)

Get KRAI running locally with these commands:

```bash
# 1. Clone repository
git clone <your-repo-url>
cd KRAI-minimal

# 2. Copy environment configuration
cp .env.example .env

# 3. Start local services
docker-compose -f docker-compose.simple.yml up -d

# 4. Initialize MinIO storage
python scripts/init_minio.py

# 5. Pull AI models (takes a few minutes)
docker exec krai-ollama ollama pull nomic-embed-text:latest
docker exec krai-ollama ollama pull llama3.1:8b:latest
docker exec krai-ollama ollama pull llava-phi3:latest

# 6. Verify everything is working
python scripts/verify_local_setup.py

# 7. Test Phase 6 features
python scripts/test_phase6_features.py
```

### Expected Output

After successful setup, you should see:

- ✅ All 7 services healthy
- ✅ 4 MinIO buckets created
- ✅ 3+ Ollama models available (including Vision AI)
- ✅ PostgreSQL with 10 schemas (including Phase 6)
- ✅ Phase 6 multimodal features enabled

### Access Points

- **MinIO Console**: <http://localhost:9001> (admin/minioadmin123)
- **pgAdmin**: <http://localhost:5050> (<admin@krai.local>/krai_admin_2024)
- **n8n**: <http://localhost:5678> (admin/krai_chat_agent_2024)
- **Ollama API**: <http://localhost:11434>

## Phase 6 Features Setup

### Enable Phase 6 Features

Add these environment variables to your `.env` file:

```bash
# Phase 6 Advanced Features
ENABLE_HIERARCHICAL_CHUNKING=true
ENABLE_SVG_EXTRACTION=true
ENABLE_MULTIMODAL_SEARCH=true
ENABLE_CONTEXT_EXTRACTION=true

# Phase 6 AI Models
VISION_AI_MODEL=llava-phi3
CONTEXT_EMBEDDING_MODEL=nomic-embed-text
MULTIMODAL_SEARCH_THRESHOLD=0.5

# Phase 6 Performance
EMBEDDING_BATCH_SIZE=10
VISION_AI_BATCH_SIZE=3
MAX_CONCURRENT_AI_REQUESTS=20
```

### Phase 6 Database Setup

Run the Phase 6 migrations:

```bash
# Apply Phase 6 database schema
python scripts/apply_phase6_migrations.py

# Verify Phase 6 tables
python scripts/verify_phase6_schema.py
```

### Phase 6 Model Requirements

Download additional models for Phase 6:

```bash
# Vision model for SVG and image analysis (3.8GB)
docker exec krai-ollama ollama pull llava-phi3:latest

# Enhanced text model for context extraction (4.7GB)
docker exec krai-ollama ollama pull llama3.1:8b:latest

# Verify models are loaded
docker exec krai-ollama ollama list
```

### Test Phase 6 Features

```bash
# Test hierarchical chunking
python scripts/test_hierarchical_chunking.py

# Test SVG extraction and processing
python scripts/test_svg_extraction.py

# Test multimodal search
python scripts/test_multimodal_search.py

# Test context extraction
python scripts/test_context_extraction_integration.py

# Run comprehensive Phase 6 test suite
python scripts/test_full_pipeline_phases_1_6.py
```

## Detailed Setup

### Step 1: Environment Configuration

The `.env` file controls all service behavior. Key sections:

#### Database Configuration

```bash
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=krai
DATABASE_USER=krai_user
DATABASE_PASSWORD=krai_secure_password
```

#### Object Storage Configuration

```bash
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin123
```

#### AI Service Configuration

```bash
AI_SERVICE_TYPE=ollama
AI_SERVICE_URL=http://localhost:11434
AI_EMBEDDING_MODEL=nomic-embed-text:latest
AI_TEXT_MODEL=llama3.1:8b:latest
AI_VISION_MODEL=llava-phi3:latest

# Phase 6 AI Settings
VISION_AI_ENABLED=true
CONTEXT_EXTRACTION_ENABLED=true
MULTIMODAL_SEARCH_ENABLED=true
HIERARCHICAL_CHUNKING_ENABLED=true
```

#### Phase 6 Performance Configuration

```bash
# Batch Processing
EMBEDDING_BATCH_SIZE=10
VISION_AI_BATCH_SIZE=3
CONTEXT_EXTRACTION_BATCH_SIZE=5

# Performance Tuning
MAX_CONCURRENT_AI_REQUESTS=20
AI_SERVICE_TIMEOUT=30
AI_SERVICE_RETRY_ATTEMPTS=3

# Quality Settings
SVG_CONVERSION_DPI=300
SVG_MAX_DIMENSION=2048
CONTEXT_MAX_LENGTH=1000
```

### Step 2: Start Services

#### Basic Startup

```bash
docker-compose up -d
```

#### With Build (if you modified Dockerfiles)

```bash
docker-compose up -d --build
```

#### Docker Compose Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f krai-postgres
docker-compose logs -f krai-minio
docker-compose logs -f krai-ollama
```

#### Check Service Status

```bash
docker-compose ps
```

### Step 3: Initialize Storage

Run the MinIO initialization script:

```bash
python scripts/init_minio.py
```

This creates:

- `documents` bucket (private)
- `images` bucket (public)
- `videos` bucket (public)
- `temp` bucket (private)

#### Manual Bucket Creation (Alternative)

```bash
# Install MinIO client
curl https://dl.min.io/client/mc/release/linux-amd64/mc \
  --create-dirs \
  -o $HOME/minio-binaries/mc

chmod +x $HOME/minio-binaries/mc
export PATH=$PATH:$HOME/minio-binaries/mc

# Configure and create buckets
mc alias set local http://localhost:9000 minioadmin minioadmin123
mc mb local/documents
mc mb local/images
mc mb local/videos
mc mb local/temp
```

### Step 4: Pull AI Models

#### Required Models for Phase 6

```bash
# Embedding model (768MB) - for semantic search
docker exec krai-ollama ollama pull nomic-embed-text:latest

# Enhanced text generation model (4.7GB) - for chat, analysis, and context extraction
docker exec krai-ollama ollama pull llama3.1:8b:latest

# Vision model (3.8GB) - for image analysis, SVG processing, and multimodal search
docker exec krai-ollama ollama pull llava-phi3:latest

# Optional: Alternative models for specific use cases
docker exec krai-ollama ollama pull llama3.2:1b:latest  # Lightweight text model
docker exec krai-ollama ollama pull bakllava:7b:latest  # Alternative vision model
```

#### Phase 6 Model Sizes and VRAM Requirements

| Model | Size | VRAM Required | Phase 6 Use Case |
|-------|------|---------------|------------------|
| nomic-embed-text | 768MB | 1GB | Text embeddings, multimodal search |
| llama3.1:8b | 4.7GB | 8GB | Text generation, context extraction |
| llava-phi3 | 3.8GB | 6GB | Image analysis, SVG processing, Vision AI |
| llama3.2:1b | 1.4GB | 2GB | Lightweight text processing |
| bakllava:7b | 3.8GB | 4GB | Stable alternative vision model |

#### Phase 6 Model Verification

```bash
# Verify all models are loaded
docker exec krai-ollama ollama list

# Test vision model capabilities
curl http://localhost:11434/api/generate -d '{
  "model": "llava-phi3:latest",
  "prompt": "Describe this image",
  "images": ["iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="],
  "stream": false
}'

# Test embedding generation
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text:latest",
  "prompt": "Hierarchical document structure detection"
}'
```

### Step 5: Verify Setup

Run comprehensive verification:

```bash
python scripts/verify_local_setup.py
```

Or check specific services:

```bash
python scripts/verify_local_setup.py --service postgresql
python scripts/verify_local_setup.py --service minio
python scripts/verify_local_setup.py --service ollama
```

## Phase 6 Configuration

### Hierarchical Chunking Settings

```bash
# Enable hierarchical structure detection
ENABLE_HIERARCHICAL_CHUNKING=true

# Chunking parameters
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
MIN_CHUNK_SIZE=30

# Section detection
DETECT_ERROR_CODE_SECTIONS=true
LINK_CHUNKS=true
```

### SVG Processing Configuration

```bash
# Enable SVG extraction and processing
ENABLE_SVG_EXTRACTION=true

# SVG to PNG conversion settings
SVG_CONVERSION_DPI=300
SVG_MAX_DIMENSION=2048
SVG_QUALITY=95
SVG_BACKGROUND_COLOR=white
```

### Multimodal Search Settings

```bash
# Enable multimodal search capabilities
ENABLE_MULTIMODAL_SEARCH=true

# Search parameters
MULTIMODAL_SEARCH_THRESHOLD=0.5
MULTIMODAL_SEARCH_LIMIT=10
ENABLE_TWO_STAGE_RETRIEVAL=true
SEARCH_RESULT_MAX_AGE=3600
```

### Context Extraction Configuration

```bash
# Enable context extraction for all media types
ENABLE_CONTEXT_EXTRACTION=true

# AI models for context extraction
VISION_AI_MODEL=llava-phi3
CONTEXT_EMBEDDING_MODEL=nomic-embed-text

# Processing parameters
CONTEXT_EXTRACTION_BATCH_SIZE=5
MAX_CONTEXT_LENGTH=1000
```

### Phase 6 Performance Tuning

```bash
# Batch processing sizes
EMBEDDING_BATCH_SIZE=10
VISION_AI_BATCH_SIZE=3
CONTEXT_EXTRACTION_BATCH_SIZE=5

# Concurrency settings
MAX_CONCURRENT_UPLOADS=5
MAX_CONCURRENT_AI_REQUESTS=20

# Timeout and retry settings
AI_SERVICE_TIMEOUT=30
AI_SERVICE_RETRY_ATTEMPTS=3
PROCESSING_TIMEOUT=300
```

### Phase 6 Storage Configuration

```bash
# Enhanced storage for multimodal content
STORAGE_MAX_FILE_SIZE=100MB
ENABLE_FILE_DEDUPLICATION=true
TEMP_FILE_TTL=3600

# Image processing settings
IMAGE_MAX_WIDTH=2048
IMAGE_MAX_HEIGHT=2048
IMAGE_QUALITY=85
ENABLE_IMAGE_OPTIMIZATION=true
```

## Service Configuration

### PostgreSQL

#### Connection Details

- **Host**: localhost:5432
- **Database**: krai
- **User**: krai_user
- **Password**: krai_secure_password
- **Schemas**: krai_core, krai_content, krai_intelligence, krai_system, krai_parts, krai_config, krai_ml, krai_service, krai_users, krai_integrations (10 total)
- **Phase 6 Tables**: structured_tables, enhanced chunks with hierarchical structure (embeddings stored in `krai_intelligence.chunks.embedding` vector column)

#### PostgreSQL Performance Tuning

The PostgreSQL container is optimized for SSD storage:

```yaml
command: >
  -c shared_buffers=256MB
  -c effective_cache_size=1GB
  -c maintenance_work_mem=128MB
  -c random_page_cost=1.1
  -c effective_io_concurrency=200
```

#### PostgreSQL Backup/Restore

```bash
# Backup
docker exec krai-postgres pg_dump -U krai_user krai > backup.sql

# Restore
docker exec -i krai-postgres psql -U krai_user krai < backup.sql
```

### MinIO

#### Console Access

- **URL**: <http://localhost:9001>
- **Username**: minioadmin
- **Password**: minioadmin123

#### Bucket Policies

- **Documents**: Private (authenticated access only)
- **Images/Videos**: Public read access (for web viewing)
- **Temp**: Private (cleanup after processing)

#### CLI Usage

```bash
# List buckets
docker exec krai-minio mc ls local/

# Upload file
docker exec krai-minio mc cp /path/to/file.txt local/documents/

# Download file
docker exec krai-minio mc cp local/documents/file.txt /path/to/output/
```

#### MinIO Backup/Restore

```bash
# Backup entire MinIO data
docker run --rm -v krai_minio_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/minio-backup.tar.gz -C /data .

# Restore MinIO data
docker run --rm -v krai_minio_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/minio-backup.tar.gz -C /data
```

### Ollama

#### Model Management

```bash
# List models
docker exec krai-ollama ollama list

# Pull model
docker exec krai-ollama ollama pull llama3.2:latest

# Remove model
docker exec krai-ollama ollama remove llama3.2:latest

# Show model info
docker exec krai-ollama ollama show llama3.2:latest
```

#### API Usage

```bash
# Generate text
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:latest",
  "prompt": "Why is the sky blue?",
  "stream": false
}'

# Generate embeddings
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text:latest",
  "prompt": "Hello, world!"
}'
```

#### GPU Verification

If you have an NVIDIA GPU, Ollama will automatically use it. Verify with:

```bash
docker exec krai-ollama nvidia-smi
```

### n8n

#### Workflow Management

- **URL**: <http://localhost:5678>
- **Username**: admin
- **Password**: krai_chat_agent_2024

#### Import Workflows

```bash
# Copy workflows to container
docker cp ./n8n_workflows/ krai-n8n-chat-agent:/home/node/.n8n/workflows/

# Restart n8n to reload
docker-compose restart n8n
```

## Troubleshooting

### Common Issues

#### Port Conflicts

**Problem**: Services fail to start with "port already in use"

```bash
# Check what's using ports
netstat -tulpn | grep :5432  # PostgreSQL
netstat -tulpn | grep :9000  # MinIO
netstat -tulpn | grep :11434 # Ollama

# Solution: Stop conflicting services or change ports in docker-compose.simple.yml or docker-compose.production.yml
```

#### Out of Memory Errors

**Problem**: Containers restart or crash with OOM errors

```bash
# Check memory usage
docker stats

# Solution: Increase RAM or reduce model sizes
# Edit .env to use smaller models:
AI_TEXT_MODEL=llama3.2:1b  # Instead of full model
```

#### GPU Not Detected

**Problem**: Ollama not using GPU despite NVIDIA GPU

```bash
# Check NVIDIA Docker support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Solution: Install NVIDIA Container Toolkit
# See Prerequisites section
```

#### Permission Denied Errors

**Problem**: Cannot access database or MinIO

```bash
# Check container logs
docker-compose logs krai-postgres
docker-compose logs krai-minio

# Solution: Verify credentials in .env match the active compose file (docker-compose.simple.yml, docker-compose.with-firecrawl.yml, or docker-compose.production.yml)
```

### Diagnostic Commands

#### Service Status

```bash
# Check all containers
docker-compose ps

# Check container health
docker inspect krai-postgres | grep Health -A 10
```

#### Diagnostic Logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs krai-postgres
```

#### Network Diagnostics

```bash
# Check Docker network
docker network inspect krai-network

# Test connectivity between containers
docker exec krai-postgres ping krai-minio
```

#### Resource Usage

```bash
# Live resource usage
docker stats

# Disk usage by volumes
docker system df

# Clean up unused resources
docker system prune -f
```

### Reset Procedures

#### Full Reset

```bash
# Stop all services
docker-compose down

# Remove all volumes (DELETES ALL DATA)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Clean rebuild
docker-compose up -d --build --force-recreate
```

#### Partial Reset

```bash
# Reset specific service
docker-compose stop krai-postgres
docker-compose rm -f krai-postgres
docker-compose up -d krai-postgres

# Reset MinIO data only
docker-compose stop krai-minio
docker volume rm krai_minio_data
docker-compose up -d krai-minio
```

## Advanced Topics

### GPU Configuration

#### Multi-GPU Setup

```yaml
# In docker-compose.production.yml
services:
  krai-ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all  # Use all available GPUs
              capabilities: [gpu]
```

#### GPU Memory Limits

```yaml
services:
  krai-ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']  # Use specific GPU
              capabilities: [gpu]
```

### Performance Tuning

#### PostgreSQL Optimization

```yaml
# For high-memory systems (32GB+ RAM)
command: >
  -c shared_buffers=1GB
  -c effective_cache_size=8GB
  -c maintenance_work_mem=512MB
  -c work_mem=16MB
  -c max_parallel_workers_per_gather=4
```

#### MinIO Performance

```yaml
services:
  krai-minio:
    environment:
      - MINIO_PROMETHEUS_AUTH_TYPE=public
      - MINIO_API_REQUESTS_MAX=5000
    command: server /data --console-address ":9001" --quiet
```

#### Ollama Concurrency

```bash
# Set concurrent requests in Ollama
docker exec krai-ollama env OLLAMA_NUM_PARALLEL=4 ollama serve
```

### Production Deployment

#### Security Hardening

```yaml
# Use secrets instead of environment variables
services:
  krai-postgres:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

#### SSL/TLS Setup

```yaml
# Enable SSL for PostgreSQL
services:
  krai-postgres:
    environment:
      - POSTGRES_INITDB_ARGS=--encoding=UTF8 --locale=en_US.UTF-8
    command: >
      -c ssl=on
      -c ssl_cert_file=/var/lib/postgresql/server.crt
      -c ssl_key_file=/var/lib/postgresql/server.key
```

#### Monitoring Setup

```yaml
# Add Prometheus monitoring
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

### Scaling

#### Horizontal Scaling

```yaml
# Multiple backend workers
services:
  krai-backend:
    deploy:
      replicas: 3
    environment:
      - WORKER_ID=${HOSTNAME}
```

#### Load Balancing

```yaml
# Add nginx load balancer
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
```

## Migration from Cloud

### Supabase → PostgreSQL (Completed November 2024)

> **⚠️ HISTORICAL REFERENCE - Migration Complete (KRAI-002)**
> This section is preserved for legacy users only. All new deployments should use PostgreSQL-only configuration.

#### Export Data from Supabase (Historical Reference)

```bash
# Using pg_dump with Supabase
# connection string
pg_dump "postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/ \
  postgres" \
  --no-owner --no-privileges \
  > supabase_export.sql
```

#### Import to Local PostgreSQL

```bash
# Copy to container
docker cp supabase_export.sql krai-postgres:/tmp/

# Import data
docker exec krai-postgres psql -U krai_user -d krai -f /tmp/supabase_export.sql
```

#### Update Connection Strings

```python
# In your application code
# Old: Supabase connection
DATABASE_URL="postgresql://postgres:[PASSWORD]@db.project.supabase.co:5432/postgres"

# New: Local PostgreSQL
DATABASE_URL="postgresql://krai_user:krai_secure_password@localhost:5432/krai"
```

### Object Storage Migration to MinIO

#### Upload to MinIO

```bash
# Using MinIO client
mc mirror ./downloads/documents/ local/documents/
mc mirror ./downloads/errors/ local/error-images/
mc mirror ./downloads/parts/ local/parts-images/
```

#### Update Storage URLs in Database

```sql
-- Update image URLs in database
UPDATE krai_content.images
SET storage_url = REPLACE(
  storage_url,
  'https://old-storage-url',
  'http://localhost:9000/images'
);
```

### Environment Variable Mapping

| Old Variable | New Variable | Notes |
|--------------|--------------|-------|
| `SUPABASE_URL` | `DATABASE_URL` | Use PostgreSQL connection string |
| `SUPABASE_ANON_KEY` | Not needed | Local setup doesn't use auth keys |
| Legacy object storage variables | `OBJECT_STORAGE_*` | See `docs/MIGRATION_R2_TO_MINIO.md` |
| `OLLAMA_URL` | `AI_SERVICE_URL` | Same value, different name |

### Migration Script

```bash
#!/bin/bash
# migration_script.sh

echo "🔄 Starting migration from cloud to local..."

# 1. Export Supabase data
echo "📤 Exporting data from Supabase..."
pg_dump "$SUPABASE_CONNECTION_STRING" > supabase_backup.sql

# 2. Start local services
echo "🚀 Starting local services..."
docker-compose up -d

# 4. Wait for services to be ready
echo "⏳ Waiting for services..."
sleep 30

# 5. Import data to PostgreSQL
echo "📥 Importing data to local PostgreSQL..."
docker exec -i krai-postgres psql -U krai_user -d krai < supabase_backup.sql

# 6. Upload files to MinIO
echo "📤 Uploading files to MinIO..."
python scripts/init_minio.py
mc mirror ./old_storage_downloads/documents/ local/documents/
mc mirror ./old_storage_downloads/parts/ local/parts-images/

# 7. Update database URLs
echo "🔄 Updating storage URLs in database..."
docker exec krai-postgres psql -U krai_user -d krai -c "
UPDATE krai_content.images
SET storage_url = REPLACE(storage_url, 'https://pub-', 'http://localhost:9000/images');
"

echo "✅ Migration completed!"
echo "🔍 Verify setup: python scripts/verify_local_setup.py"
```

## Support

### Getting Help

- **Documentation**: Check this guide and inline code comments
- **Issues**: Report problems on the project GitHub repository
- **Community**: Join discussions in the project Discord/Slack

### Contributing

- **Bug Reports**: Include logs and system information
- **Feature Requests**: Describe use case and proposed solution
- **Pull Requests**: Follow existing code style and add tests

---

**Last Updated**: 2025-12-08
**Version**: 3.0 Phase 6 Enhanced
**Compatible with**: KRAI Engine v3.0+ (Phase 6 Multimodal AI Features)

### Phase 6 Features Included

- ✅ Hierarchical Document Structure Detection
- ✅ SVG Vector Graphics Processing with Vision AI
- ✅ Multimodal Search across all content types
- ✅ Advanced Context Extraction for images, videos, tables, and links
- ✅ Enhanced Vector Embeddings with unified multimodal support
- ✅ Cross-Chunk Linking for improved navigation
- ✅ Performance optimizations for multimodal processing
- ✅ Comprehensive test suite for all Phase 6 features

### Additional Resources

- **[Phase 6 Advanced Features Documentation](docs/PHASE_6_ADVANCED_FEATURES.md)**
- **[System Architecture Documentation](docs/ARCHITECTURE.md)**
- **[Environment Variables Reference](docs/ENVIRONMENT_VARIABLES_REFERENCE.md)**
- **[Migration Guide: Cloud to Local](docs/MIGRATION_GUIDE_CLOUD_TO_LOCAL.md)**
- **[Database Migration Guide](database/migrations/MIGRATION_GUIDE.md)**

### Archived Docker Compose Files

> **Note**: 7 deprecated Docker Compose files have been archived to reduce confusion. The project now maintains 3 active configurations: `docker-compose.simple.yml`, `docker-compose.with-firecrawl.yml`, and `docker-compose.production.yml`. See `archive/docker/README.md` for details about archived files and migration guidance.
