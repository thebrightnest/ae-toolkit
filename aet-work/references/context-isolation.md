# Context Isolation in the AFK Loop

## The Problem

An AFK loop running multiple tasks in one session accumulates context:

- Task 1: 20k tokens consumed
- Task 2: +20k tokens = 40k total
- Task 3: +20k tokens = 60k total
- Task 4: agent starts missing obvious things, repeating itself, ignoring constraints

This is not hypothetical. The "smart zone" for LLMs is ~100k tokens. After that, quality degrades progressively.

## The Solution: Hybrid Orchestration

`aet-work` provides two isolation mechanisms. Use the stronger one when the standard loop shows degradation.

### Level 1 — Skill-Only Isolation (the `run` command)

Explicit context clearing between every task:

```
Task N completes
  → CLEAR CONTEXT
  → RE-PRIME (5–15k tokens)
  → Task N+1 starts with clean slate
```

The skill emits a mandatory instruction:

> "🔄 CONTEXT CLEAR REQUIRED. Stop here and clear your context window. Use /clear, restart your agent, or start a new session. Then say 'Context cleared, continuing loop' and I will re-prime before the next task."

The agent follows this instruction. No special runtime needed.

**What Re-Prime Loads:**

After clearing, run aet-prime to load:

- AGENTS.md (1–3k tokens)
- Last 5–10 git commits (1–3k tokens)
- Current branch name (<1k tokens)
- The next task's plan.md (2–5k tokens)

**Total: 5–15k tokens per task.** The loop can run 20+ tasks without degradation.

**Limitation:** This relies on the agent's compliance with the context-clear instruction. Some runtimes or user workflows do not support session resets mid-conversation. In those cases, context still leaks.

### Level 2 — OS Process Isolation (the `run-scripted` command)

When skill-only isolation is insufficient, `run-scripted` generates a bash orchestrator that spawns a fresh OS process for every task:

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

**Why this works when skill-only fails:**

- **No agent compliance required** — the OS spawns a new process; the old context is physically unreachable.
- **Works on every runtime** — as long as the agent exposes a CLI, the script can invoke it.
- **Branch isolation guaranteed** — each task runs in its own git worktree on its own branch.
- **Queue state is the memory** — `.agents/work-queue.json` persists across process boundaries.

**Trade-offs:**

- Requires the agent CLI to support non-interactive/print mode
- Each task incurs CLI startup overhead
- The parent session must remain open to wait for the background script

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

| Situation                                     | Command to use |
| --------------------------------------------- | -------------- |
| Agent supports `/clear` or session restart    | `run`          |
| Context degradation observed mid-loop         | `run-scripted` |
| Night shift / unattended execution            | `run-scripted` |
| Agent CLI unknown or unavailable              | `run`          |
| Need fastest possible loop (minimal overhead) | `run`          |
