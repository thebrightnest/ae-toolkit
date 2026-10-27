---
name: aet-drive
description: Autonomous end-to-end task and epic completion loop with natural CLI adapter auto-detection, pipelined task execution (aet run), automatic task integration (aet ship merge), and intelligent merge conflict resolution. Triggers on "/aet-drive", "run aet-drive", "aet-drive", "drive epic", "run epic", "drive sprint", "run sprint", "complete epic", "finish epic", "autonomous epic", "drive the epic to completion", "what's next", "what's unblocked", "run tasks", "run the queue", "night shift", "AFK mode", "keep working".
---

# aet-drive

Autonomous execution loop that drives the epics of a sprint queue to completion. The skill orchestrates task execution through `aet run`, continuously auto-merges finished tasks into their epic branches, intelligently resolves any staged merge conflicts encountered along the way, and loops until every task is closed.

## When to Use

- You have tasks in the sprint queue and want hands-free execution to completion.
- You want the agent to automatically run pipeline stages, ship ready tasks, and resolve any integration conflicts without pausing for user intervention.
- You have approved plans but an empty board, and want to pick which ones to admit.
- You are back from a night run and want to see what the engine left in `failed` or `quarantined`.
- Invoked anywhere via `/aet-drive` (or natural triggers: "run aet-drive", "drive epic", "complete epic", "run epic", "drive sprint", "what's next", "run the queue", "night shift", "AFK mode").

## Context

Run `aet context` and parse its JSON for session context (active branch, repo state, and queue health). Print the stage banner it emits.

## Mental Model: Deterministic CLI with Autonomous Agent Judgment

In accordance with ADR-039, ADR-029, and ADR-076:

- **Deterministic CLI**: `aet run` executes the pipeline stages in isolated worktrees and continuously auto-merges clean tasks into their epic branches under `integration_lock`. `aet ship merge` completes the integration of any staged residual tasks and records terminal closure.
- **Autonomous Agent Judgment**: When merge conflicts occur or semantic harmonization is required, the orchestrator non-blockingly stages the affected tasks in `awaiting_merge` with diagnostic metadata. The AI agent inspects recorded `conflict_diagnostics`, reconciles changes, verifies with the project test suite, and completes the merge via `aet ship merge`.
- **Epic Governance**: Tasks integrate automatically into the shared epic branch (`single-pr` mode). Opening or merging the epic PR to trunk (`main`) remains a human decision via `aet ship open-epic`.

## Prerequisites

1. `aet` is installed and on `PATH` (run `aet setup link` if needed).
2. Tasks are intaken into the sprint queue (`aet status` shows queued tasks).
3. Each task integrates into the epic branch of its PRD. `aet epic list` shows these branches.
4. Working tree is clean.

---

## Autonomous Execution Procedure

> **Zero-Hesitation Execution Rule**: Immediately launch `aet run`. Do not pause to audit plans, PRDs, queue history, or epic envelopes unless `aet run` fails or halts with an error. If no epic is set, proceed directly in standalone sprint mode without asking the user or stopping.

Execute this loop continuously until all tasks are closed.

### 0. Curate the Sprint

Run `aet status`. If it shows ready tasks, go straight to Step 1.

If no task is ready, work out the **Plan Backlog**: the `id` frontmatter of each
`docs/plans/active/*.md` that is not on the Board. `aet status` does not list the
backlog; compare the plan files against the Board yourself.

- If the backlog is empty, report the Board and halt.
- Otherwise list the backlog (id, title, `blocked_by`) and ask the user which plans
  to admit.
- Run `aet sprint add <id>` only for the ids the user names. Never bulk-add: board
  admission has one path (ADR-066). This is the one step where the
  Zero-Hesitation rule yields to the user.

No commit or push happens at intake; plan durability is deferred to terminal closure.

Intake of a new task works during a live run. `aet sprint add` and `aet sprint intake`
pass the run lease when every task they write is new, and the run spawns the task on
its next scheduling pass. Re-ingest of a task already on the Board still waits for the
run to end. Never pass `--force` to admit a task: `--force` also unlocks running tasks.

### 1. Natural CLI Adapter Adaptation

`aet run` automatically inspects process ancestry to detect host CLI adapters (`agy`, `claude`, `kimi`).

- You do **not** need to manually pass `--cli-bin` under ordinary circumstances.
- If running in a virtual or nested environment where process trees are obscured, check `echo $AET_CLI_BIN`. If unset, set `export AET_CLI_BIN=<host_bin>` or pass `--cli-bin <host_bin>`.
- Log the detected environment:

  ```text
  [aet-drive] Host adapter auto-detected. Initializing epic execution loop...
  ```

### 2. Verify Epic and Queue Status

Run:

```bash
aet epic list
aet status
```

- Note the epic branches that `aet epic list` reports. If it reports `No queued tasks.`, the queue is empty.
- Confirm tasks are ready to run on the sprint board.
- If no tasks are ready or queue is empty, report status to the user and halt.

### 3. Step A: Launch or Resume Pipeline Execution

Launch `aet run` to execute tasks through pipeline stages:

```bash
aet run
```

`aet run` starts the orchestrator in the background and prints a run ID.
One `aet run` drives every epic in the queue, one integration branch per PRD (ADR-083).
Each worktree starts from the tip of its own task's epic branch. A missing epic branch is
created locally from the trunk tip and is not pushed. Tasks on different epics run
concurrently up to `--max-jobs`. Never start a second `aet run` for another epic.
Clean tasks that pass rebase and re-validation automatically merge into their epic branches continuously during batch execution, unblocking dependent tasks in real time.

Follow execution until the batch settles:

```bash
aet run --follow <run_id>
```

*(When running in an interactive agent shell, wait for the background run notification or completion event; do not poll `manage_task` or loop on task status).*

### 4. Step B: Resolve Staged Conflicts and Merge Residuals

Tasks appearing in `awaiting_merge` on the sprint board fall into two categories:

- **Staged on the merge train** (task record has a `train` block): The task has completed its work and was staged onto `refs/aet/train/<branch>`. It is waiting for an upcoming merge train flush. When all ready work finishes or upon `aet ship open-epic`, the train flushes automatically and transitions the task to `merged`.
- **Ejected or conflicted** (task has `conflict_diagnostics`, or no `train` block): The task encountered a rebase conflict, was ejected during batch bisect validation failure (`batch_validation`), or encountered a restack conflict (`restack_conflict`). These require resolution before merging.

Once the orchestrator settles, inspect the sprint board:

```bash
aet status
```

Locate any tasks remaining in the `awaiting_merge` column.

If there are tasks remaining in `awaiting_merge`:

1. **Check Staging Status**:
   If a task is staged on the merge train (has `train` metadata), it will flush with the batch. To flush immediately, invoke `aet ship merge <task_id>` or `aet ship open-epic`.

2. **Inspect Conflict Diagnostics**:
   If a task was ejected or encountered a conflict, inspect `conflict_diagnostics` on the task record or attempt `aet ship merge <task_id>` to identify conflicting files or failing tests.

3. **Execute Conflict Resolution Runbook**:
   For each conflicted or ejected task, follow the **Conflict Resolution Runbook** (see below) to reconcile differences and verify fixes with tests.

4. **Complete the Integration**:
   Once conflicts are resolved in the task worktree, run:

   ```bash
   aet ship merge <task_id>
   ```

   *(Note: `aet ship merge` automatically resolves the target branch to the task's stamped epic branch).*

   `aet ship merge` validates gates, completes the merge into the epic branch, and records terminal closure in the provenance ledger. Proceed to the next `awaiting_merge` task.

### 5. Step C: Evaluate Queue and Loop

After processing any staged conflicts, check queue health:

```bash
aet status
```

- **If unblocked tasks are `ready`**: Return to **Step A** (`aet run`).
- **If tasks are blocked or errored**: Analyze the blocker. If it requires external human decisions or credentials, pause and report details to the user. Tasks left in `failed` or `quarantined` go to **Residual Failures**.
- **If all epic tasks are closed**: The epic is complete! Proceed to **Epic Finalization**.

---

## Conflict Resolution Runbook

When a task is in `awaiting_merge` due to integration conflict or merge train ejection:

1. **Inspect Conflict Diagnostics**:
   Inspect `conflict_diagnostics` on the task record (populated by `integrate()` or merge train `flush()`) or review output from `aet ship merge <task_id>`:

   - **`rebase_conflict`**: A direct merge conflict occurred while rebasing the task onto the integration branch.
   - **`batch_validation`**: The merge train prefix bisect identified this task as the culprit breaking batch validation. `stderr_tail` contains the failing test or command output.
   - **`restack_conflict`**: Following culprit ejection from the merge train, this downstream task could not cleanly cherry-pick onto the restacked train tip. `conflicting_files` lists the conflicting paths.

   ```json
   {
     "reason": "batch_validation",
     "conflicting_files": [],
     "stderr_tail": "FAILED tests/test_foo.py::test_bar - AssertionError...",
     "at": "2026-10-12T22:00:00Z"
   }
   ```

2. **Inspect and Reconcile**:
   - For **`batch_validation`**: Inspect `stderr_tail` to locate the failing tests or commands. In the task branch or worktree, fix the root cause and ensure all validation passes.
   - For **`rebase_conflict`** and **`restack_conflict`**: Open each conflicting file using file viewing tools. Examine conflict markers:

   ```text
   <<<<<<< <source_branch>
   [Task changes]
   =======
   [Epic integration branch changes]
   >>>>>>> <target_branch>
   ```

   Apply agent coding intelligence to synthesize both sets of changes:
   - Ensure imports, interfaces, and logic from both tasks are correctly preserved.
   - Remove all `<<<<<<<`, `=======`, and `>>>>>>>` conflict markers.

3. **Verify Resolution**:
   Run the project test suite or targeted tests in the workspace:

   ```bash
   make test
   ```

   Do not proceed until the tests pass cleanly.

4. **Stage and Commit**:
   Stage the resolved files:

   ```bash
   git add <conflicted_files>
   git commit -m "fix(merge): resolve integration conflict for <task_id>"
   ```

5. **Resume Merge**:
   Re-run:

   ```bash
   aet ship merge <task_id>
   ```

---

## Residual Failures

The engine's Triage session (ADR-030, `--on-failure=triage`, the default) already
assigns each failure its Failure Class (`environment`, `flaky`, `design`, `timeout`,
`canceled`), and the Circuit Breaker re-queues or quarantines the task. Do not repeat
that work or invent another set of classes.

For each task still in `failed` or `quarantined` after the run settles:

1. Report its recorded Failure Class and stage from `aet status`, plus the tail of
   `.agents/runs/<run-id>/output.log`.
2. For a `design` failure, point the user to re-planning with `aet-plan`.
3. Move the task forward only after the user confirms the cause is fixed:

   ```bash
   aet state transition <id> failed ready
   aet state transition <id> quarantined ready
   ```

4. Abandon a task only on the user's word:

   ```bash
   aet state transition <id> <current_status> abandoned --reason="<user's reason>"
   ```

Every move goes through `aet state transition`; never edit queue state by hand.

---

## Queue Commands

The deterministic queue surface lives in the CLI. The full operator reference is
`docs/reference/queue/queue-commands.md` in the toolkit repository.

| Command                        | Purpose                                                 |
| ------------------------------ | ------------------------------------------------------- |
| `aet status`                   | Board: counts, blockers, ready, failed, worktree health |
| `aet next`                     | Move the next ready task to `in_progress`               |
| `aet run-one <id>`             | Run the full pipeline on one task                       |
| `aet queue sync`               | Append-only reconciliation after queue edits            |
| `aet state audit` / `heal`     | Compare state with git ground truth / repair it         |
| `aet report`                   | Execution telemetry summary                             |

---

## Epic Finalization

When all tasks belonging to the epic have reached closed status:

1. Print an executive summary:
   - Epic name and integration branch.
   - List of all completed tasks.
   - Any resolved merge conflicts or notable architectural events.
2. Provide the shipping command to the user:

   ```text
   All tasks in the epic are merged and closed!
   To open the final PR to trunk (main), run:
     aet ship open-epic <branch>
   ```
