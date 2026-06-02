# Toolkit-Level Branch Safety

## Status

Accepted

**Validated by:** `workflow-audit-2026-06-01.md` — Coverage Batch 2 cleanup confirmed the same pattern across TEST-5, E2E-critical-journeys, KNW-T1, and TEST-3. Local branch deletion alone is insufficient; remote branches persist and accumulate post-merge commits.

## Context

Two completed feature branches were deleted after being "merged," but their commits never reached `origin/main`. A subsequent `git reset --hard origin/main` silently discarded the local merge commits, leaving ~20 hours of work as dangling commits. The root cause was that `git branch -d` only checks if a branch is merged into **local HEAD**, not `origin/main`.

A project-level workaround was added to `AGENTS.md` and `.agents/commands/branch-cleanup.md`, but this approach has critical weaknesses: it is human-dependent, per-project, invisible to agents unless explicitly loaded, and does not compound across projects.

## Decision

Enforce branch safety at the **toolkit skill level** rather than relying on project-level `AGENTS.md` rules. Specifically:

1. `aet-ship` verifies `git merge-base --is-ancestor HEAD origin/main` before any branch deletion
2. `aet-pipeline-implement` adds a `merged` stage after `synced` to distinguish "docs updated" from "code is on main"
3. `aet-work` tracks `merge_verified` in the work queue and checks the previous task's merge status before starting the next task

This establishes a toolkit convention: **the pipeline owns the transition from "code is ready" to "code is on main,"** not the human's memory or a project-specific rule.

## Consequences

- Every AET project benefits from the fix simultaneously — one improvement compounds across all users
- The verification gate is active and automatic; the pipeline halts with an actionable message if the check fails
- Old work queues without `merge_verified` continue to function (treated as unverified, not broken)
- SKILL.md files grow by ~60 lines total across three skills, but remain under the 400-line limit
- Project-level `AGENTS.md` branch-cleanup rules become redundant once this toolkit fix is released

## Alternatives Considered

- **Git hooks** — Rejected. Hooks are project-local, invisible to agents, and can be bypassed.
- **Wrapper scripts / aliases** — Rejected. Aliases are user-local; AET is designed to be agent-driven.
- **Enhanced `aet-evolve` retro detection** — Rejected. Retroactive detection is too late; the fix must be preventive.
- **Project-level `AGENTS.md` rules** — Rejected as the primary mechanism. They help one project but do not scale; the next AET user on a different repo will hit the same bug.
