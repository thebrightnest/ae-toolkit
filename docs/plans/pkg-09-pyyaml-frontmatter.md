---
id: pkg-09-pyyaml-frontmatter
size: M
blocked_by:
  - pkg-03-lib-extraction
pipeline: standard
status: merged
security_review: required
security_review_reason: Adds PyYAML as the package's first runtime dependency — supply-chain review per vgr-04 precedent.
docs_sync: required
docs_sync_reason: PRD R-6 divergence notes (any accepted-input differences vs. the hand-rolled parser) must be recorded.
---

# Plan: Replace Hand-Rolled Frontmatter Parsing with PyYAML (A4)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-6).
`src/aet/plan_parser.py` hand-parses YAML frontmatter (see
`_frontmatter_body` / `parse_frontmatter`). Replace the YAML subset parser
with PyYAML (`yaml.safe_load`), keeping the same accepted/rejected inputs.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. ✓ Add `pyyaml` to `pyproject.toml` runtime dependencies — S (traces: R-6)
2. ✓ Rewrite `parse_frontmatter` (and private helpers) in
   `src/aet/plan_parser.py` to use `yaml.safe_load`; preserve the None/empty
   contract for missing or unclosed frontmatter and for non-mapping values — M
   (traces: R-6) [Changed: added `_normalize_frontmatter_body` shim to keep the
   existing `docs/plans/*.md` corpus parsing without editing merged plan files]
3. ✓ Migrate `tests/test_plan_validate.py` / parser tests: every existing case
   must pass unmodified; add cases for inputs the hand-rolled parser accepted
   but `safe_load` rejects (or vice versa) and pin the chosen behavior — S
   (traces: R-6) [Added: typed-scalar, nested mapping, non-mapping top-level,
   and empty-scalar edge cases in `tests/test_init_queue_sync.py`]
4. ✓ Record any intentional accepted-input differences in the PRD divergence
   note and in `references/` for the plan frontmatter contract — S (traces: R-6)
   [Added: `aet-work/references/frontmatter-contract.md`]
5. [Deferred: pending the ship stage] Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Single-module swap; not batchable with pkg-10 (different module,
  different dependency, separate review).

## Rejected Alternatives

- **Keep the hand-rolled parser** — rejected: PRD R-6; bespoke parsers for
  real formats are a standing bug factory.
- **`ruamel.yaml`** — rejected: heavier dependency; round-trip comment
  preservation is not needed (frontmatter is read-only here).

## Files to Modify

- `pyproject.toml`
- `src/aet/plan_parser.py`
- `tests/test_plan_validate.py` (and any dedicated parser test file)
- `docs/prds/aet-package-extraction-prd.md` (divergence note, if any)

## Validation Steps

- [ ] `tests/test_plan_validate.py` (named, existing) passes unmodified;
  new edge-case tests named in task 3 pass
- [ ] `aet plan validate` and `aet sync` behave identically on the existing
  `docs/plans/*.md` corpus (all current plan files parse to the same values)
- [ ] `make validate` green
- [ ] R-trace coverage: R-6 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; PyYAML stays declared but unused for one commit is harmless, or
drop the pin in the same revert.

---

*Stage: merged*
*Next step: run `aet-ship`*
