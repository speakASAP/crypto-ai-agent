#!/bin/bash

# Crypto AI Agent - Development Stop Script (Docker Compose)
# This script stops the backend, frontend, and all related services using Docker Compose
# There is .env file in root folder. Use ls -la .env and cat .env
# to see the current variables list.
# .env is Single Source of Truth for all variables.
# Update the codebase to use process.env.VARIABLE_NAME (or equivalent) instead of hardcoded values.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Load environment variables from .env file
if [ -f ".env" ]; then
    # Use source to safely load environment variables
    set -a  # automatically export all variables
    source .env
    set +a  # stop automatically exporting
    print_status "Environment variables loaded from .env file"
else
    print_error ".env file not found!"
    exit 1
fi

# Defaults and CLI overrides
SERVICE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service)
            shift
            SERVICE="$1"
            ;;
        *)
            print_warning "Unknown argument: $1"
            ;;
    esac
    shift || true
done

# Set default values if not provided
BACKEND_PORT=${BACKEND_PORT:-8100}
FRONTEND_PORT=${FRONTEND_PORT:-3100}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-crypto-ai-agent}

VALID_SERVICES=(backend frontend postgres redis)
is_valid_service() {
    local name="$1"; shift
    for s in "$@"; do
        if [ "$s" = "$name" ]; then
            return 0
        fi
    done
    return 1
}

print_status "Stopping Crypto AI Agent services (development - Docker Compose)..."

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    print_error "Docker or docker compose not available."
    exit 1
fi

if [ -n "$SERVICE" ]; then
    if ! is_valid_service "$SERVICE" "${VALID_SERVICES[@]}"; then
        print_error "Invalid service: $SERVICE (allowed: backend, frontend, postgres, redis)"
        exit 1
    fi
    print_status "Stopping service: $SERVICE"
    docker compose -p "$COMPOSE_PROJECT_NAME" stop "$SERVICE"
    print_success "Service $SERVICE stopped"
else
    print_status "Stopping all services via docker compose (project: $COMPOSE_PROJECT_NAME)"
    docker compose -p "$COMPOSE_PROJECT_NAME" down
fi

# Wait a moment for processes to fully stop
sleep 2

# Verify ports are free (for services that were stopped)
if [ -z "$SERVICE" ]; then
    # Check if ports are still in use
    port_in_use() {
        lsof -i :$1 >/dev/null 2>&1
    }

    all_ports_free=true
    for port in $FRONTEND_PORT $BACKEND_PORT; do
        if port_in_use $port; then
            print_warning "Port $port is still in use"
            all_ports_free=false
        fi
    done

    if [ "$all_ports_free" = true ]; then
        print_success "=========================================="
        print_success "🛑 Crypto AI Agent stopped successfully!"
        print_success "=========================================="
        print_success "All services have been stopped"
        print_success "All ports ($FRONTEND_PORT, $BACKEND_PORT) are now free"
        print_success "=========================================="
    else
        print_warning "Some ports may still be in use"
        print_warning "Docker containers should be stopped, but ports may be held by other processes"
    fi
else
    print_success "=========================================="
    print_success "🛑 Service $SERVICE stopped successfully!"
    print_success "=========================================="
fi

