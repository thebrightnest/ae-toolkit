# Product Brief: Hybrid Orchestrator for aet-work Context Isolation

**Date:** 2026-05-13
**Verdict:** BUILD
**Skill:** aet-discover diagnostic

---

## The Problem

`aet-work run` degrades after 3–4 tasks because accumulated context causes hallucination, task corruption, and quality drop. The May 2026 `aet-worktree-portability-brief` proposed replacing Claude-specific `/clear` with generic "start a new session" language. This was tested and found **insufficient** — no mainstream agent runtime (Claude Code, Kimi Code, Cursor, Windsurf) supports automatic context reset from skill instructions alone.

Additional observed failures when running sequentially:

- Tasks corrupted by cross-context contamination
- Git branches/worktrees overlapping due to state leakage between tasks
- Forced sequential execution wastes time that could be parallelized

## Demand Evidence

- Direct repeated personal experience: `aet-work` corrupted multiple tasks; user abandoned the skill entirely
- Status quo is manual `aet-implement` execution task-by-task — the automation is worse than the manual path
- User attempted to use the skill as documented; it failed in practice, not theory

## The Insight

A **hybrid approach** sidesteps the "skills cannot force context reset" limitation:

1. The **skill** generates an orchestrator script tailored to the local runtime
2. The **agent** spawns the script as a background OS process (`Shell` with `run_in_background`)
3. The **script** handles the dirty work: spawning fresh agent processes per task, managing worktrees, updating the queue
4. The **agent** waits for completion (`TaskOutput` with `block`) and reports results
5. The parent session stays clean because it delegates all heavy context consumption to child processes

This pattern is agent-agnostic: the generated script adapts to whatever CLI is installed (`claude`, `kimi`, `codex`, etc.).

## Narrowest Wedge (ship this week)

A single new `aet-work` command: `run-scripted`

**Procedure:**

1. Read `.agents/work-queue.json`
2. Generate `scripts/.aet-work-orchestrator.sh` with embedded task list and worktree commands
3. Spawn via `Shell(run_in_background=true)`
4. Wait via `TaskOutput(block=true)`
5. Report results and update queue status

**Scope limits:**

- Bash-only (no Windows support yet)
- Sequential within the script for the first version (parallel comes after the isolation mechanism works)
- One runtime target per invocation (user sets `AGENT_CLI` env var)

## Out of Scope (for now)

- True parallel execution inside the orchestrator (v2)
- Native runtime plugins or extensions for Claude Code / Kimi Code
- Automatic worktree cleanup
- Cross-platform PowerShell/CMD support

## Uncomfortable Truths

- The previous `aet-worktree-portability-brief` was wrong about "start a new session" being a viable fix. It assumed agent runtimes would obey skill instructions. They don't.
- This solution admits that **skills alone cannot solve context isolation**. The AE Toolkit must embrace "skill + generated artifacts" (scripts, config, etc.) to handle problems outside the context window.
- The famous Claude Code "ralph-loop" was a shell script for exactly this reason. We are rediscovering what was already proven in the wild.

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
