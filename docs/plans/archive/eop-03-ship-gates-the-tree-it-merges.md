---
id: eop-03-ship-gates-the-tree-it-merges
size: M
work_class: critical
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes the pre-merge gate that decides whether unvalidated code reaches the trunk.
docs_sync: required
docs_sync_reason: Changes what a passing ship gate asserts, which the ship skill describes.
---

# Plan: `aet ship merge` Gates the Tree It Merges

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 3 — a check must be about
its subject.

`_resolve_feature_branch` (`src/aet/cli/ship.py`) is deliberate about the
merge source: the branch comes from the task id, "never whatever branch happens
to be checked out". Every check reads the ambient checkout instead. `_run_gate`
runs `make validate` in the cwd; `_rebase_independent_branch` rebases
`git branch --show-current`; `_has_merge_conflicts` merge-trees `HEAD`;
the commit-count checks count `pr_base..HEAD`.

Nothing asserts that `HEAD` is the feature branch, and `skills/aet-ship/SKILL.md`
does not state the precondition. Run from a `main` checkout the command prints
"Gate passed", "No conflicts detected", and merges an unvalidated branch — three
true statements about a tree it is not merging.

Safety currently rests on operator habit: fourteen of fifteen merges measured on
2026-08-27 had been rebased onto the trunk tip first, so `make validate` had in
fact run on the merge result. The defect is that this is habit rather than
construction.

`_merge_into_target` already creates or reuses a worktree for the
target branch. Gating inside it preserves the checkout independence
`_resolve_feature_branch` was built for, instead of adding a precondition the
operator must remember.

## Intake Triage

- [x] Demonstrable defect, recorded in
      `content/backlog/debt-ship-checks-the-ambient-checkout.md`
- [x] Routed here because the fix changes what a passing gate asserts — a
      contract other stages and ADR-019 rely on — rather than correcting one
      call

## Task List

1. Resolve a gate workspace from the task rather than the cwd, reusing the
   worktree `_merge_into_target` already manages, so the gate has a tree to run
   in that is independent of where the operator stands — S (traces: R-4)
2. Run `make validate` in that workspace and report the branch it validated in
   the gate's output, so a passing gate names its subject — S (traces: R-4)
3. Resolve conflict detection and the commit-count checks from the feature
   branch and its recorded base instead of `HEAD` — S (traces: R-4)
4. Rebase the resolved feature branch rather than `git branch --show-current` — S
   (traces: R-4)
5. Refuse with a diagnostic when a workspace for the feature branch cannot be
   resolved, rather than silently falling back to the ambient checkout — S
   (traces: R-4)
6. Regression tests driving each subcommand from a checkout that is not the
   feature branch, asserting the gate runs against the feature branch and that a
   red feature branch is refused from a green `main` checkout — M (traces: R-4)
7. State the resolved behaviour in the ship skill, replacing the absent
   precondition — S (traces: R-4)
8. Merge branch to main and verify integration — S

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

No boxes checked. This changes the meaning of a passing pre-merge gate.

## Rejected Alternatives

- **Assert `HEAD == feature_branch` and refuse otherwise** — rejected as the
  primary approach: it is cheaper but converts a silent wrong answer into an
  operator precondition, giving up the checkout independence the merge source
  already has. Kept only as the refusal in task 5, for the case where no
  workspace can be resolved.
- **Document the precondition in the skill and stop** — rejected: prose cannot
  enforce it, and the failure mode is a confident false pass.
- **Always merge from a fresh clone** — rejected: cost per merge, and the
  worktree the command already manages answers the same need.

## Files to Modify

- `src/aet/cli/ship.py`
- `skills/aet-ship/SKILL.md`
- `tests/ship/test_ship_gate_workspace.py` (new — covered by `test_ship_gate_workspace.py`)
- `tests/ship/test_ship_merge.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No check in `ship.py` reads `git branch --show-current` or bare `HEAD` to
      decide what to validate
- [ ] A feature branch whose suite is red is refused when shipped from a green
      `main` checkout
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Checks return to reading the ambient checkout; the operator
habit that has held so far still holds, and the backlog item returns to accepted.

## Pipeline

`standard` — this changes the pre-merge validation gate.
