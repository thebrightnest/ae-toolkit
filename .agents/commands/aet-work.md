# AET Work Operational Commands

Reference for invoking the local `aet` CLI and the AET skill pipeline in this repo. Use this whenever the user asks to run the queue, ship work, or interact with the AET state machine.

## When to Use

- The user says `aet run`, `run the queue`, `run the next task(s)`, or similar.
- The user says `aet ship`, `ship this`, `merge PR and verify`, or similar.
- The user mentions an AET skill (`aet-evolve`, `aet-plan`, etc.) and you need to know whether it maps to an `aet` CLI subcommand.

## `aet run` — Batch Queue Execution

`aet run` starts the orchestrator in a **detached process** by default. It assigns a run ID, redirects output to `.agents/runs/<run-id>/output.log`, prints the ID, and returns immediately.

### Procedure

1. Run it as a normal foreground command:

   ```bash
   aet run
   ```

2. The command prints the run ID and exits as soon as the orchestrator process is spawned.
3. Follow the run's output with:

   ```bash
   aet run --follow <run-id>
   ```

4. Check on active runs with:

   ```bash
   aet status
   ```

### Flags

- `--foreground` — block and inherit the orchestrator's stdout/stderr exactly like the pre-daemonization behavior. Use only for debugging.
- `--follow <run-id>` — attach to and tail a running or already-completed run's log.
- `--max-jobs`, `--isolation`, `--on-failure`, `--task-timeout`, `--stall-timeout`, `--cli-bin` — forwarded to the orchestrator unchanged.

### Anti-Patterns

- ❌ Running `aet run --foreground` for long batches unless you are actively debugging.
- ❌ Spawning a second `aet run` because the first one is still running; use `aet status` or `aet run --follow <id>` instead.

## `aet run-one` — Single Task Execution

Same detached behavior as `aet run`: runs in the background by default, prints a run ID, and can be followed with `aet run-one --follow <run-id>`. Use `--foreground` only for debugging.

## `aet status` — Queue and Run State

Shows the work queue plus any active detached runs (run ID, PID, and start time).

## `aet ship` — From `awaiting_merge` to Closed

`aet ship gate` runs the pre-merge gate. PR creation and merge are still human/agent steps. Closure happens **after** the PR is merged via the `ship` helper.

### Procedure

1. When tasks are `awaiting_merge`, run the pre-merge gate for each task:

   ```bash
   aet ship gate docs/plans/pkg-01-decision-records.md
   ```

2. Open the PR (e.g., with `gh pr create`), including the scope-audit section from the gate output. Report the PR URL.
3. Wait for the user to confirm the PR is merged (e.g., "merge PR and verify").
4. Run the closure helper:

   ```bash
   ship record-merge <task-id> docs/plans/<task-id>.md
   ```

   Example:

   ```bash
   ship record-merge pkg-01-decision-records docs/plans/pkg-01-decision-records.md
   ```

5. If `ship` refuses because the task's `branch` field is null, use the `--branch` or `--merge-commit` override:

   ```bash
   ship record-merge --branch <branch-name> <task-id> docs/plans/<task-id>.md
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
| `aet-plan` | `aet plan` | Creates/updates plans. |
| `aet-work` | `aet run`, `aet run-one`, `aet status`, `aet next`, `aet sync`, `aet state`, etc. | The `aet-work` skill owns the queue/orchestrator. |
| `aet-ship` | `aet ship gate` (pre-merge gate) + `ship record-merge` (closure) | Two-step workflow. |
| `aet-qa` | No direct CLI; invoked inside the pipeline. | |
| `aet-review` | No direct CLI; invoked inside the pipeline or via skill activation. | |

### Anti-Patterns

- ❌ Typing `aet evolve` as if it were a CLI subcommand.
- ❌ Treating skill activations (`aet-evolve`, `aet-qa`) as shell commands.
<!-- aet-lint: on -->
