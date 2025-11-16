# Production Infrastructure Configuration

## Overview

The crypto-ai-agent application uses a **microservices architecture** with three separate services:

1. **nginx-microservice** - Handles routing, SSL, and blue/green deployments
2. **database-server** - Provides shared PostgreSQL and Redis infrastructure
3. **crypto-ai-agent** - The application itself (backend + frontend)

## Production Setup

### Directory Structure

All services are located in `/home/statex/`:

```text
/home/statex/
├── nginx-microservice/     # Nginx routing and deployment scripts
├── database-server/         # Shared PostgreSQL and Redis
└── crypto-ai-agent/         # Application code
```

### Database Configuration

**Production uses the shared `database-server` microservice:**

- **PostgreSQL**: `db-server-postgres:5432` (from database-server)
- **Redis**: `db-server-redis:6379` (from database-server)
- **Network**: All services on `nginx-network`

**Blue/Green Deployment Configuration:**

Both `docker-compose.blue.yml` and `docker-compose.green.yml` are correctly configured:

```yaml
environment:
  - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-crypto}:${POSTGRES_PASSWORD:-crypto_pass}@db-server-postgres:5432/${POSTGRES_DB:-crypto_ai_agent}
  - REDIS_URL=redis://db-server-redis:6379/0
```

### Files NOT Used in Production

**⚠️ `docker-compose.infrastructure.yml` - DO NOT USE in Production**

This file is **only for development** or isolated testing. It creates:

- `crypto-ai-postgres` container
- `crypto-ai-redis` container

**These should NOT be running in production** when `database-server` is available.

**To check if infrastructure file is running:**

```bash
docker ps | grep -E 'crypto-ai-postgres|crypto-ai-redis'
```

If these containers are running, stop them:

```bash
cd ~/crypto-ai-agent
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure down
```

**⚠️ `docker-compose.yml` - Development Only**

This file is for local development and includes local postgres/redis services. It should NOT be used in production.

## Deployment Process

### Standard Production Deployment

```bash
ssh statex
cd ~/nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent
```

This script:

1. Checks if `database-server` is running
2. Builds and starts blue/green containers
3. Routes traffic via nginx-microservice
4. Uses `db-server-postgres` and `db-server-redis` from database-server

### Verifying Correct Database Usage

**1. Check backend is using database-server:**

```bash
docker exec crypto-ai-backend-blue env | grep DATABASE_URL
# Should show: db-server-postgres:5432
```

**2. Verify database-server is running:**

```bash
cd ~/database-server
./scripts/status.sh
```

**3. Check no duplicate infrastructure:**

```bash
docker ps | grep -E 'postgres|redis'
# Should only show: db-server-postgres and db-server-redis
# Should NOT show: crypto-ai-postgres or crypto-ai-redis
```

## Troubleshooting

### Issue: Multiple Database Containers Running

**Symptom:** Both `crypto-ai-postgres` and `db-server-postgres` are running

**Solution:**

```bash
# Stop the infrastructure file containers
cd ~/crypto-ai-agent
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure down

# Verify only database-server is running
docker ps | grep postgres
```

### Issue: Backend Cannot Connect to Database

**Check 1:** Verify database-server is running

```bash
cd ~/database-server
./scripts/status.sh
```

**Check 2:** Verify backend is on nginx-network

```bash
docker inspect crypto-ai-backend-blue | grep -A 10 Networks
# Should show nginx-network
```

**Check 3:** Test connection from backend

```bash
docker exec crypto-ai-backend-blue python3 -c "
from app.utils.db import connect_with_retry
conn = connect_with_retry()
print('✅ Connected to:', conn.info.host, conn.info.port)
"
# Should show: db-server-postgres:5432
```

## Summary

✅ **Production uses:**

- `db-server-postgres` and `db-server-redis` from `database-server` microservice
- Blue/green deployments configured correctly
- All services on `nginx-network`

❌ **Production does NOT use:**

- `docker-compose.infrastructure.yml` (development only)
- `docker-compose.yml` (development only)
- Local `crypto-ai-postgres` or `crypto-ai-redis` containers
