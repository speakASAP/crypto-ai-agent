#!/bin/bash

# =============================================================================
# Crypto AI Agent - Application Stop Script
# =============================================================================
# This script stops both the AI agent and the Streamlit UI dashboard
# Author: Crypto AI Agent Team
# Version: 1.0
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Print colored output
print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}🛑 CRYPTO AI AGENT - STOP SCRIPT${NC}"
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

# Check if a process is running
is_process_running() {
    local process_name=$1
    pgrep -f "$process_name" > /dev/null 2>&1
}

# Get process count
get_process_count() {
    local process_name=$1
    pgrep -f "$process_name" | wc -l
}

# Kill processes by name
kill_processes() {
    local process_name=$1
    local service_name=$2
    local count=$(get_process_count "$process_name")
    
    if [ $count -gt 0 ]; then
        print_status "Stopping $service_name ($count processes)..."
        pkill -f "$process_name"
        sleep 2
        
        # Force kill if still running
        if is_process_running "$process_name"; then
            print_warning "Force killing $service_name..."
            pkill -9 -f "$process_name" 2>/dev/null || true
        fi
        
        print_success "$service_name stopped"
    else
        print_warning "No $service_name processes found"
    fi
}

# Main execution
print_header

print_status "Stopping Crypto AI Agent application..."

# Stop AI Agent processes
kill_processes "agent_advanced.py" "AI Agent"

# Stop UI Dashboard processes
kill_processes "streamlit.*ui_dashboard" "UI Dashboard"

# Stop any processes on port 8501
print_status "Checking port 8501..."
if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 8501 is still in use, cleaning up..."
    lsof -ti:8501 | xargs kill -9 2>/dev/null || true
    print_success "Port 8501 cleaned up"
else
    print_success "Port 8501 is free"
fi

# Wait for processes to fully stop
sleep 2

# Final verification
print_status "Verifying shutdown..."

agent_running=$(get_process_count "agent_advanced.py")
ui_running=$(get_process_count "streamlit.*ui_dashboard")
port_in_use=$(lsof -Pi :8501 -sTCP:LISTEN -t 2>/dev/null | wc -l)

if [ $agent_running -eq 0 ] && [ $ui_running -eq 0 ] && [ $port_in_use -eq 0 ]; then
    print_success "Crypto AI Agent stopped successfully!"
    echo ""
    echo -e "${GREEN}✅ All processes stopped${NC}"
    echo -e "${GREEN}✅ Port 8501 is free${NC}"
    echo -e "${GREEN}✅ Application shutdown complete${NC}"
else
    print_warning "Some processes may still be running:"
    [ $agent_running -gt 0 ] && echo -e "   ${YELLOW}⚠️  AI Agent: $agent_running processes${NC}"
    [ $ui_running -gt 0 ] && echo -e "   ${YELLOW}⚠️  UI Dashboard: $ui_running processes${NC}"
    [ $port_in_use -gt 0 ] && echo -e "   ${YELLOW}⚠️  Port 8501: $port_in_use processes${NC}"
fi

echo ""
echo -e "${BLUE}📁 Log files are available in:${NC}"
echo -e "   📋 Agent Logs: ${GREEN}logs/agent.log${NC}"
echo -e "   🖥️  UI Logs:    ${GREEN}logs/ui.log${NC}"
echo ""
echo -e "${BLUE}🚀 To restart the application:${NC}"
echo -e "   Run: ${GREEN}./start_app.sh${NC}"
echo ""
