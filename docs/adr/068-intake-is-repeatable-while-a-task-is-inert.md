---
subject: repeatable-inert-task-intake
amends: [61]
relates: [55, 59, 66]
---

# Intake Is Repeatable While a Task Is Inert

## Status

Accepted (2026-08-27). Amends ADR-061 (The Record Is the Plan After Intake).
Implements requirement R-5 of the `plan-obligations-hardening` PRD
(`docs/prds/plan-obligations-hardening-prd.md`).

## Context

ADR-061 established that a plan file is an authoring-phase artifact and that,
after intake, the task record is the sole source of the spec. In ADR-061's
lifecycle description, intake via `aet sprint add` is named as "the handoff, and
it is the only one".

In practice, queued plans frequently need correction while waiting on the board.
When a sibling task merges ahead of a queued task, it may claim a requirement
anchor or shift an interface contract, making the queued plan outdated or invalid
before it runs. Because `aet sprint add` returned early as a no-op when a task was
already in the queue, the only way to update a queued task's spec was to manually
delete the task ref (`refs/aet/tasks/<id>`) on origin and re-add it. This violated
the principle that operators should not manually mutate shared remote refs to
correct normal plan changes.

## Decision

**Intake via `aet sprint add` is repeatable while a task is inert.**

1. **Inertness Predicate.** A task is *inert* if:
   - Its state is non-terminal and pre-execution: `planned`, `ready`, or `blocked`.
   - It has no assigned `branch` (null).
   - It has no assigned `worktree` (null).
   - It has no assigned `merge_commit` (null).
2. **Re-ingestion on Sprint Add.** When `aet sprint add` is invoked on an inert
   task already present on the board:
   - The plan file is re-validated via the intake validation suite.
   - The task's `spec`, `blocked_by`, `pending_blockers`, `state`, and `work_class`
     are re-derived from the plan file and current board state.
   - The task's identity (`id`), transition history, and any existing run metadata
     are preserved. If state changes, a transition entry is appended to history.
   - The updated task is written to the queue backend and pushed.
   - A `cut` event with the updated plan hash is appended to the provenance ledger.
3. **Refusal for Non-Inert Tasks.** If a task carries run state (state is
   `in_progress`, `awaiting_merge`, `merged`, `abandoned`, `failed`, or
   `quarantined`, or any of `branch`, `worktree`, or `merge_commit` is non-null),
   `aet sprint add` refuses re-ingestion and names the blocking field.
4. **The Record Remains the Sole Source Post-Intake.** Re-ingestion is an explicit
   handoff triggered by the operator running `aet sprint add`. Intake is repeatable
   while inert; it is not continuous or automatic. Execution, shipping, closure,
   and measurement continue to read solely from the task record.

## Consequences

- **Easier:** Operators can update queued plans by editing the markdown file and
  re-running `aet sprint add`, without needing to delete remote refs.
- **Easier:** Sibling plan changes can be reconciled safely before a task starts.
- **Maintained:** The core invariant of ADR-061 remains: execution engines read
  only from the task record, never from the filesystem.
