---
id: nsr-07-exit-gate-rehearsal
size: M
blocked_by:
  - nsr-03-circuit-breaker
  - nsr-04-on-failure-triage
  - nsr-05-stall-watchdog
  - nsr-06-per-task-cost-rollup
pipeline: standard
status: draft
security_review: skipped
security_review_reason: a rehearsal harness (fixtures + an unattended run) plus an audit write-up; it exercises existing behavior and adds no product code path, writer, or trust boundary.
docs_sync: skipped
docs_sync_reason: the deliverable is itself the audit document in `docs/audits/`; there is no separate user-facing surface to sync.
---

# Plan: Phase 5 Exit-Gate Rehearsal (injected failure + injected stall)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G5; R-12, R-13). The phase exit gate — resilience demonstrated end-to-end, not asserted.
- Precedent: the frh-14 / ewl-06 / twe-07 rehearsals wrote an A-B-findings audit to `docs/audits/`. This mirrors that shape for the night-shift runtime.
- Depends on the whole chain being live: breaker (nsr-03), triage/requeue (nsr-04), stall watchdog (nsr-05), and per-task cost (nsr-06); nsr-01/02 are transitive.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Two fixtures in `tests/fixtures/nightshift/`:
  - **Deterministic failure** — a fixture plan whose session fails the *same* way on every attempt (stable signature), so nsr-03's per-task breaker quarantines it after the threshold rather than requeuing forever.
  - **Stall** — a fixture whose session goes output-silent, so nsr-05's watchdog terminates it and nsr-01 classifies it `timeout`.
- A small queue (the two fixtures + at least one healthy task) runs unattended under `aet run` (default `--on-failure=triage`), a short `--stall-timeout`, and asserts: the healthy task completes, the deterministic failure ends `quarantined`, the stall ends killed/`timeout`, the shift exits cleanly (no hang, no whole-queue abort), and both incident tasks carry a per-task `cost` figure on the ledger.
- Write-up in `docs/audits/nightshift-runtime-rehearsal.md`: setup, observed transitions, breaker/watchdog/triage evidence, and cost figures — the recorded exit-gate artifact.

## Rejected Alternatives

- **Assert the exit gate via unit tests of each mechanism only** — rejected: the gate is specifically an *integration* claim ("the rest of the queue finishes unattended while two incidents are handled"); only an end-to-end run over a mixed queue proves the shift survives, which the per-plan unit tests cannot.
- **Use a live agent for the fixtures** — rejected: non-deterministic and costly; deterministic fixtures (scripted failure + scripted silence) make the rehearsal reproducible in CI.

## Task List

1. Add the deterministic-failure and stall fixtures under `tests/fixtures/nightshift/` — M (traces: R-12)
2. Rehearsal test: run the mixed queue unattended and assert healthy-completes / deterministic-quarantined / stall-`timeout` / clean-exit / both-costed — M (traces: R-12, R-13)
3. Write `docs/audits/nightshift-runtime-rehearsal.md` (date-stamped at execution) with the observed evidence — S (traces: R-12)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — the terminal integration gate; depends on all four capability plans

## Files to Modify

- `tests/fixtures/nightshift/` (new fixtures)
- `tests/test_nightshift_rehearsal.py` (new)
- `docs/audits/nightshift-runtime-rehearsal.md` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_nightshift_rehearsal.py`:
  - `test_mixed_queue_finishes_unattended` (healthy task reaches `awaiting_merge`)
  - `test_deterministic_failure_quarantined_by_breaker`
  - `test_stall_killed_and_classified_timeout`
  - `test_both_incidents_costed_on_ledger`
- [ ] R-trace coverage: R-12 by tasks 1–3; R-13 by task 2; no unknown R-ids
- [ ] Distinguish test types: end-to-end integration (unattended `aet run` over a mixed queue)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Fixtures, the rehearsal test, and the audit doc are additive; removing them affects no product code path.

## Pipeline

`pipeline: standard` — an integration rehearsal; `standard` grouping runs the end-to-end assertions. The audit doc is the recorded exit-gate evidence.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
