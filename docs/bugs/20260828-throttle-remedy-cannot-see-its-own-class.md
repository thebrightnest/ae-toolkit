# Bug Report: the `throttled` remedy reads the class from a record the class is excluded from, so the run never stops

## Metadata

- **Reported:** 2026-08-28
- **Severity:** high (ADR-065's decision 3 has no effect)
- **Status:** fixed 2026-08-28

## Symptoms

A session that ends against a provider limit is requeued into the same closed
window instead of stopping the run, even when the classifier gets the class
right. No `⏸️ … hit a provider limit` line appears in any log; the run reports:

```
   ⚠️  Triage for <task> failed closed; using requeue (environment)
   🔄 <task> requeued
```

## Reproduction Steps

```python
fc = classify(exit_code=1, tail="API error: status: 429 rate limit exceeded", ...)
# -> FailureClass.THROTTLED
sig = _record_failure_on_task(backend, task, fc, "plan-approved", tail)
# -> None; entries on record: 0
_finalize_task(backend, queue_file, task_id, 1, on_failure="triage", ...)
```

Observed:

```
classified as: throttled
signature returned: None
entries on record: 0
   ⚠️  Triage for t1 failed closed; using requeue (environment)
   🔄 t1 requeued
deltas: {'successes': 0, 'failures': 0, 'stop_spawn': False}
```

`stop_spawn` is `False`. The remedy ADR-065 specifies — stop the run, name the
reset — never fires, for a tail the current patterns classify correctly.

## Root Cause

Two ADR-065 decisions are each implemented correctly and are incompatible.

Decision 2, "a throttle is not breaker evidence":
`append_failure_if_countable` (`breaker.py:34-61`) refuses to append a
`throttled` signature, so `_record_failure_on_task` returns `None` and the task
record gains no entry.

Decision 3, "the run stops and the task is requeued": `_finalize_task` detects
the class by reading the record that decision 2 just declined to write
(`orchestrator.py:2922-2923`):

```python
throttled = failure_lib.FailureClass.THROTTLED.value
if ((task.get("failure_signatures") or [{}])[-1].get("class") if task else None) == throttled:
```

For a throttled failure the list is empty, or — worse — still holds an unrelated
earlier entry, in which case the class read belongs to a different failure.
Either way the branch is unreachable for the class it exists to catch, and
execution falls through to the triage path, where the same empty list defaults
`failure_class_name` to `environment` (`orchestrator.py:2947`) and the
deterministic default for `environment` is `requeue`.

The classification is not the problem here: the class was correct and was thrown
away. `_record_failure_on_task` returns the signature or `None` and its return
value is discarded at both call sites (`orchestrator.py:1460`, `1594`), so the
class the classifier computed does not survive the call in any form the finalize
path can read.

## Consequences

ADR-065's central claim — "A shift that meets a provider limit costs one attempt
and stops" — does not hold. A correctly classified throttle costs the same
unbounded requeue loop as a misclassified one, and because throttles are
deliberately not breaker evidence, the breaker cannot bound it either. The two
mechanisms that should stop the run are mutually exclusive by construction.

This also changes what the throttle-pattern widening buys. Widening the patterns
converts a `flaky` misclassification into a `throttled` correct classification,
and on today's code that makes the outcome *worse*: `flaky` is at least
countable, so with the ref-overwrite defect fixed the breaker would stop the loop
at three attempts, while `throttled` is not countable and would loop unbounded.
This defect must land with, or before, the pattern fix.

## Fix

A throttled failure is now recorded, carrying `countable: False`
(`breaker.py:34-75`). Both ADR-065 decisions survive: the class is observable
where every other class is observable, and the breaker still does not count it.

- `should_quarantine_task` skips non-countable entries (`breaker.py:80-96`), so
  three throttles still never quarantine — the guarantee decision 2 exists for.
- The systemic tally skips them too (`orchestrator.py:3236-3241`); otherwise
  three throttled tasks would trip the shift-level breaker and persist a
  poisoned signature to `refs/aet/breaker` for a cause that is not a signature.
- `_record_failure_on_task` enriches whichever entry was appended rather than
  returning early on a non-countable class (`orchestrator.py:2530-2545`), so the
  entry carries `class`, `stage`, and the tail preview that triage reads.

`canceled` is unchanged: it is still not recorded at all. Nothing reads it back,
and an operator stopping a shift is not evidence about anything.

`_TRIAGE_DEFAULT_ACTIONS[THROTTLED]` stays `"requeue"`: it is reached only if the
stop above did not fire, and requeueing a task that did nothing wrong is the
right fallback.

## Why The Tests Miss It

`tests/failure/test_throttled_stops_the_run.py` does assert the outcome —
`test_a_throttle_stops_spawning_and_requeues` checks `stop_spawn is True` — but
its fixture hand-writes the record it needs (`:87-97`):

```python
"failure_signatures": [
    {"signature": "s", "class": failure_class, "stage": "implement"}
],
```

A record in that state is unreachable in production: the only writer,
`_record_failure_on_task`, refuses to append a `throttled` entry. The test proves
the branch works given an input the system cannot produce, and the sibling test
`test_a_throttled_failure_is_not_breaker_evidence` pins the refusal that makes it
unproducible. Both pass, and together they describe behaviour that cannot occur.

The regression test has to start from a failing session, not from a record: drive
`_record_failure_on_task` with a throttled classification and assert that
`_finalize_task` then returns `stop_spawn: True`.
