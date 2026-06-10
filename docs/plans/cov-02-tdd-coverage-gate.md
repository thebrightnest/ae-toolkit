# Plan: aet-tdd — Coverage Completeness Gate + API Boundary Mandate

## Context

PRD: `docs/prds/auth-infra-blind-spots-prd.md` — Story 2.

`aet-tdd`'s `plan-tests` step currently lists behaviors "to test" based on what the agent imagines, not on a systematic enumeration of what the plan introduces. The completion protocol checks only that tests pass — never that every new file has coverage. The result: entire modules ship with zero tests.

Two changes:
1. Make `plan-tests` derive its test list from the plan's file list, not from the agent's intuition.
2. Add a coverage completeness check before `tdd-complete`.
3. For vertical slices, mandate an API boundary integration test.

A reference file covers API boundary test patterns so the skill text stays readable.

**ADR 001 framing note:** Changes to `aet-tdd/SKILL.md` add two new domains to the Cross-Cutting Completeness framework (ADR `docs/adr/001-cross-cutting-completeness.md`): (1) test coverage — "when a plan introduces new source files, every file must have at least one test"; (2) API boundary contract — "when a vertical slice introduces both a backend endpoint and a frontend consumer, an API boundary test must exist." Frame edits accordingly.

## Tasks

1. Edit `aet-tdd/SKILL.md` — rewrite the `plan-tests` procedure step 2: "List the behaviors to test" → "Enumerate every new source file or class introduced by the plan. For each, identify the behavior(s) it provides and write at least one test name. This list is the minimum test plan — behaviors beyond it are optional additions." — **S**

2. Edit `aet-tdd/SKILL.md` — add a "Coverage completeness" step to the completion protocol (before updating the plan.md footer): run the test suite with coverage; list all new source files and their coverage %; any file at 0% is a blocking failure — the `tdd-complete` stage cannot be set until every new file has at least one test touching it. — **S**

3. Edit `aet-tdd/SKILL.md` — add an "API boundary integration test" mandate: when the active plan is a vertical slice that introduces both a backend endpoint and frontend code that calls it, `plan-tests` must include an API boundary test. Reference `references/api-boundary-tests.md` for patterns. — **S**

4. Create `aet-tdd/references/api-boundary-tests.md` — explain what an API boundary test is (not E2E, uses HTTP mocking), when it is required (vertical slice with both backend route and frontend consumer), and give concrete examples for common stacks (Laravel `Http::fake()` for backend; MSW or `vi.fn()` fetch mock for frontend React). Also add a clarifying note to `aet-tdd/references/mocking.md` under "File system": filesystem mocking is acceptable for I/O performance, but must NOT be used in tests whose purpose is validating path resolution or storage configuration — mock the FS there and you hide the bug. Keep both files under 80 lines. — **S**

5. Create `docs/adr/008-test-coverage-completeness.md` — document test coverage and API boundary contract as two new domains in the Cross-Cutting Completeness framework (companion to ADR 001). Decision: hard gate (blocking failure) rather than soft suggestion. Rationale: zero-coverage files produce silent regressions; the cost of the gate is low (coverage runs with the test suite); the trade-off was explicitly evaluated and decided. — **S**

6. Merge branch to main and verify integration — **S**

## Dependencies

Task 3 references the file created in Task 4 — write Task 4 first (or in the same session). Task 5 (ADR) has no dependencies and can be written in any order.

## Validation Steps

- [ ] `make validate` passes
- [ ] `aet-tdd/SKILL.md` is under 400 lines after changes
- [ ] `aet-tdd/references/api-boundary-tests.md` exists and lint passes
- [ ] `aet-tdd/references/mocking.md` includes the filesystem/path-resolution clarification
- [ ] `docs/adr/008-test-coverage-completeness.md` exists and references ADR 001
- [ ] Reading the updated `plan-tests` procedure, a new file introduced by the plan cannot be omitted from the test list
- [ ] Reading the updated completion protocol, a file with 0% coverage causes the step to block rather than continue
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert edits to `aet-tdd/SKILL.md` and `aet-tdd/references/mocking.md`; delete `aet-tdd/references/api-boundary-tests.md` and `docs/adr/008-test-coverage-completeness.md` if created.

---

*Stage: plan-approved*
*Next step: run `aet-pipeline-implement` or `aet-work`*
