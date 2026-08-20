---
subject: plan-source-of-truth
amends: [55]
relates: [58, 59]
---

# The Record Is the Plan After Intake

## Status

Accepted (2026-08-20). Amends ADR-055 (Settled-ness Lives in a Commutative
Provenance Ledger That Travels as Pushed Git Refs). Implements requirement R-9
of the `the-record-is-the-plan` PRD
(`docs/prds/the-record-is-the-plan-prd.md`).

## Context

R-19 of the open-work-board PRD made the task record carry the plan's spec
"rather than a path to a file", and redefined a Task as "the board entry,
carrying the spec … after R-19 no plan file need exist on the machine that runs
it". The producer side was migrated: `render_task_plan` writes the worktree plan
from the record, and `derive_queue` accepts records carrying a spec.

Consumers were not. `aet ship` resolves its argument through a filesystem-only
resolver at five entry points; `queue.archive_plan_file` copies a source file
that no longer exists; `metrics._declared_size` parses frontmatter from a path.
None of them fail loudly, because in each the absent file is indistinguishable
from "nothing to do": `archive_plan_file` returns `None` for a missing source,
`_declared_size` catches `OSError` and returns `None`, and ship reports a
not-found error advising the operator to "pass the full plan path" — advice that
cannot be followed, since no such path exists.

The measured result is that declared size is `None` for **368 of 368** settled
records, the machine-local plan archive has never received a single file, and
every task reaching `awaiting_merge` through the orchestrator cannot be shipped
by the command meant to ship it.

The filed bug report proposed a fallback: try the file, then fall back to the
record. That would have preserved both representations — and would have been
unsafe as written, because sealed records also carry a spec, so a naive
id-to-record lookup would render a plan for an already-merged task and walk it
into a second merge.

## Decision

**A plan file is an authoring-phase artifact. After intake, the task record is
the only source of the spec.**

The lifecycle has one source of truth per phase and one explicit handoff:

1. **Author** — `aet-plan` writes `docs/plans/<id>.md`. The file is the artifact.
2. **Intake** — `aet sprint add` ingests it into the record's `spec`. This is the
   handoff, and it is the only one.
3. **Post-intake** — execution, shipping, closure and measurement read
   `spec.frontmatter`, `spec.tasks`, `spec.title`, and `spec.body` from the
   record. No consumer resolves `plan_file` as a path.

Three consequences follow, and are part of this decision:

- **No fallback.** A consumer that cannot find a spec fails closed, naming the
  task id (ADR-033 §3). It never treats an absent spec as an empty or default
  value, and it never falls back to the file.
- **One argument form.** Commands operating on a task after intake accept a task
  id. Board membership via `aet sprint add` is the single entry point; a plan
  path is not an accepted argument.
- **Settled records are records.** Looking a task up means the live queue first,
  then the sealed history log. Whether a task is settled is a state precondition
  on that one record, not a second resolution path.

Tools that operate on the *authoring* corpus — `plans lint`, `plan validate`,
the R-trace lint — continue to glob `docs/plans/*.md`. They are phase-1 tools and
are unaffected.

## Consequences

Removing the second representation removes what it was serializing. The plan
archive (`queue.archive_plan_file`, `~/.aet/<slug>/plans/archive/`, and the
264-file `docs/plans/archive/`) is retired rather than repaired: `metrics` reads
exactly one thing from a settled plan, `parse_frontmatter`, and the record
carries those fields structurally.

Because 360 of 368 settled records predate R-19 and carry no spec, the archive is
today their only surviving source of declared size. ADR-058 therefore governs the
order: the settled history log is backfilled with recovered specs **before**
anything is deleted, and records recoverable from no source are named rather than
silently skipped (ADR-059).

Dropping the plan-path argument form is a breaking CLI change with no deprecation
window, consistent with this project's practice of clean cuts.

This decision is what `CONTEXT.md` must state. Its glossary currently defines a
Task as "one atomic `docs/plans/*.md` file" and a Plan File as "the source of
truth for intent" — both pre-R-19, and the open-work-board PRD recorded that "the
glossary must state what the code does" without discharging it. That correction
is part of the implementing PRD.

## Alternatives Considered

- **Fall back to the record when the file is absent** — rejected: preserves the
  two representations whose divergence is the defect, and is unsafe against
  sealed records, which also carry a spec.
- **Render a temporary plan file from the spec for consumers to parse** —
  rejected: no consumer needs a file; every one reads fields. Rendering
  re-serializes data the record already holds structurally.
- **Keep the plan path as a second accepted argument** — rejected: two entry
  points is the split this decision removes.
- **Repair the archive by rendering from the spec** — rejected: it would be a
  second serialization of record data, kept alive for a reader that needs four
  frontmatter keys.
- **Delete the archive and accept the loss of legacy declared size** — rejected:
  ADR-058 exists to prevent exactly this, and declared-vs-delivered size is
  ADR-046's calibration input.
