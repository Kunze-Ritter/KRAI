# KRAI Production Deployment Guide

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- NVIDIA GPU (optional, for Ollama acceleration)
- 8GB+ RAM (16GB+ recommended)
- 20GB+ free disk space

### One-Command Deployment

#### CPU-Only Deployment
```bash
git clone <repository-url>
cd KRAI-minimal
docker-compose -f docker-compose.production.yml up -d --build
```

#### GPU-Accelerated Deployment (Recommended)
```bash
git clone <repository-url>
cd KRAI-minimal
docker-compose -f docker-compose.cuda.yml up -d --build
```

**GPU Benefits:**
- 3-5x faster text processing
- 10x faster embeddings generation
- Real-time vision model processing
- Support for larger models with 8GB+ VRAM

## 📋 Services Overview

| Service | Port | Description | Access |
|---------|------|-------------|--------|
| **Laravel Dashboard** | 80 | Laravel + Filament Admin Dashboard | http://localhost:80 |
| **Backend API** | 8000 | FastAPI Python Backend | http://localhost:8000 |
| **API Documentation** | 8000/docs | Interactive API Docs | http://localhost:8000/docs |
| **PostgreSQL Database** | 5432 | pgvector-enabled Database | localhost:5432 |
| **MinIO Console** | 9001 | S3-compatible Object Storage | http://localhost:9001 |
| **MinIO API** | 9000 | Object Storage API | http://localhost:9000 |
| **Ollama AI Service** | 11434 | Large Language Models | localhost:11434 |

## 🔧 Configuration

### Backend Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
# Database (PostgreSQL)
DATABASE_TYPE=postgresql
DATABASE_CONNECTION_URL=postgresql://krai_user:krai_secure_password@krai-postgres:5432/krai

# Storage (MinIO)
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://krai-minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin

# AI Services (Ollama)
OLLAMA_URL=http://krai-ollama:11434

# Application
ENV=production
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

> **⚠️ IMPORTANT - PostgreSQL-Only Architecture:** Legacy Supabase configurations are deprecated and no longer supported. This deployment uses PostgreSQL + MinIO exclusively. For legacy users migrating from Supabase, see `docs/SUPABASE_TO_POSTGRESQL_MIGRATION.md`.

> **Dashboard Interface:** KRAI uses **Laravel/Filament** as the sole dashboard interface, accessible at http://localhost:80. The dashboard provides visual pipeline management, document processing control, and real-time monitoring capabilities. See [Laravel Dashboard Deployment](#laravel-dashboard-deployment) and [docs/runbooks/LARAVEL_DASHBOARD_OPERATIONS.md](docs/runbooks/LARAVEL_DASHBOARD_OPERATIONS.md) for operations and troubleshooting.

### Laravel Dashboard Deployment

- **URL:** http://localhost:80 (or your configured host/port).
- **Environment variables** (in Laravel `.env`, often via root `.env` or `laravel-admin/.env`):
  - `KRAI_ENGINE_URL` – Backend API base URL (e.g. `http://krai-engine:8000`).
  - `KRAI_SERVICE_JWT` or `KRAI_ENGINE_SERVICE_JWT` – JWT for authenticated API calls; optional if auto-login is used.
  - `KRAI_ENGINE_ADMIN_USERNAME` / `KRAI_ENGINE_ADMIN_PASSWORD` – Optional; used for JWT auto-login when no service JWT is set.
  - `MONITORING_BASE_URL` – Optional override for monitoring API base URL (defaults to engine URL).
- **Health check:** Ensure Laravel container is up and the dashboard is reachable: `curl -s -o NUL -w "%{http_code}" http://localhost:80` (expect 200 or 302). Login and pipeline/processor/error pages should load without backend connection errors when the engine is running.
- **Verification and operations:** See [VERIFICATION_REPORT_LARAVEL_DASHBOARD.md](VERIFICATION_REPORT_LARAVEL_DASHBOARD.md) and [docs/runbooks/LARAVEL_DASHBOARD_OPERATIONS.md](docs/runbooks/LARAVEL_DASHBOARD_OPERATIONS.md).

### Default Credentials
- **MinIO Console:** See `OBJECT_STORAGE_ACCESS_KEY` / `OBJECT_STORAGE_SECRET_KEY` in `.env`
- **PostgreSQL:** See `DATABASE_USER` / `DATABASE_PASSWORD` in `.env`
- **Database Name:** `krai` (configured via `DATABASE_NAME`)

> **Security:** Change all default credentials before production deployment. Use `./setup.sh` or `./setup.ps1` to generate secure passwords.

## 🏗️ Architecture

### Docker Compose Structure
```
docker-compose.production.yml
├── krai-laravel (Laravel + Filament + Nginx)
│   └── Port 80 → Container port 80
├── krai-engine (FastAPI + Uvicorn)
├── krai-postgres (PostgreSQL + pgvector)
├── krai-minio (Object Storage)
├── krai-ollama (AI Service)
├── krai-redis (Cache)
├── krai-playwright (Browser Automation)
├── krai-firecrawl-api (Web Scraping API)
└── krai-firecrawl-worker (Web Scraping Worker)
```

> **Note:** `docker-compose.production-final.yml` has been archived and replaced by `docker-compose.production.yml`. The new production file includes Firecrawl services and uses uvicorn instead of gunicorn.

### Network Configuration
- All services communicate via internal Docker network `krai-network`
- Only necessary ports exposed to host
- Health checks implemented for all services
- Automatic restart on failure

## 📊 Monitoring & Health

### Health Check Endpoints
- **Laravel Dashboard:** http://localhost:80/health
- **Backend:** http://localhost:8000/health
- **Database:** `pg_isready -U krai_user -d krai`
- **MinIO:** http://localhost:9000/minio/health/live
- **Ollama:** http://localhost:11434/api/tags

### Container Status
```bash
# Check all services
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f [service-name]

# Restart specific service
docker-compose -f docker-compose.production.yml restart [service-name]
```

## 🔄 Data Persistence

### Volume Mapping
- **PostgreSQL Data:** `krai_postgres_data:/var/lib/postgresql/data`
- **MinIO Data:** `minio_data:/data`
- **Ollama Models:** `ollama_data:/root/.ollama`
- **Application Data:** `./data:/app/data`
- **Logs:** `./logs:/app/logs`

### Backups
```bash
# Database backup
docker exec krai-postgres-prod pg_dump -U krai_user krai > backup.sql

# MinIO backup
docker exec krai-minio-prod mc mirror /data ./minio-backup

# Ollama models backup
docker exec krai-ollama-prod cp -r /root/.ollama ./ollama-backup
```

## 🌐 External Access

### Domain Configuration
Update `nginx/nginx-simple.conf` for production domains:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    # ... rest of configuration
}
```

### SSL/TLS Setup
For HTTPS, modify nginx configuration and add certificates:
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    # ... rest of configuration
}
```

## 🔒 Security Considerations

### Production Checklist
- [ ] Change default MinIO credentials
- [ ] Update PostgreSQL passwords
- [ ] Configure firewall rules
- [ ] Enable SSL/TLS
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Review environment variables

### Access Control
```bash
# Restrict external access to database
# Only expose dashboard (80) and API (8000) ports externally
# Use Docker networks for internal communication
```

## 🚀 Scaling & Performance

### Resource Allocation
```yaml
# In docker-compose.production.yml
services:
  krai-engine:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
        reservations:
          memory: 1G
          cpus: '1'
```

### Horizontal Scaling
```bash
# Scale backend services
docker-compose -f docker-compose.production.yml up -d --scale krai-engine=3
```

## 🐛 Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check what's using ports
netstat -tulpn | grep :80
netstat -tulpn | grep :8000

# Change ports in docker-compose.production.yml
```

#### Build Failures
```bash
# Clean rebuild
docker-compose -f docker-compose.production.yml down --volumes
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

#### Service Not Starting
```bash
# Check logs
docker logs krai-[service-name]-prod

# Check health status
docker-compose -f docker-compose.production.yml ps
```

#### Database Connection Issues
```bash
# Test database connection
docker exec krai-postgres-prod psql -U krai_user -d krai -c "SELECT version();"

# Check database logs
docker logs krai-postgres-prod
```

## 📱 Development vs Production

### Development Setup
```bash
# Use development compose file
docker-compose -f docker-compose.yml up -d

# Or run backend locally
cd backend && python -m uvicorn main:app --reload

# Laravel dashboard runs in Docker (see laravel-admin/README.md for local setup)
```

### Production Deployment
```bash
# Use production compose file (this guide)
docker-compose -f docker-compose.production.yml up -d --build
```

## 🔄 Updates & Maintenance

### Application Updates
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml up -d --build
```

### System Updates
```bash
# Update Docker images
docker-compose -f docker-compose.production.yml pull

# Restart with new images
docker-compose -f docker-compose.production.yml up -d
```

## 📞 Support

### Log Analysis
```bash
# Aggregate logs for debugging
docker-compose -f docker-compose.production.yml logs --tail=100

# Monitor specific service
docker-compose -f docker-compose.production.yml logs -f krai-engine
```

### Performance Monitoring
```bash
# Resource usage
docker stats

# Container health
docker-compose -f docker-compose.production.yml exec krai-engine curl -f http://localhost:8000/health
```

---

## 🎯 Success Criteria

✅ **Portable:** Single docker-compose file for deployment
✅ **Complete:** All services included (Laravel Dashboard, Backend, Database, Storage, AI)
✅ **Production-Ready:** Health checks, restarts, logging, monitoring
✅ **Scalable:** Resource limits and scaling capabilities
✅ **Secure:** Internal networking, configurable credentials
✅ **Documented:** Comprehensive setup and troubleshooting guide

**Deployment Status:** ✅ PRODUCTION READY
