#!/bin/bash
# =============================================================================
# Azure Deployment Script for UKG-TravelPerk Integration
# =============================================================================
#
# This script deploys the UKG-TravelPerk sync job to Azure Container Instances
# with scheduled execution support.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed (for local builds)
#   - Proper Azure permissions (Contributor on resource group)
#
# Usage:
#   ./deploy.sh [environment]
#   ./deploy.sh prod
#   ./deploy.sh staging
#
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-prod}"

# Load environment-specific config
ENV_FILE="${SCRIPT_DIR}/env.${ENVIRONMENT}.sh"
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE"
else
    echo "Warning: Environment file not found: $ENV_FILE"
    echo "Using default configuration..."
fi

# Default Azure Configuration
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-vai-integration-rg}"
LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${AZURE_ACR_NAME:-vaiacr}"
CONTAINER_NAME="${AZURE_CONTAINER_NAME:-ukg-travelperk-sync}"
IMAGE_NAME="vai-matrix-ukg-travelperk"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-vaistorage}"
FILE_SHARE="${AZURE_FILE_SHARE:-vai-travelperk-data}"

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $1" >&2
}

log_success() {
    echo "[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

check_azure_cli() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run: az login"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Deployment Steps
# -----------------------------------------------------------------------------

create_resource_group() {
    log_info "Creating resource group: $RESOURCE_GROUP"
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    log_success "Resource group created"
}

create_acr() {
    log_info "Creating Azure Container Registry: $ACR_NAME"
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --admin-enabled true \
        --output none 2>/dev/null || log_info "ACR already exists"
    log_success "ACR ready"
}

build_and_push_image() {
    log_info "Building and pushing image to ACR..."

    # Build using ACR Tasks (no local Docker needed)
    az acr build \
        --registry "$ACR_NAME" \
        --image "${IMAGE_NAME}:${IMAGE_TAG}" \
        --file "${PROJECT_DIR}/Dockerfile" \
        "$PROJECT_DIR"

    log_success "Image pushed: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
}

create_storage() {
    log_info "Creating storage account and file share..."

    # Create storage account
    az storage account create \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --output none 2>/dev/null || log_info "Storage account already exists"

    # Get storage key
    STORAGE_KEY=$(az storage account keys list \
        --account-name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query '[0].value' -o tsv)

    # Create file share
    az storage share create \
        --name "$FILE_SHARE" \
        --account-name "$STORAGE_ACCOUNT" \
        --account-key "$STORAGE_KEY" \
        --output none 2>/dev/null || log_info "File share already exists"

    log_success "Storage ready"
}

deploy_container() {
    log_info "Deploying container instance: $CONTAINER_NAME"

    # Get ACR credentials
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

    # Get storage key
    STORAGE_KEY=$(az storage account keys list \
        --account-name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query '[0].value' -o tsv)

    # Delete existing container if exists
    az container delete \
        --name "$CONTAINER_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --yes \
        --output none 2>/dev/null || true

    # Deploy new container
    az container create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$CONTAINER_NAME" \
        --image "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}" \
        --registry-login-server "${ACR_NAME}.azurecr.io" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --cpu 1 \
        --memory 1 \
        --restart-policy Never \
        --environment-variables \
            PYTHONUNBUFFERED=1 \
            LOG_LEVEL="${LOG_LEVEL:-INFO}" \
            EXECUTION_MODE=scheduled \
        --secure-environment-variables \
            UKG_BASE_URL="${UKG_BASE_URL}" \
            UKG_CUSTOMER_API_KEY="${UKG_CUSTOMER_API_KEY}" \
            UKG_USERNAME="${UKG_USERNAME}" \
            UKG_PASSWORD="${UKG_PASSWORD}" \
            TRAVELPERK_API_BASE="${TRAVELPERK_API_BASE}" \
            TRAVELPERK_API_KEY="${TRAVELPERK_API_KEY}" \
            COMPANY_ID="${COMPANY_ID}" \
            STATES="${STATES:-}" \
            EMPLOYEE_TYPE_CODES="${EMPLOYEE_TYPE_CODES:-}" \
            WORKERS="${WORKERS:-12}" \
        --azure-file-volume-account-name "$STORAGE_ACCOUNT" \
        --azure-file-volume-account-key "$STORAGE_KEY" \
        --azure-file-volume-share-name "$FILE_SHARE" \
        --azure-file-volume-mount-path /app/data \
        --output none

    log_success "Container deployed: $CONTAINER_NAME"
}

show_status() {
    log_info "Container status:"
    az container show \
        --name "$CONTAINER_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "{Name:name, Status:instanceView.state, StartTime:containers[0].instanceView.currentState.startTime}" \
        --output table
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
main() {
    log_info "=== UKG-TravelPerk Azure Deployment ==="
    log_info "Environment: $ENVIRONMENT"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Location: $LOCATION"
    log_info "========================================"

    check_azure_cli

    create_resource_group
    create_acr
    create_storage
    build_and_push_image
    deploy_container
    show_status

    log_success "=== Deployment Complete ==="
    log_info ""
    log_info "To run the container manually:"
    log_info "  az container start --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP"
    log_info ""
    log_info "To view logs:"
    log_info "  az container logs --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP --follow"
    log_info ""
    log_info "To set up scheduled execution, see: azure/scheduler-setup.md"
}

main "$@"
