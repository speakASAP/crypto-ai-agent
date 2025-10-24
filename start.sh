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
print_status "Checking prerequisites..."

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

print_success "Prerequisites check passed"

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

# Kill any existing processes on our ports
print_status "Cleaning up existing processes..."
kill_port 8000  # Backend port
kill_port 3000  # Frontend port

# Create logs directory if it doesn't exist
mkdir -p logs

# Start Backend
print_status "Starting Backend (FastAPI)..."
cd backend

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
print_status "Installing/updating Python dependencies..."
# Install compatible versions to avoid pydantic-core build issues
pip install "pydantic>=2.8.0" "pydantic-settings>=2.4.0" "passlib[bcrypt]==1.7.4" "python-jose[cryptography]==3.3.0" python-multipart==0.0.6 email-validator==2.1.0 fastapi uvicorn websockets httpx aiohttp python-dotenv psutil > ../logs/backend_install.log 2>&1

# Start backend in background using virtual environment
print_status "Starting FastAPI server on port 8000..."
nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid

# Wait for backend to start
print_status "Waiting for backend to start..."
sleep 5

# Check if backend is running
if ! port_in_use 8000; then
    print_error "Backend failed to start. Check logs/backend.log for details"
    exit 1
fi

print_success "Backend started successfully (PID: $BACKEND_PID)"

# Go back to root directory
cd ..

# Start Frontend
print_status "Starting Frontend (Next.js)..."
cd frontend

# Install/update dependencies
print_status "Installing/updating Node.js dependencies..."
npm install > ../logs/frontend_install.log 2>&1

# Start frontend in background
print_status "Starting Next.js server on port 3000..."
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid

# Wait for frontend to start
print_status "Waiting for frontend to start..."
sleep 10

# Check if frontend is running
if ! port_in_use 3000; then
    print_error "Frontend failed to start. Check logs/frontend.log for details"
    exit 1
fi

print_success "Frontend started successfully (PID: $FRONTEND_PID)"

# Go back to root directory
cd ..

# Create status file
cat > logs/status.txt << EOF
Crypto AI Agent Status
=====================
Started: $(date)
Backend PID: $BACKEND_PID
Frontend PID: $FRONTEND_PID
Backend URL: http://localhost:8000
Frontend URL: http://localhost:3000
API Docs: http://localhost:8000/docs
EOF

print_success "=========================================="
print_success "🚀 Crypto AI Agent started successfully!"
print_success "=========================================="
print_success "Backend:  http://localhost:8000"
print_success "Frontend: http://localhost:3000"
print_success "API Docs: http://localhost:8000/docs"
print_success "=========================================="
print_status "Logs are available in the logs/ directory"
print_status "Use ./stop.sh to stop all services"
print_status "Use ./status.sh to check service status"
