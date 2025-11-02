# Fix Production Database Connection

## Issue Identified

Production has TWO PostgreSQL databases:

1. **`db-server-postgres`** - Has customer data (2 users including <ssfskype@gmail.com>)
2. **`crypto-ai-postgres`** - Empty (0 users)

Backend was connecting to **`postgres`** hostname which resolves to `crypto-ai-postgres` (empty database).

## Fix Applied

Updated `docker-compose.blue.yml` and `docker-compose.green.yml` to use `db-server-postgres` instead of `postgres`:

```yaml
DATABASE_URL=postgresql+psycopg://...@db-server-postgres:5432/...
```

## Deploy Fix to Production

### Option 1: Git Pull (if changes committed)

```bash
ssh statex
cd crypto-ai-agent
git pull
docker compose -f docker-compose.blue.yml -p crypto_ai_agent_blue restart backend
```

### Option 2: Manual Update

```bash
ssh statex
cd crypto-ai-agent

# Backup current files
cp docker-compose.blue.yml docker-compose.blue.yml.backup
cp docker-compose.green.yml docker-compose.green.yml.backup

# Update DATABASE_URL in both files
sed -i 's/@postgres:5432/@db-server-postgres:5432/g' docker-compose.blue.yml
sed -i 's/@postgres:5432/@db-server-postgres:5432/g' docker-compose.green.yml

# Restart backend
docker compose -f docker-compose.blue.yml -p crypto_ai_agent_blue restart backend
```

## Verify Fix

```bash
# Check backend can access customer data
docker exec crypto-ai-backend-blue python3 -c "
from app.dependencies.auth import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM users')
print(f'Users: {cur.fetchone()[0]}')
"

# Should show: Users: 2
```

## Test Login

After restart, login should work:

- Email: <ssfskype@gmail.com>
- Password: [your password]

The API login test already succeeded, so once backend restarts with correct DATABASE_URL, browser login will work too.
