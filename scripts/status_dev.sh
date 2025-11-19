#!/bin/bash

# Crypto AI Agent - Development Status Script (Docker Compose)
# This script checks the status of backend, frontend, and all services running via Docker Compose
# There is .env file in root folder. Use ls -la .env and cat .env
# to see the current variables list.
# .env is Single Source of Truth for all variables.
# Update the codebase to use process.env.VARIABLE_NAME (or equivalent) instead of hardcoded values.

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

# CLI args: --service, --logs N
SERVICE=""
LOG_TAIL=50

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service)
            shift
            SERVICE="$1"
            ;;
        --logs)
            shift
            LOG_TAIL="$1"
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

# Function to check service health
check_service_health() {
    local url=$1
    local name=$2
    
    if curl -s -f "$url" > /dev/null 2>&1; then
        print_success "$name is healthy and responding"
        return 0
    else
        print_error "$name is not responding"
        return 1
    fi
}

print_status "Crypto AI Agent Status Check (development - Docker Compose)"
echo "=================================="

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    print_error "Docker or docker compose not available."
    exit 1
fi

print_status "Docker compose services (project: $COMPOSE_PROJECT_NAME):"
docker compose -p "$COMPOSE_PROJECT_NAME" ps

echo
print_status "Health checks:"
if curl -s -f "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    print_success "Backend port ${BACKEND_PORT} responsive"
else
    print_error "Backend port ${BACKEND_PORT} not responding"
fi
if curl -s -f "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1; then
    print_success "Frontend port ${FRONTEND_PORT} responsive"
else
    print_error "Frontend port ${FRONTEND_PORT} not responding"
fi

echo
print_status "Service details:"
if [ -n "$SERVICE" ]; then
    if [[ " ${VALID_SERVICES[@]} " =~ " ${SERVICE} " ]]; then
        print_status "Status of service: $SERVICE"
        docker compose -p "$COMPOSE_PROJECT_NAME" ps "$SERVICE"
        echo
        print_status "Recent logs (tail ${LOG_TAIL}):"
        docker compose -p "$COMPOSE_PROJECT_NAME" logs --tail ${LOG_TAIL} "$SERVICE"
    else
        print_error "Invalid service: $SERVICE (allowed: backend, frontend, postgres, redis)"
        exit 1
    fi
else
    print_status "Recent logs (tail ${LOG_TAIL}):"
    docker compose -p "$COMPOSE_PROJECT_NAME" logs --tail ${LOG_TAIL} backend frontend
fi

echo
print_status "Summary:"
backend_healthy=$(curl -s -f "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1 && echo "true" || echo "false")
frontend_healthy=$(curl -s -f "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 && echo "true" || echo "false")

if [ "$backend_healthy" = "true" ] && [ "$frontend_healthy" = "true" ]; then
    print_success "🎉 All services are running and healthy!"
    echo
    echo "Access URLs:"
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend:  http://localhost:$BACKEND_PORT"
    echo "  API Docs: http://localhost:$BACKEND_PORT/docs"
    echo "  WebSocket: ws://localhost:$BACKEND_PORT/ws"
elif [ "$backend_healthy" = "true" ] || [ "$frontend_healthy" = "true" ]; then
    print_warning "⚠️  Some services are running, but not all"
    echo "  Use ./start_dev.sh to start all services"
    echo "  Use ./stop_dev.sh to stop all services"
else
    print_error "❌ Services are not responding"
    echo "  Use ./start_dev.sh to start all services"
    echo "  Check logs: docker compose -p $COMPOSE_PROJECT_NAME logs"
fi
echo

