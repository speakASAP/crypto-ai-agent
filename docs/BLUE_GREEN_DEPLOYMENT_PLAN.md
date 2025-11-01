# Blue/Green Deployment Implementation Plan

## Approach 3 (Nginx Upstream) + Approach 1 Structure (Centralized)

## Overview

This plan implements zero-downtime blue/green deployment for crypto-ai-agent, managed centrally from nginx-microservice. The system uses Nginx upstream blocks with instant switching and automatic rollback on health check failure.

## Architecture

### Components

1. **Service Registry**: JSON metadata files defining service structure
2. **Nginx Upstream Configuration**: Blue/green upstream blocks with backup servers
3. **Deployment Scripts**: Centralized scripts in nginx-microservice
4. **State Management**: Track active color (blue/green) per service
5. **Health Check Monitoring**: Continuous health checks with auto-rollback
6. **Integration**: Modify crypto-ai-agent docker-compose for blue/green support

### Directory Structure

```
nginx-microservice/
├── scripts/
│   └── blue-green/
│       ├── deploy.sh                    # Main deployment script
│       ├── prepare-green.sh             # Build and start green instance
│       ├── switch-traffic.sh            # Instant switch to green
│       ├── rollback.sh                  # Switch back to blue
│       ├── cleanup.sh                   # Remove old color
│       ├── health-check.sh              # Health check with auto-rollback
│       └── utils.sh                    # Shared utility functions
├── service-registry/
│   └── crypto-ai-agent.json             # Service metadata
└── state/
    └── crypto-ai-agent.json             # Current deployment state

crypto-ai-agent/
├── docker-compose.blue.yml              # Blue environment config
├── docker-compose.green.yml             # Green environment config
└── .env (updated with blue/green vars)
```

## Service Registry Format

### `/nginx-microservice/service-registry/crypto-ai-agent.json`

```json
{
  "service_name": "crypto-ai-agent",
  "service_path": "/Users/sergiystashok/Documents/GitHub/crypto-ai-agent",
  "production_path": "/home/statex/crypto-ai-agent",
  "domain": "crypto-ai-agent.statex.cz",
  "docker_compose_file": "docker-compose.yml",
  "docker_project_base": "crypto_ai_agent",
  "services": {
    "backend": {
      "container_name_base": "crypto-ai-backend",
      "port": 8100,
      "health_endpoint": "/health",
      "health_timeout": 5,
      "health_retries": 3,
      "startup_time": 30
    },
    "frontend": {
      "container_name_base": "crypto-ai-frontend",
      "port": 3100,
      "health_endpoint": "/",
      "health_timeout": 5,
      "health_retries": 3,
      "startup_time": 40
    }
  },
  "shared_services": ["postgres", "redis"],
  "network": "nginx-network"
}
```

## Nginx Configuration Updates

### New Template: `domain-blue-green.conf.template`

Updates nginx template to use upstream blocks:

```nginx
# Upstream blocks for blue/green
upstream crypto-ai-frontend {
    server crypto-ai-frontend-blue:3100 weight=100;
    server crypto-ai-frontend-green:3100 weight=0 backup;
}

upstream crypto-ai-backend {
    server crypto-ai-backend-blue:8100 weight=100;
    server crypto-ai-backend-green:8100 weight=0 backup;
}

# Server blocks use upstream
location / {
    proxy_pass http://crypto-ai-frontend;
    # ... proxy settings ...
}

location /api/ {
    proxy_pass http://crypto-ai-backend/api/;
    # ... proxy settings ...
}
```

## State Management

### `/nginx-microservice/state/crypto-ai-agent.json`

Tracks current deployment state:

```json
{
  "service_name": "crypto-ai-agent",
  "active_color": "blue",
  "blue": {
    "status": "running",
    "deployed_at": "2025-01-XX...",
    "version": "git-commit-hash"
  },
  "green": {
    "status": "stopped",
    "deployed_at": null,
    "version": null
  },
  "last_deployment": {
    "color": "blue",
    "timestamp": "2025-01-XX...",
    "success": true
  }
}
```

## Deployment Workflow

### Phase 1: Prepare Green

1. Read service registry
2. Determine inactive color (opposite of current active)
3. Build docker-compose project with color suffix
4. Start green containers with color-suffixed names
5. Wait for startup_time
6. Perform health checks
7. If health checks pass, mark green as "ready"
8. If health checks fail, mark green as "failed" and exit

### Phase 2: Switch Traffic (Instant)

1. Read current state (active=blue)
2. Update nginx upstream blocks:
   - Set green weight=100
   - Set blue weight=0 backup
3. Reload nginx configuration
4. Update state: active=green
5. Start health check monitoring on green
6. If green fails health checks → automatic rollback

### Phase 3: Monitor and Cleanup

1. Monitor green instance for specified period (e.g., 5 minutes)
2. If green remains healthy, cleanup blue
3. If green fails, execute rollback

### Phase 4: Rollback (Automatic on Failure)

1. Detect health check failure
2. Immediately update nginx upstream:
   - Set blue weight=100
   - Set green weight=0 backup
3. Reload nginx
4. Update state: active=blue
5. Stop and remove green containers
6. Log rollback event

## Scripts Implementation

### 1. `deploy.sh` - Main Deployment Script

**Location**: `/nginx-microservice/scripts/blue-green/deploy.sh`

**Usage**: `./deploy.sh crypto-ai-agent`

**Flow**:

1. Validate service exists in registry
2. Call `prepare-green.sh`
3. If successful, call `switch-traffic.sh`
4. Start background monitoring
5. After monitoring period, call `cleanup.sh` if green is healthy

### 2. `prepare-green.sh` - Build and Start Green

**Location**: `/nginx-microservice/scripts/blue-green/prepare-green.sh`

**Flow**:

1. Determine inactive color
2. Generate docker-compose file with color suffixes
3. Build containers: `docker compose -f docker-compose.green.yml -p crypto_ai_agent_green build`
4. Start containers: `docker compose -f docker-compose.green.yml -p crypto_ai_agent_green up -d`
5. Wait for startup
6. Run health checks on green services
7. Return success/failure

### 3. `switch-traffic.sh` - Instant Switch

**Location**: `/nginx-microservice/scripts/blue-green/switch-traffic.sh`

**Flow**:

1. Read current state (active color)
2. Update nginx config file with new upstream weights
3. Test nginx config: `docker compose exec nginx nginx -t`
4. Reload nginx: `docker compose exec nginx nginx -s reload`
5. Update state file
6. Return success

### 4. `rollback.sh` - Rollback to Previous Color

**Location**: `/nginx-microservice/scripts/blue-green/rollback.sh`

**Flow**:

1. Read current state
2. Determine previous color (blue if active=green, green if active=blue)
3. Update nginx config to switch back
4. Reload nginx
5. Update state
6. Stop and remove failed color containers
7. Log rollback

### 5. `health-check.sh` - Health Check with Auto-Rollback

**Location**: `/nginx-microservice/scripts/blue-green/health-check.sh`

**Flow**:

1. Read service registry for health endpoints
2. For each service (backend, frontend):
   - Check health endpoint
   - Retry up to health_retries times
   - Return success if any check passes
3. If all checks fail:
   - Call `rollback.sh`
   - Return failure
4. Return success

### 6. `cleanup.sh` - Remove Old Color

**Location**: `/nginx-microservice/scripts/blue-green/cleanup.sh`

**Flow**:

1. Read current state (active color)
2. Determine inactive color
3. Stop containers: `docker compose -f docker-compose.{color}.yml -p crypto_ai_agent_{color} down`
4. Remove images (optional, configurable)
5. Update state file

## Docker Compose Modifications

### `docker-compose.blue.yml`

```yaml
services:
  backend:
    container_name: crypto-ai-backend-blue
    # ... rest of config ...
  
  frontend:
    container_name: crypto-ai-frontend-blue
    # ... rest of config ...
  
  postgres:
    container_name: crypto-ai-postgres-blue
    # ... rest of config ...
```

### `docker-compose.green.yml`

```yaml
services:
  backend:
    container_name: crypto-ai-backend-green
    # ... rest of config ...
  
  frontend:
    container_name: crypto-ai-frontend-green
    # ... rest of config ...
  
  postgres:
    container_name: crypto-ai-postgres-green
    # ... rest of config ...
```

**Note**: Shared services (postgres, redis) can either:

- Option A: Share single instance (simpler, but data migration considerations)
- Option B: Separate instances per color (safer, but more resources)

**Recommendation**: Start with Option A (shared DB), evolve to Option B if needed.

## Environment Variables

### Update `.env` in crypto-ai-agent

Add blue/green specific variables:

```bash
# Blue/Green Deployment
DEPLOYMENT_COLOR=blue
COMPOSE_PROJECT_NAME_BLUE=crypto_ai_agent_blue
COMPOSE_PROJECT_NAME_GREEN=crypto_ai_agent_green
```

## Nginx Config Generation

### Update `add-domain.sh` or create `add-domain-blue-green.sh`

When adding a domain that supports blue/green:

1. Use `domain-blue-green.conf.template` instead of `domain.conf.template`
2. Generate config with upstream blocks
3. Initial state: blue=weight=100, green=weight=0 backup

## Implementation Checklist

### Phase 1: Infrastructure Setup

1. Create directory `/nginx-microservice/service-registry/`
2. Create directory `/nginx-microservice/state/`
3. Create directory `/nginx-microservice/logs/blue-green/`
4. Create directory `/nginx-microservice/scripts/blue-green/`
5. Create file `/nginx-microservice/service-registry/crypto-ai-agent.json` with service metadata
6. Create file `/nginx-microservice/state/crypto-ai-agent.json` with initial state (active_color=blue)
7. Create file `/nginx-microservice/nginx/templates/domain-blue-green.conf.template` with upstream blocks
8. Create file `/crypto-ai-agent/docker-compose.blue.yml` with blue container names
9. Create file `/crypto-ai-agent/docker-compose.green.yml` with green container names
10. Backup existing `.env` file in crypto-ai-agent
11. Update `.env` file in crypto-ai-agent: Add `DEPLOYMENT_COLOR=blue`, `COMPOSE_PROJECT_NAME_BLUE=crypto_ai_agent_blue`, `COMPOSE_PROJECT_NAME_GREEN=crypto_ai_agent_green`

### Phase 2: Core Utility Script

1. Create file `/nginx-microservice/scripts/blue-green/utils.sh` with function `load_service_registry(service_name)`
2. Add function `load_state(service_name)` to utils.sh
3. Add function `save_state(service_name, state_data)` to utils.sh
4. Add function `get_active_color(service_name)` to utils.sh
5. Add function `get_inactive_color(service_name)` to utils.sh
6. Add function `update_nginx_upstream(config_file, service_name, active_color)` to utils.sh
7. Add function `log_message(level, service, color, action, message)` to utils.sh
8. Add function `test_nginx_config()` to utils.sh
9. Add function `reload_nginx()` to utils.sh
10. Add function `check_docker_compose_available()` to utils.sh

### Phase 3: Prepare Green Script

1. Create file `/nginx-microservice/scripts/blue-green/prepare-green.sh` with main function
2. Implement service registry loading in prepare-green.sh
3. Implement state loading in prepare-green.sh
4. Implement inactive color determination in prepare-green.sh
5. Implement docker-compose file path construction (docker-compose.{color}.yml)
6. Implement docker project name construction (crypto_ai_agent_{color})
7. Implement docker compose build command: `docker compose -f docker-compose.{color}.yml -p {project_name} build`
8. Implement docker compose up command: `docker compose -f docker-compose.{color}.yml -p {project_name} up -d`
9. Implement startup wait loop (wait for startup_time from registry)
10. Implement backend health check: `curl http://{container-name}:{port}/health`
11. Implement frontend health check: `curl http://{container-name}:{port}/`
12. Implement health check retry logic (retry up to health_retries)
13. Implement success/failure state update in prepare-green.sh
14. Implement error handling: stop containers on failure, exit with error code

### Phase 4: Switch Traffic Script

1. Create file `/nginx-microservice/scripts/blue-green/switch-traffic.sh` with main function
2. Implement service registry loading in switch-traffic.sh
3. Implement state loading in switch-traffic.sh
4. Implement active color determination in switch-traffic.sh
5. Implement nginx config file path determination (from domain in registry)
6. Implement upstream block update: set new_color weight=100, old_color weight=0 backup
7. Implement nginx config test: `docker compose exec nginx nginx -t`
8. Implement nginx reload: `docker compose exec nginx nginx -s reload`
9. Implement state update: active_color = new_color
10. Implement error handling: rollback on nginx reload failure

### Phase 5: Health Check Script

1. Create file `/nginx-microservice/scripts/blue-green/health-check.sh` with main function
2. Implement service registry loading in health-check.sh
3. Implement state loading in health-check.sh (get active color)
4. Implement backend health check endpoint call
5. Implement frontend health check endpoint call
6. Implement retry logic: retry up to health_retries times with health_timeout interval
7. Implement rollback call if all health checks fail: call `rollback.sh`
8. Implement success return if any service passes health check
9. Implement logging of health check results

### Phase 6: Rollback Script

1. Create file `/nginx-microservice/scripts/blue-green/rollback.sh` with main function
2. Implement service registry loading in rollback.sh
3. Implement state loading in rollback.sh
4. Implement previous color determination (blue if active=green, green if active=blue)
5. Implement nginx config update: switch upstream weights back
6. Implement nginx config test in rollback.sh
7. Implement nginx reload in rollback.sh
8. Implement state update: active_color = previous_color
9. Implement stop failed color containers: `docker compose -f docker-compose.{failed_color}.yml -p {project_name} down`
10. Implement rollback event logging
11. Implement error handling: ensure nginx reloads successfully

### Phase 7: Cleanup Script

1. Create file `/nginx-microservice/scripts/blue-green/cleanup.sh` with main function
2. Implement service registry loading in cleanup.sh
3. Implement state loading in cleanup.sh
4. Implement inactive color determination in cleanup.sh
5. Implement docker compose down command: `docker compose -f docker-compose.{inactive_color}.yml -p {project_name} down`
6. Implement optional image removal (configurable)
7. Implement state update: mark inactive color as stopped
8. Implement cleanup confirmation logging

### Phase 8: Main Deploy Script

1. Create file `/nginx-microservice/scripts/blue-green/deploy.sh` with main function
2. Implement command-line argument parsing (service_name)
3. Implement service registry validation (check if service exists)
4. Implement call to prepare-green.sh and capture exit code
5. Implement conditional: if prepare-green fails, exit with error
6. Implement call to switch-traffic.sh and capture exit code
7. Implement conditional: if switch-traffic fails, call rollback.sh
8. Implement background health check monitoring: call health-check.sh every 30 seconds for 5 minutes
9. Implement conditional: if health check fails during monitoring, call rollback.sh
10. Implement conditional: after 5 minutes of healthy monitoring, call cleanup.sh
11. Implement deployment logging: log all steps with timestamps
12. Implement success/failure return codes

### Phase 9: Nginx Configuration Updates

1. Update file `/nginx-microservice/nginx/conf.d/crypto-ai-agent.statex.cz.conf` to use upstream blocks instead of direct container names
2. Add upstream block `upstream crypto-ai-frontend` with blue (weight=100) and green (weight=0 backup)
3. Add upstream block `upstream crypto-ai-backend` with blue (weight=100) and green (weight=0 backup)
4. Update location `/` to use `proxy_pass http://crypto-ai-frontend`
5. Update location `/api/` to use `proxy_pass http://crypto-ai-backend/api/`
6. Update location `/ws` to use `proxy_pass http://crypto-ai-backend/ws`
7. Update location `/health` to use `proxy_pass http://crypto-ai-backend/health`
8. Test nginx config: `docker compose exec nginx nginx -t`
9. Reload nginx: `docker compose exec nginx nginx -s reload`

### Phase 10: Docker Compose File Creation

1. Copy `/crypto-ai-agent/docker-compose.yml` to `/crypto-ai-agent/docker-compose.blue.yml`
2. In docker-compose.blue.yml: Update backend container_name to `crypto-ai-backend-blue`
3. In docker-compose.blue.yml: Update frontend container_name to `crypto-ai-frontend-blue`
4. In docker-compose.blue.yml: Update postgres container_name to `crypto-ai-postgres-blue`
5. In docker-compose.blue.yml: Update redis container_name to `crypto-ai-redis-blue`
6. Copy `/crypto-ai-agent/docker-compose.blue.yml` to `/crypto-ai-agent/docker-compose.green.yml`
7. In docker-compose.green.yml: Replace all `-blue` suffixes with `-green` in container names
8. Verify both docker-compose files have correct network: `nginx-network`

### Phase 11: Testing - Prepare Green

1. Run `./scripts/blue-green/prepare-green.sh crypto-ai-agent` and verify it builds green containers
2. Verify green containers start successfully: `docker ps | grep green`
3. Verify green backend health check passes: `curl http://crypto-ai-backend-green:8100/health`
4. Verify green frontend health check passes: `curl http://crypto-ai-frontend-green:3100/`
5. Verify state file updates correctly after successful prepare
6. Test failure scenario: stop green containers manually, verify prepare-green.sh detects failure and exits with error

### Phase 12: Testing - Switch Traffic

1. Run `./scripts/blue-green/switch-traffic.sh crypto-ai-agent` and verify nginx config updates
2. Verify upstream weights change: blue weight=0 backup, green weight=100
3. Verify nginx config test passes before reload
4. Verify nginx reloads successfully
5. Verify state file updates: active_color = green
6. Test traffic routing: curl requests go to green containers
7. Verify rollback on nginx reload failure scenario

### Phase 13: Testing - Health Check

1. Run `./scripts/blue-green/health-check.sh crypto-ai-agent` with healthy services and verify success
2. Test health check with unhealthy backend: stop backend container, verify health-check detects failure
3. Test health check with unhealthy frontend: stop frontend container, verify health-check detects failure
4. Verify automatic rollback trigger when health check fails
5. Test retry logic: verify health check retries up to health_retries times

### Phase 14: Testing - Rollback

1. Run `./scripts/blue-green/rollback.sh crypto-ai-agent` and verify nginx switches back to blue
2. Verify upstream weights revert: blue weight=100, green weight=0 backup
3. Verify nginx reloads successfully during rollback
4. Verify state file updates: active_color = blue
5. Verify green containers are stopped after rollback
6. Test rollback logging: verify rollback events are logged

### Phase 15: Testing - Cleanup

1. Run `./scripts/blue-green/cleanup.sh crypto-ai-agent` and verify inactive color containers are stopped
2. Verify docker compose down executes successfully
3. Verify state file updates: inactive color marked as stopped
4. Test cleanup logging: verify cleanup events are logged

### Phase 16: Testing - End-to-End Deployment

1. Run `./scripts/blue-green/deploy.sh crypto-ai-agent` and verify complete deployment cycle
2. Verify prepare-green executes successfully
3. Verify switch-traffic executes successfully
4. Verify health check monitoring runs for 5 minutes
5. Verify automatic rollback if green fails during monitoring
6. Verify cleanup executes after successful monitoring period
7. Test deployment logging: verify all steps are logged
8. Test failure scenario: simulate green failure after switch, verify automatic rollback

### Phase 17: Documentation

1. Update `/nginx-microservice/README.md`: Add blue/green deployment section
2. Create `/nginx-microservice/docs/BLUE_GREEN_DEPLOYMENT.md` guide
3. Document service registry JSON format in README
4. Document state file format in README
5. Document rollback procedures and scenarios
6. Update `/crypto-ai-agent/docs/DEPLOYMENT_DOCKER.md` with blue/green deployment instructions
7. Add usage examples to documentation: deploy, rollback, status

### Phase 18: Production Validation

1. Test on production server (create staging test first if possible)
2. Verify zero-downtime: monitor requests during switch, verify no 502 errors
3. Verify switch duration: time the switch, verify < 2 seconds
4. Test automatic rollback: simulate failure, verify rollback executes within 5 seconds
5. Monitor logs for 24 hours after deployment
6. Verify performance: no degradation during or after switch
7. Test manual rollback command: `./scripts/blue-green/rollback.sh crypto-ai-agent`

## Error Handling

### Health Check Failures

- If green fails health checks during prepare: Stop green, exit with error
- If green fails after switch: Immediate rollback to blue
- Log all failures with timestamps

### Nginx Reload Failures

- Test config before reload
- If test fails: Don't reload, rollback state changes
- If reload fails: Attempt rollback immediately

### Container Start Failures

- If containers fail to start: Stop all, clean up, exit
- Log container logs for debugging
- Return meaningful error messages

## Logging

### Log Locations

- Deployment logs: `/nginx-microservice/logs/blue-green/deploy.log`
- Health check logs: `/nginx-microservice/logs/blue-green/health.log`
- Rollback logs: `/nginx-microservice/logs/blue-green/rollback.log`

### Log Format

```
[TIMESTAMP] [LEVEL] [SCRIPT] [SERVICE] [COLOR] [ACTION] [MESSAGE]
2025-01-XX 10:30:15 INFO deploy.sh crypto-ai-agent green prepare Starting green deployment
2025-01-XX 10:32:00 SUCCESS switch-traffic.sh crypto-ai-agent green switch Traffic switched to green
2025-01-XX 10:35:00 ERROR health-check.sh crypto-ai-agent green rollback Health check failed, rolling back
```

## Rollback Scenarios

### Scenario 1: Green Fails After Switch

1. Health check detects failure
2. Automatic rollback to blue (< 5 seconds)
3. Green containers stopped
4. Alert logged

### Scenario 2: Nginx Config Error

1. Config test fails before reload
2. No nginx reload
3. Green remains stopped
4. Blue continues serving
5. Error logged

### Scenario 3: Manual Rollback

```bash
./scripts/blue-green/rollback.sh crypto-ai-agent
```

## Monitoring

### Health Check Monitoring Period

After switch to green:

- Monitor for 5 minutes
- Health check every 30 seconds
- If any check fails → immediate rollback
- After 5 minutes healthy → cleanup blue

### Metrics to Track

- Deployment duration
- Health check response times
- Rollback frequency
- Switch duration
- Cleanup duration

## Security Considerations

1. Service registry files: 644 permissions, readable by scripts
2. State files: 644 permissions, readable/writable by scripts
3. Scripts: 755 permissions, executable
4. No secrets in registry or state files
5. Validate all inputs (service names, paths)

## Performance Targets

- Prepare green: < 3 minutes (build + start)
- Switch traffic: < 2 seconds (nginx reload)
- Health check: < 5 seconds per service
- Rollback: < 5 seconds total
- Cleanup: < 30 seconds

## Future Enhancements

1. Gradual traffic migration (canary deployment)
2. A/B testing support
3. Multiple service orchestration
4. Deployment scheduling
5. Rollback automation based on metrics
6. Database migration strategies for blue/green
