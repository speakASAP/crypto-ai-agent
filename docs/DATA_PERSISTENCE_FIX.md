# Data Persistence Fix - Blue/Green Deployment

## Issue

During the initial blue/green deployment setup, separate database volumes were created for blue and green environments:
- `crypto_ai_agent_blue_pgdata-blue` (blue deployment)
- `crypto_ai_agent_green_pgdata-green` (green deployment)

This caused **data loss** because:
1. When blue/green deployment was first run, it created brand new empty databases
2. The original database (`crypto-ai-agent_pgdata`) was not being used
3. All user data, portfolio items, and alerts were inaccessible

## Root Cause

The blue/green compose files (`docker-compose.blue.yml` and `docker-compose.green.yml`) used separate volumes per deployment color instead of sharing the database volume.

## Solution

Updated both `docker-compose.blue.yml` and `docker-compose.green.yml` to use **shared database and Redis volumes**:

- **Database**: Both blue and green now use `crypto-ai-agent_pgdata` (same as original `docker-compose.yml`)
- **Redis**: Both blue and green now use `crypto-ai-agent_redisdata` (same as original `docker-compose.yml`)

### Changes Made

1. **docker-compose.blue.yml**:
   - Changed `pgdata-blue` → `pgdata` (with explicit name `crypto-ai-agent_pgdata`)
   - Changed `redisdata-blue` → `redisdata` (with explicit name `crypto-ai-agent_redisdata`)

2. **docker-compose.green.yml**:
   - Changed `pgdata-green` → `pgdata` (with explicit name `crypto-ai-agent_pgdata`)
   - Changed `redisdata-green` → `redisdata` (with explicit name `crypto-ai-agent_redisdata`)

## Benefits

✅ **Data Persistence**: User accounts, portfolio items, and alerts persist across blue/green deployments  
✅ **No Data Loss**: Future deployments will use the existing database  
✅ **Consistency**: All environments (standard, blue, green) use the same database  
✅ **Cache Persistence**: Redis cache is shared, improving performance

## Important Notes

1. **Database Safety**: Both blue and green containers can run simultaneously, but only one should be active at a time. The shared database ensures both see the same data.

2. **Volume Naming**: The explicit volume name (`name: crypto-ai-agent_pgdata`) ensures Docker Compose uses the existing volume created by the original `docker-compose.yml`, preventing creation of new empty volumes.

3. **Migration**: If you have data in separate blue/green volumes, it has been manually migrated to the shared volume. The old separate volumes can be removed after verification.

## Verification

After this fix:
- ✅ User accounts are accessible in both blue and green deployments
- ✅ Portfolio data is preserved
- ✅ Alerts are preserved
- ✅ No data loss during blue/green switches

## Testing

To verify the fix works:

```bash
# 1. Check that both compose files use the same volume
docker compose -f docker-compose.blue.yml config | grep -A5 "pgdata:"
docker compose -f docker-compose.green.yml config | grep -A5 "pgdata:"

# 2. Deploy using blue/green
cd /path/to/nginx-microservice
./scripts/blue-green/deploy.sh crypto-ai-agent

# 3. Verify data is accessible
# Login to the application and confirm all data is present
```

## Date

**Fixed**: November 1, 2025  
**Issue Discovered**: November 1, 2025  
**Data Restored**: November 1, 2025

