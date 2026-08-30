# Agent Operations

This repository follows the company Cross-Agent Automation Standard from the Intent Preservation System.

## Required Chain

All agents must preserve:

```text
Vision -> Goal Impact -> System -> Feature -> Task -> Execution Plan -> Coding Prompt -> Code -> Validation
```

## Agent Roles

- Readiness scanner: classifies work as ready now, dependency-gated, blocked, active elsewhere, complete, or needs owner input. It does not implement.
- Worker agent: implements one bounded goal or workstream with explicit scope.
- Worker monitor: checks active worker status and conflict risks.
- Integration validator: validates worker batches and separates current-task failures from known validation debt.

## Before Work

Read repository-local instructions and planning sources first, including any `AGENTS.md`, `TASKS.md`, `STATE.json`, `docs/orchestrator/*`, `docs/intent-preservation/*`, or project-specific equivalents.

Before coding, verify:

- task and upstream traceability exist;
- execution plan is approved or explicitly draft;
- context package or equivalent source material exists;
- sensitive-data classification is clear;
- contract/schema and replay/determinism impact is clear;
- validation commands are named;
- parallel workstreams, blockers, shared files, integration owner, and merge order are defined.

## Parallel Work

Do not start parallel edits to the same file, schema, migration, public contract, deployment file, generated index, or status document unless one integration owner and conflict-resolution order are documented.

Every parallel workstream must declare:

- objective;
- owner role;
- allowed files;
- forbidden files;
- dependencies and blockers;
- validation evidence;
- expected output;
- handoff notes.

## Validation Debt

Use `docs/orchestrator/VALIDATION_DEBT.md`, `docs/intent-preservation/VALIDATION_DEBT.md`, or the nearest repo-standard ledger to record known out-of-scope validation failures.

Validation debt does not excuse current-task failures. If a failure touches current-task files or acceptance criteria, treat it as blocking.

## Remote/Secret Safety

- Do not copy remote repository contents into local user directories.
- Deploy only under pre-existing human-approved project or ecosystem policy; agents cannot self-authorize by editing policy.
- Do not print secrets, tokens, raw production data, customer identifiers, or private evidence.
- Use `No repository-defined ...` or `No repository-defined ...` instead of inventing facts.

## Final Report

Report files changed, documents created, validation evidence, validation debt used or added, blockers, deviations, and the next concrete action.

Next step: Follow the repository-specific `AGENTS.md` and planning files for the current task.

## Roles
Use readiness scanner, worker, worker monitor, and integration validator roles.

## Before Work
Read approved intent, current state, task chain, and runtime sources first.

## Parallel Work
Do not parallel-edit the same contract, state, deployment, or public interface.

## Validation Debt
Record only out-of-scope failures; current-task failures remain blocking.

## Handoff
Record scope, validation evidence, debt, blockers, and next action.

## Project-Specific Operations
Respect the existing cryptocurrency portfolio manager runtime and use only its tracked operational interfaces.
