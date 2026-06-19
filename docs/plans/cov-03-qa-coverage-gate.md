---
id: cov-03-qa-coverage-gate
blocked_by: []
size: M
---

# Plan: aet-qa — Coverage as a First-Class QA Gate

## Context

PRD: `docs/prds/auth-infra-blind-spots-prd.md` — Story 3.

`aet-qa` runs the test suite and checks critical user flows, but never checks coverage. A new file with zero tests passes QA silently. The fix: add a coverage step to the `qa` command procedure that fails the tier if any new or modified source file has 0% coverage.

**ADR 001 framing note:** The coverage gate implements the test coverage completeness domain from the Cross-Cutting Completeness framework (ADR `docs/adr/001-cross-cutting-completeness.md`, extended by ADR 008 created in cov-02). When editing the skill, frame the coverage step as: "When a diff introduces new source files, verify each has coverage > 0% — the completeness property for the test coverage domain."

## Tasks

1. Edit `aet-qa/SKILL.md` — in the `qa` command procedure, after "Run automated test suite", add a "Coverage check" step: run the test suite with coverage reporting; identify all source files that are new or modified in the current diff; any new file at 0% coverage is a QA failure at all tiers; any modified file where all changed lines are uncovered is flagged for human review. — **S**

2. Edit `aet-qa/SKILL.md` — in the QA report spec, add a "Coverage" section: list files checked, their coverage %, and which (if any) failed the 0% gate. — **S**

3. Edit `aet-qa/SKILL.md` — add a note on coverage tooling: use language-appropriate defaults (`php artisan test --coverage` for Laravel, `vitest --coverage` / `jest --coverage` for JS/TS); do not hardcode a tool — use what the project already has configured. — **S**

4. Merge branch to main and verify integration — **S**

## Dependencies

None — all tasks are in `aet-qa/SKILL.md`.

## Validation Steps

- [ ] `make validate` passes
- [ ] `aet-qa/SKILL.md` is under 400 lines after changes
- [ ] Reading the updated `qa` procedure, a new file with 0% coverage produces a failure result, not a warning
- [ ] The QA report spec includes a coverage section
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert edits to `aet-qa/SKILL.md`.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
