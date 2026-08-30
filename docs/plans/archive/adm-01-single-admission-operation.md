---
id: adm-01-single-admission-operation
size: M
work_class: critical
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes the gate that decides what work enters the board.
docs_sync: required
docs_sync_reason: Adds a domain module and changes the admission contract both CLI doors depend on.
---

# Plan: A Single Admission Operation

## Context

PRD: docs/prds/single-admission-path-prd.md
Decision: ADR-066 (Board Admission Has One Path), which relates to ADR-019
decision 4, ADR-055 decision 1, and ADR-061.

Admission happens at `aet sprint add` (`src/aet/cli/sprint.py:230`) and
`aet sprint intake` (`:336`). Each inlines its own check sequence. Commit
`9aa5c7b4` already extracted `_unacked_intake_findings` — the `plan_validate`
half of the decision — and calls it from both doors. That helper is the seam
this plan takes over and widens to the whole decision: queued, settled, stage,
task construction, and blocked-handling.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The footer *disposition* is a conformance defect against ADR-019/055/061
      and was routed to `aet-bug-report`; the singularity of the admission path
      is decided by no accepted ADR, which is what makes this planning work

## Task List

1. Add the domain module with the admission outcome type — an enumerable result
   naming admitted, skipped (already live, already settled), and refused with
   reasons — beside `plan_parser.py` and `plan_validate.py` — S (traces: R-2)
2. Move the whole admission decision into one operation in that module: resolve
   the plan, check live and settled sets, run `plan_validate` via the existing
   `_unacked_intake_findings` logic, and build the task. It does not read the
   plan footer — S (traces: R-1, R-4, R-5)
3. Rewrite `_add` to call the operation and render its outcome: the finding
   list, the rtrace cause note, and the `⚠️ VALIDATE ACK` line on refusal — S
   (traces: R-1, R-3)
4. Rewrite `_intake`'s per-candidate branch to call the operation and record a
   refused row, removing its inlined checks and the now-duplicated call added by
   `9aa5c7b4` — S (traces: R-1, R-3)
5. Preserve each door's ledger `source` (`sprint-add`, `sprint-intake`) across
   the refactor, and assert the two produce distinct event ids — S
   (traces: R-11)
6. Regression tests: a footerless plan is admitted at both doors; a plan failing
   rtrace is refused at both with the same finding; `aet context` still reports
   plan and PRD stage — M (traces: R-7, R-10)
7. Merge branch to main and verify integration — S

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

No boxes checked. This plan introduces the architectural invariant ADR-066
records, and is the blocker for both siblings.

## Rejected Alternatives

- **Delete the footer read from each gating site and stop** — rejected: leaves N
  sites that can drift again, and leaves the audit question as expensive as it
  was. Recorded in ADR-066 Alternative 1.
- **Home the operation in `plan_parser.py`** — rejected: inverts layering by
  making a parser depend on `plan_validate` and the backends. ADR-066
  Alternative 2.
- **Home it in `sprint.py`** — rejected: `backlog.py` would import from a CLI
  command module. ADR-066 Alternative 3.
- **Keep `_unacked_intake_findings` as the shared seam and add a second helper
  for the rest** — rejected: two shared helpers called in a fixed order is the
  same duplication with more steps; the order is itself policy.

## Files to Modify

- `src/aet/admission.py` (new)
- `src/aet/cli/sprint.py`
- `tests/plan/test_intake_gate.py`
- `tests/cli/test_sprint_intake.py`
- `tests/admission/test_admission.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] `src/aet/admission.py` is covered by `tests/admission/test_admission.py`
- [ ] `new_task_from_plan` is called from exactly one place
- [ ] Neither `sprint.py` door contains a queued, settled, or stage check
- [ ] Unit tests cover the outcome type; integration tests cover both CLI doors
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The doors return to their inlined decisions, including the
`9aa5c7b4` shared-validation call, which is a strict improvement over the
pre-2026-08-27 state and is safe to sit on.

## Pipeline

`standard` — this changes the gate deciding what enters the board.

---

_Stage: plan-approved_
