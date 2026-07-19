---
id: gib-07-backlog-add
size: M
blocked_by:
  - gib-05-board-projection-machinery
  - gib-06-command-groups-sprint-add
pipeline: standard
status: draft
security_review: required
security_review_reason: `aet backlog add` commits+pushes plan status and creates a real GitHub issue. A weak plan-id resolution could label or board the wrong plan; the issue creation must be idempotent by id so a re-run or a second clone never duplicates. The resolution and id-keyed creation are the correctness boundary.
docs_sync: required
docs_sync_reason: `aet backlog add` is new user-facing surface (the board entry point); the workflow doc and command reference change.
---

# Plan: `aet backlog add` — Board Entry Point

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-10).
- **Ground truth (2026-07-17):** the `backlog` command group + dispatcher entry are scaffolded by gib-06; the id-keyed issue machinery (create, `aet:draft`/`aet:backlog` labels, provisioning) is delivered by gib-05. This plan fills in the `add` subcommand behavior. `_create_issue` was unreachable in production before gib-05/gib-06 (`is_new=True` only in tests).
- Blocked by gib-06 (the `backlog` group scaffold) and gib-05 (the projection).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**; makes the previously-unreachable creation path reachable

## Locked design

- **`aet backlog add <plan>`** = "put it on the board": resolve the plan by id (fail-closed on unknown/ambiguous), ensure `status` is at least `draft` (leave draft as draft; leave approved as approved — never advances approval, which is validate-scope's job), commit+push via gib-04's `commit_and_push_status`, then call the projection's `on_add` to create exactly one issue keyed by plan id, labeled `aet:draft` (draft) or `aet:backlog` (approved).
- **Idempotent by id.** Re-running, or running from a second clone, finds the existing issue by plan id (gib-05's id identity) and creates no duplicate — it only reconciles the label to current status.
- **Fail-closed resolution, fail-open projection.** Id resolution and the status commit fail closed (reject/abort); the issue creation runs through gib-02's dispatcher and only ever warns, so a `gh` outage never blocks the commit.

## Rejected Alternatives

- **Advance draft → approved inside `backlog add`** — rejected: approval is `aet-validate-scope`'s gate (gib-03); `backlog add` boards whatever status the plan already has.
- **Create the issue before committing status** — rejected: the board must never show work whose status is not committed; commit+push first, project second (fail-open).
- **Require `status: approved` to board** — rejected: the owner wants drafts visible too ("draft or final"); `aet:draft` exists for exactly this.

## Task List

1. `aet backlog add`: id-resolve (fail-closed) → commit+push status → `on_add` create issue labeled by status — M (traces: R-10)
2. Idempotency: find-by-id, no duplicate on re-run or second clone; reconcile label only — S (traces: R-10)
3. Docs: workflow doc + command reference for `aet backlog add` — S (traces: R-10)
4. Tests: `tests/test_backlog_add.py` (new) — M (traces: R-10)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — distinct user-facing command

## Files to Modify

- `aet-work/bin/backlog` (the `add` subcommand behavior)
- `aet-work/lib/aet_queue.py` or a shared helper (if boarding logic is shared with `sprint add`)
- `docs/WORKFLOW-github.md` (or CONVENTIONS.md), `aet-work/references/` command docs
- `tests/test_backlog_add.py` (new)

## Validation Steps

- [ ] `make validate` passes; skills-lint green (the command exists in the argparse tree from gib-06)
- [ ] New source coverage — `tests/test_backlog_add.py`:
  - `test_backlog_add_unknown_plan_id_fails_closed`
  - `test_backlog_add_draft_plan_labels_aet_draft`
  - `test_backlog_add_approved_plan_labels_aet_backlog`
  - `test_backlog_add_twice_creates_no_duplicate` (idempotent by id)
  - `test_backlog_add_second_clone_finds_existing_issue`
  - `test_backlog_add_succeeds_and_warns_when_projection_unavailable` (fail-open)
- [ ] R-trace coverage: R-10 by tasks 1–2; no unknown R-ids
- [ ] Distinguish test types: unit (resolution, idempotency) + integration (add → commit → project), `gh` mocked
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `aet backlog add` disappears; the `backlog` group scaffold from gib-06 remains but has no `add` subcommand behavior. No stored data changes; plan `status` values already written stay valid.

## Pipeline

`pipeline: standard` — user-facing command with a fail-closed resolution boundary; standard grouping is warranted.

---

*Stage: qa-complete*
