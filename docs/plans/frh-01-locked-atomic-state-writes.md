---
id: frh-01-locked-atomic-state-writes
size: M
blocked_by: []
pipeline: standard
---

# Plan: Locked, Atomic Queue Writes in the State Layer

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G1)
- Source finding: `content/fable-review/01-2026-07-09-technical-assessment.md` critical issue #1
- Evidence: `.agents/learnings.jsonl` 2026-07-09T08:22Z records queue drift during a real batch run

`aet-state` has its own non-atomic `save_queue` (`aet-work/bin/aet-state:48-51`, plain `open(path, "w")`) while `lib/queue.py:140-177` has a correct atomic writer (tempfile + fsync + `os.replace`). `cmd_set_stage` uses raw local `load_queue`/`save_queue` while every other command goes through the backend. Nothing in the codebase takes a lock, yet batch mode runs up to 8 concurrent children invoking `aet-state set-stage` against one file.

This plan makes the state layer's writes locked and atomic. The orchestrator's own read-modify-write cycles are frh-02.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (hardening of a latent race; no isolated repro exists), not a reproducible defect report

## Task List

1. Add `queue_lock(queue_file)` context manager to `aet-work/lib/queue.py` — `fcntl.flock(LOCK_EX)` on a sidecar `<queue_file>.lock` file, blocking; stdlib only; safe under nesting via reentrant counter keyed by path — S
2. In `aet-work/bin/aet-state`: delete the local `load_queue`/`save_queue` (lines 36-51); route `cmd_set_stage` through `make_backend` like every other command (envelope preservation comes free via `queue_lib.read_queue`/`write_queue`) — S
3. Wrap every `aet-state` load→mutate→save cycle in `queue_lock`: `cmd_set_stage`, `cmd_transition`, `cmd_record_merge`, `cmd_heal` (per-change reload loop), `cmd_archive`, `cmd_sync_footers`, including the `seal_terminal` call inside `_apply_transition` — M
4. Write `tests/test_concurrent_state.py`: multiprocess hammer test (4 processes × 10 `set-stage`/`transition` ops on distinct tasks against one queue file) asserting zero lost updates and valid JSON on every intermediate read; atomicity test asserting a reader never sees a partial file — M
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-02 depends on this landing first)

## Files to Modify

- `aet-work/lib/queue.py` (add `queue_lock`)
- `aet-work/bin/aet-state` (delete raw load/save; backend + lock everywhere)
- `tests/test_concurrent_state.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] Full suite passes: `python3 -m pytest tests/ -q`
- [ ] New source coverage — `tests/test_concurrent_state.py` (integration, real git-less tmp queue files):
  - `test_parallel_set_stage_no_lost_updates` (4 writer processes, all stage records present afterward)
  - `test_parallel_transitions_valid_json_every_read` (reader loop during writes never gets `JSONDecodeError`)
  - `test_set_stage_routes_through_backend_and_preserves_envelope` (dict-wrapper metadata survives `set-stage`)
  - `test_queue_lock_reentrant_same_process`
- [ ] Grep gate: `grep -n 'open(path, "w")' aet-work/bin/aet-state` returns nothing
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The lock file is a sidecar (`.agents/work-queue.json.lock`) ignored by git; deleting it is always safe.

---

_Stage: implemented_
_Next step: run `aet-qa`_
