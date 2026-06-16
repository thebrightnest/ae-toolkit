---
name: aet-work-local-orchestrator-state-parallel-prd
description: PRD for unifying AET's local workflow orchestration around derived state, agent-agnostic session isolation, clean worktrees, and conflict-aware parallel execution.
---

# PRD: Local Orchestrator, Derived State, and Parallel Execution

## Executive Summary

The AE Toolkit's current pipeline execution is split across `aet-work`, `aet-pipeline-implement`, generated per-project orchestrator scripts, hand-maintained queue JSON, and plan.md footers. The result is the exact confusion this PRD targets: ambiguous task state, stale worktrees, conflicting execution paths, and no safe way to run independent tasks in parallel.

This PRD consolidates the architecture around a single **local, agent-agnostic orchestrator** that:

1. Owns the canonical stage state machine.
2. Derives queue status from git + file-system ground truth instead of trusting stored JSON.
3. Manages worktree lifecycle deterministically.
4. Runs pipeline stages in isolated sessions via the user's chosen agent CLI.
5. Eventually executes independent tasks in parallel, but only with conflict-aware scheduling and graceful failure recovery.
6. Captures execution metadata (time, tokens, cost, outcome, isolation level) so future defaults can be evidence-based.

The scope is intentionally local and project-portable: it runs on the developer's machine, works across any project that adopts the toolkit, and adapts to Kimi Code, Claude Code, or future agent CLIs — without requiring simultaneous multi-agent execution.

## Context and Constraints

| Constraint                        | Implication                                                                                                                                                                 |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Local execution**               | The orchestrator is a local process; remote sandboxes, CI runners, and cloud execution are out of scope.                                                                    |
| **Multi-project**                 | One centralized toolkit (in `~/.claude/skills/` or equivalent) runs on many projects. No per-project generated orchestrator scripts.                                        |
| **Agent-agnostic**                | Must work with Kimi Code, Claude Code, and future CLIs via a thin adapter layer. The user does not run different agents in parallel, but may switch agents across sessions. |
| **Workflow enforcement**          | The pipeline stages and transitions must be mechanically enforced; agents cannot skip stages or invent statuses.                                                            |
| **State clarity**                 | The user must never be confused about what stage a task is in or what the work queue state is.                                                                              |
| **Clean worktrees**               | Worktrees are created, used, and destroyed deterministically. Failed tasks are preserved for inspection; completed/merged tasks are cleaned up.                             |
| **Parallel safety**               | Independent tasks may run in parallel, but tasks with overlapping file surfaces are serialized or blocked to prevent complex merge conflicts.                               |
| **Isolation as a plan parameter** | The required session-isolation level is declared by `aet-plan` per task and enforced by the orchestrator.                                                                   |

## Mission

Make the AET implementation pipeline a single, trustworthy, local execution system: correct stage transitions, derived state, clean worktrees, and safe parallelism.

## Scope

### In Scope

- `aet-work` as the sole pipeline conductor.
- Standalone `aet-state` helper for derived queue status and atomic transitions.
- Unified Python orchestrator (`aet-work/bin/orchestrator`) replacing per-project generated scripts and `aet-pipeline-implement`.
- Agent CLI adapter layer (Kimi Code, Claude Code, overrideable).
- Stage state machine enforcement from `plan-approved` through `synced`.
- Worktree lifecycle management (create, verify, clean on success, preserve on failure).
- Isolation level declared per task by `aet-plan` and enforced by the orchestrator.
- Conflict-aware parallel execution scheduling.
- Graceful drain-on-failure and resume semantics.
- Execution metadata capture (time, tokens, cost, isolation level, outcome) in an append-only local log.
- Deprecation and removal of `aet-pipeline-implement`.

### Out of Scope

- Remote execution or sandboxing.
- Real-time progress dashboards or TUIs.
- Cross-agent parallel sessions (running Kimi and Claude simultaneously on different tasks).
- Windows support (initial implementation targets macOS/Linux).
- Per-project orchestrator customization via shell scripts.
- Analysis dashboards or cost-reporting UI (the log is raw data; reports are future work).
- Prompt-craft reference docs for skill authors.

## Root Cause Analysis

| Symptom                                                              | Root Cause                                              | This PRD's Fix                                                                                   |
| -------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| "What stage is this task in?"                                        | Queue JSON, plan footer, and git state can disagree.    | `aet-state derive` recomputes status from ground truth.                                          |
| Stale worktrees left behind                                          | Cleanup is implicit and best-effort.                    | Worktree lifecycle is a core orchestrator responsibility with deterministic cleanup.             |
| `aet-pipeline-implement` vs `aet-work run` ambiguity                 | Two overlapping entry points with different behaviors.  | Single `aet-work` conductor; `aet-pipeline-implement` removed.                                   |
| Per-project generated orchestrator scripts                           | Drift between projects; fixes do not propagate.         | Centralized orchestrator inside `aet-work` ships with the toolkit.                               |
| Parallel tasks create merge conflicts                                | No check for overlapping file surfaces before spawning. | Conflict-aware scheduler serializes or warns on overlapping tasks.                               |
| Failed parallel run leaves queue half-updated                        | Queue writes are not atomic and resume is undefined.    | Main loop owns queue writes; resume re-derives state before spawning.                            |
| Cannot tell if `standard` isolation or parallelism is worth the cost | No execution metadata is captured.                      | Append-only `.agents/execution.log.jsonl` records time, tokens, cost, outcome per stage and run. |

## User Stories

### Story 1 — Single Source of Truth for Pipeline Execution

**As a developer using AET on multiple projects,** I want one command and one implementation to run the implementation pipeline, so that behavior is consistent everywhere and fixes propagate automatically.

**Acceptance Criteria:**

- `aet-work run` invokes `aet-work/bin/orchestrator` directly.
- `aet-pipeline-implement` is removed from the toolkit; its trigger phrases redirect to `aet-work run --plan-file <path>`.
- Projects no longer generate `scripts/.aet-work-orchestrator.sh` or host local orchestrator logic.
- `docs/PIPELINE.md` and `docs/use-cases.md` reference only the unified orchestrator.

### Story 2 — Derived State, Not Stored State

**As a developer checking queue status,** I want the queue to reflect what actually exists (branches, worktrees, plan footers, git ancestry) rather than what was last written to JSON, so that I never act on stale information.

**Acceptance Criteria:**

- `aet-state derive` recomputes every task's status from ground truth:
  - `plan_file` exists → planned
  - branch exists in git → in-progress
  - `git merge-base --is-ancestor` → merged/done
  - worktree directory present → has worktree
  - plan footer stage → current pipeline stage
- The JSON queue file stores only declarative data: DAG (`blocked_by`/`blocks`), `isolation_level`, `abandoned` flag + reason, and optional metadata.
- `aet-work run` calls `aet-state derive` on startup before spawning any task.
- A manual `aet-work reconcile --task-id <id> --to-stage <stage>` command resolves unresolvable conflicts, updating both queue and footer atomically.

### Story 3 — Clean, Deterministic Worktrees

**As a developer running AET over days or weeks,** I want worktrees created and destroyed predictably, so that my disk and git state stay clean.

**Acceptance Criteria:**

- Worktrees live under `{repo_root}/.worktrees/<task-id>/`.
- A worktree is created when a task transitions from `unblocked` to `in-progress`.
- A successful task's worktree is removed immediately when it reaches `done` or `merged`.
- A failed task's worktree is preserved until explicitly cleaned via `aet-work cleanup --task-id <id>` or the task is retried/reset.
- `aet-work cleanup` supports `--all-done` and `--failed` modes.
- On startup, the orchestrator detects orphaned worktrees (no matching in-progress task) and reports them for cleanup.

### Story 4 — Agent-Agnostic Session Isolation

**As a developer who switches between Kimi Code and Claude Code,** I want the orchestrator to spawn the correct agent CLI with the correct flags, so that I can use whichever agent I prefer without changing project files.

**Acceptance Criteria:**

- A `CLIAdapter` abstraction maps agent CLI names to invocation flags (`--prompt`, `--work-dir`, `--afk`/headless, etc.).
- Adapter selection precedence:
  1. `--cli-bin` argument
  2. `AET_CLI_BIN` environment variable
  3. First available binary on `$PATH` from an allowlist (`kimi`, `claude`)
- Adding a new agent CLI requires only a new adapter class; no project files change.
- Each pipeline stage runs in a fresh agent session with a focused prompt referencing only the relevant skill and plan file.
- `AET_EXECUTION_MODE=unattended` is passed to child sessions.

### Story 5 — Conflict-Aware Parallel Execution

**As a developer with a queue of independent tasks,** I want them to run in parallel to save wall-clock time, but I want overlapping tasks serialized so that I do not face complex merge conflicts.

**Acceptance Criteria:**

- `aet-work run` processes independent tasks in parallel up to a configurable concurrency cap (default 4, max 8, override via `AET_WORK_JOBS`).
- Before spawning a task, the scheduler computes its "file surface" from the plan's `files to modify` list.
- Tasks with overlapping file surfaces are not spawned concurrently; they run sequentially in dependency/DAG order.
- Only the main orchestrator loop reads/writes the queue file; child agent processes do not mutate it.
- When a task fails, running tasks are allowed to finish (drain), new tasks are not started, and the orchestrator exits non-zero.
- Resume semantics: re-running `aet-work run` re-derives state, skips `done`/`in-progress` tasks, and spawns newly unblocked tasks.

### Story 6 — Graceful Failure Recovery

**As a developer whose parallel run hit a failure,** I want the orchestrator to stop cleanly, preserve the failed state, and let me resume or reset without corrupting the queue.

**Acceptance Criteria:**

- On task failure, the orchestrator marks the task `failed` with `failed_stage` and preserves its worktree and branch.
- The orchestrator drains currently running tasks before exiting.
- `SIGINT`/`SIGTERM` handlers stop new spawns, terminate children gracefully (with timeout + force-kill), and mark running tasks `failed` with `failed_stage: interrupted`.
- `aet-work reset --task-id <id>` returns a failed task to `unblocked` (or its last good stage) so it can be retried.

### Story 7 — Planner Declares Isolation Level

**As a developer reviewing a plan,** I want `aet-plan` to declare the required session-isolation level for the task, so that the orchestrator applies the right amount of context separation without me remembering to pass a flag.

**Acceptance Criteria:**

- `aet-plan` writes `isolation_level: minimal | standard | full` into each plan's metadata (frontmatter or structured footer).
- The planner chooses the level based on task signals, with work class as one input among several:
  - Touches auth, sessions, permissions, payments, data models, migrations, infrastructure, or dependency upgrades → `full`
  - Crosses a trust boundary or has a history of review-bias incidents → `standard`
  - Everything else → `minimal`
- Work class (trivial/normal/critical) and isolation level remain separate plan fields. Work class determines pipeline depth; isolation level determines session separation within that pipeline.
- During plan approval, the user may override the planner's chosen isolation level. The override is recorded in the plan metadata and in telemetry.
- The orchestrator reads `isolation_level` from the plan and spawns sessions accordingly. It does not second-guess the planner; there is no runtime override.
- Telemetry records planned vs. actual isolation level so we can audit planner decisions.

### Story 8 — Execution Metadata Capture

**As a developer optimizing my agentic workflow,** I want the orchestrator to record the time, tokens, cost, and outcome of every task and stage, so that I can later evaluate whether higher isolation levels or parallel execution actually pay for themselves.

**Acceptance Criteria:**

- The orchestrator appends a structured record to `.agents/execution.log.jsonl` for every stage spawn.
- Each record includes: `task_id`, `plan_file`, `stage`, `agent_cli`, `isolation_level`, `start_time`, `end_time`, `duration_seconds`, `exit_code`, `result`, `files_modified` (list), `commits_created` (count), `worktree_size_bytes`, and `token_count`/`cost_estimate` when available from the agent CLI or environment.
- Per-run summary records include: `run_id`, `wall_clock_seconds`, `tasks_spawned`, `tasks_succeeded`, `tasks_failed`, `parallel_conflicts_detected`.
- The log is append-only, local, and human-readable line-by-line.
- A command `aet-work report --since <date>` reads the log and prints a simple text summary (no UI).
- Telemetry capture is always on; there is no opt-out because the data is local and required for future default decisions.

## Technical Notes

### Architecture

```
~/.claude/skills/aet-work/
├── SKILL.md
├── bin/
│   └── orchestrator              ← unified conductor (Python)
├── lib/
│   ├── __init__.py
│   ├── cli_adapter.py            ← KimiAdapter, ClaudeAdapter
│   ├── pipeline.py               ← stage state machine
│   ├── queue.py                  ← queue JSON read/write + derivation
│   ├── worktree.py               ← git worktree management
│   ├── verifier.py               ← commit + stage advancement checks
│   ├── scheduler.py              ← conflict-aware parallel scheduler
│   └── telemetry.py              ← execution metadata capture
└── references/
    └── orchestrator-spec.md      ← behavior contract for contributors

scripts/
└── aet-state.py                  ← standalone state derivation + atomic transitions
```

### Stage State Machine

| Stage           | Skills                     | Next Stage    | Session Group | Notes                                          |
| --------------- | -------------------------- | ------------- | ------------- | ---------------------------------------------- |
| `plan-approved` | `aet-tdd`, `aet-implement` | `implemented` | 1             | Tightly coupled; shared context is intentional |
| `implemented`   | `aet-qa`                   | `qa-complete` | 1             | Verification of implementation                 |
| `qa-complete`   | `aet-review`               | `reviewed`    | 2             | Must be isolated from implementation context   |
| `reviewed`      | `aet-cso`                  | `secure`      | 3             | Conditional on security-sensitive diff         |
| `secure`        | `aet-sync-docs`            | `synced`      | 3             | Conditional on divergences found               |
| `synced`        | —                          | `done`        | —             | Pipeline complete                              |

Isolation levels (plan-level parameter):

| Level      | Sessions per Plan | Use Case                                             | Planner Trigger                                                                                 |
| ---------- | ----------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `minimal`  | 1                 | All stages share one session                         | Default when no stronger signal exists                                                          |
| `standard` | 3                 | Review isolated from implement/QA; CSO+sync isolated | Security-sensitive diff, cross-boundary change, prior review-bias incident in similar task      |
| `full`     | 5-6               | One session per stage                                | Auth, payments, data models, infrastructure, dependency upgrades, or explicit audit requirement |

`aet-plan` sets `isolation_level` in the plan metadata based on the task's risk profile. The orchestrator reads and enforces it; it does not second-guess the planner.

**Rationale:** The planner has the richest context for judging whether a task needs reviewer independence or security isolation. Making it a plan parameter also lets telemetry answer: "When `aet-plan` chose `standard`, did it actually prevent defects compared to `minimal`?" That feedback loop lets us improve the planner's heuristics over time.

### Conflict-Aware Scheduling

Before spawning a task:

1. Gather `files to modify` from each unblocked, ready plan.
2. Build an overlap graph: two tasks conflict if their file sets intersect.
3. From ready tasks, pick a conflict-free set up to the concurrency cap.
4. Serialize conflicting tasks behind the earlier one in queue/DAG order.

This prevents the "absurd, very complex conflicts" that come from running overlapping changes in parallel worktrees.

### State Derivation

`aet-state derive` recomputes status for every task:

```python
def derive_status(task):
    if task.abandoned:
        return "abandoned"
    if is_ancestor(task.branch, "main"):
        return "done"
    footer_stage = read_plan_footer(task.plan_file)
    branch_exists = git_branch_exists(task.branch)
    worktree_exists = path_exists(task.worktree_dir)
    # ... combine signals into canonical status
```

If queue JSON and derived status disagree, the orchestrator logs the discrepancy and uses the derived status, optionally surfacing a warning.

### Nested Invocation Safety

- The orchestrator never calls itself recursively.
- Child sessions receive `AET_ORCHESTRATOR_PID=<pid>`.
- If a child session attempts to invoke `aet-work run`, the skill detects `AET_ORCHESTRATOR_PID` and refuses with: `⛔ Nested orchestrator invocation is not allowed. Finish the current stage and let the top-level orchestrator continue.`

### Prompt Construction

Each stage spawn uses a focused prompt:

```
Run {skill} on {repo_root}/{plan_file}
Current stage: {current_stage}. Target stage: {next_stage}.
Execute only this stage. Do not proceed to subsequent stages.
Commit your work and update the plan footer to *Stage: {next_stage}* before exiting.
```

### Execution Metadata and Telemetry

The orchestrator records every execution event to `.agents/execution.log.jsonl`. This is not a reporting feature; it is the raw observability data needed to make evidence-based decisions about isolation defaults, parallelism effectiveness, and pipeline health.

#### Per-Stage Record Schema

```json
{
  "type": "stage",
  "run_id": "uuid",
  "task_id": "FEAT-001",
  "plan_file": "docs/plans/FEAT-001-plan.md",
  "stage": "implemented",
  "agent_cli": "kimi",
  "isolation_level": "minimal",
  "start_time": "2026-06-15T14:51:53Z",
  "end_time": "2026-06-15T14:55:12Z",
  "duration_seconds": 199,
  "exit_code": 0,
  "result": "success",
  "files_modified": ["src/auth.ts"],
  "commits_created": 1,
  "worktree_size_bytes": 4194304,
  "token_count": null,
  "cost_estimate": null
}
```

#### Per-Run Summary Record Schema

```json
{
  "type": "run_summary",
  "run_id": "uuid",
  "start_time": "2026-06-15T14:51:53Z",
  "end_time": "2026-06-15T15:20:07Z",
  "wall_clock_seconds": 1694,
  "tasks_spawned": 6,
  "tasks_succeeded": 5,
  "tasks_failed": 1,
  "parallel_conflicts_detected": 2,
  "concurrency_cap": 4
}
```

#### Token and Cost Capture

Agent CLIs do not consistently expose token counts. The orchestrator captures them when available:

- Via `AET_TOKEN_COUNT` / `AET_COST_USD` environment variables injected by the agent CLI wrapper.
- By parsing known CLI output trailers if the CLI prints them.
- Falls back to `null` if unavailable; the log remains useful for time and outcome analysis.

This data feeds future decisions such as whether `standard` isolation prevents enough defects to justify its cost, or whether parallel execution actually reduces wall-clock time for typical queues.

## Roadmap

### Phase 0 — State Mechanization and Telemetry Foundation

1. Implement standalone `scripts/aet-state.py` with:
   - `derive` command to recompute task status from git + filesystem.
   - `transition` command for atomic queue + footer updates.
   - `reconcile` command for manual conflict resolution.
2. Refactor queue JSON to store only declarative data (DAG, `abandoned`, metadata).
3. Add `.agents/execution.log.jsonl` schema and `telemetry.py` module.
4. Add `aet-work report` command for basic text summaries.
5. Update `aet-work` to call `scripts/aet-state.py` instead of maintaining queue status itself.

### Phase 1 — Unified Orchestrator

1. Create `aet-work/bin/orchestrator` in Python (standard library + `git`).
2. Implement CLI adapter layer for Kimi Code and Claude Code.
3. Encode stage state machine in `lib/pipeline.py`.
4. Implement worktree lifecycle management in `lib/worktree.py`.
5. Implement stage advancement verification (footer + clean git + commits).
6. Wire `aet-work run` and `aet-work run --plan-file <path>` to the orchestrator.
7. Remove `aet-pipeline-implement` skill and per-project generated orchestrator scripts.
8. Update `docs/PIPELINE.md` and `docs/use-cases.md`.

### Phase 1b — Planner Isolation Guidance

1. Update `aet-plan` to emit `isolation_level` in plan metadata based on task risk signals.
2. Add isolation-level guidance to `aet-plan/references/` or checklist.
3. Update `aet-validate-scope` to ensure `isolation_level` is present and valid.
4. Update plan templates to include the `isolation_level` field.

### Phase 2 — Parallel Execution

1. Implement conflict-aware scheduler in `lib/scheduler.py`.
2. Add parallel task spawning with configurable concurrency cap.
3. Implement graceful drain-on-failure.
4. Harden signal handling and resume semantics.
5. Add `aet-work reset` for retrying failed tasks.

### Phase 3 — Measurement and Hardening (Follow-up Work)

1. Add orchestrator-level structured logging (`aet-work run --log` or `.agents/orchestrator.log.jsonl`).
2. Introduce `aet-eval` / `aet-qa --design-eval` to measure pipeline quality.
3. Consider disk-space management and per-task size caps.
4. Add reference docs for skill authors (prompt/context engineering) only if needed.

## File Changes

| File                                            | Change                                                                                |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- |
| `scripts/aet-state.py`                          | Create. Standalone state derivation, atomic transitions, and reconciliation.          |
| `aet-work/bin/orchestrator`                     | Create. New unified Python orchestrator.                                              |
| `aet-work/lib/*.py`                             | Create. Adapter, pipeline, queue, worktree, verifier, scheduler, telemetry modules.   |
| `aet-work/references/orchestrator-spec.md`      | Create. Contributor behavior contract.                                                |
| `aet-work/references/orchestrator-template.sh`  | Delete. Replaced by Python orchestrator.                                              |
| `aet-work/SKILL.md`                             | Update. Document `run`, `run --plan-file`, `reset`, `cleanup`, `reconcile`, `report`. |
| `aet-pipeline-implement/`                       | Delete. Redirect trigger phrases to `aet-work run --plan-file`.                       |
| `scripts/.aet-work-orchestrator.sh` (this repo) | Delete. Use central binary.                                                           |
| `docs/PIPELINE.md`                              | Update. Orchestrator is sole conductor.                                               |
| `docs/use-cases.md`                             | Update. Replace `aet-pipeline-implement` references.                                  |
| `aet-plan/SKILL.md`                             | Update. Add isolation-level selection to planning procedure.                          |
| `aet-plan/references/`                          | Update. Add isolation-level guidance for planners.                                    |
| `.agents/templates/plan-template.md`            | Update. Include `isolation_level` field.                                              |
| `aet-validate-scope/SKILL.md`                   | Update. Validate `isolation_level` presence and value.                                |
| `aet-setup/checklist.md` or template            | Update. Remove generated orchestrator script from `.gitignore`/templates.             |

## Risks

| Risk                                                                 | Likelihood | Impact | Mitigation                                                                                                       |
| -------------------------------------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| Agent CLI flag changes break adapter                                 | Medium     | Medium | Thin adapter layer; update one file.                                                                             |
| Derived-status performance degrades on large queues                  | Low        | Low    | Derivation is local git/fs operations; cache results within one run.                                             |
| Conflict-aware scheduler over-serializes and loses parallelism gains | Medium     | Medium | Log scheduling decisions; tune based on observed queue patterns.                                                 |
| Failed parallel run leaves worktree/branch mess                      | Medium     | High   | Preserve-on-failure + explicit `reset`/`cleanup` commands; drain running tasks.                                  |
| User expects cross-agent parallel execution                          | Low        | High   | Document that agent-agnosticism means session-by-session choice, not simultaneous multi-agent runs.              |
| Removal of `aet-pipeline-implement` breaks muscle memory             | Medium     | Low    | Alias `aet-work run --plan-file` and update docs/use-cases.                                                      |
| Telemetry log grows unbounded                                        | Medium     | Low    | Implement rotation/archiving in Phase 0 or Phase 1.                                                              |
| `minimal` isolation default misses review-bias bugs                  | Medium     | Medium | Capture stage-level outcomes in telemetry; revisit default once data exists.                                     |
| Token/cost data is incomplete                                        | High       | Low    | Design schema to allow nulls; report on available metrics (time, outcome) rather than require perfect cost data. |

## Open Questions

1. Should `--plan-file` be exposed as a separate subcommand (`aet-work run-one`) in addition to the flag?
2. How should the scheduler treat tasks whose file surface is not fully specified in the plan?
3. What is the retention policy for `.agents/execution.log.jsonl` — append forever, rotate monthly, or archive after N runs?
4. Should `aet-work report` live in `aet-work` or in `aet-state`? It reads the telemetry log but reports on workflow state.
5. If an agent CLI does not expose token counts, should the orchestrator attempt to estimate cost from duration + agent model, or leave the field null?

---

_Stage: scope-validated_
_Next step: run `aet-work run --plan-file docs/plans/aet-state-telemetry-foundation-plan.md`_
