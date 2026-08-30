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
Synced to K8s via ExternalSecret.

## Database

Shared `database-server` service. Connection: `db-server-postgres:5432` (within cluster: `db-server-postgres.statex-apps.svc.cluster.local:5432`), DB: `crypto`.

## Current State
<!-- AI-maintained -->
Stage: active

## Known Issues
<!-- AI-maintained -->
- None

## Purpose
AI-powered cryptocurrency portfolio management with Binance price tracking, AI predictions, price alerts, and Telegram notifications.

## Responsibilities
Provide the behavior and runtime described by the tracked project documentation.

## Non-Responsibilities
Do not add integrations, persistence, or product scope not declared by repository sources.

## Inputs
Inputs are the browser, runtime, and configuration inputs described in existing project sources.

## Outputs
Outputs are the user-visible or operational results described in existing project sources.

## Dependencies
Next.js and FastAPI runtime with PostgreSQL, Redis, auth, AI, notifications, payments, logging, and Vault-backed Kubernetes configuration.

## Upstream Traceability
The approved business baseline and vision define this system’s intent.

## Downstream Artifacts
The integration contract and bootstrap chain record planning evidence.

## Validation Criteria
Run the IPS planning validator and applicable existing project checks.

## Open Questions
No new open question is asserted by this documentation-only adoption.
Status: reviewed
completeness_level: complete
