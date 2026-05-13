# Supabase Database Export Guide

This guide explains how to export schema and seed data from Supabase for local development.

## Prerequisites

1. **PostgreSQL Client Tools** (includes `pg_dump`)
   ```powershell
   # Windows
   winget install PostgreSQL.PostgreSQL

   # Or download from: https://www.postgresql.org/download/windows/
   ```

2. **Supabase Database Password**
   - Go to: [Supabase Dashboard](https://supabase.com/dashboard) > Your Project
   - Navigate to: Settings > Database
   - Copy the password from the connection string
   - Add to `.env.database`:
     ```
     SUPABASE_DB_PASSWORD=your-actual-password-here
     ```

## Quick Export

The easiest way to export is using the provided script:

```bash
# Ensure SUPABASE_DB_PASSWORD is set in .env.database
python scripts/export_supabase_schema.py
```

This will create:
- `database/seeds/01_schema.sql` - Complete schema (DDL)
- `database/seeds/02_minimal_seed.sql` - Reference data

## Manual Export (Advanced)

If you need more control, use `pg_dump` directly:

### 1. Build Connection String

```bash
# Format
postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres

# Example
postgresql://postgres:your-password@db.crujfdpqdjzcfqeyhang.supabase.co:5432/postgres
```

### 2. Export Schema Only

```bash
pg_dump \
  --schema-only \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --schema=krai_core \
  --schema=krai_content \
  --schema=krai_intelligence \
  --schema=krai_system \
  --schema=krai_parts \
  --file=database/seeds/01_schema.sql \
  "postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres"
```

### 3. Export Seed Data

```bash
pg_dump \
  --data-only \
  --no-owner \
  --no-privileges \
  --column-inserts \
  --rows-per-insert=100 \
  --table=krai_core.manufacturers \
  --table=krai_core.product_series \
  --table=krai_core.products \
  --file=database/seeds/02_minimal_seed.sql \
  "postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres"
```

## What to Export

### Schema (Always Export)

All `krai_*` schemas:
- `krai_core` - Core entities (documents, manufacturers, products)
- `krai_content` - Content (chunks, images, videos)
- `krai_intelligence` - AI/ML (embeddings, classifications)
- `krai_system` - System (audit logs, queue, metrics)
- `krai_parts` - Parts catalog

### Data (Selective Export)

**✅ Include:**
- Reference data (manufacturers, product series)
- Sample products (5-10 per manufacturer)
- Essential configuration

**❌ Exclude:**
- User data
- Production documents
- Large binary data
- Embeddings (regenerate locally)
- Temporary data

## Filtering Data

### Limit Rows

```bash
# Export only first 10 products per manufacturer
pg_dump \
  --data-only \
  --table=krai_core.products \
  "postgresql://..." \
  | head -n 1000 > database/seeds/02_minimal_seed.sql
```

### Exclude Sensitive Tables

```bash
# Exclude specific tables
pg_dump \
  --data-only \
  --exclude-table=krai_system.audit_logs \
  --exclude-table=krai_core.users \
  "postgresql://..."
```

### Custom WHERE Clause

For more complex filtering, use SQL directly:

```sql
-- Export only HP and Canon manufacturers
COPY (
  SELECT * FROM krai_core.manufacturers
  WHERE name IN ('HP', 'Canon')
) TO STDOUT WITH CSV HEADER;
```

## Security Checklist

Before committing seed files:

- [ ] No user credentials
- [ ] No API keys or tokens
- [ ] No production customer data
- [ ] No PII (names, emails, addresses)
- [ ] No large binary data (> 1 MB)
- [ ] File size < 5 MB total
- [ ] Review with `git diff database/seeds/`

## Testing Exported Seeds

After exporting, test locally:

```bash
# 1. Remove old container
docker-compose down -v

# 2. Start fresh with seeds
docker-compose up -d krai-postgres

# 3. Wait for healthy
docker ps --filter name=krai-postgres

# 4. Test connection
python scripts/test_adapter_quick.py

# 5. Verify data
docker exec -it krai-postgres psql -U krai_user -d krai
```

```sql
-- Check schemas
\dn krai_*

-- Check tables
\dt krai_core.*

-- Check data
SELECT COUNT(*) FROM krai_core.manufacturers;
SELECT COUNT(*) FROM krai_core.products;
```

## Troubleshooting

### pg_dump not found

**Solution:** Install PostgreSQL client tools (see Prerequisites)

### Connection timeout

**Problem:** Can't connect to Supabase.

**Solution:**
1. Check firewall/VPN
2. Verify connection string
3. Test with `psql`:
   ```bash
   psql "postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres"
   ```

### Permission denied

**Problem:** `permission denied for schema krai_core`

**Solution:** Use service role key or database password, not anon key.

### File too large

**Problem:** Seed file > 10 MB

**Solution:**
1. Reduce sample data (fewer products)
2. Exclude large tables
3. Split into multiple files

## Automation

### GitHub Actions

Export seeds automatically on schema changes:

```yaml
name: Update Database Seeds

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install PostgreSQL client
        run: sudo apt-get install -y postgresql-client

      - name: Export seeds
        env:
          SUPABASE_DB_PASSWORD: ${{ secrets.SUPABASE_DB_PASSWORD }}
        run: python scripts/export_supabase_schema.py

      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          title: "Update database seeds"
          body: "Automated seed export from Supabase"
```

## Maintenance Schedule

- **Weekly:** Check for schema changes
- **Monthly:** Full seed export and review
- **After migrations:** Always update seeds
- **Before releases:** Verify seeds are current

## Related Documentation

- [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) - Current schema reference
- [database/seeds/README.md](../../database/seeds/README.md) - Seed usage guide
- [Supabase Documentation](https://supabase.com/docs/guides/database/overview)
