#!/bin/bash

# create_staging_snapshot.sh
# Export production data from the last N days for staging environment
#
# Usage:
#   ./scripts/create_staging_snapshot.sh --days 7
#   ./scripts/create_staging_snapshot.sh --days 14 --output-dir ./snapshots
#   ./scripts/create_staging_snapshot.sh --host localhost --port 5432 --database krai --user postgres
#
# Environment Variables:
#   DATABASE_HOST     - PostgreSQL host (default: localhost)
#   DATABASE_NAME     - Database name (default: krai)
#   DATABASE_USER     - Database user (default: postgres)
#   DATABASE_PASSWORD - Database password (required)
#   DATABASE_PORT     - Database port (default: 5432)

set -e

# Default values
DAYS=7
OUTPUT_DIR="./staging-snapshots"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-krai}"
DB_USER="${DATABASE_USER:-postgres}"
DB_PASSWORD="${DATABASE_PASSWORD}"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --days)
            DAYS="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --host)
            DB_HOST="$2"
            shift 2
            ;;
        --port)
            DB_PORT="$2"
            shift 2
            ;;
        --database)
            DB_NAME="$2"
            shift 2
            ;;
        --user)
            DB_USER="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --days N              Export data from last N days (default: 7)"
            echo "  --output-dir DIR      Output directory (default: ./staging-snapshots)"
            echo "  --host HOST           Database host (default: localhost)"
            echo "  --port PORT           Database port (default: 5432)"
            echo "  --database DB         Database name (default: krai)"
            echo "  --user USER           Database user (default: postgres)"
            echo "  --help                Show this help message"
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
if [ -z "$DB_PASSWORD" ]; then
    echo "Error: DATABASE_PASSWORD environment variable is required"
    exit 1
fi

# Create timestamped output directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SNAPSHOT_DIR="${OUTPUT_DIR}/snapshot_${TIMESTAMP}"
mkdir -p "$SNAPSHOT_DIR"

echo "=== KRAI Staging Snapshot Export ==="
echo "Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "Days: ${DAYS}"
echo "Output: ${SNAPSHOT_DIR}"
echo ""

# Export PGPASSWORD for pg_dump
export PGPASSWORD="$DB_PASSWORD"

# Function to export table with WHERE clause
export_table_with_filter() {
    local schema=$1
    local table=$2
    local where_clause=$3
    local output_file="${SNAPSHOT_DIR}/${schema}_${table}.sql"

    echo "Exporting ${schema}.${table}..."

    if [ -z "$where_clause" ]; then
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            --table="${schema}.${table}" \
            --data-only \
            --column-inserts \
            > "$output_file" 2>&1
    else
        # Use psql to generate INSERT statements with WHERE clause
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -c "COPY (SELECT * FROM ${schema}.${table} WHERE ${where_clause}) TO STDOUT WITH CSV HEADER" \
            > "${SNAPSHOT_DIR}/${schema}_${table}.csv" 2>&1
    fi

    if [ $? -eq 0 ]; then
        echo "  ✓ Exported ${schema}.${table}"
        return 0
    else
        echo "  ✗ Failed to export ${schema}.${table}"
        return 2
    fi
}

# Function to count rows
count_rows() {
    local schema=$1
    local table=$2
    local where_clause=$3

    if [ -z "$where_clause" ]; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -t -c "SELECT COUNT(*) FROM ${schema}.${table};" 2>/dev/null | xargs
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -t -c "SELECT COUNT(*) FROM ${schema}.${table} WHERE ${where_clause};" 2>/dev/null | xargs
    fi
}

# Test database connection
echo "Testing database connection..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Cannot connect to database"
    exit 1
fi
echo "  ✓ Database connection successful"
echo ""

# Calculate date threshold
DATE_THRESHOLD=$(date -d "${DAYS} days ago" +"%Y-%m-%d" 2>/dev/null || date -v-${DAYS}d +"%Y-%m-%d")

# Export documents from last N days
echo "Exporting documents from last ${DAYS} days (since ${DATE_THRESHOLD})..."
DOCS_WHERE="created_at >= '${DATE_THRESHOLD}'"
DOCS_COUNT=$(count_rows "krai_core" "documents" "$DOCS_WHERE")
echo "  Found ${DOCS_COUNT} documents"

export_table_with_filter "krai_core" "documents" "$DOCS_WHERE"

# Export chunks for those documents
echo ""
echo "Exporting chunks for selected documents..."
CHUNKS_WHERE="document_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}')"
CHUNKS_COUNT=$(count_rows "krai_intelligence" "chunks" "$CHUNKS_WHERE")
echo "  Found ${CHUNKS_COUNT} chunks"

export_table_with_filter "krai_intelligence" "chunks" "$CHUNKS_WHERE"

# Export related content tables
echo ""
echo "Exporting related content..."

IMAGES_WHERE="document_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}')"
IMAGES_COUNT=$(count_rows "krai_content" "images" "$IMAGES_WHERE")
echo "  Found ${IMAGES_COUNT} images"
export_table_with_filter "krai_content" "images" "$IMAGES_WHERE"

VIDEOS_WHERE="document_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}')"
VIDEOS_COUNT=$(count_rows "krai_content" "videos" "$VIDEOS_WHERE")
echo "  Found ${VIDEOS_COUNT} videos"
export_table_with_filter "krai_content" "videos" "$VIDEOS_WHERE"

LINKS_WHERE="document_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}')"
LINKS_COUNT=$(count_rows "krai_content" "links" "$LINKS_WHERE")
echo "  Found ${LINKS_COUNT} links"
export_table_with_filter "krai_content" "links" "$LINKS_WHERE"

CONTENT_CHUNKS_WHERE="document_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}')"
CONTENT_CHUNKS_COUNT=$(count_rows "krai_content" "chunks" "$CONTENT_CHUNKS_WHERE")
echo "  Found ${CONTENT_CHUNKS_COUNT} content chunks"
export_table_with_filter "krai_content" "chunks" "$CONTENT_CHUNKS_WHERE"

EMBEDDINGS_V2_WHERE="source_id IN (SELECT id FROM krai_core.documents WHERE created_at >= '${DATE_THRESHOLD}') AND source_type = 'document'"
EMBEDDINGS_V2_COUNT=$(count_rows "krai_intelligence" "embeddings_v2" "$EMBEDDINGS_V2_WHERE")
echo "  Found ${EMBEDDINGS_V2_COUNT} embeddings_v2"
export_table_with_filter "krai_intelligence" "embeddings_v2" "$EMBEDDINGS_V2_WHERE"

# Generate manifest file
echo ""
echo "Generating manifest..."
cat > "${SNAPSHOT_DIR}/manifest.json" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "export_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "days": ${DAYS},
  "date_threshold": "${DATE_THRESHOLD}",
  "database": {
    "host": "${DB_HOST}",
    "port": ${DB_PORT},
    "name": "${DB_NAME}"
  },
  "tables": {
    "krai_core.documents": ${DOCS_COUNT},
    "krai_intelligence.chunks": ${CHUNKS_COUNT},
    "krai_content.images": ${IMAGES_COUNT},
    "krai_content.videos": ${VIDEOS_COUNT},
    "krai_content.links": ${LINKS_COUNT},
    "krai_content.chunks": ${CONTENT_CHUNKS_COUNT},
    "krai_intelligence.embeddings_v2": ${EMBEDDINGS_V2_COUNT}
  },
  "total_rows": $((DOCS_COUNT + CHUNKS_COUNT + IMAGES_COUNT + VIDEOS_COUNT + LINKS_COUNT + CONTENT_CHUNKS_COUNT + EMBEDDINGS_V2_COUNT))
}
EOF

echo "  ✓ Manifest created"

# Create symlink to latest snapshot
rm -f "${OUTPUT_DIR}/latest"
ln -s "snapshot_${TIMESTAMP}" "${OUTPUT_DIR}/latest"

# Unset password
unset PGPASSWORD

echo ""
echo "=== Export Complete ==="
echo "Snapshot directory: ${SNAPSHOT_DIR}"
echo "Total rows exported: $((DOCS_COUNT + CHUNKS_COUNT + IMAGES_COUNT + VIDEOS_COUNT + LINKS_COUNT + CONTENT_CHUNKS_COUNT + EMBEDDINGS_V2_COUNT))"
echo ""
echo "Next steps:"
echo "  1. Select benchmark documents: python scripts/select_benchmark_documents.py --snapshot-dir ${SNAPSHOT_DIR}"
echo "  2. Anonymize PII: python scripts/anonymize_pii.py --snapshot-dir ${SNAPSHOT_DIR}"
echo "  3. Restore to staging: ./scripts/restore_staging_snapshot.sh --snapshot-dir ${SNAPSHOT_DIR}"

exit 0
