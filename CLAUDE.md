# Claude Instructions

Shared rules live here:

- Claude profile: `/home/ssf/.claude/CLAUDE.md`
- Shared ecosystem instructions: `/home/ssf/Documents/Github/CLAUDE.md`
- Codex profile: `/home/ssf/.codex/AGENTS.md`
- Cross-agent standard: `/home/ssf/.ai-agent-standards/CROSS_AGENT_AUTOMATION_STANDARD.md`
- Repository operations: `AGENT_OPERATIONS.md`

Read those first, then follow the repository-specific notes below and the current planning/status files.


## Repository-Specific Notes

# CLAUDE.md (crypto-ai-agent)

→ Ecosystem: [../shared/CLAUDE.md](../shared/CLAUDE.md) | Reading order: `BUSINESS.md` → `SYSTEM.md` → `AGENTS.md` → `TASKS.md` → `STATE.json`

---

## Knowledge Retrieval

Use `docs-rag-microservice` for bounded discovery when it is healthy, then
verify deployment, security, database, integration and public-contract facts
against the cited Git source. Git remains authoritative.

Authority and fallback rules:
`/home/ssf/Documents/Github/shared/docs/DOCUMENTATION_AUTHORITY.md`.

Do not generate tokens in documentation or assume an unconfident/failed RAG
response means that source documentation does not exist.

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

**Ops**: `kubectl logs -n statex-apps -l app=crypto-ai-agent -f` · `kubectl rollout restart deployment/crypto-ai-agent -n statex-apps` · `./scripts/deploy.sh`
