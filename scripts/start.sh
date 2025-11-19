#!/bin/bash

# Crypto AI Agent - Start Script
# This script starts the backend, frontend, and all necessary services
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

# Production mode - always use production environment
ENVIRONMENT="production"
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

# Use environment variables from .env file
# Align with docker-compose.yml naming convention
API_PORT=${API_PORT:-${BACKEND_PORT:-8100}}
FRONTEND_PORT=${FRONTEND_PORT:-3100}
LOG_DIR=${LOG_DIR:-logs}
DATA_DIR=${DATA_DIR:-data}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-crypto-ai-agent}

# Ensure API_PORT is exported for docker-compose.yml compatibility
export API_PORT
export FRONTEND_PORT

# Validate service name if provided
# Allow configuration from .env, otherwise use default list
VALID_SERVICES_PROD_STR=${VALID_SERVICES_PROD:-"backend frontend postgres redis"}
IFS=' ' read -ra VALID_SERVICES_PROD <<< "$VALID_SERVICES_PROD_STR"
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

# Function to check if a port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    if port_in_use $1; then
        print_warning "Port $1 is in use. Killing existing process..."
        lsof -ti :$1 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Check prerequisites
print_status "Production mode - starting services with Docker Compose"
print_status "Checking docker prerequisites..."
if ! command_exists docker; then
    print_error "Docker is not installed. Install Docker to run in production mode."
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
    # Wait up to ~120s for Docker to be ready (configurable via DOCKER_START_TIMEOUT)
    DOCKER_START_TIMEOUT=${DOCKER_START_TIMEOUT:-60}
    ATTEMPTS=0
    until docker info >/dev/null 2>&1; do
        ATTEMPTS=$((ATTEMPTS+1))
        if [ $ATTEMPTS -ge $DOCKER_START_TIMEOUT ]; then
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

# Production via docker compose
print_status "Using docker compose project: $COMPOSE_PROJECT_NAME"

if [ -n "$SERVICE" ]; then
    # Validate service name for prod
    if ! is_valid_service "$SERVICE" "${VALID_SERVICES_PROD[@]}"; then
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
    if [ -n "$SERVICE" ]; then
        print_status "Starting service: $SERVICE (docker compose up -d --build)"
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d --build "$SERVICE"
    else
        print_status "Starting all services (docker compose up -d --build)"
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d --build
    fi
fi

print_success "Services are up. Use ./status.sh for status."
