---
id: ppt-04-stage-telemetry-schema
size: M
status: approved
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: changes telemetry schema and orchestrator emission code
docs_sync: required
docs_sync_reason: PRD footer must reflect telemetry schema changes
---

# Plan: Stage Telemetry Schema v2

## Context

Upgrade stage telemetry records so they capture the actual stage(s) that ran, failure classification, plan frontmatter snapshot, and attempt counter. This removes the need to reverse-engineer the workflow when analyzing telemetry and enables richer self-evolution metrics.

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Extend `src/aet/telemetry.py` `stage_record` to include `actual_stages` (list of stage names run), `failure_class` (nsr-01 taxonomy), `plan_snapshot` (shallow copy of `size`, `pipeline`, `security_review`, `docs_sync`, `aet_version`), and `attempt` (int, default 1). — M (traces: R-6)
2. Update `src/aet/cli/orchestrator.py` `_emit_stage_session` to populate the new fields: compute `actual_stages` from the target stage and span, read plan frontmatter for `plan_snapshot`, and pass `attempt`. — M (traces: R-6)
3. Add `attempt` tracking: orchestrator increments attempt per task+stage+run; existing records default to 1. — S (traces: R-6)
4. Update `src/aet/metrics.py` and any consumers to prefer `actual_stages` when present and fall back to the legacy reverse-lookup. — S (traces: R-6)
5. Add unit tests for the new schema fields. — M (traces: R-6)

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

## Rejected Alternatives

- **Rename the existing `stage` field** — rejected: breaks existing telemetry consumers and historical archives. Adding a new field preserves backward compatibility.

## Files to Modify

- `src/aet/telemetry.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/metrics.py`
- `tests/test_telemetry.py` (or equivalent)

## Validation Steps

- [ ] `make test` passes
- [ ] `make validate` passes
- [ ] New records include all four new fields
- [ ] Existing records still parse without errors

## Rollback Plan

Revert the telemetry and orchestrator changes; old records remain valid.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and
dependency changes should usually use `standard` or `full`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
