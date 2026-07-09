---
date: 2026-07-09
author: agent-review
trigger: telemetry-driven-skill-hardening PRD review
---

# Retro: `symlink_dependencies` as a Session Workaround

## What happened

The `symlink_dependencies` mechanism was introduced during an agent session that was hitting disk-space limits while spawning many parallel git worktrees. Each worktree was copying large dependency roots (`node_modules`, `vendor`, `.venv`), so the agent autonomously created a symlink-based sharing mechanism and wrote it to `.agents/aet-work.json`.

That session fix was later surfaced by `aet-evolve mine-learnings` as a recurring pattern and proposed for promotion into `aet-setup` via the Telemetry-Driven Skill Hardening PRD (tdsh-01).

## Why it looked like a good idea

- It stopped the immediate disk-space failures.
- The telemetry showed many "missing dependency root" environment issues.
- It was a concrete, automatable mitigation.

## Why it is a workaround, not a solution

The telemetry captured a **symptom** (fresh worktrees lacking dependency roots) caused by a deeper problem:

1. The orchestrator was spawning too many parallel worktrees for the available disk.
2. Each worktree performed full dependency installs instead of reusing a shared cache.
3. The host environment was not sized for the parallelism being requested.

Symlinking dependency roots into worktrees does not fix any of those causes. Worse, it introduces new failure modes:

- **Cross-worktree contamination:** builds, installs, or mutations in one worktree affect all others.
- **Version skew:** tasks needing different dependency versions compete for the same real directory.
- **Race conditions:** parallel installs against the same target are unsafe.
- **Cleanup hazards:** deleting a worktree can accidentally remove the shared root if symlink semantics are misunderstood.
- **Stack bias:** it hardcodes Node/PHP/Python assumptions into a stack-agnostic toolkit.

## Relation to ADR-015

ADR-015 says telemetry mining should inform "documentation and guardrails, not autonomous skill edits." The original `symlink_dependencies` fix is the anti-pattern that rule is meant to prevent: an agent saw a symptom, patched code autonomously, and that patch began to look like canonical tooling.

## Decision

Do not promote `symlink_dependencies` into `aet-setup` or any other skill as part of Telemetry-Driven Skill Hardening. tdsh-01 is removed from the PRD.

The real fix belongs in the `aet-work` orchestrator:

- Limit concurrent worktrees based on available disk or configured policy.
- Prefer package-manager-level caching over AET-level symlink sharing.
- Fail fast with a clear message when the host cannot support the requested parallelism.
- Document the disk/parallelism assumption rather than silently symlinking dependency roots.

## Follow-up

- Open a separate investigation on `aet-work` parallelism and worktree disk usage.
- Revisit whether `symlink_dependencies` should be deprecated or removed from existing `.agents/aet-work.json` files.
