---
id: liveness-01-hybrid-supervision
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes session supervision and process management
docs_sync: required
docs_sync_reason: Updates supervision behavior documented in PIPELINE.md
---

# Plan: Hybrid Liveness Supervision

## Context

PRD: `docs/prds/orchestrator-liveness-and-validation-redesign-prd.md`

The orchestrator's stall watchdog currently measures stdout silence on the agent CLI. Agents can be alive and working while silent — waiting on background Bash tasks, subagents, or long validations whose output does not stream through the CLI. This causes false timeout kills. The redesign replaces stdout-silence detection with hybrid liveness: process-tree activity + run-log/file writes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Implement `ProcessTreeLiveness` probe that checks whether the session's process tree has active descendants — M (traces: R-1, R-2)
2. Implement `RunLogLiveness` probe that monitors run-log and telemetry file mtimes for writes — M (traces: R-1, R-2)
3. Replace `_run_with_live_tee`'s stdout-silence watchdog with the hybrid liveness detector — M (traces: R-1, R-2, R-3)
4. Update CLI adapter configuration to use uniform stall_timeout and wall_backstop values across all adapters (same logic, same values) — S (traces: R-2)
5. Add regression tests for hybrid liveness: alive background task survives, truly dead session is killed, wall-clock backstop still fires — M (traces: R-1, R-2, R-3)
6. Update `docs/PIPELINE.md` and `CONTEXT.md` with the new supervision model — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

Before finalizing this plan, confirm it should not be merged with a sibling plan. A plan is a floor candidate when **two or more** of the following signals are true. One checked box is a prompt to justify the shape in writing; two or more means merge unless you can explain why not.

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines; see `docs/CONVENTIONS.md`).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against (`blocked_by` that sibling, or blocked by it transitively).
- [ ] This is docs-only and its sole consumer is a single sibling.

Justification: This is the core supervision redesign. It stands alone as an independently shippable behavior change (sessions no longer die from false stalls). Merging with validation workflow plans would conflate two distinct concerns.

## Rejected Alternatives

- **Keep stdout-silence with longer timeout** — rejected: does not fix the fundamental mismatch; a 2-hour timeout just delays the false kill.
- **Explicit agent heartbeats** — rejected: requires changing the agent CLI or prompt contract; hybrid detection works without agent changes.
- **Process-tree only** — rejected: cannot distinguish "waiting on hung subprocess" from "working"; run-log writes provide the second signal.
- **Per-adapter timeout values** — rejected: ADR-053 calibrated values per adapter because output cadence differs, but with hybrid liveness the timeout is a backstop for true death, not a proxy for output cadence. Uniform values remove per-session variance and simplify reasoning. Supersedes ADR-053 item 2.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/cli_adapter.py`
- `tests/orchestrator/test_stall_watchdog.py`
- `docs/PIPELINE.md`
- `CONTEXT.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] For each new source file introduced by this plan, name the test that will cover it
  - `src/aet/liveness.py` (new) → `tests/orchestrator/test_liveness.py`
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The old stdout-silence watchdog is replaced atomically; no persistent state changes.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
