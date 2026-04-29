# Deployment: Docker Compose (Development Only)

> **Production uses Kubernetes.** See [DEPLOYMENT_K8S.md](DEPLOYMENT_K8S.md).

## Local Development

```bash
docker compose up -d --build
```

- Frontend: `http://localhost:3100`
- Backend API: `http://localhost:3102`
- API Docs: `http://localhost:3102/docs`

## Environment

Copy `.env.example` → `.env`. Required vars:

| Var | Description |
|-----|-------------|
| `DATABASE_URL` | `postgresql+psycopg://crypto:PASS@db-server-postgres:5432/crypto_ai_agent` |
| `REDIS_URL` | `redis://db-server-redis:6379/0` |
| `AUTH_SERVICE_URL` | `http://auth-microservice:3370` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:3102` |
| `CORS_ORIGINS` | `http://localhost:3100` |

Secrets come from Vault in production. For local dev, set in `.env` (never commit).

## Nginx Proxy (Production-Docker hybrid)

If running docker-compose in production alongside nginx-microservice:

- Point `crypto-ai-agent.alfares.cz` → `127.0.0.1:3100` (frontend)
- Include `/api` and `/ws` → `127.0.0.1:3102` (backend)
- WebSocket: enable `Upgrade` header proxy

## Blue/Green (Docker)

See [BLUE_GREEN_DEPLOYMENT_GUIDE.md](BLUE_GREEN_DEPLOYMENT_GUIDE.md).

Deploy:

```bash
./scripts/deploy.sh
```
