# Database Adapter Migration Guide

> **⚠️ HISTORICAL REFERENCE - Adapter Pattern Removed**
> This guide documents the legacy adapter pattern used during migration.
> **Current Architecture:** Direct asyncpg connection pools (see `backend/services/database/`)
> **Status:** Adapter pattern removed in KRAI-002 (November 2024)
> **Purpose:** Historical reference only

## Overview

The KRAI system previously supported multiple database backends through a unified `DatabaseAdapter` interface. This allowed the system to run with either Supabase or pure PostgreSQL backends. **This pattern has been removed in favor of direct PostgreSQL connections.**

## Architecture

### Database Adapter Interface

All database operations go through the `DatabaseAdapter` abstract base class defined in `backend/services/database_adapter.py`.

**Implementations (Deprecated):**
- `SupabaseAdapter` - Uses Supabase client with PostgREST API (removed)
- `PostgreSQLAdapter` - Direct PostgreSQL connection via asyncpg (removed in favor of direct connection pools)

### Database Factory

The `create_database_adapter()` function in `backend/services/database_factory.py` creates the appropriate adapter based on the `DATABASE_TYPE` environment variable.

```python
from services.database_factory import create_database_adapter

# Automatically selects adapter based on DATABASE_TYPE env var
adapter = create_database_adapter()
```

## Configuration

### Environment Variables (Historical)

**For Supabase (Deprecated - No Longer Supported):**
```bash
DATABASE_TYPE=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_CONNECTION_URL=postgresql://...  # Optional for direct PG access
```

**For PostgreSQL:**
```bash
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost  # or krai-postgres for Docker
POSTGRES_PORT=5432
POSTGRES_DB=krai
POSTGRES_USER=krai_user
POSTGRES_PASSWORD=krai_password
DATABASE_SCHEMA_PREFIX=krai
```

## API Usage

### In FastAPI Dependencies

```python
from fastapi import Depends
from services.database_adapter import DatabaseAdapter
from services.database_factory import create_database_adapter

# Singleton adapter instance
_adapter = None

def get_database_adapter() -> DatabaseAdapter:
    """Provide shared DatabaseAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = create_database_adapter()
    return _adapter

# Use in endpoints
@app.get("/example")
async def example(adapter: DatabaseAdapter = Depends(get_database_adapter)):
    # Use adapter methods
    doc = await adapter.get_document(document_id)

    # Or execute raw SQL
    results = await adapter.execute_query(
        "SELECT * FROM public.vw_documents WHERE id = %s",
        [document_id]
    )
```

### Legacy Supabase Client Access

For code that still requires Supabase-specific features (like RPC functions):

```python
from supabase import Client

def get_legacy_supabase_client() -> Client | None:
    """Get raw Supabase client when available from the adapter.

    Returns None if running with pure PostgreSQL adapter.
    """
    adapter = get_database_adapter()
    return getattr(adapter, 'client', None)

# Use in endpoints
@app.get("/legacy-feature")
async def legacy_feature(adapter: DatabaseAdapter = Depends(get_database_adapter)):
    legacy_client = get_legacy_supabase_client()
    if not legacy_client:
        raise HTTPException(
            status_code=501,
            detail="This feature requires Supabase (not available in PostgreSQL-only mode)"
        )

    # Use legacy client for Supabase-specific features
    result = legacy_client.rpc('some_function', {...})
```

## Adapter Methods

### Document Operations

```python
# Create document
doc_id = await adapter.create_document(document_model)

# Get document
doc = await adapter.get_document(document_id)

# Update document
success = await adapter.update_document(document_id, {"status": "completed"})
```

### Generic SQL Execution

```python
# Execute parameterized query
results = await adapter.execute_query(
    "SELECT * FROM krai_core.documents WHERE manufacturer_id = %s",
    [manufacturer_id]
)

# Results are returned as List[Dict[str, Any]]
for row in results:
    print(row['filename'])
```

### RPC Functions (Supabase-specific)

```python
try:
    # Try RPC (works with SupabaseAdapter)
    result = await adapter.rpc('match_documents', {
        'query_embedding': embedding,
        'match_count': 10
    })
except NotImplementedError:
    # Fallback for PostgreSQLAdapter
    result = await adapter.search_embeddings(
        query_embedding=embedding,
        limit=10
    )
```

## Table Names and Schemas

**IMPORTANT:** Always use fully qualified table names in SQL queries:

- **Views:** `public.vw_documents`, `public.vw_error_codes`, etc.
- **Tables:** `krai_core.documents`, `krai_content.chunks`, `krai_intelligence.chunks`, etc.

**Never assume** schema locations - always check `DATABASE_SCHEMA.md` for the actual table locations.

## Migration Checklist

When migrating code to use DatabaseAdapter:

- [ ] Replace `supabase=Depends(get_supabase)` with `adapter: DatabaseAdapter = Depends(get_database_adapter)`
- [ ] Replace `.table(...).select(...).execute()` with `await adapter.execute_query(...)`
- [ ] Use fully qualified table names (`schema.table`)
- [ ] Use parameterized queries with `%s` placeholders
- [ ] Make endpoint functions `async def`
- [ ] Await all adapter method calls
- [ ] Handle PostgreSQL-only mode gracefully (return 501 for Supabase-only features)
- [ ] Update type hints to use `DatabaseAdapter` instead of `Client`

## Testing

Run tests with different database backends:

```bash
# Test with Supabase
DATABASE_TYPE=supabase pytest tests/

# Test with PostgreSQL
DATABASE_TYPE=postgresql pytest tests/
```

## Troubleshooting

### "Table not found" errors

- Check `DATABASE_SCHEMA.md` for correct schema and table names
- Ensure you're using fully qualified names (`schema.table`)

### "Method not implemented" errors

- Some methods (like RPC) are Supabase-specific
- Implement fallback logic for PostgreSQL adapter
- Or return HTTP 501 for unavailable features

### Connection errors

- Verify environment variables are set correctly
- Check database connectivity
- Review logs for detailed error messages

## See Also

- `backend/services/database_adapter.py` - Base adapter interface
- `backend/services/database_factory.py` - Adapter factory
- `backend/services/supabase_adapter.py` - Supabase implementation
- `backend/services/postgresql_adapter.py` - PostgreSQL implementation
- `DATABASE_SCHEMA.md` - Complete database schema reference
