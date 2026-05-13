#!/bin/bash
################################################################################
# Docker Health Check Script (Linux/macOS)
# Validates all KRAI service components with detailed reporting
#
# Usage:
#   ./scripts/docker-health-check.sh              # Run regular health checks
#   ./scripts/docker-health-check.sh --test-persistency  # Run persistency tests
################################################################################

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service endpoints
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_USER="krai_user"
POSTGRES_DB="krai"
BACKEND_URL="http://localhost:8000"
LARAVEL_URL="http://localhost:8080"
MINIO_API_URL="http://localhost:9000"
MINIO_CONSOLE_URL="http://localhost:9001"
OLLAMA_URL="http://localhost:11434"

# Exit code tracking (0=success, 1=warnings, 2=errors)
EXIT_CODE=0

# Expected values
EXPECTED_SCHEMAS=6
EXPECTED_TABLES=44
EXPECTED_MANUFACTURERS=14
EXPECTED_RETRY_POLICIES=4
EXPECTED_EMBEDDING_DIM=768

################################################################################
# Helper Functions
################################################################################

print_status() {
    local status=$1
    local message=$2

    case $status in
        "success")
            echo -e "${GREEN}✅ ${message}${NC}"
            ;;
        "warning")
            echo -e "${YELLOW}⚠️  ${message}${NC}"
            ;;
        "error")
            echo -e "${RED}❌ ${message}${NC}"
            ;;
        "info")
            echo -e "${BLUE}ℹ️  ${message}${NC}"
            ;;
    esac
}

check_command() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        print_status "warning" "Command '$cmd' not found, some checks may be skipped"
        return 1
    fi
    return 0
}

increment_exit_code() {
    local new_code=$1
    if [ "$new_code" -gt "$EXIT_CODE" ]; then
        EXIT_CODE=$new_code
    fi
}

detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        print_status "error" "Neither 'docker-compose' nor 'docker compose' found"
        exit 2
    fi
}

################################################################################
# Data Persistency Test Functions
################################################################################

# Test data persistency across container restarts
# Verifies that data survives docker-compose down/up cycle
test_data_persistency() {
    print_status "info" "Testing Data Persistency Across Container Restarts"
    echo ""

    local test_name="TEST_PERSISTENCY_$(date +%s)"
    local test_website="http://test.persistency.local"
    local test_id=""

    # Detect Docker Compose command
    local compose_cmd=$(detect_docker_compose)

    # Create test manufacturer entry
    print_status "info" "Creating test data..."
    local insert_sql="INSERT INTO krai_core.manufacturers (name, website, is_active) VALUES ('$test_name', '$test_website', true) RETURNING id;"

    set +e
    test_id=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "$insert_sql" 2>/dev/null | tr -d ' ')
    local insert_exit_code=$?
    set -e

    if [ $insert_exit_code -ne 0 ] || [ -z "$test_id" ]; then
        print_status "error" "Failed to create test data"
        increment_exit_code 2
        return
    fi

    print_status "success" "Test manufacturer created: $test_name (ID: $test_id)"
    echo ""

    # Stop all containers
    print_status "info" "Stopping containers..."
    if ! $compose_cmd down 2>/dev/null; then
        print_status "error" "Failed to stop containers with '$compose_cmd down'"
        increment_exit_code 2
        return
    fi
    print_status "success" "Containers stopped"
    echo ""

    # Restart containers
    print_status "info" "Starting containers..."
    if ! $compose_cmd up -d 2>/dev/null; then
        print_status "error" "Failed to start containers with '$compose_cmd up -d'"
        increment_exit_code 2
        return
    fi
    print_status "success" "Containers started"
    echo ""

    # Wait for services to initialize
    print_status "info" "Waiting for services to initialize (60 seconds)..."
    for i in {60..1}; do
        printf "\r  ⏳ %02d seconds remaining..." "$i"
        sleep 1
    done
    printf "\r  ✅ Wait complete                    \n"
    echo ""

    # Verify test data persisted
    print_status "info" "Verifying data persistence..."
    local verify_sql="SELECT name, website, is_active FROM krai_core.manufacturers WHERE id = $test_id;"

    set +e
    local result=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "$verify_sql" 2>/dev/null)
    local verify_exit_code=$?
    set -e

    if [ $verify_exit_code -ne 0 ] || [ -z "$result" ]; then
        print_status "error" "Test data was lost! Persistency test FAILED"
        echo "  Expected: $test_name | $test_website | t"
        echo "  Actual: (no data found)"
        increment_exit_code 2
    else
        # Parse result and verify fields
        local retrieved_name=$(echo "$result" | awk -F'|' '{print $1}' | xargs)
        local retrieved_website=$(echo "$result" | awk -F'|' '{print $2}' | xargs)

        if [ "$retrieved_name" = "$test_name" ] && [ "$retrieved_website" = "$test_website" ]; then
            print_status "success" "Data persisted successfully!"
            echo "  Verified: $retrieved_name | $retrieved_website"
        else
            print_status "error" "Data integrity issue detected"
            echo "  Expected: $test_name | $test_website"
            echo "  Actual: $retrieved_name | $retrieved_website"
            increment_exit_code 2
        fi
    fi
    echo ""

    # Cleanup test data
    print_status "info" "Cleaning up test data..."
    local delete_sql="DELETE FROM krai_core.manufacturers WHERE id = $test_id;"

    set +e
    docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$delete_sql" &> /dev/null
    local delete_exit_code=$?
    set -e

    if [ $delete_exit_code -eq 0 ]; then
        print_status "success" "Test data cleaned up"
    else
        print_status "warning" "Failed to clean up test data (ID: $test_id)"
        increment_exit_code 1
    fi
}

# Verify volume mounts are correctly configured
# Checks that required volumes exist and are mounted to correct containers
verify_volume_mounts() {
    print_status "info" "Volume Mount Verification"
    echo ""

    # Get list of Docker volumes
    local volumes=$(docker volume ls --format "{{.Name}}" 2>/dev/null)

    # Check PostgreSQL volume
    if echo "$volumes" | grep -q "krai_postgres_data"; then
        print_status "success" "PostgreSQL volume 'krai_postgres_data' exists"

        # Verify mount
        set +e
        local pg_mount=$(docker inspect krai-postgres --format '{{range .Mounts}}{{.Name}}{{end}}' 2>/dev/null)
        local inspect_exit_code=$?
        set -e

        if [ $inspect_exit_code -eq 0 ] && echo "$pg_mount" | grep -q "krai_postgres_data"; then
            print_status "success" "PostgreSQL volume correctly mounted"
        else
            print_status "warning" "PostgreSQL volume not mounted to container"
            increment_exit_code 1
        fi
    else
        print_status "error" "PostgreSQL volume 'krai_postgres_data' not found"
        echo "  Recommendation: Check docker-compose.yml volume configuration"
        increment_exit_code 2
    fi
    echo ""

    # Check MinIO volume (try both naming conventions)
    local minio_volume_found=false
    if echo "$volumes" | grep -q "minio_data"; then
        print_status "success" "MinIO volume 'minio_data' exists"
        minio_volume_found=true
    elif echo "$volumes" | grep -q "krai_minio_data"; then
        print_status "success" "MinIO volume 'krai_minio_data' exists"
        minio_volume_found=true
    fi

    if [ "$minio_volume_found" = true ]; then
        set +e
        local minio_mount=$(docker inspect krai-minio --format '{{range .Mounts}}{{.Name}}{{end}}' 2>/dev/null)
        local minio_inspect_exit_code=$?
        set -e

        if [ $minio_inspect_exit_code -eq 0 ] && echo "$minio_mount" | grep -qE "minio_data|krai_minio_data"; then
            print_status "success" "MinIO volume correctly mounted"
        else
            print_status "warning" "MinIO volume not mounted to container"
            increment_exit_code 1
        fi
    else
        print_status "warning" "MinIO volume not found (checked 'minio_data' and 'krai_minio_data')"
        increment_exit_code 1
    fi
    echo ""

    # Check Ollama volume (try both naming conventions)
    local ollama_volume_found=false
    if echo "$volumes" | grep -q "ollama_data"; then
        print_status "success" "Ollama volume 'ollama_data' exists"
        ollama_volume_found=true
    elif echo "$volumes" | grep -q "krai_ollama_data"; then
        print_status "success" "Ollama volume 'krai_ollama_data' exists"
        ollama_volume_found=true
    fi

    if [ "$ollama_volume_found" = true ]; then
        set +e
        local ollama_mount=$(docker inspect krai-ollama --format '{{range .Mounts}}{{.Name}}{{end}}' 2>/dev/null)
        local ollama_inspect_exit_code=$?
        set -e

        if [ $ollama_inspect_exit_code -eq 0 ] && echo "$ollama_mount" | grep -qE "ollama_data|krai_ollama_data"; then
            print_status "success" "Ollama volume correctly mounted"
        else
            print_status "warning" "Ollama volume not mounted to container"
            increment_exit_code 1
        fi
    else
        print_status "warning" "Ollama volume not found (checked 'ollama_data' and 'krai_ollama_data')"
        increment_exit_code 1
    fi
    echo ""

    # Check Redis volume
    if echo "$volumes" | grep -q "redis_data"; then
        print_status "success" "Redis volume 'redis_data' exists"
    else
        print_status "warning" "Redis volume 'redis_data' not found"
        increment_exit_code 1
    fi
}

################################################################################
# PostgreSQL Health Check
################################################################################

check_postgresql() {
    print_status "info" "Checking PostgreSQL..."
    local pg_failed=0

    # Test connection
    if docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" &> /dev/null; then
        print_status "success" "PostgreSQL connection successful"
    else
        print_status "error" "PostgreSQL connection failed"
        echo "  Recommendation: Check PostgreSQL logs: docker logs krai-postgres"
        increment_exit_code 2
        return
    fi

    # Check schema count
    local schema_count=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name LIKE 'krai_%'" | tr -d ' ')

    if [ "$schema_count" -eq "$EXPECTED_SCHEMAS" ]; then
        print_status "success" "Schema count: $schema_count (expected: $EXPECTED_SCHEMAS)"
    else
        print_status "error" "Schema count: $schema_count (expected: $EXPECTED_SCHEMAS)"
        echo "  Recommendation: Run database migrations: docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/001_core_schema.sql"
        increment_exit_code 2
        pg_failed=1
    fi

    # Check table count
    local table_count=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema LIKE 'krai_%' AND table_type = 'BASE TABLE'" | tr -d ' ')

    if [ "$table_count" -eq "$EXPECTED_TABLES" ]; then
        print_status "success" "Table count: $table_count (expected: $EXPECTED_TABLES)"
    else
        print_status "error" "Table count: $table_count (expected: $EXPECTED_TABLES)"
        echo "  Recommendation: Run database migrations in database/migrations_postgresql/"
        increment_exit_code 2
        pg_failed=1
    fi

    # Check manufacturers
    local mfr_count=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM krai_core.manufacturers" 2>/dev/null | tr -d ' ')

    if [ -n "$mfr_count" ] && [ "$mfr_count" -ge "$EXPECTED_MANUFACTURERS" ]; then
        print_status "success" "Manufacturers: $mfr_count (expected: >=$EXPECTED_MANUFACTURERS)"
    else
        print_status "warning" "Manufacturers: ${mfr_count:-0} (expected: >=$EXPECTED_MANUFACTURERS)"
        echo "  Recommendation: Load seed data: docker exec krai-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/030_seeds.sql"
        increment_exit_code 1
    fi

    # Check retry policies
    local retry_count=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM krai_system.retry_policies" 2>/dev/null | tr -d ' ')

    if [ -n "$retry_count" ] && [ "$retry_count" -ge "$EXPECTED_RETRY_POLICIES" ]; then
        print_status "success" "Retry policies: $retry_count (expected: >=$EXPECTED_RETRY_POLICIES)"
    else
        print_status "warning" "Retry policies: ${retry_count:-0} (expected: >=$EXPECTED_RETRY_POLICIES)"
        echo "  Recommendation: Load seed data for retry policies"
        increment_exit_code 1
    fi

    # Check pgvector extension
    local pgvector_version=$(docker exec krai-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'" 2>/dev/null | tr -d ' ')

    if [ -n "$pgvector_version" ]; then
        print_status "success" "pgvector extension: v$pgvector_version"
    else
        print_status "error" "pgvector extension not found"
        echo "  Recommendation: Install pgvector extension: CREATE EXTENSION vector;"
        increment_exit_code 2
    fi
}

################################################################################
# FastAPI Backend Health Check
################################################################################

check_backend() {
    print_status "info" "Checking FastAPI Backend..."

    # Test /health endpoint
    if health_response=$(curl -sf "$BACKEND_URL/health" 2>/dev/null); then
        print_status "success" "Backend /health endpoint responding"

        # Parse JSON response (if jq available)
        if check_command jq; then
            local db_status=$(echo "$health_response" | jq -r '.database // "unknown"')
            local storage_status=$(echo "$health_response" | jq -r '.storage // "unknown"')
            local ai_status=$(echo "$health_response" | jq -r '.ai // "unknown"')

            echo "  Database: $db_status"
            echo "  Storage: $storage_status"
            echo "  AI: $ai_status"

            if [ "$db_status" != "healthy" ] || [ "$storage_status" != "healthy" ]; then
                print_status "warning" "Some backend services are not healthy"
                increment_exit_code 1
            fi
        fi
    else
        print_status "error" "Backend /health endpoint not responding"
        echo "  Recommendation: Check backend logs: docker logs krai-engine"
        increment_exit_code 2
        return
    fi

    # Test /docs endpoint
    if curl -sf -I "$BACKEND_URL/docs" | grep -q "200 OK"; then
        print_status "success" "Backend /docs (Swagger UI) accessible"
    else
        print_status "warning" "Backend /docs endpoint not accessible"
        increment_exit_code 1
    fi

    # Test /redoc endpoint
    if curl -sf -I "$BACKEND_URL/redoc" | grep -q "200 OK"; then
        print_status "success" "Backend /redoc (ReDoc) accessible"
    else
        print_status "warning" "Backend /redoc endpoint not accessible"
        increment_exit_code 1
    fi
}

################################################################################
# Laravel Admin Health Check
################################################################################

check_laravel() {
    print_status "info" "Checking Laravel Admin Dashboard..."

    # Test dashboard accessibility
    if curl -sf "$LARAVEL_URL/kradmin" &> /dev/null; then
        print_status "success" "Laravel dashboard accessible"
    else
        print_status "error" "Laravel dashboard not accessible"
        echo "  Recommendation: Check nginx logs: docker logs krai-laravel-nginx"
        echo "  Recommendation: Check Laravel logs: docker logs krai-laravel-admin"
        increment_exit_code 2
        return
    fi

    # Test login page
    if curl -sf "$LARAVEL_URL/kradmin/login" &> /dev/null; then
        print_status "success" "Laravel login page accessible"
    else
        print_status "warning" "Laravel login page not accessible"
        increment_exit_code 1
    fi

    # Test database connection via artisan
    if docker exec krai-laravel-admin php artisan db:show &> /dev/null; then
        print_status "success" "Laravel database connection successful"
    else
        print_status "error" "Laravel database connection failed"
        echo "  Recommendation: Check .env configuration in laravel-admin/"
        increment_exit_code 2
    fi

    # List Filament resources (check if routes exist)
    print_status "info" "Checking Filament resources..."
    local resources=("documents" "products" "manufacturers" "users" "pipeline-errors" "alert-configurations")
    local resource_count=0

    for resource in "${resources[@]}"; do
        if curl -sf "$LARAVEL_URL/kradmin/$resource" &> /dev/null || \
           curl -sf "$LARAVEL_URL/kradmin/resources/$resource" &> /dev/null; then
            resource_count=$((resource_count + 1))
        fi
    done

    if [ "$resource_count" -ge 3 ]; then
        print_status "success" "Filament resources accessible ($resource_count/${#resources[@]})"
    else
        print_status "warning" "Limited Filament resources accessible ($resource_count/${#resources[@]})"
        increment_exit_code 1
    fi
}

################################################################################
# MinIO Health Check
################################################################################

check_minio() {
    print_status "info" "Checking MinIO..."

    # Test API endpoint
    if curl -sf "$MINIO_API_URL/minio/health/live" &> /dev/null; then
        print_status "success" "MinIO API responding"
    else
        print_status "error" "MinIO API not responding"
        echo "  Recommendation: Check MinIO logs: docker logs krai-minio"
        increment_exit_code 2
        return
    fi

    # Test console accessibility
    if curl -sf -I "$MINIO_CONSOLE_URL" | grep -q "200\|302\|301"; then
        print_status "success" "MinIO console accessible"
    else
        print_status "warning" "MinIO console not accessible"
        increment_exit_code 1
    fi

    # Test bucket operations (if mc command available)
    if check_command mc; then
        local test_bucket="health-check-test-$(date +%s)"

        # Read MinIO credentials from environment or use defaults
        local minio_access_key="${OBJECT_STORAGE_ACCESS_KEY:-minioadmin}"
        local minio_secret_key="${OBJECT_STORAGE_SECRET_KEY:-minioadmin123}"

        # Configure mc alias
        mc alias set local "$MINIO_API_URL" "$minio_access_key" "$minio_secret_key" &> /dev/null || true

        # Create test bucket
        if mc mb "local/$test_bucket" &> /dev/null; then
            print_status "success" "MinIO bucket creation successful"

            # Upload test file
            if echo "test" | mc pipe "local/$test_bucket/test.txt" &> /dev/null; then
                print_status "success" "MinIO file upload successful"

                # Download test file
                if mc cat "local/$test_bucket/test.txt" &> /dev/null; then
                    print_status "success" "MinIO file download successful"
                fi
            fi

            # Cleanup
            mc rm "local/$test_bucket/test.txt" &> /dev/null || true
            mc rb "local/$test_bucket" &> /dev/null || true
        else
            print_status "warning" "MinIO bucket operations not tested (permissions issue)"
            echo "  Recommendation: Initialize MinIO: python scripts/init_minio.py"
            increment_exit_code 1
        fi
    else
        print_status "info" "MinIO client (mc) not found, skipping bucket operation tests"
    fi
}

################################################################################
# Ollama Health Check
################################################################################

check_ollama() {
    print_status "info" "Checking Ollama..."

    # Test API availability
    if curl -sf "$OLLAMA_URL/api/tags" &> /dev/null; then
        print_status "success" "Ollama API responding"
    else
        print_status "error" "Ollama API not responding"
        echo "  Recommendation: Check Ollama logs: docker logs krai-ollama"
        increment_exit_code 2
        return
    fi

    # Check model presence (required check - cannot be skipped)
    local models_response=$(curl -sf "$OLLAMA_URL/api/tags" 2>/dev/null)

    if [ -z "$models_response" ]; then
        print_status "error" "Failed to fetch model list from Ollama"
        increment_exit_code 2
        return
    fi

    # Try to parse with jq first, fallback to grep if jq is unavailable
    local model_found=false
    if check_command jq; then
        local models=$(echo "$models_response" | jq -r '.models[].name' 2>/dev/null)
        if echo "$models" | grep -q "nomic-embed-text"; then
            model_found=true
        fi
    else
        # Fallback: parse JSON with grep/sed when jq is unavailable
        if echo "$models_response" | grep -q '"name".*"nomic-embed-text'; then
            model_found=true
        fi
    fi

    if [ "$model_found" = true ]; then
        print_status "success" "Model 'nomic-embed-text' found"
    else
        print_status "error" "Model 'nomic-embed-text' not found"
        echo "  Recommendation: Pull model: docker exec krai-ollama ollama pull nomic-embed-text"
        increment_exit_code 2
        return
    fi

    # Test embedding generation
    local embed_response=$(curl -sf -X POST "$OLLAMA_URL/api/embeddings" \
        -H "Content-Type: application/json" \
        -d '{"model":"nomic-embed-text","prompt":"test"}' 2>/dev/null)

    if [ -n "$embed_response" ]; then
        if check_command jq; then
            local embedding=$(echo "$embed_response" | jq -r '.embedding' 2>/dev/null)

            if [ "$embedding" != "null" ] && [ -n "$embedding" ]; then
                local embed_dim=$(echo "$embed_response" | jq -r '.embedding | length' 2>/dev/null)

                if [ "$embed_dim" -eq "$EXPECTED_EMBEDDING_DIM" ]; then
                    print_status "success" "Embedding generation successful (dim: $embed_dim)"
                else
                    print_status "warning" "Embedding dimension mismatch: $embed_dim (expected: $EXPECTED_EMBEDDING_DIM)"
                    increment_exit_code 1
                fi
            else
                print_status "error" "Embedding generation failed (no embedding in response)"
                increment_exit_code 2
            fi
        else
            print_status "success" "Embedding generation response received"
        fi
    else
        print_status "error" "Embedding generation failed"
        echo "  Recommendation: Verify model is loaded: docker exec krai-ollama ollama list"
        increment_exit_code 2
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    # Parse command-line arguments
    local RUN_PERSISTENCY_TESTS=false

    for arg in "$@"; do
        case $arg in
            --test-persistency)
                RUN_PERSISTENCY_TESTS=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  (no options)         Run regular health checks"
                echo "  --test-persistency   Run data persistency tests"
                echo "  --help, -h           Show this help message"
                echo ""
                exit 0
                ;;
            *)
                echo "Unknown option: $arg"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    echo "=================================="
    if [ "$RUN_PERSISTENCY_TESTS" = true ]; then
        echo "KRAI Data Persistency Tests"
    else
        echo "KRAI Docker Health Check"
    fi
    echo "=================================="
    echo ""

    # Check required commands
    print_status "info" "Checking required commands..."
    check_command docker || { print_status "error" "Docker is required"; exit 2; }

    if [ "$RUN_PERSISTENCY_TESTS" = false ]; then
        check_command curl || { print_status "error" "curl is required"; exit 2; }
    fi

    echo ""

    # Run persistency tests or regular health checks
    if [ "$RUN_PERSISTENCY_TESTS" = true ]; then
        # Run persistency tests
        test_data_persistency
        echo ""

        verify_volume_mounts
        echo ""

        # Generate summary
        echo "=================================="
        echo "Persistency Test Summary"
        echo "=================================="

        if [ "$EXIT_CODE" -eq 0 ]; then
            print_status "success" "All persistency tests passed! Data survives container restarts."
        elif [ "$EXIT_CODE" -eq 1 ]; then
            print_status "warning" "Some warnings detected. Volumes may have configuration issues."
        else
            print_status "error" "Critical errors detected. Data persistency is not working properly."
        fi
    else
        # Run all regular health checks
        check_postgresql
        echo ""

        check_backend
        echo ""

        check_laravel
        echo ""

        check_minio
        echo ""

        check_ollama
        echo ""

        # Generate summary
        echo "=================================="
        echo "Health Check Summary"
        echo "=================================="

        if [ "$EXIT_CODE" -eq 0 ]; then
            print_status "success" "All checks passed successfully!"
        elif [ "$EXIT_CODE" -eq 1 ]; then
            print_status "warning" "Some warnings detected. System is functional but may have degraded performance."
        else
            print_status "error" "Critical errors detected. System may not function properly."
        fi
    fi

    echo ""
    echo "Exit code: $EXIT_CODE"
    exit $EXIT_CODE
}

main "$@"
