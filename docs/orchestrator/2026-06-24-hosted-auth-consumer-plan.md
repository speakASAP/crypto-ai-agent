# Crypto AI Agent Hosted Auth Consumer Plan

Date: 2026-06-24
Owner role: Wave 2 Crypto AI hosted Auth worker
Repo: `/home/ssf/Documents/Github/crypto-ai-agent`
Mode: bounded remote-only implementation

## IPS Chain

Vision: Alfares applications use one central hosted Auth surface and shared Auth identity instead of consumer-local credential forms.

Goal Impact: Crypto AI users start sign in and registration at `https://auth.alfares.cz`, return to Crypto AI through `/auth/callback`, and continue using Auth-owned access tokens for protected Crypto AI APIs.

System: Auth-hosted `/login` and `/register`; Auth `/auth/validate`; Crypto AI Next.js frontend redirect/callback/session adapter; Crypto AI FastAPI backend protected routes and local profile data.

Feature: hosted Auth redirect/callback adoption for user-facing `/login` and `/register`.

Task: replace active credential forms with hosted Auth redirect launchers using `client_id=crypto-ai-agent`, add fragment callback parsing with state validation and fragment stripping, preserve backend `/auth/validate` validation behavior, and mark local `/api/auth/login|register` credential proxies as compatibility/deprecated.

Execution Plan: inspect Auth consumer standard and rollout handoff; list current auth surfaces; change only allowed auth frontend/backend files; document transitional localStorage token storage debt; validate with frontend build, static credential-form scan, backend-safe tests if discoverable, and `git diff --check`.

Coding Prompt: do not touch exchange keys, portfolio/trading/alerts logic, secrets, live DB data, deploy/k8s, or legacy `speakasap-portal`; do not log token fragments; keep unavailable facts marked as missing or unknown.

Code: frontend hosted Auth helper, callback page, login/register redirect pages, auth store callback completion, token-log cleanup, backend compatibility headers/docs for credential proxy routes.

Validation: frontend build, static scan for active login/register credential POSTs, backend test discovery, and whitespace diff check.

## Current Auth Surfaces

- `frontend/src/app/login/page.tsx`: replaced local email/password form with hosted Auth `/login` redirect launcher.
- `frontend/src/app/register/page.tsx`: replaced local account/password form with hosted Auth `/register` redirect launcher.
- `frontend/src/app/auth/callback/page.tsx`: new callback route parses URL fragment, validates stored `state`, strips the fragment, stores the transitional session, and routes to the original safe in-app path.
- `frontend/src/lib/hostedAuth.ts`: new bounded adapter for `client_id=crypto-ai-agent`, `return_url`, opaque `state`, state TTL, safe return paths, and fragment parsing.
- `frontend/src/stores/authStore.ts`: keeps existing localStorage/cookie persistence but adds `completeHostedAuth` for Auth callback sessions.
- `frontend/src/lib/api.ts`: continues sending `Authorization: Bearer` for protected APIs and removes token-prefix debug logging; local `login`/`register` client methods remain compatibility-only.
- `backend/app/api/auth.py`: keeps `/api/auth/login` and `/api/auth/register` as compatibility proxy endpoints and adds deprecation headers; `/api/auth/me` can return the Auth-validated fallback profile when no local profile row exists.
- `backend/app/services/auth_service.py`: keeps Auth `/auth/validate` behavior unchanged and documents login/register proxy methods as compatibility-only.

## Transitional Session Model

Crypto AI still uses the accepted transitional browser-token model because a BFF/httpOnly-cookie adapter is not present in this repo. Tokens are stored through the existing Zustand persistence layer after the callback validates `state` and strips the URL fragment.

Debt to retire:

- Move Auth callback token handoff into an HTTP-only, Secure, SameSite cookie session adapter.
- Remove browser localStorage/cookie token persistence once the BFF session adapter exists.
- Remove `/api/auth/login` and `/api/auth/register` credential proxy routes after all active clients use hosted Auth.
- Reconcile hosted Auth registration with durable local Crypto AI profile creation instead of relying on fallback profile response only.
- Revisit password reset/change user flows so user-facing credential management is consistently Auth-hosted.

## Parallel Execution

| Workstream | Status | Owner role | Scope | Forbidden files | Dependencies | Validation evidence | Merge order |
|---|---|---|---|---|---|---|---|
| FE hosted Auth adapter | complete in this patch | Crypto AI frontend owner | `frontend/src/app/login/**`, `frontend/src/app/register/**`, `frontend/src/app/auth/**`, `frontend/src/lib/hostedAuth.ts`, `frontend/src/stores/authStore.ts`, `frontend/src/lib/api.ts` | exchange credentials, portfolio/trading/alerts logic, secrets | Auth consumer standard | `cd frontend && npm run build`; static credential-form scan | First |
| Backend compatibility marking | complete in this patch | Crypto AI backend auth owner | `backend/app/api/auth.py`, `backend/app/services/auth_service.py` | DB migrations, live data, deploy/k8s | Existing `/auth/validate` dependency behavior | backend tests if safe/discoverable; diff check | After FE adapter |
| BFF session hardening | dependency-gated | future integration owner | new server session/cookie adapter and callback exchange | live secrets, broad API refactor | [MISSING: approved Crypto AI BFF session design] | future auth tests and hosted callback smoke | After current migration |
| Proxy removal | blocked | future cleanup owner | remove `/api/auth/login|register` credential proxies | protected route validation | [MISSING: confirmation no active client depends on proxy endpoints] | API compatibility tests | Last |

Shared contract: Auth-hosted redirect URLs, `client_id=crypto-ai-agent`, callback fragment fields, state validation, and Auth `/auth/validate` protected API behavior.

Integration owner: Crypto AI auth modernization integration owner.

Validation owner: Crypto AI Wave 2 worker for this patch; future BFF/proxy cleanup owner for remaining debt.

## Dependency Maintenance Validation - 2026-06-24

Status: build blocker resolved for the hosted Auth migration slice.

Changes added after initial validation:

- Synchronized frontend lockfile with the tracked Next 16 / React 19 package manifest.
- Added frontend `.npmrc` with `legacy-peer-deps=true` so clean installs use the same dependency resolution as the successful validation install.
- Updated frontend build script to `next build --webpack` because the repo has an existing custom webpack alias configuration and Next 16 defaults to Turbopack.
- Accepted the minimal Next 16 TypeScript compatibility edits generated by the build: route types import in `next-env.d.ts`, `jsx: react-jsx`, and `.next/dev/types/**/*.ts` include.

Validation evidence:

- `cd frontend && npm ci` passed.
- `cd frontend && npm run type-check` passed.
- `cd frontend && npm run build` passed with `next build --webpack` and included `/auth/callback`, `/login`, and `/register`.

Residual non-auth debt observed during validation:

- npm audit reports 16 vulnerabilities in the existing dependency graph.
- Next warns that the `middleware` file convention is deprecated in favor of `proxy`.
- `baseline-browser-mapping` data is stale.
