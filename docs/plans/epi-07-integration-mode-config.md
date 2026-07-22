---
id: epi-07-integration-mode-config
size: M
blocked_by: [epi-01-base-branch-resolver]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: adds a config key resolved through the existing chain; no behavior change in this plan
docs_sync: required
docs_sync_reason: introduces integration_mode as user-facing project configuration
---

# Plan: Add `integration_mode` with Scenario A as the degenerate case

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-14)
- ADR: `docs/adr/045-epic-integration-branch-and-task-integration-mode.md`
  (decision 1)

This plan adds the mode and nothing else. It is behavior-neutral by design:
`pr-per-task` with `integration_branch == trunk_branch` must run the same code
path as today, and this plan proves it does before `epi-08` builds `single-pr`
on top. Splitting the config surface from the behavior keeps the
regression-guard diff reviewable on its own.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **`integration_mode` is project configuration**, resolved through the
  external-first chain (`resolve_config()`, `src/aet/backends/factory.py:59`) —
  same as `trunk_branch` (ADR-044 decision 1). No second config reader.
- **Two values, one default.** `pr-per-task` (default) and `single-pr`. An
  unrecognized value fails closed at resolution with a message naming the key
  and the legal values — a typo must not silently select a mode.
- **Resolved once per run**, alongside the branch refs (`epi-02` already
  establishes resolve-once for refs). Three resolutions can disagree if config
  changes mid-run.
- **Scenario A is a set of values, not a branch beside the path.** In this plan
  the orchestrator reads the mode and selects `pr-per-task` behavior, which is
  today's behavior unchanged. There is no `single-pr` code yet — `epi-08`.
- **The regression guard is a command-sequence assertion**, not a code read:
  with `pr-per-task` and `integration_branch == trunk_branch`, the
  orchestrator's git command sequence is identical to before this work (PRD
  acceptance criterion for R-14).

## Task List

1. Resolve `integration_mode` through `resolve_config()` with fail-closed
   validation of the value — S (traces: R-14)
2. Thread the resolved mode into the orchestrator run context, resolved once
   per run, selecting today's behavior for `pr-per-task` — M (traces: R-14)
3. Assert the `pr-per-task` git command sequence is unchanged from before this
   work — S (traces: R-14)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one config key and its
      threading
- [ ] The diff is expected to exceed 3 files or 50 lines — borderline; kept
      separate for reviewability of the regression guard, not for size
- [x] Cannot share a branch with `epi-08` — `epi-08` changes behavior; mixing
      it with the no-behavior-change guard would make the guard unverifiable

## Rejected Alternatives

- **Add the mode inside `epi-08`** — rejected: the Scenario-A regression guard
  (PRD R-14 acceptance criterion) is only meaningful when the mode exists but
  no `single-pr` behavior does. Collapsing them removes the proof.
- **Infer the mode from `integration_branch != trunk_branch`** — rejected: a
  repo with a long-lived integration branch (ADR-044's config-fallback case)
  would silently flip modes. The mode is an explicit choice.
- **Per-run `--mode` flag** — rejected: the mode is a property of how the
  project integrates, not of one run; ADR-045 makes it project configuration.
  (`integration_branch` is the per-run input; the mode is not.)

## Files to Modify

- `src/aet/backends/factory.py`
- `src/aet/cli/orchestrator.py`
- `tests/backends/test_integration_mode_config.py` (new)
- `tests/orchestrator/test_pr_per_task_unchanged.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/backends/test_integration_mode_config.py`
      covers both legal values, the default when unset, and fail-closed
      rejection of an unrecognized value through each rung of the
      external-first chain
- [ ] New source coverage: `tests/orchestrator/test_pr_per_task_unchanged.py`
      asserts the git command sequence under `pr-per-task` with
      `integration_branch == trunk_branch` matches the pre-change sequence
- [ ] The mode is resolved once per run, not per task
- [ ] R-trace coverage: R-14 covered by tasks 1–3
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Nothing downstream depends on the mode until `epi-08`, so
rollback is a pure deletion with no behavioral change to undo.

## Pipeline

`standard`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
