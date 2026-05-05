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

**Platform:** Kubernetes (k3s) · namespace `statex-apps`. See [docs/DEPLOYMENT_K8S.md](docs/DEPLOYMENT_K8S.md).  
**Image:** `localhost:5000/crypto-ai-agent:latest`  
**Deploy:** `./scripts/deploy.sh`  
**Logs:** `kubectl logs -n statex-apps -l app=crypto-ai-agent -f`

## Secrets

All secrets in Vault: `secret/prod/crypto-ai-agent`
Synced to K8s via ExternalSecret. See [../shared/docs/VAULT.md](../shared/docs/VAULT.md).

## Database

Shared `database-server` service. Connection: `db-server-postgres:5432` (within cluster: `192.168.88.53:5432`), DB: `crypto_ai_agent`.

## Current State
<!-- AI-maintained -->
Stage: active

## Known Issues
<!-- AI-maintained -->
- None
