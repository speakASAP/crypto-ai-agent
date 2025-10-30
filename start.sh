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

# Defaults and CLI overrides
ENVIRONMENT_DEFAULT="development"
SERVICE=""
ACTION="start"

# Simple CLI parsing: --env <env> [restart] [--service <name>]
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
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-crypto_ai_agent}
ENVIRONMENT=${ENVIRONMENT_OVERRIDE:-${ENVIRONMENT:-$ENVIRONMENT_DEFAULT}}

# Validate service name if provided
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
print_status "Selected environment: $ENVIRONMENT"

if [ "$ENVIRONMENT" = "production" ]; then
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
else
    print_status "Checking development prerequisites..."
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.12+"
        exit 1
    fi
    if ! command_exists node; then
        print_error "Node.js is not installed. Please install Node.js 18+"
        exit 1
    fi
    if ! command_exists npm; then
        print_error "npm is not installed. Please install npm"
        exit 1
    fi
    print_success "Development prerequisites check passed"
fi

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

if [ "$ENVIRONMENT" = "production" ]; then
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

    print_success "Services are up. Use ./status.sh --env production for status."
    exit 0
fi

# Development mode
# Kill any existing processes on our ports if starting (not restart-only)
print_status "Cleaning up existing processes..."
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

start_backend_dev() {
    print_status "Starting Backend (FastAPI)..."
    cd backend
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_status "Installing/updating Python dependencies..."
    pip install "pydantic>=2.8.0" "pydantic-settings>=2.4.0" "passlib[bcrypt]==1.7.4" "python-jose[cryptography]==3.3.0" python-multipart==0.0.6 email-validator==2.1.0 fastapi uvicorn websockets httpx aiohttp python-dotenv psutil > ../$LOG_DIR/backend_install.log 2>&1
    print_status "Starting FastAPI server on port $BACKEND_PORT..."
    nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload > ../$LOG_DIR/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../$LOG_DIR/backend.pid
    cd ..
    print_status "Waiting for backend to start..."
    sleep 5
    if ! port_in_use $BACKEND_PORT; then
        print_error "Backend failed to start. Check $LOG_DIR/backend.log for details"
        exit 1
    fi
    print_success "Backend started successfully (PID: $BACKEND_PID)"
}

start_frontend_dev() {
    print_status "Starting Frontend (Next.js)..."
    cd frontend
    print_status "Installing/updating Node.js dependencies..."
    npm install > ../$LOG_DIR/frontend_install.log 2>&1
    print_status "Starting Next.js server on port $FRONTEND_PORT..."
    nohup npm run dev > ../$LOG_DIR/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../$LOG_DIR/frontend.pid
    cd ..
    print_status "Waiting for frontend to start..."
    sleep 10
    if ! port_in_use $FRONTEND_PORT; then
        print_error "Frontend failed to start. Check $LOG_DIR/frontend.log for details"
        exit 1
    fi
    print_success "Frontend started successfully (PID: $FRONTEND_PID)"
}

if [ "$ACTION" = "restart" ]; then
    # restart in dev: stop then start specific service or all
    if [ -n "$SERVICE" ]; then
        if ! is_valid_service "$SERVICE" "${VALID_SERVICES_DEV[@]}"; then
            print_error "Invalid service: $SERVICE (allowed: backend, frontend)"
            exit 1
        fi
        print_status "Restarting $SERVICE (development)"
        if [ "$SERVICE" = "backend" ]; then
            lsof -ti :$BACKEND_PORT | xargs kill -9 2>/dev/null || true
            start_backend_dev
        else
            lsof -ti :$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
            start_frontend_dev
        fi
    else
        print_status "Restarting all services (development)"
        lsof -ti :$BACKEND_PORT | xargs kill -9 2>/dev/null || true
        lsof -ti :$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
        start_backend_dev
        start_frontend_dev
    fi
else
    # start in dev
    if [ -n "$SERVICE" ]; then
        if ! is_valid_service "$SERVICE" "${VALID_SERVICES_DEV[@]}"; then
            print_error "Invalid service: $SERVICE (allowed: backend, frontend)"
            exit 1
        fi
        if [ "$SERVICE" = "backend" ]; then
            start_backend_dev
        else
            start_frontend_dev
        fi
    else
        start_backend_dev
        start_frontend_dev
    fi
fi

# Create status file
cat > $LOG_DIR/status.txt << EOF
Crypto AI Agent Status
=====================
Started: $(date)
Backend URL: http://localhost:$BACKEND_PORT
Frontend URL: http://localhost:$FRONTEND_PORT
API Docs: http://localhost:$BACKEND_PORT/docs
EOF

print_success "=========================================="
print_success "Crypto AI Agent started successfully!"
print_success "=========================================="
print_success "Backend:  http://localhost:$BACKEND_PORT"
print_success "Frontend: http://localhost:$FRONTEND_PORT"
print_success "API Docs: http://localhost:$BACKEND_PORT/docs"
print_success "=========================================="
print_status "Logs are available in the $LOG_DIR/ directory"
print_status "Use ./stop.sh to stop services or ./start.sh restart to restart"
print_status "Use ./status.sh to check service status"
