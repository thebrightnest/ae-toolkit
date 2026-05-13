# PRD: aet-work Hybrid Orchestrator

## Overview

Add a `run-scripted` command to `aet-work` that solves the context-isolation problem skill-only instructions cannot fix. The skill auto-detects which agent runtime is hosting it, generates a bash orchestrator script tailored to that runtime, spawns the script as a background OS process (keeping the parent session clean), and waits for completion. Each task executes in a fresh agent process with its own git worktree, eliminating context leakage, task corruption, and branch overlap.

## Goals

1. `aet-work run-scripted` generates a runnable bash orchestrator from `.agents/work-queue.json`
2. The skill auto-detects the current agent runtime and generates a script that invokes the same CLI for sub-tasks
3. The parent agent delegates execution to a background process so its own context stays clean
4. Queue state updates correctly (`unblocked` → `in-progress` → `done` / `failed`)
5. Each task runs in a dedicated git worktree on its own branch
6. Works on Claude Code, Kimi Code, and any agent that exposes a CLI and sets a recognizable env var

## Non-Goals

- Parallel execution of multiple tasks inside the orchestrator (v2)
- Windows PowerShell / CMD support
- Automatic worktree cleanup after merge
- Real-time streaming progress UI inside the parent session
- Persisting partial task state mid-execution (resume from crash is manual)

## User Stories

- As a developer using `aet-work`, I want to queue multiple plans and run them without manual intervention so that I stop babysitting each task.
- As a developer using `aet-work`, I want each task to start with a completely clean context so that earlier tasks do not corrupt or leak state into later tasks.
- As a toolkit user on Kimi Code, I want the same orchestration capability that Claude Code users have, without needing to know the internal CLI differences.
- As a maintainer, I want the solution to require zero per-runtime configuration so that adding support for a new agent CLI is only a detection heuristic.

## Acceptance Criteria

- [ ] `aet-work run-scripted` command is documented in `aet-work/SKILL.md`
- [ ] The skill detects the current runtime by inspecting env vars (`CLAUDE_CODE`, `KIMI_CLI_VERSION`, `CODEX_`, etc.) and falls back to `AGENT_CLI` if uncertain
- [ ] Running `run-scripted` generates `scripts/.aet-work-orchestrator.sh` with the detected CLI hard-coded into each task invocation
- [ ] The parent agent spawns the script via `Shell(run_in_background=true)` and waits via `TaskOutput(block=true)`
- [ ] The script reads `.agents/work-queue.json`, creates worktrees, and processes unblocked tasks sequentially
- [ ] Each task branch is created via `git worktree add .worktrees/<task-id> -b <task-id>`
- [ ] Queue status updates to `done` on success or `failed` on error, with the failing stage recorded
- [ ] Dependent tasks are promoted to `unblocked` when all blockers are `done`
- [ ] `aet-work/references/context-isolation.md` accurately describes why skill-only isolation fails and documents the hybrid pattern
- [ ] `make validate` passes and `make package` regenerates `.skill` files

## Technical Notes

### Runtime Detection Heuristics

The skill detects which CLI to spawn for sub-tasks. Simplicity over comprehensiveness:

1. Check if `kimi` is in `PATH` or `KIMI_CLI_VERSION` is set → `kimi`
2. Check if `claude` is in `PATH` or `CLAUDE_CODE` is set → `claude`
3. `AGENT_CLI` (user-override) → whatever value is set
4. Fallback → emit a warning and require the user to set `AGENT_CLI` before running the script

New agents are supported by adding one line to the detection list and setting `AGENT_CLI` as a universal override.

### Script Structure

The generated script is self-contained and uses only `bash`, `git`, and `python3`:

- Reads and writes `.agents/work-queue.json` via inline Python (portable, no `jq` dependency)
- Creates worktrees on demand, skips if already present (supports resume)
- Invokes the detected CLI once per task with a prompt/message instructing it to run `aet-pipeline-implement` on the specific plan file
- Blocks until each CLI process exits, then updates queue status
- Promotes dependent tasks when blockers complete

### Context Isolation Mechanism

```
Parent agent session (clean)
  → generates script
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context)
      → Task 1 completes, commits, exits
    → Script spawns Agent CLI process #2 (clean context)
      → Task 2 completes, commits, exits
  → TaskOutput(block=true) returns
  → Parent session remains clean
```

### Resume Behavior

If the parent session is interrupted while waiting, the script continues running in the background. The user can re-run `aet-work run-scripted`; the script will skip already-in-progress or done tasks because the queue file is the source of truth.

## Open Questions

1. Should the script attempt to auto-install or validate that the detected CLI is in `PATH` before spawning?
2. How do we handle the case where the agent CLI requires an interactive TTY and cannot run headless?
3. Should we include a `--dry-run` flag in the generated script that previews commands without executing?

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
