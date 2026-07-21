---
id: pld-02-docs-lint-engine
size: M
blocked_by:
  - pld-01-governance-as-data-adr
pipeline: standard
status: queued
security_review: required
security_review_reason: New parser reading a repo-controlled rules file into the validate gate; must use yaml.safe_load and must not evaluate rule content, or a rules file becomes an execution vector.
docs_sync: required
docs_sync_reason: AGENTS.md command table and the validate-gate description gain the `aet docs lint` stage.
---

# Plan: `aet docs lint` Rule Engine

## Context

PRD: `docs/prds/prose-lint-decoupling-prd.md` (R-2, R-3).
Decision: ADR-040, delivered by pld-01.

Builds the engine the ADR specifies. No invariants move in this plan — porting
is pld-03 — so this lands with the engine, its own tests, and an empty or
minimal rules file. That keeps the engine reviewable on its own and means a
bug here cannot silently drop a live governance check.

Naming follows the noun-scoped, nested-verb convention established by gib-06
and carried by `docs/prds/namespace-consolidation-prd.md`: `aet docs lint`, not
a hyphenated `aet docs-lint`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Implement the rule model and evaluator in `src/aet/docs_lint.py`: load
   rules with `yaml.safe_load`, evaluate `must_contain`, `must_not_contain`,
   their section-scoped variants, and `path_exists` / `path_absent` — M
   (traces: R-2)
2. ✓ Give every rule a required `reason` field and render failures as
   `<file>: <reason>` with the offending expectation, so messages stay at least
   as diagnostic as the assertions they replace — S (traces: R-2)
3. ✓ Decide and implement the posture for a rule whose target file is missing,
   per the PRD open question: fail-closed by default, with `path_absent`
   covering deliberately retired files — S (traces: R-2)
4. ✓ Wire `aet docs lint` into the CLI dispatcher and into `make validate` ahead
   of pytest, preserving fail-fast ordering — S (traces: R-3)
5. ✓ Unit-test the evaluator in `tests/scripts/test_docs_lint.py`: one case per
   rule type, section scoping, a missing-target file, a malformed rules file,
   and message formatting — M (traces: R-2, R-3)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

## Rejected Alternatives

- **Port the invariants in this plan too** — rejected: bundling the engine with
  the migration means a defect in the evaluator can silently drop a live
  governance check in the same merge that introduces it. Splitting lets pld-03
  demonstrate each ported rule failing against a broken doc.
- **Ship without a `reason` field** — rejected: the current assertions carry
  messages like "SKILL.md should default to impact-scoped tests"; degrading
  those to "substring not found" would be a regression in diagnosability.
- **`yaml.load` with a custom loader** — rejected: `safe_load` is sufficient for
  a plain rule schema, and anything more permissive turns a data file into an
  execution surface inside the only gate.

## Files to Modify

- `src/aet/docs_lint.py` (new)
- `src/aet/cli/main.py` (dispatcher registration)
- `.agents/doc-rules.yaml` (new, minimal or empty)
- `tests/scripts/test_docs_lint.py` (new)
- `Makefile`
- `AGENTS.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-2 by tasks 1–3, 5; R-3 by tasks 4–5
- [ ] New source `src/aet/docs_lint.py` is covered by `tests/scripts/test_docs_lint.py`
- [ ] Test types: unit tests for the evaluator; one integration test asserting
      `make validate` invokes the stage and fails the gate on a rule violation
- [ ] `aet docs lint` runs before pytest in `make validate`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Because no invariants have moved yet, removing the stage
restores the previous gate exactly; the pytest assertions are still live.

## Pipeline

`standard` — new parsing code inside the validation gate.

---

*Stage: synced*
*Next step: run `aet-ship`*
