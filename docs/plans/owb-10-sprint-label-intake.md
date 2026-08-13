---
id: owb-10-sprint-label-intake
size: M
work_class: normal
blocked_by:
  - owb-05-board-is-open-work
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: `aet:sprint` Is Human Intent, Validated Against the Graph

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirements: R-13, R-14, R-21, R-22
- **Consolidated** from two plans at guardrail review: the former `owb-09` was a two-clause ADR narrowing whose only purpose was to authorise this plan. A reviewer is better served seeing the rule and its first use together.

Most of the write path exists: the projection creates issues keyed by plan id, relabels on transition, closes on terminal, and `_find_issue_by_id` does the reverse lookup. What is missing is the read.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Amend ADR-032 decision 2**: a forge is never read for *state*; reading human-declared *intent* is a distinct permitted operation. The source-of-truth fence is unchanged — S (traces: R-21)
2. **Amend ADR-033** with a third failure category: a forge read that gates admission fails closed, so this plan is conformant rather than exceptional. Record relations as frontmatter per ADR-056 — S (traces: R-22)
3. **Read open issues carrying `aet:sprint`** and map them to tasks via the existing keying — M (traces: R-13)
4. **Validate each candidate against the graph** and admit it or refuse with the blocking reason named. Readiness stays computed — M (traces: R-13)
5. **Enumerate once per run**, not per task, so a batch does not multiply API calls — S (traces: R-13)
6. **Retry with backoff, then halt.** An auth failure, rate limit or outage must never read as "nothing is blocking" — M (traces: R-14)
7. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: it is the operator-facing feature of the PRD.
- [x] Diff exceeds overhead: a read path, an admission check, a failure policy.
- [x] Cannot precede `owb-05`, whose board contract it reads from.
- [x] The ADR amendments are tasks 1-2 rather than a sibling plan: two clauses of narrowing are not independently shippable behaviour.

## Rejected Alternatives

- **A separate ADR-amendment plan** — rejected at guardrail review: docs-only, and its sole consumer is this plan.
- **Let the label set state directly** — rejected: readiness is derived; a label asserting it is the defect class.
- **Poll per task** — rejected: multiplies calls and invites secondary rate limits.
- **Fail open on an unreachable forge** — rejected: it silently admits blocked work.

## Files to Modify

- `src/aet/cli/sprint.py`
- `src/aet/backends/github_backend.py`
- `src/aet/projections/dispatcher.py`
- `docs/adr/032-github-issues-projection-not-backend.md`
- `docs/adr/033-projections-fail-open-storage-fail-closed.md`
- `tests/backends/`, `tests/queue/`

## Validation Steps

- [ ] `aet:sprint` on a task with an open blocker is refused, blocker named
- [ ] A simulated 403 halts the run and admits nothing
- [ ] One enumeration call per run
- [ ] Both ADRs state the narrowed rule and carry relations frontmatter
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. The label becomes inert; `aet sprint add` remains the intake path.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-10-sprint-label-intake.md*
