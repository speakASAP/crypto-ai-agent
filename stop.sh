#!/bin/bash

# Crypto AI Agent - Stop Script
# This script stops the backend, frontend, and all related processes
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
ENVIRONMENT_DEFAULT="development"
SERVICE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            shift
            ENVIRONMENT_OVERRIDE="$1"
            ;;
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
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
LOG_DIR=${LOG_DIR:-logs}
DATA_DIR=${DATA_DIR:-data}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-crypto_ai_agent}
ENVIRONMENT=${ENVIRONMENT_OVERRIDE:-${ENVIRONMENT:-$ENVIRONMENT_DEFAULT}}

VALID_SERVICES_DEV=(backend frontend)
VALID_SERVICES_PROD=(backend frontend postgres redis)
is_valid_service() {
    local name="$1"; shift
    for s in "$@"; do
        if [ "$s" = "$name" ]; then
            return 0
        fi
    done
    return 1
}

# Function to check if a port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to kill process by PID
kill_pid() {
    if [ -f "$1" ]; then
        local pid=$(cat "$1")
        if ps -p $pid > /dev/null 2>&1; then
            print_status "Stopping process with PID: $pid"
            kill $pid 2>/dev/null || true
            sleep 2
            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                print_warning "Force killing process with PID: $pid"
                kill -9 $pid 2>/dev/null || true
            fi
        fi
        rm -f "$1"
    fi
}

# Function to kill all processes on port
kill_port() {
    if port_in_use $1; then
        print_status "Stopping processes on port $1..."
        lsof -ti :$1 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

print_status "Selected environment: $ENVIRONMENT"

if [ "$ENVIRONMENT" = "production" ]; then
    print_status "Stopping services via docker compose (project: $COMPOSE_PROJECT_NAME)"
    if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
        print_error "Docker or docker compose not available."
        exit 1
    fi
    if [ -n "$SERVICE" ]; then
        if ! is_valid_service "$SERVICE" "${VALID_SERVICES_PROD[@]}"; then
            print_error "Invalid service: $SERVICE (allowed: backend, frontend, postgres, redis)"
            exit 1
        fi
        docker compose -p "$COMPOSE_PROJECT_NAME" stop "$SERVICE"
    else
        docker compose -p "$COMPOSE_PROJECT_NAME" down
    fi
else
    print_status "Stopping Crypto AI Agent services (development)..."
    if [ -n "$SERVICE" ]; then
        if ! is_valid_service "$SERVICE" "${VALID_SERVICES_DEV[@]}"; then
            print_error "Invalid service: $SERVICE (allowed: backend, frontend)"
            exit 1
        fi
    fi

    if [ -z "$SERVICE" ] || [ "$SERVICE" = "backend" ]; then
        print_status "Stopping Backend (FastAPI)..."
        kill_pid "$LOG_DIR/backend.pid"
        kill_port $BACKEND_PORT
        pkill -f "uvicorn app.main:app" 2>/dev/null || true
        pkill -f "venv/bin/uvicorn" 2>/dev/null || true
    fi

    if [ -z "$SERVICE" ] || [ "$SERVICE" = "frontend" ]; then
        print_status "Stopping Frontend (Next.js)..."
        kill_pid "$LOG_DIR/frontend.pid"
        kill_port $FRONTEND_PORT
        pkill -f "next dev" 2>/dev/null || true
    fi

    # Kill any node/uvicorn still bound
    for port in $FRONTEND_PORT $BACKEND_PORT; do
        if port_in_use $port; then
            print_warning "Port $port still in use, force killing..."
            lsof -ti :$port | xargs kill -9 2>/dev/null || true
        fi
    done
fi

# Wait a moment for processes to fully stop
sleep 2

# Verify all ports are free
all_ports_free=true
for port in $FRONTEND_PORT $BACKEND_PORT; do
    if port_in_use $port; then
        print_error "Port $port is still in use"
        all_ports_free=false
    fi
done

# Update status file
if [ -f "$LOG_DIR/status.txt" ]; then
    cat > $LOG_DIR/status.txt << EOF
Crypto AI Agent Status
=====================
Stopped: $(date)
Backend: Stopped
Frontend: Stopped
EOF
fi

if [ "$all_ports_free" = true ]; then
    print_success "=========================================="
    print_success "🛑 Crypto AI Agent stopped successfully!"
    print_success "=========================================="
    print_success "All services have been stopped"
    print_success "All ports ($FRONTEND_PORT, $BACKEND_PORT) are now free"
    print_success "=========================================="
else
    print_warning "Some processes may still be running"
    print_warning "You may need to manually kill them"
fi

# Clean up log files
print_status "Cleaning up log files..."
rm -f $LOG_DIR/backend.log $LOG_DIR/frontend.log $LOG_DIR/backend_install.log $LOG_DIR/frontend_install.log
print_success "Log files cleaned up"
