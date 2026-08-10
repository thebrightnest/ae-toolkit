---
id: cov-04-review-tests-lens
blocked_by: []
size: M
---

# Plan: aet-review — Tests Lens as Hard Coverage Check

## Context

PRD: `docs/prds/auth-infra-blind-spots-prd.md` — Story 4.

The `Tests` lens in `aet-review` currently asks "are there tests for new behavior? Are edge cases covered?" — this is too vague to catch a new file that has no test at all. The fix: make the lens a concrete coverage completeness check with a hard-fail rule, and add an explicit check for API boundary tests on vertical slices.

**ADR 001 framing note:** The Tests lens rewrite applies the Cross-Cutting Completeness framework (ADR `docs/adr/001-cross-cutting-completeness.md`, extended by ADR 008 from cov-02) to the review stage. The lens should be framed as: "When a diff introduces new source files, verify the test coverage completeness property — at least one test references each file." Follow the established pattern: detail goes in `references/test-coverage-check.md`, the lens in SKILL.md points to it.

## Tasks

1. Edit `aet-review/SKILL.md` — rewrite the `Tests` lens in the `review` procedure: replace "are there tests for new behavior? Are edge cases covered?" with a two-part check: (a) for each new source file in the diff, verify at least one test file imports or references it — if none exists, classify as **fix-now** (not flag-for-human); (b) if the diff introduces both a new backend route/controller and new frontend API client code, verify an API boundary test exists — if none exists, classify as **fix-now**. — **S**

2. Edit `aet-review/SKILL.md` — add a note defining "new source file" for this lens: any file added by the diff that is not a test file, config file, migration, seed, or type-only definition. The reviewer applies judgment — a file exporting only interfaces does not require a test; a file containing business logic, a controller, an observer, or a job does. Point to `references/test-coverage-check.md` for the mechanical procedure. — **S**

3. Create `aet-review/references/test-coverage-check.md` — mechanical procedure for the Tests lens, following the structure of `css-completeness-check.md`: when to run, procedure (enumerate new source files from diff, grep for references in test files, report fix-now if none found), and a note on what counts as a "source file" vs. a file that can be skipped (config, types, migrations). Keep under 80 lines. — **S**

4. Merge branch to main and verify integration — **S**

## Dependencies

Task 2 references the file created in Task 3 — write Task 3 first.

## Validation Steps

- [ ] `make validate` passes
- [ ] `aet-review/SKILL.md` is under 400 lines after changes
- [ ] `aet-review/references/test-coverage-check.md` exists and lint passes
- [ ] Reading the updated `Tests` lens: a new controller with no test is classified as fix-now, not flag-for-human
- [ ] Reading the updated `Tests` lens: a diff adding both a new API endpoint and new frontend fetch code without a boundary test is classified as fix-now
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert edits to `aet-review/SKILL.md`; delete `aet-review/references/test-coverage-check.md` if created.

---

## Disposition (2026-08-10, structural-review-tier-2 scope validation)

**Superseded by `t2r-08-boundary-contract-lens`.** The review-side tests/coverage lens is delivered mechanically there (diff-triggered, refuse-pass in code) instead of as this plan's scripted prose procedure.

---

_Stage: abandoned_
_Next step: none — superseded by t2r-08_
