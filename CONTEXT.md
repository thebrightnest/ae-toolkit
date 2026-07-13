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

**Gate Evidence (Verdict)**:
A schema-validated JSON verdict written by a checking skill (qa, review, cso, sync-docs) to `~/.aet/reports/{project-slug}/{task-id}/`, consumed fail-closed by the orchestrator's stage gates (ADR-019). The plan footer `*Stage:*` remains a human breadcrumb; gating decisions read evidence, never the footer.
_Avoid_: treating a footer stage string as proof a stage passed.

**Workflow**:
A named, versioned data file defining one linear stage sequence with its skill and evidence bindings (packaged default `aet-work/workflows/<name>.json`, overridable per repo in `.agents/workflows/`). Selected by the plan frontmatter key `workflow:` (default `software`). Stage vocabulary comes from the workflow; lifecycle **State** stays frozen in code.
_Avoid_: calling lifecycle states "workflow state"; using "work class" for a workflow name (work class = the Trivial/Normal/Critical intake tiers in `docs/PIPELINE.md`).

**Stage Routing Key**:
Plan frontmatter (`security_review`, `docs_sync`: `required`/`skipped`, with a reason required when skipped) deciding at plan time whether a gated stage runs. Policy input authored at triage — part of the plan's machine contract, not runtime judgment and not state.
_Avoid_: runtime heuristics deciding whether a gate runs.

## Telemetry & Panel (ADR-012, ADR-019, ADR-022)

**Telemetry Archive**:
The user-level store of execution records at `~/.aet/telemetry/{project-slug}/{date}/{run-id}/` (override: `AET_TELEMETRY_ARCHIVE_DIR`).
_Avoid_: "execution log" — that term is reserved for `.agents/work-history.jsonl`.

**Project Slug**:
`<main-worktree-dirname>/<current-worktree-dirname>` (primary worktree labelled `main`, e.g. `aiskills/main`), derived by `derive_project_slug()` and shared by the telemetry archive and the gate-evidence reports tree (ADR-022). `AET_PROJECT_ID` overrides.
_Avoid_: origin-remote derived names (pre-ADR-022).

**Run**:
One orchestrator invocation, recorded as one run directory in the telemetry archive. The execution vehicle for tasks — not the unit of intent.
_Avoid_: calling runs "projects".

**Project (telemetry/panel)**:
The repo-level grouping — first slug segment. The panel's top grouping level.
_Avoid_: "folder" in UI copy.

**Worktree (run attribute)**:
Where a run or session launched — second slug segment, or parsed from a record's raw `plan_file` prefix. An attribute/filter of a run, never a grouping level.

**Live Run (panel)**:
A run with no `last-run.json` whose archive activity is fresh — within `LIVE_FRESHNESS_MINUTES` of the newest recursive mtime, or with an mtime that advanced between panel polls (panel-live-executions PRD, lvp-01/lvp-02). A panel display status only.
_Avoid_: conflating with the queue's **Live Set** (active tasks in `.agents/work-queue.json`) — the two share no code or data.

**Incomplete Run (panel)**:
A run with no `last-run.json` and stale archive activity — crashed, abandoned, or quiet mid-stage. Always rendered with its last-activity time, never as "success" or "crashed".

## Flagged ambiguities

- “status” was used to mean both stored state and derived state. Resolved: `state` is the canonical stored value for active tasks; plan frontmatter `status` is the source of truth for lifecycle closure.
- The legacy queue-record `status` key (coexistence shim from fods-02..05) is retired by frh-06/frh-07 (2026-07-09): task records carry `state` only, legacy records are normalized on read, and plan-frontmatter `status` is unaffected.
- “done” was used interchangeably with `merged`. Resolved: `merged` is the canonical terminal state; `done` is legacy.
- “workflow” was used loosely for the lifecycle state machine (e.g. “canonical workflow state”). Resolved (2026-07-11, roadmap Phase 1): **Workflow** is the named stage-sequence data file; lifecycle states are just **State**. Where older text says “workflow state,” read “lifecycle state.”
- “execution log” was used for the telemetry archive in panel docs. Resolved (2026-07-11, thp scope validation): **Execution Log** = `.agents/work-history.jsonl` only; the browsable store is the **Telemetry Archive** (panel README rewording lands with thp-05).
