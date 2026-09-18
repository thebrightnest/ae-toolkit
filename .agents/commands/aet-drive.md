# AET Drive Operational Command

Reference for executing the autonomous `/aet-drive` workflow across AI coding agents. Drives an entire active epic to completion by coordinating `aet run`, `aet ship merge`, and intelligent merge conflict resolution.

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

Follow the run until completion:

```bash
aet run --follow <run-id>
```

*(In interactive agent environments, wait for the completion message rather than polling).*

### 4. Step B: Merge Completed Tasks

Inspect the queue for tasks that reached `awaiting_merge`:

```bash
aet status
```

For each task in `awaiting_merge`:

1. Execute direct merge:

   ```bash
   aet ship merge <task-id>
   ```

   `aet ship merge` automatically resolves the target branch to the task's stamped epic branch.

2. **If clean**: The gate passes, changes merge into the epic branch, and closure is recorded. Proceed to the next task.
3. **If conflicts are detected**:
   `aet ship merge` halts and lists the conflicting files.
   Follow the **Conflict Resolution Runbook** below.

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

When `aet ship merge <task-id>` outputs merge conflicts:

1. **Read Conflicted Files**:
   Identify the files listed in the error message.
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
