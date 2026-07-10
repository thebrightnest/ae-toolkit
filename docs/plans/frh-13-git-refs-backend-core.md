---
id: frh-13-git-refs-backend-core
size: M
blocked_by:
  - frh-08-dead-layer-deletion
pipeline: standard
---

# Plan: GitRefsBackend Core — Git-Native Task Storage

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G8)
- Owner decision (2026-07-09): working opt-in backend, storage-only; never the default. Blocked on frh-08 so it does not implement the deleted `transition` method.
- Strategic rationale: `content/fable-review/02-2026-07-09-strategic-alternatives.md` §"Git-native state" — ref updates are atomic (git's own locking), refs are visible from every worktree (dissolves the relative-path triangle), and refs push/pull (distributed night shift).

Storage design (state legality stays entirely in `aet-state`):

- Live task record → JSON blob (`git hash-object -w`), ref `refs/aet/tasks/<task-id>` points at it; `save` = per-task `update-ref` (skipping unchanged blobs), refs deleted for tasks no longer in the queue (sealing).
- Queue envelope/wrapper metadata → blob at `refs/aet/meta/queue`.
- Settled history stays in `work-history.jsonl` (append-only, unchanged).
- Local-only by default: nothing pushes `refs/aet/*`; pushing is a documented manual choice.
- Concurrency semantics: single-ref updates are atomic under git's ref locks; a multi-task `save` is per-task granular, so concurrent writers touching different tasks never lose each other's writes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. New `aet-work/lib/backends/git_refs_backend.py` implementing the (post-frh-08) `TaskBackend` surface: `load` (`for-each-ref` + `cat-file` batch), `save` (hash-object + update-ref per changed task, prune removed refs, envelope ref), `plan_drift`, `sync_task` (no-op), `close` (no-op), `on_transition`/`close_task` (defaults) — M
2. Error surface: raise a clear error when the queue path's directory is not inside a git repository — S
3. Tests: `tests/test_git_refs_backend.py` (new) against real git repos using the existing conftest fixture style — M
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (frh-14 wires and proves parity)

## Files to Modify

- `aet-work/lib/backends/git_refs_backend.py` (new)
- `tests/test_git_refs_backend.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_git_refs_backend.py` (integration, real git repos):
  - `test_state_roundtrip_via_refs` (save → load equality including history entries)
  - `test_save_prunes_refs_for_sealed_tasks`
  - `test_wrapper_envelope_roundtrip`
  - `test_refs_visible_from_second_worktree`
  - `test_concurrent_saves_of_different_tasks_lose_nothing` (two processes, disjoint tasks)
  - `test_clear_error_outside_git_repo`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Until frh-14 wires the factory, nothing instantiates this class; `refs/aet/*` in a test repo can be dropped with `git for-each-ref refs/aet --format='%(refname)' | xargs -n1 git update-ref -d`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
