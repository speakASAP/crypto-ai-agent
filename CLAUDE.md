# CLAUDE.md (crypto-ai-agent)

Ecosystem defaults: sibling [`../CLAUDE.md`](../CLAUDE.md) and [`../shared/docs/PROJECT_AGENT_DOCS_STANDARD.md`](../shared/docs/PROJECT_AGENT_DOCS_STANDARD.md).

Read this repo's `BUSINESS.md` → `SYSTEM.md` → `AGENTS.md` → `TASKS.md` → `STATE.json` first.

---

## crypto-ai-agent

**Purpose**: AI-powered cryptocurrency portfolio management — real-time price tracking via Binance WebSocket, AI predictions, price alerts, Telegram notifications.  
**Stack**: Next.js 14 (frontend) · FastAPI (backend) · PostgreSQL · Redis · WebSocket

### Key constraints
- Never execute real trades without explicit user confirmation — suggestions are advisory only
- Exchange API keys (Binance, etc.) in `.env` only — never log them
- Price alerts: max 1 alert/hour per coin per user — never spam
- All AI predictions via ai-microservice — no direct LLM calls

### Key integrations
| Service | Usage |
|---------|-------|
| ai-microservice:3380 | Price predictions |
| notifications-microservice:3368 | Telegram price alerts |
| payments-microservice:3468 | Subscription |

### Quick ops
```bash
docker compose logs -f
./scripts/deploy.sh
```
