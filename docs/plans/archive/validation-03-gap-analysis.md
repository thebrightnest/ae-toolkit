---
id: validation-03-gap-analysis
size: S
work_class: normal
blocked_by:
  - validation-01-stage-based-split
pipeline: minimal
security_review: skipped
security_review_reason: No auth, data-model, or trust-boundary changes; records metadata only
docs_sync: required
docs_sync_reason: Documents gap analysis in failure records
---

# Plan: Validation Gap Analysis on QA Failure

## Context

PRD: `docs/prds/orchestrator-liveness-and-validation-redesign-prd.md`

When `aet-qa` fails on a test that `aet-implement` should have caught, the failure record must include gap analysis: which test was missed and why it was not run during implementation. This helps operators understand whether the agent's test selection was wrong or the change had unexpected side effects.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Record the set of tests run during `aet-implement` in the stage telemetry — S (traces: R-8)
2. On `aet-qa` failure, compare failed tests against the implement-stage test set — S (traces: R-8)
3. Record the gap analysis (missed test names, reason not run) in the task's failure record — S (traces: R-8)
4. Add regression tests for gap analysis recording — S (traces: R-8)
5. Update `docs/PIPELINE.md` with gap analysis format — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines; see `docs/CONVENTIONS.md`).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against (`blocked_by` that sibling, or blocked by it transitively).
- [ ] This is docs-only and its sole consumer is a single sibling.

Justification: This is a small additive feature on top of validation-01. It records metadata; it does not change validation behavior.

## Rejected Alternatives

- **Structured JSON rationale from agent** — rejected: free text in output is sufficient for the first iteration; structured data can be added later if needed.
- **Gap analysis at implement time** — rejected: the gap is only knowable when QA fails.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/telemetry.py`
- `tests/orchestrator/test_orchestrator.py`
- `docs/PIPELINE.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] For each new source file introduced by this plan, name the test that will cover it
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Gap analysis is additive; removing it falls back to plain failure records.

## Pipeline

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
