#!/bin/bash

# Crypto AI Agent - Status Script
# This script checks the status of backend, frontend, and all services
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

# Function to check if a port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to check if a process is running
process_running() {
    ps -p $1 > /dev/null 2>&1
}

# Function to get process info
get_process_info() {
    local port=$1
    if port_in_use $port; then
        local pid=$(lsof -ti :$port)
        local cmd=$(ps -p $pid -o comm= 2>/dev/null || echo "Unknown")
        local cpu=$(ps -p $pid -o %cpu= 2>/dev/null || echo "0")
        local mem=$(ps -p $pid -o %mem= 2>/dev/null || echo "0")
        echo "PID: $pid | Command: $cmd | CPU: ${cpu}% | Memory: ${mem}%"
    else
        echo "Not running"
    fi
}

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

print_status "Crypto AI Agent Status Check"
echo "=================================="

# Check if status file exists
if [ -f "logs/status.txt" ]; then
    echo
    print_status "Last known status:"
    cat logs/status.txt
    echo
fi

# Check Backend (Port 8000)
echo "Backend (FastAPI) - Port 8000:"
if port_in_use 8000; then
    print_success "✅ Running"
    echo "  $(get_process_info 8000)"
    
    # Check health
    if check_service_health "http://localhost:8000/health" "Backend"; then
        echo "  Health: ✅ Healthy"
    else
        echo "  Health: ❌ Unhealthy"
    fi
else
    print_error "❌ Not running"
fi

echo

# Check Frontend (Port 3000)
echo "Frontend (Next.js) - Port 3000:"
if port_in_use 3000; then
    print_success "✅ Running"
    echo "  $(get_process_info 3000)"
    
    # Check health
    if check_service_health "http://localhost:3000" "Frontend"; then
        echo "  Health: ✅ Healthy"
    else
        echo "  Health: ❌ Unhealthy"
    fi
else
    print_error "❌ Not running"
fi

echo

# Check Database
echo "Database (SQLite):"
if [ -f "data/crypto_portfolio.db" ]; then
    print_success "✅ Database file exists"
    db_size=$(du -h data/crypto_portfolio.db | cut -f1)
    echo "  Size: $db_size"
else
    print_warning "⚠️  Database file not found"
fi

echo

# Check Log Files
echo "Log Files:"
if [ -f "logs/backend.log" ]; then
    backend_log_size=$(du -h logs/backend.log | cut -f1)
    echo "  Backend log: ✅ Exists ($backend_log_size)"
else
    echo "  Backend log: ❌ Not found"
fi

if [ -f "logs/frontend.log" ]; then
    frontend_log_size=$(du -h logs/frontend.log | cut -f1)
    echo "  Frontend log: ✅ Exists ($frontend_log_size)"
else
    echo "  Frontend log: ❌ Not found"
fi

echo

# Check Environment
echo "Environment:"
if [ -f ".env" ]; then
    print_success "✅ .env file exists"
    
    # Check JWT_SECRET
    if grep -q "JWT_SECRET=" .env && ! grep -q "JWT_SECRET=your" .env; then
        print_success "✅ JWT_SECRET is configured"
    else
        print_warning "⚠️  JWT_SECRET needs to be configured"
    fi
else
    print_error "❌ .env file not found"
fi

echo

# Check Dependencies
echo "Dependencies:"
if [ -d "backend/venv" ]; then
    print_success "✅ Backend virtual environment exists"
    # Check if dependencies are installed in venv
    if backend/venv/bin/python -c "import fastapi, uvicorn, passlib, jose" 2>/dev/null; then
        print_success "✅ Backend Python dependencies installed in venv"
    else
        print_warning "⚠️  Backend Python dependencies missing in venv"
    fi
else
    print_warning "⚠️  Backend virtual environment not found"
fi

if [ -d "frontend/node_modules" ]; then
    print_success "✅ Frontend node_modules exists"
else
    print_warning "⚠️  Frontend node_modules not found"
fi

echo

# Summary
echo "Summary:"
backend_running=$(port_in_use 8000 && echo "true" || echo "false")
frontend_running=$(port_in_use 3000 && echo "true" || echo "false")

if [ "$backend_running" = "true" ] && [ "$frontend_running" = "true" ]; then
    print_success "🎉 All services are running!"
    echo
    echo "Access URLs:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
elif [ "$backend_running" = "true" ] || [ "$frontend_running" = "true" ]; then
    print_warning "⚠️  Some services are running, but not all"
    echo "  Use ./start.sh to start all services"
    echo "  Use ./stop.sh to stop all services"
else
    print_error "❌ No services are running"
    echo "  Use ./start.sh to start all services"
fi

echo
