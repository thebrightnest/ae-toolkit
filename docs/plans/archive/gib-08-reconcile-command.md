---
id: gib-08-reconcile-command
size: M
blocked_by:
  - gib-05-board-projection-machinery
pipeline: standard
status: merged
security_review: required
security_review_reason: reconcile can mass-mutate a repo's GitHub issues (create/relabel/reopen). A wrong diff or a non-dry-run default could noisily corrupt a shared team board. Dry-run-by-default and the drift-detection logic are the safety boundary and must be verified.
docs_sync: required
docs_sync_reason: introduces a user-facing `aet ... reconcile` command with dry-run/`--apply` semantics; the command and its healing contract are documented.
---

# Plan: Board Reconcile / Backfill Command

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-17).
- **Ground truth (2026-07-17):** enabling the projection on a repo with an existing corpus needs a backfill — the projection only fires on live transitions, so pre-existing plans have no issue. And drift happens: an issue hand-closed while its plan is live, a wrong/extra label, a missing issue after a failed push.
- Consumes gib-05's projection (id identity, label map). Mirrors ADR-024's `audit`/`heal --apply` split.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**

## Locked design

- **Reconcile = diff then optionally apply.** Scan live plans (committed status) and the repo's `aet:*` issues; compute a drift set: missing issue, wrong/extra label, issue closed while plan live, orphan issue (no live plan). **Dry-run by default** — prints the diff, mutates nothing. `--apply` performs the minimal corrective writes through gib-02's fail-open dispatcher.
- **Hand-closed live issue:** reported by default; `--apply` re-opens (owner-leaning per PRD open question — revisited at validate-scope). Orphan issues (plan settled/gone) are reported, never auto-deleted.
- **Idempotent.** A second `--apply` with no intervening change produces an empty diff.

## Rejected Alternatives

- **Apply by default** — rejected: bulk remote mutation on a shared board must be opt-in; dry-run default is the ADR-024 lesson.
- **Auto-delete orphan issues** — rejected: destructive on a shared repo; report and let the human decide.
- **Fold reconcile into `aet sync`** — rejected: `sync` is a local plan→queue reconcile with no network; a surprise remote mass-write there violates least astonishment.

## Task List

1. Drift computation: live-plans × `aet:*` issues → {missing, mislabeled, closed-live, orphan} — M (traces: R-17)
2. Command with dry-run default + `--apply`; corrective writes via the dispatcher — M (traces: R-17)
3. Docs: reconcile command + healing contract — S (traces: R-17)
4. Tests: `tests/test_board_reconcile.py` (new) — M (traces: R-17)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — distinct command surface

## Files to Modify

- `aet-work/bin/` reconcile entry (new subcommand or `bin/report` extension)
- `aet-work/lib/projections/` (drift helper)
- `aet-work/references/` command docs
- `tests/test_board_reconcile.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] New source coverage — `tests/test_board_reconcile.py`:
  - `test_dryrun_reports_missing_issues_and_mutates_nothing`
  - `test_apply_creates_missing_and_corrects_labels`
  - `test_reports_hand_closed_live_issue` (+ `--apply` reopens)
  - `test_orphan_issue_reported_not_deleted`
  - `test_second_apply_is_empty` (idempotent)
- [ ] R-trace coverage: R-17 by tasks 1–2; no unknown R-ids
- [ ] Distinguish test types: unit (drift set) + integration (dry-run vs apply), `gh` mocked
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The reconcile command disappears; the projection still self-maintains on live transitions. No stored state changes.

## Pipeline

`pipeline: standard` — bulk-mutation command with a dry-run safety default; standard grouping is warranted.

---

_Stage: merged_
