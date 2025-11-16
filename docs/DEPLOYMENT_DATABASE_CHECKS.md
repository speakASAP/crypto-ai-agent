# Database Connectivity Checks for Blue/Green Deployment

## Overview

During blue/green deployments, the database **MUST** be available and contain customer data at all times. The deployment scripts should verify database connectivity before switching traffic.

## Critical Requirements

1. **Database MUST be available** - Never deploy if database is unavailable
2. **Database MUST have customer data** - Never deploy if database is empty (no users)
3. **NEVER create tables during deployment** - Database schema already exists with thousands of customer accounts
4. **Verify database before switching traffic** - Both blue and green must be able to access the database

## Implementation

### 1. Application-Level Checks

The application now includes:

#### Health Endpoint (`/health`)

- Verifies database connectivity
- Checks if database has customer data (users table with records)
- Returns 503 (Service Unavailable) if database is unavailable or empty
- **Deployment scripts should check this endpoint before switching traffic**

**Health Check Response:**

```json
{
  "status": "healthy",
  "database": "postgres",
  "database_connected": true,
  "database_has_data": true,
  "user_count": 1234,
  "version": "2.0.0",
  "websocket_connections": 0
}
```

#### Database Initialization

- **NEVER creates tables if database is not available**
- **NEVER creates tables if database already has customer data**
- Only creates tables if database is completely new (no schema exists)
- Verifies database connection before any table operations

### 2. Deployment Script Checks

The deployment script should verify database connectivity **before** switching traffic.

#### Option 1: Check Health Endpoint (Recommended)

Before switching traffic, check the health endpoint of both blue and green:

```bash
# Check blue health
BLUE_HEALTH=$(curl -s http://localhost:8100/health || echo "unhealthy")
if echo "$BLUE_HEALTH" | grep -q '"status":"healthy"'; then
    echo "✅ Blue instance is healthy"
else
    echo "❌ Blue instance is unhealthy - aborting deployment"
    exit 1
fi

# Check green health (after starting)
GREEN_HEALTH=$(curl -s http://localhost:8101/health || echo "unhealthy")
if echo "$GREEN_HEALTH" | grep -q '"status":"healthy"'; then
    echo "✅ Green instance is healthy"
else
    echo "❌ Green instance is unhealthy - aborting deployment"
    exit 1
fi

# Verify both have database access
BLUE_HAS_DATA=$(echo "$BLUE_HEALTH" | grep -o '"database_has_data":true' || echo "")
GREEN_HAS_DATA=$(echo "$GREEN_HEALTH" | grep -o '"database_has_data":true' || echo "")

if [ -z "$BLUE_HAS_DATA" ] || [ -z "$GREEN_HAS_DATA" ]; then
    echo "❌ Database is not accessible or has no data - aborting deployment"
    exit 1
fi
```

#### Option 2: Direct Database Check Script

Use the provided database check script:

```bash
# From nginx-microservice directory or crypto-ai-agent directory
cd /path/to/crypto-ai-agent
./scripts/check_database.sh

# If script exits with 0, database is ready
# If script exits with non-zero, abort deployment
```

### 3. Adding Database Checks to Deployment Script

#### Modify `prepare-green.sh`

Add database check **before** starting green containers:

```bash
# In prepare-green.sh, before starting containers:

# Step 1: Check database is available
echo "[INFO] Verifying database connectivity..."
cd "$SERVICE_PATH"
if ! ./scripts/check_database.sh; then
    echo "[ERROR] Database is not available. Aborting deployment."
    exit 1
fi

# Step 2: Start green containers
# ... existing container startup code ...

# Step 3: After containers start, verify green can access database
echo "[INFO] Verifying green instance can access database..."
MAX_RETRIES=10
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    GREEN_HEALTH=$(curl -s http://localhost:${API_PORT_GREEN:-8101}/health 2>/dev/null || echo "")
    if echo "$GREEN_HEALTH" | grep -q '"database_has_data":true'; then
        echo "[INFO] ✅ Green instance can access database"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "[INFO] Waiting for green instance database access... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "[ERROR] Green instance cannot access database after $MAX_RETRIES retries"
    exit 1
fi
```

#### Modify `switch-traffic.sh`

Add database check **before** switching traffic:

```bash
# In switch-traffic.sh, before updating nginx:

# Verify blue instance still has database access (critical!)
echo "[INFO] Verifying blue instance database access before switching..."
BLUE_HEALTH=$(curl -s http://localhost:${API_PORT:-8100}/health 2>/dev/null || echo "")
if ! echo "$BLUE_HEALTH" | grep -q '"database_has_data":true'; then
    echo "[ERROR] Blue instance lost database access. Aborting traffic switch."
    exit 1
fi

# Verify green instance has database access
echo "[INFO] Verifying green instance database access..."
GREEN_HEALTH=$(curl -s http://localhost:${API_PORT_GREEN:-8101}/health 2>/dev/null || echo "")
if ! echo "$GREEN_HEALTH" | grep -q '"database_has_data":true'; then
    echo "[ERROR] Green instance does not have database access. Aborting traffic switch."
    exit 1
fi

echo "[INFO] ✅ Both instances have database access. Proceeding with traffic switch."
```

## Deployment Workflow with Database Checks

```text
1. Start deployment
   ↓
2. Check database is available (using check_database.sh or health endpoint)
   ├─ ❌ If unavailable → ABORT deployment
   └─ ✅ If available → Continue
   ↓
3. Start green containers
   ↓
4. Wait for green containers to be ready
   ↓
5. Verify green instance can access database (health endpoint)
   ├─ ❌ If cannot access → ABORT deployment, cleanup green
   └─ ✅ If can access → Continue
   ↓
6. Verify blue instance still has database access
   ├─ ❌ If lost access → ABORT deployment (database issue)
   └─ ✅ If has access → Continue
   ↓
7. Switch traffic to green
   ↓
8. Monitor green instance database access
   ├─ ❌ If loses access → Rollback immediately
   └─ ✅ If maintains access → Continue monitoring
   ↓
9. Cleanup blue (after successful monitoring period)
```

## Safety Measures

### Application Safety

1. **Never creates tables if database unavailable**
   - `init_postgres_database()` verifies connection first
   - Returns early if database is unavailable
   - Logs error but doesn't crash application

2. **Never creates tables if database has data**
   - Checks if `users` table exists and has records
   - Skips table creation if data exists
   - Protects existing customer data

3. **Health endpoint requires database AND data**
   - Returns 503 if database is unavailable
   - Returns 503 if database has no data
   - Deployment scripts can rely on this

### Deployment Safety

1. **Pre-flight checks**
   - Verify database before starting deployment
   - Abort if database is unavailable

2. **Post-startup checks**
   - Verify green instance can access database
   - Abort if green cannot access database

3. **Pre-switch checks**
   - Verify both blue and green have database access
   - Abort if either instance loses database access

4. **Post-switch monitoring**
   - Continuously monitor green instance database access
   - Rollback immediately if database access is lost

## Testing Database Checks

### Test Database Unavailable

```bash
# Stop database
docker stop crypto-ai-postgres

# Run health check
curl http://localhost:8100/health
# Should return 503 with database_connected: false

# Run database check script
./scripts/check_database.sh
# Should exit with error code 1
```

### Test Database Empty (No Data)

```bash
# Connect to database and truncate users table (DANGER - only in test!)
docker exec crypto-ai-postgres psql -U crypto -d crypto_ai_agent -c "TRUNCATE users;"

# Run health check
curl http://localhost:8100/health
# Should return 503 with database_has_data: false

# Run database check script
./scripts/check_database.sh
# Should exit with error code 1
```

## Environment Variables

The database check script uses these environment variables (or defaults):

- `POSTGRES_USER` (default: `crypto`)
- `POSTGRES_DB` (default: `crypto_ai_agent`)
- `POSTGRES_PASSWORD` (from `.env` file)

## Notes

- Database checks add ~5-10 seconds to deployment time (acceptable for safety)
- Health endpoint checks are fast (< 1 second)
- Direct database checks are slightly slower but more reliable
- Both methods can be used together for redundancy
