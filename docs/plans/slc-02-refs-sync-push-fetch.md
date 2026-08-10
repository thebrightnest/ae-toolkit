---
id: slc-02-refs-sync-push-fetch
size: M
work_class: critical
blocked_by:
  - slc-01-content-addressed-ledger-events
pipeline: standard
status: queued
security_review: required
security_review_reason: adds network transport of queue state to the forge remote
docs_sync: required
docs_sync_reason: changes the operator-visible durability posture documented in skills and CONTEXT.md
---

# Plan: Refs Sync — Push and Fetch for `refs/aet/*`

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-4, R-3). ADR-055. The
git-refs backend's own docstring states "Nothing here pushes `refs/aet/*`:
the backend is local-only by default." One refspec pushed and fetched
against the origin every AET project is guaranteed to have makes state
travel with the repo — inside the repository, outside the working tree,
invisible to every PR diff (deployment configurations 2, 3, 4).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Push `refs/aet/*` after each state-mutating command boundary (sprint add,
   set-stage, gate submit, ship); best-effort — a failed push never blocks
   local operation and is retried at the next boundary — M (traces: R-4)
2. Fetch `refs/aet/*` at the start of operational commands that read or
   write queue state (`aet run`, `run-one`, `status`, `next`, `state`,
   `gate submit`, `sprint add`, `ship`) — S (traces: R-4)
3. Closure-mandatory push: `aet ship` close fails loudly with a named
   remedy when the refs push fails — S (traces: R-4)
4. Two-clone fixture test: both clones append events offline, both push,
   fetch yields the union with no conflict; guard test that `~/.aet` paths
   are never pushed — M (traces: R-3, R-4)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: sync is an independently observable behavior (state on a
  second clone) with its own failure modes.
- [x] Expected diff (~350 lines + fixture tests) exceeds PR overhead.
- [x] Cannot share a branch with slc-01 (the store must exist first) or
  slc-04 (closure transaction is a separate concern; only its push
  guarantee is shared, and task 3 is one call site).

## Rejected Alternatives

- **Push on every micro-mutation** — rejected: couples interactive latency
  to the network for no freshness the four configurations need; closure is
  the only boundary requiring durability synchronously.
- **A config toggle for sync** — rejected: matches the project's no-mode
  principle (ADR-054 decision 5); refs sync is the behavior.
- **`git notes` instead of a ref namespace** — rejected: `refs/aet/*`
  already exists as the backend layout; notes would be a second mechanism.

## Files to Modify

- `src/aet/backends/git_refs_backend.py`
- `src/aet/backends/base.py`
- `src/aet/cli/ship.py` (mandatory closure push)
- `tests/backends/test_git_refs_sync.py` (new)
- `tests/fixtures/` (two-clone fixture)

## Validation Steps

- [ ] Lint passes (`make lint-py`)
- [ ] Tests pass (`make test`)
- [ ] `tests/backends/test_git_refs_sync.py` covers the new sync surface:
  offline-tolerant mutation, deferred retry, closure push failure naming
  its remedy (integration, two-clone fixture)
- [ ] Two clones each append offline; after both push, fetch produces the
  union of events with no manual reconciliation (integration)
- [ ] No code path pushes `~/.aet` content (unit guard)
- [ ] R-trace coverage: R-3, R-4 covered by tasks 1–4
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Pushed refs on origin are harmless without the code that
reads them; no data migration is involved.

## Pipeline

`standard` — infrastructure/transport change touching persisted state
(risk override per ADR-047).

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*
