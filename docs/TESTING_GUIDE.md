# Blue/Green Deployment Testing Guide

This guide helps you test the blue/green deployment system step by step.

## Prerequisites Checklist

Before starting testing, verify:

- [ ] Docker and docker compose are installed and running
- [ ] `jq` is installed (`brew install jq` or `apt-get install jq`)
- [ ] Nginx microservice is running
- [ ] `nginx-network` Docker network exists
- [ ] Service registry file exists: `/nginx-microservice/service-registry/crypto-ai-agent.json`
- [ ] State file exists: `/nginx-microservice/state/crypto-ai-agent.json`
- [ ] Docker compose files exist: `docker-compose.blue.yml` and `docker-compose.green.yml`
- [ ] `.env` file is configured with blue/green variables

## Test Phase 11: Prepare Green

### Test 103: Run prepare-green.sh

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/prepare-green.sh crypto-ai-agent
```

**Expected Result:**

- Script executes without errors
- Green containers are built
- Green containers start successfully
- Health checks pass
- Exit code: 0

**If it fails:**

- Check logs: `tail -f logs/blue-green/deploy.log`
- Check container logs: `docker compose -f /path/to/crypto-ai-agent/docker-compose.green.yml -p crypto_ai_agent_green logs`

### Test 104: Verify Green Containers Start

```bash
docker ps | grep green
```

**Expected Result:**
You should see:

- `crypto-ai-backend-green`
- `crypto-ai-frontend-green`
- `crypto-ai-postgres-green`
- `crypto-ai-redis-green`

All should be in "Up" status.

### Test 105: Verify Backend Health Check

```bash
docker run --rm --network nginx-network alpine/curl:latest \
  curl -s http://crypto-ai-backend-green:8100/health
```

**Expected Result:**

```json
{"status":"healthy","database":"postgres","version":"2.0.0","websocket_connections":0}
```

### Test 106: Verify Frontend Health Check

```bash
docker run --rm --network nginx-network alpine/curl:latest \
  curl -s -o /dev/null -w "%{http_code}" http://crypto-ai-frontend-green:${FRONTEND_PORT:-3100}/
```

**Expected Result:**
HTTP status code: `200` or `304`

### Test 107: Verify State File Updates

```bash
cat /path/to/nginx-microservice/state/crypto-ai-agent.json | jq .green
```

**Expected Result:**

```json
{
  "status": "ready",
  "deployed_at": "2025-01-XX...",
  "version": null
}
```

### Test 108: Test Failure Scenario

```bash
# Stop green containers manually
cd /path/to/crypto-ai-agent
docker compose -f docker-compose.green.yml -p crypto_ai_agent_green down

# Try prepare again (should fail if containers can't start)
cd /path/to/nginx-microservice
./scripts/blue-green/prepare-green.sh crypto-ai-agent
```

**Expected Result:**

- Script detects failure
- Exits with error code (non-zero)
- Logs error message
- Stops and cleans up failed containers

## Test Phase 12: Switch Traffic

### Test 109: Run switch-traffic.sh

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/switch-traffic.sh crypto-ai-agent
```

**Expected Result:**

- Script executes without errors
- Nginx config is updated
- Nginx reloads successfully
- Exit code: 0

### Test 110: Verify Upstream Weights Change

```bash
cat nginx/conf.d/crypto-ai-agent.alfares.cz.conf | grep -A 2 "upstream crypto-ai-frontend"
```

**Expected Result:**

```nginx
upstream crypto-ai-frontend {
    server crypto-ai-frontend-blue:${FRONTEND_PORT:-3100} weight=0 backup;  # Port configured in crypto-ai-agent/.env
    server crypto-ai-frontend-green:${FRONTEND_PORT:-3100} weight=100;  # Port configured in crypto-ai-agent/.env
}
```

### Test 111: Verify Nginx Config Test Passes

The script should test nginx config before reload. Check logs:

```bash
tail -20 logs/blue-green/deploy.log | grep "Testing nginx configuration"
```

**Expected Result:**
Should see "SUCCESS" message for config test.

### Test 112: Verify Nginx Reloads Successfully

```bash
docker compose exec nginx nginx -s reload && echo "✅ Nginx reloaded"
```

**Expected Result:**

- Nginx reloads without errors
- No error messages in logs

### Test 113: Verify State File Updates

```bash
cat state/crypto-ai-agent.json | jq .active_color
```

**Expected Result:**

```text
"green"
```

### Test 114: Test Traffic Routing

```bash
# From nginx container, test routing
docker compose exec nginx curl -s http://crypto-ai-frontend/ | head -20
```

**Expected Result:**

- Request should be routed to green container
- Should get response from green (check container logs to verify)

## Test Phase 13: Health Check

### Test 116: Run Health Check with Healthy Services

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/health-check.sh crypto-ai-agent
```

**Expected Result:**

- Exit code: 0
- Logs show "SUCCESS" messages
- All health checks pass

### Test 117: Test with Unhealthy Backend

```bash
# Stop backend container
docker stop crypto-ai-backend-green

# Run health check
./scripts/blue-green/health-check.sh crypto-ai-agent

# Restart backend (cleanup)
docker start crypto-ai-backend-green
```

**Expected Result:**

- Health check detects failure
- Automatic rollback is triggered
- Script exits with error code

### Test 118: Test with Unhealthy Frontend

```bash
# Stop frontend container
docker stop crypto-ai-frontend-green

# Run health check
./scripts/blue-green/health-check.sh crypto-ai-agent

# Restart frontend (cleanup)
docker start crypto-ai-frontend-green
```

**Expected Result:**

- Health check detects failure
- Automatic rollback is triggered
- Script exits with error code

## Test Phase 14: Rollback

### Test 121: Run Rollback

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/rollback.sh crypto-ai-agent
```

**Expected Result:**

- Script executes without errors
- Traffic switches back to blue
- Green containers are stopped
- Exit code: 0

### Test 122: Verify Upstream Weights Revert

```bash
cat nginx/conf.d/crypto-ai-agent.alfares.cz.conf | grep -A 2 "upstream crypto-ai-frontend"
```

**Expected Result:**

```nginx
upstream crypto-ai-frontend {
    server crypto-ai-frontend-blue:${FRONTEND_PORT:-3100} weight=100;  # Port configured in crypto-ai-agent/.env
    server crypto-ai-frontend-green:${FRONTEND_PORT:-3100} weight=0 backup;  # Port configured in crypto-ai-agent/.env
}
```

### Test 124: Verify State File Updates

```bash
cat state/crypto-ai-agent.json | jq .active_color
```

**Expected Result:**

```text
"blue"
```

### Test 125: Verify Green Containers Stopped

```bash
docker ps | grep green
```

**Expected Result:**

- No green containers running
- All green containers stopped

## Test Phase 15: Cleanup

### Test 127: Run Cleanup

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/cleanup.sh crypto-ai-agent
```

**Expected Result:**

- Script executes without errors
- Inactive color containers are removed
- Exit code: 0

## Test Phase 16: End-to-End Deployment

### Test 131: Full Deployment Cycle

```bash
cd /path/to/nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent
```

**Expected Result:**

- All phases execute successfully
- Prepare green: ✅
- Switch traffic: ✅
- Monitor health (5 minutes): ✅
- Cleanup: ✅
- Exit code: 0

### Test 138: Failure Scenario with Auto-Rollback

```bash
# Start deployment
./scripts/blue-green/deploy.sh crypto-ai-agent &
DEPLOY_PID=$!

# Wait for switch to complete (about 2-3 minutes)
sleep 180

# Simulate failure by stopping green backend
docker stop crypto-ai-backend-green

# Wait for rollback to trigger (should happen within 30 seconds)
sleep 35

# Check if rollback occurred
cat state/crypto-ai-agent.json | jq .active_color
# Should be "blue" if rollback worked

# Cleanup
kill $DEPLOY_PID 2>/dev/null || true
docker start crypto-ai-backend-green 2>/dev/null || true
```

**Expected Result:**

- Deployment detects failure
- Automatic rollback executes
- State shows active_color: "blue"
- Green containers are stopped

## Testing Checklist Summary

Before production:

- [ ] All scripts have correct syntax (verified ✅)
- [ ] JSON files are valid (verified ✅)
- [ ] Docker compose files exist (verified ✅)
- [ ] Prepare green works (Test 103-108)
- [ ] Switch traffic works (Test 109-115)
- [ ] Health checks work (Test 116-120)
- [ ] Rollback works (Test 121-126)
- [ ] Cleanup works (Test 127-130)
- [ ] Full deployment cycle works (Test 131-138)
- [ ] Auto-rollback works on failure (Test 138)

## Common Issues During Testing

### Issue: "jq not found"

**Solution**: Install jq: `brew install jq` (macOS) or `apt-get install jq` (Linux)

### Issue: "Service registry not found"

**Solution**: Check file exists: `/nginx-microservice/service-registry/crypto-ai-agent.json`

### Issue: "Docker network nginx-network not found"

**Solution**: Create network: `docker network create nginx-network`

### Issue: "Nginx container not running"

**Solution**: Start nginx: `cd /nginx-microservice && docker compose up -d`

### Issue: "Health checks fail"

**Solution**:

- Verify containers are running: `docker ps | grep green`
- Check container logs for errors
- Verify health endpoints are accessible
- Check network connectivity

### Issue: "Nginx reload fails"

**Solution**:

- Test nginx config: `docker compose exec nginx nginx -t`
- Check nginx logs: `docker compose logs nginx`
- Verify upstream blocks are correct

## Next Steps After Testing

Once all tests pass:

1. Document any service-specific requirements
2. Test in staging environment
3. Schedule production deployment
4. Monitor first production deployment closely
5. Review logs after deployment
