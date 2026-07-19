# AET Work Operational Commands

Reference for invoking the local `aet` CLI and the AET skill pipeline in this repo. Use this whenever the user asks to run the queue, ship work, or interact with the AET state machine.

## When to Use

- The user says `aet run`, `run the queue`, `run the next task(s)`, or similar.
- The user says `aet ship`, `ship this`, `merge PR and verify`, or similar.
- The user mentions an AET skill (`aet-evolve`, `aet-plan`, etc.) and you need to know whether it maps to an `aet` CLI subcommand.

## `aet run` — Batch Queue Execution

`aet run` is the orchestrator. It spawns headless agent sessions per task and can run for **tens of minutes to hours**. Never invoke it as a short foreground command.

### Procedure

1. Run it in the background with an explicit long timeout:

   ```bash
   # Preferred: disable timeout entirely for long batches
   Bash(run_in_background=true, disable_timeout=true, command="aet run", description="AET batch queue run")

   # Alternative if the tool requires a timeout
   Bash(run_in_background=true, timeout=7200, command="aet run", description="AET batch queue run")
   ```

2. Report the background task ID to the user.
3. Poll with `TaskOutput(task_id=..., block=false)` or wait for the automatic completion notification.
4. If the user asks for status while it runs, use `TaskOutput` — do not spawn a second `aet run`.

### Anti-Patterns

- ❌ Running `aet run` as a foreground command with the default 60–300 s timeout.
- ❌ Letting the user believe the command hung when it was only killed by timeout.

## `aet run-one` — Single Task Execution

Same rules as `aet run`: run in background with a long or disabled timeout. Single tasks can still take 10–60 minutes.

## `aet ship` — From `awaiting_merge` to Closed

`aet ship` opens the PR. Closure happens **after** the PR is merged.

### Procedure

1. When tasks are `awaiting_merge`, run `aet ship <task-id>` for each task (or prompt the user for the exact task IDs if unclear):

   ```bash
   aet ship pkg-01-decision-records
   ```

2. The command opens a PR. Report the PR URL.
3. Wait for the user to confirm the PR is merged (e.g., "merge PR and verify").
4. Run the closure helper:

   ```bash
   ship <task-id> docs/plans/<task-id>.md
   ```

   Example:

   ```bash
   ship pkg-01-decision-records docs/plans/pkg-01-decision-records.md
   ```

5. If `ship` refuses because the task's `branch` field is null, use the `--branch` or `--merge-commit` override:

   ```bash
   ship --branch <branch-name> <task-id> docs/plans/<task-id>.md
   ```

### Anti-Patterns

- ❌ Asking the user to clarify whether they want to ship when they explicitly said `aet ship`.
- ❌ Trying to merge the PR yourself; the merge is the human's decision.
- ❌ Forgetting the closure step after the PR is merged.

## Skill vs. CLI Namespace

| Skill / Concept | CLI Entry Point | Notes |
| --------------- | --------------- | ----- |
| `aet-evolve` | **No CLI subcommand.** Activate as a skill. Use `aet retro` (telemetry retro) or run the `retro` + `system-evolve` procedure manually. | `aet evolve` fails. |
| `aet-plan` | `aet plan` | Creates/updates plans. |
| `aet-work` | `aet run`, `aet run-one`, `aet status`, `aet next`, `aet sync`, `aet state`, etc. | The `aet-work` skill owns the queue/orchestrator. |
| `aet-ship` | `aet ship` (open PR) + `ship` helper (closure) | Two-step workflow. |
| `aet-qa` | No direct CLI; invoked inside the pipeline. | |
| `aet-review` | No direct CLI; invoked inside the pipeline or via skill activation. | |

### Anti-Patterns

- ❌ Typing `aet evolve` as if it were a CLI subcommand.
- ❌ Treating skill activations (`aet-evolve`, `aet-qa`) as shell commands.
