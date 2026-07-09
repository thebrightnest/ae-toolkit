---
id: frh-03-process-group-kill
size: S
blocked_by:
  - frh-02-orchestrator-locked-writes
pipeline: standard
---

# Plan: Process-Group Spawning and killpg on Timeout

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G2)
- Source finding: technical assessment critical issue #2

`run_batch` spawns children with plain `Popen` (`orchestrator:764`). On timeout it calls `proc.terminate()` then `proc.kill()` (`:790-798`, same pattern in the `finally` cleanup at `:816-825`). The child's SIGTERM handler only sets a flag checked between stages, and the child is blocked in `subprocess.run` waiting on the agent CLI — so SIGKILL is what lands, killing the child orchestrator but **not the grandchild `claude`/`kimi` process**, which keeps burning tokens and writing into a worktree that `_finalize_task` then removes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (hardening; orphan leak has no recorded repro), not a reproducible defect report

## Task List

1. Spawn batch children with `start_new_session=True`; on timeout and in `finally` cleanup, escalate via `os.killpg(os.getpgid(proc.pid), SIGTERM)` → bounded wait → `killpg(..., SIGKILL)`; guard `ProcessLookupError`/`PermissionError` — S
2. Add test: batch child spawns a long-lived grandchild (`sh -c 'sleep 300'` stand-in for the agent CLI); force a timeout; assert the grandchild's process group is dead before `_finalize_task` removes the worktree — M
3. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines (test is the bulk)
- [x] Cannot share a branch with related tasks (serialized on the orchestrator file)

## Files to Modify

- `aet-work/bin/orchestrator`
- `tests/test_orchestrator.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] Named tests: `test_timeout_kills_grandchild_process_group`, `test_cleanup_kills_process_groups_on_shutdown` (integration, real processes)
- [ ] Manual spot-check: `pgrep` for the stand-in grandchild after a forced-timeout run returns nothing
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Behavior falls back to child-only kill; no data changes.

---

_Stage: implemented_
_Next step: run `aet-qa`_
