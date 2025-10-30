# Web Flow Execution Plan (Login, Alerts, Profile/Bitfinex)

This document defines the exact steps to execute the tasks from `data/notepad.md` with environment, logging, and verification safeguards. No implementation occurs here; this is the authoritative plan to be executed in EXECUTE MODE after approval.

## Scope

- Open browser and log in
- Add a test crypto
- Add two alerts (Above 0.1%, Below 0.1%)
- Check console messages throughout
- Check logs
- Open Profile and verify Bitfinex settings

## Key Components and Endpoints

- Frontend (Next.js): `frontend/`
  - Port: 3100 (`frontend/package.json` → `next dev -p 3100`)
  - API base: `NEXT_PUBLIC_API_URL` (`frontend/next.config.js`)
  - WebSocket: `NEXT_PUBLIC_WS_URL` (`frontend/next.config.js`)
  - Login page: `frontend/src/app/login/page.tsx`
  - Profile page: `frontend/src/app/profile/page.tsx`
  - Alerts UI: `frontend/src/components/AlertModal.tsx`, store `frontend/src/stores/alertsStore.ts`
  - WebSocket wrapper: `frontend/src/components/WebSocketWrapper.tsx`, context `frontend/src/contexts/WebSocketContext.tsx`
  - API helper: `frontend/src/lib/api.ts`
- Backend (FastAPI): `backend/app/`
  - App entry: `backend/app/main.py`
  - Auth endpoints: `backend/app/api/auth.py` (prefix `/api/auth`)
  - Alerts endpoints: `backend/app/api/alerts.py` (prefix `/api/alerts`)
  - Prices endpoints: `backend/app/api/prices.py` (prefix `/api/prices`)
  - WebSocket: `backend/app/api/ws.py` (prefix `/api/ws` and `ws://.../ws`)
  - Config: `backend/app/core/config.py` (reads env via `settings`)
  - Central logger: prefers root `utils/logger.py`, fallback `backend/app/utils/logger.py`
- Logs directory: `logs/` (files: `logs/crypto_agent.log`, `logs/agent.log`, `logs/status.txt`)
- Control scripts: `./start.sh`, `./stop.sh`, `./status.sh`

## Environment and Configuration Preconditions

1. Backup `.env` (do not print or expose secrets).
   - Command to run: `cp .env .env.backup_YYYYmmdd_HHMMSS`
2. Update `.env.example` with missing keys (names only, no values):
   - `NEXT_PUBLIC_API_URL`
   - `NEXT_PUBLIC_WS_URL`
   - `LOG_LEVEL`
   - `LOG_FILE`
   - Any existing backend settings in `backend/app/core/config.py` used by `settings` (e.g., `API_HOST`, `API_PORT`, `CORS_ORIGINS`, `DATABASE_URL`, `ENVIRONMENT`).
3. Ensure frontend uses env for endpoints:
   - `frontend/next.config.js` already uses `process.env.NEXT_PUBLIC_API_URL` and `process.env.NEXT_PUBLIC_WS_URL` with localhost defaults.
4. Ensure central logging is configured:
   - Root logger module: `utils/logger.py` reads `LOG_LEVEL`, `LOG_FILE` and writes to `logs/crypto_agent.log` by default.
   - Backend imports `get_logger` with root-first import.
5. Search for hardcoded secrets/URLs and replace with env variables if found:
   - Scan `frontend/src/**`, `backend/app/**`, `utils/**` for API keys, URLs, credentials.
   - Replace literals with `process.env.*` (frontend) or `os.getenv`/`settings` (backend) where applicable.

## Runtime Setup

1. Confirm `.env` is present and valid: `cat .env` (do not expose content in outputs).
2. Start services using provided scripts:
   - `./start.sh` (expects backend on 8100, frontend on 3100 per defaults).
3. Verify health:
   - Backend: GET `http://localhost:8100/api/health` (`backend/app/api/health.py`).
   - Frontend: open `http://localhost:3100/`.
4. Tail logs in parallel during test execution:
   - `tail -n 200 -f logs/crypto_agent.log` (observe for errors/warnings/info).

## Test Data and Accounts

- Test login will use the credentials provided in `data/notepad.md` during execution only. Do not persist or expose in code or logs beyond necessary authentication requests.

## Browser Execution Steps

1. Navigate to login page: `http://localhost:3100/login`.
2. Perform login via form fields on `frontend/src/app/login/page.tsx`:
   - Fill email and password.
   - Submit and wait for successful redirect or token acquisition (frontend likely stores token in zustand store `frontend/src/stores/authStore.ts`).
   - Verify tokens present in client state and that `/api/auth/login` call returned 200 with `TokenResponse`.
   - Check browser console for errors.
3. Add test crypto (tracked symbol):
   - Use UI component `frontend/src/components/CryptoSearchSelect.tsx` or relevant page to add a symbol (e.g., `BTC`).
   - Confirm network calls to `/api/prices/*` or tracked symbols endpoints, and state update in `frontend/src/stores/symbolsStore.ts`.
   - Validate price stream over WebSocket (`frontend/src/hooks/useWebSocket.ts`) shows live updates.
4. Add two alerts for selected symbol:
   - Open `AlertModal` and create alerts with thresholds Above 0.1% and Below 0.1% as percentages (or set equivalent price-based values if UI uses absolute values). Ensure correct alert type mapping to backend enum values `ABOVE` and `BELOW`.
   - Confirm POSTs to `/api/alerts` succeed and alert appears in UI via `alertsStore`.
   - Verify backend logs indicate alert creation and check cycle in `backend/app/main.py` `check_and_trigger_alerts`.
5. Re-check console messages after each action for warnings/errors.
6. Check logs:
   - `logs/crypto_agent.log` for backend activity and errors.
   - `logs/status.txt` and `logs/agent.log` for ancillary entries if any.
7. Open profile and verify Bitfinex settings:
   - Navigate to `http://localhost:3100/profile`.
   - Page component `frontend/src/app/profile/page.tsx` loads `/api/auth/me` and Bitfinex status endpoints (`/api/auth/bitfinex-credentials`).
   - Confirm whether credentials status is displayed and that test endpoints return expected results (`/api/auth/test-bitfinex-connection`).
8. Final console and logs check to ensure no unhandled errors.

## Verification Points and Evidence

- Frontend Network tab:
  - Successful `POST /api/auth/login` (200) with `TokenResponse` shape.
  - Alert creation `POST /api/alerts` responses (200/201).
  - WebSocket connected to `ws://localhost:8100/ws` and receiving price updates.
- Backend logs (`logs/crypto_agent.log`):
  - Startup entries (app, DB init, currency service, background tasks).
  - Login-related info and no 5xx traces.
  - Alert creation logs and periodic price checks.
- Profile:
  - `GET /api/auth/me` returns user profile.
  - Bitfinex credentials status endpoint responds without server errors.

## Rollback and Safety

- `.env` backed up as `.env.backup_YYYYmmdd_HHMMSS`.
- If errors introduced by env changes, restore `.env` from backup and restart via `./stop.sh` + `./start.sh`.
- No code changes planned unless hardcoded secrets/URLs are found; then only replace with env-backed reads.

---

## IMPLEMENTATION CHECKLIST

1. Backup `.env` to `.env.backup_YYYYmmdd_HHMMSS`.
2. Add missing variable names to `.env.example` (no values).
3. Scan codebase for hardcoded secrets/URLs; document findings.
4. Replace any found hardcoded values with env variables; update code to use `process.env.*` (frontend) or `settings`/`os.getenv` (backend).
5. Start services with `./start.sh`.
6. Verify backend health at `/api/health` and frontend at `http://localhost:3100/`.
7. Open `http://localhost:3100/login` and log in.
8. Confirm successful login (200 response, tokens stored, no console errors).
9. Add a test crypto in UI and confirm prices stream via WebSocket.
10. Create two alerts: Above 0.1%, Below 0.1%.
11. Verify alerts persisted and visible in UI; check backend logs for processing.
12. Re-check browser console for warnings/errors.
13. Review `logs/crypto_agent.log` and `logs/status.txt` for issues.
14. Open `http://localhost:3100/profile` and review Bitfinex settings/status.
15. Run Bitfinex test connection endpoint from profile UI; confirm response.
16. Final pass: ensure no 4xx/5xx in Network tab, no errors in logs.
