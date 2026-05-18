# PostgreSQL-Only Architecture (Migration Complete)

> **✅ Migration Complete - November 2024 (KRAI-002)**
> This guide is for **reference and legacy deployments only**.
> All new deployments should use PostgreSQL-only configuration.
> See [SUPABASE_DEPRECATION_NOTICE.md](SUPABASE_DEPRECATION_NOTICE.md) for current status.

## 📋 Introduction

This guide documents the completed architectural shift from cloud-based Supabase and external object storage to local-first PostgreSQL and MinIO. The KRAI project successfully completed this migration in November 2024 (KRAI-002) to provide better data sovereignty, reduced costs, and improved performance for local deployments.

### Migration Status

- **Code Changes:** ✅ Complete (KRAI-002)
- **Database Architecture:** ✅ Complete (asyncpg connection pool, adapter pattern removed)
- **API Endpoints:** ✅ Complete (no Supabase dependencies)
- **Scripts:** ✅ Complete (101 scripts archived, active scripts migrated)
- **Documentation:** ✅ Complete (KRAI-009 - all Supabase references updated)
- **Testing:** ✅ Complete (validation scripts updated)

> **Note:** The `database_factory.py` adapter pattern referenced in this guide is historical. Current architecture uses direct asyncpg connection pools. See `backend/services/database/` for current implementation.

### Why the Migration?

- **Data Sovereignty:** Complete control over your data with local PostgreSQL
- **Cost Efficiency:** No cloud storage fees with MinIO
- **Performance:** Reduced latency with local services
- **Simplicity:** Unified Docker Compose deployment
- **Flexibility:** Optional cloud migration path when needed

### Migration Timeline

- **Completed:** November 2024 (KRAI-002)
- **Status:** PostgreSQL-only architecture is now the standard
- **Legacy Support:** This guide is maintained for reference and for any remaining legacy deployments. All new deployments should use PostgreSQL-only configuration.

---

## 🔄 Environment Variable Mapping

### Database Variables

| Old (Supabase) | New (PostgreSQL) | Notes |
|----------------|------------------|-------|
| `SUPABASE_URL` | `DATABASE_CONNECTION_URL` | Full PostgreSQL connection string |
| `SUPABASE_ANON_KEY` | *(not needed)* | PostgreSQL uses password authentication |
| `SUPABASE_SERVICE_ROLE_KEY` | *(not needed)* | PostgreSQL uses password authentication |
| `SUPABASE_STORAGE_URL` | `OBJECT_STORAGE_ENDPOINT` | MinIO endpoint for storage |
| `SUPABASE_DB_PASSWORD` | `DATABASE_PASSWORD` | PostgreSQL password |
| `DATABASE_URL` | `DATABASE_CONNECTION_URL` | Renamed for clarity |

### Storage Variables

| Old | New (MinIO) | Notes |
|-----|-------------|-------|
| `MINIO_ENDPOINT` | `OBJECT_STORAGE_ENDPOINT` | Renamed for consistency |
| `MINIO_ACCESS_KEY` | `OBJECT_STORAGE_ACCESS_KEY` | Renamed for consistency |
| `MINIO_SECRET_KEY` | `OBJECT_STORAGE_SECRET_KEY` | Renamed for consistency |

### AI Service Variables

| Old | New | Notes |
|-----|-----|-------|
| `OLLAMA_BASE_URL` | `OLLAMA_URL` | Simplified naming |
| `AI_SERVICE_URL` | `OLLAMA_URL` | Consolidated variable |

### Example Configuration

**Docker Compose (Recommended):**
```bash
# Database (PostgreSQL)
DATABASE_TYPE=postgresql
DATABASE_HOST=krai-postgres
DATABASE_PORT=5432
DATABASE_NAME=krai
DATABASE_USER=krai_user
DATABASE_PASSWORD=<generated-password>
DATABASE_CONNECTION_URL=postgresql://krai_user:<password>@krai-postgres:5432/krai

# Object Storage (MinIO)
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://krai-minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=<generated-password>
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_USE_SSL=false
OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000

# AI Service (Ollama)
OLLAMA_URL=http://krai-ollama:11434
```

**Local Development (Host Access):**
```bash
# Database (PostgreSQL)
DATABASE_HOST=localhost
DATABASE_CONNECTION_URL=postgresql://krai_user:<password>@localhost:5432/krai

# Object Storage (MinIO)
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000

# AI Service (Ollama)
OLLAMA_URL=http://localhost:11434
```

---

## 🗄️ Database Migration

### PostgreSQL Setup

The project uses PostgreSQL with pgvector extension for vector search capabilities.

**1. Connection String Format:**
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

**2. Required Extensions:**
- `pgvector` - Vector similarity search
- `uuid-ossp` - UUID generation

**3. Schema Structure:**
- `krai_core` - Core tables (users, documents, products)
- `krai_intelligence` - AI-related tables (chunks, embeddings)
- `krai_parts` - Parts catalog tables
- `krai_content` - Content tables (images, videos, links)
- `public` - Views and public-facing tables

### Data Migration from Supabase

If you have existing data in Supabase:

**1. Export Data from Supabase:**
```bash
# Using pg_dump
pg_dump -h db.your-project.supabase.co \
  -U postgres \
  -d postgres \
  --schema=krai_* \
  --data-only \
  --inserts \
  -f supabase_data.sql
```

**2. Import to Local PostgreSQL:**
```bash
# Apply migrations first
cd database/migrations
# Run migrations in order

# Then import data
psql -h localhost -U krai_user -d krai -f supabase_data.sql
```

**3. Verify Migration:**
```bash
python scripts/verify_local_setup.py
```

### pgvector Configuration

The pgvector extension is automatically installed in the Docker PostgreSQL container. For manual installations:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

---

## 📦 Storage Migration

### MinIO Setup

MinIO provides S3-compatible object storage that runs locally in Docker.

**1. Bucket Structure:**
- `documents` - Processed PDF documents
- `images` - Extracted images from documents
- `parts` - Parts catalog images
- `error` - Error screenshots and diagnostics

**2. Access Configuration:**
```bash
# MinIO Console: http://localhost:9001
# MinIO API: http://localhost:9000
# Default Credentials: minioadmin / minioadmin (change for production!)
```

**3. S3 API Compatibility:**
MinIO implements the S3 API, so existing S3 client libraries work without modification.

### Public URL Configuration

MinIO uses a single public base URL with bucket paths:
- `OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000`

**Frontend Access:**
```javascript
const imageUrl = `${OBJECT_STORAGE_PUBLIC_URL}/documents/${imagePath}`;
```

---

## 💻 Code Changes

### Database Architecture (Historical Reference)

> **⚠️ HISTORICAL NOTE:** The adapter pattern described below was used during the migration but has since been replaced with direct asyncpg connection pools. This section is preserved for reference only.

**Legacy Adapter Pattern (Removed):**

The codebase previously used a factory pattern to abstract database operations:

**File:** `backend/services/database_factory.py` (deprecated)

```python
from backend.services.database_factory import create_database_adapter

# Automatically selects PostgreSQL or Supabase based on DATABASE_TYPE
db = create_database_adapter()

# All database operations use the adapter
documents = await db.get_documents()
```

**Current Architecture:**

The codebase now uses direct asyncpg connection pools:

```python
from backend.services.database.connection import get_db_pool

# Get asyncpg connection pool
pool = await get_db_pool()

# Execute queries directly
async with pool.acquire() as conn:
    documents = await conn.fetch('SELECT * FROM krai_core.documents')
```

### Script Migration

> **⚠️ HISTORICAL NOTE:** Scripts were initially migrated to use an adapter pattern, but now use direct asyncpg connections.

**Reference:** `scripts/README_MIGRATION.md`

**Example Migration (Historical):**
```python
# Old Supabase-specific code
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
data = supabase.table('documents').select('*').execute()

# Intermediate adapter-based code (deprecated)
from backend.services.database_factory import create_database_adapter
db = create_database_adapter()
data = await db.query('SELECT * FROM krai_core.documents')

# Current asyncpg-based code
from backend.services.database.connection import get_db_pool
pool = await get_db_pool()
async with pool.acquire() as conn:
    data = await conn.fetch('SELECT * FROM krai_core.documents')
```

### API Endpoints

> **⚠️ HISTORICAL NOTE:** API endpoints previously used an adapter pattern but now use direct asyncpg connection pools.

**Legacy Approach (Deprecated):**

**File:** `backend/api/dependencies/database.py` (historical)

```python
from backend.services.database_factory import create_database_adapter

async def get_database():
    """Dependency injection for database adapter."""
    db = create_database_adapter()
    try:
        yield db
    finally:
        await db.close()
```

**Current Approach:**

API endpoints now use asyncpg connection pools directly via dependency injection. See `backend/api/dependencies/` for current implementation.

---

## ⚙️ Configuration Updates

### Step-by-Step .env Update

**1. Backup Current Configuration:**
```bash
cp .env .env.backup
```

**2. Update Database Variables:**
```bash
# Comment out Supabase variables
#SUPABASE_URL=https://your-project.supabase.co
#SUPABASE_ANON_KEY=your-anon-key
#SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Set PostgreSQL variables
DATABASE_TYPE=postgresql
DATABASE_HOST=krai-postgres  # or localhost for host access
DATABASE_PORT=5432
DATABASE_NAME=krai
DATABASE_USER=krai_user
DATABASE_PASSWORD=<secure-password>
DATABASE_CONNECTION_URL=postgresql://krai_user:<password>@krai-postgres:5432/krai
```

**3. Update Storage Variables:**
```bash
# Set MinIO variables
OBJECT_STORAGE_TYPE=s3
OBJECT_STORAGE_ENDPOINT=http://krai-minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=<secure-password>
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_USE_SSL=false
OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000
```

**4. Update AI Service Variables:**
```bash
# Use OLLAMA_URL (not OLLAMA_BASE_URL)
OLLAMA_URL=http://krai-ollama:11434
```

**5. Validate Configuration:**
```bash
python scripts/validate_env.py --verbose
```

### Using Setup Scripts

The easiest way to generate a correct `.env` file:

```bash
# Linux/macOS
./setup.sh

# Windows (PowerShell)
.\setup.ps1

# Windows (Legacy)
setup.bat
```

These scripts automatically generate:
- Secure passwords for all services
- RSA keypair for JWT authentication
- Correct variable names and values
- Proper Docker service names

---

## 🧪 Testing the Migration

### Smoke Tests

**1. Verify Services are Running:**
```bash
docker-compose ps

# Expected output:
# krai-postgres    running
# krai-minio       running
# krai-ollama      running
# krai-engine      running
# krai-frontend    running
```

**2. Check Health Endpoints:**
```bash
# Backend health
curl http://localhost:8000/health

# Expected: {"status": "healthy", "database": "connected", "storage": "connected"}

```

**3. Verify Database Connectivity:**
```bash
python scripts/verify_local_setup.py

# Expected: All checks pass
```

**4. Verify Storage Connectivity:**
```bash
# MinIO Console
open http://localhost:9001

# Login with OBJECT_STORAGE_ACCESS_KEY / OBJECT_STORAGE_SECRET_KEY
# Verify buckets exist: documents, images, parts, error
```

**5. Test Document Upload:**
```bash
# Upload a test document via API
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@test.pdf"

# Verify document appears in MinIO
mc ls local/documents
```

### Integration Tests

Run the full test suite:

```bash
# API tests
pytest tests/api/

# Database tests
pytest tests/database/

# Storage tests
pytest tests/storage/
```

---

## 🔧 Troubleshooting

### Common Issues

**1. Connection Refused to PostgreSQL**

**Symptom:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps krai-postgres

# Check logs
docker-compose logs krai-postgres

# Verify DATABASE_HOST matches service name
# Docker: DATABASE_HOST=krai-postgres
# Host: DATABASE_HOST=localhost
```

**2. MinIO Access Denied**

**Symptom:** `S3Error: Access Denied`

**Solution:**
```bash
# Verify credentials in .env
echo $OBJECT_STORAGE_ACCESS_KEY
echo $OBJECT_STORAGE_SECRET_KEY

# Check MinIO logs
docker-compose logs krai-minio

# Verify buckets exist
mc ls local/
```

**3. Legacy Scripts Fail**

**Symptom:** `KeyError: 'SUPABASE_URL'`

**Solution:**
```bash
# Update script to use adapter pattern
# See scripts/README_MIGRATION.md for examples

# Or temporarily set legacy variables
export SUPABASE_URL="postgresql://..."  # Point to PostgreSQL
```

**4. Connection String Format Errors**

**Symptom:** `Invalid connection string`

**Solution:**
```bash
# Correct format:
DATABASE_CONNECTION_URL=postgresql://user:password@host:port/database

# Common mistakes:
# - Missing protocol: user:password@host:port/database (wrong)
# - Wrong protocol: postgres:// instead of postgresql://
# - Special characters in password not URL-encoded
```

**5. Authentication Differences**

**Issue:** Supabase used anon keys and service role keys, PostgreSQL uses password auth

**Solution:**
- Remove all `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` references
- Use `DATABASE_USER` and `DATABASE_PASSWORD` for authentication
- Update API clients to use password-based auth

---

## 🔙 Rollback Procedure

If you need to temporarily revert to Supabase:

**1. Restore Backup:**
```bash
cp .env.backup .env
```

**2. Uncomment Supabase Variables:**
```bash
# In .env file
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_URL=https://your-project.supabase.co/storage/v1
```

**3. Set DATABASE_TYPE:**
```bash
DATABASE_TYPE=supabase
```

**4. Restart Services:**
```bash
docker-compose down
docker-compose up -d
```

**⚠️ Warning:** Rollback is not recommended for production. The Supabase adapter is deprecated and may be removed in future versions.

---

## ❓ FAQ

### Why was the migration done?

The migration provides better data sovereignty, reduced costs, improved performance, and simplified deployment. Local-first architecture gives you complete control over your data.

### Can I still use Supabase?

Yes, but it's deprecated. Uncomment the Supabase variables in `.env` and set `DATABASE_TYPE=supabase`. However, this is not recommended for production deployments.

### What about existing Supabase deployments?

Existing deployments can continue using Supabase, but we recommend migrating to PostgreSQL + MinIO for better long-term support and performance.

### How do I migrate my production data?

Follow the "Data Migration from Supabase" section above. Export your data using `pg_dump`, apply migrations to your new PostgreSQL instance, then import the data.

### What are the performance differences?

Local PostgreSQL + MinIO typically provides:
- **Lower latency:** No network round-trips to cloud services
- **Higher throughput:** Local disk I/O is faster than network storage
- **Better consistency:** No dependency on external service availability

### Can I use cloud PostgreSQL instead of local?

Yes! You can use any PostgreSQL-compatible database (AWS RDS, Google Cloud SQL, Azure Database, etc.). Just update `DATABASE_CONNECTION_URL` to point to your cloud instance.

### What about MinIO in production?

MinIO is production-ready and used by many enterprises. For cloud deployments, you can also use AWS S3, Google Cloud Storage, or Azure Blob Storage (all S3-compatible).

### How do I get help with migration?

- Check this guide first
- Review `docs/ENVIRONMENT_VARIABLES_REFERENCE.md`
- Check `docs/setup/DEPRECATED_VARIABLES.md`
- Run `python scripts/validate_env.py --verbose` for diagnostics
- Check Docker logs: `docker-compose logs`

---

## 📚 Related Documentation

- [Environment Variables Reference](ENVIRONMENT_VARIABLES_REFERENCE.md)
- [Deprecated Variables List](setup/DEPRECATED_VARIABLES.md)
- [Database Schema Documentation](../DATABASE_SCHEMA.md)
- [Adapter Migration Guide](database/ADAPTER_MIGRATION.md)
- [Script Migration README](../scripts/README_MIGRATION.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [Docker Setup Guide](../DOCKER_SETUP.md)

---

**Last Updated:** 2024-11-29
**Migration Status:** Complete (KRAI-002)
**Support:** PostgreSQL + MinIO (Production Only). Supabase support removed in KRAI-002.
