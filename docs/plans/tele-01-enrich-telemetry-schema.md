---
id: tele-01-enrich-telemetry-schema
size: M
blocked_by: []
---

# Plan: Enrich Telemetry Schema for Loops, Environment Issues & Test Runs

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`

The current telemetry log only records stage and run-summary events. To learn from runs like the one that took ~25 minutes, we need granular records for internal loops (test retries, format fixes), environment/dependency issues, and individual test invocations. This plan adds those record types and wires them into the orchestrator.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Add record builders to `aet-work/lib/telemetry.py` — M
   - `loop_record`
   - `environment_issue_record`
   - `test_run_record`
   - `learning_candidate_record`
2. Update `aet-work/references/telemetry-log-schema.md` with the new record types — S
3. Update `aet-work/bin/report` to print loop and environment-issue counts — S
4. Emit `environment_issue` from `aet-work/bin/orchestrator` when dependency warmup is required — S
5. Run `make validate` and exercise `aet-work report` — S

## Files to Modify

- `aet-work/lib/telemetry.py`
- `aet-work/references/telemetry-log-schema.md`
- `aet-work/bin/report`
- `aet-work/bin/orchestrator`

## Validation Steps

- [ ] `make lint` and `make format-check` pass.
- [ ] `make validate` passes.
- [ ] `python3 aet-work/bin/report` on a sample log shows the new counts.
- [ ] Each new source file (none introduced) or changed file has its behavior covered by existing validation.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the telemetry library and reference doc changes; the orchestrator can still run with the original stage/run_summary records.

---

_Stage: reviewed_
