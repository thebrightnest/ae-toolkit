# AET Work Operational Commands

Reference for invoking the local `aet` CLI and the AET skill pipeline in this repo. Use this whenever the user asks to run the queue, ship work, or interact with the AET state machine.

## When to Use

- The user says `aet run`, `run the queue`, `run the next task(s)`, or similar.
- The user says `aet ship`, `ship this`, `merge PR and verify`, or similar.
- The user mentions an AET skill (`aet-evolve`, `aet-plan`, etc.) and you need to know whether it maps to an `aet` CLI subcommand.

## `aet run` — Batch Queue Execution

`aet run` starts the orchestrator in a **detached process**. It assigns a run ID, redirects output to `.agents/runs/<run-id>/output.log`, prints the ID and log path, and returns immediately.

### Procedure

1. Run it as a normal foreground command:

   ```bash
   aet run
   ```

2. The command prints the run ID, log path, and follow command, then exits as soon as the orchestrator process is spawned.
3. Wait for the run to finish and print a bounded completion report with:

   ```bash
   aet run --follow <run-id>
   ```

4. Check on active runs with:

   ```bash
   aet status
   ```

### Flags

- `--follow <run-id>` — wait for an already-spawned run to reach a terminal state and print a bounded completion report. It does **not** tail or stream run output.
- `--on-failure`, `--task-timeout`, `--cli-bin`, `--base` — forwarded to the orchestrator unchanged.

### Anti-Patterns

- ❌ Spawning a second `aet run` because the first one is still running; use `aet status` or `aet run --follow <id>` instead.
- ❌ Shell-backgrounding `aet run` with `&`; the command already returns immediately after spawning.

## `aet run-one` — Single Task Execution

`aet run-one <plan>` runs a single plan through the full pipeline. Like `aet run`, it spawns the orchestrator in a detached process, but `run-one` **blocks** until the run reaches a terminal state, prints a bounded completion report, and exits with the run's exit code.

## `aet status` — Queue and Run State

Shows the work queue plus any active detached runs (run ID, PID, and start time).

## `aet ship` — From `awaiting_merge` to Closed

`aet ship` is the unified shipping workflow. It runs the pre-merge gate and opens a PR in one command. After the PR is merged, `aet ship close` records closure.

### Procedure

1. When a task is `awaiting_merge`, run the unified ship command:

   ```bash
   aet ship docs/plans/pkg-01-decision-records.md
   ```

   A bare task id also works — it resolves to the conventional `docs/plans/<task-id>.md` path:

   ```bash
   aet ship pkg-01-decision-records
   ```

   This runs `aet ship gate` followed by `aet ship open`. If the gate fails, resolve the issue before re-running.

2. Wait for the user to confirm the PR is merged (e.g., "merge PR and verify").
3. Run the closure command. The preferred form is the plan path; `aet-ship` derives the task id from the plan frontmatter and resolves the merge commit from the task's branch on `origin/main`:

   ```bash
   aet ship close docs/plans/<task-id>.md
   ```

   Example:

   ```bash
   aet ship close docs/plans/pkg-01-decision-records.md
   ```

   You may also pass the task id (the plan path is read from the queue task) or supply both identifiers explicitly:

   ```bash
   aet ship close pkg-01-decision-records
   aet ship close pkg-01-decision-records docs/plans/pkg-01-decision-records.md
   ```

4. If `aet ship close` cannot resolve the merge commit (for example, the feature branch was already deleted), use the `--branch` or `--merge-commit` override:

   ```bash
   aet ship close --branch <branch-name> docs/plans/<task-id>.md
   aet ship close --merge-commit <sha> docs/plans/<task-id>.md
   ```

### Anti-Patterns

- ❌ Asking the user to clarify whether they want to ship when they explicitly said `aet ship`.
- ❌ Trying to merge the PR yourself; the merge is the human's decision.
- ❌ Forgetting the closure step after the PR is merged.

## Skill vs. CLI Namespace

<!-- aet-lint: off -->
The table below documents namespace mapping; strings in backticks are labels, not shell commands.

| Skill / Concept | CLI Entry Point | Notes |
| --------------- | --------------- | ----- |
| `aet-evolve` | **No CLI subcommand.** Activate as a skill. Use `aet retro` (telemetry retro) or run the `retro` + `system-evolve` procedure manually. | `aet evolve` fails. |
| `aet-plan` | `aet plan validate` | Validates plans. |
| `aet-work` | `aet run`, `aet run-one`, `aet status`, `aet next`, `aet queue sync`, `aet state`, etc. | The `aet-work` skill owns the queue/orchestrator. |
| `aet-ship` | `aet ship` (gate + open) and `aet ship close` (post-merge closure) | Unified workflow; skill is judgment residue only. |
| `aet-qa` | No direct CLI; invoked inside the pipeline. | |
| `aet-review` | No direct CLI; invoked inside the pipeline or via skill activation. | |

### Anti-Patterns

- ❌ Typing `aet evolve` as if it were a CLI subcommand.
- ❌ Treating skill activations (`aet-evolve`, `aet-qa`) as shell commands.
<!-- aet-lint: on -->
