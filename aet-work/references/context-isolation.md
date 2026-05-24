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

## Further Reading

- `references/orchestrator-template.sh` — the template used by `run` to generate the orchestrator
- `references/afk-loop-orchestrator.sh` — a standalone, heavily commented example script you can adapt for custom orchestration
