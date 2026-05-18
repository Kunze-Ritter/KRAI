#!/bin/bash
set -euo pipefail

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Service endpoints
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_USER="krai_user"
POSTGRES_DB="krai"
BACKEND_URL="http://localhost:8000"
LARAVEL_URL="http://localhost:8080"
MINIO_API_URL="http://localhost:9000"
OLLAMA_URL="http://localhost:11434"

# Authentication
BACKEND_TOKEN="${BACKEND_API_TOKEN:-}"  # Set via environment variable

# Test tracking
EXIT_CODE=0
TESTS_PASSED=0
TESTS_FAILED=0
TEST_DOCUMENT_ID=""
TEST_IMAGE_ID=""
LARAVEL_JWT_TOKEN=""

# Helper functions
print_status() {
    local status=$1
    local message=$2
    case $status in
        "success")
            echo -e "${GREEN}✅ ${message}${NC}"
            ((TESTS_PASSED++))
            ;;
        "warning")
            echo -e "${YELLOW}⚠️  ${message}${NC}"
            ;;
        "error")
            echo -e "${RED}❌ ${message}${NC}"
            ((TESTS_FAILED++))
            ;;
        "info")
            echo -e "${BLUE}ℹ️  ${message}${NC}"
            ;;
    esac
}

increment_exit_code() {
    local severity=$1
    if [ "$severity" == "critical" ] && [ $EXIT_CODE -lt 2 ]; then
        EXIT_CODE=2
    elif [ "$severity" == "warning" ] && [ $EXIT_CODE -lt 1 ]; then
        EXIT_CODE=1
    fi
}

cleanup_test_data() {
    print_status "info" "Cleaning up test data..."

    # Remove test document from PostgreSQL
    if [ -n "$TEST_DOCUMENT_ID" ]; then
        docker exec krai-postgres-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
            "DELETE FROM krai_core.documents WHERE document_id = '$TEST_DOCUMENT_ID'" >/dev/null 2>&1 || true
        print_status "info" "Removed test document: $TEST_DOCUMENT_ID"
    fi

    # Remove test image from MinIO via backend API
    if [ -n "$TEST_IMAGE_ID" ] && [ -n "$BACKEND_TOKEN" ]; then
        curl -sf -X DELETE "$BACKEND_URL/api/v1/images/$TEST_IMAGE_ID?delete_from_storage=true" \
            -H "Authorization: Bearer $BACKEND_TOKEN" >/dev/null 2>&1 || true
        print_status "info" "Removed test image: $TEST_IMAGE_ID"
    fi
}

# Backend → PostgreSQL Tests
test_backend_postgres() {
    print_status "info" "Testing Backend → PostgreSQL integration..."

    # Query test - check backend health
    if response=$(curl -sf "$BACKEND_URL/health" 2>/dev/null); then
        if echo "$response" | grep -q '"database".*"healthy"'; then
            print_status "success" "Backend database connection verified"
        else
            print_status "error" "Backend database status not healthy"
            increment_exit_code "critical"
        fi
    else
        print_status "error" "Backend health check failed"
        increment_exit_code "critical"
        return
    fi

    # Read manufacturers test
    if mfr_count=$(docker exec krai-postgres-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM krai_core.manufacturers" 2>/dev/null | tr -d ' '); then
        if [ "$mfr_count" -ge 14 ]; then
            print_status "success" "Manufacturers query successful: $mfr_count records"
        else
            print_status "warning" "Manufacturers count lower than expected: $mfr_count"
            increment_exit_code "warning"
        fi
    else
        print_status "error" "Manufacturers query failed"
        increment_exit_code "critical"
    fi

    # Write test - create test document (requires authentication)
    if [ -z "$BACKEND_TOKEN" ]; then
        print_status "warning" "Backend token not set - skipping write tests (set BACKEND_API_TOKEN env var)"
        increment_exit_code "warning"
        return
    fi

    TEST_DOCUMENT_ID="test_integration_$(date +%s)"
    test_doc_json=$(cat <<EOF
{
    "document_id": "$TEST_DOCUMENT_ID",
    "filename": "integration_test.pdf",
    "file_path": "/tmp/test.pdf",
    "file_hash": "test_hash_$(date +%s)",
    "file_size": 1024,
    "mime_type": "application/pdf"
}
EOF
)

    if response=$(curl -sf -X POST "$BACKEND_URL/api/v1/documents" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $BACKEND_TOKEN" \
        -d "$test_doc_json" 2>/dev/null); then

        # Verify document created in database
        if doc_exists=$(docker exec krai-postgres-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM krai_core.documents WHERE document_id = '$TEST_DOCUMENT_ID'" 2>/dev/null | tr -d ' '); then
            if [ "$doc_exists" -eq 1 ]; then
                print_status "success" "Test document created and persisted: $TEST_DOCUMENT_ID"
            else
                print_status "error" "Test document not found in database"
                increment_exit_code "critical"
            fi
        fi
    else
        print_status "error" "Document creation failed (check authentication)"
        increment_exit_code "critical"
    fi

    # Transaction rollback test - attempt invalid document
    invalid_doc_json='{"filename": "invalid.pdf"}'
    if curl -sf -X POST "$BACKEND_URL/api/v1/documents" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $BACKEND_TOKEN" \
        -d "$invalid_doc_json" 2>/dev/null; then
        print_status "warning" "Invalid document was accepted (validation may be weak)"
        increment_exit_code "warning"
    else
        print_status "success" "Transaction rollback test passed (invalid document rejected)"

        # Verify no stray rows inserted
        if stray_count=$(docker exec krai-postgres-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM krai_core.documents WHERE filename = 'invalid.pdf'" 2>/dev/null | tr -d ' '); then
            if [ "$stray_count" -eq 0 ]; then
                print_status "success" "No stray rows inserted after rollback"
            else
                print_status "error" "Found $stray_count stray row(s) after rollback"
                increment_exit_code "critical"
            fi
        fi
    fi
}

# Backend → MinIO Tests
test_backend_minio() {
    print_status "info" "Testing Backend → MinIO integration..."

    if [ -z "$BACKEND_TOKEN" ]; then
        print_status "warning" "Backend token not set - skipping MinIO tests (set BACKEND_API_TOKEN env var)"
        increment_exit_code "warning"
        return
    fi

    # Upload test - create temporary test file
    test_file="/tmp/integration_test_$(date +%s).png"
    echo "test image content $(date +%s)" > "$test_file"

    if response=$(curl -sf -X POST "$BACKEND_URL/api/v1/images/upload" \
        -H "Authorization: Bearer $BACKEND_TOKEN" \
        -F "file=@$test_file" 2>/dev/null); then

        if echo "$response" | grep -q "image_id"; then
            TEST_IMAGE_ID=$(echo "$response" | grep -o '"image_id":"[^"]*"' | cut -d'"' -f4)
            storage_path=$(echo "$response" | grep -o '"storage_path":"[^"]*"' | cut -d'"' -f4)
            public_url=$(echo "$response" | grep -o '"public_url":"[^"]*"' | cut -d'"' -f4)

            print_status "success" "File upload successful: image_id=$TEST_IMAGE_ID, storage_path=$storage_path"

            # Download test - verify file exists via public URL
            if [ -n "$public_url" ]; then
                if curl -sf -I "$public_url" >/dev/null 2>&1; then
                    print_status "success" "File download verified via public URL"
                else
                    print_status "warning" "File uploaded but not accessible via public URL"
                    increment_exit_code "warning"
                fi
            else
                print_status "warning" "Upload response missing public_url"
                increment_exit_code "warning"
            fi
        else
            print_status "error" "File upload response missing image_id"
            increment_exit_code "critical"
        fi
    else
        print_status "error" "File upload failed (check authentication and endpoint)"
        increment_exit_code "critical"
    fi

    # Cleanup temporary file
    rm -f "$test_file"

    # Delete test
    if [ -n "$TEST_IMAGE_ID" ]; then
        if curl -sf -X DELETE "$BACKEND_URL/api/v1/images/$TEST_IMAGE_ID?delete_from_storage=true" \
            -H "Authorization: Bearer $BACKEND_TOKEN" >/dev/null 2>&1; then
            print_status "success" "File deletion successful (image_id=$TEST_IMAGE_ID)"
            TEST_IMAGE_ID=""
        else
            print_status "warning" "File deletion failed"
            increment_exit_code "warning"
        fi
    fi
}

# Backend → Ollama Tests
test_backend_ollama() {
    print_status "info" "Testing Backend → Ollama integration..."

    # Check AI service health
    if response=$(curl -sf "$BACKEND_URL/health" 2>/dev/null); then
        if echo "$response" | grep -q '"ai".*"healthy"'; then
            print_status "success" "Backend AI service connection verified"
        else
            print_status "warning" "Backend AI service status not healthy"
            increment_exit_code "warning"
        fi
    fi

    # Embedding generation test
    embed_json='{"model":"nomic-embed-text","prompt":"integration test"}'

    if response=$(curl -sf -X POST "$OLLAMA_URL/api/embeddings" \
        -H "Content-Type: application/json" \
        -d "$embed_json" 2>/dev/null); then

        # Count embedding dimensions (rough check)
        embed_count=$(echo "$response" | grep -o '\-\?[0-9]\+\.[0-9]\+' | wc -l)
        if [ "$embed_count" -ge 700 ]; then
            print_status "success" "Embedding generation successful: ~768 dimensions"
        else
            print_status "error" "Embedding dimension mismatch: $embed_count"
            increment_exit_code "critical"
        fi
    else
        print_status "error" "Embedding generation failed"
        increment_exit_code "critical"
    fi

    # Model availability check
    if response=$(curl -sf "$OLLAMA_URL/api/tags" 2>/dev/null); then
        if echo "$response" | grep -q "nomic-embed-text"; then
            print_status "success" "Model 'nomic-embed-text' available"
        else
            print_status "warning" "Model 'nomic-embed-text' not found in available models"
            increment_exit_code "warning"
        fi
    else
        print_status "error" "Failed to query Ollama models"
        increment_exit_code "critical"
    fi
}

# Laravel → Backend Tests
test_laravel_backend() {
    print_status "info" "Testing Laravel → Backend integration..."

    # JWT authentication test - mint or retrieve token
    print_status "info" "Attempting to retrieve JWT token from Laravel..."

    # Try to get JWT token via artisan command (adjust command as needed)
    if jwt_output=$(docker exec krai-laravel-admin php artisan tinker --execute="echo (new \App\Services\JwtService())->generateToken(['user_id' => 1, 'role' => 'admin']);" 2>/dev/null); then
        LARAVEL_JWT_TOKEN=$(echo "$jwt_output" | tail -1 | tr -d '"' | tr -d "'" | xargs)

        if [ -n "$LARAVEL_JWT_TOKEN" ] && [ "$LARAVEL_JWT_TOKEN" != "null" ]; then
            print_status "success" "JWT token retrieved from Laravel"

            # Test valid JWT token
            if response=$(curl -sf "$BACKEND_URL/api/v1/pipeline/errors?page=1&page_size=10" \
                -H "Authorization: Bearer $LARAVEL_JWT_TOKEN" 2>/dev/null); then
                if echo "$response" | grep -q '"errors"' && echo "$response" | grep -q '"total"'; then
                    print_status "success" "JWT authentication test passed (valid token accepted)"
                else
                    print_status "error" "Valid JWT token accepted but response invalid"
                    increment_exit_code "critical"
                fi
            else
                print_status "error" "Valid JWT token rejected"
                increment_exit_code "critical"
            fi

            # Test invalid JWT token
            invalid_token="invalid.jwt.token"
            if curl -sf "$BACKEND_URL/api/v1/pipeline/errors?page=1&page_size=10" \
                -H "Authorization: Bearer $invalid_token" 2>/dev/null >/dev/null; then
                print_status "error" "Invalid JWT token was accepted (should return 401)"
                increment_exit_code "critical"
            else
                print_status "success" "JWT authentication test passed (invalid token rejected with 401)"
            fi
        else
            print_status "warning" "JWT token generation returned empty/null"
            increment_exit_code "warning"
        fi
    else
        print_status "warning" "JWT service not available - testing without authentication"
        increment_exit_code "warning"
    fi

    # REST API call test with valid token (if available)
    if [ -n "$LARAVEL_JWT_TOKEN" ]; then
        if response=$(docker exec krai-laravel-admin curl -sf "$BACKEND_URL/api/v1/pipeline/errors?page=1&page_size=10" \
            -H "Authorization: Bearer $LARAVEL_JWT_TOKEN" 2>/dev/null); then
            if echo "$response" | grep -q '"errors"' && echo "$response" | grep -q '"total"'; then
                print_status "success" "Laravel → Backend REST API call successful (with JWT)"
            else
                print_status "error" "Laravel → Backend API response invalid"
                increment_exit_code "critical"
            fi
        else
            print_status "warning" "Laravel → Backend API call failed"
            increment_exit_code "warning"
        fi
    else
        # Fallback: test without authentication
        if response=$(docker exec krai-laravel-admin curl -sf "$BACKEND_URL/api/v1/pipeline/errors?page=1&page_size=10" 2>/dev/null); then
            if echo "$response" | grep -q '"errors"' && echo "$response" | grep -q '"total"'; then
                print_status "success" "Laravel → Backend API call successful (no auth)"
            else
                print_status "error" "Laravel → Backend API response invalid"
                increment_exit_code "critical"
            fi
        else
            print_status "warning" "Laravel → Backend API call failed"
            increment_exit_code "warning"
        fi
    fi
}

# Laravel → PostgreSQL Tests
test_laravel_postgres() {
    print_status "info" "Testing Laravel → PostgreSQL integration..."

    # Direct query test - Manufacturer count
    if mfr_count=$(docker exec krai-laravel-admin php artisan tinker --execute="echo App\\Models\\Manufacturer::count();" 2>/dev/null | tail -1 | tr -d ' '); then
        if [ "$mfr_count" -ge 14 ]; then
            print_status "success" "Laravel Eloquent query successful: $mfr_count manufacturers"
        else
            print_status "warning" "Manufacturer count lower than expected: $mfr_count"
            increment_exit_code "warning"
        fi
    else
        print_status "error" "Laravel Eloquent query failed"
        increment_exit_code "critical"
    fi

    # Product model test
    if docker exec krai-laravel-admin php artisan tinker --execute="echo App\\Models\\Product::count();" >/dev/null 2>&1; then
        print_status "success" "Product model test passed"
    else
        print_status "warning" "Product model test failed"
        increment_exit_code "warning"
    fi

    # User model test
    if user_count=$(docker exec krai-laravel-admin php artisan tinker --execute="echo App\\Models\\User::count();" 2>/dev/null | tail -1 | tr -d ' '); then
        if [ "$user_count" -ge 1 ]; then
            print_status "success" "User model test passed: $user_count users"
        else
            print_status "warning" "No users found in database"
            increment_exit_code "warning"
        fi
    else
        print_status "warning" "User model test failed"
        increment_exit_code "warning"
    fi

    # PipelineError model test
    if docker exec krai-laravel-admin php artisan tinker --execute="echo App\\Models\\PipelineError::count();" >/dev/null 2>&1; then
        print_status "success" "PipelineError model test passed"
    else
        print_status "warning" "PipelineError model test failed"
        increment_exit_code "warning"
    fi
}

# Generate report
generate_report() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Integration Test Results                                 ║${NC}"
    echo -e "${CYAN}╠═══════════════════════════════════════════════════════════╣${NC}"

    total_tests=$((TESTS_PASSED + TESTS_FAILED))

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${CYAN}║  ${GREEN}Total:                       ✅ $TESTS_PASSED/$total_tests passed${CYAN}             ║${NC}"
    else
        echo -e "${CYAN}║  ${RED}Total:                       ❌ $TESTS_PASSED/$total_tests passed${CYAN}             ║${NC}"
        echo -e "${CYAN}║  ${RED}Failed:                      $TESTS_FAILED tests${CYAN}                        ║${NC}"
    fi

    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ $EXIT_CODE -eq 0 ]; then
        print_status "success" "All integration tests passed successfully!"
    elif [ $EXIT_CODE -eq 1 ]; then
        print_status "warning" "Some tests passed with warnings"
    else
        print_status "error" "Critical integration test failures detected"
    fi

    echo ""
    echo "Exit code: $EXIT_CODE"
}

# Main execution
main() {
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  KRAI Docker Integration Tests                            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    test_backend_postgres
    echo ""
    test_backend_minio
    echo ""
    test_backend_ollama
    echo ""
    test_laravel_backend
    echo ""
    test_laravel_postgres

    generate_report
}

# Set trap for cleanup
trap cleanup_test_data EXIT

# Run main
main

exit $EXIT_CODE
