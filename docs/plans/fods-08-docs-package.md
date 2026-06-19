---
id: fods-08-docs-package
blocked_by:
  - fods-04-stage-substate
  - fods-06-migration-reconcile
  - fods-07-live-settled-partition
size: M
---

# Plan: Cross-Cutting Docs Update & Repackage

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Cross-cutting)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md`

With the new model implemented (state spine, zero-git reads, stage sub-state, fail-closed intake, live/settled partition), the docs must describe it and the `.skill` bundles must be regenerated. ADR-010 is already marked superseded and ADR-011 is already accepted, so this plan is documentation + packaging only.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Update `aet-work/SKILL.md`** — S

   Forward-only state model; `transition` is the sole writer; `audit` replaces `derive` off the hot path; live/settled partition; stage as an `in_progress` sub-state. Remove derive-on-read language.

2. **Update `aet-plan/SKILL.md` + `aet-plan/references/work-queue-format.md`** — S

   Frontmatter contract (`id`/`blocked_by`/`size`); new task-record schema (`state`, `history`, `pending_blockers`, `blocks`, `stage`).

3. **Update `docs/PIPELINE.md`, `docs/CONVENTIONS.md`, `CONTEXT.md`** — S

   Lifecycle and legal transitions, the intake contract, and the live/settled partition. Align the `migration-aet-state.md` reference if it still describes derive-on-read.

4. **`make validate` + `make package`** — S

   Regenerate the `.skill` bundles; confirm reproducibility via `scripts/check-reproducible-package.sh`.

5. **Merge branch to main and verify integration** — S

## Blocked by

- fods-04-stage-substate
- fods-06-migration-reconcile
- fods-07-live-settled-partition

## Validation Steps

- [ ] Each listed doc describes the recorded-forward model (no stale derive-on-read language remains; grep for "derive" returns only `audit`/historical references).
- [ ] `aet-plan/references/work-queue-format.md` documents the new schema fields.
- [ ] `make validate` passes and `make package` regenerates the `.skill` files.
- [ ] `scripts/check-reproducible-package.sh` confirms deterministic packaging.

## Rollback Plan

Docs-only and regenerated artifacts; revert the doc commits and re-run `make package` from the prior state.

---

_Stage: implemented_
_Next step: run `aet-qa`_
