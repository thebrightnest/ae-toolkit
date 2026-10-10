---
name: aet-drive
description: Autonomous end-to-end task and epic completion loop with natural CLI adapter auto-detection, pipelined task execution (aet run), automatic task integration (aet ship merge), and intelligent merge conflict resolution. Triggers on "/aet-drive", "run aet-drive", "aet-drive", "drive epic", "run epic", "drive sprint", "run sprint", "complete epic", "finish epic", "autonomous epic", "drive the epic to completion".
---

# aet-drive

Autonomous execution loop that drives an entire declared epic or sprint queue to completion. The skill orchestrates task execution through `aet run`, continuously auto-merges finished tasks into the active epic branch, intelligently resolves any staged merge conflicts encountered along the way, and loops until every task is closed.

## When to Use

- You have tasks in the sprint queue (with or without an active epic) and want hands-free execution to completion.
- You want the agent to automatically run pipeline stages, ship ready tasks, and resolve any integration conflicts without pausing for user intervention.
- Invoked anywhere via `/aet-drive` (or natural triggers: "run aet-drive", "drive epic", "complete epic", "run epic", "drive sprint").

## Context

Run `aet context` and parse its JSON for session context (active branch, repo state, active epic, and queue health). Print the stage banner it emits.

## Mental Model: Deterministic CLI with Autonomous Agent Judgment

In accordance with ADR-039, ADR-029, and ADR-076:

- **Deterministic CLI**: `aet run` executes the pipeline stages in isolated worktrees and continuously auto-merges clean tasks into the active epic branch under `integration_lock`. `aet ship merge` completes the integration of any staged residual tasks and records terminal closure.
- **Autonomous Agent Judgment**: When merge conflicts occur or semantic harmonization is required, the orchestrator non-blockingly stages the affected tasks in `awaiting_merge` with diagnostic metadata. The AI agent inspects recorded `conflict_diagnostics`, reconciles changes, verifies with the project test suite, and completes the merge via `aet ship merge`.
- **Epic Governance**: Tasks integrate automatically into the shared epic branch (`single-pr` mode). Opening or merging the epic PR to trunk (`main`) remains a human decision via `aet ship open-epic`.

## Prerequisites

1. `aet` is installed and on `PATH` (run `aet setup link` if needed).
2. Tasks are intaken into the sprint queue (`aet status` shows queued tasks).
3. If an active epic is set (`aet epic show`), tasks integrate into its branch. If `aet epic show` reports no active epic, proceed directly in standalone sprint mode without prompting or stopping.
4. Working tree is clean.

---

## Autonomous Execution Procedure

> **Zero-Hesitation Execution Rule**: Immediately launch `aet run`. Do not pause to audit plans, PRDs, queue history, or epic envelopes unless `aet run` fails or halts with an error. If no epic is set, proceed directly in standalone sprint mode without asking the user or stopping.

Execute this loop continuously until all tasks are closed.

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
aet epic show
aet status
```

- Note the active epic integration branch if present; if `aet epic show` outputs `No active epic.`, continue immediately in standalone sprint mode without pausing.
- Confirm tasks are ready to run on the sprint board.
- If no tasks are ready or queue is empty, report status to the user and halt.

### 3. Step A: Launch or Resume Pipeline Execution

Launch `aet run` to execute tasks through pipeline stages:

```bash
aet run
```

`aet run` starts the orchestrator in the background and prints a run ID.
Clean tasks that pass rebase and re-validation automatically merge into the active epic branch continuously during batch execution, unblocking dependent tasks in real time.

Follow execution until the batch settles:

```bash
aet run --follow <run_id>
```

*(When running in an interactive agent shell, wait for the background run notification or completion event; do not poll `manage_task` or loop on task status).*

### 4. Step B: Resolve Staged Conflicts and Merge Residuals

Clean tasks auto-merge into the active epic branch continuously during `aet run`. Tasks appearing in `awaiting_merge` after `aet run` settles were non-blockingly staged due to merge conflicts or post-rebase validation issues encountered during batch execution.

Once the orchestrator settles, inspect the sprint board:

```bash
aet status
```

Locate any tasks remaining in the `awaiting_merge` column.

If there are tasks remaining in `awaiting_merge`:

1. **Inspect Conflict Diagnostics**:
   For each task in `awaiting_merge`, inspect the recorded `conflict_diagnostics` on the task record or attempt `aet ship merge <task_id>` to identify conflicting files or validation failures.

2. **Execute Conflict Resolution Runbook**:
   For each conflicted task, follow the **Conflict Resolution Runbook** (see below) to reconcile differences and verify fixes with tests.

3. **Complete the Integration**:
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
- **If tasks are blocked or errored**: Analyze the blocker. If it requires external human decisions or credentials, pause and report details to the user.
- **If all epic tasks are closed**: The epic is complete! Proceed to **Epic Finalization**.

---

## Conflict Resolution Runbook

When a task is staged in `awaiting_merge` due to merge conflicts:

1. **Locate Conflicting Files**:
   Inspect `conflict_diagnostics` on the task record or review output from `aet ship merge <task_id>`:

   ```text
   Merging feat/<task_id> into feat/<epic> produced conflicts in:
     - path/to/file1.py
     - path/to/file2.py
   ```

2. **Inspect and Reconcile**:
   Open each conflicting file using file viewing tools.
   Examine conflict markers:

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
     aet ship open-epic
   ```
