---
id: gib-02-projection-axis-fail-open-dispatcher
size: M
blocked_by: []
pipeline: standard
status: draft
security_review: required
security_review_reason: changes backend selection (deletes `github`/`both` as storage) and introduces a fail-open dispatcher that inverts the fail-closed kernel rule. The security-critical property is that fail-open is scoped strictly to projections and cannot leak into a storage write — must be verified, not asserted.
docs_sync: required
docs_sync_reason: the config schema gains a `projections` axis and loses `task_backend: "github"`/`"both"`; `aet-setup`'s SKILL, checklist, and references document the backend/projection contract.
---

# Plan: Projection Config Axis + Fail-Open Dispatcher

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-1, R-2, R-3, R-4, R-5).
- **Ground truth (2026-07-17):** `factory.py` selects one backend from `task_backend` ∈ {json, git-refs, github, both}. `github` routes storage to local JSON (load/save call `read_queue`/`write_queue`); `both` is `raise NotImplementedError`. `GitHubBackend`'s remote methods (`sync_task`/`on_transition`/`close_task`) are projection behavior mis-housed inside a `TaskBackend`. `_run_gh` raises `BackendError` on any non-zero exit — correct for storage, wrong for a mirror.
- Foundation task: gib-05 (board machinery) and gib-06 (commands) fan out through the dispatcher this task creates.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement** (with two latent defects folded in: the storage/projection conflation and the fail-closed mirror)

## Locked design

- **Config axis.** `create_backend` keeps selecting storage from `task_backend` ∈ {json, git-refs}. A new resolver reads `projections: [{type, ...}]` from the same external-first config (`ewl-07` order) and builds a **projection dispatcher** separate from the storage backend.
- **Delete forge-as-storage.** Remove the `github` and `both` branches from `factory.py`. Unknown `task_backend` (now including `github`/`both`) raises a named error pointing at the `projections` config. `GitHubBackend` stops implementing storage `load`/`save` — it becomes a `Projection`, not a `TaskBackend`.
- **Projection contract.** A small `Projection` interface: `on_add`, `on_transition`, `on_close`, `ensure_labels`, `reconcile`. gib-05 implements the GitHub one against it.
- **Fail-open dispatcher.** The dispatcher calls each projection inside a guard that catches every projection exception, writes a `warning:` line to stderr naming the projection and cause, and returns — the accompanying storage write/commit always proceeds. Storage writes keep raising. A test asserts a raising projection does not fail the storage path, and that a storage failure still raises (fail-open did not leak).

## Rejected Alternatives

- **Keep `task_backend: "github"` and add projections beside it** — rejected: the event/interface tax and the config lie (doc 10; PRD Overview); no config on the owner's machine selects it, so zero migration cost to cut.
- **Make the dispatcher a list of `TaskBackend`s** — rejected: conflates storage and projection again; a projection has no `load`/`save` and must never be asked for one.
- **Global try/except at each call site** — rejected: every future call site would have to remember the fail-open rule; centralizing it in the dispatcher makes it structural.

## Task List

1. Add `Projection` interface + projection resolver reading `projections` config (external-first) — S (traces: R-1)
2. Build the fail-open dispatcher: fan out, catch-and-warn per projection, never raise — M (traces: R-4, R-5)
3. Remove `github`/`both` from `factory.py`; named error on unknown `task_backend`; reclass `GitHubBackend` off `TaskBackend` (stub methods move in gib-05) — M (traces: R-2)
4. Update `aet-setup` SKILL/checklist/references: `task_backend` ∈ {git-refs, json}; document `projections` — S (traces: R-3)
5. Tests: `tests/test_projection_dispatcher.py` (new) — M (traces: R-4, R-5)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — foundational surface others depend on

## Files to Modify

- `aet-work/lib/backends/factory.py`
- `aet-work/lib/backends/base.py` (or new `projections/base.py`)
- `aet-work/lib/projections/dispatcher.py` (new)
- `aet-work/lib/backends/github_backend.py` (reclass; label/remote logic stays for gib-05)
- `aet-setup/SKILL.md`, `aet-setup/checklist.md`, `aet-setup/references/README.md`
- `tests/test_projection_dispatcher.py` (new)

## Validation Steps

- [ ] `make validate` passes; existing `tests/test_backends.py`, `tests/test_aet_setup_backend_config.py` updated for the removed values
- [ ] New source coverage — `tests/test_projection_dispatcher.py`:
  - `test_dispatcher_swallows_projection_error_and_warns`
  - `test_storage_write_proceeds_when_projection_raises`
  - `test_storage_failure_still_raises` (fail-open did not leak)
  - `test_unknown_task_backend_github_raises_named_error`
  - `test_projections_resolved_external_first`
- [ ] R-trace coverage: R-1 (t1), R-2 (t3), R-3 (t4), R-4/R-5 (t2, t5); no unknown R-ids
- [ ] Distinguish test types: unit (dispatcher guard, resolver) + integration (factory selection end to end)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Storage backend selection returns to the prior enum; the dispatcher and projection interface disappear. No data change — projections are additive and no config selected them before.

## Pipeline

`pipeline: standard` — touches backend selection and a security-relevant fail rule; standard grouping (TDD→implement→QA, review, CSO) is warranted.

---

_Stage: plan-approved_
