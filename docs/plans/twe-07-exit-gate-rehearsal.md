---
id: twe-07-exit-gate-rehearsal
size: S
blocked_by:
  - twe-03-desk-actions-merge-abandon
  - twe-05-intake-gate-wiring
  - twe-06-zero-review-mechanism
  - twe-09-harness-merge-guard
pipeline: standard
security_review: skipped
security_review_reason: a demonstration + write-up that exercises already-shipped, already-reviewed code paths (desk merge, intake rejection, zero-review off); it introduces no new runtime code path of its own.
docs_sync: skipped
docs_sync_reason: the deliverable is an audit document under `docs/audits/`; it records evidence rather than changing a user-facing contract, so there is no skill/doc contract to sync.
status: merged
---

# Plan: Phase 4 Exit-Gate — End-to-End Rehearsal + Audit Doc

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G4, G5; R-10, R-11, R-14). The phase's exit gate, demonstrated rather than asserted — matching the frh-14 / ewl-06 A-B-findings precedent (`docs/audits/2026-07-git-refs-backend-ab.md`, `docs/audits/2026-07-enforcement-walls-rehearsal.md`).
- Depends on all four capability streams being merged: desk actions (twe-03), the intake wall (twe-05), the zero-review mechanism (twe-06), and the harness merge-guard (twe-09).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- A recorded rehearsal exercising the three exit-gate claims end-to-end, written up in `docs/audits/2026-07-two-human-ends-rehearsal.md`:
  - **(a) Desk merge** — an `awaiting_merge` task is reviewed in `aet desk` and **merged from the desk** (`aet desk merge <id>`), reaching `merged` via the closure path.
  - **(b) Intake rejection** — a plan that fails validation is **rejected at `aet-work add`** and does not enter the queue.
  - **(c) Zero-review present-but-off** — the shipped default config auto-merges nothing, shown alongside the twe-06 test proving that with a class explicitly enabled and its track-record threshold met, an equivalent task *would* auto-merge.
  - **(d) Merge-guard holds** — after `aet setup` installs the guard (twe-09), an agent-issued `gh pr merge` under simulated auto mode is **refused**, while `aet desk merge` and a plain `git push` succeed — demonstrating the exit-end boundary is enforced, not merely defaulted (the 2026-07-15 audit's core failure).
- The audit doc records commands, observed outputs, and a findings section (what held, what surprised), consistent with the prior rehearsal write-ups.

## Rejected Alternatives

- **Assert the exit gate in the PRD without a recorded rehearsal** — rejected: the phase's own G4 demands demonstration; the frh/ewl precedent is a written A-B-findings audit, not a claim.
- **Fold the rehearsal into twe-03/05/06's own tests** — rejected: those tests prove each mechanism in isolation; the exit gate is the *integrated* walk-through across all three, and belongs in one place after they land.

## Task List

1. [x] Execute the four-part rehearsal (desk merge, intake rejection, zero-review off, merge-guard refuses a self-merge) on a scratch queue and capture commands + outputs — S (traces: R-10, R-14)
2. [x] Write `docs/audits/2026-07-two-human-ends-rehearsal.md` (setup, A-B observations per claim, findings), citing the twe-06 enabled-and-qualified test as the (c) proof and the twe-09 guard as the (d) proof — S (traces: R-10, R-11, R-14)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level
- [x] Single deliverable (one audit doc from one rehearsal); no branch-sharing concern
- [x] Depends on twe-03/05/06/09 being merged first (`blocked_by` edges)

## Files to Modify

- `docs/audits/2026-07-two-human-ends-rehearsal.md` (new)

## Validation Steps

- [x] `make validate` passes
- [x] The audit doc records all four claims with observed commands + outputs; the (c) claim cites the passing twe-06 enabled-and-qualified test and the (d) claim cites the twe-09 guard refusing a self-merge
- [x] R-trace coverage: R-10 by tasks 1–2; R-11 (integration demonstration) by task 2; R-14 (guard demo) by tasks 1–2; no unknown R-ids cited
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin-main`

## Rollback Plan

Revert the merge commit — removes a documentation artifact only; no code path is affected.

## Pipeline

`pipeline: standard` — a demonstration + audit write-up over already-shipped code; no isolation profile needed.

---

*Stage: merged*
*Next step: None*
