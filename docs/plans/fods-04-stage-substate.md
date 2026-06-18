---
id: fods-04-stage-substate
blocked_by:
  - fods-03-read-path-zero-git
size: M
---

# Plan: Pipeline Stage as `in_progress` Sub-State; Footer Becomes a Breadcrumb

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream B, criteria 6–7)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decision 6)

Today the orchestrator reads the plan footer `*Stage:*` (`verifier.read_plan_stage`) to decide the current pipeline stage — a second state machine in parallel with the queue. This plan records the stage as a **sub-state of `in_progress` in the task record**; the orchestrator reads and writes `task["stage"]`. The footer `*Stage:*` is still **written** from the record as a human breadcrumb, but is **never read** to make a scheduling decision.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Record `stage` in the task record** — S (`aet-work/bin/aet-state`)

   Add `set-stage <task_id> <stage>`: writes `task["stage"]` and appends a history entry (`by="orch"`), valid only when `state == "in_progress"`. `stage` lives only in the task record, never in plan frontmatter.

2. **Orchestrator drives stage from the record** — M (`aet-work/bin/orchestrator`)

   In `process_task`, determine the current stage from `task["stage"]` (not `read_plan_stage`); after each stage advances, call `set-stage`. Stage skills may still write the footer breadcrumb, but the orchestrator no longer reads it for control flow.

3. **Stop reading the footer for scheduling** — S (`aet-work/lib/verifier.py`)

   `verify_stage_advancement` verifies commits + the **recorded** stage rather than the footer string. Document that `read_plan_stage` is no longer a scheduling input (kept only for the advisory breadcrumb comparison).

4. **Tests** — M (`tests/test_pipeline.py`, `tests/test_orchestrator_derived.py`)

   - `test_stage_read_from_record_not_footer`
   - `test_set_stage_appends_history_and_requires_in_progress`
   - `test_footer_divergence_does_not_change_scheduling`

5. **Merge branch to main and verify integration** — S

## Blocked by

- fods-03-read-path-zero-git

## Validation Steps

- [ ] Orchestrator determines current stage from `task["stage"]`, not the plan footer.
- [ ] `aet-state set-stage` rejects when `state != in_progress` and appends history.
- [ ] A plan whose footer disagrees with the record does not change which stage runs.
- [ ] Named tests above pass.
- [ ] `make validate` passes.

## Rollback Plan

Revert `aet-state set-stage`, the orchestrator stage source, and `verifier.py`. The footer-reading path still exists as a fallback.

---

_Stage: implemented_
_Next step: run `aet-qa`_
