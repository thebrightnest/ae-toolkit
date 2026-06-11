# Retro: 2026-06-10 — Orchestrator Completes Tasks Without Committing

## What Went Well

- **Parallel execution worked.** 13 tasks ran concurrently via worktrees without conflicts.
- **Dependency resolution worked.** Blocked tasks were promoted correctly when their dependencies finished.
- **Self-recovery was possible.** Once the issue was identified, manual commits on the 5 affected branches allowed merge to proceed.
- **Orchestrator already had partial safeguards.** The `remove_empty_worktree` function checked for uncommitted changes and warned, but did not fail the task.

## What Went Wrong

- **5 of 13 tasks completed with exit code 0 but zero commits on their branch.**

  - Affected: `clv-01`, `clv-02`, `sci-01`, `smr-01`, `smr-02`
  - Each had uncommitted changes in the worktree
  - The orchestrator marked them `done` and removed the worktree (or warned and left it)
  - When we later ran `aet-ship`, the branches were empty — `git diff main..HEAD` showed nothing
  - We had to manually `cd` into each worktree, `git add -A && git commit`, then re-merge

- **The agent wrote code but skipped the commit step.**

  - `aet-implement` step 9 says "Commit with a message that references the ticket/plan" — but this is procedural, not enforced
  - `aet-pipeline-implement` terminal mode mentions `git commit --no-edit`, but only when "fewer than 10 steps remain"
  - In unattended mode, the agent can run out of steps, fail to commit, and still exit cleanly

- **The orchestrator's success criteria was wrong.**
  - It checked `EXIT_CODE -eq 0` to mark a task as done
  - It did not verify that the branch actually had commits
  - The `remove_empty_worktree` function warned about uncommitted changes but did not fail the task

## Learnings

- **Unattended pipeline completion must be verified, not assumed.** Exit code 0 is insufficient. The orchestrator must check that the branch has at least one commit ahead of main before marking a task done.
- **Commit must be a hard gate, not a procedural step.** In unattended mode, if the agent can't commit, it must fail loudly — not exit successfully with uncommitted changes.
- **Worktree cleanup is lossy.** Removing a worktree with uncommitted changes destroys the work silently. The orchestrator must either commit first or preserve the worktree for inspection.

## Action Items

- [ ] **Orchestrator: Add commit verification after task completion.** Before marking `done`, verify `git rev-list --count main..HEAD` is > 0. If 0, mark task as `failed` with `failed_stage: uncommitted`. — @agent — 2026-06-10
- [ ] **aet-pipeline-implement: Make commit non-negotiable in unattended mode.** Add an explicit final step: "If `AET_EXECUTION_MODE=unattended`, commit is mandatory. If commit fails, exit non-zero." — @agent — 2026-06-10
- [ ] **aet-implement: Add commit verification to completion protocol.** Before declaring implementation complete, verify `git status --short` is empty. If not, auto-commit or fail. — @agent — 2026-06-10
