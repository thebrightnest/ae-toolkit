---
subject: throttle-remedy
amends: [65]
---

# A Failure Whose Remedy Reads the Record Is Recorded, Even When It Does Not Count

## Status

Accepted (2026-08-28). Amends ADR-065 (Throttling Is Not a Flake), whose
decisions 2 and 3 are individually correct and jointly unreachable. Motivated by
`docs/bugs/20260828-throttle-remedy-cannot-see-its-own-class.md`.

## Context

ADR-065 decision 2 keeps a `throttled` signature out of the task record, on the
grounds that three attempts against a closed provider window say nothing about
the task. Decision 3 stops the run on a throttle, and detects the class by
reading it off that same record. Both landed. Decision 2 removed the evidence
decision 3 depends on, so the stop was unreachable for every input: a correctly
classified throttle recorded nothing, read back as the `environment` default,
and requeued.

ADR-065's Consequences state that the 185-attempt outcome "is no longer
reachable — signatures normalise timestamps, hex and paths, and the per-task
breaker quarantines at three." On 2026-08-27 a task requeued 22 times against one
closed window at a recorded $23.77, carrying one signature entry. The breaker
never counted, for a second and independent reason
(`docs/bugs/20260828-fetch-discards-unpushed-record-writes.md`), and the throttle
stop never fired, for this one.

## Decision

**Exclusion from breaker counting is a flag on a recorded entry, not the absence
of an entry.**

1. A `throttled` failure is recorded, carrying `countable: false`.
2. `should_quarantine_task` and the shift-level systemic tally skip
   non-countable entries. ADR-065 decision 2 stands: three throttles still never
   quarantine, and a throttle never contributes a signature to
   `refs/aet/breaker`.
3. ADR-065 decision 3 stands and now functions: the class is on the record where
   the finalize path reads it, so a throttle stops the run and names the remedy.
4. `canceled` remains unrecorded. No remedy reads it back, and an operator
   stopping a shift is not evidence about the work.

## Consequences

- The class is observable where every other class is observable, which is what
  ADR-065's own Consequences section promised.
- **The general rule this cost:** two decisions about the same field, each
  correct alone, can cancel. A class whose remedy reads the record must be
  written to the record; whether it *counts* is a property of the entry.
- ADR-065's "no longer reachable" claim is withdrawn. The mechanisms it cites
  are real but were both disabled — one by this defect, one by a ref-fetch
  overwriting local writes.
