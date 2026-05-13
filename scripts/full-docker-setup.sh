#!/bin/bash

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global variables for tracking
OVERALL_EXIT_CODE=0
CLEAN_EXIT_CODE=0
HEALTH_EXIT_CODE=0
INTEGRATION_EXIT_CODE=0
PERSISTENCY_EXIT_CODE=0

CLEAN_START_TIME=0
HEALTH_START_TIME=0
INTEGRATION_START_TIME=0
PERSISTENCY_START_TIME=0

CLEAN_DURATION=""
HEALTH_DURATION=""
INTEGRATION_DURATION=""
PERSISTENCY_DURATION=""

CLEAN_TIMESTAMP=""
HEALTH_TIMESTAMP=""
INTEGRATION_TIMESTAMP=""
PERSISTENCY_TIMESTAMP=""

# Flags
SKIP_CLEAN=false
SKIP_INTEGRATION=false
LOG_FILE=""

# Helper functions
print_header() {
    local title="$1"
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  ${title}${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_status() {
    local status="$1"
    local message="$2"
    local timestamp=$(get_timestamp)

    case "$status" in
        "success")
            echo -e "[${timestamp}] ${GREEN}[SUCCESS]${NC} ✅ ${message}"
            ;;
        "warning")
            echo -e "[${timestamp}] ${YELLOW}[WARNING]${NC} ⚠️  ${message}"
            ;;
        "error")
            echo -e "[${timestamp}] ${RED}[ERROR]${NC} ❌ ${message}"
            ;;
        "info")
            echo -e "[${timestamp}] ${BLUE}[INFO]${NC} ${message}"
            ;;
    esac
}

get_timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

update_exit_code() {
    local new_code=$1
    if [ $new_code -gt $OVERALL_EXIT_CODE ]; then
        OVERALL_EXIT_CODE=$new_code
    fi
}

log_step() {
    local step_num="$1"
    local step_name="$2"
    local timestamp=$(get_timestamp)

    echo ""
    echo -e "[${timestamp}] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_status "info" "Step ${step_num}/4: ${step_name}..."
    echo -e "[${timestamp}] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

format_duration() {
    local seconds=$1
    local minutes=$((seconds / 60))
    local remaining_seconds=$((seconds % 60))

    if [ $minutes -gt 0 ]; then
        echo "${minutes}m ${remaining_seconds}s"
    else
        echo "${seconds}s"
    fi
}

show_help() {
    cat << EOF
KRAI Full Docker Setup Orchestrator

Usage: $0 [OPTIONS]

Runs complete Docker setup workflow: clean setup, health checks,
integration tests, and persistency tests with detailed reporting.

OPTIONS:
    --skip-clean         Skip the clean setup step
    --skip-integration   Skip integration tests
    --log-file <path>    Save logs to specified file
    --help               Show this help message

EXAMPLES:
    # Full setup with all steps
    $0

    # Skip clean setup (faster validation)
    $0 --skip-clean

    # Skip integration tests
    $0 --skip-integration

    # Save logs to file
    $0 --log-file setup.log

EXIT CODES:
    0 - All steps completed successfully
    1 - Completed with warnings (system functional but degraded)
    2 - Critical errors detected (manual intervention required)

EOF
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-clean)
            SKIP_CLEAN=true
            shift
            ;;
        --skip-integration)
            SKIP_INTEGRATION=true
            shift
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Setup logging if requested
if [ -n "$LOG_FILE" ]; then
    exec > >(tee -a "$LOG_FILE")
    exec 2>&1
fi

# Main execution
WORKFLOW_START_TIME=$(date +%s)

print_header "KRAI Full Docker Setup - Starting Workflow"

# Step 1: Clean Setup
if [ "$SKIP_CLEAN" = false ]; then
    log_step "1" "Running Clean Setup"
    CLEAN_START_TIME=$(date +%s)
    CLEAN_TIMESTAMP=$(get_timestamp)

    if ./scripts/docker-clean-setup.sh; then
        CLEAN_EXIT_CODE=0
        CLEAN_END_TIME=$(date +%s)
        CLEAN_DURATION=$(format_duration $((CLEAN_END_TIME - CLEAN_START_TIME)))
        echo ""
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        print_status "success" "Step 1 completed (Duration: ${CLEAN_DURATION}, Exit Code: 0)"
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        CLEAN_EXIT_CODE=$?
        CLEAN_END_TIME=$(date +%s)
        CLEAN_DURATION=$(format_duration $((CLEAN_END_TIME - CLEAN_START_TIME)))
        update_exit_code $CLEAN_EXIT_CODE
        echo ""
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        if [ $CLEAN_EXIT_CODE -eq 1 ]; then
            print_status "warning" "Step 1 completed with warnings (Duration: ${CLEAN_DURATION}, Exit Code: 1)"
        else
            print_status "error" "Step 1 failed (Duration: ${CLEAN_DURATION}, Exit Code: ${CLEAN_EXIT_CODE})"
        fi
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

        if [ $CLEAN_EXIT_CODE -eq 2 ]; then
            print_status "error" "Critical error in clean setup. Continuing to final report."
            OVERALL_EXIT_CODE=2
        fi
    fi
else
    print_status "info" "Skipping Step 1: Clean Setup (--skip-clean flag)"
    CLEAN_TIMESTAMP=$(get_timestamp)
    CLEAN_DURATION="skipped"
    CLEAN_EXIT_CODE=-1
fi

# Step 2: Health Check
log_step "2" "Running Health Check"
HEALTH_START_TIME=$(date +%s)
HEALTH_TIMESTAMP=$(get_timestamp)

if ./scripts/docker-health-check.sh; then
    HEALTH_EXIT_CODE=0
    HEALTH_END_TIME=$(date +%s)
    HEALTH_DURATION=$(format_duration $((HEALTH_END_TIME - HEALTH_START_TIME)))
    echo ""
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_status "success" "Step 2 completed (Duration: ${HEALTH_DURATION}, Exit Code: 0)"
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    HEALTH_EXIT_CODE=$?
    HEALTH_END_TIME=$(date +%s)
    HEALTH_DURATION=$(format_duration $((HEALTH_END_TIME - HEALTH_START_TIME)))
    update_exit_code $HEALTH_EXIT_CODE
    echo ""
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [ $HEALTH_EXIT_CODE -eq 1 ]; then
        print_status "warning" "Step 2 completed with warnings (Duration: ${HEALTH_DURATION}, Exit Code: 1)"
    else
        print_status "error" "Step 2 failed (Duration: ${HEALTH_DURATION}, Exit Code: ${HEALTH_EXIT_CODE})"
    fi
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ $HEALTH_EXIT_CODE -eq 2 ]; then
        print_status "error" "Critical health check failure. System may not be functional."
        print_status "error" "Recommendation: Review health check logs and fix critical issues before proceeding."
        OVERALL_EXIT_CODE=2
    fi
fi

# Step 3: Integration Tests
if [ "$SKIP_INTEGRATION" = false ]; then
    log_step "3" "Running Integration Tests"
    INTEGRATION_START_TIME=$(date +%s)
    INTEGRATION_TIMESTAMP=$(get_timestamp)

    # Check for BACKEND_API_TOKEN
    if [ -z "${BACKEND_API_TOKEN:-}" ]; then
        print_status "warning" "BACKEND_API_TOKEN not set. Some write tests may be skipped."
    fi

    if ./scripts/docker-integration-tests.sh; then
        INTEGRATION_EXIT_CODE=0
        INTEGRATION_END_TIME=$(date +%s)
        INTEGRATION_DURATION=$(format_duration $((INTEGRATION_END_TIME - INTEGRATION_START_TIME)))
        echo ""
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        print_status "success" "Step 3 completed (Duration: ${INTEGRATION_DURATION}, Exit Code: 0)"
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        INTEGRATION_EXIT_CODE=$?
        INTEGRATION_END_TIME=$(date +%s)
        INTEGRATION_DURATION=$(format_duration $((INTEGRATION_END_TIME - INTEGRATION_START_TIME)))
        update_exit_code $INTEGRATION_EXIT_CODE
        echo ""
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        if [ $INTEGRATION_EXIT_CODE -eq 1 ]; then
            print_status "warning" "Step 3 completed with warnings (Duration: ${INTEGRATION_DURATION}, Exit Code: 1)"
        else
            print_status "error" "Step 3 failed (Duration: ${INTEGRATION_DURATION}, Exit Code: ${INTEGRATION_EXIT_CODE})"
        fi
        echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi
else
    print_status "info" "Skipping Step 3: Integration Tests (--skip-integration flag)"
    INTEGRATION_TIMESTAMP=$(get_timestamp)
    INTEGRATION_DURATION="skipped"
    INTEGRATION_EXIT_CODE=-1
fi

# Step 4: Persistency Tests
log_step "4" "Running Persistency Tests"
PERSISTENCY_START_TIME=$(date +%s)
PERSISTENCY_TIMESTAMP=$(get_timestamp)

if ./scripts/docker-health-check.sh --test-persistency; then
    PERSISTENCY_EXIT_CODE=0
    PERSISTENCY_END_TIME=$(date +%s)
    PERSISTENCY_DURATION=$(format_duration $((PERSISTENCY_END_TIME - PERSISTENCY_START_TIME)))
    echo ""
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_status "success" "Step 4 completed (Duration: ${PERSISTENCY_DURATION}, Exit Code: 0)"
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    PERSISTENCY_EXIT_CODE=$?
    PERSISTENCY_END_TIME=$(date +%s)
    PERSISTENCY_DURATION=$(format_duration $((PERSISTENCY_END_TIME - PERSISTENCY_START_TIME)))
    update_exit_code $PERSISTENCY_EXIT_CODE
    echo ""
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [ $PERSISTENCY_EXIT_CODE -eq 1 ]; then
        print_status "warning" "Step 4 completed with warnings (Duration: ${PERSISTENCY_DURATION}, Exit Code: 1)"
    else
        print_status "error" "Step 4 failed (Duration: ${PERSISTENCY_DURATION}, Exit Code: ${PERSISTENCY_EXIT_CODE})"
    fi
    echo -e "[$(get_timestamp)] ${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi

# Generate final report
WORKFLOW_END_TIME=$(date +%s)
TOTAL_DURATION=$(format_duration $((WORKFLOW_END_TIME - WORKFLOW_START_TIME)))

echo ""
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  KRAI Full Docker Setup - Final Report                   ║${NC}"
echo -e "${CYAN}╠═══════════════════════════════════════════════════════════╣${NC}"

# Step 1 Report
echo -e "${CYAN}║  Step 1: Clean Setup                                      ║${NC}"
if [ $CLEAN_EXIT_CODE -eq -1 ]; then
    echo -e "${CYAN}║    Status: ⏭️  SKIPPED                                     ║${NC}"
elif [ $CLEAN_EXIT_CODE -eq 0 ]; then
    echo -e "${CYAN}║    Status: ${GREEN}✅ SUCCESS${CYAN} (Exit Code: 0)                      ║${NC}"
elif [ $CLEAN_EXIT_CODE -eq 1 ]; then
    echo -e "${CYAN}║    Status: ${YELLOW}⚠️  WARNING${CYAN} (Exit Code: 1)                     ║${NC}"
else
    echo -e "${CYAN}║    Status: ${RED}❌ ERROR${CYAN} (Exit Code: ${CLEAN_EXIT_CODE})                       ║${NC}"
fi
echo -e "${CYAN}║    Duration: ${CLEAN_DURATION}${NC}"
printf "${CYAN}║    Timestamp: %-44s║${NC}\n" "$CLEAN_TIMESTAMP"
echo -e "${CYAN}║                                                           ║${NC}"

# Step 2 Report
echo -e "${CYAN}║  Step 2: Health Check                                     ║${NC}"
if [ $HEALTH_EXIT_CODE -eq 0 ]; then
    echo -e "${CYAN}║    Status: ${GREEN}✅ SUCCESS${CYAN} (Exit Code: 0)                      ║${NC}"
elif [ $HEALTH_EXIT_CODE -eq 1 ]; then
    echo -e "${CYAN}║    Status: ${YELLOW}⚠️  WARNING${CYAN} (Exit Code: 1)                     ║${NC}"
else
    echo -e "${CYAN}║    Status: ${RED}❌ ERROR${CYAN} (Exit Code: ${HEALTH_EXIT_CODE})                       ║${NC}"
fi
echo -e "${CYAN}║    Duration: ${HEALTH_DURATION}${NC}"
printf "${CYAN}║    Timestamp: %-44s║${NC}\n" "$HEALTH_TIMESTAMP"
echo -e "${CYAN}║                                                           ║${NC}"

# Step 3 Report
echo -e "${CYAN}║  Step 3: Integration Tests                                ║${NC}"
if [ $INTEGRATION_EXIT_CODE -eq -1 ]; then
    echo -e "${CYAN}║    Status: ⏭️  SKIPPED                                     ║${NC}"
elif [ $INTEGRATION_EXIT_CODE -eq 0 ]; then
    echo -e "${CYAN}║    Status: ${GREEN}✅ SUCCESS${CYAN} (Exit Code: 0)                      ║${NC}"
elif [ $INTEGRATION_EXIT_CODE -eq 1 ]; then
    echo -e "${CYAN}║    Status: ${YELLOW}⚠️  WARNING${CYAN} (Exit Code: 1)                     ║${NC}"
else
    echo -e "${CYAN}║    Status: ${RED}❌ ERROR${CYAN} (Exit Code: ${INTEGRATION_EXIT_CODE})                       ║${NC}"
fi
echo -e "${CYAN}║    Duration: ${INTEGRATION_DURATION}${NC}"
printf "${CYAN}║    Timestamp: %-44s║${NC}\n" "$INTEGRATION_TIMESTAMP"
echo -e "${CYAN}║                                                           ║${NC}"

# Step 4 Report
echo -e "${CYAN}║  Step 4: Persistency Tests                                ║${NC}"
if [ $PERSISTENCY_EXIT_CODE -eq 0 ]; then
    echo -e "${CYAN}║    Status: ${GREEN}✅ SUCCESS${CYAN} (Exit Code: 0)                      ║${NC}"
elif [ $PERSISTENCY_EXIT_CODE -eq 1 ]; then
    echo -e "${CYAN}║    Status: ${YELLOW}⚠️  WARNING${CYAN} (Exit Code: 1)                     ║${NC}"
else
    echo -e "${CYAN}║    Status: ${RED}❌ ERROR${CYAN} (Exit Code: ${PERSISTENCY_EXIT_CODE})                       ║${NC}"
fi
echo -e "${CYAN}║    Duration: ${PERSISTENCY_DURATION}${NC}"
printf "${CYAN}║    Timestamp: %-44s║${NC}\n" "$PERSISTENCY_TIMESTAMP"

echo -e "${CYAN}╠═══════════════════════════════════════════════════════════╣${NC}"

# Overall Status
if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    echo -e "${CYAN}║  Overall Status: ${GREEN}✅ ALL STEPS COMPLETED SUCCESSFULLY${CYAN}      ║${NC}"
elif [ $OVERALL_EXIT_CODE -eq 1 ]; then
    echo -e "${CYAN}║  Overall Status: ${YELLOW}⚠️  COMPLETED WITH WARNINGS${CYAN}              ║${NC}"
else
    echo -e "${CYAN}║  Overall Status: ${RED}❌ CRITICAL ERRORS DETECTED${CYAN}                ║${NC}"
fi

printf "${CYAN}║  Total Duration: %-42s║${NC}\n" "$TOTAL_DURATION"
printf "${CYAN}║  Final Exit Code: %-40s║${NC}\n" "$OVERALL_EXIT_CODE"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Final recommendations
if [ $OVERALL_EXIT_CODE -eq 0 ]; then
    print_status "success" "KRAI Docker environment is fully validated and ready!"
elif [ $OVERALL_EXIT_CODE -eq 1 ]; then
    print_status "warning" "System is functional but some warnings were detected."
    echo ""
    echo -e "${YELLOW}Recommendations:${NC}"
    if [ -z "${BACKEND_API_TOKEN:-}" ]; then
        echo "  - Set BACKEND_API_TOKEN environment variable for full integration tests"
    fi
    echo "  - Review individual step logs for detailed warnings"
    echo "  - Consider running failed steps individually for more details"
else
    print_status "error" "Critical errors detected. System may not be functional."
    echo ""
    echo -e "${RED}Recommendations:${NC}"
    echo "  - Review error messages above for specific issues"
    echo "  - Run failed steps individually with verbose output"
    echo "  - Check Docker logs: docker logs <container-name>"
    echo "  - Verify .env configuration and Docker daemon status"
fi

echo ""

exit $OVERALL_EXIT_CODE
