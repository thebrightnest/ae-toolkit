---
id: epi-08-single-pr-completion-loop
size: L
blocked_by: [epi-02-thread-resolver-through-consumers, epi-03-worktree-refresh-no-repo-root-checkout, epi-07-integration-mode-config]
pipeline: standard
status: queued
security_review: required
security_review_reason: adds local squash-merge and branch-deletion paths and a push-suppression guarantee — new git command surface that must not leak task branches to origin
docs_sync: required
docs_sync_reason: introduces single-pr completion semantics — what "done" means changes for this mode
---

# Plan: `single-pr` completion — ephemeral branches, local integration, live-tip cuts

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-15, R-16, R-17; R-4
  mode-keyed sentence)
- ADR: `docs/adr/045-epic-integration-branch-and-task-integration-mode.md`
  (decisions 2, 3, 4, 6)

This is the core of Scenario B. With it, one engineer in a shared repository
drives a multi-plan ticket and produces exactly one branch and one PR. Without
it, ADR-044 alone leaves N branches and N PRs visible — the specific cost the
host branching policy exists to avoid.

**Size L, re-evaluated and kept whole.** Expected diff exceeds 200 lines with
tests, so the label is L. Re-evaluation against the full guardrail model: one
subsystem (`src/aet/` + its tests); task-list lines far under 300; the three
requirements are one mechanism — cutting from the live tip (R-17) without
integrating into it (R-16) leaves branches nothing merges, and integrating
without the ephemeral lifecycle (R-15) leaves the push path reachable. The
intermediate states are not shippable, so the split test fails and the plan
stays whole.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **No per-task branch reaches `origin` — a guarantee, not a default.** In
  `single-pr` the push path for task branches is not reachable, not merely
  unused (ADR-045 decision 4). Each task branch is created, integrated, and
  deleted locally. Only the integration branch is pushed (by `epi-10`), and
  only it gets a PR.
- **"Done" means integrated.** A task completes by squash-merging into the
  integration branch **locally**, and ADR-011 dependency-unblocking fires on
  that event rather than on trunk arrival (ADR-045 decision 3). The queue,
  `aet ship`, and telemetry all read the mode — this is the two-meanings-of-done
  cost ADR-045 names, and it is why `epi-07` insists Scenario A is the same
  code path.
- **The base is the live tip.** A task worktree is cut from the integration
  branch's tip at the time the task starts, after its blockers have integrated
  — not from a snapshot taken when the run began (ADR-045 decision 2). The
  engine is: task completes → integration branch advances → next unblocked task
  is cut from the new tip.
- **Hygiene and telemetry follow the mode** (ADR-045 decision 6, PRD R-4):
  `check_base_hygiene` and `_session_diff_stats` read the integration branch in
  `single-pr`, so a run is gated on the epic's branch being clean and in sync —
  not on trunk, which this operator may not be able to push to.
- **Worktree refresh rebases onto the current tip** and never checks out in
  `repo_root` — `epi-03` is a hard prerequisite, because in this mode divergence
  at refresh is the normal case, not the exceptional one.

## Task List

1. Create per-task branches locally in `single-pr` and make their push path
   unreachable — M (traces: R-15)
2. Complete tasks by local squash-merge into the integration branch, firing
   ADR-011 unblocking on integration rather than trunk arrival
   — M (traces: R-16)
3. Cut task worktrees from the integration branch's live tip at task-start
   time, after blockers have integrated — M (traces: R-17)
4. Key `check_base_hygiene` and `_session_diff_stats` to the integration
   branch in `single-pr` — S (traces: R-4)
5. Delete each per-task branch locally after it integrates — S (traces: R-15)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one completion mechanism
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-09` — serialization and re-validation
      layer on top of this loop and are reviewable separately; see Rejected
      Alternatives for the merge-them case

## Rejected Alternatives

- **Split into cut-timing (R-17) and integration (R-15, R-16) plans** —
  rejected: the intermediate state has worktrees cut from a tip nothing
  integrates into, or integration into a branch tasks are not cut from. Neither
  is shippable; the split fails the independence test.
- **Merge `epi-09` into this plan** — rejected: it would push the diff well
  past 400 lines and bury the one genuinely new mechanism (the lock) inside the
  largest change. The lock reviews better against a stable loop.
- **Rebase each task branch onto trunk at completion instead of squash-merging
  into the integration branch** — rejected: it keeps "done" bound to trunk,
  which is the identity ADR-045 exists to break, and in a shared repo this
  operator may not be able to read trunk's protected tip at all.
- **Push per-task branches but delete them remotely after integration** —
  rejected: N visible branches in the shared repository is the cost Scenario B
  exists to avoid; remote deletion does not undo the noise.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/worktree.py`
- `src/aet/cli/aet_state.py`
- `tests/orchestrator/test_single_pr_loop.py` (new)
- `tests/state/test_done_means_integrated.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/orchestrator/test_single_pr_loop.py` runs a
      two-task `single-pr` epic with a dependency and asserts
      `git ls-remote --heads origin` contains the integration branch and no
      task branch, and that the dependent task's worktree contains its
      blocker's committed changes at creation time (PRD acceptance criteria
      for R-15, R-16, R-17)
- [ ] New source coverage: `tests/state/test_done_means_integrated.py` asserts
      a task integrated into the integration branch derives terminal and
      unblocks its dependents, while trunk arrival is not required
- [ ] `pr-per-task` behavior is unchanged — the `epi-07` command-sequence
      regression test still passes
- [ ] No push of a task branch is reachable in `single-pr` (asserted by
      inspecting the commands issued, not by reading the code)
- [ ] R-trace coverage: R-15 by tasks 1 and 5; R-16 by task 2; R-17 by task 3;
      R-4 (mode-keyed sentence) by task 4
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Locally integrated task commits remain reachable from the
integration branch ref; per-task branches already deleted are recoverable from
reflog. `pr-per-task` is untouched by construction.

## Pipeline

`standard`.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*
