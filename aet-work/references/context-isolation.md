# Context Isolation in the AFK Loop

## The Problem

An AFK loop running multiple tasks in one session accumulates context:

- Task 1: 20k tokens consumed
- Task 2: +20k tokens = 40k total
- Task 3: +20k tokens = 60k total
- Task 4: agent starts missing obvious things, repeating itself, ignoring constraints

This is not hypothetical. The "smart zone" for LLMs is ~100k tokens. After that, quality degrades progressively.

## Two Kinds of Isolation

| Property    | Cooperative (skill-only)      | Guaranteed (OS-process)    |
| ----------- | ----------------------------- | -------------------------- |
| Mechanism   | Agent clears its own context  | OS spawns a new process    |
| Reliability | Depends on runtime support    | Works on any OS with a CLI |
| Speed       | Fastest (no startup overhead) | Slower (CLI boot per task) |
| Command     | `aet-work run`                | `aet-work run-scripted`    |

### Cooperative Isolation — `aet-work run`

The skill emits a mandatory instruction at steps 6 and 14:

> "🔄 CONTEXT CLEAR REQUIRED. Stop here and clear your context window. Use /clear, restart your agent, or start a new session. Then say 'Context cleared, continuing loop' and I will re-prime before the next task."

**Whether the agent actually complies depends on the runtime.** Some agents honor `/clear` perfectly. Others lack the feature, ignore the instruction, or run in a UI that cannot reset mid-conversation. When compliance fails, context leaks and quality degrades.

**What Re-Prime Loads:**

After clearing, run aet-prime to load:

- AGENTS.md (1–3k tokens)
- Last 5–10 git commits (1–3k tokens)
- Current branch name (<1k tokens)
- The next task's plan.md (2–5k tokens)

**Total: 5–15k tokens per task.** The loop can run 20+ tasks without degradation — if the agent resets reliably.

### Guaranteed Isolation — `aet-work run-scripted`

When cooperative isolation is insufficient, `run-scripted` generates a bash orchestrator that spawns a fresh OS process for every task:

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

**Why this is guaranteed:**

- **Physical process boundary** — the old context is unreachable; no compliance needed.
- **Universal** — works on every runtime that exposes a CLI (Claude Code, Kimi, Cursor, etc.).
- **Branch isolation enforced** — each task runs in its own git worktree on its own branch.
- **Queue state is the memory** — `.agents/work-queue.json` persists across process boundaries.

**Trade-offs:**

- Requires the agent CLI to support non-interactive/print mode
- Each task incurs CLI startup overhead (2–10s depending on runtime)
- The parent session must remain open to wait for the background script

## Runtime Capability Reference

| Runtime             | `/clear` or equivalent     | Non-interactive CLI | Recommended mode                           |
| ------------------- | -------------------------- | ------------------- | ------------------------------------------ |
| Claude Code         | `/clear` available         | `claude --print`    | `run` if monitored; `run-scripted` for AFK |
| Kimi Code CLI       | `/clear` available         | `kimi --print`      | `run` if monitored; `run-scripted` for AFK |
| Cursor              | Session-based, no `/clear` | Limited             | `run-scripted`                             |
| GitHub Copilot Chat | Per-conversation reset     | Not available       | `run` only; manual queue advancement       |
| Aider               | `/clear` available         | `aider --message`   | `run` if monitored; `run-scripted` for AFK |

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

## When to Use Which

| Situation                                      | Command to use |
| ---------------------------------------------- | -------------- |
| Agent supports `/clear` and you are monitoring | `run`          |
| Context degradation observed mid-loop          | `run-scripted` |
| Night shift / unattended execution             | `run-scripted` |
| Agent CLI unknown or unavailable               | `run`          |
| Need fastest possible loop (minimal overhead)  | `run`          |
| Running on a runtime with no `/clear`          | `run-scripted` |

## Further Reading

- `references/orchestrator-template.sh` — the template used by `run-scripted` to generate the orchestrator
- `references/afk-loop-orchestrator.sh` — a standalone, heavily commented example script you can adapt for custom orchestration
