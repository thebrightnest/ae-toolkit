---
id: pkg-02-package-skeleton
size: M
blocked_by:
  - pkg-01-decision-records
pipeline: standard
status: queued
security_review: required
security_review_reason: Introduces pyproject.toml and a build backend — the repo's first packaging/build supply-chain surface (vgr-04 precedent for first-dependency review).
docs_sync: required
docs_sync_reason: Makefile tooling table and AGENTS.md tooling reference must match the new editable-install workflow.
---

# Plan: Python Package Skeleton (A1a)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-2,
R-4). Roadmap phase A1, first step. Create the installable package shell that
later extraction plans fill in. No tool code moves in this plan; the goal is
that `pip install -e .` works and `make validate` exercises the installed
package (initially an empty `aet` package).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `pyproject.toml`: project metadata (`aet`, version `0.1.0`), src
   layout config, zero runtime dependencies for now, optional-dependencies
   group `dev` absorbing `requirements-dev.txt` (pytest, pytest-xdist, ruff);
   build backend hatchling — S (traces: R-2)
2. Create `src/aet/__init__.py` with `__version__` — S (traces: R-2)
3. Update `Makefile`: `make test`/`make validate` ensure the package is
   installed editable (`pip install -e .[dev]` or `uv pip install -e .[dev]`);
   document plain-pip path (no uv requirement, per PRD technical notes) — S
   (traces: R-4)
4. Delete `requirements-dev.txt`; update `AGENTS.md` tooling references and
   pre-commit/dev-install instructions to `pip install -e .[dev]` — S
   (traces: R-4)
5. Add `tests/test_packaging.py`: package imports, `__version__` present,
   console entry point declared in pyproject metadata — S (traces: R-2)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Not a near-identical addition; single cohesive packaging change.

## Rejected Alternatives

- **uv-only install path** — rejected: PRD technical notes require plain
  `pip install -e .` to keep working in Track A; uv optional for speed.
- **setuptools backend** — rejected in favor of hatchling: simpler src-layout
  config, no `setup.py`/`MANIFEST.in` sprawl; build backend is a build-time
  only dependency (not shipped to runtime).
- **Flat `aet/` package at repo root** — rejected: src layout prevents
  accidental imports from the working tree and matches the roadmap target.

## Files to Modify

- `pyproject.toml` (new)
- `src/aet/__init__.py` (new)
- `Makefile`
- `requirements-dev.txt` (delete)
- `AGENTS.md` (tooling table + dev-install lines)
- `tests/test_packaging.py` (new)

## Validation Steps

- [ ] `pip install -e .[dev]` succeeds in a fresh venv; `python -c "import aet"` works
- [ ] `make validate` passes unchanged
- [ ] `tests/test_packaging.py` (new unit test) covers `src/aet/__init__.py`
      and the pyproject entry-point declaration
- [ ] R-trace coverage: R-2 covered by tasks 1, 2, 5; R-4 (partial — dev-deps
      group only) by tasks 3, 4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; the package is inert (no tool code imports it yet), so
removal cannot break existing behavior.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
