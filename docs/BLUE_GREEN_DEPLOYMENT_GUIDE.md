# Blue/Green Deployment Guide - Crypto AI Agent

## Overview

This guide covers the complete blue/green deployment system for crypto-ai-agent, enabling zero-downtime deployments with automatic rollback on failure.

## Architecture

The blue/green deployment system uses:

1. **Nginx Upstream Blocks**: Weight-based routing between blue and green environments
2. **Shared Infrastructure**: Database and Redis managed separately (database-server or docker-compose.infrastructure.yml)
3. **Automatic Health Checks**: Continuous monitoring with auto-rollback
4. **State Management**: Tracks active color and deployment status

## Prerequisites

1. **Nginx Microservice Running**: Blue/green scripts are managed from nginx-microservice
2. **Service Registered**: Service must be in `/nginx-microservice/service-registry/crypto-ai-agent.json`
3. **Docker Compose Files**:
   - `docker-compose.blue.yml` - Blue environment
   - `docker-compose.green.yml` - Green environment
   - `docker-compose.infrastructure.yml` (optional - if using shared database-server, not needed)
4. **Health Endpoints**:
   - Backend: `/health`
   - Frontend: `/`

## Infrastructure Setup

### Option 1: Shared Database-Server (Recommended for Production)

The shared `database-server` service provides centralized PostgreSQL and Redis:

```bash
# Start database-server (if not running)
cd /path/to/database-server
./scripts/start.sh

# Verify it's running
./scripts/status.sh
```

The blue/green deployment scripts automatically detect and use shared infrastructure.

**Connection Details:**

- PostgreSQL: `db-server-postgres:${DB_SERVER_PORT:-5432}` (configured in `database-server/.env`)
- Redis: `db-server-redis:${REDIS_SERVER_PORT:-6379}` (configured in `database-server/.env`)

### Option 2: Service-Specific Infrastructure

If using `docker-compose.infrastructure.yml` (for development or isolated deployments):

```bash
cd /path/to/crypto-ai-agent
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure up -d
```

**Connection Details:**

- PostgreSQL: `crypto-ai-postgres:${POSTGRES_PORT_GREEN:-5433}` (configured in `crypto-ai-agent/.env`)
- Redis: `crypto-ai-redis:${REDIS_PORT_GREEN:-6380}` (configured in `crypto-ai-agent/.env`)

## Deployment Workflow

### Full Deployment (Recommended)

From nginx-microservice directory:

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent
```

**What This Does:**

1. **Phase 0: Infrastructure Check**
   - Checks if shared database-server is running OR service-specific infrastructure
   - Starts infrastructure if needed
   - Waits for health checks

2. **Phase 1: Prepare Green**
   - Builds green containers
   - Starts green containers
   - Performs health checks
   - Marks as "ready" if healthy

3. **Phase 2: Switch Traffic**
   - Updates nginx upstream config
   - Reloads nginx (instant switch, < 2 seconds)
   - Updates state file

4. **Phase 3: Monitor**
   - Health checks every 30 seconds
   - Monitors for 5 minutes
   - Automatic rollback on failure

5. **Phase 4: Cleanup**
   - Removes old color containers if green is healthy
   - Infrastructure stays running (never stopped)

### Manual Rollback

If you need to rollback manually:

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/rollback.sh crypto-ai-agent
```

This will:

- Switch traffic back to previous color
- Stop failed color containers
- Update state file

### Check Deployment Status

```bash
cat /path/to/nginx-microservice/state/crypto-ai-agent.json | jq .
```

**State Values:**

- `active_color`: Currently active color (blue or green)
- `blue.status`: blue container status (running, stopped, backup)
- `green.status`: green container status (running, stopped, backup)
- `last_deployment`: Last deployment timestamp and success status

## Troubleshooting

### Issue: "Infrastructure compose file not found"

**Cause:** Script can't find `docker-compose.infrastructure.yml` and shared database-server is not running.

**Solution:**

1. Start shared database-server: `cd database-server && ./scripts/start.sh`
2. OR copy `docker-compose.infrastructure.yml` to production server

### Issue: "Nginx configuration test failed"

**Cause:** Nginx config references containers that don't exist.

**Solution:**

- The `update_nginx_upstream` function automatically comments out missing containers
- Ensure at least one color (blue or green) has running containers
- Run: `./scripts/blue-green/switch-traffic.sh crypto-ai-agent` to fix config

### Issue: "Health check failed, rollback triggered"

**Cause:** New deployment failed health checks.

**Actions Taken:**

- Automatic rollback to previous color
- Failed containers stopped
- Traffic switched back immediately

**Investigation:**

```bash
# Check container logs
docker logs crypto-ai-backend-green
docker logs crypto-ai-frontend-green

# Check deployment logs
tail -f /path/to/nginx-microservice/logs/blue-green/deploy.log
```

### Issue: "Container not found in upstream"

**Cause:** Nginx references a container that doesn't exist or isn't on nginx-network.

**Solution:**

1. Verify containers are running: `docker ps | grep crypto-ai`
2. Verify containers are on nginx-network: `docker inspect crypto-ai-backend-blue | grep nginx-network`
3. Use switch-traffic script to update config: `./scripts/blue-green/switch-traffic.sh crypto-ai-agent`

### Issue: HTTPS Connection Timeout

**Cause:** Nginx config issue or firewall blocking port 443.

**Solution:**

1. Check nginx status: `docker ps | grep nginx-microservice`
2. Test config: `docker compose exec nginx nginx -t`
3. Check logs: `docker compose logs nginx | tail -50`
4. Verify SSL certificates exist: `ls -la certificates/crypto-ai-agent.statex.cz/`

## Best Practices

### 1. Always Test Before Production

```bash
# Test prepare-green (doesn't switch traffic)
./scripts/blue-green/prepare-green.sh crypto-ai-agent

# Verify green containers are healthy
docker ps | grep green
docker logs crypto-ai-backend-green
docker logs crypto-ai-frontend-green

# Then proceed with full deployment
./scripts/blue-green/deploy.sh crypto-ai-agent
```

### 2. Monitor After Deployment

```bash
# Watch deployment logs
tail -f /path/to/nginx-microservice/logs/blue-green/deploy.log

# Monitor container health
watch -n 5 'docker ps | grep crypto-ai'

# Check application logs
docker logs -f crypto-ai-backend-green
docker logs -f crypto-ai-frontend-green
```

### 3. Keep State File Accurate

The state file must match actual running containers. If you manually restart containers:

```bash
# Update state file to reflect current status
cd /path/to/nginx-microservice
./scripts/blue-green/switch-traffic.sh crypto-ai-agent
```

### 4. Infrastructure Management

- **Never stop database-server during deployments** (managed separately)
- **Infrastructure containers use `restart: always`** (automatic recovery)
- **Shared infrastructure is preferred** (database-server service)

### 5. Cleanup Old Deployments

After successful deployment, old color is automatically cleaned up. To manually cleanup:

```bash
./scripts/blue-green/cleanup.sh crypto-ai-agent
```

**Warning:** Only run cleanup if you're sure the other color is healthy and running.

## Configuration Files

### Service Registry

Location: `/nginx-microservice/service-registry/crypto-ai-agent.json`

Defines service structure, health endpoints, and paths.

### State File

Location: `/nginx-microservice/state/crypto-ai-agent.json`

Tracks active color and deployment status. **DO NOT** edit manually. Use scripts.

### Nginx Config

Location: `/nginx-microservice/nginx/conf.d/crypto-ai-agent.statex.cz.conf`

Managed automatically by `switch-traffic.sh`. **DO NOT** edit manually unless troubleshooting.

## Logs

### Deployment Logs

```text
/path/to/nginx-microservice/logs/blue-green/deploy.log
```

**Format:**

```text
[TIMESTAMP] [LEVEL] [SERVICE] [COLOR] [ACTION] [MESSAGE]
```

### Application Logs

```bash
# Backend logs
docker logs crypto-ai-backend-blue
docker logs crypto-ai-backend-green

# Frontend logs
docker logs crypto-ai-frontend-blue
docker logs crypto-ai-frontend-green

# Follow logs
docker logs -f crypto-ai-backend-green
```

### Nginx Logs

```bash
docker compose logs nginx
docker compose logs nginx --tail 100 -f
```

## Production Deployment Checklist

- [ ] Verify database-server is running
- [ ] Verify nginx-microservice is running
- [ ] Check current state: `cat state/crypto-ai-agent.json | jq .`
- [ ] Test prepare-green: `./scripts/blue-green/prepare-green.sh crypto-ai-agent`
- [ ] Verify green containers are healthy
- [ ] Run full deployment: `./scripts/blue-green/deploy.sh crypto-ai-agent`
- [ ] Monitor logs for 5+ minutes after deployment
- [ ] Verify website is accessible: `curl -I https://crypto-ai-agent.statex.cz/`
- [ ] Check application functionality
- [ ] Verify old color was cleaned up (if successful)

## Emergency Procedures

### Immediate Rollback

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/rollback.sh crypto-ai-agent
```

### Stop All Deployments

```bash
# Stop green containers
docker compose -f /path/to/crypto-ai-agent/docker-compose.green.yml \
    -p crypto_ai_agent_green down

# Keep blue running (active)
# Infrastructure stays running
```

### Full Restart

```bash
# Restart nginx (if needed)
cd /path/to/nginx-microservice
docker compose restart nginx

# Restart database-server (if needed)
cd /path/to/database-server
./scripts/restart.sh

# Restart crypto-ai-agent blue (if needed)
cd /path/to/crypto-ai-agent
docker compose -f docker-compose.blue.yml -p crypto_ai_agent_blue restart
```

## Related Documentation

- [Blue/Green Deployment Overview](../nginx-microservice/docs/BLUE_GREEN_DEPLOYMENT.md)
- [Docker Deployment Guide](./DEPLOYMENT_DOCKER.md)
- [Database Server Documentation](../database-server/README.md)
