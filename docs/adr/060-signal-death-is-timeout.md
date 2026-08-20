---
subject: timeout-classification
---

# Signal-Death Sessions Are Classified as Timeout

## Status

Accepted (2026-08-20). Extends ADR-053 (Supervision Defaults Live on the CLI
Adapter). Implements requirement R-8 of the
`orchestrator-signal-exit-determinism` PRD.

## Context

In batch mode, a task session can be killed by at least two independent layers:

1. The child orchestrator's own stdout-silence watchdog (`_run_with_live_tee`),
   which records a `timeout` failure signature before exiting.
2. The batch parent's per-task wall-clock backstop (`--task-timeout`), which
   kills the *child orchestrator process* and finalises the task with `ret=-9`.

When the parent backstop fires first, the child dies before it can record a
signature. The parent therefore saw a signal-killed child (`ret=-9`) with no
`timeout` signature, treated the failure as transient, and requeued the task to
`ready`. The operator-visible result was the same wall-clock kill producing both
`failed` and `ready` outcomes depending on which layer won the race.

Three candidate mechanisms were investigated and ruled out in the osd-01 plan:
process-group terminate racing the child's own exit; tee threads reaching EOF
before `proc.wait()`; and a second signature recorded from a different call
site. The confirmed trigger is the race between the two timeout layers.

## Decision

1. **Any signal-killed session is classified as `timeout`.** A negative exit
   code means the process died by signal. Both `failure.classify` (via
   `killed_by_timeout`) and `_finalize_task` treat a negative exit code as
   authoritative evidence of timeout, regardless of which signal was delivered
   or whether the child orchestrator recorded a signature first.

2. **The batch parent is the backstop for signature recording.** If a signal-
   killed session reaches `_finalize_task` and the latest failure signature is
   not already `timeout`, the parent appends exactly one `timeout` signature
   before leaving the task failed. This closes the race where the child is
   killed before it can write the signature.

3. **`timeout` is not restricted to the stall watchdog.** The stall watchdog
   remains the primary, preferred source of timeout detection because it records
   the signature inside the dying child. The wall-clock backstop and any other
   signal death are secondary sources that produce the same classification.

## Consequences

- A task killed by the wall-clock backstop is deterministic: it always ends
  `failed` with a `timeout` signature, never `ready`.
- The per-task circuit breaker and systemic breaker now see a consistent
  `timeout` signature for signal deaths, so repeated timeout patterns can still
  trip the breaker.
- The `Stall Timeout` definition in `CONTEXT.md` is widened to cover any signal
  death, not only the watchdog's kill.
- The night-shift rehearsal's stall fixture continues to exercise the same path
  (a self-SIGKILL that the child classifies as timeout), but its documentation
  no longer claims the fixture "produces a timeout-classified exit (-9) without
  waiting for the real stall watchdog" as if -9 were special.

## Alternatives Considered

1. **Make the stall watchdog the only source of `timeout`.** Rejected. It would
   require removing the existing `killed_by_timeout=exit_code < 0` classification
   in the child orchestrator, changing production behaviour for every signal-
   killed session and throwing away the signal information the exit code already
   carries.

2. **Record the `timeout` signature from the child even when killed by the
   parent.** Rejected. `SIGKILL` cannot be caught or handled, so the child cannot
   guarantee it records anything after the parent backstop fires.

3. **Widen the rehearsal assertion to accept `ready`.** Rejected. It would
   encode the race as expected behaviour rather than fixing it.
