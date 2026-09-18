---
name: aet-drive
description: Autonomous end-to-end epic completion loop with natural CLI adapter auto-detection, pipelined task execution (aet run), automatic task integration (aet ship merge), and intelligent merge conflict resolution. Triggers on "/aet-drive", "drive epic", "run epic", "complete epic", "finish epic", "autonomous epic", "drive the epic to completion".
---

# aet-drive

Autonomous execution loop that drives an entire declared epic to completion. The skill orchestrates task execution through `aet run`, automatically merges finished tasks into the active epic branch via `aet ship merge`, intelligently resolves any merge conflicts encountered along the way, and loops until every task in the epic is closed.

## When to Use

- You have an active epic with tasks in the sprint queue and want hands-free execution to completion.
- You want the agent to automatically run pipeline stages, ship ready tasks, and resolve any integration conflicts without pausing for user intervention.
- Invoked anywhere via `/aet-drive` (or natural triggers: "drive epic", "complete epic", "run epic").

## Context

Run `aet context` and parse its JSON for session context (active branch, repo state, active epic, and queue health). Print the stage banner it emits.

## Mental Model: Deterministic CLI with Autonomous Agent Judgment

In accordance with ADR-039, ADR-029, and ADR-076:

- **Deterministic CLI**: `aet run` executes the pipeline stages in isolated worktrees. `aet ship merge` executes the integration gate, merges tasks into the declared epic branch, and records terminal closure.
- **Autonomous Agent Judgment**: When merge conflicts occur or semantic harmonization is required, the AI agent inspects conflicting files, reconciles changes, verifies with the project test suite, and completes the merge.
- **Epic Governance**: Tasks integrate automatically into the shared epic branch (`single-pr` mode). Opening or merging the epic PR to trunk (`main`) remains a human decision via `aet ship open-epic`.

## Prerequisites

1. `aet` is installed and on `PATH` (run `aet setup link` if needed).
2. An active epic is set (`aet epic show`). If no epic is set, set one or confirm standalone sprint operation.
3. Tasks are intaken into the sprint queue (`aet status` shows queued tasks).
4. Working tree is clean.

---

## Autonomous Execution Procedure

Execute this loop continuously until all tasks in the epic are closed.

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

- Verify the active epic integration branch (e.g. `feat/<epic-name>`).
- Confirm tasks are ready to run on the sprint board.
- If no tasks are ready or queue is empty, report status to the user and halt.

### 3. Step A: Launch or Resume Pipeline Execution

Launch `aet run` to execute tasks through pipeline stages:

```bash
aet run
```

`aet run` starts the orchestrator in the background and prints a run ID.
Follow execution until the batch settles:

```bash
aet run --follow <run_id>
```

*(When running in an interactive agent shell, wait for the background run notification or completion event; do not poll `manage_task` or loop on task status).*

### 4. Step B: Identify and Ship Merges

Once the orchestrator settles, inspect the sprint board:

```bash
aet status
```

Locate all tasks in the `awaiting_merge` column.

For each task in `awaiting_merge`:

1. Run direct merge:

   ```bash
   aet ship merge <task_id>
   ```

   *(Note: `aet ship merge` automatically resolves the target branch to the task's stamped epic branch).*

2. **If merge succeeds**:
   `aet ship merge` validates gates, checks conflicts, performs the merge, and records terminal closure in the provenance ledger.
   Proceed to the next `awaiting_merge` task.

3. **If merge reports conflicts**:
   `aet ship merge` aborts and lists the conflicting files.
   Immediately trigger the **Conflict Resolution Runbook** (see below).

### 5. Step C: Evaluate Queue and Loop

After processing merges, check queue health:

```bash
aet status
```

- **If unblocked tasks are `ready`**: Return to **Step A** (`aet run`).
- **If tasks are blocked or errored**: Analyze the blocker. If it requires external human decisions or credentials, pause and report details to the user.
- **If all epic tasks are closed**: The epic is complete! Proceed to **Epic Finalization**.

---

## Conflict Resolution Runbook

When `aet ship merge <task_id>` outputs merge conflicts:

1. **Locate Conflicting Files**:
   `aet ship merge` prints the conflicting files:

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
