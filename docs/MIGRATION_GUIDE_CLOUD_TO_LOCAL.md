# KRAI Database Migration Guide - Local-First Architecture

This guide provides comprehensive instructions for applying database migrations to set up the KRAI system with all Phase 1-6 advanced features. The migration mechanism uses sequential SQL files that create schemas, tables, indexes, and functions in the correct order.

## 🎯 Migration Overview

The KRAI database uses a **sequential migration system** with numbered SQL files that must be applied in order. Each migration builds upon the previous ones and includes all Phase 1-6 features.

### Migration Structure

The database is organized into **5 core schemas** with Phase 6 enhancements:

```sql
krai_core          - Documents, manufacturers, products, product_series
krai_content       - Chunks, images, videos, links, structured tables
krai_intelligence  - Chunk embeddings (`chunks.embedding`), error_codes, search_analytics, context data
krai_system        - Processing_queue, audit_log, system_metrics
krai_parts         - Parts catalog and accessories
```

### Phase 6 Enhanced Features

- ✅ **Multimodal Embeddings** - Embeddings in `krai_intelligence.chunks.embedding` (a planned separate embeddings table was never implemented)
- ✅ **Hierarchical Chunking** - Section structure and cross-chunk linking
- ✅ **SVG Vector Graphics** - Vector graphics extraction and PNG conversion
- ✅ **Context Extraction** - AI-powered context for all media types
- ✅ **Advanced Search** - Multimodal search with context awareness

---

## 🚀 Quick Start Migration

### Method 1: Docker Compose (Recommended)

```bash
# 1. Start PostgreSQL container
docker-compose up -d postgresql

# 2. Wait for database to be ready
python scripts/wait_for_services.py

# 3. Apply all migrations automatically
python scripts/apply_migrations.py

# 4. Verify migration success
python scripts/test_postgresql_migrations.py
```

### Method 2: Manual SQL Application

```bash
# 1. Connect to PostgreSQL
docker-compose exec postgresql psql -U krai_user -d krai_db

# 2. Apply core migrations in order
\ir database/migrations/000_setup_pgvector.sql
\ir database/migrations/01_schema_and_tables.sql
\ir database/migrations/02_extend_users_table.sql
\ir database/migrations/02_security_rls_triggers.sql
\ir database/migrations/03_indexes_performance.sql

# 3. Apply Phase 6 migrations (116-119)
\ir database/migrations/116_add_context_aware_media.sql
\ir database/migrations/117_add_multi_vector_embeddings.sql  -- updates chunks.embedding support; no separate embeddings table was implemented
\ir database/migrations/118_add_structured_tables.sql
\ir database/migrations/119_add_hierarchical_chunk_indexes.sql
```

---

## 📋 Migration Files and Order

### Core Infrastructure Migrations

| File | Description | Dependencies |
|------|-------------|--------------|
| `000_setup_pgvector.sql` | Install pgvector extension | None |
| `01_schema_and_tables.sql` | Create schemas and base tables | pgvector |
| `02_extend_users_table.sql` | User management enhancements | Base tables |
| `02_security_rls_triggers.sql` | RLS policies and triggers | User tables |
| `03_indexes_performance.sql` | Performance indexes | All tables |

### Phase 6 Feature Migrations

| File | Description | Dependencies |
|------|-------------|--------------|
| `116_add_context_aware_media.sql` | Context extraction for media | Base schemas |
| `117_add_multi_vector_embeddings.sql` | Chunk embedding support (`krai_intelligence.chunks.embedding`; planned separate table not implemented) | Context tables |
| `118_add_structured_tables.sql` | Enhanced table processing | chunks.embedding |
| `119_add_hierarchical_chunk_indexes.sql` | Hierarchical chunking optimization | All Phase 6 |

### Additional Feature Migrations

The system includes **100+ additional migrations** for specific features:
- Video enhancement (08, 19, 38-42)
- Error code improvements (09, 22-24, 29, 41-45)
- Product catalog (70-72, 102, 107-108, 110-115)
- Agent integration (06, 07, 75-77)
- Performance optimizations (10, 27, 50-51)

---

## 🔧 Migration Execution

### Automated Migration Script

The recommended approach uses the automated migration script:

```bash
# Apply all pending migrations
python scripts/apply_migrations.py

# Apply specific migration
python scripts/apply_migrations.py --version 116

# Apply up to specific version
python scripts/apply_migrations.py --target 119

# Dry run (show what would be applied)
python scripts/apply_migrations.py --dry-run
```

### Manual Migration Steps

For manual control over the migration process:

#### Step 1: Database Preparation

```bash
# Connect to PostgreSQL
docker-compose exec postgresql psql -U krai_user -d krai_db

# Verify pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### Step 2: Apply Core Migrations

```sql
-- Install pgvector (if not already installed)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schemas and base tables
\ir database/migrations/01_schema_and_tables.sql

-- Verify schemas created
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name LIKE 'krai_%'
ORDER BY schema_name;
```

#### Step 3: Apply Security and Indexes

```sql
-- Apply RLS and triggers
\ir database/migrations/02_security_rls_triggers.sql

-- Apply performance indexes
\ir database/migrations/03_indexes_performance.sql

-- Verify indexes created
SELECT schemaname, COUNT(*) as index_count
FROM pg_indexes
WHERE schemaname LIKE 'krai_%'
GROUP BY schemaname;
```

#### Step 4: Apply Phase 6 Features

```sql
-- Context extraction support
\ir database/migrations/116_add_context_aware_media.sql

-- Multimodal embeddings (stored in krai_intelligence.chunks.embedding)
\ir database/migrations/117_add_multi_vector_embeddings.sql  -- updates chunks.embedding support; no separate embeddings table was implemented

-- Structured tables
\ir database/migrations/118_add_structured_tables.sql

-- Hierarchical chunking
\ir database/migrations/119_add_hierarchical_chunk_indexes.sql
```

---

## ✅ Migration Verification

### Core Schema Verification

```sql
-- 1. Check all schemas exist
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name LIKE 'krai_%'
ORDER BY schema_name;
-- Expected: krai_core, krai_content, krai_intelligence, krai_system, krai_parts

-- 2. Check table count
SELECT schemaname, COUNT(*) as table_count
FROM pg_tables
WHERE schemaname LIKE 'krai_%'
GROUP BY schemaname
ORDER BY schemaname;
-- Expected: 30+ tables across all schemas
```

### Phase 6 Feature Verification

```sql
-- 1. Check chunk embedding column
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'chunks'
AND table_schema = 'krai_intelligence'
AND column_name = 'embedding';

-- 2. Check hierarchical chunking columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'chunks'
AND table_schema = 'krai_intelligence'
AND column_name IN ('section_hierarchy', 'section_level', 'previous_chunk_id', 'next_chunk_id');

-- 3. Check context extraction columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'krai_content'
AND table_name = 'images'
AND column_name LIKE '%context%';

-- 4. Check SVG support columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'krai_content'
AND table_name = 'images'
AND column_name IN ('image_type', 'svg_content', 'vector_graphic');
```

### Function Verification

```sql
-- Check RPC functions exist
SELECT routine_schema, routine_name
FROM information_schema.routines
WHERE routine_name IN ('match_multimodal', 'match_images_by_context')
AND routine_schema IN ('public', 'krai_intelligence', 'krai_content', 'krai_core')
ORDER BY routine_schema, routine_name;

-- Test multimodal search function
SELECT * FROM krai_intelligence.match_multimodal(
    '[0.1,0.2,0.3]'::vector,
    0.5,
    10
) LIMIT 1;
```

---

## 🔄 Migration Rollback

### Automatic Rollback

```bash
# Rollback last migration
python scripts/apply_migrations.py --rollback

# Rollback to specific version
python scripts/apply_migrations.py --rollback-to 115

# Rollback multiple migrations
python scripts/apply_migrations.py --rollback-count 5
```

### Manual Rollback

For manual rollback control:

```sql
-- Disable Phase 6 features (if needed)
DROP TABLE IF EXISTS krai_intelligence.structured_tables CASCADE;
-- Embeddings remain in krai_intelligence.chunks.embedding

-- Note: Core schema rollback requires manual table drops
-- Use with caution and ensure proper backups
```

---

## 🛠️ Troubleshooting

### Common Migration Issues

#### 1. "relation already exists" Errors

**Problem**: Migration fails because objects already exist

**Solution**: The migration system is designed to be idempotent
```sql
-- Check if object exists before creating
CREATE TABLE IF NOT EXISTS krai_core.documents (...);
```

#### 2. pgvector Extension Missing

**Problem**: `extension "vector" does not exist`

**Solution**: Install pgvector extension first
```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### 3. Permission Denied Errors

**Problem**: Insufficient permissions to create objects

**Solution**: Ensure proper database user permissions
```sql
-- Grant necessary permissions
GRANT CREATE ON SCHEMA krai_core TO krai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA krai_core TO krai_user;
```

#### 4. Foreign Key Constraint Failures

**Problem**: Foreign key references fail during migration

**Solution**: Ensure tables are created in correct order
```bash
# Use automated migration script to handle dependencies
python scripts/apply_migrations.py --verbose
```

### Performance Issues

#### Slow Index Creation

**Problem**: Migration takes too long on large datasets

**Solution**: Optimize index creation settings
```sql
-- Disable autovacuum during migration
SET autovacuum = OFF;

-- Increase work_mem for index creation
SET work_mem = '256MB';

-- Create indexes concurrently
CREATE INDEX CONCURRENTLY idx_name ON table_name (column_name);
```

---

## 📊 Migration Status Tracking

### Migration History Table

The system tracks applied migrations:

```sql
-- Check migration status
SELECT * FROM krai_system.migrations
ORDER BY applied_at DESC;

-- Check pending migrations
SELECT migration_file
FROM krai_system.pending_migrations
ORDER BY migration_number;
```

### Migration Validation Script

```bash
# Run comprehensive migration validation
python scripts/test_postgresql_migrations.py --verbose

# Expected output:
# ✅ Database: Connected
# ✅ Schemas: 5 found
# ✅ Tables: 32 found
# ✅ Indexes: 127 found
# ✅ Functions: 12 found
# ✅ Phase 6: All features enabled
# 🎉 Migration validation successful!
```

---

## 🎯 Best Practices

### Before Migration

1. **Create Database Backup**
   ```bash
   docker-compose exec postgresql pg_dump -U krai_user krai_db > backup_before_migration.sql
   ```

2. **Verify Database Connection**
   ```bash
   python scripts/test_database_connection.py
   ```

3. **Check Disk Space**
   ```bash
   df -h  # Ensure sufficient space for migration
   ```

### During Migration

1. **Use Automated Scripts** - Prefer `apply_migrations.py` over manual SQL
2. **Monitor Progress** - Use `--verbose` flag for detailed output
3. **Handle Failures Gracefully** - Migrations are idempotent and can be retried

### After Migration

1. **Run Validation Tests**
   ```bash
   python scripts/test_postgresql_migrations.py
   ```

2. **Verify Phase 6 Features**
   ```bash
   python scripts/test_multimodal_search.py
   python scripts/test_hierarchical_chunking.py
   ```

3. **Update Application Configuration**
   ```bash
   # Enable Phase 6 features in .env
   ENABLE_HIERARCHICAL_CHUNKING=true
   ENABLE_SVG_EXTRACTION=true
   ENABLE_MULTIMODAL_SEARCH=true
   ```

---

## 📚 Additional Resources

### Documentation
- [Database Schema Reference](docs/database/DATABASE_SCHEMA.md)
- [Phase 6 Features Guide](docs/PHASES_1_6_SUMMARY.md)
- [Testing Guide](docs/TESTING_GUIDE_PHASES_1_6.md)

### Scripts and Tools
- `scripts/apply_migrations.py` - Automated migration runner
- `scripts/test_postgresql_migrations.py` - Migration validation
- `scripts/generate_db_doc_from_migrations.py` - Schema documentation

### Configuration Files
- `.env.database` - Database connection settings
- `docker-compose.simple.yml` or `docker-compose.production.yml` - Service configuration
- `database/migrations/` - Complete migration file collection

---

## ✅ Migration Checklist

Before proceeding with application deployment:

### Core Infrastructure
- [ ] PostgreSQL container running and accessible
- [ ] pgvector extension installed
- [ ] Database user with proper permissions
- [ ] All core migrations (000-03) applied successfully

### Phase 6 Features
- [ ] Migration 116: Context-aware media support
- [ ] Migration 117: chunks.embedding support (planned separate embeddings table was never implemented)
- [ ] Migration 118: Structured tables enhancement
- [ ] Migration 119: Hierarchical chunking indexes

### Validation
- [ ] All schemas created (krai_core, krai_content, krai_intelligence, krai_system, krai_parts)
- [ ] All tables present with proper structure
- [ ] All indexes created for performance
- [ ] RPC functions available and executable
- [ ] Migration history tracking enabled

### Testing
- [ ] Migration validation script passes
- [ ] Phase 6 feature tests pass
- [ ] Multimodal search functionality verified
- [ ] Hierarchical chunking working correctly

---

**🎉 Migration Complete!**

Your KRAI database is now ready with all Phase 1-6 features. The system supports multimodal document processing, hierarchical chunking, SVG extraction, context extraction, and advanced search capabilities.

For questions or issues, refer to the troubleshooting section or create an issue in the GitHub repository.
