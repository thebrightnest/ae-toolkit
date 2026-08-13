---
id: owb-01-spec-travels-in-task-record
size: M
work_class: critical
blocked_by: []
pipeline: full
security_review: required
docs_sync: required
---

# Plan: The Task Record Carries the Spec; the Worktree Plan Is Rendered

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirements: R-19, R-4
- Enables the plan-on-one-machine, run-on-another scenario
- **Consolidated** from two plans at guardrail review: the footer commit path is dead code once the stage lives on the record, and untracking the 53 tracked live plans is the same behavioural change seen from git. Split, this landed in a half-state.

Today the record carries `plan_file` as a *path* (`plan_parser.py:266`), the issue body carries a reference (`github_backend.py:429`), and the file itself is gitignored — so a plan authored on one machine reaches no other. `stage_enabled()` and `gate.required_evidence()` also read plan frontmatter at run time, so the file is load-bearing for routing, not just for the agent.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Carry the spec in the record.** `new_task_from_plan` writes the task list and the gate keys (`security_review`, `docs_sync`, `pipeline`, `size`) into the record instead of only a path — M (traces: R-19)
2. **Render the working plan** into the worktree from the record at task start — M (traces: R-19)
3. **Remove `_copy_deferred_files`' main-checkout overlay.** With the working copy rendered, there is nothing to overlay, so the clobber defect is deleted rather than guarded — S (traces: R-19)
4. **Resolve routing from the record**, so `stage_enabled` and `required_evidence` no longer need a file on disk — M (traces: R-19)
5. **Stop the footer write path** from producing commits, now that the stage lives on the record — S (traces: R-4)
6. **Untrack the 53 tracked live plans** with `git rm --cached`, so `.gitignore:24`'s declaration actually holds — S (traces: R-4)
7. **Remove the archive `git mv` + commit** from the closure transaction; relocation is `owb-03`'s job — S (traces: R-4)
8. **Prove the two-machine path**: plan and add on one clone, fetch and run to completion on another, with no plan file in the first clone's tree — M (traces: R-19)
9. **Regression guard**: a full task lifecycle adds no commit touching only plan state — S (traces: R-4)
10. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: it is the transport that every later phase assumes.
- [x] Diff exceeds overhead: record schema, a renderer, two deletions, a routing change, an untracking.
- [x] Cannot share a branch with `owb-05`, which consumes the rendered model.
- ⚠️ **Near the ceiling.** Consolidating the former `owb-02` puts this close to the `M` limit on expected diff and context budget. It is one coherent change, so it is not split — but if implementation trips two ceiling signals, split along the record/commit-hygiene seam and record `Split from: owb-01-spec-travels-in-task-record`.

## Rejected Alternatives

- **Put the spec in the issue body** — rejected: makes the forge load-bearing for execution and leaves shadow projects with no equivalent.
- **Commit plan files** — rejected: reinstates the 7% state-commit pollution this PRD removes.
- **Guard the overlay with an mtime check** — rejected: fixes a symptom of a divergence that this plan removes entirely.

## Files to Modify

- `src/aet/plan_parser.py`
- `src/aet/worktree.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/gate.py`
- `src/aet/queue.py`
- `src/aet/cli/aet_state.py`
- `docs/plans/*.md` (untracking only)
- `tests/plan/`, `tests/worktree/`, `tests/orchestrator/`, `tests/queue/`

## Validation Steps

- [ ] A task runs to completion on a clone that never had its plan file
- [ ] Gate skips and pipeline mode resolve identically from the record
- [ ] `_copy_deferred_files` no longer exists
- [ ] `git ls-files docs/plans | grep -v archive` is empty
- [ ] A full lifecycle adds no `mark plan stage` commit
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert. Records written with a spec remain readable; the path field is still present, so the file-based path resumes.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-01-spec-travels-in-task-record.md*
