#!/bin/bash
# Database connectivity check script for blue/green deployments
# This script verifies database is available and contains customer data
# Usage: ./scripts/check_database.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Docker environment
if [ -f /.dockerenv ]; then
    CONTAINER_NAME="crypto-ai-postgres"
    NETWORK="nginx-network"
else
    CONTAINER_NAME="crypto-ai-postgres"
    NETWORK="nginx-network"
fi

echo "🔍 Checking database connectivity..."

# Check if postgres container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}❌ ERROR: PostgreSQL container '$CONTAINER_NAME' is not running${NC}"
    exit 1
fi

echo "✅ PostgreSQL container is running"

# Check container health
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")

if [ "$HEALTH_STATUS" = "healthy" ]; then
    echo "✅ PostgreSQL container is healthy"
elif [ "$HEALTH_STATUS" = "starting" ]; then
    echo -e "${YELLOW}⚠️  WARNING: PostgreSQL container is still starting${NC}"
    echo "⏳ Waiting for database to be ready..."
    
    # Wait up to 60 seconds for health check
    MAX_WAIT=60
    ELAPSED=0
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        if [ "$HEALTH_STATUS" = "healthy" ]; then
            echo "✅ PostgreSQL container is now healthy"
            break
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
        echo "   Waiting... ($ELAPSED/$MAX_WAIT seconds)"
    done
    
    if [ "$HEALTH_STATUS" != "healthy" ]; then
        echo -e "${RED}❌ ERROR: PostgreSQL container did not become healthy within $MAX_WAIT seconds${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  WARNING: PostgreSQL container health status: $HEALTH_STATUS${NC}"
fi

# Try to connect to database using pg_isready
echo "🔍 Testing database connection..."
if docker exec "$CONTAINER_NAME" pg_isready -U "${POSTGRES_USER:-crypto}" -d "${POSTGRES_DB:-crypto_ai_agent}" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo -e "${RED}❌ ERROR: Cannot connect to database${NC}"
    exit 1
fi

# Check if database has data (users table with records)
echo "🔍 Verifying database has customer data..."
USER_COUNT=$(docker exec "$CONTAINER_NAME" psql -U "${POSTGRES_USER:-crypto}" -d "${POSTGRES_DB:-crypto_ai_agent}" -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | xargs || echo "0")

if [ -z "$USER_COUNT" ] || [ "$USER_COUNT" = "0" ]; then
    echo -e "${RED}❌ ERROR: Database exists but has no customer data (0 users found)${NC}"
    echo -e "${RED}❌ Deployment should NOT proceed if database is empty${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Database verification complete${NC}"
echo "   ✓ PostgreSQL container is running and healthy"
echo "   ✓ Database connection successful"
echo "   ✓ Database contains customer data: $USER_COUNT users"
echo ""
echo "✅ Database is ready for blue/green deployment"

exit 0

