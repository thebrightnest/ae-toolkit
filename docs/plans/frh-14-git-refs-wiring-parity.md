---
id: frh-14-git-refs-wiring-parity
size: M
blocked_by:
  - frh-13-git-refs-backend-core
pipeline: standard
---

# Plan: GitRefsBackend Wiring, Sealing Hook, Parity Suite, and A/B Findings

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G8)

Two couplings block a clean opt-in: `backends/factory.py` only knows `json|github|both`, and `_apply_transition` seals terminal tasks by calling `queue_lib.seal_terminal(backend.queue_file, ...)` — a file-path assumption that breaks any non-file backend. This plan routes sealing through the backend interface, wires the config, proves behavioral parity, and writes the A/B findings report the owner asked for.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Add `seal(task_id, history_file)` to `TaskBackend` with a default file-based implementation (current `seal_terminal` behavior); `GitRefsBackend` overrides (drop the task's ref + append to history JSONL); `aet-state:_apply_transition` calls `backend.seal(...)` instead of `queue_lib.seal_terminal(backend.queue_file, ...)` — M
2. `backends/factory.py`: `task_backend: "git-refs"` → `GitRefsBackend`; `aet-setup/bin/configure-task-backend`: offer the new option with a "prototype, opt-in" note — S
3. Parity suite `tests/test_git_refs_parity.py` (new): run the same scenario script against a JSON-backed and a refs-backed queue — transition chain planned→ready→in_progress→awaiting_merge→merged (with a real merged branch fixture), set-stage, dependent promotion, sealing — and assert equivalent observable outcomes (states, history entries, settled records) — M
4. A/B findings report `docs/audits/2026-07-git-refs-backend-ab.md`: parity results, timing comparison of the parity scenarios on both backends, worktree-visibility demonstration, known gaps (e.g. multi-task save granularity), recommendation for/against promotion — S
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/lib/backends/base.py`
- `aet-work/lib/backends/json_backend.py` (inherit default `seal`)
- `aet-work/lib/backends/git_refs_backend.py`
- `aet-work/lib/backends/factory.py`
- `aet-work/bin/aet-state`
- `aet-setup/bin/configure-task-backend`
- `tests/test_git_refs_parity.py` (new)
- `docs/audits/2026-07-git-refs-backend-ab.md` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes (including the JSON-backend suite against the refactored sealing path)
- [ ] New source coverage — `tests/test_git_refs_parity.py`:
  - `test_transition_chain_parity`
  - `test_set_stage_parity`
  - `test_dependent_promotion_parity`
  - `test_sealing_parity_settled_history_identical`
- [ ] With `.agents/aet-work.json` set to `git-refs` in a scratch repo: `aet-state transition` and `set-stage` behave identically to JSON mode (manual spot-check recorded in the A/B report)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `task_backend: "git-refs"` configs fail loudly back to an unknown-backend error, and JSON remains the default throughout.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_
