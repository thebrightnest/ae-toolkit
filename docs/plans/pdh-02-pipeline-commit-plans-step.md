---
id: pdh-02-pipeline-commit-plans-step
size: S
blocked_by: []
pipeline: minimal
status: draft
security_review: skipped
security_review_reason: Edits skill instruction docs only (process step); no code, dependency, or trust-boundary surface.
docs_sync: skipped
docs_sync_reason: The skill instruction files ARE the deliverable; there is no separate doc to sync.
---

# Plan: Commit-Plans Step in `aet-pipeline-plan` + `aet-plan`

## Context

PRD: [plan-durability-hardening](../prds/plan-durability-hardening-prd.md) (R-2).
Root: `docs/bugs/2026-07-14-aet-add-queues-untracked-plans.md` (Gap 3).

The planning skills run `aet add`/`aet sync` with no commit step, so plans stay
uncommitted through intake — the process gap that let this session queue untracked
plans. With the Gap-1 guard now refusing untracked plans, the happy path must
commit plans _before_ `aet add`, or `aet add` will (correctly) refuse them. This
plan makes the pipeline commit by construction. These are live symlinked skills, so
the change takes effect on merge.

## Intake Triage

- [x] Confirmed this is a **feature/hardening** (process), not a reproducible defect

## Task List

1. `aet-pipeline-plan/SKILL.md` — insert an explicit "commit the plan files (and PRD/ADR)" step at the start of Step 3, before `aet add`; note it satisfies the intake durability guard — S (traces: R-2)
2. `aet-plan/SKILL.md` — add the commit step to the `create-stories`/`plan` queue-handoff guidance and the Completion Protocol, before any `aet add` instruction — S (traces: R-2)
3. Verify (see Validation Steps) and merge — S (traces: R-2)

**Size labels:** 2 files, ~25 diff lines → **S**.

## Batching Check

- [x] Not near-identical additions
- [ ] Diff expected to exceed 3 files or 50 lines — **no** (2 skill files, small)
- [x] Distinct file set from pdh-01 (orchestrator/ADR)

(Small; kept separate from pdh-01 because it targets skill docs, a distinct blast
radius from the orchestrator behavior change.)

## Rejected Alternatives

- **Rely on the Gap-1 guard alone** — rejected: the guard _refuses_ the bad state but the pipeline should _avoid producing_ it; committing by construction is the fix, the guard is the backstop.

## Files to Modify

- `aet-pipeline-plan/SKILL.md`
- `aet-plan/SKILL.md`

## Validation Steps

- [ ] `./scripts/validate-skills.sh` passes on both edited skills (structure, line count ≤ 400, links)
- [ ] `./scripts/skills-lint` passes (no broken `aet` references introduced)
- [ ] Both skills now describe committing plans before `aet add`; no `aet add` instruction precedes the commit step
- [ ] **No new source modules** — skill instruction docs, covered by validate-skills.sh / skills-lint, not pytest
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (pipeline-plan=t1, plan=t2) PASS · Check 3 (observable: commit precedes add in the docs) PASS · Check 4 (R-2 covered) PASS.

## Rollback Plan

`git revert` the commit; the skills return to add-without-commit guidance.

## Pipeline

`minimal` — skill-doc edits; all stages fit one session.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
