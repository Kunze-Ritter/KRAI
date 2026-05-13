# Phase 6 Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying KRAI Phase 6 with advanced multimodal AI features in production environments. Phase 6 includes hierarchical document structure detection, SVG vector graphics processing, multimodal search, and advanced context extraction.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Options](#deployment-options)
- [Production Setup](#production-setup)
- [Configuration](#configuration)
- [Performance Optimization](#performance-optimization)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Upgrade Path](#upgrade-path)

## Prerequisites

### Hardware Requirements

#### Minimum Requirements
- **CPU**: 8 cores (Intel i7/AMD Ryzen 7 or equivalent)
- **RAM**: 32GB DDR4
- **Storage**: 500GB SSD (NVMe recommended)
- **GPU**: NVIDIA GPU with 12GB+ VRAM (RTX 3060/4060 or better)
- **Network**: 1Gbps Ethernet

#### Recommended Requirements
- **CPU**: 16 cores (Intel i9/AMD Ryzen 9 or equivalent)
- **RAM**: 64GB DDR4/DDR5
- **Storage**: 1TB NVMe SSD + 2TB HDD for data
- **GPU**: NVIDIA GPU with 24GB+ VRAM (RTX 4090/A6000)
- **Network**: 10Gbps Ethernet

#### Cloud Requirements
- **AWS**: g5.xlarge or better (GPU instances)
- **Azure**: Standard_NC6s_v3 or better
- **GCP**: n1-standard-8 with NVIDIA Tesla T4 or better

### Software Requirements

- **Operating System**: Ubuntu 22.04 LTS (recommended) / RHEL 9 / CentOS 9
- **Docker**: 24.0+ with Docker Compose v2
- **NVIDIA Drivers**: 535.104.05+ (for GPU support)
- **NVIDIA Container Toolkit**: Latest version
- **Python**: 3.11+ (if not using Docker)
- **PostgreSQL**: 15+ (if not using Docker)

## Architecture Overview

### Phase 6 Components

```text
┌─────────────────────────────────────────────────────────────┐
│                    KRAI Phase 6 Architecture                │
├─────────────────────────────────────────────────────────────┤
│  Dashboard Layer                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Laravel   │  │   Filament  │  │   Admin UI  │         │
│  │  Dashboard  │  │  + Metrics  │  │  + Config   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  API Gateway Layer                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   FastAPI   │  │   Auth API  │  │  Monitoring │         │
│  │ + Multimodal│  │   + OAuth   │  │   + Metrics │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Service Layer                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Multimodal  │  │   Context   │  │   SVG Proc  │         │
│  │  Search Svc │  │ Extraction  │  │   Service   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Hierarchical│  │   AI Service│  │ Database Svc│         │
│  │  Chunker    │  │  + Vision AI│  │ + Multimodal│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Data Layer                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ PostgreSQL  │  │    MinIO    │  │    Redis    │         │
│  │ + pgvector  │  │ + Deduplication│ │   + Cache   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Ollama   │  │   n8n       │  │Prometheus   │         │
│  │ + Vision AI │  │ + Workflows │  │ + Grafana   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Phase 6 New Services

1. **Multimodal Search Service**: Unified search across text, images, videos, tables, and links
2. **Context Extraction Service**: AI-powered context generation for all media types
3. **SVG Processing Service**: Vector graphics extraction and Vision AI analysis
4. **Hierarchical Chunker**: Document structure detection and cross-chunk linking
5. **Enhanced Database Service**: Support for multimodal embeddings and hierarchical data

## Deployment Options

### Option 1: Docker Compose (Recommended for Small/Medium Deployments)

#### Advantages
- Easy setup and maintenance
- Built-in service orchestration
- Consistent environments
- Easy scaling with Docker Swarm

#### Setup Instructions

1. **Clone Repository**
```bash
git clone https://github.com/Kunze-Ritter/Manual2Vector.git
cd Manual2Vector
```

2. **Configure Environment**
```bash
# Copy environment templates
cp .env.example .env
cp .env.production.example .env.production

# Edit production configuration
nano .env.production
```

3. **Start Services**
```bash
# Use production compose file
docker-compose -f docker-compose.production.yml up -d
```

> **Note:** `docker-compose.prod.yml` (with enterprise features) has been archived. The simpler `docker-compose.production.yml` is now the standard production configuration.

4. **Initialize Database**
```bash
# Run Phase 6 migrations
docker-compose exec krai-backend python scripts/apply_phase6_migrations.py

# Create admin user
docker-compose exec krai-backend python scripts/create_admin_user.py
```

5. **Pull AI Models**
```bash
# Required models for Phase 6
docker-compose exec krai-ollama ollama pull nomic-embed-text:latest
docker-compose exec krai-ollama ollama pull llama3.1:8b:latest
docker-compose exec krai-ollama ollama pull llava-phi3:latest
```

### Option 2: Kubernetes (Recommended for Large/Enterprise Deployments)

#### Advantages
- Auto-scaling and self-healing
- Advanced load balancing
- Rolling updates and rollbacks
- Multi-cluster support

#### Prerequisites
- Kubernetes cluster 1.25+
- kubectl configured
- Helm 3.0+
- Ingress controller (nginx/traefik)

#### Setup Instructions

1. **Add KRAI Helm Repository**
```bash
helm repo add krai https://krai.github.io/helm-charts
helm repo update
```

2. **Create Namespace**
```bash
kubectl create namespace krai-phase6
```

3. **Install KRAI Phase 6**
```bash
helm install krai-phase6 krai/krai \
  --namespace krai-phase6 \
  --values values.phase6.yaml \
  --set phase6.enabled=true \
  --set gpu.enabled=true
```

4. **Verify Deployment**
```bash
kubectl get pods -n krai-phase6
kubectl get services -n krai-phase6
```

### Option 3: Cloud Native (AWS/Azure/GCP)

#### AWS Deployment

1. **Using ECS with Fargate**
```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name krai-phase6

# Deploy task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster krai-phase6 \
  --service-name krai-backend \
  --task-definition krai-phase6:1 \
  --desired-count 3
```

2. **Using EKS (Kubernetes)**
```bash
# Create EKS cluster
aws eks create-cluster \
  --name krai-phase6 \
  --version 1.28 \
  --role-arn arn:aws:iam::ACCOUNT:role/EKSClusterRole \
  --resources-vpc-config subnetIds=SUBNET_IDS,securityGroupIds=SG_IDS

# Deploy using Helm (see Option 2)
```

## Production Setup

### Security Configuration

1. **SSL/TLS Setup**
```bash
# Generate SSL certificates
certbot certonly --standalone -d your-domain.com

# Configure nginx for SSL
cp nginx/ssl.conf /etc/nginx/sites-available/krai
ln -s /etc/nginx/sites-available/krai /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

2. **Firewall Configuration**
```bash
# Open required ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 9001/tcp  # MinIO Console (internal)
ufw allow 5050/tcp  # pgAdmin (internal)
ufw enable
```

3. **Database Security**
```sql
-- Create dedicated database user
CREATE USER krai_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE krai TO krai_app;
GRANT USAGE ON SCHEMA krai_core TO krai_app;
GRANT USAGE ON SCHEMA krai_content TO krai_app;
GRANT USAGE ON SCHEMA krai_intelligence TO krai_app;

-- Enable Row Level Security
ALTER DATABASE krai SET row_security = on;
```

### Performance Tuning

1. **PostgreSQL Optimization**
```sql
-- postgresql.conf optimizations
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
work_mem = 256MB
max_parallel_workers_per_gather = 4
max_connections = 200
```

2. **Redis Configuration**
```conf
# redis.conf optimizations
maxmemory 8gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

3. **Ollama GPU Optimization**
```bash
# Set GPU memory limits
export OLLAMA_GPU_LAYERS=35
export OLLAMA_MAX_QUEUE=512
export OLLAMA_NUM_PARALLEL=4
```

### Monitoring Setup

1. **Prometheus Configuration**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'krai-backend'
    static_configs:
      - targets: ['krai-backend:8000']
    metrics_path: '/metrics'

  - job_name: 'krai-postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'krai-ollama'
    static_configs:
      - targets: ['ollama-exporter:9090']
```

2. **Grafana Dashboards**
```bash
# Import KRAI Phase 6 dashboards
curl -X POST \
  http://admin:admin@<grafana-host>/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @monitoring/grafana/krai-phase6-dashboard.json
```

## Configuration

### Environment Variables

#### Core Configuration
```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
BASE_URL=https://your-domain.com

# Database
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=krai
DATABASE_USER=krai_app
DATABASE_PASSWORD=secure_password
DATABASE_POOL_SIZE=50
DATABASE_MAX_CONNECTIONS=200

# AI Service
AI_SERVICE_URL=http://ollama:11434
AI_EMBEDDING_MODEL=nomic-embed-text:latest
AI_TEXT_MODEL=llama3.1:8b:latest
AI_VISION_MODEL=llava-phi3:latest
AI_SERVICE_TIMEOUT=60
AI_SERVICE_RETRY_ATTEMPTS=3
```

#### Phase 6 Specific Configuration
```bash
# Hierarchical Chunking
ENABLE_HIERARCHICAL_CHUNKING=true
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
DETECT_ERROR_CODE_SECTIONS=true
LINK_CHUNKS=true

# SVG Processing
ENABLE_SVG_EXTRACTION=true
SVG_CONVERSION_DPI=300
SVG_MAX_DIMENSION=2048
SVG_QUALITY=95
SVG_BACKGROUND_COLOR=white

# Multimodal Search
ENABLE_MULTIMODAL_SEARCH=true
MULTIMODAL_SEARCH_THRESHOLD=0.5
MULTIMODAL_SEARCH_LIMIT=20
ENABLE_TWO_STAGE_RETRIEVAL=true
SEARCH_RESULT_MAX_AGE=3600

# Context Extraction
ENABLE_CONTEXT_EXTRACTION=true
CONTEXT_EXTRACTION_BATCH_SIZE=10
MAX_CONTEXT_LENGTH=1000
VISION_AI_BATCH_SIZE=5

# Performance
EMBEDDING_BATCH_SIZE=20
VISION_AI_BATCH_SIZE=5
MAX_CONCURRENT_AI_REQUESTS=50
MAX_CONCURRENT_UPLOADS=10
PROCESSING_TIMEOUT=600
```

### Docker Compose Configuration

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  krai-backend:
    image: krai/backend:phase6-latest
    environment:
      - ENABLE_HIERARCHICAL_CHUNKING=true
      - ENABLE_SVG_EXTRACTION=true
      - ENABLE_MULTIMODAL_SEARCH=true
      - ENABLE_CONTEXT_EXTRACTION=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped

  krai-postgres:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=krai
      - POSTGRES_USER=krai_app
      - POSTGRES_PASSWORD=secure_password
    command: >
      -c shared_buffers=4GB
      -c effective_cache_size=12GB
      -c maintenance_work_mem=1GB
      -c work_mem=256MB
      -c max_parallel_workers_per_gather=4
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/migrations:/docker-entrypoint-initdb.d
    restart: unless-stopped

  krai-ollama:
    image: ollama/ollama:latest
    environment:
      - OLLAMA_GPU_LAYERS=35
      - OLLAMA_MAX_QUEUE=512
      - OLLAMA_NUM_PARALLEL=4
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

  krai-minio:
    image: cgr.dev/chainguard/minio:latest
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=secure_minio_password
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
  minio_data:
```

## Performance Optimization

### GPU Optimization

1. **NVIDIA GPU Settings**
```bash
# Set GPU performance mode
nvidia-smi -pm 1

# Set maximum power limit
nvidia-smi -pl 250

# Set memory clock
nvidia-smi -ac 877,1215
```

2. **Ollama GPU Configuration**
```bash
# Optimize for RTX 4090
export OLLAMA_GPU_LAYERS=45
export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_NUM_PARALLEL=6

# Optimize for RTX 3090
export OLLAMA_GPU_LAYERS=35
export OLLAMA_MAX_LOADED_MODELS=2
export OLLAMA_NUM_PARALLEL=4
```

### Database Optimization

1. **Vector Search Optimization**
```sql
-- Create optimized vector indexes
CREATE INDEX CONCURRENTLY chunks_embedding_vector_idx
ON krai_intelligence.chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create composite indexes for multimodal search
CREATE INDEX CONCURRENTLY chunks_source_idx
ON krai_intelligence.chunks (source_type, source_id);

-- Analyze tables for better query planning
ANALYZE krai_intelligence.chunks;
ANALYZE krai_intelligence.structured_tables;
ANALYZE krai_content.images;
```

2. **Query Optimization**
```sql
-- Optimized multimodal search function
CREATE OR REPLACE FUNCTION match_multimodal_optimized(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 20
) RETURNS TABLE (
    id bigint,
    content text,
    source_type text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.content,
        e.source_type,
        1 - (e.embedding <=> query_embedding) as similarity
    FROM krai_intelligence.chunks e
    WHERE e.embedding IS NOT NULL
      AND 1 - (e.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

### Caching Strategy

1. **Redis Configuration**
```conf
# Optimized for Phase 6 workloads
maxmemory 16gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
tcp-keepalive 300
timeout 0
```

2. **Application Caching**
```python
# Cache embeddings for 24 hours
CACHE_EMBEDDINGS_TTL = 86400

# Cache search results for 1 hour
CACHE_SEARCH_RESULTS_TTL = 3600

# Cache context extraction for 6 hours
CACHE_CONTEXT_EXTRACTION_TTL = 21600
```

## Monitoring & Maintenance

### Health Checks

1. **Service Health Endpoints**
```bash
# Backend health
curl https://your-domain.com/health

# Database health
curl https://your-domain.com/health/database

# AI service health
curl https://your-domain.com/health/ai

# Storage health
curl https://your-domain.com/health/storage
```

2. **Custom Health Checks**
```python
# Phase 6 specific health checks
async def check_phase6_features():
    checks = {
        "hierarchical_chunking": await check_hierarchical_chunking(),
        "svg_processing": await check_svg_processing(),
        "multimodal_search": await check_multimodal_search(),
        "context_extraction": await check_context_extraction()
    }
    return checks
```

### Metrics Collection

1. **Key Performance Indicators**
```yaml
# Phase 6 KPIs
metrics:
  - name: phase6_processing_time
    type: histogram
    labels: [document_type, processing_stage]

  - name: phase6_search_latency
    type: histogram
    labels: [query_type, modality]

  - name: phase6_ai_model_usage
    type: counter
    labels: [model_name, operation]

  - name: phase6_storage_usage
    type: gauge
    labels: [storage_type, bucket]
```

2. **Alerting Rules**
```yaml
# Prometheus alerting rules
groups:
  - name: phase6_alerts
    rules:
      - alert: HighProcessingLatency
        expr: phase6_processing_time_p95 > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High processing latency detected"

      - alert: AIServiceDown
        expr: up{job="krai-ollama"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AI service is down"
```

### Backup Strategy

1. **Database Backup**
```bash
# Automated daily backup
0 2 * * * pg_dump -h localhost -U krai_app krai | gzip > /backups/krai_$(date +\%Y\%m\%d).sql.gz

# Weekly full backup
0 3 * * 0 pg_dumpall -h localhost -U krai_app | gzip > /backups/full_$(date +\%Y\%m\%d).sql.gz
```

2. **Storage Backup**
```bash
# MinIO backup to S3
aws s3 sync s3://krai-storage s3://krai-backup/$(date +\%Y\%m\%d)/

# Local backup
rsync -av /data/minio/ /backup/minio/$(date +\%Y\%m\%d)/
```

## Security Considerations

### Authentication & Authorization

1. **JWT Configuration**
```bash
# Strong JWT settings
JWT_SECRET_KEY=your_super_secret_jwt_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

2. **OAuth2 Integration**
```bash
# Enable OAuth2 providers
ENABLE_GOOGLE_OAUTH=true
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

ENABLE_MICROSOFT_OAUTH=true
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
```

### Data Protection

1. **Encryption at Rest**
```sql
-- Enable transparent data encryption
ALTER DATABASE krai SET encryption = on;

-- Encrypt sensitive columns
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

2. **Network Security**
```bash
# Configure firewall rules
ufw deny 5432  # PostgreSQL (internal only)
ufw deny 9000  # MinIO API (internal only)
ufw deny 11434 # Ollama (internal only)
ufw allow from 10.0.0.0/8 to any port 5432  # Internal network
```

### Access Control

1. **Role-Based Access Control**
```sql
-- Create application roles
CREATE ROLE krai_readonly;
CREATE ROLE krai_operator;
CREATE ROLE krai_admin;

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA krai_core TO krai_readonly;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA krai_content TO krai_operator;
GRANT ALL PRIVILEGES ON ALL TABLES IN ALL SCHEMAS TO krai_admin;
```

## Troubleshooting

### Common Issues

1. **GPU Memory Issues**
```bash
# Check GPU memory usage
nvidia-smi

# Clear GPU cache
docker exec krai-ollama ollama stop
docker exec krai-ollama ollama start

# Reduce model layers
export OLLAMA_GPU_LAYERS=20
```

2. **Database Performance**
```sql
-- Check slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Rebuild indexes
REINDEX INDEX CONCURRENTLY embeddings_vector_idx;
```

3. **Storage Issues**
```bash
# Check MinIO disk usage
docker exec krai-minio df -h

# Clean up temporary files
docker exec krai-minio mc rm --recursive --force local/temp/
```

### Debug Mode

1. **Enable Debug Logging**
```bash
# Set debug environment
export LOG_LEVEL=DEBUG
export DEBUG_SQL=true
export DEBUG_AI_REQUESTS=true
```

2. **Performance Profiling**
```python
# Enable profiling
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Upgrade Path

### From Phase 5 to Phase 6

1. **Backup Current System**
```bash
# Create full backup
./scripts/backup_system.sh

# Export configuration
docker-compose config > backup-compose.yml
```

2. **Update Dependencies**
```bash
# Pull latest images
docker-compose pull

# Update database schema
./scripts/apply_phase6_migrations.py
```

3. **Configure Phase 6 Features**
```bash
# Add Phase 6 environment variables
echo "ENABLE_HIERARCHICAL_CHUNKING=true" >> .env
echo "ENABLE_SVG_EXTRACTION=true" >> .env
echo "ENABLE_MULTIMODAL_SEARCH=true" >> .env
echo "ENABLE_CONTEXT_EXTRACTION=true" >> .env
```

4. **Deploy New Features**
```bash
# Restart services with new configuration
docker-compose down
docker-compose -f docker-compose.production.yml up -d

# Verify Phase 6 features
./scripts/test_phase6_integration.py
```

### Rollback Procedure

1. **Database Rollback**
```bash
# Restore database backup
pg_restore -h localhost -U krai_app -d krai backup.sql

# Rollback migrations
./scripts/rollback_phase6_migrations.py
```

2. **Service Rollback**
```bash
# Switch to previous images
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.phase5.yml up -d
```

## Conclusion

This deployment guide provides comprehensive instructions for deploying KRAI Phase 6 in production environments. The advanced multimodal AI features require careful planning and optimization to ensure optimal performance.

For additional support:
- Review the [Phase 6 Advanced Features documentation](PHASE_6_ADVANCED_FEATURES.md)
- Check the [Environment Variables reference](ENVIRONMENT_VARIABLES_REFERENCE.md)
- Consult the [System Architecture documentation](ARCHITECTURE.md)
- Contact the KRAI development team for assistance

---

**Last Updated**: 2025-12-08
**Version**: 1.0
**Compatible with**: KRAI Phase 6 (v3.0+)
