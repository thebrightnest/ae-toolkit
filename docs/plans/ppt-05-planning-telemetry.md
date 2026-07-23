---
id: ppt-05-planning-telemetry
size: M
status: queued
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: changes skill instructions to emit telemetry; no runtime code paths
docs_sync: required
docs_sync_reason: PRD footer must reflect planning telemetry changes
---

# Plan: Planning-Phase Telemetry

## Context

Capture planning-phase sessions (`aet-plan`, `aet-validate-scope`) in telemetry so the toolkit can measure planning cost against implementation cost and evaluate whether planning is the core value. See PRD: docs/prds/pipeline-performance-telemetry-prd.md

## Intake Triage

- [ ] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Design a `planning` telemetry record schema (session id, start/end, duration, tokens, cost, skill, outcome, plan/PRD path, `aet_version`). — M (traces: R-7)
2. Add a helper in `src/aet/telemetry.py` to write planning records to `.agents/telemetry/planning/{date}/{session-id}.json`. — M (traces: R-7)
3. Update `skills/aet-plan/SKILL.md` and `skills/aet-validate-scope/SKILL.md` to emit a planning record at session end (duration, tokens if measurable, outcome). — M (traces: R-7)
4. Add unit tests for the planning record writer. — S (traces: R-7)
5. Update `docs/telemetry-guide.md` to document the new record type and location. — S (traces: R-7)

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 100 expected diff lines
- **M**: ≤ 1 day human time / ≤ 200 expected diff lines
- **L**: > 1 day OR > 200 lines — re-evaluate against the full guardrail model; split only if a limit is actually exceeded

## Rejected Alternatives

- **Capture planning telemetry inside the orchestrator** — rejected: planning happens before the orchestrator runs and may be interactive; the orchestrator has no visibility into it.
- **Reuse stage record schema** — rejected: planning is not a pipeline stage; a separate record type keeps the schema honest.

## Files to Modify

- `src/aet/telemetry.py`
- `skills/aet-plan/SKILL.md`
- `skills/aet-validate-scope/SKILL.md`
- `docs/telemetry-guide.md`
- `tests/test_telemetry.py` (or equivalent)

## Validation Steps

- [ ] `make test` passes
- [ ] `make validate` passes
- [ ] A test run of `aet-plan` produces a planning record
- [ ] Records are written to `.agents/telemetry/planning/`

## Rollback Plan

Revert the telemetry helper and skill-text changes; remove the new record directory.

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
