#!/bin/bash
# =============================================================================
# UKG-TravelPerk Integration Docker Entrypoint
# Handles environment validation, logging, and execution for Azure deployment
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_NAME="docker-entrypoint.sh"
LOG_PREFIX="[ENTRYPOINT]"

# -----------------------------------------------------------------------------
# Logging Functions
# -----------------------------------------------------------------------------
log_info() {
    echo "${LOG_PREFIX} [INFO] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo "${LOG_PREFIX} [ERROR] $(date '+%Y-%m-%d %H:%M:%S') $1" >&2
}

log_warn() {
    echo "${LOG_PREFIX} [WARN] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# -----------------------------------------------------------------------------
# Environment Validation
# -----------------------------------------------------------------------------
validate_environment() {
    log_info "Validating environment variables..."

    local missing_vars=()

    # Required UKG variables
    [[ -z "${UKG_BASE_URL}" ]] && missing_vars+=("UKG_BASE_URL")
    [[ -z "${UKG_CUSTOMER_API_KEY}" ]] && missing_vars+=("UKG_CUSTOMER_API_KEY")

    # Either UKG_BASIC_B64 or both USERNAME/PASSWORD required
    if [[ -z "${UKG_BASIC_B64}" ]]; then
        [[ -z "${UKG_USERNAME}" ]] && missing_vars+=("UKG_USERNAME (or UKG_BASIC_B64)")
        [[ -z "${UKG_PASSWORD}" ]] && missing_vars+=("UKG_PASSWORD (or UKG_BASIC_B64)")
    fi

    # Required TravelPerk variables
    [[ -z "${TRAVELPERK_API_BASE}" ]] && missing_vars+=("TRAVELPERK_API_BASE")
    [[ -z "${TRAVELPERK_API_KEY}" ]] && missing_vars+=("TRAVELPERK_API_KEY")

    # Required batch variables
    [[ -z "${COMPANY_ID}" ]] && missing_vars+=("COMPANY_ID")

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            log_error "  - ${var}"
        done
        return 1
    fi

    log_info "Environment validation passed"
    return 0
}

# -----------------------------------------------------------------------------
# Display Configuration (redacted)
# -----------------------------------------------------------------------------
display_config() {
    log_info "=== Configuration ==="
    log_info "  UKG_BASE_URL: ${UKG_BASE_URL}"
    log_info "  UKG_CUSTOMER_API_KEY: ${UKG_CUSTOMER_API_KEY:0:4}****"
    log_info "  TRAVELPERK_API_BASE: ${TRAVELPERK_API_BASE}"
    log_info "  TRAVELPERK_API_KEY: ${TRAVELPERK_API_KEY:0:8}****"
    log_info "  COMPANY_ID: ${COMPANY_ID}"
    log_info "  STATES: ${STATES:-ALL}"
    log_info "  EMPLOYEE_TYPE_CODES: ${EMPLOYEE_TYPE_CODES:-ALL}"
    log_info "  WORKERS: ${WORKERS:-12}"
    log_info "  DRY_RUN: ${DRY_RUN:-0}"
    log_info "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"
    log_info "====================="
}

# -----------------------------------------------------------------------------
# Build Command Arguments
# -----------------------------------------------------------------------------
build_args() {
    local args=()

    # Required
    args+=("--company-id" "${COMPANY_ID}")

    # Optional filters
    [[ -n "${STATES}" ]] && args+=("--states" "${STATES}")
    [[ -n "${EMPLOYEE_TYPE_CODES}" ]] && args+=("--employee-type-codes" "${EMPLOYEE_TYPE_CODES}")
    [[ -n "${EMPLOYEE_ID}" ]] && args+=("--employee-id" "${EMPLOYEE_ID}")
    [[ -n "${LIMIT}" ]] && args+=("--limit" "${LIMIT}")
    [[ -n "${INSERT_SUPERVISOR}" ]] && args+=("--insert-supervisor" "${INSERT_SUPERVISOR}")

    # Flags
    [[ "${DRY_RUN}" == "1" ]] && args+=("--dry-run")
    [[ "${SAVE_LOCAL}" == "1" ]] && args+=("--save-local")

    # Workers
    [[ -n "${WORKERS}" ]] && args+=("--workers" "${WORKERS}")

    echo "${args[@]}"
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
main() {
    log_info "Starting UKG-TravelPerk Integration"
    log_info "Execution mode: ${EXECUTION_MODE:-batch}"
    log_info "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    # Validate environment
    if ! validate_environment; then
        log_error "Environment validation failed. Exiting."
        exit 1
    fi

    # Display configuration
    display_config

    # Check if specific command passed
    if [[ $# -gt 0 ]]; then
        log_info "Executing custom command: $@"
        exec "$@"
    fi

    # Build command arguments
    local cmd_args
    cmd_args=$(build_args)

    log_info "Executing: python3 run-travelperk-batch.py ${cmd_args}"

    # Execute the batch job
    local start_time=$(date +%s)
    local exit_code=0

    python3 run-travelperk-batch.py ${cmd_args} || exit_code=$?

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [[ ${exit_code} -eq 0 ]]; then
        log_info "Batch job completed successfully in ${duration}s"
    else
        log_error "Batch job failed with exit code ${exit_code} after ${duration}s"
    fi

    # For Azure Container Instances - exit with proper code
    exit ${exit_code}
}

# -----------------------------------------------------------------------------
# Run Main
# -----------------------------------------------------------------------------
main "$@"
