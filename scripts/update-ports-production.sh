#!/bin/bash

# Crypto AI Agent - Update Ports on Production Server
# This script updates the .env file on production server via SSH
# Usage: ./scripts/update-ports-production.sh [user@host]

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

# Default production server (adjust as needed)
PROD_SERVER="${1:-statex}"
PROD_PATH="/home/statex/crypto-ai-agent"

print_status "Updating ports on production server: $PROD_SERVER"
print_status "Production path: $PROD_PATH"

# Check if SSH connection works
print_status "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "$PROD_SERVER" "echo 'Connection successful'" > /dev/null 2>&1; then
    print_error "Cannot connect to $PROD_SERVER"
    print_error "Please check your SSH configuration and try again"
    exit 1
fi

print_success "SSH connection successful"

# Create remote update script
REMOTE_SCRIPT=$(cat <<'REMOTE_EOF'
#!/bin/bash
set -e

ENV_FILE="/home/statex/crypto-ai-agent/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

# Create backup
BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
echo "Created backup: $BACKUP_FILE"

# Update ports
sed -i.bak 's/^API_PORT=8100/API_PORT=3102/' "$ENV_FILE" 2>/dev/null || sed -i.bak 's/^API_PORT=.*/API_PORT=3102/' "$ENV_FILE" || echo "API_PORT=3102" >> "$ENV_FILE"
sed -i.bak 's/^API_PORT_GREEN=8101/API_PORT_GREEN=3103/' "$ENV_FILE" 2>/dev/null || sed -i.bak 's/^API_PORT_GREEN=.*/API_PORT_GREEN=3103/' "$ENV_FILE" || echo "API_PORT_GREEN=3103" >> "$ENV_FILE"
sed -i.bak 's/^BACKEND_PORT=8100/BACKEND_PORT=3102/' "$ENV_FILE" 2>/dev/null || sed -i.bak 's/^BACKEND_PORT=.*/BACKEND_PORT=3102/' "$ENV_FILE" || echo "BACKEND_PORT=3102" >> "$ENV_FILE"
sed -i.bak 's/^UI_PORT=8501/UI_PORT=3104/' "$ENV_FILE" 2>/dev/null || sed -i.bak 's/^UI_PORT=.*/UI_PORT=3104/' "$ENV_FILE" || echo "UI_PORT=3104" >> "$ENV_FILE"

# Remove backup files
rm -f "${ENV_FILE}.bak"

# Show updated ports
echo ""
echo "Updated port configuration:"
grep -E "^API_PORT=|^API_PORT_GREEN=|^BACKEND_PORT=|^UI_PORT=|^FRONTEND_PORT=" "$ENV_FILE" | sort
echo ""
echo "SUCCESS: Ports updated successfully"
REMOTE_EOF
)

# Execute remote script
print_status "Executing port update on production server..."
ssh "$PROD_SERVER" "cd $PROD_PATH && bash -s" <<< "$REMOTE_SCRIPT"

if [ $? -eq 0 ]; then
    print_success "Ports updated successfully on production server!"
    print_warning "Remember to restart services on production:"
    print_warning "  ssh $PROD_SERVER 'cd $PROD_PATH && ./scripts/stop.sh'"
    print_warning "  ssh $PROD_SERVER 'cd $PROD_PATH && ./scripts/start.sh'"
else
    print_error "Failed to update ports on production server"
    exit 1
fi

