---
id: epi-03-worktree-refresh-no-repo-root-checkout
size: S
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: removes a git checkout side effect; creates no new network, credential, or filesystem-write surface
docs_sync: skipped
docs_sync_reason: restores intended behavior; no documented behavior changes
---

# Plan: Stop worktree refresh from checking out a branch in `repo_root`

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-7)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md` (decision 5)
- Bug: `docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md`
  ("Dangerous side effect found while applying the workaround")

Highest-urgency item in the PRD and deliberately unblocked: this is a data-safety
bug that fires at any branch name, and it should not wait on `epi-01`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

This **is** a reproducible defect and was investigated under `aet-bug-report`. It
is planned here only because it shares a test surface and a code path with the
rest of the worktree work; the diagnosis is not re-derived.

## Locked design

- The defect is `src/aet/worktree.py:120`:
  `git -C <repo_root> rebase --onto <base> <branch_base_sha> <branch_name>`.
  Passing `rebase` a `<branch>` argument makes git **check that branch out in
  `repo_root` first**. `repo_root` is the operator's own working tree.
- **Move the ref, do not check it out.** The branch here has no worktree yet —
  this arm runs before `worktree add` — so the rebase result can be computed and
  the ref moved with `git branch -f` / `git update-ref`. Prefer that to running
  a rebase at all.
- If a rebase must run, it runs **inside a worktree dedicated to that branch**,
  never in `repo_root`. Under no circumstance may `HEAD` in `repo_root` change.
- The existing failure path is preserved: on conflict, abort, delete the branch,
  and fall through to creating it fresh from base (`:124-131`). Only the
  mechanism changes, not the outcome.
- **This is not a branch-name bug.** A non-trunk base only makes the divergence
  that triggers it routine. Do not scope the fix to non-`main` bases.

## Task List

1. Replace the `repo_root` rebase at `worktree.py:120` with a
   no-checkout ref move, preserving the existing conflict fallback
   — S (traces: R-7)
2. Assert no AET code path runs a `HEAD`-changing git command in `repo_root`
   — S (traces: R-7)
3. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — one call site
- [ ] The diff is expected to exceed 3 files or 50 lines — it does not; ~15 lines
- [x] Cannot share a branch with `epi-02` — it could, but this is a data-safety
      fix that should ship without waiting on `epi-01`

Kept separate deliberately despite the small diff: it is the only item here that
can move an operator's working tree, and it has no dependency on the resolver.

## Rejected Alternatives

- **Guard with "only rebase when `repo_root` is not on that branch"** —
  rejected: the hijack is that git *switches to* the branch. The guard tests the
  state before the command that creates the problem.
- **Stash and restore `repo_root`'s HEAD around the rebase** — rejected:
  ADR-027 already treats the operator's tree as something AET checks, not
  something it mutates. Restoring correctly after a crash is not achievable.
- **Skip refresh when the branch has diverged and recreate from base** —
  rejected: discards committed task work whenever divergence occurs, which is
  the normal case in `single-pr` mode (ADR-045).
- **Scope the fix to non-`main` bases** — rejected: the bug is
  branch-name-independent; scoping it leaves it live in Scenario A.

## Files to Modify

- `src/aet/worktree.py`
- `tests/worktree/test_worktree.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] Regression test in `tests/worktree/test_worktree.py`: with a diverged task
      branch and `repo_root` checked out on a feature branch, refresh leaves
      `git -C <repo_root> rev-parse --abbrev-ref HEAD` unchanged — demonstrated
      **failing** against current `worktree.py` before the fix
- [ ] The conflict path still deletes the branch and recreates from base
- [ ] The existing 10 `tests/worktree` tests pass unchanged
- [ ] R-trace coverage: R-7 covered by tasks 1–2
- [ ] No new source files introduced
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The ref-move is equivalent to the rebase in the non-conflict
case, so rollback restores the prior behavior — including the hijack — with no
migration.

## Pipeline

`standard`.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
