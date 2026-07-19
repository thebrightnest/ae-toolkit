---
id: pkg-03-lib-extraction
size: L
blocked_by:
  - pkg-02-package-skeleton
pipeline: standard
status: approved
security_review: skipped
security_review_reason: Pure relocation of existing code with import rewrites; no new dependencies, behavior, or trust-boundary changes.
docs_sync: required
docs_sync_reason: PRD R-2/R-3 traceability must record where each lib module landed in the package.
---

# Plan: Extract `aet-work/lib` into the Package (A1b)

## Context

PRD: [aet-package-extraction](../prds/aet-package-extraction-prd.md) (R-2, R-3,
R-4). Move all 28 modules of `aet-work/lib/` into `src/aet/` as real package
modules, rewrite every import site (bin scripts, tests, panel, scripts/), and
delete the `sys.path.insert` hacks. Behavior-preserving: same public functions,
same CLI behavior, same test suite expectations.

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> Exceeds the file-count guardrail (~30 moved modules + ~100 import sites).
> Not splittable further without broken intermediate states: the lib import
> graph is densely interconnected (`aet_queue` alone is imported by nearly
> every binary and test), so a partial move forces re-export shims whose
> creation and removal doubles the churn. The diff is rename-dominated with
> near-zero per-file complexity; session feasibility is preserved.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. `git mv aet-work/lib/*.py aet-work/lib/backends aet-work/lib/projections`
   into `src/aet/` preserving module names (`aet/queue.py`,
   `aet/backends/*`, `aet/projections/*`, ...); decide mechanical renames
   (`aet_queue.py` → `aet/queue.py`) and record them in the PRD divergence
   note — L (traces: R-2)
2. Rewrite intra-package imports to `from aet.x import ...` (absolute) — M
   (traces: R-3)
3. Update all bin scripts (`aet-work/bin/*`, `aet-ship/bin/ship`,
   `aet-evolve/bin/*`, `aet-setup/bin/*`) to drop `sys.path.insert` and import
   the installed package — M (traces: R-3)
4. Update `aet-work/panel/serve` and `scripts/test-*.py` import sites — S
   (traces: R-3)
5. Update `tests/conftest.py` (remove lib `sys.path` insertion; keep isolation
   fixtures) and every test file's imports; verify no bare `import telemetry`
   style imports remain — L (traces: R-4)
6. Move `aet-work/workflows/` → `src/aet/workflows/` as package data (declare
   in `pyproject.toml`); fix `_PACKAGED_DIR` in `src/aet/workflow.py`
   (`Path(__file__).parent / "workflows"`); update the **Workflow** glossary
   path in `CONTEXT.md` — S (traces: R-2, R-3)
7. Delete now-empty `aet-work/lib/` and `aet-setup/lib/` (harness_guard moves
   in pkg-06; leave its shim until then — record in divergence note) — S
   (traces: R-2)
8. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] One cohesive migration; batching with pkg-04 was considered and rejected
  (see Rejected Alternatives).

## Rejected Alternatives

- **Move with re-export shims left in `aet-work/lib/`** — rejected: the shim
  layer doubles file churn (create + later delete) and lets stale import paths
  linger undetected; a single sweep fails loudly and immediately.
- **Module-by-module incremental moves** — rejected: the import graph is too
  dense; every partial state still touches most import sites, multiplying PRs
  without reducing risk.
- **Batching lib + bin moves into one plan** — rejected: two reviewable
  failure domains (library relocation vs CLI relocation); keeping them
  separate preserves bisectability.

## Files to Modify

- `aet-work/lib/**` → `src/aet/**` (move; incl. `backends/`, `projections/`)
- `aet-work/workflows/` → `src/aet/workflows/` (package data)
- `pyproject.toml` (package-data declaration)
- `CONTEXT.md` (**Workflow** glossary packaged-path reference)
- `aet-work/bin/*` (import lines only)
- `aet-ship/bin/ship`, `aet-evolve/bin/*`, `aet-setup/bin/*` (import lines only)
- `aet-work/panel/serve` (import lines only)
- `scripts/test-aet-state.py`, `scripts/test-telemetry.py` (import lines only)
- `tests/conftest.py`, `tests/test_*.py` (import lines only)

## Validation Steps

- [ ] `grep -rn "sys.path.insert" aet-work aet-ship aet-evolve aet-setup src/`
  returns nothing
- [ ] `grep -rln "^import telemetry\|^from telemetry\|^import aet_queue" tests/`
  returns nothing (spot-check: bare-module imports gone)
- [ ] Full pytest suite passes unmodified in behavior — the existing ~80 test
  files (e.g. `tests/test_backends.py`, `tests/test_telemetry.py`,
  `tests/test_orchestrator.py`) are the named coverage for every moved module;
  no new source behavior is introduced, so no new tests are required
- [ ] `make validate` green (lint-py + skills-lint + workflow lint + validator)
- [ ] `aet status`, `aet report` run identically from the repo checkout
- [ ] R-trace coverage: R-2 by tasks 1, 6, 7; R-3 by tasks 2–4, 6; R-4 by task 5; no
  unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge — all changes are moves/imports in one commit range;
the old layout returns wholesale. No data or state files are touched.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
