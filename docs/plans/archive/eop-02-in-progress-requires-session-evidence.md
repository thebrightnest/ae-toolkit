---
id: eop-02-in-progress-requires-session-evidence
size: S
work_class: critical
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Changes a read-side derivation only; writes no new state and grants no new capability.
docs_sync: required
docs_sync_reason: Completes an ADR-064 conformance the state model documents.
---

# Plan: `in_progress` Requires Session Evidence, Not a Branch

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 1 — existence is not
activity. Generalises ADR-064.

`derive_status` (`src/aet/cli/aet_state.py`) sets `in_progress` whenever
`derived["branch_exists"]` is true, with no check that the branch carries work or
that a session ever ran. A failed task whose branch was left behind derives
`in_progress` — a state an unattended batch never spawns — so `aet state reset`
strands it rather than clearing it.

This is the surviving half of a fix already made. ADR-064 established that
ancestry is not merge evidence, and the follow-up closed the `merged` derivation
by requiring `branch_has_own_commits(branch, base_commit)` before it resolves
(in `derive_status` and `resolve_merge_commit`). The `in_progress` branch of the same function never
received the same treatment: existence still stands in for activity one level
down.

Observed on 2026-08-29 on this repo's `main`: `ppa-01` stored `in_progress`,
`aet state audit` deriving `ready`, no branch, and a stale worktree.

## Intake Triage

- [x] Demonstrable defect, recorded in
      `content/backlog/debt-in-progress-is-derived-from-branch-existence.md`
- [x] Routed here because it is the unfinished half of an accepted ADR's
      conformance, decided by the same rule the PRD's ADR states, rather than an
      isolated fix

## Task List

1. Require positive evidence before `derive_status` returns `in_progress`: reuse
   `branch_has_own_commits(branch, base_commit)` as the `merged` path does, so a
   branch sitting at its base does not derive activity — S (traces: R-3)
2. Derive an unstarted task to `ready` or `blocked` on its blockers, matching
   what the forward-recorded model would hold for work that never began — S
   (traces: R-3)
3. Regression tests: a zero-commit branch derives unstarted; a branch with own
   commits still derives `in_progress`; a task with no branch is unaffected; the
   `merged` path is unchanged — S (traces: R-3)
4. Merge branch to main and verify integration — S

### Floor Check

- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] Expected diff is below the calibrated floor threshold
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked: the invariant is ADR-064's and already accepted; this applies it
to a second derivation inside one function. It is not below the floor because the
derivation feeds `reset`, `heal` and `audit`, each of which needs its own
regression.

## Rejected Alternatives

- **Record a session marker at spawn and read that instead** — rejected: a new
  written artifact where an existing evidence test already answers the question,
  and it would leave pre-existing tasks underivable.
- **Drop `in_progress` from derivation entirely and always require an explicit
  transition** — rejected: it would make `aet state audit`'s discrepancy report
  unable to name a genuinely running task, which is the report's main use.
- **Leave it and document the `aet state transition` workaround** — rejected:
  that is the current state, and it strands a task by default while the exact
  fix already exists a few lines away.

## Files to Modify

- `src/aet/cli/aet_state.py`
- `tests/state/test_derive_status.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] `aet state audit` reports no discrepancy for a task whose branch carries no
      commits
- [ ] The `merged` derivation's existing tests are untouched and still pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The derivation returns to reading branch existence, and the
documented `aet state transition <id> failed ready` workaround still applies.

## Pipeline

`standard` — this changes a derivation the board and `state reset` consume.
