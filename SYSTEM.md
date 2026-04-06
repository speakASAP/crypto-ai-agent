# System: crypto-ai-agent

## Architecture

Next.js 14 frontend + FastAPI backend + PostgreSQL + Redis + WebSocket.

- Real-time price feed via Binance WebSocket
- AI predictions via ai-microservice
- Telegram notifications via notifications-microservice

## Integrations

| Service | Usage |
|---------|-------|
| auth-microservice:3370 | User auth |
| database-server:5432 | PostgreSQL + Redis |
| logging-microservice:3367 | Logs |
| notifications-microservice:3368 | Telegram alerts |
| payments-microservice:3468 | Subscription payments |
| ai-microservice:3380 | Price predictions |

## Current State
<!-- AI-maintained -->
Stage: active

## Known Issues
<!-- AI-maintained -->
- None
