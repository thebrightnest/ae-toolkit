# Retro: AET Work Queue Run on Telemetry-Driven Skill Hardening

## Context

Ran `aet-work run` on the revised Telemetry-Driven Skill Hardening queue (tdsh-02 through tdsh-05). The run exposed several issues in the AET tooling itself, independent of the skill content being changed.

## What Went Well

- All four remaining plans landed on `main`.
- `make validate` passes after all merges.
- The `mine-learnings` signal that started this work was validated: the fixes were small, doc/test-level changes, not large architectural work.
- The decision to remove tdsh-01 (dependency warmup) was correct; it was a session workaround, not a root-cause fix.

## What Went Wrong

### 1. Orchestrator crashed with `NameError: read_queue`

- **Impact:** tdsh-02 completed through review, then the batch process crashed before continuing to tdsh-03/04/05. Required manual intervention.
- **Root cause:** `aet-work/bin/orchestrator` referenced an undefined `read_queue` helper in the success path after a task advanced to `awaiting_merge`. The variable was removed or never imported.
- **Layer:** `aet-work/bin/orchestrator`

### 2. Orchestrator sub-agent sessions timed out repeatedly

- **Impact:** Each task took longer than the 10-minute foreground/background timeout window. Two background orchestrator runs had to be killed, and tdsh-03 through tdsh-05 were completed manually.
- **Root cause:** Each stage spawns a fresh headless AI session that must reload skills, context, and run validation from cold. There is no per-task timeout or heartbeat inside the orchestrator; the only timeout is the outer shell command.
- **Layer:** `aet-work/bin/orchestrator` — missing per-task wall-clock budget and heartbeat logging.

### 3. Worktree `origin/main` became stale, polluting PR diffs

- **Impact:** The tdsh-03 worktree was created while `origin/main` was at an older commit. After tdsh-02 merged and `origin/main` advanced, the worktree's cached `origin/main` was stale, causing unrelated files (including a reverted `aet-implement/SKILL.md`) to appear in the diff.
- **Root cause:** Worktrees fetch `origin/main` once at creation and do not refresh it before comparing diffs or rebasing. `create_worktree` does not verify the local `origin/main` ref is current.
- **Layer:** `aet-work/lib/worktree.py`

### 4. Queue state drifted from actual work

- **Impact:** Tasks that completed through QA were still marked `failed` or `in_progress` in `.agents/work-queue.json` because the orchestrator timed out or crashed. Closing them with `aet-ship/bin/ship` required manual state transitions and setting the `branch` field.
- **Root cause:** The queue is the scheduling source of truth, but terminal closure depends on the orchestrator cleanly finishing. When the orchestrator dies, the queue does not self-heal.
- **Layer:** `aet-work/bin/orchestrator` + `aet-work/bin/aet-state`

### 5. `aet-ship/bin/ship` requires a `branch` field that is null for manually merged work

- **Impact:** After manually merging tdsh-04 and tdsh-05 on feature branches, `ship` refused to close the tasks because `branch` was `null` in the queue.
- **Root cause:** `ship` derives merge verification from `task["branch"]`. When work is done outside the orchestrator, that field is never populated.
- **Layer:** `aet-ship/bin/ship` and `aet-work/bin/aet-state record-merge`

## Learnings

- The orchestrator is still fragile for multi-task batches; timeouts and crashes leave the queue in an inconsistent state.
- Worktree-based isolation assumes `origin/main` is stable, but in active repos it advances between task creations.
- Manual completion of queued tasks is possible but fights the tooling because the queue expects orchestrator-owned metadata.

## Action Items

- [ ] Add per-task timeout, heartbeat logging, and a guaranteed cleanup/summary path to `aet-work/bin/orchestrator` — owner: agent — due: next cycle
- [ ] Make `create_worktree` refresh `origin/main` before creating or reusing a worktree, and rebase existing worktrees when `origin/main` advances — owner: agent — due: next cycle
- [ ] Allow `aet-ship/bin/ship` to close a task from a branch name or merge commit supplied on the CLI, so manually merged work can be closed without queue edits — owner: agent — due: next cycle
- [ ] Consider adding a queue self-heal / audit command that reconciles queued tasks against git ground truth and offers to mark merged tasks terminal — owner: agent — due: next cycle
