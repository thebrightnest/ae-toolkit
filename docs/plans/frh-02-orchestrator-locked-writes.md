---
id: frh-02-orchestrator-locked-writes
size: M
blocked_by:
  - frh-01-locked-atomic-state-writes
pipeline: standard
---

# Plan: Orchestrator Queue Mutations Under Lock; One Validated Failure Path

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G1)
- Depends on `queue_lock` from frh-01.

The batch orchestrator does unlocked read-modify-write on the queue while children write concurrently: `_finalize_task` loads at `orchestrator:673/680` and saves an unmodified stale copy at `:684` (pure lost-update window — a concurrent `set-stage` between load and save is silently reverted); spawn bookkeeping mutates worktree/branch at `:743-748`; `_record_run_one_in_queue` does the same at `:907-913`. `_mark_failed`'s fallback (`:536-542`) writes `task["state"] = "failed"` directly via `backend.save`, bypassing validation and history. `run_single` has a latent crash: `task = next(..., None)` at `:1002` rebinds `task`, and `:1029` calls `task.get("stage")` — `AttributeError` if the task was sealed mid-run. `references/context-isolation.md:148` claims no locking is required, which is false in batch mode.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (hardening; the crash path has no isolated repro), not a reproducible defect report

## Task List

1. Wrap each orchestrator load→mutate→save cycle in `queue_lock` (import from lib): spawn bookkeeping (`run_batch` worktree/branch recording), `_record_run_one_in_queue`, and `_finalize_task` — S
2. Restructure `_finalize_task` to stop re-saving an unmutated queue: only `backend.save` when the parent actually changed task fields; state changes stay with `aet-state transition` — S
3. Replace `_mark_failed`'s direct-write fallback: under `queue_lock`, re-read the task's current state and retry `aet-state transition <current> failed`; if no legal path to `failed` exists (e.g. already terminal), log loudly and write nothing. Post-condition: no code path in the repo assigns `task["state"]` outside `_apply_transition`/`_set_stage` — M
4. Fix the `run_single` None-rebind: keep the synthetic task dict separate from the queue lookup so the `:1029` footer/stage read cannot dereference `None` — S
5. Correct `aet-work/references/context-isolation.md:148`: queue mutations are serialized by the queue lock, not by the polling loop — S
6. Add tests (extend `tests/test_orchestrator.py`): finalize-vs-set-stage interleaving preserves the child's stage record; `_mark_failed` on an already-merged task leaves state untouched; `run_single` completes when the queue task disappears mid-run — M
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-03 continues in this file)

## Files to Modify

- `aet-work/bin/orchestrator`
- `aet-work/references/context-isolation.md`
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests (integration, real subprocess + tmp repo fixtures already used by `test_orchestrator.py`):
  - `test_finalize_preserves_concurrent_stage_write`
  - `test_mark_failed_fallback_never_writes_illegal_state`
  - `test_run_single_survives_task_sealed_mid_run`
- [ ] Grep gate: `grep -rn '\["state"\] *=' aet-work/bin/orchestrator` returns nothing
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; no data format changes.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
