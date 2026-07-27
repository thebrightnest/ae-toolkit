---
id: rid-05-adapter-supervision-defaults
size: M
work_class: critical
blocked_by: []
pipeline: standard
status: approved
security_review: required
security_review_reason: Changes the watchdog kill path and per-provider process supervision.
docs_sync: required
docs_sync_reason: Implements ADR-053 and changes a documented ADR-031 default.
---

# Plan: Per-Adapter Supervision Defaults

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-6, R-7, R-8, R-8b).
ADR-053 (accepted) records the decision; ADR-031 item 2 is superseded and already annotated.

The watchdog's 300-second stall default (`orchestrator.py:787`, ADR-031 item 2) kills a
healthy run during a full pytest suite. The value is adapter-specific — it is a property of
how often a given agent CLI emits output — so it belongs on `CLIAdapter`
(`cli_adapter.py:17-33`), not in config and not on the command line.

**R-6 is a non-change requirement.** `_run_with_live_tee` echoes each line to stdout and
keeps a bounded tail (`orchestrator.py:848-851`). In detached mode the orchestrator's stdout
*is* `output.log` (`main.py:265-274`), so that echo writes the log; and claude's usage is
parsed from the tail, whereas kimi's is read post-exit from session wire files. Silencing the
tee would empty the log and break claude's token capture while leaving kimi's intact — a
provider-asymmetric regression easily misattributed to `tap-07`. Do not "optimize" the tee.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add `stall_timeout` and `wall_backstop` fields to the `CLIAdapter` frozen dataclass and
   populate them for the `kimi` and `claude` entries; `build_cmd` is untouched — S
   (traces: R-7)
2. Resolve the watchdog's stall interval from the active adapter in `orchestrator.py`,
   replacing the `stall_timeout: float = 300` parameter default on the spawn helpers — M
   (traces: R-7)
3. Set the per-adapter stall defaults above the observed silent interval of a full suite run,
   and the wall backstop well above the stall interval, per ADR-053 — S (traces: R-8)
4. Add a regression test asserting `output.log` is non-empty and complete for a detached run,
   and that usage resolves non-null for the `json-envelope` and `wire-file` adapters — one
   test per adapter — M (traces: R-6)
5. Verify ADR-053 matches what shipped and that ADR-031's supersession annotation is accurate;
   correct either if implementation diverged — S (traces: R-8b)
6. Merge branch to main and verify integration — S

## Validation

- A full QA-stage pytest run completes without a `timeout`-classified kill.
- `grep -n "= 300" src/aet/cli/orchestrator.py` shows no remaining stall default.
- A detached run's `output.log` is non-empty and ends with the orchestrator's final output.
- Usage records carry non-null token fields for both adapters after the change.
- Named tests: `tests/cli/test_cli_adapter.py` (adapter fields present per provider),
  `tests/orchestrator/` (watchdog resolves the interval from the adapter),
  `tests/usage/` (non-null usage per adapter), `tests/wirelog/` (kimi wire-file path intact).

---

*Stage: plan-approved*
*Next step: run `aet-work`*
