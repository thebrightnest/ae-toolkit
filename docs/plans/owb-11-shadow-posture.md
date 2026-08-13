---
id: owb-11-shadow-posture
size: M
work_class: critical
blocked_by:
  - owb-07-git-refs-only-store
  - owb-10-sprint-label-intake
pipeline: full
security_review: required
docs_sync: required
---

# Plan: Shadow Posture: Local by Default, Announced, Never Pushed

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirements: R-15, R-16
- Decision: posture is **inferred** from the absence of project-scope config

A project nobody configured is local, which is the safe direction — it can never leak `refs/aet/*` to someone else's remote by omission. What the inference owes the operator is visibility.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Infer posture** from the absence of project-scope config, and resolve it in one place — M (traces: R-15)
2. **Announce it on every run**, naming the consequence (refs are not pushed) and the command that opts out — S (traces: R-15)
3. **Suppress the push**, including the mandatory closure push, with an explicit ADR-055 exemption rather than a silent bypass — M (traces: R-16)
4. **Run no projection** and write no AET artifact into the working tree — S (traces: R-15)
5. **Prove it**: a full run leaves `git status` clean, no `refs/aet/*` on the remote, and no project-scope config file — M (traces: R-15, R-16)
6. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: a posture with its own durability contract.
- [x] Diff exceeds overhead: inference, announcement, a push exemption, a projection skip.
- [x] Cannot precede `owb-10`: the projection must be skippable by posture.

## Rejected Alternatives

- **An explicit posture key** — rejected by the operator in favour of inference; recorded as the fallback if the announcement proves insufficient.
- **Silently skipping the closure push** — rejected: it disables a fail-closed durability rule without saying so.

## Files to Modify

- `src/aet/backends/factory.py`
- `src/aet/backends/git_refs_backend.py`
- `src/aet/cli/configure_backend.py`
- `src/aet/projections/dispatcher.py`
- `docs/adr/055-settled-ness-in-commutative-ledger.md`
- `tests/backends/`

## Validation Steps

- [ ] A full shadow run leaves the tree clean and the remote untouched
- [ ] The posture and its consequence are announced once per run
- [ ] The closure-push exemption is recorded in ADR-055
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. Posture resolution returns to unconditional push; no stored state changes.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-11-shadow-posture.md*
