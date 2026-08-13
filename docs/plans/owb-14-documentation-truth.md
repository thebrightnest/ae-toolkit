---
id: owb-14-documentation-truth
size: S
work_class: trivial
blocked_by:
  - owb-11-shadow-posture
  - owb-13-prd-integration-branch
pipeline: minimal
security_review: skipped
security_review_reason: Documentation only — no executable surface changes.
docs_sync: required
---

# Plan: Make the Documentation Describe the System That Exists

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-18
- Blocked until the behaviour it describes has shipped

Five sites assert ledger refs transport that does not exist: `CONVENTIONS.md:388`, `WORKFLOW-github.md:23`, `git_refs_backend.py:13`, `cli/sync.py:82`, and CONTEXT.md's glossary — the last already corrected at scope validation and to be updated again here.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Correct the five transport claims** to describe the shipped model — S (traces: R-18)
2. **Retire ADR-054's stale clause** asserting plan `status` as the liveness signal, which ADR-055 removed — S (traces: R-18)
3. **Write a new ADR** recording the open-work board contract and the shadow posture, amending ADR-011, ADR-013, ADR-045 and ADR-055 and closing the lineage — S (traces: R-18)
4. **Land the agreed vocabulary** in CONTEXT.md: Task as the board entry, Rendered Plan, Issue as the projection, Board versus Plan Backlog, Shadow Posture — S (traces: R-18)
5. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone as the documentation-truth pass.
- [ ] Small diff — justified because five files asserting an unbuilt model is what this audit identified as the worst available option, and because the glossary is what `aet-validate-scope` checks every future plan against.
- [x] Cannot precede its blockers: describing behaviour before it ships repeats the defect.

## Rejected Alternatives

- **Correct the docs before the code lands** — rejected: that is exactly how ADR-055 came to describe an unbuilt system.
- **Skip the glossary and fix only prose files** — rejected: the glossary compounds, because every plan is validated against it.

## Files to Modify

- `docs/CONVENTIONS.md`
- `docs/WORKFLOW-github.md`
- `src/aet/backends/git_refs_backend.py`
- `src/aet/cli/sync.py`
- `CONTEXT.md`
- `docs/adr/054-plan-documents-are-outside-the-durability-gate.md`
- one new ADR file under the ADR directory (number assigned at implementation time)

## Validation Steps

- [ ] No file claims refs transport for the ledger
- [ ] CONTEXT.md carries the agreed vocabulary
- [ ] The new ADR names every decision it amends
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the documentation commits. No runtime behaviour is affected.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-14-documentation-truth.md*
