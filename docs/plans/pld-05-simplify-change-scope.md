---
id: pld-05-simplify-change-scope
size: S
blocked_by:
  - pld-03-port-prose-assertions
  - pld-04-plans-lint-corpus
pipeline: standard
status: merged
security_review: required
security_review_reason: Changes the condition under which the only safety net skips pytest entirely; landing it before its blockers, or widening the prose classifier by mistake, silently under-tests every prose-only change.
docs_sync: required
docs_sync_reason: The fast-path behavior described in AGENTS.md and CONVENTIONS.md changes from "narrowed pytest" to "no pytest".
---

# Plan: Simplify `change_scope` to Skip Pytest

## Context

PRD: `docs/prds/prose-lint-decoupling-prd.md` (R-6, R-7).

Once pld-03 and pld-04 land, nothing under `tests/` reads the repo's Markdown,
so a prose-only change needs no pytest at all. This plan collects the payoff:
`DOC_COUPLED_TESTS`, `pytest_targets`, and the AST guard in
`tests/test_change_scope.py` are deleted rather than maintained, and the fast
path becomes safe by construction instead of by enumeration.

**This plan must land last.** Both blockers are hard: running it earlier would
skip live doc-coupled tests on exactly the changes that can break them. The
classifier itself, its fail-safe behavior (unknown paths, unreadable diffs, and
empty change sets all resolve to a full run), and their tests all stay.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Verify the precondition before changing anything: no module under `tests/`
   reads Markdown from the checkout outside `tests/`. If it fails, stop — a
   blocker is incomplete — S (traces: R-6)
2. Reduce `src/aet/change_scope.py` to the single rule "prose-only change → run
   no pytest", deleting `DOC_COUPLED_TESTS` and `pytest_targets` while keeping
   `is_code_path`, `changed_paths`, and `decide` with their fail-safe behavior
   — S (traces: R-6)
3. Update `Makefile` so a prose-only change skips the pytest step entirely
   rather than passing a narrowed `PYTEST_TARGETS` — S (traces: R-6)
4. Delete the AST guard from `tests/test_change_scope.py`, keeping the
   classifier and decision tests — S (traces: R-6)
5. Replace it with a standing regression guard: fail when any module under
   `tests/` reads Markdown from the checkout outside `tests/`. This is the
   inverse of the deleted guard — it enforces that the coupling stays absent
   instead of tracking which modules have it — S (traces: R-7)
6. Update the fast-path description in `AGENTS.md` and `docs/CONVENTIONS.md` —
   S (traces: R-6)
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

- **Land this alongside pld-03 or pld-04** — rejected: the skip is only safe
  once *both* couplings are gone. Bundling makes the unsafe intermediate state
  reachable inside a single merge.
- **Keep the AST guard as well as the regression guard** — rejected: with no
  doc-coupled tests left there is no list to police; the inverse guard covers
  the property that actually matters.
- **Keep a token doc-coupled test as a canary** — rejected: it would reintroduce
  the coupling the workstream removes, and a canary that never fires is not
  evidence.

## Files to Modify

- `src/aet/change_scope.py`
- `tests/test_change_scope.py`
- `Makefile`
- `AGENTS.md`
- `docs/CONVENTIONS.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-6 by tasks 1–4, 6; R-7 by task 5
- [ ] No new source files introduced; the new guard lives in the existing
      `tests/test_change_scope.py`
- [ ] Test types: unit tests for the classifier and decision; the regression
      guard is a repo-wide static check
- [ ] A prose-only change runs zero pytest tests and completes `make validate`
      in under 10 seconds
- [ ] A change touching any `.py` file still runs the full suite
- [ ] Adding a test that reads repo Markdown fails the regression guard
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The classifier returns to narrowing rather than skipping,
which is strictly more conservative, so rollback cannot under-test.

## Pipeline

`standard` — changes the condition under which the only gate skips its test
suite.

---

*Stage: merged*
*Next step: run aet-ship*
