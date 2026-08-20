---
id: validation-01-stage-based-split
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Changes validation workflow and agent prompt contract
docs_sync: required
docs_sync_reason: Updates validation behavior documented in PIPELINE.md and skills
---

# Plan: Stage-Based Validation Split

## Context

PRD: `docs/prds/orchestrator-liveness-and-validation-redesign-prd.md`

Agents currently run the full test suite during `aet-implement`, causing long sessions and redundant work. The redesign splits validation by stage: `aet-implement` runs targeted tests only; `aet-qa` owns the full suite unconditionally. The orchestrator prompt is updated to remove the conflicting "never background validations" instruction.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Implement `select_targeted_tests(changed_files)` helper with path-based floor (same directory or matching name) — M (traces: R-4)
2. Update `aet-implement` skill to run targeted tests only and record which tests were run — M (traces: R-4)
3. Update `aet-qa` skill to explicitly state it runs the full suite unconditionally with no caching — S (traces: R-5)
4. Remove "Run validations … in the foreground and wait for them to finish — never background validations or end your turn while one is still running" from orchestrator prompts — S (traces: R-7)
5. Update orchestrator stage transition to pass targeted-test results from implement to QA for gap analysis — M (traces: R-8)
6. Add regression tests for test selection, stage validation ownership, and prompt content — M (traces: R-4, R-5, R-7, R-8)
7. Update `docs/PIPELINE.md` and `skills/aet-implement/SKILL.md`, `skills/aet-qa/SKILL.md` — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines; see `docs/CONVENTIONS.md`).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against (`blocked_by` that sibling, or blocked by it transitively).
- [ ] This is docs-only and its sole consumer is a single sibling.

Justification: This is the validation workflow core change. It stands alone as an independently shippable behavior change (implement no longer runs full suite). Caching and gap analysis build on it but are separable.

## Rejected Alternatives

- **Parallel validation** — rejected: runs the full suite when it may not be needed; user explicitly excluded this.
- **Agent-driven test selection only** — rejected: too inconsistent; path-based floor provides a minimum coverage guarantee.
- **Keep full suite in implement** — rejected: causes the redundant full-suite runs this redesign eliminates.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/validation.py` (new)
- `skills/aet-implement/SKILL.md`
- `skills/aet-qa/SKILL.md`
- `tests/orchestrator/test_orchestrator.py`
- `tests/test_validation.py` (new)
- `docs/PIPELINE.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] For each new source file introduced by this plan, name the test that will cover it
  - `src/aet/validation.py` (new) → `tests/test_validation.py`
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The validation split is a behavioral change; no persistent state changes.

## Pipeline

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: qa-complete_
_Next step: run `aet-review`_
