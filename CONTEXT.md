# AE Toolkit Work Queue Context

The Agentic Engineering Toolkit uses a local work queue to coordinate sequential and parallel task execution across planning, implementation, review, and shipping skills.

## Language

**Work Queue**:
The active list of tasks stored in `.agents/work-queue.json`.
_Avoid_: issue tracker, backlog.

**Task**:
A single unit of work represented by one atomic `docs/plans/*.md` file and one queue entry.
_Avoid_: ticket, story, issue.

**Plan File**:
The markdown document in `docs/plans/` that describes how to implement a task.
_Avoid_: PRD, roadmap, spec.

**Persistent Fact**:
A value stored in the queue JSON that does not change unless the underlying reality changes, such as `plan_file`, `blocked_by`, `branch`, `worktree`, or `merge_commit`.
_Avoid_: status.

**Stored Status**:
A workflow state written to `tasks[].status`: `planned`, `in-progress`, `merged`, `abandoned`, or `failed`.
_Avoid_: blocked, unblocked.

**Derived Status**:
Actionable state computed on read from persistent facts and git ground truth: `blocked`, `unblocked`, `in-progress`, or `merged`.
_Avoid_: stored status.

**Blocker**:
A task that must reach a terminal state before another task can become pickable.

**Dependent**:
A task that is blocked by another task.

**Terminal Status**:
A stored status that ends a task’s lifecycle: `merged`, `abandoned`, or `failed`.
_Avoid_: done.

**Plan Drift**:
A plan file exists on disk but is not represented in the active queue or settled history.

**Archive / Settled History**:
`.agents/work-history.jsonl`, the append-only log of terminal tasks removed from the active queue.

**Source PRD**:
The product requirements document that generated the current queue, stored as wrapper metadata.

## Relationships

- A **Task** has exactly one **Plan File**.
- A **Task** may have zero or more **Blockers**.
- A **Task** may be a **Blocker** for zero or more **Dependents**.
- A **Dependent** is **Derived** as `unblocked` only when all its **Blockers** have a **Terminal Status**.
- **Plan Drift** occurs when a **Plan File** is absent from both the **Work Queue** and the **Archive / Settled History**.

## Example dialogue

> **Dev:** “I added a new plan file. Why doesn’t `aet-work status` show it as unblocked?”
>
> **Expert:** “`unblocked` is derived, not stored. Run `aet-work sync` so the **Work Queue** has the **Persistent Facts**, then `derive` will compute the **Derived Status** from the blockers and git state.”

## Forward-Only State Model (ADR-011)

**State**:
The canonical workflow state stored in `tasks[].state`: `planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, `merged`, `abandoned`, or `failed`.
_Avoid_: using `status` for scheduling truth once the forward-only spine is active.

**Terminal State**:
A `state` value that ends a task's lifecycle and satisfies blockers: `merged` or `abandoned`. `failed` is **not** terminal and does **not** unblock dependents.
_Avoid_: treating `failed` or legacy `done` as terminal.

**History**:
Append-only array of transition entries `{from, to, at, by, evidence}` recording every state change.

**Pending Blockers**:
Counter maintained forward by the state writer; a task becomes `ready` only when `pending_blockers == 0`.

**Stage**:
Sub-state of `in_progress` recorded in the task record (e.g., `implement`, `qa`, `review`), never in plan frontmatter.

**Live Set**:
Non-terminal tasks in `.agents/work-queue.json`; the only set loaded for scheduling.

**Settled History**:
Terminal tasks appended to `.agents/work-history.jsonl`; retained but never loaded for scheduling.

**Audit**:
Explicit human-run reconciliation of stored state against git; replaces implicit derive-on-read.

## Flagged ambiguities

- “status” was used to mean both **Stored Status** and **Derived Status**. Resolved: these are distinct concepts; only **Stored Status** lives in JSON.
- “done” was used interchangeably with `merged`. Resolved: `merged` is the canonical terminal status; `done` is legacy.
