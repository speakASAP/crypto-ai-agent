#!/bin/bash

# Crypto AI Agent Startup Script
# This script starts both the agent and UI dashboard

set -e  # Exit on any error

echo "🚀 Starting Crypto AI Agent..."
echo "=================================="

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

# Check for Python 3.12 (preferred) or fallback to python3
PYTHON_CMD=""
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    print_status "Using Python 3.12 (recommended for TensorFlow compatibility)"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    print_warning "Using Python 3 (may have TensorFlow compatibility issues)"
    print_warning "For best results, install Python 3.12"
else
    print_error "No Python 3 installation found"
    print_error "Please install Python 3.12 or Python 3"
    exit 1
fi


# Check if we're in the right directory
if [ ! -f "agent_advanced.py" ]; then
    print_error "Please run this script from the main project directory"
    print_error "Expected structure: agent_advanced.py"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_error "Please copy .env.example to .env and configure your API keys"
    exit 1
fi

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill processes on a port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ ! -z "$pids" ]; then
        print_warning "Killing existing processes on port $port..."
        echo $pids | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Check and clean up ports
print_status "Checking ports..."
if check_port 8501; then
    print_warning "Port 8501 is already in use (Streamlit UI)"
    kill_port 8501
fi

# Check if agent is already running
if pgrep -f "agent_advanced.py" > /dev/null; then
    print_warning "Agent is already running, stopping it..."
    pkill -f "agent_advanced.py" || true
    sleep 2
fi

# Create logs directory if it doesn't exist
mkdir -p logs

print_status "Starting Crypto AI Agent..."

# Start the agent in background
print_status "Launching agent process with $PYTHON_CMD..."
nohup $PYTHON_CMD agent_advanced.py > logs/agent.log 2>&1 &
AGENT_PID=$!

# Wait a moment for agent to start
sleep 3

# Check if agent started successfully
if ps -p $AGENT_PID > /dev/null; then
    print_success "Agent started successfully (PID: $AGENT_PID)"
else
    print_error "Failed to start agent. Check logs/agent.log for details."
    exit 1
fi

# Start the UI dashboard
print_status "Starting UI Dashboard with $PYTHON_CMD..."
nohup $PYTHON_CMD -m streamlit run ui_dashboard/app.py --server.port 8501 --server.headless true > logs/ui.log 2>&1 &
UI_PID=$!

# Wait for UI to start
print_status "Waiting for UI to start..."
for i in {1..30}; do
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        print_success "UI Dashboard is running!"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "UI failed to start after 30 seconds"
        print_error "Check logs/ui.log for details"
        exit 1
    fi
    sleep 1
done

# Print status
echo ""
echo "=================================="
print_success "Crypto AI Agent is now running!"
echo ""
echo "📊 UI Dashboard: http://localhost:8501"
echo "🤖 Agent PID: $AGENT_PID"
echo "🖥️  UI PID: $UI_PID"
echo ""
echo "📁 Logs:"
echo "   - Agent: logs/agent.log"
echo "   - UI: logs/ui.log"
echo ""
echo "🛑 To stop the services:"
echo "   ./stop.sh"
echo "   or"
echo "   kill $AGENT_PID $UI_PID"
echo ""
echo "Press Ctrl+C to stop this script (services will continue running)"
echo ""

# Function to handle cleanup on script exit
cleanup() {
    echo ""
    print_status "Stopping services..."
    kill $AGENT_PID $UI_PID 2>/dev/null || true
    print_success "Services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Keep script running and show status
while true; do
    if ! ps -p $AGENT_PID > /dev/null; then
        print_error "Agent process died! Check logs/agent.log"
        break
    fi
    if ! ps -p $UI_PID > /dev/null; then
        print_error "UI process died! Check logs/ui.log"
        break
    fi
    sleep 10
done

cleanup
