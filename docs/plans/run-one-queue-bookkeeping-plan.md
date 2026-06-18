---
id: run-one-queue-bookkeeping-plan
blocked_by: []
size: S
---

# Plan: Make `run-one` update the work queue

## Context

`aet-work run-one <plan>` runs the full pipeline on a single plan file, but it never writes to `.agents/work-queue.json`. After the branch is merged, `aet-state record-merge` fails because the task has no `branch` or `worktree` recorded. The recent `2026-06-18-orchestrator-run-one-hardening` task had to be fixed up manually after merge.

`run_batch` already solves this: before it spawns a child process for each task, it records `branch` and `worktree` via `queue.record_task_meta()`. `run_single` should do the equivalent when the plan corresponds to a queued task.

## Intake Triage

- [x] Defect-driven hardening of existing tooling with a known reproduction (manual queue fix-up after `run-one` + merge).
- [ ] If treated as a pure defect, a companion `docs/bugs/` entry can be filed via `aet-bug-report`.

**Reproduction:**

1. Add a plan to `docs/plans/` and run `aet-work sync`.
2. Run `aet-work run-one docs/plans/TASK-plan.md`.
3. Ship the resulting branch with `aet-ship` and merge the PR.
4. Run `aet-state record-merge TASK .agents/work-queue.json`.
5. Observe: `Task TASK has no branch.`

## Tasks

1. **Look up the queued task from `run_single`** — S (`aet-work/bin/orchestrator`)

   In `run_single`, after resolving the absolute `plan_file` path, attempt to read `.agents/work-queue.json` and find the task whose `plan_file` matches. Prefer an exact match; fall back to matching the task `id` against the plan filename stem. If no queued task is found, continue without queue mutation (preserves the ability to run arbitrary plan files outside the queue).

2. **Record `branch`/`worktree` and transition state when appropriate** — S (`aet-work/bin/orchestrator`)

   If a queued task is found and `AET_TASK_ID` is **not** set (i.e. this is a top-level `run-one`, not a child spawned by `run_batch`), atomically:

   - Transition the task from `planned` → `in_progress` using `aet-state transition`.
   - Record `branch` and `worktree` via `queue.record_task_meta()`.
   - Write the queue back to disk.

   When `AET_TASK_ID` **is** set, skip the write; the parent `run_batch` already owns the queue record.

3. **Defend against race conditions and partial writes** — S (`aet-work/bin/orchestrator`)

   Queue writes must be atomic: read the latest queue, apply the mutation, and write it back. If the transition or write fails, log the error and continue with the run (do not block implementation because of queue bookkeeping).

4. **Unit tests** — S (`tests/test_orchestrator.py`)

   - `test_run_single_records_branch_and_worktree_when_plan_is_queued`
   - `test_run_single_does_not_mutate_queue_when_plan_not_queued`
   - `test_run_single_does_not_mutate_queue_when_spawned_by_batch`
   - `test_record_merge_succeeds_after_run_one` (end-to-end using a temp repo, queue, and mocked merge)

5. **Update skill docs** — XS (`aet-work/SKILL.md`)

   Add a note to the `run-one` section stating that when the plan file is tracked in the work queue, `run-one` will move the task to `in-progress` and record the branch/worktree.

6. **Run end-to-end and archive** — S

   Run `aet-work run-one` on a small plan, verify the queue shows `in-progress` with `branch`/`worktree`, ship it, and confirm `aet-state record-merge` succeeds without manual fix-up.

## Dependencies

- Independent of other in-flight work; touches only `aet-work/bin/orchestrator`, `tests/test_orchestrator.py`, and `aet-work/SKILL.md`.
- Task 4 depends on Task 2.

## Validation Steps

- [ ] Lint passes (`make validate`).
- [ ] Tests pass; `tests/test_orchestrator.py` covers queue bookkeeping for `run-one`.
- [ ] After `run-one` on a queued plan, `.agents/work-queue.json` shows the task as `in-progress` with `branch` and `worktree` set.
- [ ] After `run-one` on an unqueued plan file, the queue is unchanged.
- [ ] When `run-one` is spawned by `run_batch` (`AET_TASK_ID` set), the child does not write the queue.
- [ ] `aet-state record-merge` succeeds after the branch ships, with no manual queue edits.

## Rollback Plan

Revert `aet-work/bin/orchestrator`, `aet-work/SKILL.md`, and `tests/test_orchestrator.py`. The queue is the only runtime state touched; reverting restores the previous behaviour with no schema impact.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
