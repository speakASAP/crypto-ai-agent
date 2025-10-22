#!/bin/bash

# Crypto AI Agent Stop Script
# This script stops both the agent and UI dashboard

echo "🛑 Stopping Crypto AI Agent..."
echo "==============================="

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

# Stop agent processes
print_status "Stopping agent processes..."
if pgrep -f "agent_advanced.py" > /dev/null; then
    pkill -f "agent_advanced.py"
    print_success "Agent processes stopped"
else
    print_warning "No agent processes found"
fi

# Stop Streamlit UI processes
print_status "Stopping UI dashboard..."
if pgrep -f "streamlit.*ui_dashboard" > /dev/null; then
    pkill -f "streamlit.*ui_dashboard"
    print_success "UI dashboard stopped"
else
    print_warning "No UI dashboard processes found"
fi

# Stop any processes on port 8501
print_status "Checking port 8501..."
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8501 is still in use, forcing cleanup..."
    lsof -ti:8501 | xargs kill -9 2>/dev/null || true
    print_success "Port 8501 cleaned up"
else
    print_success "Port 8501 is free"
fi

# Wait a moment for processes to fully stop
sleep 2

# Verify everything is stopped
if pgrep -f "agent_advanced.py\|streamlit.*ui_dashboard" > /dev/null; then
    print_warning "Some processes may still be running. Force killing..."
    pkill -9 -f "agent_advanced.py\|streamlit.*ui_dashboard" 2>/dev/null || true
fi

print_success "Crypto AI Agent stopped successfully!"
echo ""
echo "📁 Logs are available in:"
echo "   - logs/agent.log"
echo "   - logs/ui.log"
echo ""
