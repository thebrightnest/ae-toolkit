---
toolkit-relevant: true
---

# Retro: 2026-07-06 `aet-work run` / `aet-ship` batch

## What Went Well

- The orchestrator correctly prepared worktrees, ran the pipeline, and produced working branches for 9 independent tasks.
- `ght-01-backend-abstraction` completed a meaningful backend refactor with passing tests and a clean security audit.
- `are-07`, `are-08` produced real value: new templates, tests, and skill/checklist updates.
- `aet-ship` subagents created PRs for 8 of 9 tasks without human hand-holding.

## What Went Wrong

- **Over-granular `are-*` plans.** Five of the eight `are-*` tasks were essentially plan-stage bookkeeping plus a drive-by link fix. The underlying example templates had already landed on `origin/main` in the v0.9.1 release commit (`d974ce8`), so each plan shrank to a 2–8 line diff. This generated 8 PRs where 2–3 would have sufficed.
  - _Root cause:_ The PRD was decomposed into one plan per file, and no guardrail asked “can these be batched?”
- **Orchestrator timeout / dirty-main hygiene.** The first `aet-work run` timed out after 10 minutes, leaving the queue in an inconsistent state. A resumed run immediately halted because `.agents/work-queue.json` is tracked and the orchestrator treats its own mutations as a dirty working tree.
  - _Root cause:_ The queue file is the system's runtime memory, but it is also a tracked file that fails the orchestrator's pre-flight hygiene check.
- **Pre-existing broken link duplicated across PRs.** `docs/upgrades/README.md` contained a broken relative link. Every `are-*` branch had to fix it to pass `make validate`, so the same one-line fix appears in multiple PR diffs.
  - _Root cause:_ A repo-health issue that should have been fixed on `main` was left for each feature branch to rediscover.
- **`mine-learnings` shipped with a missing `import sys`.** The script crashed before it could scan telemetry.
  - _Root cause:_ No import-check test covered the CLI entry point.

## Learnings

- Batching rule needed: related template/example additions should share a plan/branch when each individual change is < 3 files and < 50 lines.
- Runtime queue state should not block the orchestrator that writes it; either the hygiene check must ignore `.agents/work-queue.json`, or the file should not be tracked.
- Repo-wide broken links should be fixed on `main` as soon as `make validate` starts failing; deferring them creates duplicated fixes across branches.
- CLI scripts need at least a smoke import/entry-point test.

## Action Items

- [ ] Add a batching guardrail to `docs/CONVENTIONS.md` and `.agents/templates/plan-template.md`.
- [ ] Decide whether `.agents/work-queue.json` should remain tracked; if so, update `aet-work` hygiene check to ignore it.
- [ ] Fix `docs/upgrades/README.md` broken link on `main`.
- [ ] Add a minimal import/exit-code test for `aet-evolve/bin/mine-learnings`.
