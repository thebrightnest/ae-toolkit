---
id: gib-05-board-projection-machinery
size: M
blocked_by:
  - gib-02-projection-axis-fail-open-dispatcher
pipeline: standard
status: draft
security_review: skipped
security_review_reason: label mirroring through gib-02's fail-open dispatcher; one-way, read-nothing-back, and the only remote credential is the operator's own `gh` auth. No new trust boundary beyond the `gh` calls already present in the file; the write can never gate or block a local state change.
docs_sync: required
docs_sync_reason: the label contract (state → `aet:*`, plus `draft`/`backlog`) and id-keyed issue identity are documented in `aet-work/references/github-backend.md`.
---

# Plan: GitHub Board Projection Machinery

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-13, R-14, R-15, R-16).
- **Ground truth (2026-07-17):** `STATE_LABELS` is missing `quarantined` (added to `STATES` by `nsr-02`, 2026-07-16) and has no `draft`/`backlog` values. `_update_issue_labels` finds issues by `github_issue_number` else falls back to `_find_issue_by_title` — brittle across clones. `ensure_labels()` exists but is never called. `on_transition`/`close_task` are already wired at `aet-state:312/323`.
- Implements the GitHub `Projection` against gib-02's interface. Consumed by gib-06 (commands) and gib-07 (reconcile).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**; folds in the `quarantined` label gap (R-14)

## Locked design

- **Complete the label map.** Add `draft`, `backlog`, and `quarantined` to `STATE_LABELS` (+ colors). A **parity test** asserts every member of `STATES` plus `draft`/`backlog` has a label — so a future state addition fails CI, not silently in production.
- **Id-keyed identity.** Issue lookup keys on plan id (embedded in the issue via a stable marker — a `aet-id:{plan-id}` line in the body or a hidden label), not title. `_find_issue_by_title` is removed as the identity path. This makes creation idempotent across clones (gib-06 relies on it).
- **Provisioning is called.** `ensure_labels()` runs on first projection use (lazy, once), so labels exist before the first `on_add`.
- **Re-home remote methods.** The `sync_task`/`on_transition`/`close_task`/label logic moves onto the GitHub `Projection` class (off `TaskBackend`, per gib-02), mapping: pre-sprint plan `status` → `aet:draft`/`aet:backlog`; in-sprint queue `state` → `aet:<state>`; terminal → issue closed.

## Rejected Alternatives

- **Keep title-based lookup as a fallback** — rejected: titles change and collide; a single deterministic id key is the only cross-clone-safe identity, and dual paths reintroduce the drift.
- **Provision labels in `aet-setup`** — rejected: setup may run before a repo/remote exists; lazy first-use provisioning is self-healing and matches fail-open.
- **Hardcode the label list in the test** — rejected: the test must derive from `STATES` so it tracks the source of truth, which is the whole point of the parity guard.

## Task List

1. Add `draft`/`backlog`/`quarantined` to `STATE_LABELS` + colors; parity test binding to `STATES` — S (traces: R-14)
2. Id-keyed issue identity (stable marker); remove title-based identity path — M (traces: R-13)
3. Lazy `ensure_labels()` on first projection use — S (traces: R-14)
4. Re-home remote/label methods onto the GitHub `Projection`; map status/state → label; close on terminal — M (traces: R-15, R-16)
5. Tests: rework `tests/test_github_backend.py` → `tests/test_github_projection.py` — M (traces: R-13, R-14, R-15, R-16)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — the projection implementation surface

## Files to Modify

- `aet-work/lib/backends/github_backend.py` (→ projection; label map, identity, provisioning)
- `aet-work/references/github-backend.md`
- `tests/test_github_backend.py` → `tests/test_github_projection.py`

## Validation Steps

- [ ] `make validate` passes
- [ ] New/reworked source coverage — `tests/test_github_projection.py`:
  - `test_state_labels_cover_all_states` (parity; would fail today on `quarantined`)
  - `test_issue_identity_is_plan_id_not_title`
  - `test_ensure_labels_runs_on_first_use`
  - `test_draft_and_backlog_labels_from_plan_status`
  - `test_transition_relabels_and_removes_prior`, `test_terminal_closes_issue`
- [ ] R-trace coverage: R-13 (t2), R-14 (t1, t3), R-15/R-16 (t4); no unknown R-ids
- [ ] Distinguish test types: unit (label map, identity, mapping) — `gh` mocked; live behavior is gib-08's job
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The projection loses `draft`/`backlog`/`quarantined` and id-keyed identity; since nothing shipped consumes it until gib-06, no user-facing regression.

## Pipeline

`pipeline: standard` — projection implementation with a mocked-remote test surface; standard grouping is sufficient.

---

_Stage: implemented_
_Next step: run `aet-qa`_
