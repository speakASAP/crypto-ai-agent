#!/bin/bash

# Crypto AI Agent - Development Start Script (Docker Compose)
# This script starts the backend, frontend, and all necessary services using Docker Compose
# This ensures the same environment as production for proper testing (WebSockets, etc.)
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
ACTION="start"

# Simple CLI parsing: [restart] [--service <name>]
while [[ $# -gt 0 ]]; do
    case "$1" in
        --service)
            shift
            SERVICE="$1"
            ;;
        restart)
            ACTION="restart"
            ;;
        start)
            ACTION="start"
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
LOG_DIR=${LOG_DIR:-logs}
DATA_DIR=${DATA_DIR:-data}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-crypto-ai-agent}

# Validate service name if provided
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

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Starting development environment with Docker Compose..."
print_status "This ensures the same setup as production for proper testing (WebSockets, etc.)"

print_status "Checking docker prerequisites..."
if ! command_exists docker; then
    print_error "Docker is not installed. Install Docker to run in development mode."
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    print_error "docker compose is not available. Install Docker Compose v2+."
    exit 1
fi
# Ensure Docker daemon is running; try to start it if not
if ! docker info >/dev/null 2>&1; then
    print_warning "Docker daemon not running. Attempting to start Docker..."
    UNAME=$(uname -s 2>/dev/null || echo "")
    if [ "$UNAME" = "Darwin" ]; then
        # macOS: start Docker Desktop
        if command_exists open; then
            print_status "Starting Docker Desktop..."
            open -g -a Docker || open -a Docker || true
        fi
    else
        # Linux: try systemd
        if command_exists systemctl; then
            print_status "Starting docker service via systemctl..."
            sudo systemctl start docker || true
        fi
    fi
    # Wait up to ~120s for Docker to be ready
    ATTEMPTS=0
    until docker info >/dev/null 2>&1; do
        ATTEMPTS=$((ATTEMPTS+1))
        if [ $ATTEMPTS -ge 60 ]; then
            print_error "Docker daemon did not start in time. Please start Docker and retry."
            exit 1
        fi
        sleep 2
    done
    print_success "Docker daemon is running"
fi
print_success "Docker prerequisites check passed"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found. Please create it from .env.example"
    exit 1
fi

# Check if JWT_SECRET is set
if ! grep -q "JWT_SECRET=" .env || grep -q "JWT_SECRET=your" .env; then
    print_warning "JWT_SECRET not properly configured in .env file"
    print_warning "Please update JWT_SECRET in .env file for security"
fi

mkdir -p $LOG_DIR
mkdir -p $DATA_DIR

# Create nginx-network if it doesn't exist (required by docker-compose.yml)
print_status "Checking for nginx-network..."
if ! docker network inspect nginx-network >/dev/null 2>&1; then
    print_status "Creating nginx-network..."
    docker network create nginx-network 2>/dev/null || print_warning "Network may already exist or creation failed (this is OK for local dev)"
else
    print_success "nginx-network exists"
fi

# Development via docker compose (same as production)
print_status "Using docker compose project: $COMPOSE_PROJECT_NAME"

if [ -n "$SERVICE" ]; then
    # Validate service name
    if ! is_valid_service "$SERVICE" "${VALID_SERVICES[@]}"; then
        print_error "Invalid service: $SERVICE (allowed: backend, frontend, postgres, redis)"
        exit 1
    fi
fi

if [ "$ACTION" = "restart" ]; then
    if [ -n "$SERVICE" ]; then
        print_status "Restarting service: $SERVICE"
        docker compose -p "$COMPOSE_PROJECT_NAME" restart "$SERVICE"
    else
        print_status "Restarting all services"
        docker compose -p "$COMPOSE_PROJECT_NAME" restart
    fi
else
    # Rebuild without cache to ensure latest code changes are included
    if [ -n "$SERVICE" ]; then
        print_status "Rebuilding service: $SERVICE (without cache)"
        docker compose -p "$COMPOSE_PROJECT_NAME" build --no-cache "$SERVICE"
        print_status "Starting service: $SERVICE"
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d "$SERVICE"
    else
        print_status "Rebuilding all services (without cache)"
        docker compose -p "$COMPOSE_PROJECT_NAME" build --no-cache
        print_status "Starting all services"
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d
    fi
fi

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 5

# Check service health
if [ -z "$SERVICE" ] || [ "$SERVICE" = "backend" ]; then
    print_status "Checking backend health..."
    ATTEMPTS=0
    while ! curl -s -f "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; do
        ATTEMPTS=$((ATTEMPTS+1))
        if [ $ATTEMPTS -ge 30 ]; then
            print_warning "Backend health check timed out, but service may still be starting..."
            break
        fi
        sleep 2
    done
    if curl -s -f "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
        print_success "Backend is healthy"
    fi
fi

if [ -z "$SERVICE" ] || [ "$SERVICE" = "frontend" ]; then
    print_status "Checking frontend health..."
    ATTEMPTS=0
    while ! curl -s -f "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; do
        ATTEMPTS=$((ATTEMPTS+1))
        if [ $ATTEMPTS -ge 30 ]; then
            print_warning "Frontend health check timed out, but service may still be starting..."
            break
        fi
        sleep 2
    done
    if curl -s -f "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
        print_success "Frontend is healthy"
    fi
fi

print_success "=========================================="
print_success "🚀 Crypto AI Agent (Development) started successfully!"
print_success "=========================================="
print_success "Backend:  http://localhost:$BACKEND_PORT"
print_success "Frontend: http://localhost:$FRONTEND_PORT"
print_success "API Docs: http://localhost:$BACKEND_PORT/docs"
print_success "=========================================="
print_status "Services are running in Docker Compose (same as production)"
print_status "Use ./stop_dev.sh to stop services or ./start_dev.sh restart to restart"
print_status "Use ./status_dev.sh to check service status"
print_status "Use 'docker compose -p $COMPOSE_PROJECT_NAME logs -f' to view logs"

