# Phase 5 Exit-Gate — Night-Shift Runtime Rehearsal

**Date:** 2026-07-17
**Scope:** `nsr-07-exit-gate-rehearsal` — Phase 5 exit-gate demonstration (roadmap P5 PRD G5; R-12, R-13), executed after nsr-03 (circuit breaker), nsr-04 (`--on-failure=triage`), nsr-05 (stall watchdog), and nsr-06 (per-task cost rollup) landed on `origin/main`.
**Question:** Does the unattended night-shift runner survive a mixed queue that contains one healthy task, one deterministic failure, and one stall — finishing without hanging, classifying the two incidents correctly, and recording per-task cost on the ledger?

**Verdict, up front:** all four claims hold after two small orchestrator fixes. (a) **PASS** — the healthy fixture reaches `awaiting_merge`. (b) **PASS** — the deterministic-failure fixture is quarantined by the per-task breaker after three identical signatures. (c) **PASS** — the stall fixture is killed by the watchdog and its final failure signature is classified `timeout`; it is left `failed` rather than requeued. (d) **PASS** — both incident tasks carry a `cost` object (`tokens` + `usd`) on the ledger. Two honest findings are recorded below.

## Method

- Code under test: the globally installed `aet` CLI symlinks to `/Users/pedrorocha/Sites/aiskills/aet-work/bin/aet`, which exercises the merged nsr-03 / nsr-04 / nsr-05 / nsr-06 code at `origin/main`.
- Rehearsal harness: `tests/test_nightshift_rehearsal.py` builds a scratch repo, a fake `claude` CLI, a three-task queue (healthy + deterministic-failure + stall), and invokes the batch orchestrator with `--on-failure=triage`, `--max-jobs=3`, `--stall-timeout=1`, and `--task-timeout=999`.
- The fake CLI emits a JSON usage envelope and then either fails deterministically, sleeps silently, or completes with a commit.
- Validation: `pytest tests/test_nightshift_rehearsal.py -v` and the full suite (`pytest -q`).

## (a) Healthy task completes — PASS (traces: R-12)

Assertion: `test_mixed_queue_finishes_unattended` checks that `nightshift-healthy.state == "awaiting_merge"`.

Observed transitions:

```text
▶️  Task: Healthy fixture (nightshift-healthy)
   Stage: plan-approved → implemented
   Invoking: claude ...
   [nightshift-healthy ...] healthy fixture
   ✅ Task complete: nightshift-healthy
   ✅ nightshift-healthy awaiting merge
```

The healthy task produced a commit and advanced to `awaiting_merge`; the batch did not hang waiting for the other tasks.

## (b) Deterministic failure is quarantined — PASS (traces: R-12)

Assertion: `test_deterministic_failure_quarantined_by_breaker` checks that `nightshift-deterministic-failure.state == "quarantined"`.

Observed transitions:

```text
▶️  Task: Deterministic failure fixture (nightshift-deterministic-failure)
   ❌ Stage failed with exit code 1
   ❌ Stage failed with exit code 1
   ❌ Stage failed with exit code 1
   🚫 nightshift-deterministic-failure quarantined (circuit breaker)
```

The fixture failed with the same tail/signature on every attempt; the per-task breaker tripped after the third countable signature and quarantined the task.

## (c) Stall is killed and classified as timeout — PASS (traces: R-12, R-13)

Assertion: `test_stall_killed_and_classified_timeout` checks that `nightshift-stall.state in {"quarantined", "failed"}` and that the last failure signature has `class == "timeout"`.

Observed transitions:

```text
▶️  Task: Stall fixture (nightshift-stall)
   Invoking: claude ...
   ❌ Stage failed with exit code -9
   ⏱️  nightshift-stall killed by timeout; leaving failed
```

The stall watchdog terminated the silent session after one second; the orchestrator classified the kill as `timeout` and left the task `failed` instead of requeueing it for another doomed attempt.

### Honest finding 1: stall kills were misclassified as `flaky`

`run_stage` and `run_stage_group` hardcoded `killed_by_timeout=False` when recording failure signatures. Because `_run_with_live_tee` already returns exit code `-9` for stall kills, the correct classification can be derived from `exit_code == -9`. Both helpers were updated to pass `killed_by_timeout=(exit_code == -9)`, so the ledger now records `timeout` for killed-silent sessions.

### Honest finding 2: timeout kills were requeued by the triage router

Even after the classification was fixed, the default `--on-failure=triage` path consulted the triage agent. The deterministic classifier default for `timeout` is `requeue`, so stall tasks were returned to `ready` and never reached a terminal state. `_finalize_task` now reads the latest failure-signature class and leaves the task `failed` when that class is `timeout`, matching the terminal semantics of a watchdog kill.

## (d) Both incidents carry per-task cost — PASS (traces: R-13)

Assertion: `test_both_incidents_costed_on_ledger` checks that both `nightshift-deterministic-failure` and `nightshift-stall` have a non-null `cost` with `tokens` and `usd` keys.

### Honest finding 3: cost was not persisted for failed tasks

`_finalize_task` rolled up cost only on the success path (`ret == 0`). Failed and quarantined tasks had no `cost` written to the ledger. Two changes fixed this:

1. `run_single` now rolls up and writes per-task cost for any queued task, success or failure, using the child process's own telemetry logger.
2. `_finalize_task` calls a shared `_write_task_cost` helper on both success and failure paths; because the helper only overwrites `cost` when telemetry is present, it does not clobber cost written by the child.

After the fixes, both incident tasks show `cost.tokens` and `cost.usd`.

## Test evidence

```text
$ pytest tests/test_nightshift_rehearsal.py -v
============================== 4 passed in 23.95s ==============================

$ pytest -q
835 passed, 1 skipped, 69 subtests passed in 155.37s
```

## Files changed

- `aet-work/bin/orchestrator` — classify stall kills as `timeout`; leave timeout-killed tasks `failed`; persist per-task cost for failed/quarantined tasks.
- `tests/test_nightshift_rehearsal.py` — end-to-end rehearsal harness; fake CLI flushes usage envelope so stalled sessions still record cost.
- `tests/fixtures/nightshift/{healthy,deterministic-failure,stall}.md` — fixture plans.
- `docs/audits/2026-07-17-nightshift-runtime-rehearsal.md` — this audit.

## R-trace

- **R-12** (exit-gate claims demonstrated): rehearsals (a), (b), (c).
- **R-13** (unattended runner telemetry and cost): rehearsals (c), (d).
