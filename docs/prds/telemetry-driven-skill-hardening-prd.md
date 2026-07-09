---
id: telemetry-driven-skill-hardening
---

# PRD: Telemetry-Driven Skill Hardening (Revised)

## Overview

Apply the top recurring patterns surfaced by `aet-evolve mine-learnings` to the AE Toolkit skills. The goal is to reduce friction, retry loops, and review noise across projects that use the toolkit by hardening the skills that agents invoke most often.

> **Scope change from original PRD:** tdsh-01 (dependency warmup / `symlink_dependencies`) has been removed. See `docs/retros/2026-07-09-symlink-dependencies-workaround-retro.md` for the rationale. The symptom it targeted — missing dependency roots in parallel worktrees — is a downstream effect of orchestrator parallelism and disk usage, not a setup defect that belongs in `aet-setup`.

## Goals

1. Catch validation failures earlier in the implementation pipeline to reduce retry loops.
2. Prefer impact-scoped tests over full-suite runs unless core framework files changed.
3. Give agents a structured stage-failure triage checklist before escalating to humans.
4. Reduce review noise by tightening `aet-review` scope to the PR base diff and ignoring project-level files.

## Non-Goals

- No new skills; only changes to existing `aet-implement`, `aet-qa`, and `aet-review` skills.
- No changes to the orchestrator, queue state model, or skill packaging format.
- No external telemetry service or cloud integration; analysis remains local-first.
- No breaking changes to existing skill triggers or primary commands.
- No stack-specific dependency-root warmup or symlink automation.

## User Stories

- As an implementer, I want `aet-implement` to run validation after every task so small errors are caught before they compound into retry loops.
- As a QA runner, I want `aet-qa` to run impact-scoped tests by default and only fall back to the full suite when core framework files changed.
- As a QA runner, I want a stage-failure triage checklist so I know what evidence to gather before asking a human.
- As a reviewer, I want `aet-review` to ignore `.gitignore`, `AGENTS.md`, and other project-level noise unless the task explicitly touches them.

## Acceptance Criteria

- [ ] `aet-implement/SKILL.md` includes a "run validation after every task" guardrail in its `implement` procedure.
- [ ] `aet-qa/SKILL.md` defaults to impact-scoped tests and defines the exact conditions for running the full suite.
- [ ] `aet-qa/SKILL.md` includes a stage-failure triage checklist with required evidence fields.
- [ ] `aet-review/SKILL.md` explicitly ignores project-level noise files and scopes the diff to the PR base.
- [ ] Each changed skill is repackaged and `make validate` passes.
- [ ] A new ADR records the decision to drive skill improvements from telemetry mining.

## Technical Notes

### Validation-after-every-task

- After each task in `aet-implement`, run the relevant validation command from the plan's self-validation strategy.
- If validation fails, stop and report before proceeding to the next task.
- Do not wait until the end of the plan to run validation.

### Impact-scoped tests

- Use `git diff --name-only <pr-base>..HEAD` to identify changed files.
- Map changed files to test files via project conventions or heuristics.
- Run full suite only when the diff touches: test harness, config, shared fixtures, dependency lockfiles, or files imported by many tests.

### Stage-failure triage

- Checklist must capture: failing command/output, files touched, last successful stage, environment variables (`AET_*`), and whether the failure reproduces outside the orchestrator.
- Report is appended to the QA report, not the repo.

### Review noise filter

- Ignore changes to `.gitignore`, `AGENTS.md`, `docs/CONVENTIONS.md`, and project-level docs unless the task explicitly modifies them.
- Always scope the review diff to the PR base (`<base>..HEAD`), not the working tree.

## Open Questions

- Should the stage-failure triage checklist be mandatory before marking a task `failed`, or advisory? (Default: mandatory for tasks that will be retried.)

## Relation to Other Documents

- `docs/adr/015-telemetry-driven-skill-improvements.md` — accepted ADR establishing telemetry mining as a first-class input.
- `docs/retros/2026-07-09-symlink-dependencies-workaround-retro.md` — retro explaining why dependency warmup was removed from scope.

---

_Intake triage: This is a feature or enhancement, not a reproducible defect._

_Stage: scope-validated (revised)_
_Next step: update or close plans tdsh-02 through tdsh-05, then run `aet-work`_
