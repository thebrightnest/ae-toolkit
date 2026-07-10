---
id: frh-08-dead-layer-deletion
size: M
blocked_by:
  - frh-03-process-group-kill
  - frh-07-status-retirement-state-bin
pipeline: standard
---

# Plan: Delete the Dead Layer — Backend `transition`, Verifier Retries, `estimate_repo_size`

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G5)
- Source finding: technical assessment "Dead and vestigial code"

`TaskBackend.transition` (`backends/base.py:37`, `json_backend.py:43`, `github_backend.py:84`) is a complete **parallel implementation of the state machine called only by tests** — and it's wrong relative to the real one: no dependent promotion, no sealing, no timestamps. Tested dead code reads as alive; frh-13's `GitRefsBackend` must not be forced to implement it. `verify_stage_advancement`'s retry loop (`verifier.py:51-73`) sleeps and re-compares a local variable that cannot change; every call site passes `retries=0`. `estimate_repo_size` (`worktree.py:193`) has zero callers and its `du -sb` doesn't work on macOS.

Blocked on frh-03 (last writer in the orchestrator chain — this plan touches the orchestrator's `verify_stage_advancement` call sites) and frh-07 (vocabulary settled so backend deletions rebase cleanly).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Delete the abstract `transition` from `backends/base.py` and both implementations (`json_backend.py`, `github_backend.py`); move the GitHub label/close side-effects fully onto the existing `on_transition`/`close_task` hooks if any test relied on `transition` for them — M
2. `verifier.py`: reduce `verify_stage_advancement` to a single comparison + commit check; drop the `retries` parameter and the `time` import; update both orchestrator call sites (`retries=0` args removed) — S
3. `worktree.py`: delete `estimate_repo_size` — S
4. Update tests: delete `transition` tests from `tests/test_backends.py` and `tests/test_github_backend.py` (keep `on_transition`/`close_task` coverage); adjust any `verify_stage_advancement` signatures in `tests/test_orchestrator.py` — M
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines (net-negative diff)
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/lib/backends/base.py`
- `aet-work/lib/backends/json_backend.py`
- `aet-work/lib/backends/github_backend.py`
- `aet-work/lib/verifier.py`
- `aet-work/lib/worktree.py`
- `aet-work/bin/orchestrator` (two call-site signature updates only)
- `tests/test_backends.py`
- `tests/test_github_backend.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] No new source files → no new named tests; deletions covered by:
  - `test_backends.py` still exercising `load`/`save`/`plan_drift`/`sync_task`
  - `test_github_backend.py` still exercising `on_transition` label updates and `close_task`
- [ ] Grep gates: `grep -rn "def transition" aet-work/lib/backends/` returns nothing; `grep -rn "estimate_repo_size\|retries" aet-work/lib aet-work/bin` returns nothing (excluding history/docs)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; all deletions restore cleanly from git history.

---

_Stage: reviewed_
_Next step: merge — review completed in-session after the aet-review child hit a transient provider connection error; objective gates green (`make validate`: 309 tests, lint, format, skill structure)_
