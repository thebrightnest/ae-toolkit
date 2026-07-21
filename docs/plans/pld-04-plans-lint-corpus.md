---
id: pld-04-plans-lint-corpus
size: S
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: Relocates an existing read-only corpus classifier into a validate stage; no new dependencies, no writes, no execution surface.
docs_sync: required
docs_sync_reason: AGENTS.md command table and the validate-gate description gain the `aet plans lint` stage.
---

# Plan: `aet plans lint` Corpus Stage

## Context

PRD: `docs/prds/prose-lint-decoupling-prd.md` (R-5).

`tests/orchestrator/test_status_liveness_contract.py::test_corpus_classifier_matches_known_live_set`
reads the live `docs/plans/*.md` corpus and asserts that only statusless and
terminal plans classify as settled. It is the one doc-coupled check that runs
real `plan_parser` / `plan_validate` logic, so it cannot become a string rule —
it needs a code stage of its own.

This is the check that makes `docs/plans/` edits require pytest today, and
since every doc-only commit in recent history touches `docs/plans/`, it is the
binding constraint on the fast path. It is independent of the docs-lint engine
and can proceed in parallel with pld-01 through pld-03.

The module's other ~200 lines are ordinary temp-dir unit tests of
`plan_validate` and stay in pytest untouched.

The same test also carries a hardcoded census (`len(plan_files) == 243`,
`live == 12`, commented "Update when the corpus changes"). It fires on every
plan addition — drafting this workstream's own five plans broke it and required
a Python edit — while the divergence assertion above it already catches genuine
misclassification. Task 4 settles what happens to it rather than porting the
tax into the new stage.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add a corpus classifier check as `aet plans lint`, reusing `plan_parser` and
   `plan_validate` so the classification logic has exactly one implementation —
   S (traces: R-5)
2. Wire the stage into `make validate` ahead of pytest, alongside the other
   cheap checks — S (traces: R-5)
3. Report violations per offending plan file — which plan, its `status`, and
   why it misclassifies — rather than as a set-difference dump — S
   (traces: R-5)
4. Decide the hardcoded census's fate rather than porting it: drop it in favour
   of the divergence assertion, or replace it with a check that does not need
   editing whenever a plan is added (for example, asserting that no plan
   carries an unrecognized `status`). Record the choice in the plan before
   implementing — S (traces: R-5)
   - **Decision:** Drop the hardcoded counts. The classifier already reports
     every plan whose `is_settled_plan()` classification disagrees with its
     committed `status`, so a per-plan divergence assertion is sufficient. An
     unrecognized `status` is surfaced as an explicit "invalid status" finding
     rather than a census mismatch, removing the need to edit Python whenever
     the corpus grows.
5. Remove `test_corpus_classifier_matches_known_live_set` from
   `tests/orchestrator/test_status_liveness_contract.py`, leaving the module's
   temp-dir unit tests intact, and drop the now-unused `_REPO_ROOT / "docs"`
   anchor — S (traces: R-5)
6. Cover the stage in `tests/plan/test_plans_lint.py` using temp corpora: a
   clean corpus, a misclassifying plan, and an empty corpus — S (traces: R-5)
7. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 3 files or 50 lines.
- [x] The work cannot share a branch/PR with related tasks.

## Rejected Alternatives

- **Drop the corpus check and rely on `init-queue` failing** — rejected: it
  would move detection from validate time to queue-rebuild time, and a known
  `init-queue` ordering bug already makes stale frontmatter hard-fail the
  rebuild. Catching it at the gate is the point.
- **Express it as a docs-lint rule** — rejected: it evaluates
  `plan_validate.is_settled_plan()` against parsed frontmatter, which is logic,
  not string matching.
- **Leave it in pytest** — rejected: `docs/plans/` is touched by every doc-only
  commit in recent history, so leaving it would preserve the allowlist and the
  AST guard, forfeiting most of the workstream's benefit.

## Files to Modify

- `src/aet/plan_validate.py` or a new `src/aet/plans_lint.py` (stage entry)
- `src/aet/cli/main.py` (dispatcher registration)
- `tests/orchestrator/test_status_liveness_contract.py`
- `tests/plan/test_plans_lint.py` (new)
- `Makefile`
- `AGENTS.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-5 covered by tasks 1–6
- [ ] Any new source file is covered by `tests/plan/test_plans_lint.py`
- [ ] Test types: unit tests over temp corpora; one integration check that
      `make validate` fails when a plan in the real corpus misclassifies
- [ ] Introducing a misclassifying plan fails `make validate` with a message
      naming that plan file
- [ ] `test_status_liveness_contract.py` no longer reads the real corpus
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit; the pytest case returns and the stage disappears. Safe at
any point before pld-05, which is the plan that depends on this coupling being
gone.

## Pipeline

`standard` — removes a live repo-health check from pytest and re-homes it.

---

*Stage: implemented*
*Next step: run `aet-qa`*
