---
id: vre-03-orchestrator-serial-pole-speedup
size: M
blocked_by:
  - vre-02-orchestrator-xdist-subgroups
pipeline: standard
status: merged
security_review: skipped
security_review_reason: internal test-speed refactor; replaces sleeps/fixtures with event-based waits, no product, auth, data, or trust surface
docs_sync: skipped
docs_sync_reason: internal test-performance change with no user-facing behavior, convention, or documentation impact
---

# Plan: Shrink the Orchestrator Serial Pole (Sleeps → Event Waits)

## Context

- PRD: `docs/prds/validation-runtime-efficiency-prd.md` (R-5)
- Measured motivation: `reports/2026-07-24-validation-runtime-review.md` — the orchestrator
  group's serial pole is ~120 s of the suite's wall clock, dominated by fixed `sleep` waits and
  heavy subprocess fixtures. The suite floor is ~150 s of real work; this plan reduces the
  avoidable serial time on top of it.
- Sequenced after `vre-02`: that plan re-marks the same orchestrator test files, so doing the
  speedup first would collide on marker churn. This plan edits test bodies (waits/fixtures),
  vre-02 edits the module markers.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Profile the post-vre-02 orchestrator subgroups to find the hottest tests in the serial pole.
- Replace fixed `time.sleep`-based waits with **event/poll waits bounded by a timeout** (poll a
  condition, fail fast on timeout) so tests finish as soon as the condition holds instead of
  sleeping a fixed budget.
- Remove or lighten avoidable subprocess fixtures where a cheaper double or in-process path
  gives the same coverage.
- Preserve isolation: no test moves out of the subgroup vre-02 assigned it; behavior coverage
  is unchanged, only the waiting is faster.

## Rejected Alternatives

- **Reduce the fixed sleep durations** (e.g. `sleep(2)` → `sleep(0.2)`) — rejected: trades
  speed for flakiness; a shorter fixed sleep is still a race. Poll the condition instead.
- **Mark slow tests to skip in the fast loop** — rejected: hides the cost and loses coverage;
  the target is faster real execution, not skipping.
- **Fold into vre-02** — rejected: different files-of-concern (markers vs bodies) and each is
  independently measurable against the 238 s baseline; sequencing avoids the conflict.

## Task List

1. Profile the orchestrator subgroups (post-vre-02) and identify the hottest tests contributing
   to the serial pole — S (traces: R-5)
2. Replace fixed sleeps / heavy subprocess fixtures in those tests with bounded event/poll
   waits, coverage unchanged — M (traces: R-5)
3. Re-measure the serial pole and full-suite wall clock vs the 238 s baseline; confirm the
   suite stays green across ≥ 10 consecutive runs — S (traces: R-5)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: independently shippable and measurable; depends on vre-02 only to avoid
  editing the same files concurrently, not for correctness.

## Files to Modify

- The hottest `tests/orchestrator/*.py` (and any sibling orchestrator-group files) in the pole
- Optionally a shared `tests/` wait helper (poll-until-timeout) if several tests need it

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage: the task-3 measurement (serial-pole delta + full-suite wall clock + ≥ 10-run
  green streak) is the acceptance evidence; record the numbers on closure
- [ ] R-trace coverage: R-5 by tasks 1, 2, 3; no unknown R-ids
- [ ] No behavioral coverage lost: each edited test asserts the same conditions, only the wait
  mechanism changes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; the affected tests return to their fixed-sleep waits. vre-02's
subgroup markers are unaffected by the revert.

---

*Stage: merged*

*Next step: run `aet run-one docs/plans/vre-03-orchestrator-serial-pole-speedup.md` (after vre-02 merges)*
