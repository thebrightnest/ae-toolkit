---
id: ewl-04-git-refs-default-flip
size: S
blocked_by:
  - cli-03-skills-lint
  - uct-01-usage-cost-telemetry
pipeline: standard
security_review: skipped
security_review_reason: flips a default between two backends already implemented and parity-tested (frh-13/14); no new code path or trust boundary introduced
docs_sync: required
docs_sync_reason: configure-task-backend messaging and backend-selection docs currently describe git-refs as "prototype, opt-in" — that framing becomes incorrect once it is the default
---

# Plan: git-refs Becomes the Default Task-Storage Backend

## Context

- PRD: `docs/prds/roadmap-p3-enforcement-walls-prd.md` (G3; R-5, plus R-8 tests)
- `aet-work/lib/backends/factory.py` (frh-14) maps the `task_backend` config key to a backend class, currently defaulting to `JsonBackend` when unset. `GitRefsBackend` (frh-13) is fully implemented and, per frh-14's parity suite (`tests/test_git_refs_parity.py`), behavior-equivalent to the JSON backend for all existing operations.
- This plan changes only the default — it does not remove the JSON backend, which remains available as an explicit `task_backend: "json"` opt-out (Non-Goal in the PRD: "demoted to disposable projection/cache" describes the JSON backend's new _role_, not its removal).
- `aet-setup/bin/configure-task-backend` currently frames git-refs as a "prototype, opt-in" choice; that messaging is now stale once this plan lands and must change alongside the default.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `aet-work/lib/backends/factory.py`: flip **both** unset-default sites to `GitRefsBackend` — the `config.get("task_backend", "json")` fallback (`factory.py:31`, for a config dict present but missing the key) **and** `_read_config`'s no-config-file return `{"task_backend": "json"}` (`factory.py:56-57`), plus the docstring's "`json` (default), `git-refs` (prototype, opt-in)" framing (`factory.py:24-26`). The second site is load-bearing and easy to miss: a genuinely fresh install has no `.agents/aet-work.json`, so it never reaches line 31's `.get` default — line 57 governs, and if only line 31 is flipped, R-5's acceptance criterion ("a fresh `aet-setup` run yields git-refs") silently fails while the unit test on the key-absent path still passes. Explicit `task_backend: "json"` and `task_backend: "git-refs"` both continue to work unchanged.
- `aet-setup/bin/configure-task-backend`: update prompt/messaging so git-refs is presented as the default, JSON as the documented fallback/opt-out (reverse of today's framing) — no change to the mechanics of how the choice is written to config.
- No change to `GitRefsBackend` or `JsonBackend` implementations themselves in this plan — this is a default-selection change plus the messaging and test-default-assertion that follow from it. (Tamper-evidence for `GitRefsBackend` is ewl-05, a separate plan, so this flip does not silently ship a backend with weaker integrity guarantees than the one it replaces as default — ewl-05 is sequenced to land alongside or before this default takes effect in practice, per the PRD's phase-closing R-7/R-8.)

## Rejected Alternatives

- **Remove `JsonBackend` entirely** — rejected: explicit Non-Goal in the PRD; existing installs that pinned `task_backend: "json"` must keep working, and the parity suite's continued existence depends on both backends still being real, selectable code paths.
- **Bundle the tamper-evidence work (R-6) into this plan** — rejected: R-5 (default flip) and R-6 (integrity mechanism) are independently testable and independently revertible; keeping them separate lets the flip merge as soon as the parity suite is green against the new default, without waiting on the tamper-evidence design to land first.

## Task List

1. Flip **both** unset-default sites in `aet-work/lib/backends/factory.py` to `GitRefsBackend`: the `config.get("task_backend", "json")` fallback (`:31`) and `_read_config`'s no-file return `{"task_backend": "json"}` (`:56-57`); update the docstring framing (`:24-26`) — S (traces: R-5)
2. Update `aet-setup/bin/configure-task-backend` messaging: git-refs as default, JSON as explicit opt-out — S (traces: R-5)
3. Extend `tests/test_git_refs_parity.py` (or the factory's own test file) with an explicit assertion that the _no-config_ factory output is `GitRefsBackend` — S (traces: R-5, R-8)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition to anything queued
- [x] Diff expected ≤ 60 lines / 3 files
- [x] Cannot share a branch with ewl-05 — this changes the default selection, ewl-05 changes the backend's internal integrity mechanism; independently revertible

## Files to Modify

- `aet-work/lib/backends/factory.py`
- `aet-setup/bin/configure-task-backend`
- `tests/test_git_refs_parity.py`

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] `tests/test_git_refs_parity.py::test_default_backend_is_git_refs_when_unconfigured` (new) — unit: factory returns `GitRefsBackend` for **both** unset paths — (a) a config dict present but missing `task_backend`, and (b) no config file at all (`_read_config`'s no-file fallback). Case (b) is the one guarding R-5's fresh-install acceptance criterion; a test covering only (a) would pass while a fresh install still gets JSON.
- [ ] Full `tests/test_git_refs_parity.py` suite still green against the new default (frh-14's existing parity cases re-run, now exercising the default path rather than an explicit opt-in)
- [ ] Manual: a fresh `aet-setup` run with no prior config yields git-refs as the active backend (satisfies PRD acceptance criterion for R-5)
- [ ] R-trace coverage: R-5 by tasks 1–3; R-8 by task 3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit — factory default returns to `JsonBackend`. Any queue already migrated to git-refs by an install that picked up this default keeps working (git-refs remains a valid explicit choice), it just stops being what a _fresh, unconfigured_ install gets.

## Pipeline

`pipeline: standard`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
