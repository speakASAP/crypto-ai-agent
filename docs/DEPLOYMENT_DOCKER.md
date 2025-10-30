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
