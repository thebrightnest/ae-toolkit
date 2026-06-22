# AE Toolkit

A modular skill suite for AI coding agents. Each skill is a self-contained package of instructions, examples, and reference material that guides an agent through a specific phase of agentic engineering — from discovery and planning to implementation, review, security, shipping, and release.

---

## Current Version: 0.8.0

Last updated: 2026-06-22

---

## Core Features

### Planning Skills

Turn ideas into actionable, validated plans.

- **aet-discover** — Product-definition diagnostic with forcing questions to validate demand and narrow the wedge.
- **aet-plan** — PRD creation, goal clarification, and atomic `plan.md` generation.
- **aet-pipeline-plan** — End-to-end planning pipeline that runs discovery, planning, and scope validation in sequence.
- **aet-validate-scope** — Stress-test plans against the existing domain model, terminology, and documented decisions.

### Execution Skills

Run plans with isolation, quality gates, and traceability.

- **aet-work** — Work queue management and sequential or parallel task execution. Spawns isolated sessions per task in git worktrees.
- **aet-implement** — Fresh-session implementation from an approved `plan.md`.
- **aet-tdd** — Test-driven development with red-green-refactor loops and vertical tracer bullets.

### Quality and Security Skills

Verify code before it ships.

- **aet-review** — Staff-level code review with multi-lens checks.
- **aet-cso** — Diff-focused security audit.
- **aet-qa** — Automated QA with tiered validation.
- **aet-verify** — Conditional live verification with evidence capture.

### Shipping and Release Skills

Land code cleanly and document releases.

- **aet-ship** — Pre-merge validation, PR creation, and merge verification.
- **aet-release-prep** — Release preparation: commit analysis, changelog updates, and version bump suggestions.
- **aet-sync-docs** — Sync PRD and `plan.md` to reflect what was actually built.

### Maintenance Skills

Keep projects and the toolkit itself healthy.

- **aet-setup** — Bootstrap or upgrade projects with best-practice documentation and AI guardrails.
- **aet-upgrade** — Dependency and framework upgrade planning with breaking-change analysis.
- **aet-bug-report** — Structured bug investigation and fixing.
- **aet-evolve** — System evolution through retrospectives and rule updates. Mines telemetry archives and narrative reports for cross-project patterns.

---

## Integrations

| Name                   | Description                                                                                              |
| ---------------------- | -------------------------------------------------------------------------------------------------------- |
| `.skill` packages      | Skills are distributed as plain zip archives of the skill directory, installable anywhere.               |
| `make install-skills`  | Symlinks all skills to `~/.claude/skills/` for local agent use.                                          |
| `install-aet-binaries` | Installs skill executables such as `ingest-telemetry` and `mine-learnings` on `PATH`.                    |
| Git                    | All skills use git commands for branch, worktree, and merge operations; no agent-specific APIs required. |

---

## What's New

### What's New in v0.8.0

- **Telemetry learning system** — capture richer run data, warm worktree dependencies, reuse isolated stage sessions, scope tests to the diff, and archive findings across projects so the same lesson never has to be relearned.
- **Centralized skill binaries** — `aet-setup` now installs skill executables on `PATH` consistently, starting with telemetry mining tools.
- **Smarter queue intake** — `aet-work` reconciles terminal tasks from history and git automatically, and only validates new plans instead of re-scanning the entire queue.
- **Reliable unattended runs** — orchestrator children skip redundant main-hygiene checks, and merge verification works from recorded merge commits without a local branch.

### What's New in v0.7.0

- **Deterministic work state** — `aet-work` now records state forward through validated transitions, seals completed work to an append-only history log, and never re-derives status from git during normal reads.
- **Validated plan intake** — every plan must declare `id`, `blocked_by`, and `size` in YAML frontmatter; malformed or legacy plans are rejected at intake.
- **Reliable merge recording** — `aet-state record-merge` resolves the real squash-merge SHA automatically, so finished tasks never resurrect as unblocked.
- **Safer single-task runs** — `aet-work run-one` now enforces branch/worktree hygiene, confirms the plan file exists before spawning, and emits telemetry.
- **aet-design-system-creation commands** — new design-system, design-review, and design-check command workflows for design-driven projects.
- **aet-validate-scope closure checks** — planning and validation skills now enforce closure discipline before work proceeds.

### What's New in v0.6.0

- **aet-work** now shows only active tasks in `status` and archives terminal tasks during `cleanup`.
- **Unified orchestrator** cleanup is complete, with `aet-plan` implementation flows routed through `aet-work`.
- **aet-ship** and **aet-work** now guarantee clean PR diffs by branching worktrees from `origin/main`, rebasing independent branches before shipping, detecting stacked branches, and auditing PR scope.
- **Orchestrator reliability fixes** ensure real CLI flags are used, queue metadata is preserved, and untracked plans are copied into worktrees.

---

_This file is maintained by `aet-release-prep`. Do not delete historical "What's New" sections._
