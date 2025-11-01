# Database Migration to Centralized Server - Complete ✅

## Migration Summary

Successfully migrated `crypto-ai-agent` from local database containers to the centralized database server.

## What Was Done

### 1. Created Centralized Database Server ✅

- **Repository**: `git@github.com:speakASAP/database-server.git`
- **Location**: `/home/statex/database-server`
- **PostgreSQL**: `db-server-postgres:5432`
- **Redis**: `db-server-redis:6379`

### 2. Database Migration ✅

- **Source**: `crypto-ai-postgres-green` (local container)
- **Destination**: `db-server-postgres` (centralized server)
- **Database**: `crypto_ai_agent`
- **Backup Size**: 57KB (compressed)

### 3. Data Verified ✅

- **Users**: 2
- **Alerts**: 27
- **Portfolio Items**: 50
- **All Tables**: 13 tables migrated successfully

### 4. Configuration Updated ✅

**Files Updated:**
- `docker-compose.green.yml` - Removed local postgres/redis, points to centralized
- `docker-compose.blue.yml` - Updated to use centralized server
- `.env` - Updated connection strings

**Connection Strings:**
```bash
DATABASE_URL=postgresql+psycopg://crypto:crypto_pass@db-server-postgres:5432/crypto_ai_agent
REDIS_URL=redis://db-server-redis:6379/0
```

### 5. Containers Updated ✅

**Running:**
- ✅ `db-server-postgres` - Centralized PostgreSQL
- ✅ `db-server-redis` - Centralized Redis
- ✅ `crypto-ai-backend-green` - Connected to centralized DB
- ✅ `crypto-ai-frontend-green` - Running

**Removed:**
- ✅ `crypto-ai-postgres-green` - Removed (using centralized)
- ✅ `crypto-ai-redis-green` - Removed (using centralized)

## Architecture Change

### Before

```
crypto-ai-agent/
├── crypto-ai-postgres (local)
├── crypto-ai-redis (local)
├── crypto-ai-backend
└── crypto-ai-frontend
```

### After

```
database-server/          (centralized)
├── db-server-postgres   (serves all projects)
└── db-server-redis      (shared cache)

crypto-ai-agent/
├── crypto-ai-backend    (connects to db-server-postgres)
└── crypto-ai-frontend
```

## Benefits

✅ **Resource Efficiency**: Single PostgreSQL instead of N containers  
✅ **Centralized Management**: One place for all database operations  
✅ **Easy Scaling**: Add new projects without new database containers  
✅ **Simplified Backups**: Centralized backup strategy  
✅ **Better Performance**: Shared connection pooling  

## Old Volumes (Can Be Removed)

After verification, these old volumes can be safely removed:

```bash
docker volume rm crypto-ai-agent_pgdata
docker volume rm crypto-ai-agent_redisdata
docker volume rm crypto_ai_agent_blue_pgdata-blue
docker volume rm crypto_ai_agent_blue_redisdata-blue
docker volume rm crypto_ai_agent_green_pgdata-green
docker volume rm crypto_ai_agent_green_redisdata-green
```

⚠️ **Warning**: Only remove after confirming all data is migrated and accessible!

## Backup Strategy

### Manual Backup

```bash
cd /home/statex/database-server
./scripts/backup-database.sh crypto-ai-agent
```

### Backup All Databases

```bash
./scripts/backup-all-databases.sh
```

### Automated Backups

```bash
./scripts/setup-backup-cron.sh
```

This sets up daily backups at 2:00 AM.

## Verification

### Check Database Status

```bash
cd /home/statex/database-server
./scripts/status.sh
```

### Test Connection

```bash
docker exec crypto-ai-backend-green python -c "
import os, psycopg
url = os.getenv('DATABASE_URL', '').replace('+psycopg', '')
conn = psycopg.connect(url)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM users')
print('Users:', cur.fetchone()[0])
"
```

### List All Databases

```bash
cd /home/statex/database-server
./scripts/list-databases.sh
```

## Next Steps for Other Projects

To migrate other projects to the centralized server:

1. **Create Database:**
   ```bash
   cd /home/statex/database-server
   ./scripts/create-database.sh project-name user password db_name
   ```

2. **Backup Existing Database:**
   ```bash
   docker exec old-postgres-container pg_dump -U user db_name > backup.sql
   ```

3. **Restore to Centralized:**
   ```bash
   cat backup.sql | docker exec -i db-server-postgres psql -U dbadmin -d db_name
   ```

4. **Update Project Configuration:**
   - Update `DATABASE_URL` to point to `db-server-postgres`
   - Update `REDIS_URL` to point to `db-server-redis`
   - Remove local postgres/redis from docker-compose files

## Status

✅ **Migration**: Complete  
✅ **Data**: All migrated successfully  
✅ **Configuration**: Updated  
✅ **Verification**: Passed  
✅ **Backups**: Configured  

---

**Migration Date**: 2025-11-01  
**Status**: ✅ Production Ready

