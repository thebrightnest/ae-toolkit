# `main` cannot gate a merge — eight failing tests at `4db046d3`

**Date:** 2026-08-22
**Status:** fixed
**Source:** `content/bugs/open-items.md` item 7

## Symptom

A clean checkout of `main` fails its own test suite, so no change can be
attributed to its author: every investigation needs a measured baseline before
a failure means anything. Measured 8 failed / 1852 passed at `6b6b1f62`, and
the same set still fails at `4db046d3`.

## Reproduction

```
git worktree add --detach <dir> 4db046d3
.venv/bin/python -m pytest tests/orchestrator/test_orchestrator.py \
    tests/orchestrator/test_single_pr_rehearsal.py \
    tests/ship/test_aet_ship.py tests/gate/test_gate_evidence.py \
    -p no:randomly -q
```

All eight fail deterministically, in isolation and under load. The
"flaky under full-suite load" note in the open-items list applied only to
`TestWireTestRunEmission`, which is a separate, still-open issue.

## Root cause

No production defect. All eight tests encode contracts that later ADRs and
design decisions superseded; the code under test behaves correctly.

### Cause 1 — test-double drift (3 failures)

`_run_with_live_tee` grew a liveness monitor that reads `proc.pid`
(`src/aet/cli/orchestrator.py:1225`) and a watchdog thread that calls
`proc.poll()`. Two independent `_StubPopen` doubles — one in
`tests/orchestrator/test_orchestrator.py`, one local to a test in
`tests/gate/test_gate_evidence.py` — expose only `stdout` and `wait()`, so
constructing the monitor raises `AttributeError`.

The sibling stub `_InstantProc`, twelve lines below the first, already carries
both attributes. The doubles were simply never updated alongside it.

Affected: `TestRunStageGroup` ×2, `TestGroupSessionEnvVars` ×1.

### Cause 2 — ADR-064 merge evidence (2 failures)

ADR-064 decision 3 forbids `resolve_merge_commit` from reporting a commit the
task did not author, and decision 4 fails closed when `base_commit` is absent.

- `test_record_merge_succeeds_after_run_one` stubs out `process_task`, so its
  branch authors zero commits and its tip equals its `base_commit`. The test
  then asserts the task seals as `merged` — **the exact defect ADR-064 was
  written to eliminate**. Probing `run_single` directly confirmed it records
  `base_commit` correctly (`orchestrator.py:3397`); the fixture, not the
  production path, was wrong.
- `test_record_merge_records_delivered_size` seeds a queue fixture with a
  `branch` but no `base_commit`. All three resolution paths then close:
  ancestry fails closed, `gh` is absent, and the diff fallback returns
  `ambiguous` because a fully merged branch has an empty diff against its own
  merge-base. ADR-064's Consequences section names this case.

### Cause 3 — shadow posture suppresses the history write (3 failures)

`resolve_posture` (`src/aet/backends/factory.py:147`) returns `shared` only
when an in-tree project-scope config is the *effective* config source. Test
fixtures that create a bare temp repo get `shadow`, and shadow posture
deliberately skips `append_history_record` (`git_refs_backend.py:534`) — the
call that also stamps `delivered_size` (`queue.py:604`). Three tests assert on
a `work-history.jsonl` the seal was never going to write.

`test_single_pr_rehearsal` is the interesting one: it writes its config to the
**user** scope, and config resolution is external-first, so no in-tree file can
make `project` the effective source. Shared posture and the shadow-layer config
that rehearsal exists to exercise are mutually exclusive by design. In shadow
posture the durable settled record is the `refs/aet/sealed/<id>` tombstone
blob, not a working-tree file.

## Fix

Test-side only; no production code changed.

| File | Change |
| --- | --- |
| `tests/orchestrator/test_orchestrator.py` | `_StubPopen` gains `pid`/`poll()`; `_use_shared_posture` helper; branch authors a real commit; fixture records `base_commit` |
| `tests/gate/test_gate_evidence.py` | Local `_StubPopen` gains `pid`/`poll()` |
| `tests/ship/test_aet_ship.py` | `TestShipClosure` opts into shared posture |
| `tests/orchestrator/test_single_pr_rehearsal.py` | `_settled_tasks` reads sealed tombstone refs instead of `work-history.jsonl` |

Shared posture is opt-in per test rather than folded into `_init_git_repo`: a
first attempt at the latter turned 5 failures into 9, because
`TestEnforceBaseHygiene` reads the untracked config as a dirty tree and
`TestDeferredDurabilityNotice` asserts shadow-posture messaging.

## Validation

Full suite green (see commit). Targeted files verified individually:
`tests/gate` 21 passed, `tests/ship` 41 passed,
`tests/orchestrator/test_single_pr_rehearsal.py` 6 passed.

## Still open

- `TestWireTestRunEmission::test_orchestrated_claude_stage_writes_observed_test_run`
  remains flaky under full-suite load — it spawns a real subprocess and asserts
  a non-null duration. Not addressed here.
- **New finding, unfixed:** `resolve_task_record` (`src/aet/cli/aet_state.py:85`)
  looks for sealed records only in `work-history.jsonl`. In shadow posture that
  file is never written, so `record-merge`'s idempotency-on-settled-task path
  (R-4) cannot find the record and reports "Task not found". The durable record
  in shadow posture is the `refs/aet/sealed/<id>` tombstone, which the function
  never consults. Deserves its own entry.
