#!/bin/bash
#
# Docker Clean Setup Script for KRAI
#
# This script performs a complete Docker environment reset:
# - Stops all containers
# - Removes all KRAI volumes
# - Prunes Docker networks
# - Starts fresh containers
# - Waits for service initialization
# - Verifies seed data
#
# Usage:
#   ./scripts/docker-clean-setup.sh
#
# Requirements:
#   - Docker and Docker Compose installed
#   - .env file configured in project root
#   - Sufficient permissions to manage Docker resources
#

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Docker Compose command (will be detected)
DOCKER_COMPOSE_CMD=""

# Helper functions for colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} ✓ $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} ⚠ $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Detect Docker Compose command
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        return 1
    fi
    return 0
}

# Check prerequisites
check_prerequisites() {
    print_status "Step 1/7: Checking prerequisites..."

    local all_ok=true

    # Check Docker
    if command -v docker &> /dev/null; then
        print_success "Docker is available"
    else
        print_error "Docker is not installed or not in PATH"
        all_ok=false
    fi

    # Check Docker Compose
    if detect_docker_compose; then
        print_success "Docker Compose is available ($DOCKER_COMPOSE_CMD)"
    else
        print_error "Docker Compose is not installed or not in PATH"
        all_ok=false
    fi

    # Check .env file
    if [ -f ".env" ]; then
        print_success ".env file found"
    else
        print_error ".env file not found in project root"
        all_ok=false
    fi

    if [ "$all_ok" = false ]; then
        print_error "Prerequisites check failed"
        exit 1
    fi

    return 0
}

# Stop all containers
stop_containers() {
    print_status "Step 2/7: Stopping all Docker containers..."

    if $DOCKER_COMPOSE_CMD down 2>&1; then
        print_success "Containers stopped successfully"
        return 0
    else
        print_error "Failed to stop containers"
        return 1
    fi
}

# Remove KRAI volumes
remove_volumes() {
    print_status "Step 3/7: Removing KRAI volumes..."

    local volumes=(
        "krai_postgres_data"
        "krai_minio_data"
        "minio_data"
        "krai_ollama_data"
        "ollama_data"
        "krai_redis_data"
        "redis_data"
        "laravel_vendor"
        "laravel_node_modules"
    )

    for volume in "${volumes[@]}"; do
        if docker volume ls -q | grep -w "^${volume}$" &> /dev/null; then
            if docker volume rm "$volume" 2>&1; then
                print_success "Removed volume: $volume"
            else
                print_warning "Failed to remove volume: $volume (may be in use)"
            fi
        else
            print_info "Volume not found: $volume (skipping)"
        fi
    done

    return 0
}

# Prune Docker networks
prune_networks() {
    print_status "Step 4/7: Pruning Docker networks..."

    local output
    output=$(docker network prune -f 2>&1)

    if echo "$output" | grep -q "Deleted Networks"; then
        local count=$(echo "$output" | grep -c "^" || echo "0")
        print_success "Networks pruned successfully"
    else
        print_success "No networks to prune"
    fi

    return 0
}

# Start containers
start_containers() {
    print_status "Step 5/7: Starting fresh Docker containers..."

    if $DOCKER_COMPOSE_CMD up -d 2>&1; then
        print_success "Containers started successfully"
        return 0
    else
        print_error "Failed to start containers"
        return 1
    fi
}

# Wait for services to initialize
wait_for_services() {
    print_status "Step 6/7: Waiting 60 seconds for services to initialize..."

    for i in {60..1}; do
        printf "\r${BLUE}[INFO]${NC} Time remaining: %02d seconds" $i
        sleep 1
    done
    printf "\n"

    print_success "Service initialization wait completed"
    return 0
}

# Verify seed data
verify_seed_data() {
    print_status "Step 7/7: Verifying seed data..."

    # Load database credentials from .env using safer loader
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi

    # Set defaults
    local db_host="${DATABASE_HOST:-localhost}"
    local db_port="${DATABASE_PORT:-5432}"
    local db_name="${DATABASE_NAME:-krai}"
    local db_user="${DATABASE_USER:-krai_user}"

    # Detect PostgreSQL container name
    local pg_container
    if docker ps --filter "name=krai-postgres-prod" --format "{{.Names}}" | grep -q "krai-postgres-prod"; then
        pg_container="krai-postgres-prod"
    elif docker ps --filter "name=krai-postgres" --format "{{.Names}}" | grep -q "krai-postgres"; then
        pg_container="krai-postgres"
    else
        print_warning "PostgreSQL container not found, skipping seed data verification"
        return 0
    fi

    print_info "Using PostgreSQL container: $pg_container"

    # Verify manufacturers (expected: 14)
    local manufacturers_count
    manufacturers_count=$(docker exec "$pg_container" psql -U "$db_user" -d "$db_name" -t -c "SELECT COUNT(*) FROM krai_core.manufacturers;" 2>/dev/null | tr -d '[:space:]' || echo "0")

    local verification_failed=false

    if [ "$manufacturers_count" = "14" ]; then
        print_success "Manufacturers count verified: 14"
    else
        print_warning "Manufacturers count mismatch: expected 14, got $manufacturers_count"
        verification_failed=true
    fi

    # Verify retry policies (expected: 4)
    local retry_policies_count
    retry_policies_count=$(docker exec "$pg_container" psql -U "$db_user" -d "$db_name" -t -c "SELECT COUNT(*) FROM krai_system.retry_policies;" 2>/dev/null | tr -d '[:space:]' || echo "0")

    if [ "$retry_policies_count" = "4" ]; then
        print_success "Retry policies count verified: 4"
    else
        print_warning "Retry policies count mismatch: expected 4, got $retry_policies_count"
        verification_failed=true
    fi

    if [ "$verification_failed" = true ]; then
        return 1
    fi

    return 0
}

# Main function
main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  KRAI Docker Clean Setup Script           ║${NC}"
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo ""

    local overall_success=true

    # Execute workflow
    check_prerequisites || overall_success=false

    if [ "$overall_success" = true ]; then
        stop_containers || overall_success=false
    fi

    if [ "$overall_success" = true ]; then
        remove_volumes || overall_success=false
    fi

    if [ "$overall_success" = true ]; then
        prune_networks || overall_success=false
    fi

    if [ "$overall_success" = true ]; then
        start_containers || overall_success=false
    fi

    if [ "$overall_success" = true ]; then
        wait_for_services || overall_success=false
    fi

    if [ "$overall_success" = true ]; then
        verify_seed_data || overall_success=false
    fi

    # Print final summary
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    if [ "$overall_success" = true ]; then
        echo -e "${GREEN}[SUCCESS]${NC} ✓ Docker clean setup completed successfully!"
        echo -e "${BLUE}═══════════════════════════════════════════${NC}"
        echo ""
        exit 0
    else
        echo -e "${RED}[ERROR]${NC} ✗ Docker clean setup encountered errors"
        echo -e "${BLUE}═══════════════════════════════════════════${NC}"
        echo ""
        exit 1
    fi
}

# Run main function
main
