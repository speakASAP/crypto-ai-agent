# CLAUDE.md (crypto-ai-agent)

→ Ecosystem: [../shared/CLAUDE.md](../shared/CLAUDE.md) | Reading order: `BUSINESS.md` → `SYSTEM.md` → `AGENTS.md` → `TASKS.md` → `STATE.json`

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

**Ops**: `docker compose logs -f` · `./scripts/deploy.sh`
