#!/bin/bash

# Crypto AI Agent v2.0 Deployment Script
# This script deploys the application to production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="crypto-ai-agent"
BACKUP_DIR="/backups/crypto-ai-agent"
LOG_FILE="/var/log/crypto-ai-agent-deploy.log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check if user is in docker group
    if ! groups $USER | grep -q '\bdocker\b'; then
        error "User $USER is not in the docker group. Please add user to docker group."
    fi
    
    success "Prerequisites check passed"
}

# Create backup
create_backup() {
    log "Creating backup of current deployment..."
    
    if [ -d "$BACKUP_DIR" ]; then
        # Create timestamped backup
        BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_PATH="$BACKUP_DIR/backup_$BACKUP_TIMESTAMP"
        
        mkdir -p "$BACKUP_PATH"
        
        # Backup database
        if docker ps | grep -q "crypto-agent-postgres"; then
            log "Backing up database..."
            docker exec crypto-agent-postgres pg_dump -U crypto_user crypto_agent > "$BACKUP_PATH/database.sql"
            success "Database backup created"
        fi
        
        # Backup application data
        if [ -d "./data" ]; then
            cp -r ./data "$BACKUP_PATH/"
            success "Application data backed up"
        fi
        
        success "Backup created at $BACKUP_PATH"
    else
        warning "Backup directory does not exist, skipping backup"
    fi
}

# Pull latest changes
pull_changes() {
    log "Pulling latest changes from repository..."
    
    if [ -d ".git" ]; then
        git fetch origin
        git reset --hard origin/main
        success "Latest changes pulled"
    else
        warning "Not a git repository, skipping git pull"
    fi
}

# Build and test
build_and_test() {
    log "Building and testing application..."
    
    # Run tests
    if [ -f "run_tests.py" ]; then
        log "Running test suite..."
        python3 run_tests.py
        success "Tests passed"
    else
        warning "Test script not found, skipping tests"
    fi
    
    # Build Docker images
    log "Building Docker images..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    success "Docker images built"
}

# Deploy application
deploy_application() {
    log "Deploying application..."
    
    # Stop existing containers
    log "Stopping existing containers..."
    docker-compose -f docker-compose.prod.yml down
    
    # Start new containers
    log "Starting new containers..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
}

# Check service health
check_service_health() {
    log "Checking service health..."
    
    # Check backend health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        success "Backend service is healthy"
    else
        error "Backend service is not responding"
    fi
    
    # Check frontend health
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        success "Frontend service is healthy"
    else
        error "Frontend service is not responding"
    fi
    
    # Check database connection
    if docker exec crypto-agent-postgres pg_isready -U crypto_user -d crypto_agent > /dev/null 2>&1; then
        success "Database is healthy"
    else
        error "Database is not responding"
    fi
    
    # Check Redis connection
    if docker exec crypto-agent-redis redis-cli ping > /dev/null 2>&1; then
        success "Redis is healthy"
    else
        error "Redis is not responding"
    fi
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Create monitoring script
    cat > monitor.sh << 'EOF'
#!/bin/bash
# Simple monitoring script for Crypto AI Agent

while true; do
    echo "=== Crypto AI Agent Status $(date) ==="
    
    # Check Docker containers
    echo "Docker Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Check service health
    echo -e "\nService Health:"
    echo -n "Backend: "
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Healthy"
    else
        echo "❌ Unhealthy"
    fi
    
    echo -n "Frontend: "
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Healthy"
    else
        echo "❌ Unhealthy"
    fi
    
    # Check performance metrics
    echo -e "\nPerformance Metrics:"
    curl -s http://localhost:8000/api/v2/performance/summary | jq '.uptime_seconds, .api_metrics, .system_metrics' 2>/dev/null || echo "Metrics not available"
    
    echo -e "\n" + "="*50 + "\n"
    sleep 60
done
EOF
    
    chmod +x monitor.sh
    success "Monitoring script created"
}

# Cleanup old images
cleanup() {
    log "Cleaning up old Docker images..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove old backups (keep last 5)
    if [ -d "$BACKUP_DIR" ]; then
        cd "$BACKUP_DIR"
        ls -t | tail -n +6 | xargs -r rm -rf
        success "Old backups cleaned up"
    fi
}

# Main deployment function
main() {
    log "Starting Crypto AI Agent v2.0 deployment..."
    
    check_root
    check_prerequisites
    create_backup
    pull_changes
    build_and_test
    deploy_application
    setup_monitoring
    cleanup
    
    success "Deployment completed successfully!"
    
    echo -e "\n${GREEN}🎉 Crypto AI Agent v2.0 is now deployed!${NC}"
    echo -e "\n${BLUE}Access URLs:${NC}"
    echo -e "  Frontend: http://localhost:3000"
    echo -e "  Backend API: http://localhost:8000"
    echo -e "  API Documentation: http://localhost:8000/docs"
    echo -e "  Performance Dashboard: http://localhost:8000/api/v2/performance/summary"
    
    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo -e "  View logs: docker-compose -f docker-compose.prod.yml logs -f"
    echo -e "  Stop services: docker-compose -f docker-compose.prod.yml down"
    echo -e "  Restart services: docker-compose -f docker-compose.prod.yml restart"
    echo -e "  Monitor status: ./monitor.sh"
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo -e "  1. Configure SSL certificates in nginx/ssl/"
    echo -e "  2. Update environment variables in .env"
    echo -e "  3. Set up domain name and DNS"
    echo -e "  4. Configure monitoring and alerting"
}

# Run main function
main "$@"
