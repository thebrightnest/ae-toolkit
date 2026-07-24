# AE Toolkit

An integrated agentic engineering system. Skills are directories of instructions, examples, and reference material that guide an agent through each phase of the workflow — from discovery and planning to implementation, review, security, shipping, and release. They are designed to be installed together; the pipeline only works when the whole system is present.

---

## Current Version: 1.5.0

Last updated: 2026-07-24

---

## Core Features

### Planning Skills

Turn ideas into actionable, validated plans.

- **aet-plan** — PRD creation, goal clarification, atomic `plan.md` generation, and a `validate` command that checks plans against structure, scope, dependency, and traceability rules.
- **aet-pipeline-plan** — End-to-end planning pipeline that runs discovery, planning, and scope validation in sequence.
- **aet-validate-scope** — Stress-test plans against the existing domain model, terminology, and documented decisions.

### Execution Skills

Run plans with isolation, quality gates, and traceability.

- **aet-work** — Work queue management and sequential or parallel task execution. Spawns isolated sessions per task in git worktrees, with curated sprint intake, evidence-gated completion, live-run visibility in the panel, usage-cost telemetry, optional GitHub Issues or git-refs backend, night-shift runtime resilience, and configurable branch models including single-PR integration mode.
- **aet-implement** — Fresh-session implementation from an approved `plan.md`.
- **aet-tdd** — Test-driven development with red-green-refactor loops and vertical tracer bullets.

### Quality and Security Skills

Verify code before it ships.

- **aet-review** — Staff-level code review with multi-lens checks.
- **aet-cso** — Diff-focused security audit.
- **aet-qa** — Automated QA with tiered validation. Defaults to impact-scoped tests and falls back to the full suite when needed.
- **aet-verify** — Conditional live verification with evidence capture.

### Shipping and Release Skills

Land code cleanly and document releases.

- **aet-ship** — Pre-merge validation, PR creation, merge verification, direct merge via `aet ship merge`, and provider-specific merge-guard harness detection. Accepts plan paths or bare task ids across open, gate, close, and merge.
- **aet-release-prep** — Release preparation: commit analysis, changelog updates, and version bump suggestions.
- **aet-sync-docs** — Sync PRD and `plan.md` to reflect what was actually built.

### Maintenance Skills

Keep projects and the toolkit itself healthy.

- **aet-setup** — Bootstrap or upgrade projects with best-practice documentation, AI guardrails, optional pre-push hook gates, and `aet setup verify` / `aet setup bootstrap` helpers for trunk resolution and required `.gitignore` entries.
- **aet-upgrade** — Dependency and framework upgrade planning with breaking-change analysis.
- **aet-bug-report** — Structured bug investigation and fixing.
- **aet-evolve** — System evolution through retrospectives and rule updates. Mines telemetry archives and narrative reports for cross-project patterns, and includes `aet-retro` for automated post-run review.

---

## Integrations

| Name                  | Description                                                                                                                          |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `make install-skills` | Symlinks all skills to `~/.agents/skills/` for local agent use.                                                                      |
| `aet` binary          | A single multicall binary that dispatches to every toolkit subcommand; `aet setup link` installs the console script on `PATH`. |
| `aet size` commands   | Report and backfill delivered diff-size measurements for closed plans to calibrate sizing estimates. |
| Telemetry panel       | A local, stdlib-launched viewer for the telemetry archive, with a Plans lens for browsing plans, pipeline progress, and run history. |
| GitHub Issues         | Optional task backend for `aet-work`. Syncs queue state with labeled GitHub issues.                                                  |
| git-refs backend      | `aet-work` task backend that stores queue state in git refs instead of local JSON files; now the default written backend.              |
| Git                   | All skills use git commands for branch, worktree, and merge operations; no agent-specific APIs required.                             |

---

## What's New

### What's New in v1.5.0

- **Configurable branch model** — `trunk_branch`, `integration_branch`, and `integration_mode` are resolved from config, environment, or CLI instead of hardcoding `main`; `aet setup verify` reports the resolved trunk and its provenance.
- **Single-PR integration mode** — squash multiple task branches into a shared integration branch instead of opening one PR per task, with serialized integration and re-validation after rebase.
- **`aet ship merge` direct merges** — merge a task branch straight into a target branch with pre-merge conflict detection; `--branch` defaults to `main`.
- **Bare task IDs across `aet ship`** — `open`, `gate`, `close`, and `merge` accept a bare task id and resolve it to the conventional plan path.
- **Delivered-size calibration** — `aet size report` and `aet size backfill` aggregate diff-size measurements from closed plans to improve future size estimates.
- **Cleaner intake and status UX** — `init-queue` only validates plans actually entering the sprint, and `aet status` summarizes empty sections in compact sentences.

### What's New in v1.2.0

- **Night-shift runtime resilience** — unattended runs now recover from stalls, overloads, and failures with circuit breakers, a stall watchdog, failure-taxonomy routing, and quarantine support.
- **Fail-closed plan intake** — `aet-work` rejects malformed plans at `add`, `init-queue`, and `sync` using the new `aet plan validate` check suite.
- **Optional zero-review auto-merge** — `desk --eligibility` and a track-record policy can let trusted, low-risk tasks merge without manual review; disabled by default.
- **Better ship decisions from `aet desk`** — risk-ranked awaiting-merge view, evidence bundles, and direct merge/abandon actions.
- **Smarter merge guards** — `aet-ship` detects provider-specific merge-guard requirements and adapts behavior accordingly.

### What's New in v1.1.0

- **Live execution panel** — `aet-work status` now shows running tasks with auto-refreshing live-run visibility and a cleaner dependency/blocker table.
- **Usage-cost telemetry** — agent CLI usage and kimi wire files are captured into the telemetry archive, with a cost view in the panel.
- **`aet gate submit` verdict writer** — record skill verdicts directly from the CLI, feeding the orchestrator's evidence-gated completion.
- **git-refs as the default task backend** — queue state now lives in git refs by default, with tamper-evidence and a pre-push hook gate in `aet-setup`.
- **Validation freshness** — verdicts carry a `tree_hash` and freshness query so QA gates can detect stale evidence.
- **Test-run extraction and classification** — wire logs yield structured test-run records classified by verdict scope.
- **Structural pattern mining** — `mine-learnings` and `aet-retro` can surface recurring structural patterns across projects.
- **Faster, slimmer validation** — `pytest-xdist` parallelizes the suite and `aet-setup` drops Prettier from the default scaffold.

### What's New in v1.0.0

- **One `aet` command for the whole toolkit** — a single multicall binary now dispatches to every subcommand, self-installs, and repairs `PATH` on invocation, replacing the many separate legacy binaries.
- **Local telemetry panel with a Plans lens** — browse plans, pipeline progress, consolidated timelines, and run history from a stdlib-launched viewer of the telemetry archive.
- **Curated sprint intake** — `aet-work` sync no longer auto-adds plans; intake parks them as ready or blocked so you decide what enters the queue.
- **More trustworthy unattended runs** — the orchestrator uses locked, atomic queue writes with a tamper-evident guard, requires a structured evidence verdict before completing a task, and shuts down batch children cleanly by process group.
- **git-refs task backend option** — `aet-work` can store queue state in git refs as an alternative to local JSON files or GitHub Issues.
- **Pipelines as data** — pipeline stage sequences are declared in a packaged workflow file and linted by `make validate`, instead of being hardcoded.

### What's New in v0.10.0

- **Automated run review with `aet-retro`** — after every `aet-work run`, `aet-evolve` can surface errors, timeouts, and improvement opportunities from telemetry archives and narrative reports.
- **GitHub Issues as a task backend** — `aet-work` can mirror the queue to GitHub Issues, so task state is visible to the whole team and survives local worktree cleanup.
- **Faster, quieter QA** — `aet-qa` now runs only the tests that touch changed files by default, falling back to the full suite when coverage requires it.
- **More resilient unattended runs** — the orchestrator uses per-task timeouts and inner heartbeats, refreshes worktrees from `origin/main`, and guarantees a final summary even when a task crashes.
- **Cleaner review focus** — `aet-review` filters out project-level noise so reviewers stay focused on the actual diff.

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
