# CLAUDE.md (crypto-ai-agent)

→ Ecosystem: [../shared/CLAUDE.md](../shared/CLAUDE.md) | Reading order: `BUSINESS.md` → `SYSTEM.md` → `AGENTS.md` → `TASKS.md` → `STATE.json`

---

## Knowledge Retrieval — docs-rag-microservice (MANDATORY, query before reading files)

**Query the RAG before reading source files** — saves 2000-5000 tokens per answer.

```bash
kubectl -n statex-apps exec deployment/business-orchestrator -- curl -s -X POST http://docs-rag-microservice:3397/retrieval/agent-context \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(cat ~/.claude/rag-token)" \
  -d '{"query": "YOUR QUESTION HERE", "maxTokens": 3000}'
```


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

**Ops**: `kubectl logs -n statex-apps -l app=crypto-ai-agent -f` · `kubectl rollout restart deployment/crypto-ai-agent -n statex-apps` · `./scripts/deploy.sh`
