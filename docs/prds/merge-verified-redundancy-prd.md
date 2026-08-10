# PRD: Eliminate `merge_verified` Redundancy

## Overview

The work queue currently carries both a `merge_verified` boolean field and a `status` field that includes `merged`/`done`/`abandoned`. This is confusing: the same semantic ("is this work verified on origin/main?") lives in two places with the same conceptual name. This PRD removes `merge_verified` entirely and makes `status` the single source of truth.

## Goals

1. **Single source of truth** — `status` alone communicates where a task is in its lifecycle.
2. **Remove confusion** — No more `merge_verified: true` vs `status: merged` ambiguity.
3. **Simplify skill instructions** — `aet-work`, `aet-ship`, and `aet-pipeline-implement` reference one field, not two.

## Non-Goals

- Changing the semantics of `merged`/`done`/`abandoned` (already defined).
- Adding new statuses or transitions.
- Modifying the orchestrator runtime logic beyond field references.

## User Stories

- As an agent operator, I want the queue to have one field for terminal state so I don't need to check two fields to know if a task is safely on main.
- As a skill maintainer, I want skill instructions to reference `status` only, so there's no risk of checking `merge_verified` while forgetting `status` (or vice versa).

## Acceptance Criteria

- [ ] `merge_verified` is removed from the work queue schema going forward; skill instructions no longer read or write it.
- [ ] `aet-work/SKILL.md` references `status` only; `merge_verified` is removed from `sync`, `cleanup`, `mark-terminal`, `post-ship-verify`, and orchestrator-template instructions.
- [ ] `aet-ship/SKILL.md` references `status` only; `merge_verified` is removed from merge result examples.
- [ ] `aet-pipeline-implement/SKILL.md` references `status` only; `merge_verified` is removed from post-ship queue update instructions.
- [ ] `aet-work` `cleanup` command uses `status == "merged"` (and `merge_commit` set) to determine verification instead of `merge_verified`.
- [ ] `aet-work` `mark-terminal` command validates `status == "merged"` requires `merge_commit` set and git ancestry check passing.
- [ ] Backward-compatible: old queue entries with `merge_verified` are ignored (skill instructions reference `status` only).

## Technical Notes

- The queue JSON schema loses one field; no new fields are added.
- Git ancestry verification (`git merge-base --is-ancestor <ref> origin/main`) is still performed by `cleanup` and `mark-terminal`, but the result is expressed via `status` transition, not a boolean flag.
- Example docs in `aet-ship/examples/` that show `merge_verified` must be updated.

---

## Disposition (2026-08-10, structural-review-tier-2 scope validation)

**Closed — superseded.** mvr-01 merged (the only plan this PRD produced; no `mvr-*` siblings exist). The PRD's premise — "`status` as the single source of truth" — was voided when ADR-055 deleted the `status` field from the plan contract; settled-ness is now derived from the provenance ledger plus git ancestry.

---

_Stage: closed (superseded by ADR-055; delivered by mvr-01)_
_Next step: none_
