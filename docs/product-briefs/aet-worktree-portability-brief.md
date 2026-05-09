# Product Brief: Agent-Agnostic Worktree Isolation for aet-implement + aet-work

**Date:** 2026-05-09
**Verdict:** BUILD
**Skill:** aet-discover diagnostic

---

## The Problem

`aet-implement` and `aet-work` contain Claude Code-specific instructions:

- `/clear` (context reset)
- `EnterWorktree` / `ExitWorktree` (branch isolation)
- `Agent` tool with `isolation: "worktree"` (sub-agent spawning)

Real users on Cursor, Windsurf, Gemini CLI, and other agents cannot adopt these skills
because the instructions literally don't exist in their tools.

Separately: `aet-work run` degrades after 3–4 tasks because accumulated context
causes hallucination and quality drop. This is observed behavior, not theoretical.

## Demand Evidence

- Users on non-Claude Code agents have asked for these skills but can't use them
- Context degradation in long aet-work loops is observed + documented in references/context-isolation.md
- The status quo is: manual branch switching + `/clear` between tasks, which is fragile and Claude Code-only

## The Insight

Git worktrees solve both problems simultaneously with zero agent-specific tooling:

- `git worktree add .worktrees/<name> -b <branch>` → branch isolation, works everywhere
- Each worktree = separate working directory → natural implementation boundary
- "Start a new session" replaces `/clear` with agent-agnostic language

Portability and reliability are the same fix.

## Narrowest Wedge (ship this week)

Remove Claude Code-specific instructions from `aet-implement/SKILL.md` and
`aet-work/SKILL.md`. Replace with:

- `git worktree` commands for branch isolation
- "Start a new session / clear your context" for context isolation (generic language)

This unblocks users on every agent immediately. Worktrees are the mechanism, not a
separate feature.

## Out of Scope (for now)

- Parallel worktree execution (v3)
- Automatic worktree cleanup
- Per-agent setup guides (Cursor-specific, Gemini-specific docs)

## Uncomfortable Truths

- The current `aet-work` skill documents the status quo (manual /clear) rather than
  solving it. The worktree update is the first real improvement to the loop.
- "Agent-agnostic" wasn't a design principle from day one — it should have been.
  This is technical debt being paid down.
