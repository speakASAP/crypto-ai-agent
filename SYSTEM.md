# System: crypto-ai-agent

## Architecture

Next.js 14 frontend + FastAPI backend + PostgreSQL + Redis + WebSocket.

- Real-time price feed via Binance WebSocket
- AI predictions via ai-microservice
- Telegram notifications via notifications-microservice

## Integrations

| Service | Usage |
|---------|-------|
| auth-microservice:3370 | User auth (JWT issued + validated here) |
| database-server:5432 | PostgreSQL (`crypto_ai_agent` DB) + Redis |
| logging-microservice:3367 | Logs |
| notifications-microservice:3368 | Telegram alerts |
| payments-microservice:3468 | Subscription payments |
| ai-microservice:3380 | Price predictions |

## Deployment

**Primary:** Kubernetes — namespace `statex-apps`. See [docs/DEPLOYMENT_K8S.md](docs/DEPLOYMENT_K8S.md).
**Legacy (dev only):** Docker Compose. See [docs/DEPLOYMENT_DOCKER.md](docs/DEPLOYMENT_DOCKER.md).

## Secrets

All secrets in Vault: `secret/prod/crypto-ai-agent`
Synced to K8s via ExternalSecret. See [../shared/docs/VAULT.md](../shared/docs/VAULT.md).

## Database

Shared `database-server` service. Connection: `db-server-postgres:5432`, DB: `crypto_ai_agent`.
Blue/green both connect to the same instance — never stop DB during deploy.

## Current State
<!-- AI-maintained -->
Stage: active

## Known Issues
<!-- AI-maintained -->
- None
