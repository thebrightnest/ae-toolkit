# AE Toolkit Work Queue Context

The Agentic Engineering Toolkit uses a local work queue to coordinate sequential and parallel task execution across planning, implementation, review, and shipping skills.

## Language

**Work Queue / Sprint Board**:
The ephemeral, gitignored active list of tasks stored in `.agents/work-queue.json`. It holds only the current sprint; approved plans are not added automatically.
_Avoid_: issue tracker, backlog.

**Task**:
A single unit of work represented by one atomic `docs/plans/*.md` file and, while active, one queue entry.
_Avoid_: ticket, story, issue.

**Plan File**:
The markdown document in `docs/plans/` that describes how to implement a task and records its lifecycle status. It is the durable source of truth for intent and terminal closure.
_Avoid_: PRD, roadmap, spec.

**State**:
The canonical workflow state stored in `tasks[].state` while a task is in the queue: `planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, or `failed`.
_Avoid_: using `state` for terminal truth.

**Status (plan lifecycle)**:
The lifecycle value stored in a plan file's frontmatter: `draft`, `approved`, `queued`, `in_progress`, `awaiting_merge`, `merged`, or `abandoned`. It is the source of truth for whether a task is open or closed.
_Avoid_: using plan `status` for runtime scheduling decisions; use queue `state` while the task is active.

**Blocker**:
A task that must reach a terminal state before another task can become pickable.

**Dependent**:
A task that is blocked by another task.

**Terminal State**:
A plan `status` value that ends a task's lifecycle and satisfies blockers: `merged` or `abandoned`.
_Avoid_: done.

**Plan Backlog**:
Approved plans in `docs/plans/` that are not yet in the queue and not yet closed.

**Execution Log**:
`.agents/work-history.jsonl`, the optional, gitignored append-only log of transitions and closures. It supports project-management reporting but is not used to determine whether a task is closed.

**Source PRD**:
The product requirements document that generated the plan, referenced from the plan file's Context section.

## Relationships

- A **Task** has exactly one **Plan File**.
- A **Task** may have zero or more **Blockers**.
- A **Task** may be a **Blocker** for zero or more **Dependents**.
- A **Dependent** becomes `ready` only when all its **Blockers** have a **Terminal State**; the writer promotes it forward when the last blocker reaches terminal.
- A plan with `status: approved` is part of the **Plan Backlog** until it is explicitly added to the **Work Queue**.
- A plan is closed when its `status` is `merged` or `abandoned`; at that point it no longer appears in the **Work Queue**.

## Example dialogue

> **Dev:** “I added a new plan file. Why doesn’t `aet-work status` show it as `ready`?”
>
> **Expert:** “Approved plans are not added to the sprint automatically. Run `aet-work add docs/plans/<id>.md` to put it in the queue; it will become `ready` if it has no blockers. Use `aet-work review` to see all approved plans that are not yet queued.”

## Forward-Only State Model (ADR-011, revised by ADR-013)

**State**:
The canonical workflow state stored in `tasks[].state` while a task is active in the queue: `planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, or `failed`.
_Avoid_: using `state` for terminal truth.

**Terminal State**:
A plan `status` value that ends a task's lifecycle and satisfies blockers: `merged` or `abandoned`. `failed` is **not** terminal and does **not** unblock dependents.
_Avoid_: treating `failed` or legacy `done` as terminal.

**History**:
Append-only log of transition entries and closure events written to the optional, gitignored `.agents/work-history.jsonl`. It is used for reporting, not for scheduling or closure determination.

**Pending Blockers**:
Counter maintained forward by the state writer; a task becomes `ready` only when `pending_blockers == 0`.

**Stage**:
Sub-state of `in_progress` recorded in the task record (e.g., `implement`, `qa`, `review`) and reflected in the plan footer `*Stage:*`.

**Live Set**:
Active tasks in `.agents/work-queue.json`; the only set loaded for scheduling. The queue is gitignored and recreated as needed.

**Execution Log**:
Optional, gitignored `.agents/work-history.jsonl` containing transitions and closure evidence. Projects may omit it.

**Audit**:
Explicit human-run reconciliation of stored state against git; replaces implicit derive-on-read.

## Flagged ambiguities

- “status” was used to mean both stored state and derived state. Resolved: `state` is the canonical stored value for active tasks; plan frontmatter `status` is the source of truth for lifecycle closure.
- “done” was used interchangeably with `merged`. Resolved: `merged` is the canonical terminal state; `done` is legacy.
