# AE Toolkit

An integrated agentic engineering system. Skills are directories of instructions, examples, and reference material that guide an agent through each phase of the workflow — from discovery and planning to implementation, review, security, shipping, and release. They are designed to be installed together; the pipeline only works when the whole system is present.

---

## Current Version: 0.9.1

Last updated: 2026-07-06

---

## Core Features

### Planning Skills

Turn ideas into actionable, validated plans.

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
| `make install-skills`  | Symlinks all skills to `~/.agents/skills/` for local agent use.                                          |
| `install-aet-binaries` | Installs skill executables such as `mine-learnings` on `PATH`.                                           |
| Git                    | All skills use git commands for branch, worktree, and merge operations; no agent-specific APIs required. |

---

## What's New

### What's New in v0.9.1

- **Correct installation URLs** — `README.md` now points to the right repository (`https://github.com/thebrightnest/ae-toolkit`), so `npx skills add` commands work out of the box.
- **Clearer setup path** — installation examples use the standard `.agents/skills` directory and show the correct helper-binary setup step.

### What's New in v0.9.0

- **Telemetry that never gets lost** — `aet-work` writes execution logs directly to the user-level archive, so background runs and deleted worktrees no longer lose telemetry before it can be mined.
- **One-click cross-project learning** — `aet-evolve mine-learnings` reads the archive directly without a manual `ingest-telemetry` step.
- **Right-sized isolation per task** — plans can declare `pipeline: minimal|standard|full` so low-risk tasks run faster and high-risk changes keep full stage isolation.
- **Run health at a glance** — every orchestrator run produces a `last-run.json` summary with success/failure counts and total time.

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
