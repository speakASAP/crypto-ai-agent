# Production Deployment (Docker + docker-compose)

## Overview

- Single host using docker-compose
- External Nginx reverse proxy handles TLS and routing to:
  - Frontend: <http://127.0.0.1:3100>
  - Backend API + WebSocket: <http://127.0.0.1:8100> (including `/ws`)
- Persistent volumes for Postgres/Redis, bind-mount `./logs` for backend logs

## Prerequisites

- Docker 24+
- docker-compose v2+
- Existing Nginx reverse proxy with domains and TLS certs
- Production `.env` file placed at repo root (not committed)

## Steps

1. Copy and fill environment variables
   - Use `.env.example` as a reference (do not commit secrets)
   - Ensure these are set: `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `CORS_ORIGINS`, `JWT_SECRET`
2. Start the stack

```bash
# From repo root
# Preferred: use scripts (sets project name and supports per-service)
echo "ENVIRONMENT=production" >> .env
./start.sh --env production
```

3. Verify services

```bash
# Backend
curl -f http://127.0.0.1:8100/docs
# Frontend
curl -f http://127.0.0.1:3100
```

4. Configure external Nginx

- Point `app.example.com` to 127.0.0.1:3100
- Point `api.example.com` to 127.0.0.1:8100
- Enable WebSocket proxying for `/ws`

## Nginx snippets

### API (with WebSocket)

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    location /ws {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Frontend

```nginx
server {
    listen 443 ssl http2;
    server_name app.example.com;

    location / {
        proxy_pass http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Volumes and logs

- Backend writes to `/app/logs` which is bind-mounted to `./logs` on host
- Postgres and Redis use named volumes: `pgdata`, `redisdata`

## Environment variables (production)

Set in `.env` or in server environment:

- Backend
  - `DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5432/DB`
  - `REDIS_URL=redis://localhost:6379/0`
  - `JWT_SECRET` (long random string)
  - `CORS_ORIGINS=https://app.example.com`
  - `LOG_LEVEL=INFO`
- Frontend
  - `NEXT_PUBLIC_API_URL=https://api.example.com`
  - `NEXT_PUBLIC_WS_URL=wss://api.example.com/ws`

## Healthchecks

- Compose defines HTTP healthchecks for backend and frontend

## Data migration (SQLite → Postgres)

- Stop services (`docker compose down`)
- Backup `data/crypto_portfolio.db`
- Run migration script to populate Postgres (see migration doc)
- Start services and verify

## Troubleshooting

- Check container logs: `docker compose logs -f backend frontend postgres redis`
- Ensure Nginx forwards WebSocket upgrades to `/ws`
- Verify CORS matches your frontend domain

## Managing with scripts

The scripts wrap `docker compose` with a fixed project name via `COMPOSE_PROJECT_NAME`.

```bash
# Start all services
./start.sh --env production

# Start a single service
./start.sh --env production --service backend

# Restart services
./start.sh --env production restart                 # all
./start.sh --env production restart --service backend

# Stop
./stop.sh --env production                          # down
./stop.sh --env production --service backend        # stop one

# Status and logs
./status.sh --env production --logs 100
./status.sh --env production --service backend --logs 200
```

## Blue/Green Deployment (Zero-Downtime)

The project supports zero-downtime blue/green deployments managed from the nginx-microservice.

### Prerequisites

- Nginx microservice running
- Service registered in nginx-microservice service registry
- `docker-compose.infrastructure.yml` for shared database/Redis (NEW - required)
- `docker-compose.blue.yml` and `docker-compose.green.yml` files created
- Health check endpoints configured (`/health` for backend, `/` for frontend)
- **Shared infrastructure must be running** (postgres, redis) before deployments

### Quick Deployment

From the nginx-microservice directory:

```bash
# Full deployment (recommended)
./scripts/blue-green/deploy.sh crypto-ai-agent

# This will:
# 0. Ensure shared infrastructure (postgres, redis) is running
# 1. Build and start green containers
# 2. Run health checks
# 3. Switch traffic to green (< 2 seconds)
# 4. Monitor for 5 minutes
# 5. Clean up old blue containers if healthy
```

### Shared Infrastructure Management

**IMPORTANT**: Database (PostgreSQL) and Redis are now managed separately as shared infrastructure. This ensures:

- ✅ **Zero data loss** - Only one database instance prevents data corruption
- ✅ **Always online** - Database survives blue/green deployments
- ✅ **No conflicts** - No volume conflicts during deployments

**Starting Infrastructure:**

```bash
cd /path/to/crypto-ai-agent

# Start shared infrastructure (postgres, redis)
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure up -d

# Verify it's running
docker ps | grep -E 'postgres|redis'
```

**Infrastructure is automatically checked** before each blue/green deployment. If not running, it will be started automatically.

**Stopping Infrastructure** (use with caution - stops database!):

```bash
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure down
```

**Note**: Infrastructure containers use `restart: always` and will automatically restart on failure.

### Manual Rollback

If something goes wrong:

```bash
./scripts/blue-green/rollback.sh crypto-ai-agent
```

### What Gets Deployed

The blue/green system deploys:

- **Backend**: FastAPI service with health checks
- **Frontend**: Next.js application
- **Shared Infrastructure** (managed separately): Postgres and Redis (singleton services, shared by both blue and green)

**Important**: Database and Redis are NOT part of blue/green deployments. They run as singleton services and are shared by both environments. This prevents data corruption and ensures zero data loss.

### Deployment Flow

0. **Infrastructure Check**: Ensure shared infrastructure (postgres, redis) is running
1. **Prepare**: Build and start green containers, verify health
2. **Switch**: Update nginx upstream weights, reload nginx (< 2 seconds)
3. **Monitor**: Continuous health checks for 5 minutes
4. **Rollback**: Automatic if health checks fail
5. **Cleanup**: Remove old deployment after successful monitoring (infrastructure stays running)

### Configuration

Ensure your `.env` file includes:

```bash
# Blue/Green Deployment Configuration
DEPLOYMENT_COLOR=blue
COMPOSE_PROJECT_NAME_BLUE=crypto_ai_agent_blue
COMPOSE_PROJECT_NAME_GREEN=crypto_ai_agent_green

# Blue/Green Deployment Port Configuration
POSTGRES_PORT_GREEN=5433
REDIS_PORT_GREEN=6380
REDIS_APPENDONLY=no
API_PORT_GREEN=8101
FRONTEND_PORT_GREEN=3101
```

### Docker Compose Files

The deployment uses:

- `docker-compose.infrastructure.yml` - **Shared infrastructure** (postgres, redis) - always running
- `docker-compose.blue.yml` - Blue environment configuration (backend, frontend only)
- `docker-compose.green.yml` - Green environment configuration (backend, frontend only)

**Architecture:**
- Infrastructure runs independently with `restart: always`
- Blue/green deployments only manage application containers
- Both blue and green connect to the same shared database/Redis
- This prevents data corruption from multiple database instances

### Health Checks

The system checks:

- **Backend**: `http://crypto-ai-backend-{color}:8100/health`
- **Frontend**: `http://crypto-ai-frontend-{color}:3100/`

### Monitoring

After switching traffic, the system monitors for 5 minutes:

- Health check every 30 seconds
- Automatic rollback if any check fails
- Cleanup after successful monitoring period

### Troubleshooting

**Deployment fails during prepare:**

- Check container logs: `docker compose -f docker-compose.green.yml -p crypto_ai_agent_green logs`
- Verify health endpoints are accessible
- Check service registry configuration in nginx-microservice

**Automatic rollback triggered:**

- Check logs: `tail -f /nginx-microservice/logs/blue-green/deploy.log`
- Verify green containers: `docker ps | grep green`
- Test health endpoints manually

For more details, see [nginx-microservice Blue/Green Deployment Guide](../../nginx-microservice/docs/BLUE_GREEN_DEPLOYMENT.md).
