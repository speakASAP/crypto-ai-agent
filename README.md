# crypto-ai-agent

AI-powered cryptocurrency portfolio management. Real-time price tracking via Binance WebSocket, AI predictions, price alerts, Telegram notifications.

**Stack:** Next.js 14 · FastAPI · PostgreSQL · Redis · WebSocket

## Quick Links

| Topic | File |
|-------|------|
| Business goals & constraints | [BUSINESS.md](BUSINESS.md) |
| Architecture & integrations | [SYSTEM.md](SYSTEM.md) |
| Deploy (K8s — primary) | [docs/DEPLOYMENT_K8S.md](docs/DEPLOYMENT_K8S.md) |
| Deploy (Docker — dev only) | [docs/DEPLOYMENT_DOCKER.md](docs/DEPLOYMENT_DOCKER.md) |
| Blue/green deployment | [docs/BLUE_GREEN_DEPLOYMENT_GUIDE.md](docs/BLUE_GREEN_DEPLOYMENT_GUIDE.md) |
| Secrets | `secret/prod/crypto-ai-agent` in Vault |
| AI Advisor | [docs/AI_ADVISOR.md](docs/AI_ADVISOR.md) |
| Binance import | [docs/BINANCE_IMPORT_GUIDE.md](docs/BINANCE_IMPORT_GUIDE.md) |
| CSV import | [docs/CSV_IMPORT_GUIDE.md](docs/CSV_IMPORT_GUIDE.md) |

## Ports

| Service | Port |
|---------|------|
| Frontend | 3100 (blue) / 3101 (green) |
| Backend API | 3102 (blue) / 3103 (green) |

## Development Setup

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 3102

# Frontend
cd frontend && npm install && npm run dev
```

Requires `.env` — see `.env.example`. All secrets come from Vault in production.

## Key Constraints

- Exchange API keys in `.env` only — never log them
- Price alerts: max 1/hour per coin per user
- All AI predictions via ai-microservice — no direct LLM calls
