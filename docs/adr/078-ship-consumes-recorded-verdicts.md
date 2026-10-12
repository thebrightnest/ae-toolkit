---
subject: ship-verdict-consumption
relates: [70, 25, 48]
---

# Ship Consumes Recorded Verdicts; Validation Is Configured Once

## Status

Accepted (2026-10-12). Supersedes ADR-070 decision 2 only; ADR-070's other
decisions stand. Delivered by `mtv-02-validation-config-and-verdict-aware-gate`
(PRD: `docs/prds/merge-train-validation-prd.md`).

## Context

ADR-070 decision 2 kept `aet ship` from reading any verdict but `verify`, on the
ground that the reports archive (`~/.aet/reports`) is per-machine, so a task
shipped from a different checkout would be refused for evidence that existed
elsewhere. Two facts undercut it:

- A task's lifecycle — run, integrate, ship — happens on one machine. The
  operator posture never moves an in-flight task between machines.
- `aet run` integration already reads every required verdict kind from that
  same archive (`gate.check_task_evidence` in `_integrate_completed_task`).
  The concern was applied to one integration path and not the other.

The consequence was that ship could not ask the question ADR-025 already
answers in code — "does the QA verdict still cover this tree?" — and re-ran
the full suite after every rebase, including rebases that changed nothing.
The command it ran was configured by `AET_SHIP_TEST_CMD`, while integration
used `AET_INTEGRATION_VALIDATE_CMD`; the two could disagree about what
"validated" means.

## Decision

1. **Ship-time gates consume recorded verdicts.** `aet ship gate`,
   `aet ship merge` and `aet ship open-epic` decide whether to validate with
   `evidence.validation_freshness` (ADR-025), exactly as stage spawns do.
2. **The decision is code.** `validation.pre_integration_check` maps
   SKIP → nothing; LINT_ONLY → `lint_command`, else `validate_command`;
   RUN → `validate_command`. Every uncertainty is RUN.
3. **A missing verdict means run, not refuse.** On a machine without the
   verdict (not the supported posture, but possible), freshness returns RUN
   and the suite runs. Evidence *requirements* (ADR-019, ADR-070 decision 1)
   are unchanged.
4. **Validation is configured once.** `validate_command` and `lint_command`
   are project config keys under the ADR-048 two-layer model.
   `AET_SHIP_TEST_CMD`, `AET_INTEGRATION_VALIDATE_CMD` and
   `AET_SHIP_COVERAGE_CMD` are removed without aliases (ADR-039).

## Consequences

- A rebase that pulls in nothing yields an identical content hash, so ship
  runs nothing.
- `aet run` and `aet ship` cannot diverge on the validation command.
- Projects that exported the removed variables must set `validate_command`
  instead; the variables are silently ignored after upgrade, so the upgrade
  guide must name them.
- The single-machine lifecycle becomes an explicit posture in CONTEXT.md.

## Alternatives Considered

- **Keep ADR-070 decision 2 and add a ship-local freshness record** —
  rejected: a second store for the same fact.
- **Keep one environment override** — rejected: two configuration channels
  are how the two commands drifted.
