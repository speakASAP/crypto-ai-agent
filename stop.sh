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

print_status "Stopping Crypto AI Agent services..."

# Stop backend
print_status "Stopping Backend (FastAPI)..."
kill_pid "logs/backend.pid"
kill_port 8000

# Stop frontend
print_status "Stopping Frontend (Next.js)..."
kill_pid "logs/frontend.pid"
kill_port 3000

# Kill any remaining processes that might be related
print_status "Cleaning up any remaining processes..."

# Kill any uvicorn processes (including from virtual environment)
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "venv/bin/uvicorn" 2>/dev/null || true

# Kill any next.js processes
pkill -f "next dev" 2>/dev/null || true

# Kill any node processes running on our ports
for port in 3000 8000; do
    if port_in_use $port; then
        print_warning "Port $port still in use, force killing..."
        lsof -ti :$port | xargs kill -9 2>/dev/null || true
    fi
done

# Wait a moment for processes to fully stop
sleep 2

# Verify all ports are free
all_ports_free=true
for port in 3000 8000; do
    if port_in_use $port; then
        print_error "Port $port is still in use"
        all_ports_free=false
    fi
done

# Update status file
if [ -f "logs/status.txt" ]; then
    cat > logs/status.txt << EOF
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
    print_success "All ports (3000, 8000) are now free"
    print_success "=========================================="
else
    print_warning "Some processes may still be running"
    print_warning "You may need to manually kill them"
fi

# Clean up log files (optional)
read -p "Do you want to clean up log files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Cleaning up log files..."
    rm -f logs/backend.log logs/frontend.log logs/backend_install.log logs/frontend_install.log
    print_success "Log files cleaned up"
fi
