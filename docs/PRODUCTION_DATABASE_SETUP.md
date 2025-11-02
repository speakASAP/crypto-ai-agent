# Production Database Setup - USE ONLY PRODUCTION DATA

## ⚠️ CRITICAL: NEVER MIGRATE FROM LOCAL TO PRODUCTION

**Production database is the source of truth.**

- ✅ Production database has customer data (4 users, 48 portfolio items)
- ❌ DO NOT overwrite production with local data
- ❌ DO NOT migrate local database to production

## Current Production Database Status

✅ **Verified Working:**

- Database: PostgreSQL
- Customer accounts: 4 users
- Your account: <ssfskype@gmail.com> (ID: 1, Active)
- Portfolio items: 48 items
- Connection: Working

## Production Backend Configuration

### Required Environment Variables

Production backend **MUST** use these settings:

```bash
# In production .env file or docker-compose environment
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-crypto}:${POSTGRES_PASSWORD:-crypto_pass}@postgres:5432/${POSTGRES_DB:-crypto_ai_agent}
```

**Important points:**

1. **Hostname is 'postgres'** (Docker network hostname, NOT 'localhost')
2. **ENVIRONMENT=production** (ensures PostgreSQL is used)
3. **Network must be 'nginx-network'** (to reach 'postgres' hostname)

### Docker Compose Configuration

Production backend container configuration:

```yaml
# docker-compose.blue.yml or docker-compose.green.yml
services:
  backend:
    environment:
      - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-crypto}:${POSTGRES_PASSWORD:-crypto_pass}@postgres:5432/${POSTGRES_DB:-crypto_ai_agent}
      - ENVIRONMENT=production
    networks:
      - default
      - nginx-network  # CRITICAL: Must be on this network
```

**Network requirement:**

- Backend container MUST be on `nginx-network`
- This allows backend to reach `postgres` hostname (shared infrastructure)

### Shared Infrastructure Database

Production database runs as shared infrastructure:

```yaml
# docker-compose.infrastructure.yml
services:
  postgres:
    container_name: crypto-ai-postgres
    networks:
      - nginx-network  # Shared network
```

Both blue and green backends connect to the **SAME** production database.

## Troubleshooting "Could not validate credentials"

If production login fails with "Could not validate credentials":

### 1. Check Database Connection

```bash
# From production server
cd /path/to/crypto-ai-agent
python3 scripts/check_production_database.py
```

Should show:

- ✅ Connection successful
- ✅ 4 customer accounts
- ✅ Your account found

### 2. Check Production Backend Can Reach Database

```bash
# Check backend container is on nginx-network
docker inspect crypto-ai-backend-blue | grep -A 10 Networks

# Should show: nginx-network
```

### 3. Check Backend Environment Variables

```bash
# Check backend container environment
docker exec crypto-ai-backend-blue env | grep -E "DATABASE_URL|ENVIRONMENT"

# Should show:
# ENVIRONMENT=production
# DATABASE_URL=postgresql+psycopg://crypto:***@postgres:5432/crypto_ai_agent
```

**Critical:** Hostname must be `postgres` (not `localhost` or IP)

### 4. Test Database Connection from Backend Container

```bash
# Test connection from inside backend container
docker exec crypto-ai-backend-blue python3 -c "
from app.utils.db import connect_with_retry
conn = connect_with_retry()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM users')
print(f'Users: {cur.fetchone()[0]}')
"
```

### 5. Check Backend Logs

```bash
# Check backend logs for database errors
docker logs crypto-ai-backend-blue | grep -i "database\|connection\|error"
```

Look for:

- ✅ "Database connection successful"
- ✅ "Database schema exists with X users"
- ❌ "Database connection failed"
- ❌ "Could not connect to database"

### 6. Verify Health Endpoint

```bash
# Check backend health endpoint
curl https://crypto-ai-agent.statex.cz/api/health

# Should show:
# {
#   "status": "healthy",
#   "database_connected": true,
#   "database_has_data": true,
#   "user_count": 4
# }
```

## Common Issues

### Issue 1: Backend uses 'localhost' instead of 'postgres'

**Symptom:** Backend cannot connect to database

**Solution:**

```bash
# Update DATABASE_URL in .env or docker-compose
DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/db
# NOT: @localhost:5432/db
```

### Issue 2: Backend not on nginx-network

**Symptom:** Cannot resolve 'postgres' hostname

**Solution:**

```yaml
# docker-compose.blue.yml
services:
  backend:
    networks:
      - default
      - nginx-network  # Add this
```

### Issue 3: Wrong DATABASE_URL

**Symptom:** Connects to wrong/empty database

**Solution:**

- Verify DATABASE_URL matches production database
- Check POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB match infrastructure

### Issue 4: ENVIRONMENT not set to production

**Symptom:** Backend uses SQLite instead of PostgreSQL

**Solution:**

```bash
# Set in .env or docker-compose
ENVIRONMENT=production
```

## Verification Checklist

Before deploying, verify:

- [ ] Production database has customer data (4+ users)
- [ ] Backend DATABASE_URL uses 'postgres' hostname
- [ ] Backend ENVIRONMENT=production
- [ ] Backend container on nginx-network
- [ ] Shared infrastructure (postgres) running
- [ ] Health endpoint shows database_has_data=true
- [ ] Login endpoint can query users table

## Scripts Available

1. **check_production_database.py** - Verify production database has data
2. **verify_production_connection.py** - Verify backend can connect to production DB
3. **verify_customer_data.py** - List all customer accounts

**DO NOT USE:**

- ❌ migrate_to_production_db.py (DELETED - never migrate from local)

## Summary

✅ **Production database HAS customer data**
✅ **Production backend MUST connect to production database**
✅ **Production backend MUST use 'postgres' hostname (Docker network)**
✅ **Production backend MUST be on nginx-network**

If login fails, the issue is **configuration** (wrong DATABASE_URL, wrong network, etc.), NOT missing data.
