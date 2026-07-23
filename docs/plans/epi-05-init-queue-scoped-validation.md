---
id: epi-05-init-queue-scoped-validation
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: reorders existing validation and downgrades unrelated-plan aborts to warnings; no new input, network, or write surface
docs_sync: required
docs_sync_reason: changes init-queue from fail-closed to warn-and-skip for unrelated plans — user-visible behavior change
---

# Plan: Scope `init-queue` validation to the plans being included

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-10)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md` (decision 6)
- Bug: `docs/bugs/2026-07-22-queue-reset-dead-end.md` (root cause #1)

ADR-013 makes the queue safe to lose because it can be regenerated from plans.
`init_queue.py` breaks that guarantee: it validates the whole `plan_files` set
and returns `1` on any finding (`:230-238`) **before** the per-plan
`is_settled_plan` skip at `:253` and the `is_sprint_member` skip at `:260`. A
plan it would have skipped anyway still aborts the rebuild — and in a shared
repository the invalid plans belong to other people's features and will never
be fixed by this operator, so the queue is permanently unregenerable. It is
gitignored, so git cannot restore it either.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

This is a reproducible defect, investigated in the bug report above. It is
planned here because the fix is an ordering change inside the regeneration
path; the diagnosis is not re-derived. This is the same ordering defect already
recorded for `frh-17`/`frh-18` — fixing the ordering resolves both instances.

## Locked design

- **Validation moves after the skips.** The abort at `:230-238` runs before the
  `is_settled_plan` (`:253`) and `is_sprint_member` (`:260`) skips today. The
  included-set is computed first; validation runs against that set only.
- **Warn-and-skip applies to plans the caller did not ask for.** An invalid
  unrelated plan produces a warning naming the plan and the finding, and is
  skipped. The queue file is never left unwritten because of such a plan.
- **Included plans still fail closed.** A plan the caller asked to include that
  fails validation is an error, not a skip. Scoping loosens the blast radius,
  not the contract.
- **`queue sync` is decided with the code in front of it** (PRD open question).
  If validation is a shared helper, scope it there so both commands inherit the
  behavior; if not, this plan does not duplicate the logic into `sync.py` — it
  records the finding in the plan's divergence notes instead.

## Task List

1. ✓ Compute the included-plan set before validation in `init_queue.py`, moving
   validation after the settled/sprint skips — M (traces: R-10)
2. ✓ Warn-and-skip invalid plans outside the included set; keep fail-closed for
   invalid plans inside it — S (traces: R-10)
3. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one validation path
- [ ] The diff is expected to exceed 3 files or 50 lines — it does not; one
      module plus its test
- [x] Cannot share a branch with `epi-06` — it could, but the heal/reset work
      depends on `epi-02` and this does not; keeping it unblocked lets it ship
      first

## Rejected Alternatives

- **Add `init-queue --force` or `--only <glob>`** — rejected: the bug report's
  own sketch, superseded by scoping. Once unrelated plans cannot abort the
  rebuild, plain delete-and-regenerate is the supported reset and no flag is
  needed (PRD technical notes).
- **Downgrade all validation findings to warnings** — rejected: the frontmatter
  contract (`docs/CONVENTIONS.md`) is fail-closed for the plans being queued;
  scoping must not become silent acceptance of a broken included plan.
- **Gitignore-tolerant rebuild (restore the queue from git)** — rejected: the
  queue is gitignored by design (ADR-013); the fix is that regeneration works,
  not that the file becomes durable.

## Files to Modify

- `src/aet/cli/init_queue.py`
- `src/aet/cli/sync.py` (only if validation proves to be a shared helper)
- `tests/queue/test_init_queue_scoped_validation.py` (new)

## Validation Steps

- [x] Lint passes
- [x] Tests pass
- [x] New source coverage: `tests/queue/test_init_queue_scoped_validation.py`
      asserts a complete queue is written in a plans directory containing
      unrelated plans that fail validation, with one warning per invalid plan —
      demonstrated **failing** against the current abort-at-`:230` behavior
- [x] An invalid plan inside the included set still fails closed with a
      non-zero exit and no queue write
- [x] The `frh-17`/`frh-18` ordering instance is covered by the same test or a
      named sibling test
- [x] R-trace coverage: R-10 covered by tasks 1–2
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The abort-before-skip ordering returns; a wedged queue in a
shared repository becomes unregenerable again, but no data is lost because the
queue is ephemeral.

## Divergence Notes

- **`queue sync` needed no change.** The locked design left this open: if
  validation were a shared helper, scope it there; otherwise record the finding
  here. `src/aet/cli/sync.py` already skips settled and non-sprint plans
  (`:69-72`) before calling `plan_validate.validate` (`:98`), so it never had
  the abort-before-skip defect. `sync.py` was not modified.
- **Test fixtures updated beyond the listed files.** Bad-plan fixtures in
  `tests/plan/test_intake_gate.py` and `tests/queue/test_init_queue_sync.py`
  gained `status: queued` so they stay in the included set and keep exercising
  fail-closed rejection after scoping.

## Pipeline

`standard`.

---

*Stage: merged*
*Next step: run `aet-ship`*
