# AET Drive Operational Command

Reference for executing the autonomous `/aet-drive` workflow across AI coding agents. Drives an entire active epic to completion by coordinating `aet run`, continuous auto-merging, and intelligent merge conflict resolution.

## When to Use

- The user says `/aet-drive`, `drive epic`, `run epic`, `complete epic`, or `finish epic`.
- You want hands-free execution across an entire epic until all its tasks are closed.
- You need to naturally adapt the host CLI binary without manual `--cli-bin` flags.

## Operational Procedure

Execute this loop continuously until all tasks in the epic are closed.

### 1. Host CLI Adapter Adaptation

`aet run` automatically inspects process ancestry to identify whether it is running under `agy` (Antigravity), `claude` (Claude Code), or `kimi` (Kimi CLI).

- Do not pass `--cli-bin` manually unless running in a sandboxed IDE environment where process trees are hidden.
- If necessary, set `export AET_CLI_BIN=<bin>` in the environment.

### 2. Verify Active Epic & Board State

Confirm the active epic and queue readiness:

```bash
aet epic show
aet status
```

- Verify the target epic branch (e.g. `feat/<epic-name>`).
- Confirm tasks are intaken on the sprint board.

### 3. Step A: Launch or Resume Pipeline Execution

Launch the orchestrator batch:

```bash
aet run
```

Clean tasks that pass rebase and re-validation automatically merge into the active epic branch continuously during batch execution.

Follow the run until completion:

```bash
aet run --follow <run-id>
```

*(In interactive agent environments, wait for the completion message rather than polling).*

### 4. Step B: Resolve Staged Conflicts and Merge Residuals

Clean tasks auto-merge into the active epic branch continuously during `aet run`. Tasks appearing in `awaiting_merge` after the batch settles were non-blockingly staged due to merge conflicts or validation issues.

Inspect the queue for any tasks remaining in `awaiting_merge`:

```bash
aet status
```

For each task in `awaiting_merge`:

1. **Inspect Diagnostics**:
   Inspect recorded `conflict_diagnostics` on the task record or attempt `aet ship merge <task-id>` to identify conflicting files and failure reasons.

2. **Reconcile Conflicts**:
   Follow the **Conflict Resolution Runbook** below to reconcile conflicting files in the task worktree and verify fixes with tests.

3. **Complete Integration**:
   Once resolved, run:

   ```bash
   aet ship merge <task-id>
   ```

   `aet ship merge` validates gates, completes the merge into the epic branch, and records closure in the provenance ledger. Proceed to the next task.

### 5. Step C: Loop Evaluation

Check queue status:

```bash
aet status
```

- If unblocked tasks are `ready`: return to **Step A** (`aet run`).
- If an unrecoverable failure occurs: pause and report details to the user.
- If all epic tasks are closed: proceed to **Finalization**.

---

## Conflict Resolution Runbook

When a task is staged in `awaiting_merge` due to merge conflicts:

1. **Read Conflicted Files**:
   Identify the files listed in `conflict_diagnostics` or the `aet ship merge` error message.
2. **Harmonize**:
   Inspect conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`). Reconcile both sides to satisfy the task intent and maintain epic integrity. Remove all conflict markers.
3. **Validate**:
   Run project verification:

   ```bash
   make test
   ```

4. **Commit**:
   Stage and commit the resolution:

   ```bash
   git add <conflicted_files>
   git commit -m "fix(merge): resolve integration conflict for <task-id>"
   ```

5. **Resume**:
   Re-run:

   ```bash
   aet ship merge <task-id>
   ```

---

## Finalization

When all epic tasks are closed:

1. Report completed tasks to the user.
2. Inform the user that the epic integration branch is ready to ship:

   ```bash
   aet ship open-epic
   ```
