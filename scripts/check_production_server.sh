#!/bin/bash
# Production server status check script
# Run this on the production server: ssh statex && cd crypto-ai-agent && ./scripts/check_production_server.sh

set -e

echo "================================================================================"
echo "🔍 PRODUCTION SERVER STATUS CHECK"
echo "================================================================================"

# Check if in crypto-ai-agent directory
if [ ! -f "docker-compose.infrastructure.yml" ]; then
    echo "❌ ERROR: Not in crypto-ai-agent directory"
    echo "   Run: cd crypto-ai-agent"
    exit 1
fi

echo "✅ Current directory: $(pwd)"
echo ""

# Check Docker
echo "📦 Checking Docker..."
if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker not installed"
    exit 1
fi
echo "✅ Docker available: $(docker --version)"

# Check infrastructure containers
echo ""
echo "🗄️  Checking Infrastructure Containers..."
if docker ps --filter "name=crypto-ai-postgres" --format "{{.Names}}: {{.Status}}" | grep -q crypto-ai-postgres; then
    echo "✅ PostgreSQL container running:"
    docker ps --filter "name=crypto-ai-postgres" --format "   {{.Names}}: {{.Status}}"
    
    # Check health
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' crypto-ai-postgres 2>/dev/null || echo "unknown")
    echo "   Health status: $HEALTH"
else
    echo "❌ PostgreSQL container NOT running"
fi

if docker ps --filter "name=crypto-ai-redis" --format "{{.Names}}: {{.Status}}" | grep -q crypto-ai-redis; then
    echo "✅ Redis container running:"
    docker ps --filter "name=crypto-ai-redis" --format "   {{.Names}}: {{.Status}}"
else
    echo "⚠️  Redis container NOT running (optional)"
fi

# Check backend containers
echo ""
echo "🚀 Checking Backend Containers..."
BLUE_BACKEND=$(docker ps --filter "name=crypto-ai-backend-blue" --format "{{.Names}}" 2>/dev/null || echo "")
GREEN_BACKEND=$(docker ps --filter "name=crypto-ai-backend-green" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$BLUE_BACKEND" ]; then
    echo "✅ Blue backend running: $BLUE_BACKEND"
    echo "   Status: $(docker ps --filter "name=crypto-ai-backend-blue" --format "{{.Status}}")"
    
    # Check environment variables
    echo "   Environment check:"
    docker exec $BLUE_BACKEND env 2>/dev/null | grep -E "DATABASE_URL|ENVIRONMENT" | sed 's/\(.*PASSWORD.*\)/***/' || echo "   Could not check environment"
    
    # Check network
    echo "   Networks:"
    docker inspect $BLUE_BACKEND --format '   {{range $net, $conf := .NetworkSettings.Networks}}{{$net}} {{end}}' 2>/dev/null || echo "   Could not check networks"
    
    # Test database connection from container
    echo "   Database connection test:"
    docker exec $BLUE_BACKEND python3 -c "
from app.utils.db import connect_with_retry
try:
    conn = connect_with_retry(max_retries=1, initial_delay=0.5, max_delay=1.0, is_startup=False)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    count = cur.fetchone()[0]
    print(f'      ✅ Database accessible: {count} users')
    conn.close()
except Exception as e:
    print(f'      ❌ Database connection failed: {str(e)[:100]}')
" 2>/dev/null || echo "      ⚠️  Could not test database connection"
fi

if [ -n "$GREEN_BACKEND" ]; then
    echo "✅ Green backend running: $GREEN_BACKEND"
    echo "   Status: $(docker ps --filter "name=crypto-ai-backend-green" --format "{{.Status}}")"
fi

if [ -z "$BLUE_BACKEND" ] && [ -z "$GREEN_BACKEND" ]; then
    echo "❌ No backend containers running"
fi

# Check frontend containers
echo ""
echo "🎨 Checking Frontend Containers..."
BLUE_FRONTEND=$(docker ps --filter "name=crypto-ai-frontend-blue" --format "{{.Names}}" 2>/dev/null || echo "")
GREEN_FRONTEND=$(docker ps --filter "name=crypto-ai-frontend-green" --format "{{.Names}}" 2>/dev/null || echo "")

if [ -n "$BLUE_FRONTEND" ]; then
    echo "✅ Blue frontend running: $BLUE_FRONTEND"
fi
if [ -n "$GREEN_FRONTEND" ]; then
    echo "✅ Green frontend running: $GREEN_FRONTEND"
fi
if [ -z "$BLUE_FRONTEND" ] && [ -z "$GREEN_FRONTEND" ]; then
    echo "❌ No frontend containers running"
fi

# Check database directly
echo ""
echo "📊 Checking Production Database..."
if docker ps --filter "name=crypto-ai-postgres" | grep -q crypto-ai-postgres; then
    echo "   Connecting to database..."
    USER_COUNT=$(docker exec crypto-ai-postgres psql -U ${POSTGRES_USER:-crypto} -d ${POSTGRES_DB:-crypto_ai_agent} -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | xargs || echo "0")
    
    if [ "$USER_COUNT" != "0" ] && [ -n "$USER_COUNT" ]; then
        echo "   ✅ Database has $USER_COUNT customer account(s)"
        
        # Check your account
        YOUR_ACCOUNT=$(docker exec crypto-ai-postgres psql -U ${POSTGRES_USER:-crypto} -d ${POSTGRES_DB:-crypto_ai_agent} -t -c "SELECT COUNT(*) FROM users WHERE email = 'ssfskype@gmail.com';" 2>/dev/null | xargs || echo "0")
        if [ "$YOUR_ACCOUNT" != "0" ]; then
            echo "   ✅ Your account (ssfskype@gmail.com) found in database"
        else
            echo "   ⚠️  Your account (ssfskype@gmail.com) NOT found"
        fi
    else
        echo "   ❌ Database is EMPTY (0 users)"
    fi
fi

# Check network
echo ""
echo "🌐 Checking Docker Networks..."
if docker network ls | grep -q nginx-network; then
    echo "✅ nginx-network exists"
    
    # Check which containers are on the network
    echo "   Containers on nginx-network:"
    docker network inspect nginx-network --format '   {{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "   Could not inspect network"
else
    echo "❌ nginx-network NOT found"
fi

# Check backend logs for database errors
echo ""
echo "📋 Recent Backend Logs (database-related):"
if [ -n "$BLUE_BACKEND" ]; then
    echo "   Blue backend (last 20 lines with database/keywords):"
    docker logs --tail 50 $BLUE_BACKEND 2>&1 | grep -i "database\|connection\|error\|postgres" | tail -10 || echo "   No relevant logs"
fi

echo ""
echo "================================================================================"
echo "✅ STATUS CHECK COMPLETE"
echo "================================================================================"
echo ""
echo "🔍 Key Things to Verify:"
echo "   1. PostgreSQL container running and healthy"
echo "   2. Backend container running and on nginx-network"
echo "   3. Backend DATABASE_URL uses 'postgres' hostname"
echo "   4. Backend ENVIRONMENT=production"
echo "   5. Database has customer data (not empty)"
echo ""

