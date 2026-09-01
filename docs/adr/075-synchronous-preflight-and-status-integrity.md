---
subject: orchestrator-preflight-integrity
---

# Synchronous Preflight Validation and Status Truthfulness

## Status

Accepted (2026-09-01). Extends ADR-030 (Night-Shift Failure Handling) and ADR-033 (Projections Fail Open, Storage Fails Closed).

Implements the decision record of [docs/prds/orchestrator-status-and-preflight-integrity-prd.md](../prds/orchestrator-status-and-preflight-integrity-prd.md).

## Context

When launching orchestrator runs via `aet run` or `aet run-one`, the CLI immediately dispatches a detached subprocess (`start_new_session=True`), prints `🚀 Started run <id>`, and exits with code 0. However, orchestrator preflight checks (such as systemic circuit breaker state verification, queue integrity, and adapter binary resolution) previously ran only inside the background child process.

If preflight validation failed (e.g. `refs/aet/breaker` tripped by 3 repeated failure signatures across distinct tasks), the background process logged the failure and exited immediately. Because `aet run` had already returned exit code 0, the operator/caller was left with a false assertion that tasks were executing.

Additionally, `aet status` historically inspected only queue tasks and worktrees without inspecting `refs/aet/breaker` or recent run telemetry. As a result, `aet status` reported tasks as `ready` and declared "No failed tasks" even when the orchestrator was hard-blocked by a tripped circuit breaker.

Finally, managing the circuit breaker required direct low-level git ref commands (`git update-ref -d refs/aet/breaker`), and unit tests risked polluting the host repository's git refs when unisolated fixtures were used.

## Decision

1. **Preflight validation is synchronous before detachment.** `aet run` and `aet run-one` perform all precondition checks (systemic circuit breaker, queue integrity, CLI binary existence, and worktree base branch) in the foreground CLI process before calling `_spawn_detached`. If preflight fails, the command prints the diagnostic error to stderr and exits with non-zero code immediately without announcing a run start.
2. **`_spawn_detached` validates child process vitality.** After spawning the detached process, `_spawn_detached` checks that the child PID remains alive past the initial launch window before returning 0.
3. **`aet status` reports circuit breaker state and last-run health.** `aet status` loads `refs/aet/breaker` via `BreakerStore` and displays a prominent warning banner if the systemic circuit breaker is tripped. When no active runs are detected, `aet status` inspects the latest telemetry run record and reports if the previous run terminated with a failure.
4. **First-class CLI commands for circuit breaker lifecycle.** The CLI introduces `aet breaker show` and `aet breaker reset` to provide declarative inspection and reset of `refs/aet/breaker`.
5. **Strict test isolation for git-backed stores.** All tests exercising `BreakerStore` or orchestrator execution must target temporary isolated git repositories (`tmp_path`) and never write to the host checkout's git refs.

## Consequences

- Silent startup failures during orchestrator batch or single runs are eliminated.
- Operators and managing agents receive immediate, truthful feedback about run health and circuit breaker status in both `aet run` and `aet status`.
- Low-level git ref manipulation is replaced with declarative `aet breaker` CLI commands.
