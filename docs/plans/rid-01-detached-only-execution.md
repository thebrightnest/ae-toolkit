---
id: rid-01-detached-only-execution
size: M
work_class: normal
blocked_by: []
pipeline: standard
status: queued
security_review: required
security_review_reason: Changes process spawning and removes an execution path in the CLI dispatcher.
docs_sync: required
docs_sync_reason: Removes a documented flag that live command docs reference.
---

# Plan: Detached-Only Execution and Tuning-Flag Removal

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-1, R-9).
Decision context: ADR-053 (supervision defaults per adapter), ADR-031 (item 2 superseded),
ADR-030 (triage routing retained). This reverses `docs/plans/nc-06-run-daemonization.md`
task 4, which added `--foreground` as a debugging affordance.

`aet run` / `aet run-one` currently offer two execution modes. `--foreground` execs the
orchestrator as the invoking session's own process (`main.py:246-252, 303, 333`), where
`_run_with_live_tee` mirrors every line to stdout — a full firehose into an agent's context.
Detached is already the default; this plan removes the alternative, and removes the three
tuning flags that have no correct call-time value.

`--base`, `--on-failure`, `--task-timeout`, and `--cli-bin` are **retained** as semantic
per-run inputs and must keep working.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Remove the `--foreground` option from `run` and `run-one` in `src/aet/cli/main.py`, delete
   the `_exec_orchestrator` helper and its `os.execvp` path, and make both commands always
   route through `_spawn_detached` — S (traces: R-1)
2. Remove `--max-jobs`, `--isolation`, and `--stall-timeout` from both command signatures and
   from `_build_orchestrator_flags`; keep `--base`, `--on-failure`, `--task-timeout`, and
   `--cli-bin` forwarding unchanged — S (traces: R-9)
3. Supply the orchestrator's `--max-jobs` and `--isolation` values internally from their
   current defaults (4, `standard`) so orchestrator behavior is unchanged when the flags stop
   being caller-supplied — S (traces: R-9)
4. Update `tests/cli/test_aet_dispatcher.py`, `tests/test_aet_run_dispatch.py`, and
   `tests/test_orchestrator_daemonize.py`: delete the `--foreground` routing and behavioral-
   equivalence cases, and assert the three removed flags are rejected as unknown options while
   the four retained flags still forward — M (traces: R-1, R-9)
5. Merge branch to main and verify integration — S

## Validation

- `aet run --foreground` and `aet run-one --foreground <plan>` exit non-zero with an unknown-
  option error.
- `grep -rn "_exec_orchestrator\|--foreground" src/` returns no hits.
- `aet run --max-jobs 2`, `--isolation full`, and `--stall-timeout 60` are each rejected.
- `aet run --base feat/x --on-failure halt --task-timeout 900 --cli-bin /bin/kimi` is accepted
  and forwards all four to the orchestrator argv.
- Named tests: `tests/cli/test_aet_dispatcher.py` (retained-flag forwarding, removed-flag
  rejection), `tests/test_aet_run_dispatch.py` (both commands route to detached spawn with no
  exec path), `tests/test_orchestrator_daemonize.py` (detached spawn returns promptly).

---

*Stage: implemented*
*Next step: run `aet-qa`*
