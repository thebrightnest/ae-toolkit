# PRD: Unified Orchestrator with Session-Isolated Pipeline

## Overview

Replace the per-project generated orchestrator script and the `aet-pipeline-implement` skill with a single, centralized Python orchestrator that lives inside the `aet-work` skill. The orchestrator becomes the sole conductor of the implementation pipeline, invoking each stage (aet-tdd, aet-implement, aet-qa, aet-review, aet-cso, aet-sync-docs) as a fresh agent session. This eliminates cross-project drift, prevents context pollution between skills, and provides one source of truth for how the toolkit pipeline executes.

## Goals

1. **Single source of truth:** Exactly one orchestrator implementation exists, versioned inside the `aet-work` skill. No project generates or hosts a local copy.
2. **Session isolation:** Each pipeline stage runs in a fresh agent session. Context from aet-implement cannot bias aet-review; aet-cso runs with a clean security-audit context.
3. **Multi-agent CLI support:** The orchestrator detects and adapts to Kimi Code, Claude Code, and future agent CLIs at runtime via a small adapter layer.
4. **Nested invocation safety:** The orchestrator can be invoked from within an agent session without creating recursive loops, context leaks, or trust-boundary violations.
5. **No generated project artifacts:** Projects no longer contain `scripts/.aet-work-orchestrator.sh` or equivalent. The only project-side file is the queue (`*.json`) and the plan files.
6. **Two native invocation modes:**
   - `--queue-file`: AFK/batch mode that processes multiple tasks in parallel worktrees.
   - `--plan-file`: Single-plan mode that replaces the manual `aet-pipeline-implement` use case.
7. **Deprecate** `aet-pipeline-implement`**:** Remove the skill and redirect its trigger phrases to the centralized orchestrator.
8. **Enforce trust boundaries:** The orchestrator explicitly forbids spawning a different agent CLI than the one it was invoked with, mutating global agent configs, or executing arbitrary shell from plan files.

## Non-Goals

- **Migration path for existing generated orchestrators:** Projects with legacy `scripts/.aet-work-orchestrator.sh` will delete it and rely on the centralized binary.
- **Per-project customization hooks:** The orchestrator does not support project-specific bash logic. Legitimate differences (concurrency, excluded paths) are expressed through configuration, not script edits.
- **Real-time UI or progress dashboards:** Output remains text logs. A richer UI is out of scope.
- **Windows support:** Initial implementation targets macOS/Linux. Windows adapters can be added later in the CLI layer.

## User Stories

- **As a developer working on one plan,** I want to say "pipeline implement this plan" so that the orchestrator runs all stages in isolated sessions and leaves the branch ready for `aet-ship`.
- **As a tech lead,** I want to say "aet-work run" so that multiple plans execute in parallel worktrees with the same quality gates I would apply manually.
- **As a maintainer of the toolkit,** I want to fix a pipeline bug in one file so that every project using the toolkit receives the fix immediately after updating skills.
- **As a security reviewer,** I want aet-cso to run in a session that has not been polluted by implementation context so that audit findings are unbiased.

## Acceptance Criteria

- [ ] `aet-work/bin/orchestrator` exists as a self-contained Python script (≥3.) with no external dependencies beyond the Python standard library and `git`.

- [ ] The orchestrator supports `--queue-file <path>` and `--plan-file <path>` invocation modes.

- [ ] A `CLIAdapter` abstraction supports Kimi Code and Claude Code with detected/overrideable flags for prompt, working directory, and headless mode.

- [ ] The stage state machine (`plan-approved` → `implemented` → `qa-complete` → `reviewed` → `secure` → `synced`) is encoded in exactly one data structure inside the orchestrator.

- [ ] Each stage transition spawns a fresh OS process running the configured agent CLI with a focused prompt referencing only the relevant skill and plan file.

- [ ] The orchestrator verifies stage advancement by reading the plan.md footer after each child session exits. If the stage did not advance, the task is marked failed.

- [ ] The orchestrator verifies each branch has at least one commit ahead of `main` before marking a task done (commit-verifier gate).

- [ ] `AET_EXECUTION_MODE=unattended` is passed to child sessions, and the orchestrator rejects any attempt by a child to re-invoke the orchestrator unless explicitly signaled via a queue state change.

- [ ] The orchestrator refuses to spawn a CLI binary that is not in its allowlist or differs from the parent CLI that invoked it.

- [ ] Projects no longer generate `scripts/.aet-work-orchestrator.sh`; the file is removed from `.gitignore` templates and existing projects delete it.

- [ ] `aet-pipeline-implement/SKILL.md` and its directory are removed from the toolkit.

- [ ] `docs/PIPELINE.md` is updated to show the orchestrator as the sole conductor.

- [ ] Unit tests exist for the stage state machine and CLI adapter selection.

## Technical Notes

### Architecture

```
~/.claude/skills/aet-work/
├── SKILL.md
├── bin/
│   └── orchestrator                    ← unified conductor (Python)
├── lib/
│   ├── __init__.py
│   ├── cli_adapter.py                  ← KimiAdapter, ClaudeAdapter
│   ├── pipeline.py                     ← stage state machine
│   ├── queue.py                        ← queue JSON read/write
│   ├── worktree.py                     ← git worktree management
│   └── verifier.py                     ← commit + stage advancement checks
└── references/
    └── orchestrator-spec.md            ← behavior contract for contributors
```

### CLI Adapter Pattern

The orchestrator determines the active agent CLI using the following precedence:

1. `--cli-bin` argument (explicit override).
2. `AET_CLI_BIN` environment variable.
3. First available binary on `$PATH` from the allowlist (`kimi`, `claude`).

**Deprecated:** Parent process inspection (`ps` chain) is fragile and unreliable across shells, IDEs, and tmux sessions. It is removed from the precedence chain. The parent agent session should pass `--cli-bin` explicitly.

Each adapter maps to a small dataclass:

```python
@dataclass
class CLIAdapter:
    name: str
    bin: str
    prompt_flag: str          # e.g., "-p"
    workdir_flag: str         # e.g., "--work-dir" or "--cwd"
    headless_flag: str        # e.g., "--afk" or "--dangerously-skip-permissions"
    max_steps_flag: str       # optional CLI-specific override
```

Adding a new agent CLI means adding one adapter class; no project files change.

### Stage State Machine and Session Grouping

The pipeline has **six stages**, but they are grouped into **session bundles** based on isolation requirements. The orchestrator supports three isolation levels via `--isolation`:

| Level                | Sessions per plan | Grouping                                        | Cost vs current | Use case                            |
| -------------------- | ----------------- | ----------------------------------------------- | --------------- | ----------------------------------- |
| `minimal`            | 1                 | All stages in one session                       | 1×              | Tight budget, trusted codebase      |
| `standard` (default) | 3                 | (TDD+Implement+QA) → (Review) → (CSO+Sync-docs) | 3×              | Balanced quality/cost               |
| `full`               | 5-6               | One session per stage                           | 5-6×            | Security-critical, high-stakes code |

```python
STAGES = [
    Stage(name="plan-approved", skills=["aet-tdd", "aet-implement"], next_stage="implemented", session_group=1),
    Stage(name="implemented",   skills=["aet-qa"],                   next_stage="qa-complete",   session_group=1),
    Stage(name="qa-complete",   skills=["aet-review"],               next_stage="reviewed",     session_group=2),
    Stage(name="reviewed",      skills=["aet-cso"],                  next_stage="secure",       session_group=3, conditional=security_sensitive),
    Stage(name="secure",        skills=["aet-sync-docs"],            next_stage="synced",       session_group=3, conditional=divergences_found),
    Stage(name="synced",        skills=[],                           next_stage="done",         session_group=None),
]
```

**Why this grouping:**

- **Group 1** (TDD → Implement → QA): These are tightly coupled. TDD writes tests; implement makes them pass; QA verifies. Context sharing here is a feature, not a bug.
- **Group 2** (Review): Must be isolated. The reviewer must not know implementation context to avoid bias.
- **Group 3** (CSO → Sync-docs): Security audit and documentation sync are post-review activities that benefit from clean context.

`security_sensitive(plan_file, worktree_dir)` inspects the diff for auth, data model, API, or dependency changes. `divergences_found(...)` checks for the existence of review/cso reports in `/tmp/aet-reports/{task_id}/`.

**Cost control defaults:** The orchestrator defaults to `standard` isolation. Users can override per invocation: `aet-work run --isolation=minimal` for quick tasks or `--isolation=full` for security reviews.

### Nested Invocation Safety

When the orchestrator is invoked from an agent session, it must avoid recursion and context leakage:

- The orchestrator sets `AET_EXECUTION_MODE=unattended` for child sessions.
- Child sessions receive `AET_ORCHESTRATOR_PID=<pid>` so skills can detect they are inside an orchestrator-run context.
- The orchestrator **never** calls itself recursively. If a child plan advances to a new stage, the orchestrator handles the next spawn in the top-level loop, not by nesting.
- If a child session attempts to invoke `aet-work run`, the skill detects `AET_ORCHESTRATOR_PID` and refuses, printing: `⛔ Nested orchestrator invocation is not allowed. Finish the current stage and let the top-level orchestrator continue.`

### Prompt Construction

Each stage spawn uses a focused prompt that isolates the skill context:

```
Run {skill} on {repo_root}/{plan_file}
Current stage: {current_stage}. Target stage: {next_stage}.
Execute only this stage. Do not proceed to subsequent stages.
Commit your work and update the plan footer to *Stage: {next_stage}* before exiting.
```

For multi-skill stages (e.g., aet-tdd + aet-implement), the prompt lists both skills in execution order.

### Invocation Modes

**Batch mode (**`--queue-file`**):**

- Reads `.agents/work-queue.json`.
- Spawns up to `AET_WORK_JOBS` (default 4, max 8) tasks in parallel.
- Each task advances through its own stage machine independently.
- On failure, drains running tasks and exits non-zero.

**Single-plan mode (**`--plan-file`**):**

- Creates no queue.
- Advances one plan through all stages sequentially.
- Exits when the plan reaches `synced` or a stage fails.

### Trust Boundaries

The orchestrator enforces the following hard rules:

- **CLI allowlist only:** Spawns only the CLI identified by the adapter. Any other binary is rejected.
- **No global config mutation:** The orchestrator does not write to `~/.kimi-code/config.toml`, `~/.claude/`, or any file outside `repo_root`.
- **No shell injection:** Plan file paths are passed as arguments, not interpolated into shell commands.
- **Worktree containment:** All git operations happen inside worktrees under `{repo_root}/.worktrees/`. The orchestrator verifies no process escapes this directory.

### Stage Advancement Verification

After a child session exits, the orchestrator must verify the stage actually advanced before proceeding. The verification strategy is:

1. **Read plan.md footer** — extract the `*Stage:*` value.
2. **Check git status** — verify the worktree has no uncommitted changes (all work is committed).
3. **Check branch commits** — verify `git rev-list --count main..HEAD > 0`.

If the footer stage matches the expected next stage, git is clean, and commits exist → advance.

If any check fails, the orchestrator performs **one retry** after a 2-second delay (filesystem sync latency), then re-reads. If still failing:

- Mark the task as `failed` with `failed_stage: {expected_stage}`
- Preserve the worktree for inspection
- Log the specific failure reason (footer mismatch, uncommitted changes, or zero commits)

### Signal Handling and Graceful Shutdown

The orchestrator registers handlers for `SIGINT` and `SIGTERM`:

1. On signal receipt, set a shutdown flag and stop spawning new tasks.
2. Send `SIGTERM` to all running child processes.
3. Wait up to 30 seconds for children to exit gracefully.
4. Force-kill (`SIGKILL`) any remaining children after the timeout.
5. Update the queue: running tasks are marked `failed` with `failed_stage: interrupted`.
6. Print a summary of what was preserved and how to resume.
7. Exit with code `130` (SIGINT) or `143` (SIGTERM).

**Resume after interrupt:** Re-running `aet-work run` reads the queue state and resumes from the last recorded stage. No work is lost.

### Manual Fix and Resume Reconciliation

When a stage fails and the user manually fixes the code, the queue status (`failed`) and plan.md footer (e.g., `reviewed`) may disagree. The orchestrator reconciles on startup:

1. Read the queue status.
2. Read the plan.md footer stage.
3. If the footer stage is **ahead** of the queue status, trust the footer and update the queue to match.
4. If the footer stage is **behind** the queue status, trust the queue (the stage may have regressed).
5. If they conflict in an unresolvable way, print a warning and require `aet-work reconcile --task-id <id>` to force a specific stage.

**Manual override command:**

```bash
aet-work reconcile --task-id FEAT-001 --to-stage reviewed
```

This updates both the queue and the plan.md footer atomically.

### Disk Space Management

The orchestrator monitors disk usage throughout execution:

1. **Pre-flight check:** Before creating a worktree, estimate available space (worktree size ≈ repo size). If disk would drop below 5GB free, refuse to spawn and print a warning.
2. **Aggressive cleanup:** After a task reaches `done` or `merged`, the worktree is removed immediately (not left for `aet-work cleanup`). Failed tasks preserve their worktrees for inspection.
3. **Per-task size cap:** If a worktree grows beyond 2× the original repo size (indicating runaway temp file generation), the task is killed and marked `failed`.
4. **Configurable:** `AET_WORK_MAX_DISC_USAGE_GB` sets a per-project cap. Default is unlimited (only the 5GB free-space floor is enforced).

### File Changes

| File                                            | Change                                                                                       |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `aet-work/bin/orchestrator`                     | **Create.** New unified Python orchestrator.                                                 |
| `aet-work/lib/*.py`                             | **Create.** Adapter, pipeline, queue, worktree, verifier modules.                            |
| `aet-work/references/orchestrator-template.sh`  | **Delete.** Replaced by `bin/orchestrator`.                                                  |
| `aet-work/references/orchestrator-spec.md`      | **Create.** Behavior contract for future contributors.                                       |
| `aet-work/SKILL.md`                             | **Update.** `run` command invokes `bin/orchestrator`; add `run-one` alias for `--plan-file`. |
| `aet-pipeline-implement/`                       | **Delete.** Skill removed entirely.                                                          |
| `docs/PIPELINE.md`                              | **Update.** Orchestrator is the conductor.                                                   |
| `docs/use-cases.md`                             | **Update.** Reference `aet-work run --plan-file` instead of `aet-pipeline-implement`.        |
| `aet-setup/checklist.md` or template            | **Update.** Remove `scripts/.aet-work-orchestrator.sh` from `.gitignore` recommendations.    |
| `scripts/.aet-work-orchestrator.sh` (this repo) | **Delete.** Use central binary.                                                              |

### Test Strategy

- **Unit tests** for `pipeline.py` stage transitions, including conditional skips.
- **Unit tests** for `cli_adapter.py` selection and flag generation.
- **Unit tests** for `verifier.py` commit and stage advancement checks.
- **Integration test** (optional, manual): run the orchestrator on a toy plan in a temporary git repo and verify it advances through stages.

## Open Questions

1. Should the orchestrator persist a structured log (e.g., `.agents/orchestrator.log.jsonl`) for debugging multi-session failures, or is stderr/stdout sufficient?
2. Should `--plan-file` be exposed as a separate command (`aet-work run-one`) for easier UX, or is the flag style (`aet-work run --plan-file`) acceptable?
3. Do we need an explicit `AET_MAX_STEPS_PER_STAGE` config to avoid the 100-step limit, or should each skill internally handle step budgets?
4. Should the orchestrator support resuming a single plan from an arbitrary stage, or only from the stage recorded in the plan.md footer?
