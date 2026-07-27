---
id: rid-04-bounded-completion-report
size: M
work_class: normal
blocked_by:
  - rid-03-non-streaming-follower
pipeline: standard
status: approved
security_review: required
security_review_reason: Renders excerpts of agent output, which may contain secrets or injected content.
docs_sync: required
docs_sync_reason: Defines new user-visible output for every run.
---

# Plan: Bounded Completion Report

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-3, R-4, R-12).
Glossary: **Bounded Report** in CONTEXT.md.

rid-03 makes the follower silent. This plan gives it something to say. The report must have a
length that does not scale with the volume of run output — that property is the entire point,
and it is what makes a run's context cost predictable.

Because the excerpt renders raw agent output, it is a trust boundary: content is displayed,
never interpreted as instructions.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Define the report structure — per-stage status, duration, and exit code, plus an overall
   result line — sourced from existing stage telemetry rather than by parsing `output.log` — M
   (traces: R-3)
2. Emit the report from the follower on completion for `run-one` and `aet run --follow` — S
   (traces: R-3)
3. On failure, append a bounded excerpt of the failing stage capped at a fixed line count, with
   the excerpt clearly delimited as displayed output — M (traces: R-4)
4. Update the `aet run` start message to print the `output.log` path and to describe
   `--follow` as waiting for a report, never as tailing or streaming (`main.py:277-279`) — S
   (traces: R-12)
5. Add tests: report line count is identical for runs whose logs differ by orders of magnitude;
   a failing run's excerpt is capped at the configured limit; the start message names the log
   path and does not describe streaming — M (traces: R-3, R-4, R-12)
6. Merge branch to main and verify integration — S

## Validation

- Two successful runs whose `output.log` sizes differ by more than 100× produce reports of
  the same line count.
- A run failing in QA reports the failing stage and an excerpt no longer than the cap.
- `aet run` start output contains the log path and the word "report", not "tail" or "stream".
- Named tests: `tests/test_orchestrator_daemonize.py` (report shape and boundedness, failure
  excerpt cap), `tests/test_aet_run_dispatch.py` (start message content).

---

*Stage: plan-approved*
*Next step: run `aet-work`*
