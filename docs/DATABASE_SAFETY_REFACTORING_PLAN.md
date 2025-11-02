# Database Safety Refactoring Plan - Zero Data Loss Architecture

## Overview

This plan outlines the refactoring required to ensure zero data loss and zero fault tolerance for database services during blue/green deployments.

## Current Problem Summary

- PostgreSQL and Redis containers are included in blue/green compose files
- Both blue and green try to start their own database containers
- Multiple instances attempt to access the same volumes simultaneously
- **RISK: Data corruption and loss**

## Solution Architecture

### New Structure

```text
crypto-ai-agent/
├── docker-compose.infrastructure.yml  # NEW: Shared infrastructure (postgres, redis)
├── docker-compose.blue.yml            # MODIFIED: Only backend/frontend
├── docker-compose.green.yml           # MODIFIED: Only backend/frontend
└── docker-compose.yml                 # UNCHANGED: Standard deployment

nginx-microservice/
└── scripts/
    └── blue-green/
        └── ensure-infrastructure.sh   # NEW: Ensure shared infrastructure is running
```

### Architecture Flow

```text
┌─────────────────────────────────────────┐
│  Shared Infrastructure (Always Online)  │
│  ┌─────────────┐  ┌─────────────┐      │
│  │  postgres   │  │   redis     │      │
│  │ (singleton) │  │ (singleton) │      │
│  └─────────────┘  └─────────────┘      │
│        │                │              │
│        └────────┬───────┘              │
│                 │                      │
│          nginx-network                 │
└─────────────────┼──────────────────────┘
                  │
        ┌──────────┴──────────┐
        │                     │
┌───────▼──────┐    ┌────────▼───────┐
│  Backend Blue │    │ Backend Green   │
│  Frontend Blue│    │ Frontend Green  │
│  (connects to │    │ (connects to    │
│  shared DB)   │    │  shared DB)     │
└───────────────┘    └─────────────────┘
```

## Implementation Steps

### Phase 1: Create Infrastructure Compose File (CRITICAL)

**File:** `docker-compose.infrastructure.yml`

**Purpose:** Run shared infrastructure (postgres, redis) independently

**Contents:**

- PostgreSQL service (singleton)
- Redis service (singleton)
- Both with `restart: always`
- Health checks
- Named volumes
- nginx-network connection

**Key Features:**

- `restart: always` - Automatic restart on failure
- Health checks - Detect failures quickly
- Named volumes - Explicit volume management
- Network isolation - Accessible only via docker network

### Phase 2: Remove Database from Blue/Green Compose Files

**Files to Modify:**

- `docker-compose.blue.yml`
- `docker-compose.green.yml`

**Changes:**

1. Remove `postgres` service definition
2. Remove `redis` service definition
3. Remove volume definitions for `pgdata` and `redisdata`
4. Remove `depends_on: postgres, redis` (or change to external check)
5. Keep backend/frontend services only

**Connection Changes:**

- Backend connects to `postgres:5432` (not `postgres-blue` or `postgres-green`)
- Backend connects to `redis:6379` (not `redis-blue` or `redis-green`)
- Both services must be on `nginx-network` to discover shared infrastructure

### Phase 3: Update Service Registry

**File:** `nginx-microservice/service-registry/crypto-ai-agent.json`

**Changes:**

1. Add `infrastructure_compose_file: "docker-compose.infrastructure.yml"`
2. Update `shared_services` documentation to clarify they run separately
3. Add infrastructure management configuration

### Phase 4: Create Infrastructure Management Script

**File:** `nginx-microservice/scripts/blue-green/ensure-infrastructure.sh`

**Purpose:** Ensure shared infrastructure is running before blue/green deployments

**Functionality:**

1. Check if infrastructure compose file exists
2. Start infrastructure if not running
3. Wait for health checks
4. Exit with error if infrastructure fails to start
5. Log infrastructure status

**Integration:**

- Called at the beginning of `deploy.sh`
- Called at the beginning of `prepare-green.sh`
- Called at the beginning of `switch-traffic.sh`

### Phase 5: Update Deployment Scripts

**Files to Modify:**

- `nginx-microservice/scripts/blue-green/deploy.sh`
- `nginx-microservice/scripts/blue-green/prepare-green.sh`
- `nginx-microservice/scripts/blue-green/switch-traffic.sh`
- `nginx-microservice/scripts/blue-green/cleanup.sh`

**Changes:**

1. Call `ensure-infrastructure.sh` at the start of each script
2. Update logging to mention infrastructure dependency
3. Ensure cleanup does NOT stop infrastructure containers

### Phase 6: Update Blue/Green Scripts Logic

**File:** `nginx-microservice/scripts/blue-green/prepare-green.sh`

**Changes:**

1. Start infrastructure first (via `ensure-infrastructure.sh`)
2. Start only application containers (backend, frontend)
3. Health checks should verify database connectivity

**File:** `nginx-microservice/scripts/blue-green/cleanup.sh`

**Changes:**

1. Explicitly exclude infrastructure containers from cleanup
2. Only stop application containers (backend, frontend)

### Phase 7: Add Database Health Checks

**File:** `docker-compose.infrastructure.yml`

**Add Health Checks:**

- PostgreSQL: `pg_isready -U crypto -d crypto_ai_agent`
- Redis: `redis-cli ping`

**Purpose:**

- Detect database failures immediately
- Enable automatic restart on failure
- Integration with monitoring

### Phase 8: Update Documentation

**Files to Update:**

- `docs/DEPLOYMENT_DOCKER.md`
- `docs/BLUE_GREEN_DEPLOYMENT.md`
- `nginx-microservice/docs/BLUE_GREEN_DEPLOYMENT.md`
- `docs/BLUE_GREEN_DEPLOYMENT_PLAN.md`

**Documentation Updates:**

1. Explain new infrastructure separation
2. Update deployment instructions
3. Document infrastructure management
4. Add troubleshooting section for database issues
5. Document backup and recovery procedures

### Phase 9: Testing

**Test Scenarios:**

1. **Infrastructure Independence:**
   - Start infrastructure separately
   - Verify it runs independently
   - Stop blue/green containers, verify database remains running

2. **Blue/Green Deployment:**
   - Run full deployment
   - Verify only one database instance running
   - Verify both blue and green connect to same database
   - Verify data persists across switches

3. **Database Failure Recovery:**
   - Stop database container manually
   - Verify automatic restart
   - Verify application containers reconnect

4. **Volume Persistence:**
   - Write data to database
   - Stop all containers
   - Restart infrastructure
   - Verify data is present

5. **Cleanup Safety:**
   - Run cleanup.sh
   - Verify infrastructure containers NOT stopped
   - Verify only application containers stopped

### Phase 10: Production Validation

**Before Production Deployment:**

1. Test on staging environment
2. Verify zero data loss during deployments
3. Verify database stays online during switches
4. Monitor resource usage
5. Test failure scenarios

## Implementation Checklist

### Critical (Must Do First)

- [ ] Create `docker-compose.infrastructure.yml`
- [ ] Remove `postgres` and `redis` from `docker-compose.blue.yml`
- [ ] Remove `postgres` and `redis` from `docker-compose.green.yml`
- [ ] Update backend connection strings to use `postgres` and `redis` (not colored names)
- [ ] Test infrastructure can run independently
- [ ] Test blue/green deployment with separated infrastructure

### High Priority

- [ ] Create `ensure-infrastructure.sh` script
- [ ] Update `deploy.sh` to call `ensure-infrastructure.sh`
- [ ] Update `prepare-green.sh` to call `ensure-infrastructure.sh`
- [ ] Update `cleanup.sh` to exclude infrastructure containers
- [ ] Add database health checks
- [ ] Test database restart and recovery

### Medium Priority

- [ ] Update service registry with infrastructure configuration
- [ ] Update all documentation
- [ ] Add monitoring for database health
- [ ] Create backup automation script
- [ ] Test backup and restore procedures

### Future Enhancements

- [ ] PostgreSQL replication setup
- [ ] Redis cluster mode
- [ ] Automated backup verification
- [ ] Database performance monitoring
- [ ] Connection pool optimization

## Migration Path

### Step 1: Stop Current Deployments

```bash
# Stop any running blue/green deployments
cd /path/to/crypto-ai-agent
docker compose -f docker-compose.blue.yml -p crypto_ai_agent_blue down
docker compose -f docker-compose.green.yml -p crypto_ai_agent_green down
```

### Step 2: Start Infrastructure

```bash
# Start shared infrastructure
docker compose -f docker-compose.infrastructure.yml -p crypto_ai_agent_infrastructure up -d

# Verify it's running
docker ps | grep -E 'postgres|redis'
```

### Step 3: Verify Database Access

```bash
# Test database connection
docker exec crypto-ai-postgres psql -U crypto -d crypto_ai_agent -c "SELECT 1;"
```

### Step 4: Test Blue/Green with New Structure

```bash
# Test deployment
cd /path/to/nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent
```

### Step 5: Verify Only One Database Instance

```bash
# Verify only one postgres container
docker ps | grep postgres
# Should show only one: crypto-ai-postgres (from infrastructure)
```

## Rollback Plan

If issues occur:

1. Stop all containers
2. Revert compose file changes
3. Use original `docker-compose.yml` for standard deployment
4. Investigate and fix issues
5. Retry migration

## Success Criteria

✅ Only ONE PostgreSQL instance running at any time  
✅ Only ONE Redis instance running at any time  
✅ Database survives blue/green container restarts  
✅ No volume conflicts during deployments  
✅ Zero data loss during deployments  
✅ Database automatically restarts on failure  
✅ Blue and green applications connect to same database  
✅ Infrastructure can be managed independently  

## Risk Mitigation

1. **Test Thoroughly:** Complete all test scenarios before production
2. **Backup First:** Take full database backup before migration
3. **Gradual Rollout:** Test on staging, then production
4. **Monitor Closely:** Watch logs and metrics during first deployments
5. **Rollback Ready:** Have rollback plan ready

---

**Priority:** 🔴 P0 - Critical  
**Estimated Time:** 2-3 hours  
**Risk Level:** Medium (with proper testing)  
**Impact:** High (prevents data loss)
