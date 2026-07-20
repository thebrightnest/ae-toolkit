---
id: pkg-07-test-reorganization
size: M
blocked_by:
  - pkg-03-lib-extraction
pipeline: standard
status: queued
security_review: skipped
security_review_reason: Test-only file renames and conftest cleanup; no production code or dependency changes.
docs_sync: skipped
docs_sync_reason: Internal test layout is not described in PRD/user docs beyond this plan; no divergence to record.
---

# Plan: Reorganize the Test Suite by Domain (A2)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-4).
~80 flat test files mirror nothing. Reorganize `tests/` into domain packages
mirroring `src/aet/` and finish the conftest cleanup started in pkg-03.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create domain dirs (`tests/backends/`, `tests/telemetry/`,
   `tests/queue/`, `tests/cli/`, `tests/panel/`, `tests/workflow/`, ...) with
   `__init__.py`-free layout (pytest rootdir config); `git mv` each test file
   to its domain — M (traces: R-4)
2. Final `tests/conftest.py` pass: only fixtures remain (telemetry archive
   isolation, `AET_BIN_DIR` isolation, etc.); any residual path logic deleted — S
   (traces: R-4)
3. Update `pyproject.toml` pytest config (testpaths, xdist grouping if needed)
   and `Makefile` test target if paths are referenced — S (traces: R-4)
4. Verify zero test-name collisions across domain dirs and stable pytest-xdist
   behavior — S (traces: R-4)
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Single mechanical reorganization; deliberately separate from pkg-03 so
  import migration and file renames are two reviewable diffs.

## Rejected Alternatives

- **Keep flat tests/** — rejected: the PRD acceptance criteria require domain
  mirroring; flat layout at ~100 files is already a navigation tax.
- **Rename test files to match new module names in the same plan** — rejected:
  rename + rehome in one diff destroys reviewability; renames (if any) are a
  follow-up inside each domain dir.

## Files to Modify

- `tests/test_*.py` → `tests/<domain>/test_*.py` (moves only)
- `tests/conftest.py`
- `tests/fixtures/**` (stays at `tests/fixtures/`; path references updated)
- `pyproject.toml` (pytest config)

## Validation Steps

- [ ] `pytest` collects the same test count before and after (record both
  numbers in the PR description)
- [ ] Full suite green including `pytest-xdist` parallel run
- [ ] `tests/fixtures/` references resolve (skills-lint fixtures,
  validate-skills fixtures)
- [ ] Named coverage check: every moved test file still exercises its package
  module (e.g. `tests/telemetry/test_telemetry.py` ↔ `src/aet/telemetry.py`)
  — this plan moves tests, it does not add source files
- [ ] R-trace coverage: R-4 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; moves are pure renames with no content edits beyond conftest and
config.

---

*Stage: reviewed*
