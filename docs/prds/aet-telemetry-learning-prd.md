# PRD: AET Telemetry Learning & Pipeline Efficiency

## Overview

Add the ability for the AE Toolkit to learn from its own execution telemetry across projects, and remove the pipeline inefficiencies that show up in that telemetry. The work is driven by a real project run where ~25 minutes of automated pipeline time was spent rediscovering environment gaps, re-running full test suites, and re-reading context between stages. We will make the orchestrator reuse context within a stage group, pre-warm worktree dependencies, run tests more selectively, scope review/CSO to the actual branch diff, and archive telemetry in a durable cross-project location that `aet-evolve` can mine.

## Goals

- Reduce average per-task orchestrator wall-clock time by at least 20% for projects using standard isolation.
- Eliminate repeated rediscovery of missing worktree dependencies (`node_modules`, `vendor`, etc.) by making them configurable and warmed-up once per task.
- Reduce redundant full-suite test runs during a single task's pipeline.
- Reduce review/CSO time spent on project-level diff noise (`.gitignore`, `AGENTS.md`) by scoping the diff to the PR base.
- Create a durable, user-level telemetry archive so project logs are not lost after `aet-ship` / cleanup.
- Give `aet-evolve` a miner that can surface recurring patterns across projects and propose toolkit-level learnings.

## Non-Goals

- Does not change the packaging format of `.skill` files.
- Does not introduce a database or external service for telemetry; archive stays local filesystem/JSONL.
- Does not remove OS-process isolation between tasks; we still spawn a fresh process per task.
- Does not auto-apply mined learnings without human review.
- Does not handle non-`git` version-control systems.

## User Stories

- As an AET user running `aet-work run`, I want each task's pipeline stages to share context where safe, so that the agent stops re-reading the same plan and tests.
- As a project maintainer, I want missing dependency directories in worktrees to be symlinked automatically from the parent repo, so that every stage does not rediscover the same gap.
- As a reviewer, I want `aet-review` and `aet-cso` to look only at the branch diff against the real PR base, so that unrelated project noise is ignored.
- As a toolkit maintainer, I want telemetry from many projects archived in one place, so that `aet-evolve` can detect systemic issues and suggest rule updates.

## Acceptance Criteria

- [ ] `aet-work run` on a standard-isolation task spawns one agent session per stage group, not one per stage.
- [ ] A project can declare worktree dependency symlinks in `.agents/aet-work.json`; the orchestrator creates them before the first stage runs.
- [ ] `aet-implement` and `aet-qa` instructions prefer focused/impact-scoped tests and run the full suite only once per task unless the core framework changed.
- [ ] `aet-review` and `aet-cso` compute the PR base (`origin/main` or parent branch) and review `git diff <base>..HEAD`.
- [ ] New telemetry record types (`loop`, `environment_issue`, `test_run`, `learning_candidate`) are emitted and documented.
- [ ] `aet-evolve ingest-telemetry` copies project telemetry and reports into `~/.aet/telemetry/{project-slug}/{date}-{run_id}/`.
- [ ] `aet-evolve mine-learnings` scans the archive and produces a ranked report of recurring patterns without errors.
- [ ] `make validate` and `make package` pass after all changes.

## Technical Notes

- Stage-group reuse is implemented in `aet-work/bin/orchestrator` by building a compound prompt for all stages in a `session_group`. The existing `pipeline.py` grouping is reused; `standard` isolation becomes the first group (plan-approved + implemented), the second group (qa-complete), and the third group (reviewed + secure).
- Dependency warmup lives in `aet-work/lib/worktree.py` and is called after `copy_untracked_files`. It reads `.agents/aet-work.json` with a `symlink_dependencies` array and falls back to doing nothing if the config is missing.
- The telemetry archive is intentionally simple: copy append-only JSONL files and markdown reports into a dated directory under `~/.aet/telemetry`. A future iteration can add SQLite/aggregation if the volume justifies it.
- All skill instruction changes must follow the package-deliverable rule: any rule enforced at runtime must live inside the skill's packaged files.

## Open Questions

- Should the archive be opt-in per project, or should `aet-ship` auto-export telemetry by default?
  - **Decision:** Opt-in per project. `aet-evolve ingest-telemetry` is run explicitly; no automatic export in `aet-ship`.
- Should stage-group reuse be the default for `standard`, or gated behind an env var until proven stable?
  - **Decision:** Default for `standard` isolation. `minimal` and `full` behavior is unchanged.
- Should `mine-learnings` be able to propose edits to installed skill files, or only to `.agents/learnings.jsonl`?
  - **Decision:** `mine-learnings` may _propose_ edits to skill files in the report, but it never writes to installed skill files directly. Human approval is required before any skill file change.
