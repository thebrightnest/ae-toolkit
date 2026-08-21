---
subject: open-work-board
---

# Open-Work Board Contract and Shadow Posture

## Status

Accepted (2026-08-20). Amends ADR-011 (forward-only work state), ADR-013 (queue
as ephemeral sprint board), ADR-045 (integration mode), and ADR-055
(settled-ness). Closes the documentation-truth lineage opened by ADR-054 and
ADR-055.

## Context

The board vocabulary and the shadow posture were settled at scope validation for
the open-work board PRD but had not been recorded as an ADR. Meanwhile, five
sites in the documentation and code comments continued to assert a ledger
refs-transport model that ADR-055 decided but the code did not implement. This
ADR records the shipped contract so the glossary and the code describe the same
system.

## Decision

1. **Task is the board entry.** A task is the unit of work represented by one
   queue record under `refs/aet/tasks/<id>`. It carries the spec (task list and
   gate keys) after R-19. It is not "one atomic `docs/plans/*.md` file"; the
   plan file is a rendered working copy, not the source of truth.
2. **Rendered Plan is ephemeral.** The working plan produced in a task worktree
   is rendered from the task record. It is never committed and never the source
   of anything.
3. **Issue is the projection.** A GitHub issue is the projection of a task plus
   the carrier of the `aet:sprint` intent label. It is not the source of truth
   and never replaces the task record.
4. **Board is open work.** The board is the set of non-terminal tasks loaded by
   the queue backend. It is distinct from the **Plan Backlog** (approved plans
   not yet on the board).
5. **Shadow posture is the default local-only mode.** A repository with no
   project-scope AET configuration is in shadow posture: configuration lives at
   user scope, no projection runs, and no AET artifact appears in the working
   tree. The operator has not opted into cross-device sharing, so `refs/aet/*`
   are never pushed. Every run announces the inferred posture and its
   consequence.
6. **Queue state travels; ledger and execution log do not.** Only the queue
   backend's `refs/aet/*` namespace replicates to the forge remote. The
   Provenance Ledger and Execution Log are gitignored working-tree files with
   no transport.

This amends:

- **ADR-011**: the forward-only state model applies to the board (open work);
  terminal closure is recorded in the ledger and execution log, but scheduling
  reads only the board.
- **ADR-013**: the queue is the ephemeral sprint board; the plan file is not
  the source of truth for state — the task record is.
- **ADR-045**: integration mode operates on the board; in shadow posture no
  projection runs and the integration branch remains local.
- **ADR-055**: the ledger is provenance only and has no production reader; it
  does not travel as pushed git refs. Only queue state travels.

## Consequences

- **Easier:** The glossary, skills, and code describe the same system.
- **Easier:** Shadow posture is explicit and announced, so the default is never
  silent.
- **Harder:** Documentation must be kept in sync with the shipped model; future
  changes that touch storage or posture need to update this ADR.

## Alternatives Considered

1. **Update each amended ADR in place** — Rejected. ADRs are append-only
   records; amendments are made by new records that cite the old ones.
2. **Record shadow posture as a separate ADR** — Rejected. It is inseparable
   from the board contract: the posture determines whether the board's refs
   travel.
3. **Leave the vocabulary in the PRD only** — Rejected.
   `aet-validate-scope` checks every plan against CONTEXT.md, so the glossary
   must state the shipped model.
