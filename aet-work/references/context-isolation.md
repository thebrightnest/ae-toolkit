# Context Isolation in the AFK Loop

## The Problem

An AFK loop running multiple tasks in one session accumulates context:

- Task 1: 20k tokens consumed
- Task 2: +20k tokens = 40k total
- Task 3: +20k tokens = 60k total
- Task 4: agent starts missing obvious things, repeating itself, ignoring constraints

This is not hypothetical. The "smart zone" for LLMs is ~100k tokens. After that, quality degrades progressively.

## The Solution

Explicit context clearing between every task:

```
Task N completes
  → CLEAR CONTEXT
  → RE-PRIME (5–15k tokens)
  → Task N+1 starts with clean slate
```

## How to Clear Context (Agent-Agnostic)

The skill emits a mandatory instruction:

> "🔄 CONTEXT CLEAR REQUIRED. Stop here and clear your context window. Use /clear, restart your agent, or start a new session. Then say 'Context cleared, continuing loop' and I will re-prime before the next task."

The agent follows this instruction. No special runtime needed.

## What Re-Prime Loads

After clearing, run aet-prime to load:
- AGENTS.md (1–3k tokens)
- Last 5–10 git commits (1–3k tokens)
- Current branch name (<1k tokens)
- The next task's plan.md (2–5k tokens)

**Total: 5–15k tokens per task.** The loop can run 20+ tasks without degradation.

## Without Context Isolation

| Task # | Cumulative Context | Agent Quality |
|--------|-------------------|---------------|
| 1 | 20k | ✅ Sharp |
| 2 | 40k | ✅ Good |
| 3 | 60k | ⚠️ Slight decline |
| 4 | 80k | ⚠️ Missing details |
| 5 | 100k | ❌ Repetitive, confused |
| 6+ | 120k+ | ❌ Unreliable |

## With Context Isolation

| Task # | Context Per Task | Agent Quality |
|--------|-----------------|---------------|
| 1 | 15k | ✅ Sharp |
| 2 | 15k | ✅ Sharp |
| 3 | 15k | ✅ Sharp |
| ... | 15k | ✅ Sharp |
| 20 | 15k | ✅ Sharp |
