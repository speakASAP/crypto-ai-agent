# Repository Agent Instructions

Shared rules live here:

- Codex profile: `/home/ssf/.codex/AGENTS.md`
- Cross-agent standard: `/home/ssf/.ai-agent-standards/CROSS_AGENT_AUTOMATION_STANDARD.md`
- Repository operations: `AGENT_OPERATIONS.md`

Read those first, then follow the repository-specific notes below and the current planning/status files.


## Repository-Specific Notes

# Agents: crypto-ai-agent

## Coordinator Config

```yaml
model_tier: cheap
cycle_interval_minutes: 30
max_tasks_per_cycle: 10
```

## Worker Pool Config

```yaml
max_concurrent_workers: 3
default_model_tier: free
allowed_mcp_servers: [filesystem, postgres]
```

## Typical Task Types

- analyze_market_trend
- generate_price_alert_report
- write_portfolio_summary

## Active Agents
<!-- Coordinator-maintained -->

## Required Reading
Read `BUSINESS.md`, `SYSTEM.md`, `TASKS.md`, `STATE.json`, runtime manifests, and numbered IPS artifacts before work.

## Authority
Git-tracked repository contracts are authoritative; protected intent needs owner approval.

## Intent Preservation System
Preserve Vision to Goal Impact to System to Feature to Task to Execution Plan to Coding Prompt to Code to Validation.

## Safety and Operations
Do not expose secrets or alter deployment policy outside pre-existing authorization.

## Project-Specific Rules
Keep changes within the documented cryptocurrency portfolio manager scope and runtime boundaries.

## Required Final Report
Report changed files, validation evidence, debt, blockers, deviations, and next action.
