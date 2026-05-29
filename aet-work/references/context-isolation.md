# Context Isolation in the AFK Loop

## The Problem

An AFK loop running multiple tasks in one session accumulates context:

- Task 1: 20k tokens consumed
- Task 2: +20k tokens = 40k total
- Task 3: +20k tokens = 60k total
- Task 4: agent starts missing obvious things, repeating itself, ignoring constraints

This is not hypothetical. The "smart zone" for LLMs is ~100k tokens. After that, quality degrades progressively.

## Why Cooperative Isolation Failed

Earlier versions of `aet-work` attempted a cooperative approach: the skill instructed the agent to clear its own context between tasks (via `/clear`, session restart, or equivalent). This failed on every tested runtime for the same reason — **no agent can reset its own context and continue executing skill instructions mid-session.** The instruction is ignored, context leaks, and quality degrades.

The only reliable solution is to move isolation out of the skill and into the OS process layer.

## OS-Process Isolation — `aet-work run`

`aet-work run` generates a bash orchestrator that spawns a fresh OS process for every task:

```
Parent agent session (clean)
  → detects runtime
  → generates scripts/.aet-work-orchestrator.sh
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context, fresh process)
      → Task 1 completes, commits, exits
    → Script spawns Agent CLI process #2 (clean context, fresh process)
      → Task 2 completes, commits, exits
  → TaskOutput(block=true) returns
  → Parent session remains clean
```

**Why this works:**

- **Physical process boundary** — the old context is unreachable; no compliance needed.
- **Universal** — works on every runtime that exposes a CLI (Claude Code, Kimi, Cursor, etc.).
- **Branch isolation enforced** — each task runs in its own git worktree on its own branch.
- **Queue state is the memory** — `.agents/work-queue.json` persists across process boundaries.

**Trade-offs:**

- Requires the agent CLI to support non-interactive/print mode
- Each task incurs CLI startup overhead (2–10s depending on runtime)
- The parent session must remain open to wait for the background script
- Interactive approval gates inside skills must be bypassed when running headless. The orchestrator sets `AET_EXECUTION_MODE=unattended`; skills that gate on human judgment (e.g., `aet-implement`, `aet-pipeline-implement`) detect this and skip the gate, logging the bypass for auditability.

## Runtime Self-Detection

`aet-work run` does not scan `PATH` or maintain a hard-coded priority list. The agent executing the skill **self-reports** its own CLI command and flags. This means:

- Kimi Code running `aet-work run` generates a script that calls `kimi`
- Claude Code running `aet-work run` generates a script that calls `claude`
- A new agent CLI works immediately without any changes to the skill

The skill asks the currently running agent: "What CLI command and flags should the orchestrator use to spawn a fresh process of you?" The agent answers based on its own identity.

### Known Runtime Capabilities

| Runtime             | Non-interactive CLI | `aet-work run` support |
| ------------------- | ------------------- | ---------------------- |
| Claude Code         | `claude --print`    | ✅ Supported           |
| Kimi Code CLI       | `kimi --print`      | ✅ Supported           |
| Cursor              | Limited             | ⚠️ Check CLI docs      |
| GitHub Copilot Chat | Not available       | ❌ Not supported       |
| Aider               | `aider --message`   | ✅ Supported           |

> This table reflects known capabilities as of the skill's last update. Runtimes evolve; verify with your specific version.

## Without Context Isolation

| Task # | Cumulative Context | Agent Quality           |
| ------ | ------------------ | ----------------------- |
| 1      | 20k                | ✅ Sharp                |
| 2      | 40k                | ✅ Good                 |
| 3      | 60k                | ⚠️ Slight decline       |
| 4      | 80k                | ⚠️ Missing details      |
| 5      | 100k               | ❌ Repetitive, confused |
| 6+     | 120k+              | ❌ Unreliable           |

## With Context Isolation

| Task # | Context Per Task | Agent Quality |
| ------ | ---------------- | ------------- |
| 1      | 15k              | ✅ Sharp      |
| 2      | 15k              | ✅ Sharp      |
| 3      | 15k              | ✅ Sharp      |
| ...    | 15k              | ✅ Sharp      |
| 20     | 15k              | ✅ Sharp      |

## Parallel Execution Is Safe

Parallel execution of independent tasks is safe because isolation is enforced at two independent layers:

1. **Git worktree isolation** — each task runs in a separate git worktree on its own branch. Files, git state, and branch history are physically separate. Two tasks cannot collide on the same working tree because each has its own `.git/worktrees/<id>` directory.

2. **OS process isolation** — each task runs in its own agent CLI process. There is no shared memory, no shared context, and no way for one agent to read another's state. The only shared resource is the queue file, and access to that is serialized.

Because these layers are independent, doubling the number of concurrent tasks does not weaken isolation. Task #1 and Task #10 are as isolated from each other as Task #1 and Task #2 were in sequential mode.

## Drain-on-Failure Behavior

When a task fails under parallel execution, the orchestrator does not kill the other running tasks. Instead it:

1. Records the failed task's status
2. Stops spawning new tasks
3. Waits for all currently running tasks to finish
4. Exits with a non-zero status

This preserves work already in progress. If Task #3 fails while Tasks #4 and #5 are running, Tasks #4 and #5 complete normally and their results are saved. Only new spawns are halted. The user can inspect the failed branch, fix the issue, and re-run `aet-work run` to resume.

## Queue-Update Invariant

Under parallel execution, only the main orchestrator loop reads and writes `.agents/work-queue.json`. Child processes (the agent CLI invocations) do not touch the queue file. This eliminates race conditions without requiring file locking:

- The orchestrator spawns a child
- The child runs to completion and exits
- The orchestrator's `wait` returns, and only then does it update the queue

Because bash job control guarantees only one `wait` returns at a time, queue mutations are naturally serialized. No lock file, no `flock`, no database is required.

## Further Reading

- `references/orchestrator-template.sh` — the template used by `run` to generate the orchestrator
- `references/afk-loop-orchestrator.sh` — a standalone, heavily commented example script you can adapt for custom orchestration
- `references/parallel-execution.md` — deep dive on concurrency caps, bash job control, and resume behavior
