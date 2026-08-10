---
id: slc-03-frontmatter-status-removal
size: M
work_class: critical
blocked_by:
  - slc-01-content-addressed-ledger-events
pipeline: standard
security_review: required
security_review_reason: changes the settled-ness authority every gate and scheduler decision reads
docs_sync: required
docs_sync_reason: the plan frontmatter contract is documented across skills, templates, and CONTEXT.md
---

# Plan: Frontmatter `status` Removal — One Settled-ness Authority

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-1, R-9). ADR-055 voids
ADR-034: plan frontmatter `status` leaves the plan contract, the ledger +
git ancestry become the only settled-ness authority, and the mechanism that
policed the redundancy (plan drift detection, footer↔status validation,
"footer is only a breadcrumb" defenses) is deleted with it. This is the plan
that makes the five-plan resurrection defect structurally impossible rather
than patched.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Remove `status` from the plan contract: `.agents/templates/plan-template.md`,
   `plan_validate.py`, and intake no longer require or validate the
   field; `aet plans lint` flags a live `status` field as an error — M
   (traces: R-1)
2. [x] `init-queue` and `aet next`/`status` derive settled-ness from the ledger
   (settled ids) + git ancestry, never from plan frontmatter; legacy plans
   with terminal `status` still read as settled via ancestry — M (traces: R-1)
3. [x] Delete the redundancy police: `plan_drift` from the backend interface and
   all three backends, the "No plan drift detected" report path
   (`status.py:163`), and the footer↔status validator — S (traces: R-9)
4. [x] Queue membership is the explicit `aet sprint add` record only — the
   "frontmatter `queued` status loads the sprint" path dies — S (traces: R-1)
5. [x] Regression test: a plan with `status: queued` in frontmatter and
   `*Stage: merged*` in its footer is NOT re-queued by `init-queue`
   (the five-plan defect as a fixture) — S (traces: R-1)
6. [x] Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: the contract change and its deletions are one reviewable
  behavior ("where does settled-ness come from").
- [x] Expected diff (~500 lines including deletions and tests) exceeds PR
  overhead.
- [x] Cannot share a branch with slc-04: closure's transaction must be
  built against the post-R-1 world, so the changes are sequenced, not
  batched.

## Rejected Alternatives

- **Keep `status` as a non-authoritative convenience field** — rejected: a
  field that four plan files currently contradict is worse than no field
  (review, 01-state-model); two signals invite a new validator to police
  them.
- **Patch the five drifted plans in this branch** — rejected: mutually
  exclusive with this PRD (the fork, 10-order-of-attack); the class dies
  with the mechanism.
- **Grandfather the field forever (ADR-034's legacy rule)** — rejected:
  lint flags it instead; the legacy corpus reads as settled via git
  ancestry, which is the actual truth.

## Files to Modify

- `.agents/templates/plan-template.md`
- `src/aet/plan_parser.py`
- `src/aet/cli/init_queue.py`
- `src/aet/cli/next.py`
- `src/aet/cli/status.py`
- `src/aet/cli/plans_lint.py`
- `src/aet/backends/base.py`, `json_backend.py`, `git_refs_backend.py`
  (drop `plan_drift`)
- `tests/cli/test_init_queue.py`, `tests/cli/test_plans_lint.py`
- `tests/backends/` (drift-removal updates)

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`make test`)
- [x] Five-plan fixture: frontmatter `queued` + footer `merged` is not
  resurrected (integration, `tests/queue/test_init_queue_sync.py`)
- [x] `aet plans lint` errors on a live `status` field (unit)
- [x] `grep -rn "plan_drift" src/aet` returns nothing (structural)
- [x] R-trace coverage: R-1, R-9 covered by tasks 1–5
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. No data is migrated; plans with `status` fields remain
readable by the pre-change code.

## Pipeline

`standard` — changes the authority every scheduling and gate decision reads
(risk override per ADR-047).

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*
