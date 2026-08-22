# An idle run holds the lease forever instead of exiting

**Date:** 2026-08-22
**Status:** fixed
**Source:** `content/bugs/open-items.md` item 1 (E40 incident)

## Symptom

From the E40 incident: two orchestrator parents sat alive for **8+ hours with
zero worker processes**. One was deadlocked on the lease; the other was idle
because every remaining task was `in_progress` / `failed` / `awaiting_merge`
and nothing was dispatchable. The idle one held the lease the whole time.

The lease-seizure half was fixed earlier (`acquire_lease` refuses at startup).
This is the idle-exit half.

## Correcting the original report

The open-items entry said `grep` finds no "nothing to dispatch" exit condition
in `src/aet/cli/orchestrator.py`. One does exist — added by frh-16, at what is
now `orchestrator.py:3293`:

```python
if not running:
    if stop_spawn or _shutdown_requested:
        break
    if has_actionable_tasks(queue):
        time.sleep(0.2)
        continue
    leftover_report.update(leftover_counts(queue))
    break
```

The exit condition is present. It simply never fires for this case.

## Reproduction

`TestBatchLivePickupAndExit::test_batch_exits_when_only_orphaned_in_progress_remains`
seeds a queue with one task stored `in_progress` and runs `run_batch` with a
10s watchdog. Before the fix the run never returns and the watchdog trips.

## Root cause

`has_actionable_tasks` tested stored state alone:

```python
_BATCH_ACTIONABLE_STATES = frozenset({"ready", "in_progress"})

def has_actionable_tasks(queue):
    return any(current_state(task) in _BATCH_ACTIONABLE_STATES for task in queue)
```

Its only call site sits behind `if not running:`, so `running` is empty by
construction. A task left `in_progress` by a dead run therefore keeps the
predicate `True` forever, while `get_next_ready_task` returns nothing because
the task is not `ready`. The loop sleeps 200ms and retries — indefinitely, at
five iterations a second, holding the lease.

`in_progress` means "a worker is advancing this" only when a worker actually
is. Stored state cannot distinguish a live worker from a dead one; ownership
can.

A second, quieter gap: `in_progress` was absent from `_BATCH_LEFTOVER_STATES`,
so even once the loop broke, the leftover report omitted the stranded task —
the very reason the run had nothing to do.

## Fix

1. `has_actionable_tasks(queue, owned_ids)` — `ready` is always actionable; an
   `in_progress` task is actionable only when this run owns a live worker for
   it. The call site passes `running.keys()`.
2. `in_progress` added to `_BATCH_LEFTOVER_STATES` / `_BATCH_LEFTOVER_LABELS`,
   labelled "orphaned in progress" and ordered first, so the exit report names
   it.

Files: `src/aet/cli/orchestrator.py`, `tests/orchestrator/test_orchestrator.py`.

## Validation

`tests/orchestrator/` — 255 passed, 1 failed. The single failure is
`TestWireTestRunEmission::test_orchestrated_claude_stage_writes_observed_test_run`,
a pre-existing flake, confirmed independent of this change by two controlled
runs: the change applied to the baseline test file passes 11/11, and the test
fails at ~1-in-5 at the clean baseline commit with no change applied.

Note for that flake's own investigation: it does not only fail on the
non-null duration assertion. It also fails as `session_ref is None`.
