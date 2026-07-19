# AE Toolkit Work Queue Context

The Agentic Engineering Toolkit uses a local work queue to coordinate sequential and parallel task execution across planning, implementation, review, and shipping skills.

## Language

**Work Queue / Sprint Board**:
The ephemeral, gitignored active list of tasks stored in `.agents/work-queue.json`. It is rebuilt from committed plan files: only plans whose frontmatter `status` is `queued` are sprint members. Approved plans (`status: approved`) and draft plans (`status: draft`) live on the board but are not in the sprint.
_Avoid_: issue tracker, backlog.

**Task**:
A single unit of work represented by one atomic `docs/plans/*.md` file and, while active, one queue entry.
_Avoid_: ticket, story, issue.

**Plan File**:
The markdown document in `docs/plans/` that describes how to implement a task and records its lifecycle status. It is the durable source of truth for intent and terminal closure.
_Avoid_: PRD, roadmap, spec.

**State**:
The canonical workflow state stored in `tasks[].state` while a task is in the queue: `planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, `failed`, or `quarantined`.
_Avoid_: using `state` for terminal truth.

**Status (plan lifecycle)**:
The lifecycle value stored in a plan file's frontmatter: `draft`, `approved`, `queued`, `in_progress`, `awaiting_merge`, `merged`, or `abandoned`. It is the source of truth for whether a task is open or closed. New plans carry `status: draft`; intake validation requires any declared `status` to be from this set. Plans with no `status` field are grandfathered as legacy settled work.
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
- A plan with `status: approved` is part of the **Plan Backlog** until it is explicitly promoted to `status: queued`; only `status: queued` plans are loaded into the **Work Queue**.
- A plan is closed when its `status` is `merged` or `abandoned`; at that point it no longer appears in the **Work Queue**.
- Closure updates the plan file (`status` and `*Stage:*`) and the change is committed and pushed so the terminal state is versioned and reproducible across clones.

## Example dialogue

> **Dev:** “I added a new plan file. Why doesn’t `aet-work status` show it as `ready`?”
>
> **Expert:** “Approved plans are not added to the sprint automatically. Run `aet sprint add docs/plans/<id>.md` to put it in the queue; it will become `ready` if it has no blockers. Use `aet review` to see all approved plans that are not yet queued.”

## Forward-Only State Model (ADR-011, revised by ADR-013)

**State**:
The canonical workflow state stored in `tasks[].state` while a task is active in the queue: `planned`, `ready`, `blocked`, `in_progress`, `awaiting_merge`, `failed`, or `quarantined`.
_Avoid_: using `state` for terminal truth.

**Terminal State**:
A plan `status` value that ends a task's lifecycle and satisfies blockers: `merged` or `abandoned`. `failed` is **not** terminal and does **not** unblock dependents.
_Avoid_: treating `failed` or legacy `done` as terminal.

**Quarantined**:
A non-actionable task state entered when the **Circuit Breaker** judges a failure deterministic (`{in_progress, failed} → quarantined`). Like `failed`, it is **not** terminal and does **not** unblock dependents; unlike `failed`, it is never auto-retried — a human clears it forward (`quarantined → ready`) after a fix, or abandons it. (ADR-030)
_Avoid_: conflating a breaker quarantine with human `abandoned`, or expecting the scheduler to ever re-pick it on its own.

## Night-Shift Runtime (ADR-030, ADR-031)

**Failure Class**:
The single category assigned to a terminating agent session: `environment`, `flaky`, `design`, `timeout`, or `canceled`. A fixed, code-owned menu — the breaker's counting never depends on an LLM inferring it. (ADR-030)

**Failure Signature**:
A deterministic short digest of `(stage, normalized-error)` with volatile spans (paths, PIDs, timestamps, ids, line numbers) stripped, so identical failures collide and distinct ones do not. It is the key the **Circuit Breaker** counts. (ADR-030)

**Circuit Breaker**:
The deterministic rule that stops throwing work at a repeating failure: **per-task** (the same **Failure Signature** 3× ⇒ the task is quarantined) and **systemic** (one signature across N distinct tasks ⇒ the shift stops spawning). Counts are persisted, so a quarantine survives across shifts. (ADR-030)

**Triage**:
A bounded judgment session spawned on a failure under the default `--on-failure=triage`, which confirms the **Failure Class** and routes the outcome — requeue (`flaky`/`environment`) vs quarantine (`design`). Judgment lives in an explicit, sanctioned session; the engine only enforces its verdict, and the breaker bounds it. (ADR-030)
_Avoid_: reading "triage" as a runtime conditional embedded in the engine — the engine holds no hidden branch; it spawns a session and enforces the result, as it does for any stage.

**Per-Task Cost**:
Token and dollar totals rolled up per task from stage telemetry onto the task's ledger record at close, stored as `cost: {tokens, usd}`. **Analytics only** — read by the desk and the scoreboard, never by any gate, kill, or triage path. Null is preserved honestly: when no stage record carried a measurable value, the field is omitted rather than zeroed or written as a null-valued object. (ADR-031)
_Avoid_: treating cost as a budget ceiling or any execution-control signal.

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
_Avoid_: calling lifecycle states "workflow state"; using "work class" for a workflow name (work class = a recorded machine-readable task attribute, one of `trivial`/`normal`/`critical`/`unclassified`, authored in plan frontmatter).

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

## Factory Metrics (ADR-035)

**First-Pass Merge**:
A settled task that reached `merged` with every verdict kind required by its plan's **Stage Routing Key** passing, no failed stage/test_run telemetry record, and no **Rework**. Computed retroactively from settled history + telemetry archive + gate evidence by one shared definition consumed by the desk, `aet metrics`, and the scoreboard. (ADR-035, refining ADR-028)
_Avoid_: requiring verdicts for gates the plan routed to `skipped`; persisting a `first_pass` flag (derivation is query-side).

**Rework**:
Per task, the count of repeated stage runs (stage telemetry records beyond the first per stage name) plus `failed → *` re-entry transitions. A task with zero rework is a candidate **First-Pass Merge**. (ADR-035)
_Avoid_: counting `failure_signatures` as rework (a separate signal), or a second definition outside the shared counting core.

**Cost per Merged Task**:
The sum of a task's stage telemetry (`token_count` / `cost_estimate`) across the whole **Telemetry Archive** — cross-run — reported with explicit coverage counts. Null-honest: all-null stays null (Kimi `usd` is null by design), never estimated. Distinct from **Per-Task Cost**, which is the settling-run rollup stored on the ledger record for desk display. Analytics only, per ADR-031. (ADR-035)
_Avoid_: reading it from the ledger `cost` field (under-counts reworked tasks); treating it as a budget or control signal.

## Flagged ambiguities

- “status” was used to mean both stored state and derived state. Resolved: `state` is the canonical stored value for active tasks; plan frontmatter `status` is the source of truth for lifecycle closure.
- The legacy queue-record `status` key (coexistence shim from fods-02..05) is retired by frh-06/frh-07 (2026-07-09): task records carry `state` only, legacy records are normalized on read, and plan-frontmatter `status` is unaffected.
- “done” was used interchangeably with `merged`. Resolved: `merged` is the canonical terminal state; `done` is legacy.
- “workflow” was used loosely for the lifecycle state machine (e.g. “canonical workflow state”). Resolved (2026-07-11, roadmap Phase 1): **Workflow** is the named stage-sequence data file; lifecycle states are just **State**. Where older text says “workflow state,” read “lifecycle state.”
- “execution log” was used for the telemetry archive in panel docs. Resolved (2026-07-11, thp scope validation): **Execution Log** = `.agents/work-history.jsonl` only; the browsable store is the **Telemetry Archive** (panel README rewording lands with thp-05).
