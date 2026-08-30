---
id: validation-02-single-run-caching
size: S
work_class: normal
blocked_by:
  - validation-01-stage-based-split
pipeline: minimal
security_review: skipped
security_review_reason: No auth, data-model, or trust-boundary changes; cache is ephemeral and run-scoped
docs_sync: required
docs_sync_reason: Documents caching behavior in validation workflow
---

# Plan: Single-Run Validation Caching

## Context

PRD: `docs/prds/orchestrator-liveness-and-validation-redesign-prd.md`

After validation is split by stage, repeated targeted validations within a single run still re-run tests when files haven't changed. This plan adds file-hash-based caching scoped to a single orchestration run. The cache is invalidated when source, test, or dependency files change. Cross-run caching is explicitly out of scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Implement `ValidationCache` class with SHA-256 file hashing for `src/`, `tests/`, `pyproject.toml`, and lockfiles — M (traces: R-6)
2. Integrate cache into `aet-implement` targeted validation: skip re-run when hash matches — S (traces: R-6)
3. Store cache in run-scoped telemetry directory, not the worktree — S (traces: R-6)
4. Add regression tests for cache hit, cache miss on file change, and no cross-run persistence — S (traces: R-6)
5. Update `docs/PIPELINE.md` with caching behavior — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines — re-evaluate against the full guardrail model; justify above 1500

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines; see `docs/CONVENTIONS.md`).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against (`blocked_by` that sibling, or blocked by it transitively).
- [ ] This is docs-only and its sole consumer is a single sibling.

Justification: This builds on validation-01 but is independently shippable (validation-01 works without caching). The diff is moderate and focused on one new module.

## Rejected Alternatives

- **Cross-run caching** — rejected: risks stale results across runs; single-run caching captures the redundancy within a session.
- **Commit-based invalidation** — rejected: too broad; a docs commit would invalidate the cache. File-hash is precise.
- **Cache in worktree** — rejected: worktrees are ephemeral; run-scoped telemetry directory is the correct lifetime.

## Files to Modify

- `src/aet/validation.py`
- `src/aet/validation_cache.py` (new)
- `tests/test_validation_cache.py` (new)
- `docs/PIPELINE.md`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] For each new source file introduced by this plan, name the test that will cover it
  - `src/aet/validation_cache.py` (new) → `tests/test_validation_cache.py`
- [ ] Distinguish test types: unit tests (single layer), integration tests (cross-layer), API boundary tests (frontend ↔ backend contract)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The cache is additive; removing it falls back to always running validations.

## Pipeline

| Value      | Behavior                                            |
| ---------- | --------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

Only change this after considering task risk. Auth, data-model, API, and dependency changes should usually use `standard` or `full`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
