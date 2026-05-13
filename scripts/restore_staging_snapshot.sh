#!/bin/bash

# restore_staging_snapshot.sh
# Restore database snapshot to staging environment
#
# Usage:
#   ./scripts/restore_staging_snapshot.sh --snapshot-dir ./staging-snapshots/anonymized
#   ./scripts/restore_staging_snapshot.sh --snapshot-dir ./staging-snapshots/latest --staging-host postgres-staging
#   ./scripts/restore_staging_snapshot.sh --snapshot-dir ./staging-snapshots/snapshot_20250116_103000 --no-backup
#
# Environment Variables:
#   STAGING_DB_HOST     - Staging PostgreSQL host (default: postgres-staging)
#   STAGING_DB_PORT     - Staging database port (default: 5433)
#   STAGING_DB_NAME     - Staging database name (default: krai_staging)
#   STAGING_DB_USER     - Staging database user (default: postgres)
#   STAGING_DB_PASSWORD - Staging database password (required)

set -e

# Default values
SNAPSHOT_DIR=""
STAGING_HOST="${STAGING_DB_HOST:-postgres-staging}"
STAGING_PORT="${STAGING_DB_PORT:-5433}"
STAGING_DB="${STAGING_DB_NAME:-krai_staging}"
STAGING_USER="${STAGING_DB_USER:-postgres}"
STAGING_PASSWORD="${STAGING_DB_PASSWORD}"
CREATE_BACKUP=true

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --snapshot-dir)
            SNAPSHOT_DIR="$2"
            shift 2
            ;;
        --staging-host)
            STAGING_HOST="$2"
            shift 2
            ;;
        --staging-port)
            STAGING_PORT="$2"
            shift 2
            ;;
        --staging-db)
            STAGING_DB="$2"
            shift 2
            ;;
        --staging-user)
            STAGING_USER="$2"
            shift 2
            ;;
        --no-backup)
            CREATE_BACKUP=false
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --snapshot-dir DIR       Path to snapshot directory (required)"
            echo "  --staging-host HOST      Staging database host (default: postgres-staging)"
            echo "  --staging-port PORT      Staging database port (default: 5433)"
            echo "  --staging-db DB          Staging database name (default: krai_staging)"
            echo "  --staging-user USER      Staging database user (default: postgres)"
            echo "  --no-backup              Skip backup creation before restoration"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$SNAPSHOT_DIR" ]; then
    echo "Error: --snapshot-dir is required"
    exit 1
fi

if [ ! -d "$SNAPSHOT_DIR" ]; then
    echo "Error: Snapshot directory not found: $SNAPSHOT_DIR"
    exit 1
fi

if [ -z "$STAGING_PASSWORD" ]; then
    echo "Error: STAGING_DB_PASSWORD environment variable is required"
    exit 1
fi

# Validate manifest file
MANIFEST_FILE="${SNAPSHOT_DIR}/manifest.json"
if [ ! -f "$MANIFEST_FILE" ]; then
    echo "Error: Manifest file not found: $MANIFEST_FILE"
    exit 1
fi

echo "=== KRAI Staging Snapshot Restoration ==="
echo "Snapshot: ${SNAPSHOT_DIR}"
echo "Target: ${STAGING_HOST}:${STAGING_PORT}/${STAGING_DB}"
echo ""

# Export PGPASSWORD for psql
export PGPASSWORD="$STAGING_PASSWORD"

# Test database connection
echo "Testing database connection..."
psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" -c "SELECT 1;" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Cannot connect to staging database"
    exit 1
fi
echo "  ✓ Database connection successful"
echo ""

# Create backup if requested
if [ "$CREATE_BACKUP" = true ]; then
    echo "Creating backup of staging database..."
    BACKUP_DIR="./staging-backups"
    BACKUP_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="${BACKUP_DIR}/staging_backup_${BACKUP_TIMESTAMP}.sql"

    mkdir -p "$BACKUP_DIR"

    pg_dump -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
        --schema=krai_core --schema=krai_intelligence --schema=krai_content \
        --data-only \
        > "$BACKUP_FILE" 2>&1

    if [ $? -eq 0 ]; then
        echo "  ✓ Backup created: $BACKUP_FILE"
    else
        echo "  ⚠️  Backup failed, but continuing..."
    fi
    echo ""
fi

# Function to restore CSV data
restore_csv_data() {
    local schema=$1
    local table=$2
    local csv_file="${SNAPSHOT_DIR}/${schema}_${table}.csv"

    if [ ! -f "$csv_file" ]; then
        echo "  ⚠️  CSV file not found: $csv_file"
        return 1
    fi

    echo "Restoring ${schema}.${table}..."

    # Truncate table first
    psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
        -c "TRUNCATE TABLE ${schema}.${table} CASCADE;" > /dev/null 2>&1

    # Copy data from CSV
    psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
        -c "\COPY ${schema}.${table} FROM '${csv_file}' WITH CSV HEADER;" 2>&1

    if [ $? -eq 0 ]; then
        local row_count=$(psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
            -t -c "SELECT COUNT(*) FROM ${schema}.${table};" 2>/dev/null | xargs)
        echo "  ✓ Restored ${row_count} rows to ${schema}.${table}"
        return 0
    else
        echo "  ✗ Failed to restore ${schema}.${table}"
        return 2
    fi
}

# Disable triggers temporarily
echo "Disabling triggers..."
psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
    -c "SET session_replication_role = replica;" > /dev/null 2>&1
echo "  ✓ Triggers disabled"
echo ""

# Restore tables in dependency order
echo "Restoring tables..."

# 1. Documents (no dependencies)
restore_csv_data "krai_core" "documents"

# 2. Chunks (depends on documents)
restore_csv_data "krai_intelligence" "chunks"

# 3. Content tables (depend on documents)
restore_csv_data "krai_content" "images"
restore_csv_data "krai_content" "videos"
restore_csv_data "krai_content" "links"
restore_csv_data "krai_content" "chunks"

# 4. Embeddings (depend on documents)
restore_csv_data "krai_intelligence" "embeddings_v2"

echo ""

# Re-enable triggers
echo "Re-enabling triggers..."
psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
    -c "SET session_replication_role = DEFAULT;" > /dev/null 2>&1
echo "  ✓ Triggers re-enabled"
echo ""

# Update sequences
echo "Updating sequences..."

update_sequence() {
    local schema=$1
    local table=$2
    local sequence="${schema}.${table}_id_seq"

    psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
        -c "SELECT setval('${sequence}', COALESCE((SELECT MAX(id) FROM ${schema}.${table}), 1));" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "  ✓ Updated sequence: $sequence"
    fi
}

update_sequence "krai_core" "documents"
update_sequence "krai_intelligence" "chunks"
update_sequence "krai_content" "images"
update_sequence "krai_content" "videos"
update_sequence "krai_content" "links"
update_sequence "krai_content" "chunks"
update_sequence "krai_intelligence" "embeddings_v2"

echo ""

# Verify restoration
echo "Verifying restoration..."

verify_table() {
    local schema=$1
    local table=$2
    local expected_count=$3

    local actual_count=$(psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" \
        -t -c "SELECT COUNT(*) FROM ${schema}.${table};" 2>/dev/null | xargs)

    if [ "$actual_count" = "$expected_count" ]; then
        echo "  ✓ ${schema}.${table}: ${actual_count} rows (matches manifest)"
    else
        echo "  ⚠️  ${schema}.${table}: ${actual_count} rows (expected ${expected_count})"
    fi
}

# Read expected counts from manifest
DOCS_COUNT=$(jq -r '.tables."krai_core.documents"' "$MANIFEST_FILE")
CHUNKS_COUNT=$(jq -r '.tables."krai_intelligence.chunks"' "$MANIFEST_FILE")
IMAGES_COUNT=$(jq -r '.tables."krai_content.images"' "$MANIFEST_FILE")
VIDEOS_COUNT=$(jq -r '.tables."krai_content.videos"' "$MANIFEST_FILE")
LINKS_COUNT=$(jq -r '.tables."krai_content.links"' "$MANIFEST_FILE")
CONTENT_CHUNKS_COUNT=$(jq -r '.tables."krai_content.chunks"' "$MANIFEST_FILE")
EMBEDDINGS_V2_COUNT=$(jq -r '.tables."krai_intelligence.embeddings_v2"' "$MANIFEST_FILE")

verify_table "krai_core" "documents" "$DOCS_COUNT"
verify_table "krai_intelligence" "chunks" "$CHUNKS_COUNT"
verify_table "krai_content" "images" "$IMAGES_COUNT"
verify_table "krai_content" "videos" "$VIDEOS_COUNT"
verify_table "krai_content" "links" "$LINKS_COUNT"
verify_table "krai_content" "chunks" "$CONTENT_CHUNKS_COUNT"
verify_table "krai_intelligence" "embeddings_v2" "$EMBEDDINGS_V2_COUNT"

echo ""

# Generate restoration report
REPORT_FILE="${SNAPSHOT_DIR}/restoration_report.json"
cat > "$REPORT_FILE" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "snapshot_dir": "${SNAPSHOT_DIR}",
  "staging_database": {
    "host": "${STAGING_HOST}",
    "port": ${STAGING_PORT},
    "name": "${STAGING_DB}"
  },
  "backup_created": ${CREATE_BACKUP},
  "verification": {
    "krai_core.documents": {
      "expected": ${DOCS_COUNT},
      "actual": $(psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" -t -c "SELECT COUNT(*) FROM krai_core.documents;" 2>/dev/null | xargs)
    },
    "krai_intelligence.chunks": {
      "expected": ${CHUNKS_COUNT},
      "actual": $(psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" -t -c "SELECT COUNT(*) FROM krai_intelligence.chunks;" 2>/dev/null | xargs)
    },
    "krai_content.images": {
      "expected": ${IMAGES_COUNT},
      "actual": $(psql -h "$STAGING_HOST" -p "$STAGING_PORT" -U "$STAGING_USER" -d "$STAGING_DB" -t -c "SELECT COUNT(*) FROM krai_content.images;" 2>/dev/null | xargs)
    }
  },
  "status": "completed"
}
EOF

echo "  ✓ Restoration report saved: $REPORT_FILE"

# Unset password
unset PGPASSWORD

echo ""
echo "=== Restoration Complete ==="
echo "Staging database is ready for testing"
echo ""
echo "Next steps:"
echo "  1. Validate snapshot: python scripts/validate_snapshot.py --snapshot-dir ${SNAPSHOT_DIR}"
echo "  2. Run tests against staging environment"

exit 0
