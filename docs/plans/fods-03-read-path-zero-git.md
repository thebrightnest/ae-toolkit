---
id: fods-03-read-path-zero-git
blocked_by:
  - fods-02-state-spine
size: M
---

# Plan: Read Path Reads Stored State (Zero Git); `derive` → `audit`

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream B, criteria 4–5)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decision 3)

With state recorded forward (`fods-02`), `status`, `next`, and the orchestrator must return stored `state` and make **zero git calls** — today they each shell out to `aet-state derive`, which runs git per task (the orchestrator 3× per loop). The old `derive` leaves the hot path and becomes `aet-state audit`: an explicit, human-run reconcile against git that never runs during normal operation.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **`status` reads stored `state`** — S (`aet-work/bin/status`)

   Drop the `derive_statuses` subprocess. Render counts, next-ready, failed, and worktree health from stored `state`. No git, no subprocess on this path.

2. **`next` reads stored `state`** — S (`aet-work/bin/next`)

   Pick the first `state == "ready"` task in topological order; transition `ready`→`in_progress` via `aet-state transition`. Remove the `derive` call.

3. **Orchestrator reads stored `state`** — M (`aet-work/bin/orchestrator`)

   Replace the three `derive_statuses()` calls per loop with stored-state reads; spawn tasks whose `state == "ready"`; the pending check uses stored non-terminal states. Route the pipeline-success write (`awaiting_merge`) through `aet-state transition`.

4. **Repurpose `derive` → `audit`** — S (`aet-work/bin/aet-state`)

   Rename `cmd_derive` → `cmd_audit`; keep the git reconciliation logic but make it report stored-vs-git discrepancies **without mutating**. Remove the `derive` subcommand; register `audit`.

5. **Read-path no-git guard test** — M (`tests/test_read_path_no_git.py`, update `tests/test_aet_work_read_side.py`, `tests/test_orchestrator_derived.py`)

   New test stubs `subprocess.run`/git so that any git invocation on the `status`/`next`/orchestrator read path **fails the test**. Update existing read-side tests to assert stored-state behavior.

6. **Merge branch to main and verify integration** — S

## Blocked by

- fods-02-state-spine

## Validation Steps

- [ ] `tests/test_read_path_no_git.py` fails if `status`/`next`/orchestrator invoke a git subprocess on read.
- [ ] `aet-state derive` no longer exists; `aet-state audit` exists and never runs during `status`/`next`/orchestrator.
- [ ] `status` and `next` output is a projection of stored `state`.
- [ ] `tests/test_aet_work_read_side.py` and `tests/test_orchestrator_derived.py` updated and passing.
- [ ] `make validate` passes.

## Rollback Plan

Revert `status`, `next`, `orchestrator`, and the `derive`→`audit` rename in `aet-state`. fods-02's writer is unaffected.

---

_Stage: implemented_
_Next step: run `aet-qa`_
