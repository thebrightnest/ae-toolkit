# PRD: Plan Obligations Hardening

## Overview

A plan declares its machine contract once, at plan time: the spec the task will
execute, and the routing keys deciding which gated stages run. Three points in
the toolkit fail to honour that contract after intake. The spec is frozen with
no correction path, so a plan that becomes wrong while queued can only be fixed
by deleting shared refs on origin. The verify obligation for critical work is
enforced at `aet ship merge` but produced by no stage, so a task is refused
after every expensive stage has run. The divergence record — what a task built
that its plan did not describe — is a side effect of the docs stage, so routing
that stage to `skipped` drops the record with it.

Each is a case of an obligation without a matching owner. This PRD gives each
obligation one owner, and makes the frozen spec correctable while the task has
not yet run.

## Goals

1. Correcting a queued plan is a supported operation that touches no shared
   remote state.
2. A critical task's verify evidence is produced by the pipeline that requires
   it, and the requirement is declared in one place.
3. The record of unplanned work survives any routing decision about
   documentation.

## Non-Goals

- **Making verify universal.** `docs/prds/conditional-live-verification-prd.md`
  states as a non-goal that normal and trivial tasks run verification; that
  decision stands. The verify stage runs for critical work only.
- **A `sprint remove` subcommand.** A task leaves the board by tombstone
  assertion (ADR-059); removal and re-add would mint a tombstone and then have
  to defeat it.
- **Unfreezing the spec.** The record remains the only source of the spec after
  intake (ADR-061). Intake becomes repeatable while a task is inert; it does not
  become continuous.
- **Narrative divergence prose.** The written Divergence Summary remains the
  work of `aet-sync-docs` when that stage runs. Only the mechanical record moves.
- **Renaming a queued plan file.** A rename changes the filename stem, so
  `_add`'s lookup matches no existing record and admits a second task while the
  original stays on the board. The gap predates this PRD and is not narrowed by
  re-ingestion.
- **The three defects filed separately.** `aet ship merge` validating the
  ambient checkout, `teardown_worktree`'s obstruction predicate, and
  `telemetry.report` reading the wrong archive file are reproducible defects
  routed to `aet-bug-report`.

## Requirements

- **R-1**: `aet sprint add` on a queued task that has not run re-ingests the
  plan file into the task record's `spec`.
- **R-2**: The command reports which of three outcomes occurred — task admitted,
  spec re-ingested with changed content, or spec unchanged — in distinguishable
  wording.
- **R-3**: `aet sprint add` refuses to re-ingest a task carrying run state,
  naming the state or artifact that blocks it.
- **R-4**: Re-ingestion recomputes `blocked_by`, `pending_blockers`, `state` and
  `work_class` from the plan file and the current board, and preserves the
  task's `id`, transition history, and any recorded run fields.
- **R-5**: An ADR amends ADR-061 to record that intake is repeatable while a
  task is inert, and that the record remains the sole source of the spec.
- **R-6**: A workflow stage may declare that its gate defaults to skipped unless
  the plan's `work_class` is `critical`, so the default is derived from
  plan-time data rather than judged at run time.
- **R-7**: The packaged `software` workflow defines a verify stage that runs for
  critical work and is skipped otherwise, producing `verify` evidence.
- **R-8**: `aet ship merge` resolves the verify evidence requirement from the
  workflow definition rather than from a hardcoded work-class branch.
- **R-9**: Terminal closure records the mechanical divergence between a task's
  spec and its merged diff on the settled history record.
- **R-10**: The divergence record is written independently of the `docs_sync`
  routing key.
- **R-11**: A divergence computation that cannot complete is recorded as a
  failure with a reason, and never blocks a task from settling.

## User Stories

- As an operator queueing plans in bulk, I want to correct a plan a sibling has
  invalidated by editing the file and re-running `aet sprint add`, so that
  correcting a plan does not require deleting refs other clones read
  (satisfies: R-1, R-3, R-4).
- As an operator, I want the intake command to tell me whether it changed
  anything, so that a failed correction does not read as a completed one
  (satisfies: R-2).
- As a maintainer, I want the repeatable-intake rule recorded as a decision, so
  that the lifecycle in ADR-061 and the code agree (satisfies: R-5).
- As a developer shipping critical work, I want the pipeline to produce the
  verify evidence its own ship gate demands, so that a refusal does not arrive
  after every expensive stage has run (satisfies: R-6, R-7, R-8).
- As a maintainer reading a settled task, I want to see what it built that its
  plan did not describe, whatever the plan decided about documentation
  (satisfies: R-9, R-10).
- As an operator, I want a task to settle even when its divergence cannot be
  computed, so that a reporting concern never blocks closure (satisfies: R-11).

## Acceptance Criteria

- [ ] Editing a queued plan file and re-running `aet sprint add` changes the
      `spec.body` stored in `refs/aet/tasks/<id>`, with no `git update-ref` or
      `git push --delete` in the procedure (satisfies: R-1).
- [ ] The three intake outcomes print three distinct messages; the unchanged
      case is not worded as the admitted case (satisfies: R-2).
- [ ] A task with a non-null `branch`, `worktree`, or `merge_commit`, or in
      `in_progress`, `awaiting_merge`, `failed`, or `quarantined`, is refused
      with the blocking field named (satisfies: R-3).
- [ ] After re-ingesting a plan whose `blocked_by` changed, the task's
      `pending_blockers` and `state` match the new blocker set, and its
      transition history retains its earlier entries (satisfies: R-4).
- [ ] An ADR numbered 066 or later amends ADR-061 and is referenced from
      `CONTEXT.md`'s Plan Lifecycle section (satisfies: R-5).
- [ ] A plan with `work_class: critical` and no verify routing key runs the
      verify stage; the same plan with `work_class: normal` skips it, and the
      skip is reported with its source (satisfies: R-6, R-7).
- [ ] A critical task that completed the pipeline reaches `aet ship merge` with
      verify evidence already present, and a workflow with no verify stage
      produces no verify requirement at ship (satisfies: R-8).
- [ ] A task closed with `docs_sync: skipped` carries a divergence record naming
      files changed outside the plan's declared file list (satisfies: R-9, R-10).
- [ ] A closure whose merge commit has no first parent records the divergence as
      failed with a reason and still settles (satisfies: R-11).

## Technical Notes

**Intake re-ingestion.** `_add` in `src/aet/cli/sprint.py:97` returns early at
`:123-130` when a task with the plan's id is already on the board. The
re-ingestion path replaces that early return for inert tasks. `new_task_from_plan`
(`src/aet/plan_parser.py:479`) already derives every field re-ingestion needs —
`spec`, `blocked_by`, `pending_blockers`, `state`, `work_class` — from the plan
and the live board, so re-ingestion re-runs it and carries forward the identity
and run fields from the existing record. `backend.fetch()` at `sprint.py:104`
runs before the board is read, which is why a locally deleted ref returns before
the existing-task check; the outcome wording in R-2 makes that reconciliation
visible rather than silent.

**Gate defaults.** `stage_enabled` (`src/aet/cli/orchestrator.py:1610`) resolves
a gated stage purely from frontmatter: absent key means run. R-6 adds a second
default, selected per stage by the workflow definition, deriving from the plan's
`work_class`. Both defaults remain plan-time data, so ADR-020's rule that routing
is decided at plan time and enforced as data holds. The registries to extend are
`ROUTING_GATE_KEYS` and `VERDICT_GATE_KEYS` (`plan_parser.py:545-551`),
`_STAGE_KEYS` (`src/aet/workflow.py:23`), and `required_evidence`
(`src/aet/gate.py:59`). `_routing_key_error` (`plan_parser.py:568`) already
enforces that a `skipped` key carries a non-empty reason; a verify key inherits
that contract by being added to `ROUTING_GATE_KEYS`.

**Ship requirement.** `_run_gate`'s critical-class branch at
`src/aet/cli/ship.py:523-540` reads `work_class` from the spec and checks
`.agents/verify/<task>-evidence.md`. R-8 replaces the class branch with a
workflow lookup; the evidence path stays as the verify stage's output location.

**Divergence at closure.** `plan_size.delivered_size`
(`src/aet/plan_size.py:49`) already computes `git diff --numstat` over
`<merge_commit>^1..<merge_commit>` at closure, treats every git failure as a
recorded failure rather than an exception, and writes onto the settled history
record through `metrics.backfill_delivered_size` (`src/aet/metrics.py:323`). The
divergence record uses the same range with `--name-only`, compares against the
file list in the task's `spec`, and adopts the same fail-soft contract, which is
what R-11 requires.

## Architecture Decisions

- Intake is repeatable while a task is inert; the record remains the sole source
  of the spec after intake. Amends ADR-061.
- A gated stage's default may derive from another plan-time frontmatter key.
  Extends, and does not weaken, ADR-020 decision 4: `work_class` is authored at
  plan time, and the engine applies a fixed rule to it rather than judging at
  run time. Recorded as ADR-067.
- A default-derived skip carries no written reason, unlike an explicit
  `skipped`. The `work_class` declaration is the plan-time judgment in that
  case. Recorded as ADR-067.
- The mechanical divergence record belongs to closure, not to a stage. The
  narrative Divergence Summary remains a stage output.

## Resolved Questions

1. **Re-ingestion needs no `id`-mismatch refusal.** Intake validation already
   rejects a plan whose frontmatter `id` differs from its filename stem
   (`plan_parser.py:633-634`), so the two cannot diverge by editing. A renamed
   plan file is a separate case, recorded in Non-Goals.
2. **The divergence record does not surface in `aet metrics`.** That command
   prints the `metrics.aggregate` projection — first-pass rate, rework, and cost
   as per-work-class rate buckets. A per-task list of surplus paths does not fit
   that shape, and an aggregate form would be a new canonical metric definition
   under ADR-035. The record lands on the settled history entry only.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Reproducible defects found alongside these items — the ship-merge gate
      reading the ambient checkout, the teardown obstruction predicate, and
      `telemetry.report` scanning the wrong archive file — were routed to
      `aet-bug-report` rather than planned here

## Divergence Summary

_Recorded: 2026-08-27 — Branch: poh-02-verify-routing-key-and-work-class-gate-default_

### Changed from plan

- (none)

### Added (unplanned)

- Re-export `settled_ids_from` in `src/aet/cli/sprint.py` to maintain backward compatibility across sprint subcommands.

### Deferred

- **Task 8 (merge branch to main and verify integration)**: deferred to the `aet-ship` closure stage, consistent with the standard pipeline.

---

*Stage: synced*
*Next step: run `aet-ship`*

