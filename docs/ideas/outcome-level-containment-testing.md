# Idea: Assert Runaway Containment at the Outcome, Not per Mechanism

- **Status:** Proposed (2026-08-28). Not blocked by any decision; blocked only on
  being planned.
- **Origin:** `docs/retros/2026-08-28-aet-run-retro.md`. Five mechanisms exist to
  stop a runaway requeue loop and four were inert at once, each for its own
  reason, while every one of them had a passing test.
- **Would-be artifact:** a small PRD and one end-to-end test fixture; no ADR is
  needed, because nothing here contests a decision.

## Summary

Four independent stops failed together on 2026-08-27 — throttle classification,
the throttle stop, the per-task breaker, and the loop miner — at a cost of
$23.77 on one task. Each has since been fixed, and each already had a test that
passed throughout.

Every one of those tests exercised its mechanism. None asserted the outcome: that
a task whose sessions keep failing stops being spawned, within a bounded number
of attempts, at a bounded cost. A single test that asserts the outcome would have
failed on 2026-08-27 with all four defects present, and would fail again on the
fifth mechanism nobody has found yet.

## Why the existing tests could not catch it

Three patterns, all documented in the retro and each independently sufficient:

- **The fixture is not shaped like a project.** Shared posture requires an
  in-tree `.agents/aet-config.json`; no test repo has one, so pushes are
  suppressed, `refs/aet/*` never reaches origin, and the ref-overwrite defect is
  invisible. A configured project — the recommended setup — is the only place it
  bites.
- **Thresholds are patched away for speed.** The end-to-end rehearsal patches
  `should_quarantine_task` to `threshold=1`, so it asserts that *one* signature
  is read and never that signatures accumulate across attempts. Accumulation was
  the broken half.
- **The record is hand-written.** `test_a_throttle_stops_spawning_and_requeues`
  built the `failure_signatures` entry its assertion needed, in a state the only
  writer of that field refused to produce. The test and the code it guarded
  described behaviour that could not occur, and both passed.

## Shape of the work

One unattended run, in a fixture that resembles a project, whose harness stub
always fails with a provider-limit envelope:

- shared posture: an in-tree config and a real (local, bare) origin
- real thresholds: no patched breaker, no patched triage defaults
- assertions on the outcome: the run stops spawning; attempts are bounded; the
  task's recorded state and cost are what the taxonomy says they should be
- a second variant whose stub fails deterministically for the task's own reasons,
  asserting quarantine at `PER_TASK_BREAKER_THRESHOLD` — the accumulation path
  the current rehearsal patches out

The existing `tests/orchestrator/test_nightshift_rehearsal.py` is the nearest
relative and the reason this needs planning rather than a patch: it is a
class-scoped single run whose fixtures and patches would have to change, and its
current shape is load-bearing for other assertions.

## Open questions for the plan

- Does the shared-posture variant replace the rehearsal's fixture or sit beside
  it? A second real batch run costs wall-clock in every `make validate`.
- What is the bounded-cost assertion measured against — attempt count, telemetry
  cost roll-up, or both?
- Does the same fixture cover the group-failure resume path (ADR-069), or does
  that stay a unit test?
