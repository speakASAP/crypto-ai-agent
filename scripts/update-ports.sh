#!/bin/bash

# Crypto AI Agent - Update Ports Script
# This script updates the .env file to use 31xx ports
# Run this on both local and production environments

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

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

print_status "Updating ports in .env file..."
print_status "Project root: $PROJECT_ROOT"
print_status "Env file: $ENV_FILE"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found at $ENV_FILE"
    exit 1
fi

# Create backup
BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
print_success "Created backup: $BACKUP_FILE"

# Update ports in .env file
print_status "Updating port values..."

# Update API_PORT from 8100 to 3102
if grep -q "^API_PORT=8100" "$ENV_FILE"; then
    sed -i.bak 's/^API_PORT=8100/API_PORT=3102/' "$ENV_FILE"
    print_success "Updated API_PORT: 8100 → 3102"
elif grep -q "^API_PORT=" "$ENV_FILE"; then
    # If API_PORT exists but is not 8100, update it to 3102
    sed -i.bak 's/^API_PORT=.*/API_PORT=3102/' "$ENV_FILE"
    print_success "Updated API_PORT to 3102"
else
    # If API_PORT doesn't exist, add it
    echo "API_PORT=3102" >> "$ENV_FILE"
    print_success "Added API_PORT=3102"
fi

# Update API_PORT_GREEN from 8101 to 3103
if grep -q "^API_PORT_GREEN=8101" "$ENV_FILE"; then
    sed -i.bak 's/^API_PORT_GREEN=8101/API_PORT_GREEN=3103/' "$ENV_FILE"
    print_success "Updated API_PORT_GREEN: 8101 → 3103"
elif grep -q "^API_PORT_GREEN=" "$ENV_FILE"; then
    sed -i.bak 's/^API_PORT_GREEN=.*/API_PORT_GREEN=3103/' "$ENV_FILE"
    print_success "Updated API_PORT_GREEN to 3103"
else
    echo "API_PORT_GREEN=3103" >> "$ENV_FILE"
    print_success "Added API_PORT_GREEN=3103"
fi

# Update BACKEND_PORT from 8100 to 3102
if grep -q "^BACKEND_PORT=8100" "$ENV_FILE"; then
    sed -i.bak 's/^BACKEND_PORT=8100/BACKEND_PORT=3102/' "$ENV_FILE"
    print_success "Updated BACKEND_PORT: 8100 → 3102"
elif grep -q "^BACKEND_PORT=" "$ENV_FILE"; then
    sed -i.bak 's/^BACKEND_PORT=.*/BACKEND_PORT=3102/' "$ENV_FILE"
    print_success "Updated BACKEND_PORT to 3102"
else
    echo "BACKEND_PORT=3102" >> "$ENV_FILE"
    print_success "Added BACKEND_PORT=3102"
fi

# Update UI_PORT from 8501 to 3104
if grep -q "^UI_PORT=8501" "$ENV_FILE"; then
    sed -i.bak 's/^UI_PORT=8501/UI_PORT=3104/' "$ENV_FILE"
    print_success "Updated UI_PORT: 8501 → 3104"
elif grep -q "^UI_PORT=" "$ENV_FILE"; then
    sed -i.bak 's/^UI_PORT=.*/UI_PORT=3104/' "$ENV_FILE"
    print_success "Updated UI_PORT to 3104"
else
    echo "UI_PORT=3104" >> "$ENV_FILE"
    print_success "Added UI_PORT=3104"
fi

# Remove backup files created by sed
rm -f "${ENV_FILE}.bak"

# Verify changes
print_status "Verifying updated ports..."
echo ""
echo "Current port configuration:"
grep -E "^API_PORT=|^API_PORT_GREEN=|^BACKEND_PORT=|^UI_PORT=|^FRONTEND_PORT=" "$ENV_FILE" | sort
echo ""

print_success "Port update completed successfully!"
print_warning "Remember to restart services after updating ports:"
print_warning "  ./scripts/stop.sh"
print_warning "  ./scripts/start.sh"

