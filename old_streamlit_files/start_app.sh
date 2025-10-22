#!/bin/bash

# =============================================================================
# Crypto AI Agent - Application Startup Script
# =============================================================================
# This script starts both the AI agent and the Streamlit UI dashboard
# Author: Crypto AI Agent Team
# Version: 1.0
# =============================================================================

set -e  # Exit on any error

# =============================================================================
# CONFIGURATION
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Application settings
UI_PORT=8501
AGENT_SCRIPT="agent_advanced.py"
UI_SCRIPT="ui_dashboard/app.py"

# Detect Python command (prefer Python 3.12, fallback to python3)
PYTHON_CMD=""
if command_exists python3.12; then
    PYTHON_CMD="python3.12"
elif command_exists python3; then
    PYTHON_CMD="python3"
else
    print_error "No Python 3 installation found"
    print_error "Please install Python 3.12 or Python 3"
    exit 1
fi

# =============================================================================
# FUNCTIONS
# =============================================================================

# Print colored output
print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}🚀 CRYPTO AI AGENT - STARTUP SCRIPT${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
    echo ""
}

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

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if a port is in use
is_port_in_use() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Kill processes on a specific port
kill_port_processes() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pids" ]; then
        print_warning "Killing existing processes on port $port..."
        echo $pids | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Check if a process is running
is_process_running() {
    local process_name=$1
    pgrep -f "$process_name" > /dev/null 2>&1
}

# Wait for a service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to start..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_error "$service_name failed to start after $max_attempts seconds"
            return 1
        fi
        
        echo -n "."
        sleep 1
        ((attempt++))
    done
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

print_header

# Step 1: Pre-flight checks
print_step "1. Running pre-flight checks..."

# Check Python availability
print_success "Using $PYTHON_CMD: $($PYTHON_CMD --version)"


# Check if we're in the right directory
if [ ! -f "$AGENT_SCRIPT" ]; then
    print_error "Please run this script from the main project directory"
    print_error "Expected structure: $AGENT_SCRIPT"
    exit 1
fi
print_success "Project structure verified"

# Check .env file
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_error "Please copy .env.example to .env and configure your API keys"
    exit 1
fi
print_success ".env file found"

# Step 2: Cleanup existing processes
print_step "2. Cleaning up existing processes..."

# Stop existing agent processes
if is_process_running "agent_advanced.py"; then
    print_warning "Stopping existing agent processes..."
    pkill -f "agent_advanced.py" || true
    sleep 2
fi

# Stop existing UI processes
if is_process_running "streamlit.*ui_dashboard"; then
    print_warning "Stopping existing UI processes..."
    pkill -f "streamlit.*ui_dashboard" || true
    sleep 2
fi

# Clean up ports
if is_port_in_use $UI_PORT; then
    kill_port_processes $UI_PORT
fi

print_success "Cleanup completed"

# Step 3: Create necessary directories
print_step "3. Setting up directories..."

mkdir -p logs
print_success "Directories created"

# Step 4: Start the AI Agent
print_step "4. Starting AI Agent..."

# Start agent in background
print_status "Launching AI agent process..."
nohup $PYTHON_CMD $AGENT_SCRIPT > logs/agent.log 2>&1 &
AGENT_PID=$!

# Wait for agent to start
sleep 3

# Check if agent started successfully
if ps -p $AGENT_PID > /dev/null; then
    print_success "AI Agent started successfully (PID: $AGENT_PID)"
else
    print_error "Failed to start AI Agent. Check logs/agent.log for details."
    exit 1
fi

# Step 5: Start the UI Dashboard
print_step "5. Starting UI Dashboard..."

# Start UI in background
print_status "Launching UI dashboard process..."
nohup $PYTHON_CMD -m streamlit run $UI_SCRIPT --server.port $UI_PORT --server.headless true > logs/ui.log 2>&1 &
UI_PID=$!

# Wait for UI to be ready
if ! wait_for_service "http://localhost:$UI_PORT" "UI Dashboard"; then
    print_error "UI Dashboard failed to start. Check logs/ui.log for details."
    kill $AGENT_PID 2>/dev/null || true
    exit 1
fi

# Step 6: Display status and information
print_step "6. Application Status"

echo ""
echo -e "${GREEN}🎉 CRYPTO AI AGENT IS NOW RUNNING! 🎉${NC}"
echo ""
echo -e "${CYAN}📊 Access Points:${NC}"
echo -e "   🌐 UI Dashboard: ${GREEN}http://localhost:$UI_PORT${NC}"
echo -e "   📱 Mobile URL:   ${GREEN}http://$(hostname -I | awk '{print $1}'):$UI_PORT${NC}"
echo ""
echo -e "${CYAN}🔧 Process Information:${NC}"
echo -e "   🤖 AI Agent PID: ${GREEN}$AGENT_PID${NC}"
echo -e "   🖥️  UI Dashboard PID: ${GREEN}$UI_PID${NC}"
echo ""
echo -e "${CYAN}📁 Log Files:${NC}"
echo -e "   📋 Agent Logs: ${GREEN}logs/agent.log${NC}"
echo -e "   🖥️  UI Logs:    ${GREEN}logs/ui.log${NC}"
echo ""
echo -e "${CYAN}🛑 To Stop the Application:${NC}"
echo -e "   Run: ${YELLOW}./stop_app.sh${NC}"
echo -e "   Or:  ${YELLOW}kill $AGENT_PID $UI_PID${NC}"
echo ""

# Step 7: Open browser (optional)
if command_exists open; then
    print_status "Opening browser..."
    open "http://localhost:$UI_PORT" &
    print_success "Browser opened"
fi

# Step 8: Monitor processes
print_step "7. Monitoring processes..."

# Function to handle cleanup on script exit
cleanup() {
    echo ""
    print_warning "Stopping application..."
    kill $AGENT_PID $UI_PID 2>/dev/null || true
    print_success "Application stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

print_status "Application is running. Press Ctrl+C to stop monitoring (services will continue running)."
echo ""

# Monitor processes
while true; do
    if ! ps -p $AGENT_PID > /dev/null; then
        print_error "AI Agent process died! Check logs/agent.log"
        break
    fi
    if ! ps -p $UI_PID > /dev/null; then
        print_error "UI Dashboard process died! Check logs/ui.log"
        break
    fi
    sleep 10
done

cleanup
